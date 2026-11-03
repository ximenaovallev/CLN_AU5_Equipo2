"""Adaptador SQLAlchemy de IUnitOfWork y de los cuatro repositorios (Unidad 5).

Por qué existe:
  * ADR-002 sigue vigente: el BRD NO define la tecnología de persistencia. Este adaptador NO es
    esa decisión; es una segunda implementación de los puertos para las pruebas de integración.
  * Permite verificar commit/rollback reales con SQLAlchemy (SQLite en memoria, nunca producción).
  * Cierra el hallazgo SOLID #5 de la U3 ("la sustitución real no se ha probado"): los mismos
    handlers corren sin cambios sobre EnMemoriaUnitOfWork y sobre SqlAlchemyUnitOfWork.

Modelo de almacenamiento: estilo documental. Cada agregado/entidad se guarda serializado en
`datos` (pickle) con columnas consultables (`tipo`, `id`, `estado`). Pickle solo es aceptable
porque la base es local y de prueba; un adaptador productivo usaría un mapeo explícito.
"""
from __future__ import annotations

import copy
import pickle
from collections.abc import Callable
from typing import Any, Self

from sqlalchemy import LargeBinary, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from ..aplicacion.puertos import IUnitOfWork
from ..dominio.comunes import EntidadNoEncontrada
from ..dominio.cotizacion import Cotizacion
from ..dominio.orden_de_servicio import OrdenDeServicio
from ..dominio.recursos import Operador, Unidad
from ..dominio.repositorios import (
    ICotizacionRepository,
    IOperadorRepository,
    IOrdenServicioRepository,
    IUnidadRepository,
)


class Base(DeclarativeBase):
    pass


class AgregadoRow(Base):
    __tablename__ = "agregados"
    tipo: Mapped[str] = mapped_column(String(20), primary_key=True)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    estado: Mapped[str] = mapped_column(String(30))
    datos: Mapped[bytes] = mapped_column(LargeBinary)


def crear_fabrica_de_sesiones(url: str = "sqlite+pysqlite:///:memory:") -> sessionmaker[Session]:
    """Motor aislado por llamada. Con `:memory:` cada prueba obtiene su propia base vacía."""
    engine = create_engine(url, poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


class _RepositorioSql:
    def __init__(self, uow: SqlAlchemyUnitOfWork, tipo: str, nombre: str, estado_de: Callable[[Any], str]):
        self._uow, self._tipo, self._nombre, self._estado_de = uow, tipo, nombre, estado_de

    def obtener_por_id(self, id: str):
        row = self._uow.sesion.get(AgregadoRow, (self._tipo, id))
        if row is None:
            raise EntidadNoEncontrada(f"No existe {self._nombre} con identificador {id}.")
        return pickle.loads(row.datos)

    def guardar(self, objeto) -> None:
        # Los eventos de dominio NO se persisten: se publican tras confirmar() (ADR-002).
        copia = copy.copy(objeto)
        if hasattr(copia, "_eventos"):
            copia._eventos = []
        self._uow.sesion.merge(AgregadoRow(tipo=self._tipo, id=objeto.id, estado=self._estado_de(objeto),
                                           datos=pickle.dumps(copia)))


class SqlCotizacionRepository(_RepositorioSql, ICotizacionRepository):
    def __init__(self, uow: SqlAlchemyUnitOfWork):
        super().__init__(uow, "cotizacion", "la cotización", lambda c: c.estado.value)


class SqlOrdenServicioRepository(_RepositorioSql, IOrdenServicioRepository):
    def __init__(self, uow: SqlAlchemyUnitOfWork):
        super().__init__(uow, "orden", "la orden de servicio", lambda o: o.estado_actual().value)


class SqlUnidadRepository(_RepositorioSql, IUnidadRepository):
    def __init__(self, uow: SqlAlchemyUnitOfWork):
        super().__init__(uow, "unidad", "la unidad", lambda u: u.tipo)


class SqlOperadorRepository(_RepositorioSql, IOperadorRepository):
    def __init__(self, uow: SqlAlchemyUnitOfWork):
        super().__init__(uow, "operador", "el operador",
                         lambda op: "DISPONIBLE" if op.esta_disponible() else "NO_DISPONIBLE")


class SqlAlchemyUnitOfWork(IUnitOfWork):
    """Una sesión por caso de uso: se abre en `with`, confirmar() = commit, si no, rollback."""

    def __init__(self, fabrica: sessionmaker[Session]):
        self._fabrica = fabrica
        self.sesion: Session | None = None
        self._confirmada = False
        self.cotizaciones = SqlCotizacionRepository(self)
        self.ordenes = SqlOrdenServicioRepository(self)
        self.unidades = SqlUnidadRepository(self)
        self.operadores = SqlOperadorRepository(self)

    def __enter__(self) -> Self:
        self.sesion = self._fabrica()
        self._confirmada = False
        return self

    def __exit__(self, tipo, valor, traza) -> None:
        if not self._confirmada:
            self.revertir()
        self.sesion.close()
        self.sesion = None

    def confirmar(self) -> None:
        self.sesion.commit()
        self._confirmada = True

    def revertir(self) -> None:
        self.sesion.rollback()


def sembrar(fabrica: sessionmaker[Session], *objetos: Cotizacion | OrdenDeServicio | Unidad | Operador) -> None:
    """Carga datos ficticios de prueba en una transacción confirmada (equivale al `mundo` en memoria)."""
    uow = SqlAlchemyUnitOfWork(fabrica)
    repos = {Cotizacion: uow.cotizaciones, OrdenDeServicio: uow.ordenes, Unidad: uow.unidades, Operador: uow.operadores}
    with uow:
        for objeto in objetos:
            repos[type(objeto)].guardar(objeto)
        uow.confirmar()

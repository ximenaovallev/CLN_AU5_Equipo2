"""Implementaciones en memoria de los puertos (la tecnología de BD no está definida en el BRD).

Sustituibles por implementaciones con base de datos sin tocar dominio ni aplicación (ADR-002).
"""
from __future__ import annotations

import copy
from datetime import date
from typing import Self

from ..aplicacion.dto import EstadoDelServicioDTO, IndicadoresDTO
from ..aplicacion.puertos import IConsultaDeServicios, IPublicadorDeEventos, IUnitOfWork
from ..dominio.comunes import EntidadNoEncontrada, EventoDeDominio
from ..dominio.cotizacion import Cotizacion
from ..dominio.orden_de_servicio import EstadoServicio, OrdenDeServicio, TipoDeIncidencia
from ..dominio.recursos import Operador, Unidad
from ..dominio.repositorios import (
    ICotizacionRepository,
    IOperadorRepository,
    IOrdenServicioRepository,
    IUnidadRepository,
)


class AlmacenEnMemoria:
    def __init__(self) -> None:
        self.cotizaciones: dict[str, Cotizacion] = {}
        self.ordenes: dict[str, OrdenDeServicio] = {}
        self.unidades: dict[str, Unidad] = {}
        self.operadores: dict[str, Operador] = {}

    def _tablas(self) -> tuple[dict, ...]:
        return self.cotizaciones, self.ordenes, self.unidades, self.operadores

    def instantanea(self) -> tuple[dict, ...]:
        return tuple(copy.deepcopy(t) for t in self._tablas())

    def restaurar(self, instantanea: tuple[dict, ...]) -> None:
        for tabla, copia in zip(self._tablas(), instantanea):
            tabla.clear()
            tabla.update(copia)


def _obtener(tabla: dict, id: str, nombre: str):
    try:
        return tabla[id]
    except KeyError:
        raise EntidadNoEncontrada(f"No existe {nombre} con identificador {id}.") from None


class EnMemoriaCotizacionRepository(ICotizacionRepository):
    def __init__(self, almacen: AlmacenEnMemoria):
        self._a = almacen

    def obtener_por_id(self, id: str) -> Cotizacion:
        return _obtener(self._a.cotizaciones, id, "la cotización")

    def guardar(self, cotizacion: Cotizacion) -> None:
        self._a.cotizaciones[cotizacion.id] = cotizacion


class EnMemoriaOrdenServicioRepository(IOrdenServicioRepository):
    def __init__(self, almacen: AlmacenEnMemoria):
        self._a = almacen

    def obtener_por_id(self, id: str) -> OrdenDeServicio:
        return _obtener(self._a.ordenes, id, "la orden de servicio")

    def guardar(self, orden: OrdenDeServicio) -> None:
        self._a.ordenes[orden.id] = orden


class EnMemoriaUnidadRepository(IUnidadRepository):
    def __init__(self, almacen: AlmacenEnMemoria):
        self._a = almacen

    def obtener_por_id(self, id: str) -> Unidad:
        return _obtener(self._a.unidades, id, "la unidad")


class EnMemoriaOperadorRepository(IOperadorRepository):
    def __init__(self, almacen: AlmacenEnMemoria):
        self._a = almacen

    def obtener_por_id(self, id: str) -> Operador:
        return _obtener(self._a.operadores, id, "el operador")


class EnMemoriaUnitOfWork(IUnitOfWork):
    """Transacción simulada: instantánea al entrar; se restaura si no se confirmó."""

    def __init__(self, almacen: AlmacenEnMemoria):
        self._almacen = almacen
        self.cotizaciones = EnMemoriaCotizacionRepository(almacen)
        self.ordenes = EnMemoriaOrdenServicioRepository(almacen)
        self.unidades = EnMemoriaUnidadRepository(almacen)
        self.operadores = EnMemoriaOperadorRepository(almacen)
        self._instantanea = None
        self._confirmada = False

    def __enter__(self) -> Self:
        self._instantanea = self._almacen.instantanea()
        self._confirmada = False
        return self

    def __exit__(self, tipo, valor, traza) -> None:
        if not self._confirmada:
            self.revertir()

    def confirmar(self) -> None:
        self._confirmada = True
        self._instantanea = None

    def revertir(self) -> None:
        if self._instantanea is not None:
            self._almacen.restaurar(self._instantanea)
            self._instantanea = None


class PublicadorDeEventosEnMemoria(IPublicadorDeEventos):
    def __init__(self) -> None:
        self.publicados: list[EventoDeDominio] = []

    def publicar(self, eventos: list[EventoDeDominio]) -> None:
        self.publicados.extend(eventos)


class EnMemoriaConsultaDeServicios(IConsultaDeServicios):
    """Lado de lectura: construye View Models sin exponer el modelo de escritura."""

    def __init__(self, almacen: AlmacenEnMemoria):
        self._a = almacen

    def estado_del_servicio(self, orden_id: str) -> EstadoDelServicioDTO:
        orden = _obtener(self._a.ordenes, orden_id, "la orden de servicio")
        return EstadoDelServicioDTO(
            orden_id=orden.id,
            estado_actual=orden.estado_actual().value,
            eventos=[f"{e.fecha:%Y-%m-%d %H:%M} · {e.descripcion}" for e in orden.historial],
            retrasos=[i.descripcion for i in orden.incidencias if i.tipo is TipoDeIncidencia.RETRASO],
            incidencias=[f"{i.tipo.value}: {i.descripcion}" for i in orden.incidencias],
        )

    def indicadores(self, desde: date, hasta: date) -> IndicadoresDTO:
        ordenes = [o for o in self._a.ordenes.values() if desde <= o.historial[0].fecha.date() <= hasta]
        tiempos = [
            (o.historial[-1].fecha - o.historial[0].fecha).total_seconds() / 3600
            for o in ordenes if o.estado_actual() is EstadoServicio.ENTREGADO
        ]
        entregadas = [o for o in ordenes if o.estado_actual() is EstadoServicio.ENTREGADO]
        a_tiempo = sum(1 for o in entregadas
                       if o.fecha_requerida is not None and o.fecha_entrega.date() <= o.fecha_requerida)
        incidencias = [i for o in ordenes for i in o.incidencias]
        return IndicadoresDTO(
            tiempos_reales_de_entrega_horas=tiempos,
            retrasos=sum(1 for i in incidencias if i.tipo is TipoDeIncidencia.RETRASO),
            incidencias=len(incidencias),
            entregas_realizadas=len(tiempos),
            ordenes_en_el_periodo=len(ordenes),
            entregas_a_tiempo=a_tiempo,
            cumplimiento_de_entregas=(a_tiempo / len(entregadas)) if entregadas else None,
        )

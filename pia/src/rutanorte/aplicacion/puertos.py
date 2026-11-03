"""Puertos de la aplicación: el dominio y los casos de uso dependen de abstracciones (DIP)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from ..dominio.comunes import EventoDeDominio
from ..dominio.repositorios import (
    ICotizacionRepository,
    IOperadorRepository,
    IOrdenServicioRepository,
    IUnidadRepository,
)
from .dto import EstadoDelServicioDTO, IndicadoresDTO


class IUnitOfWork(ABC):
    """Una transacción por caso de uso: inicia en `with`, termina con confirmar() o revierte."""

    cotizaciones: ICotizacionRepository
    ordenes: IOrdenServicioRepository
    unidades: IUnidadRepository
    operadores: IOperadorRepository

    @abstractmethod
    def __enter__(self) -> IUnitOfWork: ...
    @abstractmethod
    def __exit__(self, tipo, valor, traza) -> None: ...
    @abstractmethod
    def confirmar(self) -> None: ...
    @abstractmethod
    def revertir(self) -> None: ...


class IPublicadorDeEventos(ABC):
    @abstractmethod
    def publicar(self, eventos: list[EventoDeDominio]) -> None: ...


class IConsultaDeServicios(ABC):
    """Puerto de lectura (lado Query de CQRS)."""

    @abstractmethod
    def estado_del_servicio(self, orden_id: str) -> EstadoDelServicioDTO: ...
    @abstractmethod
    def indicadores(self, desde: date, hasta: date) -> IndicadoresDTO: ...

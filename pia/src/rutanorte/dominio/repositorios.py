"""Interfaces de Repository en términos del dominio (sin SQL ni detalles de infraestructura)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .cotizacion import Cotizacion
from .orden_de_servicio import OrdenDeServicio
from .recursos import Operador, Unidad


class ICotizacionRepository(ABC):
    @abstractmethod
    def obtener_por_id(self, id: str) -> Cotizacion: ...
    @abstractmethod
    def guardar(self, cotizacion: Cotizacion) -> None: ...


class IOrdenServicioRepository(ABC):
    @abstractmethod
    def obtener_por_id(self, id: str) -> OrdenDeServicio: ...
    @abstractmethod
    def guardar(self, orden: OrdenDeServicio) -> None: ...


class IUnidadRepository(ABC):
    @abstractmethod
    def obtener_por_id(self, id: str) -> Unidad: ...


class IOperadorRepository(ABC):
    @abstractmethod
    def obtener_por_id(self, id: str) -> Operador: ...

"""Aggregate Root: Cotizacion."""
from __future__ import annotations

from enum import Enum

from .comunes import CotizacionNoModificable, EventoDeDominio
from .eventos import CotizacionAceptada
from .valores import SolicitudDeCotizacion


class EstadoCotizacion(Enum):
    EN_PROCESO = "EN_PROCESO"
    ACEPTADA = "ACEPTADA"
    RECHAZADA = "RECHAZADA"


class Cotizacion:
    def __init__(self, id: str, cliente_id: str, solicitud: SolicitudDeCotizacion):
        self.id = id
        self.cliente_id = cliente_id
        self._solicitud = solicitud
        self._estado = EstadoCotizacion.EN_PROCESO
        self._eventos: list[EventoDeDominio] = []

    @property
    def solicitud(self) -> SolicitudDeCotizacion:
        return self._solicitud

    @property
    def estado(self) -> EstadoCotizacion:
        return self._estado

    def modificar(self, solicitud: SolicitudDeCotizacion) -> None:
        self._exigir_en_proceso("modificar")
        self._solicitud = solicitud

    def aceptar(self) -> None:
        self._exigir_en_proceso("aceptar")
        self._estado = EstadoCotizacion.ACEPTADA
        self._eventos.append(CotizacionAceptada(cotizacion_id=self.id))

    def rechazar(self) -> None:
        self._exigir_en_proceso("rechazar")
        self._estado = EstadoCotizacion.RECHAZADA

    def esta_aceptada(self) -> bool:
        return self._estado is EstadoCotizacion.ACEPTADA

    def extraer_eventos(self) -> list[EventoDeDominio]:
        eventos, self._eventos = self._eventos, []
        return eventos

    def _exigir_en_proceso(self, accion: str) -> None:
        if self._estado is not EstadoCotizacion.EN_PROCESO:
            raise CotizacionNoModificable(
                f"No se puede {accion} la cotización {self.id}: está {self._estado.value}."
            )

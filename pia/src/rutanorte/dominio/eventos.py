"""Domain Events: hechos del negocio que ya ocurrieron."""
from __future__ import annotations

from dataclasses import dataclass

from .comunes import EventoDeDominio
from .valores import Asignacion, Destinatario


@dataclass(frozen=True, kw_only=True)
class CotizacionAceptada(EventoDeDominio):
    cotizacion_id: str


@dataclass(frozen=True, kw_only=True)
class OrdenDeServicioGenerada(EventoDeDominio):
    orden_id: str
    cotizacion_id: str


@dataclass(frozen=True, kw_only=True)
class RecursosAsignados(EventoDeDominio):
    orden_id: str
    asignacion: Asignacion
    es_reasignacion: bool


@dataclass(frozen=True, kw_only=True)
class CargaDeAltoValorAutorizada(EventoDeDominio):
    orden_id: str
    autorizado_por: str


@dataclass(frozen=True, kw_only=True)
class ServicioCancelado(EventoDeDominio):
    orden_id: str
    solicitado_por: str
    motivo: str


@dataclass(frozen=True, kw_only=True)
class EntregaRegistrada(EventoDeDominio):
    orden_id: str
    destinatario: Destinatario


@dataclass(frozen=True, kw_only=True)
class IncidenciaRegistrada(EventoDeDominio):
    orden_id: str
    tipo: TipoDeIncidencia  # noqa: F821 (definido en orden_de_servicio)

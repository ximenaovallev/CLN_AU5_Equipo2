"""Commands y Queries (CQRS básico): cada uno expresa una intención completa."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from ..dominio.orden_de_servicio import TipoDeIncidencia
from ..dominio.valores import Destinatario, Evidencia


class RespuestaDelCliente(Enum):
    ACEPTA = "ACEPTA"
    RECHAZA = "RECHAZA"


# ------------------------------- Commands -------------------------------
@dataclass(frozen=True)
class ResponderCotizacionCommand:
    cotizacion_id: str
    respuesta: RespuestaDelCliente


@dataclass(frozen=True)
class GenerarOrdenDeServicioCommand:
    cotizacion_id: str
    ruta: str
    horario_recoleccion: datetime


@dataclass(frozen=True)
class AsignarRecursosCommand:
    orden_id: str
    unidad_id: str
    operador_id: str


@dataclass(frozen=True)
class RegistrarEntregaCommand:
    """Si `incidencia` es None la entrega fue posible, completa y sin daño."""

    orden_id: str
    destinatario: Destinatario | None
    evidencia: Evidencia
    incidencia: TipoDeIncidencia | None = None
    descripcion_incidencia: str = ""


@dataclass(frozen=True)
class AutorizarCargaDeAltoValorCommand:
    orden_id: str
    autorizado_por: str


@dataclass(frozen=True)
class CancelarServicioCommand:
    orden_id: str
    solicitado_por: str
    motivo: str
    rol_que_autoriza: str = "Operaciones"


# ------------------------------- Queries -------------------------------
@dataclass(frozen=True)
class ConsultarEstadoDelServicioQuery:
    orden_id: str


@dataclass(frozen=True)
class ConsultarIndicadoresQuery:
    desde: date
    hasta: date

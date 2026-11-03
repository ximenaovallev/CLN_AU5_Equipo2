"""Value Objects: se definen por sus valores, no tienen identidad propia."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


@dataclass(frozen=True)
class Peso:
    kilogramos: float


@dataclass(frozen=True)
class Volumen:
    metros_cubicos: float


@dataclass(frozen=True)
class Dimensiones:
    largo_m: float
    ancho_m: float
    alto_m: float

    @property
    def volumen(self) -> Volumen:
        return Volumen(self.largo_m * self.ancho_m * self.alto_m)


@dataclass(frozen=True)
class Ubicacion:
    ciudad: str
    direccion: str = ""


@dataclass(frozen=True)
class Mercancia:
    descripcion: str
    peso: Peso
    dimensiones: Dimensiones
    caracteristicas_especiales: str = ""
    alto_valor: bool = False  # carga de alto valor: requiere controles adicionales (SUPUESTO S-02)


@dataclass(frozen=True)
class Capacidad:
    peso: Peso
    volumen: Volumen


@dataclass(frozen=True)
class SolicitudDeCotizacion:
    origen: Ubicacion
    destino: Ubicacion
    mercancia: Mercancia
    fecha_requerida: date


@dataclass(frozen=True)
class Horario:
    inicio: datetime


@dataclass(frozen=True)
class Asignacion:
    unidad_id: str
    operador_id: str


@dataclass(frozen=True)
class Destinatario:
    identificacion: str


class TipoDeEvidencia(Enum):
    FOTOGRAFIA = "FOTOGRAFIA"
    DOCUMENTO = "DOCUMENTO"


class EventoAsociado(Enum):
    RECEPCION = "RECEPCION"
    ENTREGA = "ENTREGA"
    INCIDENCIA = "INCIDENCIA"


@dataclass(frozen=True)
class Evidencia:
    tipo: TipoDeEvidencia
    referencia: str
    fecha: datetime
    evento_asociado: EventoAsociado


@dataclass(frozen=True)
class PoliticaDeConservacion:
    """SUPUESTO S-03 (pendiente de validar): `dias=None` significa que las evidencias no caducan.

    El BRD pide conservar evidencias asociadas al servicio pero no define por cuánto tiempo;
    el plazo es un parámetro, no un valor inventado.
    """

    dias: int | None = None

    def conserva(self, evidencia: Evidencia, hoy: datetime) -> bool:
        return self.dias is None or (hoy - evidencia.fecha).days <= self.dias

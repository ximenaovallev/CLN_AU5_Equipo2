"""Elementos básicos compartidos del dominio: tiempo, eventos y errores de negocio."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


def ahora() -> datetime:
    return datetime.now(UTC)


# ----------------------------- Errores de dominio -----------------------------
class ErrorDeDominio(Exception):
    """Base de los errores que se explican con términos del negocio."""


class EntidadNoEncontrada(ErrorDeDominio):
    pass


class CotizacionNoModificable(ErrorDeDominio):
    """La cotización solo cambia mientras está EN_PROCESO (US-03)."""


class OrdenNoGenerable(ErrorDeDominio):
    """La orden de servicio solo se genera después de la aceptación (US-06)."""


class RecursosNoDisponibles(ErrorDeDominio):
    """Unidad no adecuada u operador no disponible (compuerta G2 del BPMN)."""


class SinAutoridadParaCancelar(ErrorDeDominio):
    """El rol que intenta cancelar no tiene autoridad (SUPUESTO S-04, pendiente de validar)."""


class ControlDeAltoValorPendiente(ErrorDeDominio):
    """La carga de alto valor requiere autorización antes de asignar recursos (SUPUESTO S-02)."""


class TransicionDeEstadoInvalida(ErrorDeDominio):
    """El estado actual del servicio no permite la operación solicitada."""


# ----------------------------- Eventos de dominio -----------------------------
@dataclass(frozen=True, kw_only=True)
class EventoDeDominio:
    ocurrio_en: datetime = field(default_factory=ahora)

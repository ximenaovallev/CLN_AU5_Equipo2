"""Resultados de la aplicación y View Models de lectura (no se reutilizan para escribir)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Resultado:
    exito: bool
    mensaje_de_negocio: str = ""
    datos: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, mensaje: str = "", **datos: Any) -> Resultado:
        return cls(True, mensaje, datos)

    @classmethod
    def fallo(cls, mensaje: str) -> Resultado:
        return cls(False, mensaje)


@dataclass(frozen=True)
class EstadoDelServicioDTO:
    orden_id: str
    estado_actual: str
    eventos: list[str]
    retrasos: list[str]
    incidencias: list[str]


@dataclass(frozen=True)
class IndicadoresDTO:
    tiempos_reales_de_entrega_horas: list[float]
    retrasos: int
    incidencias: int
    entregas_realizadas: int
    ordenes_en_el_periodo: int
    entregas_a_tiempo: int
    # SUPUESTO S-05 (pendiente de validar): cumplimiento = entregas realizadas en o antes de la
    # fecha requerida por el cliente / entregas realizadas. None si aún no hay entregas.
    cumplimiento_de_entregas: float | None

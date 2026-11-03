"""Entities: Unidad y Operador (identidad propia, ciclo de vida independiente de la orden)."""
from __future__ import annotations

from .valores import Capacidad


class Unidad:
    def __init__(self, id: str, tipo: str, capacidad: Capacidad):
        self.id = id
        self.tipo = tipo
        self.capacidad = capacidad


class Operador:
    def __init__(self, id: str, nombre: str, disponible: bool = True):
        self.id = id
        self.nombre = nombre
        self._disponible = disponible

    def esta_disponible(self) -> bool:
        return self._disponible

    def marcar_disponibilidad(self, disponible: bool) -> None:
        self._disponible = disponible

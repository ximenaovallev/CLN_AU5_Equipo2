"""Domain Service y política de capacidad."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .comunes import RecursosNoDisponibles, SinAutoridadParaCancelar
from .orden_de_servicio import OrdenDeServicio
from .recursos import Operador, Unidad
from .valores import Asignacion, Mercancia


class PoliticaDeCapacidad(ABC):
    """Abstracción (ADR-004): permite cambiar la política sin editar Unidad ni el servicio."""

    @abstractmethod
    def permite(self, unidad: Unidad, mercancia: Mercancia) -> bool: ...


class PoliticaDeCapacidadEmpresa(PoliticaDeCapacidad):
    """Regla del BRD: la unidad debe tener capacidad suficiente para la carga.

    SUPUESTO S-01 (pendiente de validar): los límites propios de la empresa son parámetros
    opcionales; con `None` no hay tope adicional al de la capacidad de la unidad.
    """

    def __init__(self, peso_maximo_kg: float | None = None, volumen_maximo_m3: float | None = None):
        self._peso_maximo_kg = peso_maximo_kg
        self._volumen_maximo_m3 = volumen_maximo_m3

    def permite(self, unidad: Unidad, mercancia: Mercancia) -> bool:
        if self._peso_maximo_kg is not None and mercancia.peso.kilogramos > self._peso_maximo_kg:
            return False
        if (self._volumen_maximo_m3 is not None
                and mercancia.dimensiones.volumen.metros_cubicos > self._volumen_maximo_m3):
            return False
        peso_ok = mercancia.peso.kilogramos <= unidad.capacidad.peso.kilogramos
        volumen_ok = mercancia.dimensiones.volumen.metros_cubicos <= unidad.capacidad.volumen.metros_cubicos
        return peso_ok and volumen_ok


class AsignadorDeRecursos:
    """Domain Service: la regla G2 (¿unidad adecuada y operador disponible?) no pertenece a una sola entidad."""

    def __init__(self, politica: PoliticaDeCapacidad):
        self._politica = politica

    def validar_y_crear(self, orden: OrdenDeServicio, unidad: Unidad, operador: Operador) -> Asignacion:
        if not self._politica.permite(unidad, orden.mercancia):
            raise RecursosNoDisponibles(f"La unidad {unidad.id} no es adecuada para la mercancía de la orden {orden.id}.")
        if not operador.esta_disponible():
            raise RecursosNoDisponibles(f"El operador {operador.id} no está disponible.")
        return Asignacion(unidad_id=unidad.id, operador_id=operador.id)


class AutoridadDeCancelacion:
    """SUPUESTO S-04 (pendiente de validar): qué roles pueden cancelar un servicio aceptado.

    El BRD solo exige registrar quién solicita la cancelación y el motivo; por defecto se asume que
    Operaciones, que administra la orden, es quien la autoriza. Es un parámetro, no una regla fija.
    """

    def __init__(self, roles_autorizados: frozenset[str] = frozenset({"Operaciones"})):
        self._roles = roles_autorizados

    def verificar(self, rol: str) -> None:
        if rol not in self._roles:
            raise SinAutoridadParaCancelar(
                f"El rol {rol} no tiene autoridad para cancelar un servicio (autorizados: {', '.join(sorted(self._roles))})."
            )

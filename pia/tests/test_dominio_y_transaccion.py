"""Invariantes del dominio y comportamiento de la Unit of Work."""
from datetime import UTC, datetime

import pytest

from rutanorte.dominio.comunes import CotizacionNoModificable, TransicionDeEstadoInvalida
from rutanorte.dominio.cotizacion import Cotizacion
from rutanorte.dominio.orden_de_servicio import EstadoServicio, OrdenDeServicio, TipoDeIncidencia
from rutanorte.dominio.valores import Asignacion, Horario
from rutanorte.infraestructura.en_memoria import AlmacenEnMemoria, EnMemoriaUnitOfWork


def test_cotizacion_solo_se_modifica_mientras_esta_en_proceso(solicitud):
    c = Cotizacion("C", "CLI", solicitud)
    c.modificar(solicitud)
    c.aceptar()
    with pytest.raises(CotizacionNoModificable):
        c.modificar(solicitud)


def _orden(solicitud):
    c = Cotizacion("C", "CLI", solicitud)
    c.aceptar()
    return OrdenDeServicio.generar_desde("O-1", c, "ruta", Horario(datetime.now(UTC)))


def test_la_orden_exige_el_orden_de_los_estados(solicitud):
    o = _orden(solicitud)
    with pytest.raises(TransicionDeEstadoInvalida):
        o.registrar_recepcion(None)  # aún no tiene unidad asignada
    o.asignar_recursos(Asignacion("U", "OP"))
    assert o.estado_actual() is EstadoServicio.UNIDAD_ASIGNADA


def test_toda_incidencia_queda_en_el_historial_sin_cambiar_estado(solicitud):
    o = _orden(solicitud)
    antes = o.estado_actual()
    o.registrar_incidencia(TipoDeIncidencia.UNIDAD_AVERIADA, "Falla mecánica")
    assert o.estado_actual() is antes
    assert "UNIDAD_AVERIADA" in o.historial[-1].descripcion


def test_unit_of_work_revierte_si_no_se_confirma(solicitud):
    almacen = AlmacenEnMemoria()
    uow = EnMemoriaUnitOfWork(almacen)
    with uow:
        uow.cotizaciones.guardar(Cotizacion("C", "CLI", solicitud))
    assert almacen.cotizaciones == {}  # sin confirmar() no queda nada

    with uow:
        uow.cotizaciones.guardar(Cotizacion("C", "CLI", solicitud))
        uow.confirmar()
    assert "C" in almacen.cotizaciones

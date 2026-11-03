"""U5 · Reglas de negocio de RutaNorte Logistics: éxito, error y límite (PIA-01 a PIA-15).

Las reglas vienen del BRD/historias de la U2 y de la arquitectura U3 (no se inventan reglas).
R4 se apoya en el SUPUESTO S-04 (pendiente de validar): se prueba como parámetro, no como hecho.
"""
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from rutanorte.aplicacion.comandos import CancelarServicioCommand, RegistrarEntregaCommand
from rutanorte.dominio.comunes import (
    CotizacionNoModificable,
    OrdenNoGenerable,
    RecursosNoDisponibles,
    TransicionDeEstadoInvalida,
)
from rutanorte.dominio.cotizacion import Cotizacion
from rutanorte.dominio.eventos import EntregaRegistrada, OrdenDeServicioGenerada, ServicioCancelado
from rutanorte.dominio.orden_de_servicio import EstadoServicio, OrdenDeServicio, TipoDeIncidencia
from rutanorte.dominio.recursos import Operador, Unidad
from rutanorte.dominio.servicios import AsignadorDeRecursos, PoliticaDeCapacidadEmpresa
from rutanorte.dominio.valores import Asignacion, Capacidad, Destinatario, EventoAsociado, Horario, Peso, Volumen

HORARIO = Horario(datetime(2026, 11, 2, 8, tzinfo=UTC))
U_GRANDE = Unidad("U-GRANDE", "Caja seca", Capacidad(Peso(5000), Volumen(30)))
OP_1 = Operador("OP-1", "Operador uno", disponible=True)
OP_2 = Operador("OP-2", "Operador dos", disponible=False)


def _cotizacion(solicitud, aceptar=True):
    c = Cotizacion("COT-1", "CLI-1", solicitud)
    if aceptar:
        c.aceptar()
    return c


def _orden(solicitud, **cambios_mercancia):
    if cambios_mercancia:
        solicitud = replace(solicitud, mercancia=replace(solicitud.mercancia, **cambios_mercancia))
    return OrdenDeServicio.generar_desde("O-1", _cotizacion(solicitud), "MTY-QRO", HORARIO)


def _asignador(**topes_s01):
    return AsignadorDeRecursos(PoliticaDeCapacidadEmpresa(**topes_s01))


# =============================== R1 · US-06 ===============================
@pytest.mark.unitaria
def test_pia01_orden_desde_cotizacion_aceptada(solicitud, registrar):
    # Arrange
    cotizacion = _cotizacion(solicitud, aceptar=True)
    # Act
    orden = OrdenDeServicio.generar_desde("O-1", cotizacion, "MTY-QRO", HORARIO)
    # Assert
    eventos = orden.extraer_eventos()
    assert orden.estado_actual() is EstadoServicio.CONFIRMADO
    assert len(orden.historial) == 1
    assert [type(e) for e in eventos] == [OrdenDeServicioGenerada]
    registrar("PIA-01", f"{orden.estado_actual().value}, historial={len(orden.historial)}, "
                        f"eventos={[type(e).__name__ for e in eventos]}")


@pytest.mark.unitaria
def test_pia02_cotizacion_en_proceso_no_genera_orden(solicitud, registrar):
    cotizacion = _cotizacion(solicitud, aceptar=False)
    with pytest.raises(OrdenNoGenerable) as error:
        OrdenDeServicio.generar_desde("O-1", cotizacion, "MTY-QRO", HORARIO)
    registrar("PIA-02", f"OrdenNoGenerable: {error.value}")


@pytest.mark.unitaria
def test_pia03_cotizacion_rechazada_es_terminal(solicitud, registrar):
    cotizacion = _cotizacion(solicitud, aceptar=False)
    cotizacion.rechazar()
    with pytest.raises(OrdenNoGenerable):
        OrdenDeServicio.generar_desde("O-1", cotizacion, "MTY-QRO", HORARIO)
    with pytest.raises(CotizacionNoModificable) as error:
        cotizacion.aceptar()
    registrar("PIA-03", f"OrdenNoGenerable + CotizacionNoModificable: {error.value}")


# =============================== R2 · US-07 / G2 ===============================
@pytest.mark.unitaria
def test_pia04_asignacion_con_recursos_adecuados(solicitud, registrar):
    asignacion = _asignador().validar_y_crear(_orden(solicitud), U_GRANDE, OP_1)
    assert asignacion == Asignacion("U-GRANDE", "OP-1")
    registrar("PIA-04", f"Asignacion({asignacion.unidad_id}; {asignacion.operador_id})")


@pytest.mark.unitaria
def test_pia05_operador_no_disponible(solicitud, registrar):
    with pytest.raises(RecursosNoDisponibles, match="no está disponible") as error:
        _asignador().validar_y_crear(_orden(solicitud), U_GRANDE, OP_2)
    registrar("PIA-05", f"RecursosNoDisponibles: {error.value}")


@pytest.mark.unitaria
def test_pia06_carga_igual_a_capacidad_se_permite(solicitud, registrar):
    exacta = Unidad("U-EXACTA", "Caja", Capacidad(Peso(800), Volumen(4.5)))   # carga: 800 kg y 2x1.5x1.5 m
    asignacion = _asignador().validar_y_crear(_orden(solicitud), exacta, OP_1)
    assert asignacion.unidad_id == "U-EXACTA"
    registrar("PIA-06", "Asignación permitida (800 kg = 800 kg; 4.5 m3 = 4.5 m3)")


@pytest.mark.unitaria
def test_pia07_carga_excede_capacidad_por_10_gramos(solicitud, registrar):
    exacta = Unidad("U-EXACTA", "Caja", Capacidad(Peso(800), Volumen(4.5)))
    orden = _orden(solicitud, peso=Peso(800.01))
    with pytest.raises(RecursosNoDisponibles, match="no es adecuada") as error:
        _asignador().validar_y_crear(orden, exacta, OP_1)
    registrar("PIA-07", f"RecursosNoDisponibles: {error.value}")


@pytest.mark.unitaria
def test_pia08_tope_de_volumen_s01(solicitud, registrar):
    """S-01 (pendiente de validar): el tope es un PARÁMETRO; 4.0 m3 es un valor de prueba, no del negocio."""
    with pytest.raises(RecursosNoDisponibles) as error:
        _asignador(volumen_maximo_m3=4.0).validar_y_crear(_orden(solicitud), U_GRANDE, OP_1)
    registrar("PIA-08", f"RecursosNoDisponibles: {error.value}")


# =============================== R3 · US-12 / US-13 / G4 ===============================
@pytest.mark.integracion
def test_pia09_entrega_completa(orden_en_destino, evidencia, registrar):
    app, orden_id = orden_en_destino
    r = app.registrar_entrega.handle(
        RegistrarEntregaCommand(orden_id, Destinatario("Juan Pérez (INE)"), evidencia(EventoAsociado.ENTREGA)))
    orden = app.almacen.ordenes[orden_id]
    assert r.exito and orden.estado_actual() is EstadoServicio.ENTREGADO
    assert orden.destinatario == Destinatario("Juan Pérez (INE)")
    assert len(orden.evidencias_entrega) == 1
    assert any(isinstance(e, EntregaRegistrada) for e in app.publicador.publicados)
    registrar("PIA-09", f"{orden.estado_actual().value}, evidencias_entrega={len(orden.evidencias_entrega)}, "
                        "evento EntregaRegistrada")


@pytest.mark.unitaria
def test_pia10_entrega_antes_de_llegar_se_rechaza(solicitud, evidencia, registrar):
    orden = _orden(solicitud)
    orden.asignar_recursos(Asignacion("U-GRANDE", "OP-1"))
    orden.registrar_recepcion(evidencia(EventoAsociado.RECEPCION))
    orden.iniciar_traslado()
    with pytest.raises(TransicionDeEstadoInvalida) as error:
        orden.registrar_entrega(Destinatario("Juan Pérez (INE)"), evidencia())
    assert orden.estado_actual() is EstadoServicio.EN_TRANSITO
    registrar("PIA-10", f"TransicionDeEstadoInvalida: {error.value}")


@pytest.mark.integracion
def test_pia11_entrega_sin_receptor_se_rechaza(orden_en_destino, evidencia, registrar):
    app, orden_id = orden_en_destino
    eventos_antes = len(app.publicador.publicados)
    r = app.registrar_entrega.handle(RegistrarEntregaCommand(orden_id, None, evidencia()))
    assert not r.exito
    assert app.almacen.ordenes[orden_id].estado_actual() is EstadoServicio.LLEGADA_A_DESTINO
    assert len(app.publicador.publicados) == eventos_antes
    registrar("PIA-11", f"Resultado.fallo: {r.mensaje_de_negocio} · estado LLEGADA_A_DESTINO · sin eventos")


@pytest.mark.unitaria
def test_pia12_no_hay_incidencias_despues_de_entregar(solicitud, evidencia, registrar):
    orden = _orden(solicitud)
    orden.asignar_recursos(Asignacion("U-GRANDE", "OP-1"))
    orden.registrar_recepcion(evidencia(EventoAsociado.RECEPCION))
    orden.iniciar_traslado()
    orden.registrar_llegada_a_destino()
    orden.registrar_entrega(Destinatario("Juan Pérez (INE)"), evidencia())
    with pytest.raises(TransicionDeEstadoInvalida) as error:
        orden.registrar_incidencia(TipoDeIncidencia.DESTINATARIO_AUSENTE, "Reporte tardío")
    registrar("PIA-12", f"TransicionDeEstadoInvalida: {error.value}")


# =============================== R4 · S-04 (seguridad / autorización) ===============================
@pytest.mark.integracion
def test_pia13_operaciones_cancela_con_motivo(orden_confirmada, registrar):
    app, orden_id = orden_confirmada
    r = app.cancelar_servicio.handle(
        CancelarServicioCommand(orden_id, "Cliente CLI-1", "Cambio de fecha", rol_que_autoriza="Operaciones"))
    orden = app.almacen.ordenes[orden_id]
    assert r.exito and orden.estado_actual() is EstadoServicio.CANCELADO
    assert (orden.cancelacion.solicitado_por, orden.cancelacion.motivo) == ("Cliente CLI-1", "Cambio de fecha")
    assert any(isinstance(e, ServicioCancelado) for e in app.publicador.publicados)
    registrar("PIA-13", f"{orden.estado_actual().value}; solicitado_por={orden.cancelacion.solicitado_por}; "
                        f"motivo={orden.cancelacion.motivo}; evento ServicioCancelado")


@pytest.mark.integracion
def test_pia14_rol_sin_autoridad_no_cancela(orden_confirmada, registrar):
    app, orden_id = orden_confirmada
    r = app.cancelar_servicio.handle(
        CancelarServicioCommand(orden_id, "Cliente CLI-1", "Cambio de fecha", rol_que_autoriza="Ventas"))
    orden = app.almacen.ordenes[orden_id]
    assert not r.exito and "Ventas" in r.mensaje_de_negocio
    assert orden.estado_actual() is EstadoServicio.CONFIRMADO
    assert not any(isinstance(e, ServicioCancelado) for e in app.publicador.publicados)
    registrar("PIA-14", f"SinAutoridadParaCancelar: {r.mensaje_de_negocio} · estado CONFIRMADO · sin eventos")


@pytest.mark.integracion
def test_pia15_ni_operaciones_cancela_un_servicio_entregado(orden_en_destino, evidencia, registrar):
    app, orden_id = orden_en_destino
    app.registrar_entrega.handle(RegistrarEntregaCommand(orden_id, Destinatario("Juan Pérez (INE)"), evidencia()))
    r = app.cancelar_servicio.handle(CancelarServicioCommand(orden_id, "Cliente CLI-1", "Ya no lo quiere"))
    assert not r.exito and "ENTREGADO" in r.mensaje_de_negocio
    assert app.almacen.ordenes[orden_id].estado_actual() is EstadoServicio.ENTREGADO
    registrar("PIA-15", f"TransicionDeEstadoInvalida: {r.mensaje_de_negocio}")

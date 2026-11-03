"""Supuestos S-01 a S-05 (pendientes de validar con el stakeholder): se prueban como parámetros, no como hechos."""
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from rutanorte.aplicacion.comandos import (
    AsignarRecursosCommand,
    AutorizarCargaDeAltoValorCommand,
    CancelarServicioCommand,
    ConsultarIndicadoresQuery,
    GenerarOrdenDeServicioCommand,
    RegistrarEntregaCommand,
    ResponderCotizacionCommand,
)
from rutanorte.aplicacion.comandos import (
    RespuestaDelCliente as R,
)
from rutanorte.composicion import construir_aplicacion
from rutanorte.dominio.cotizacion import Cotizacion
from rutanorte.dominio.orden_de_servicio import EstadoServicio, TipoDeIncidencia
from rutanorte.dominio.recursos import Operador, Unidad
from rutanorte.dominio.valores import (
    Asignacion,
    Capacidad,
    Destinatario,
    EventoAsociado,
    Evidencia,
    Peso,
    PoliticaDeConservacion,
    TipoDeEvidencia,
    Volumen,
)

HORARIO = datetime(2026, 11, 2, 8, tzinfo=UTC)


def _orden(app, solicitud, **cambios_mercancia):
    """Crea cotización aceptada y orden; devuelve el id de la orden."""
    if cambios_mercancia:
        solicitud = replace(solicitud, mercancia=replace(solicitud.mercancia, **cambios_mercancia))
    app.almacen.cotizaciones["C"] = Cotizacion("C", "CLI", solicitud)
    app.almacen.unidades["U"] = Unidad("U", "Caja seca", Capacidad(Peso(5000), Volumen(30)))
    app.almacen.operadores["OP"] = Operador("OP", "Operador", True)
    app.responder_cotizacion.handle(ResponderCotizacionCommand("C", R.ACEPTA))
    return app.generar_orden.handle(GenerarOrdenDeServicioCommand("C", "ruta", HORARIO)).datos["orden_id"]


def _evidencia(evento=EventoAsociado.ENTREGA, fecha=None):
    return Evidencia(TipoDeEvidencia.FOTOGRAFIA, "f.jpg", fecha or datetime.now(UTC), evento)


# S-01 límites propios de capacidad
def test_s01_limite_propio_de_peso_rechaza_aunque_la_unidad_tenga_capacidad(solicitud):
    app = construir_aplicacion(peso_maximo_kg=500)
    orden_id = _orden(app, solicitud)  # carga de 800 kg
    r = app.asignar_recursos.handle(AsignarRecursosCommand(orden_id, "U", "OP"))
    assert not r.exito and "no es adecuada" in r.mensaje_de_negocio


def test_s01_sin_limite_propio_solo_cuenta_la_capacidad_de_la_unidad(solicitud):
    app = construir_aplicacion()
    orden_id = _orden(app, solicitud)
    assert app.asignar_recursos.handle(AsignarRecursosCommand(orden_id, "U", "OP")).exito


# S-02 carga de alto valor
def test_s02_alto_valor_exige_autorizacion_antes_de_asignar(solicitud):
    app = construir_aplicacion()
    orden_id = _orden(app, solicitud, alto_valor=True)
    r = app.asignar_recursos.handle(AsignarRecursosCommand(orden_id, "U", "OP"))
    assert not r.exito and "alto valor" in r.mensaje_de_negocio
    assert app.autorizar_alto_valor.handle(AutorizarCargaDeAltoValorCommand(orden_id, "Operaciones")).exito
    assert app.asignar_recursos.handle(AsignarRecursosCommand(orden_id, "U", "OP")).exito
    assert any("alto valor autorizada" in e.descripcion for e in app.almacen.ordenes[orden_id].historial)


def test_s02_no_se_autoriza_una_carga_que_no_es_de_alto_valor(solicitud):
    app = construir_aplicacion()
    orden_id = _orden(app, solicitud)
    assert not app.autorizar_alto_valor.handle(AutorizarCargaDeAltoValorCommand(orden_id, "Operaciones")).exito


# S-03 conservación de evidencias
def test_s03_sin_plazo_las_evidencias_no_caducan(solicitud):
    app = construir_aplicacion()
    orden_id = _orden(app, solicitud)
    o = app.almacen.ordenes[orden_id]
    o.asignar_recursos(Asignacion("U", "OP"))
    o.registrar_recepcion(_evidencia(EventoAsociado.RECEPCION, datetime(2000, 1, 1, tzinfo=UTC)))
    assert len(o.evidencias(app.politica_de_conservacion)) == 1


def test_s03_con_plazo_solo_se_conservan_las_vigentes(solicitud):
    app = construir_aplicacion(dias_de_conservacion=30)
    orden_id = _orden(app, solicitud)
    o = app.almacen.ordenes[orden_id]
    o.asignar_recursos(Asignacion("U", "OP"))
    o.registrar_recepcion(_evidencia(EventoAsociado.RECEPCION, datetime.now(UTC) - timedelta(days=90)))
    o.registrar_incidencia(TipoDeIncidencia.RETRASO, "Demora", _evidencia(EventoAsociado.INCIDENCIA))
    assert len(o.evidencias()) == 2
    assert len(o.evidencias(PoliticaDeConservacion(30))) == 1


# S-04 cancelación
def test_s04_cancelacion_registra_quien_y_motivo(solicitud):
    app = construir_aplicacion()
    orden_id = _orden(app, solicitud)
    r = app.cancelar_servicio.handle(CancelarServicioCommand(orden_id, "Cliente ACME", "Ya no requiere el envío"))
    assert r.exito
    o = app.almacen.ordenes[orden_id]
    assert o.estado_actual() is EstadoServicio.CANCELADO
    assert o.cancelacion.solicitado_por == "Cliente ACME" and o.cancelacion.motivo == "Ya no requiere el envío"


def test_s04_rol_sin_autoridad_no_cancela(solicitud):
    app = construir_aplicacion()
    orden_id = _orden(app, solicitud)
    r = app.cancelar_servicio.handle(CancelarServicioCommand(orden_id, "Ventas", "Prueba", rol_que_autoriza="Ventas"))
    assert not r.exito and "autoridad" in r.mensaje_de_negocio
    assert app.almacen.ordenes[orden_id].estado_actual() is EstadoServicio.CONFIRMADO


def test_s04_la_autoridad_es_configurable(solicitud):
    app = construir_aplicacion(roles_que_cancelan=frozenset({"Operaciones", "Ventas"}))
    orden_id = _orden(app, solicitud)
    assert app.cancelar_servicio.handle(CancelarServicioCommand(orden_id, "Ventas", "Duplicado", "Ventas")).exito


def test_s04_exige_motivo_y_no_cancela_un_servicio_entregado_ni_ya_cancelado(solicitud):
    app = construir_aplicacion()
    orden_id = _orden(app, solicitud)
    assert not app.cancelar_servicio.handle(CancelarServicioCommand(orden_id, "Cliente", "  ")).exito
    assert app.cancelar_servicio.handle(CancelarServicioCommand(orden_id, "Cliente", "Motivo")).exito
    assert not app.cancelar_servicio.handle(CancelarServicioCommand(orden_id, "Cliente", "Otra vez")).exito
    # un servicio cancelado ya no admite asignación
    assert not app.asignar_recursos.handle(AsignarRecursosCommand(orden_id, "U", "OP")).exito


# S-05 cumplimiento de entregas
def _entregar(app, orden_id):
    o = app.almacen.ordenes[orden_id]
    o.asignar_recursos(Asignacion("U", "OP"))
    o.registrar_recepcion(_evidencia(EventoAsociado.RECEPCION))
    o.iniciar_traslado()
    o.registrar_llegada_a_destino()
    return app.registrar_entrega.handle(RegistrarEntregaCommand(orden_id, Destinatario("INE"), _evidencia()))


def test_s05_cumplimiento_es_entregas_a_tiempo_sobre_entregas_realizadas(solicitud):
    en_plazo = replace(solicitud, fecha_requerida=date(2100, 1, 1))
    tarde = replace(solicitud, fecha_requerida=date(2000, 1, 1))
    app = construir_aplicacion()
    for nombre, sol in (("A", en_plazo), ("B", tarde)):
        app.almacen.cotizaciones[nombre] = Cotizacion(nombre, "CLI", sol)
    app.almacen.unidades["U"] = Unidad("U", "Caja seca", Capacidad(Peso(5000), Volumen(30)))
    app.almacen.operadores["OP"] = Operador("OP", "Operador", True)
    for nombre in ("A", "B"):
        app.responder_cotizacion.handle(ResponderCotizacionCommand(nombre, R.ACEPTA))
        oid = app.generar_orden.handle(GenerarOrdenDeServicioCommand(nombre, "ruta", HORARIO)).datos["orden_id"]
        assert _entregar(app, oid).exito
    ind = app.consultar_indicadores.handle(ConsultarIndicadoresQuery(date(2000, 1, 1), date(2200, 1, 1)))
    assert ind.entregas_realizadas == 2 and ind.entregas_a_tiempo == 1
    assert ind.cumplimiento_de_entregas == 0.5


def test_s05_sin_entregas_el_cumplimiento_no_esta_definido():
    app = construir_aplicacion()
    ind = app.consultar_indicadores.handle(ConsultarIndicadoresQuery(date(2000, 1, 1), date(2200, 1, 1)))
    assert ind.cumplimiento_de_entregas is None

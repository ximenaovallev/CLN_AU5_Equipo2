"""U5 · Integración con base de datos (PIA-16 a PIA-19).

Cada prueba crea su propia base SQLite EN MEMORIA: no existe ni se modifica ninguna base de producción.
Los handlers son los mismos de la U3: solo cambia la implementación de IUnitOfWork (ADR-002).
"""
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from rutanorte.aplicacion.comandos import (
    AsignarRecursosCommand,
    CancelarServicioCommand,
    GenerarOrdenDeServicioCommand,
    RegistrarEntregaCommand,
    ResponderCotizacionCommand,
)
from rutanorte.aplicacion.comandos import RespuestaDelCliente as R
from rutanorte.aplicacion.handlers import (
    AsignarRecursosHandler,
    CancelarServicioHandler,
    GenerarOrdenDeServicioHandler,
    RegistrarEntregaHandler,
    ResponderCotizacionHandler,
)
from rutanorte.dominio.cotizacion import Cotizacion
from rutanorte.dominio.orden_de_servicio import EstadoServicio
from rutanorte.dominio.recursos import Operador, Unidad
from rutanorte.dominio.servicios import AsignadorDeRecursos, AutoridadDeCancelacion, PoliticaDeCapacidadEmpresa
from rutanorte.dominio.valores import Capacidad, Destinatario, EventoAsociado, Peso, Volumen
from rutanorte.infraestructura.en_memoria import AlmacenEnMemoria, EnMemoriaUnitOfWork, PublicadorDeEventosEnMemoria
from rutanorte.infraestructura.sqlalchemy_uow import (
    AgregadoRow,
    SqlAlchemyUnitOfWork,
    crear_fabrica_de_sesiones,
    sembrar,
)

pytestmark = pytest.mark.integracion
HORARIO = datetime(2026, 11, 2, 8, tzinfo=UTC)


def _datos(solicitud):
    return (Cotizacion("COT-1", "CLI-1", solicitud),
            Unidad("U-GRANDE", "Caja seca", Capacidad(Peso(5000), Volumen(30))),
            Operador("OP-1", "Operador uno", disponible=True),
            Operador("OP-2", "Operador dos", disponible=False))


def _app(uow):
    pub = PublicadorDeEventosEnMemoria()
    asignador = AsignadorDeRecursos(PoliticaDeCapacidadEmpresa())
    return SimpleNamespace(
        uow=uow, publicador=pub,
        responder=ResponderCotizacionHandler(uow, pub), generar=GenerarOrdenDeServicioHandler(uow, pub),
        asignar=AsignarRecursosHandler(uow, pub, asignador), entregar=RegistrarEntregaHandler(uow, pub),
        cancelar=CancelarServicioHandler(uow, pub, AutoridadDeCancelacion()))


def _app_sql(solicitud):
    fabrica = crear_fabrica_de_sesiones()          # sqlite :memory: nueva para esta prueba
    sembrar(fabrica, *_datos(solicitud))
    return _app(SqlAlchemyUnitOfWork(fabrica)), fabrica


def _app_memoria(solicitud):
    almacen = AlmacenEnMemoria()
    cot, unidad, op1, op2 = _datos(solicitud)
    almacen.cotizaciones[cot.id], almacen.unidades[unidad.id] = cot, unidad
    almacen.operadores[op1.id], almacen.operadores[op2.id] = op1, op2
    return _app(EnMemoriaUnitOfWork(almacen))


def _orden_generada(app):
    app.responder.handle(ResponderCotizacionCommand("COT-1", R.ACEPTA))
    return app.generar.handle(GenerarOrdenDeServicioCommand("COT-1", "MTY-QRO", HORARIO)).datos["orden_id"]


def _fila(fabrica, orden_id):
    with fabrica() as sesion:                      # sesión NUEVA: lee lo confirmado en la base
        return sesion.get(AgregadoRow, ("orden", orden_id))


def test_pia16_commit_persiste_la_orden(solicitud, registrar):
    app, fabrica = _app_sql(solicitud)
    orden_id = _orden_generada(app)
    fila = _fila(fabrica, orden_id)
    assert fila is not None and fila.estado == "CONFIRMADO"
    registrar("PIA-16", f"Fila tipo=orden visible en sesión nueva; estado={fila.estado}")


def test_pia17_error_de_negocio_hace_rollback(solicitud, registrar):
    app, fabrica = _app_sql(solicitud)
    orden_id = _orden_generada(app)
    r = app.asignar.handle(AsignarRecursosCommand(orden_id, "U-GRANDE", "OP-2"))   # OP-2 no disponible
    fila = _fila(fabrica, orden_id)
    with SqlAlchemyUnitOfWork(fabrica) as uow:
        orden = uow.ordenes.obtener_por_id(orden_id)
    assert not r.exito
    assert fila.estado == "CONFIRMADO" and orden.asignacion is None
    assert "RecursosAsignados" not in [type(e).__name__ for e in app.publicador.publicados]
    registrar("PIA-17", f"Resultado.fallo ({r.mensaje_de_negocio}); rollback: estado={fila.estado}, "
                        "asignacion=None, sin RecursosAsignados")


def _flujo_hasta_entrega(app, evidencia):
    orden_id = _orden_generada(app)
    assert app.asignar.handle(AsignarRecursosCommand(orden_id, "U-GRANDE", "OP-1")).exito
    with app.uow as uow:                           # pasos sin handler propio (Anexo B de la U3)
        orden = uow.ordenes.obtener_por_id(orden_id)
        orden.registrar_recepcion(evidencia(EventoAsociado.RECEPCION))
        orden.iniciar_traslado()
        orden.registrar_llegada_a_destino()
        uow.ordenes.guardar(orden)
        uow.confirmar()
    r = app.entregar.handle(RegistrarEntregaCommand(orden_id, Destinatario("Juan Pérez (INE)"), evidencia()))
    assert r.exito
    with app.uow as uow:
        return uow.ordenes.obtener_por_id(orden_id)


def test_pia18_mismo_resultado_en_memoria_y_sqlalchemy(solicitud, evidencia, registrar):
    app_mem = _app_memoria(solicitud)
    app_sql, _ = _app_sql(solicitud)
    final_mem = _flujo_hasta_entrega(app_mem, evidencia)
    final_sql = _flujo_hasta_entrega(app_sql, evidencia)
    eventos_mem = [type(e).__name__ for e in app_mem.publicador.publicados]
    eventos_sql = [type(e).__name__ for e in app_sql.publicador.publicados]
    assert final_mem.estado_actual() is final_sql.estado_actual() is EstadoServicio.ENTREGADO
    assert [h.descripcion for h in final_mem.historial] == [h.descripcion for h in final_sql.historial]
    assert eventos_mem == eventos_sql
    registrar("PIA-18", f"EnMemoria={final_mem.estado_actual().value} / SqlAlchemy={final_sql.estado_actual().value};"
                        f" eventos idénticos {eventos_sql}")


def test_pia19_recargar_no_duplica_eventos(solicitud, registrar):
    app, _ = _app_sql(solicitud)
    orden_id = _orden_generada(app)
    app.asignar.handle(AsignarRecursosCommand(orden_id, "U-GRANDE", "OP-1"))
    app.cancelar.handle(CancelarServicioCommand(orden_id, "Cliente CLI-1", "Cambio de fecha"))
    eventos = [type(e).__name__ for e in app.publicador.publicados]
    assert eventos == ["CotizacionAceptada", "OrdenDeServicioGenerada", "RecursosAsignados", "ServicioCancelado"]
    registrar("PIA-19", f"Cada evento una sola vez: {eventos}")


def test_sql_recurso_inexistente_es_error_de_negocio_igual_que_en_memoria(solicitud):
    """Rama de obtener_por_id sin fila: mismo contrato que EnMemoria (test_cu03_recurso_inexistente...)."""
    app, _ = _app_sql(solicitud)
    orden_id = _orden_generada(app)
    r = app.asignar.handle(AsignarRecursosCommand(orden_id, "U-NO-EXISTE", "OP-1"))
    assert not r.exito and "No existe la unidad" in r.mensaje_de_negocio

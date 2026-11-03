"""U5 · PIA-23: flujo completo CU-01 → CU-05 por la Service Layer.

No es un E2E real: RutaNorte aún no tiene API ni interfaz (alcance U3). Esta prueba recorre el proceso
completo desde la raíz de composición, que es lo más cercano posible. El E2E propuesto está en el README.
"""
from datetime import UTC, datetime, timedelta

import pytest

from rutanorte.aplicacion.comandos import (
    AsignarRecursosCommand,
    ConsultarEstadoDelServicioQuery,
    ConsultarIndicadoresQuery,
    GenerarOrdenDeServicioCommand,
    RegistrarEntregaCommand,
    ResponderCotizacionCommand,
)
from rutanorte.aplicacion.comandos import RespuestaDelCliente as R
from rutanorte.composicion import construir_aplicacion
from rutanorte.dominio.cotizacion import Cotizacion
from rutanorte.dominio.recursos import Operador, Unidad
from rutanorte.dominio.valores import (
    Capacidad,
    Destinatario,
    Dimensiones,
    EventoAsociado,
    Mercancia,
    Peso,
    SolicitudDeCotizacion,
    Ubicacion,
    Volumen,
)


@pytest.mark.flujo
def test_pia23_flujo_completo_hasta_consulta(evidencia, registrar):
    hoy = datetime.now(UTC).date()
    app = construir_aplicacion()
    app.almacen.cotizaciones["COT-9"] = Cotizacion("COT-9", "CLI-9", SolicitudDeCotizacion(
        Ubicacion("Monterrey"), Ubicacion("Saltillo"),
        Mercancia("Rollos de acero", Peso(1200), Dimensiones(2, 2, 1)), fecha_requerida=hoy + timedelta(days=3)))
    app.almacen.unidades["U-1"] = Unidad("U-1", "Plataforma", Capacidad(Peso(10000), Volumen(40)))
    app.almacen.operadores["OP-1"] = Operador("OP-1", "Operador uno")

    assert app.responder_cotizacion.handle(ResponderCotizacionCommand("COT-9", R.ACEPTA)).exito          # CU-01
    orden_id = app.generar_orden.handle(GenerarOrdenDeServicioCommand(
        "COT-9", "MTY-SAL", datetime(2026, 11, 3, 7, tzinfo=UTC))).datos["orden_id"]                       # CU-02
    assert app.asignar_recursos.handle(AsignarRecursosCommand(orden_id, "U-1", "OP-1")).exito             # CU-03
    orden = app.almacen.ordenes[orden_id]
    orden.registrar_recepcion(evidencia(EventoAsociado.RECEPCION))
    orden.iniciar_traslado()
    orden.registrar_llegada_a_destino()
    assert app.registrar_entrega.handle(RegistrarEntregaCommand(
        orden_id, Destinatario("Almacén Saltillo · Rosa M."), evidencia())).exito                         # CU-04

    estado = app.consultar_estado.handle(ConsultarEstadoDelServicioQuery(orden_id))                        # CU-05
    indicadores = app.consultar_indicadores.handle(
        ConsultarIndicadoresQuery(hoy - timedelta(days=1), hoy + timedelta(days=1)))

    assert estado.estado_actual == "ENTREGADO"
    assert len(estado.eventos) == 6 and estado.incidencias == []
    assert indicadores.entregas_realizadas == 1 and indicadores.cumplimiento_de_entregas == 1.0
    registrar("PIA-23", f"Consulta: {estado.estado_actual}, {len(estado.eventos)} eventos, 0 incidencias; "
                        f"cumplimiento={indicadores.cumplimiento_de_entregas}")

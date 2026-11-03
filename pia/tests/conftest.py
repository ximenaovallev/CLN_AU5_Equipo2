from datetime import UTC, date, datetime

import pytest

from rutanorte.composicion import construir_aplicacion
from rutanorte.dominio.cotizacion import Cotizacion
from rutanorte.dominio.recursos import Operador, Unidad
from rutanorte.dominio.valores import (
    Capacidad,
    Dimensiones,
    EventoAsociado,
    Evidencia,
    Mercancia,
    Peso,
    SolicitudDeCotizacion,
    TipoDeEvidencia,
    Ubicacion,
    Volumen,
)


@pytest.fixture
def app():
    return construir_aplicacion()


@pytest.fixture
def solicitud():
    return SolicitudDeCotizacion(
        origen=Ubicacion("Monterrey"), destino=Ubicacion("Querétaro"),
        mercancia=Mercancia("Refacciones", Peso(800), Dimensiones(2, 1.5, 1.5)),
        fecha_requerida=date(2026, 11, 1),
    )


@pytest.fixture
def evidencia():
    def _crear(evento=EventoAsociado.ENTREGA):
        return Evidencia(TipoDeEvidencia.FOTOGRAFIA, "foto-001.jpg", datetime.now(UTC), evento)
    return _crear


@pytest.fixture
def mundo(app, solicitud):
    """Cotización en proceso, una unidad adecuada, una pequeña y dos operadores."""
    a = app.almacen
    a.cotizaciones["COT-1"] = Cotizacion("COT-1", "CLI-1", solicitud)
    a.unidades["U-GRANDE"] = Unidad("U-GRANDE", "Caja seca", Capacidad(Peso(5000), Volumen(30)))
    a.unidades["U-CHICA"] = Unidad("U-CHICA", "Pick-up", Capacidad(Peso(500), Volumen(4)))
    a.operadores["OP-1"] = Operador("OP-1", "Operador uno", disponible=True)
    a.operadores["OP-2"] = Operador("OP-2", "Operador dos", disponible=False)
    return app


@pytest.fixture
def orden_confirmada(mundo):
    from rutanorte.aplicacion.comandos import (
        GenerarOrdenDeServicioCommand,
        ResponderCotizacionCommand,
    )
    from rutanorte.aplicacion.comandos import (
        RespuestaDelCliente as R,
    )
    mundo.responder_cotizacion.handle(ResponderCotizacionCommand("COT-1", R.ACEPTA))
    r = mundo.generar_orden.handle(
        GenerarOrdenDeServicioCommand("COT-1", "MTY-QRO", datetime(2026, 11, 2, 8, tzinfo=UTC)))
    return mundo, r.datos["orden_id"]


@pytest.fixture
def orden_en_destino(orden_confirmada, evidencia):
    from rutanorte.aplicacion.comandos import AsignarRecursosCommand
    app, orden_id = orden_confirmada
    app.asignar_recursos.handle(AsignarRecursosCommand(orden_id, "U-GRANDE", "OP-1"))
    orden = app.almacen.ordenes[orden_id]
    orden.registrar_recepcion(evidencia(EventoAsociado.RECEPCION))
    orden.iniciar_traslado()
    orden.registrar_llegada_a_destino()
    return app, orden_id


# ----------------------------------------------------------------------------
# Unidad 5: cada prueba de la matriz registra su caso y el resultado REAL observado
# (record_property -> JUnit XML -> scripts/generar_matriz_pia.py -> evidencias/matriz_casos_pia.csv)
# ----------------------------------------------------------------------------
@pytest.fixture
def registrar(record_property):
    def _registrar(caso: str, resultado_real: str) -> None:
        record_property("caso", caso)
        record_property("resultado_real", resultado_real)
    return _registrar

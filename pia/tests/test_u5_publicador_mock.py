"""U5 · Servicio externo simulado (PIA-20 a PIA-22).

RutaNorte no cobra en línea (el BRD no tiene pasarela de pago). Su integración externa es el bus de
eventos / notificación a Operaciones (puerto IPublicadorDeEventos, N3: dejar de depender de WhatsApp).
Se sustituye por Mock(spec=IPublicadorDeEventos): no se envía ningún mensaje real.
"""
from unittest.mock import Mock

import pytest

from rutanorte.aplicacion.comandos import AsignarRecursosCommand
from rutanorte.aplicacion.handlers import AsignarRecursosHandler
from rutanorte.aplicacion.puertos import IPublicadorDeEventos
from rutanorte.dominio.eventos import RecursosAsignados
from rutanorte.dominio.orden_de_servicio import EstadoServicio
from rutanorte.dominio.servicios import AsignadorDeRecursos, PoliticaDeCapacidadEmpresa
from rutanorte.infraestructura.en_memoria import EnMemoriaUnitOfWork

pytestmark = pytest.mark.integracion


def _handler(app, publicador):
    return AsignarRecursosHandler(EnMemoriaUnitOfWork(app.almacen), publicador,
                                  AsignadorDeRecursos(PoliticaDeCapacidadEmpresa()))


def test_pia20_publica_solo_despues_de_confirmar(orden_confirmada, registrar):
    app, orden_id = orden_confirmada
    estado_al_publicar = []
    bus = Mock(spec=IPublicadorDeEventos)
    bus.publicar.side_effect = lambda ev: estado_al_publicar.append(app.almacen.ordenes[orden_id].estado_actual())

    r = _handler(app, bus).handle(AsignarRecursosCommand(orden_id, "U-GRANDE", "OP-1"))

    assert r.exito
    bus.publicar.assert_called_once()
    (eventos,), _ = bus.publicar.call_args
    assert [type(e) for e in eventos] == [RecursosAsignados]
    assert estado_al_publicar == [EstadoServicio.UNIDAD_ASIGNADA]   # ya confirmado cuando se publica
    registrar("PIA-20", f"publicar() x{bus.publicar.call_count} con {[type(e).__name__ for e in eventos]}; "
                        f"estado al publicar={estado_al_publicar[0].value}")


def test_pia21_error_de_negocio_no_publica(orden_confirmada, registrar):
    app, orden_id = orden_confirmada
    bus = Mock(spec=IPublicadorDeEventos)
    r = _handler(app, bus).handle(AsignarRecursosCommand(orden_id, "U-CHICA", "OP-1"))   # 500 kg < 800 kg
    assert not r.exito
    bus.publicar.assert_not_called()
    motivo = r.mensaje_de_negocio.split(" para la mercancía")[0]
    registrar("PIA-21", f"Resultado.fallo ({motivo}); publicar() llamado {bus.publicar.call_count} veces")


def test_pia22_falla_del_bus_tras_commit_riesgo_documentado(orden_confirmada, registrar):
    """RIESGO (no se oculta): el handler confirma y DESPUÉS publica. Si el bus falla, la excepción
    sale del handler pero la asignación ya quedó confirmada y Operaciones no recibe el aviso.
    Propuesta: patrón Outbox (guardar el evento en la misma transacción y publicarlo con reintentos)."""
    app, orden_id = orden_confirmada
    bus = Mock(spec=IPublicadorDeEventos)
    bus.publicar.side_effect = ConnectionError("bus de eventos no disponible")
    with pytest.raises(ConnectionError):
        _handler(app, bus).handle(AsignarRecursosCommand(orden_id, "U-GRANDE", "OP-1"))
    estado = app.almacen.ordenes[orden_id].estado_actual()
    assert estado is EstadoServicio.UNIDAD_ASIGNADA
    registrar("PIA-22", f"ConnectionError propagado; estado ya confirmado={estado.value} (evento perdido: riesgo)")

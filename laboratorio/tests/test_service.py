"""Servicio de checkout con la pasarela SIMULADA (unittest.mock).

Ninguna prueba abre conexiones de red ni mueve dinero: el gateway es un Mock con la
misma interfaz (spec) que tendría un adaptador real.
"""
from unittest.mock import Mock

import pytest

from src.application import OrderService
from src.domain import Order


class PaymentGateway:
    """Contrato (puerto) que espera OrderService. Solo se usa como `spec` del mock."""

    def charge(self, amount: float) -> bool:  # pragma: no cover - nunca se ejecuta
        raise NotImplementedError("Adaptador real fuera del alcance del laboratorio")


def test_gateway_approved():
    gateway = Mock()
    gateway.charge.return_value = True
    assert OrderService(gateway).checkout(Order(100)) == 100
    gateway.charge.assert_called_once_with(100)


def test_gateway_rejected():
    gateway = Mock()
    gateway.charge.return_value = False
    with pytest.raises(RuntimeError):
        OrderService(gateway).checkout(Order(100))


# ---------------------------------------------------------------------------
# Paso 5 · Evidencia E5
# ---------------------------------------------------------------------------
def test_payment_approved_example():
    gateway = Mock(spec=PaymentGateway)
    gateway.charge.return_value = True
    amount = OrderService(gateway).checkout(Order(100))
    assert amount == 100
    gateway.charge.assert_called_once_with(100)


def test_vip_200_rechazado_intenta_cobrar_170_y_lanza_runtimeerror():
    # Arrange
    gateway = Mock(spec=PaymentGateway)
    gateway.charge.return_value = False
    order = Order(200, vip=True)
    # Act + Assert
    with pytest.raises(RuntimeError, match="payment rejected"):
        OrderService(gateway).checkout(order)
    gateway.charge.assert_called_once_with(170)
    # El mock solo registró UNA llamada simulada: no hubo cargo real ni reintentos.
    assert gateway.mock_calls == [(("charge", (170,), {}))]


def test_timeout_de_la_pasarela_se_propaga_sin_reintentar():
    gateway = Mock(spec=PaymentGateway)
    gateway.charge.side_effect = TimeoutError("gateway timeout")
    with pytest.raises(TimeoutError):
        OrderService(gateway).checkout(Order(100))
    assert gateway.charge.call_count == 1


def test_riesgo_documentado_pedido_queda_confirmado_aunque_el_pago_falle():
    """Comportamiento ACTUAL del código base (riesgo de consistencia, no se oculta):
    confirm() se ejecuta antes de conocer la respuesta de la pasarela."""
    gateway = Mock(spec=PaymentGateway)
    gateway.charge.return_value = False
    order = Order(200, vip=True)
    with pytest.raises(RuntimeError):
        OrderService(gateway).checkout(order)
    assert order.status == "CONFIRMED"   # <- riesgo: confirmado sin pago exitoso


@pytest.mark.xfail(strict=True, reason="Propuesta de mejora E5: confirmar solo tras pago aprobado "
                                       "(o compensar a PAYMENT_FAILED). No implementada en el base.")
def test_propuesta_pedido_no_debe_quedar_confirmado_si_el_pago_falla():
    gateway = Mock(spec=PaymentGateway)
    gateway.charge.return_value = False
    order = Order(200, vip=True)
    with pytest.raises(RuntimeError):
        OrderService(gateway).checkout(order)
    assert order.status != "CONFIRMED"

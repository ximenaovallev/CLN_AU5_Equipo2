"""Pruebas UNITARIAS del dominio: no usan base de datos, red ni pasarela de pago."""
import pytest

from src.domain import CustomerHasDebt, Order


def test_vip_discount():
    o = Order(100, vip=True)            # Arrange: preparar
    assert o.confirm() == 85            # Act + Assert: confirmar y verificar
    assert o.status == "CONFIRMED"      # Assert: estado final


def test_regular_no_discount():
    assert Order(100).confirm() == 100


def test_customer_debt():
    with pytest.raises(CustomerHasDebt):
        Order(100).confirm(customer_debt=50)


@pytest.mark.parametrize("total", [0, -1])
def test_invalid_total(total):
    with pytest.raises(ValueError):
        Order(total).confirm()


# ---------------------------------------------------------------------------
# Paso 2 · Evidencia E2: nuevas pruebas unitarias (Arrange-Act-Assert)
# ---------------------------------------------------------------------------
def test_vip_200_recibe_15_por_ciento_y_cobra_170():
    # Arrange
    order = Order(200, vip=True)
    # Act
    amount = order.confirm()
    # Assert
    assert amount == 170
    assert order.discount == 30
    assert order.status == "CONFIRMED"


def test_regular_200_no_recibe_descuento_y_cobra_200():
    # Arrange
    order = Order(200, vip=False)
    # Act
    amount = order.confirm()
    # Assert
    assert amount == 200
    assert order.discount == 0.0
    assert order.status == "CONFIRMED"


# ---------------------------------------------------------------------------
# Paso 3 · Evidencia E3: TDD (RED -> GREEN -> REFACTOR)
# Regla nueva: no confirmar un pedido que ya fue confirmado (caso CP08).
# ---------------------------------------------------------------------------
def test_cannot_confirm_twice():
    order = Order(100)
    order.confirm()
    with pytest.raises(ValueError, match="already confirmed"):
        order.confirm()

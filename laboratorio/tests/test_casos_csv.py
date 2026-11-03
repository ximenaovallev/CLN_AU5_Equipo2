"""Pruebas parametrizadas desde los CSV didácticos (datos/casos_de_prueba.csv + pedidos_prueba.csv).

Los CSV no se cargan solos: se leen con csv.DictReader y cada fila se convierte en un caso.
CP01-CP12 -> dominio (Order.confirm); CP13 -> mock de pasarela; CP14/CP15 -> SqlOrderRepository.
"""
import csv
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from src.application import OrderService
from src.domain import CustomerHasDebt, Order
from src.repository import OrderRow, SqlOrderRepository, make_engine

DATOS = Path(__file__).resolve().parent.parent / "datos"


def _leer(nombre):
    with (DATOS / nombre).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


PEDIDOS = {row["pedido_id"]: row for row in _leer("pedidos_prueba.csv")}
CASOS = _leer("casos_de_prueba.csv")
CASOS_DOMINIO = [c for c in CASOS if c["accion"] == "confirmar"]

# CP08 se amplió con TDD (Paso 3): el resultado esperado ya NO es CONFIRMED.
EXPECTATIVA_ACTUALIZADA = {"CP08": "ValueError: already confirmed"}


def pedido_desde_csv(row):
    return Order(total=float(row["total"]), vip=row["es_vip"] == "1", status=row["estado_inicial"])


@pytest.mark.parametrize("caso", CASOS_DOMINIO, ids=[c["caso_id"] for c in CASOS_DOMINIO])
def test_caso_de_dominio_desde_csv(caso):
    row = PEDIDOS[caso["pedido_id"]]
    order = pedido_desde_csv(row)
    deuda = float(row["deuda_cliente"])
    esperado = EXPECTATIVA_ACTUALIZADA.get(caso["caso_id"], caso["resultado_esperado"])

    if esperado.startswith("CONFIRMED"):
        cobro_esperado = float(esperado.split("cobro")[1])
        assert order.confirm(customer_debt=deuda) == pytest.approx(cobro_esperado, abs=0.005)
        assert order.status == "CONFIRMED"
    elif esperado.startswith("CustomerHasDebt"):
        with pytest.raises(CustomerHasDebt):
            order.confirm(customer_debt=deuda)
        assert order.status == row["estado_inicial"]
    elif esperado.startswith("ValueError"):
        with pytest.raises(ValueError):
            order.confirm(customer_debt=deuda)
    else:  # pragma: no cover - protege contra filas mal escritas en el CSV
        pytest.fail(f"Resultado esperado no reconocido: {esperado}")


def test_cp13_pago_rechazado_con_mock():
    gateway = Mock()
    gateway.charge.return_value = False
    with pytest.raises(RuntimeError, match="payment rejected"):
        OrderService(gateway).checkout(Order(120))
    gateway.charge.assert_called_once_with(120)


def test_cp14_registro_visible_despues_de_commit():
    engine = make_engine()
    with Session(engine) as s:
        SqlOrderRepository(s).save(14, pedido_desde_csv(PEDIDOS["1"]))
        s.commit()
    with Session(engine) as s:
        assert s.get(OrderRow, 14) is not None


def test_cp15_registro_ausente_despues_de_rollback():
    engine = make_engine()
    with Session(engine) as s:
        SqlOrderRepository(s).save(15, pedido_desde_csv(PEDIDOS["1"]))
        s.rollback()
    with Session(engine) as s:
        assert s.get(OrderRow, 15) is None

"""Pruebas de INTEGRACIÓN: dominio + SQLAlchemy + SQLite en memoria.

Cada prueba crea su propio motor (make_engine) => no se toca ninguna base de producción
ni el archivo didáctico datos/pedidos_prueba.sqlite3.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.domain import Order
from src.repository import OrderRow, SqlOrderRepository, make_engine


def test_repository_commit():
    engine = make_engine()
    with Session(engine) as session:
        SqlOrderRepository(session).save(1, Order(120))
        session.commit()
        assert session.scalar(select(OrderRow).where(OrderRow.id == 1)).total == 120


def test_repository_rollback():
    engine = make_engine()
    with Session(engine) as session:
        SqlOrderRepository(session).save(1, Order(120))
        session.rollback()
        assert session.scalar(select(OrderRow).where(OrderRow.id == 1)) is None


# ---------------------------------------------------------------------------
# Paso 4 · Evidencia E4
# ---------------------------------------------------------------------------
def test_commit_pedido_250_id_2_persiste_id_total_y_estado():
    # Arrange: base de prueba aislada y un pedido confirmado de 250
    engine = make_engine()
    order = Order(250)
    order.confirm()
    # Act: guardar y confirmar la transacción
    with Session(engine) as session:
        SqlOrderRepository(session).save(2, order)
        session.commit()
    # Assert: se lee desde una sesión NUEVA (no desde la caché de la sesión anterior)
    with Session(engine) as other_session:
        row = other_session.get(OrderRow, 2)
        assert row is not None
        assert (row.id, row.total, row.status) == (2, 250, "CONFIRMED")


def test_rollback_no_borra_lo_confirmado_antes():
    engine = make_engine()
    with Session(engine) as session:
        repo = SqlOrderRepository(session)
        repo.save(1, Order(120))
        session.commit()                 # límite transaccional 1: persiste
        repo.save(2, Order(250))
        session.rollback()               # límite transaccional 2: se descarta
    with Session(engine) as check:
        ids = check.scalars(select(OrderRow.id).order_by(OrderRow.id)).all()
        assert ids == [1]


def test_id_duplicado_viola_unicidad_y_se_revierte():
    engine = make_engine()
    with Session(engine) as session:
        repo = SqlOrderRepository(session)
        repo.save(1, Order(120))
        session.commit()
        repo.save(1, Order(999))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    with Session(engine) as check:
        assert check.get(OrderRow, 1).total == 120   # el valor original no cambió

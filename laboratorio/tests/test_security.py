"""Autorización de cancelación (src/security.py). Fechas FIJAS y `now` explícito."""
from datetime import UTC, datetime, timedelta

import pytest

from src.security import can_cancel


def test_owner_within_24h():
    now = datetime.now(UTC)
    assert can_cancel("NEW", 1, 1, False, now - timedelta(hours=1), now)


def test_stranger_denied():
    now = datetime.now(UTC)
    assert not can_cancel("NEW", 1, 2, False, now, now)


def test_shipped_denied_even_admin():
    now = datetime.now(UTC)
    assert not can_cancel("SHIPPED", 1, 1, True, now, now)


def test_expired_denied():
    now = datetime.now(UTC)
    assert not can_cancel("NEW", 1, 1, False, now - timedelta(hours=25), now)


# ---------------------------------------------------------------------------
# Paso 6 · Evidencia E6 (fechas fijas => resultados reproducibles)
# ---------------------------------------------------------------------------
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
OWNER, STRANGER, ADMIN = 1, 2, 99


def test_admin_cancela_pedido_new_de_otro_usuario():
    assert can_cancel("NEW", OWNER, ADMIN, True, NOW - timedelta(hours=72), NOW)


def test_propietario_exactamente_a_las_24h_es_rechazado():
    assert not can_cancel("NEW", OWNER, OWNER, False, NOW - timedelta(hours=24), NOW)


def test_propietario_un_segundo_antes_de_24h_es_permitido():
    assert can_cancel("NEW", OWNER, OWNER, False, NOW - timedelta(hours=23, minutes=59, seconds=59), NOW)


def test_now_por_defecto_usa_reloj_utc():
    """Cubre la rama `now=None`: pedido recién creado por su dueño."""
    assert can_cancel("NEW", OWNER, OWNER, False, datetime.now(UTC))


# Matriz de autorización completa (rol, propietario, estado, antigüedad -> resultado)
MATRIZ = [
    # id,   estado,      dueño, usuario,  admin, horas, permitido
    ("A01", "NEW",       OWNER, OWNER,    False, 1,     True),
    ("A02", "NEW",       OWNER, OWNER,    False, 24,    False),
    ("A03", "NEW",       OWNER, OWNER,    False, 25,    False),
    ("A04", "NEW",       OWNER, STRANGER, False, 1,     False),
    ("A05", "NEW",       OWNER, ADMIN,    True,  72,    True),
    ("A06", "CONFIRMED", OWNER, OWNER,    False, 2,     True),
    ("A07", "CONFIRMED", OWNER, ADMIN,    True,  2,     True),
    ("A08", "SHIPPED",   OWNER, OWNER,    False, 1,     False),
    ("A09", "SHIPPED",   OWNER, ADMIN,    True,  1,     False),
]


@pytest.mark.parametrize("caso,estado,dueno,usuario,admin,horas,esperado", MATRIZ,
                         ids=[m[0] for m in MATRIZ])
def test_matriz_de_autorizacion(caso, estado, dueno, usuario, admin, horas, esperado):
    assert can_cancel(estado, dueno, usuario, admin, NOW - timedelta(hours=horas), NOW) is esperado

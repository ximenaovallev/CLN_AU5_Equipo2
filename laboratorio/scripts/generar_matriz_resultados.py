"""Genera la matriz de resultados REALES vs ESPERADOS de CP01-CP15 ejecutando el código de src/.

Uso (desde laboratorio/):  python scripts/generar_matriz_resultados.py
Salida: ../evidencias/matriz_resultados_laboratorio.csv
"""
import csv
import sys
from pathlib import Path
from unittest.mock import Mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from sqlalchemy.orm import Session

from src.application import OrderService
from src.domain import Order
from src.repository import OrderRow, SqlOrderRepository, make_engine

DATOS = RAIZ / "datos"
SALIDA = RAIZ.parent / "evidencias" / "matriz_resultados_laboratorio.csv"
ACTUALIZADO = {"CP08": "ValueError: already confirmed (expectativa actualizada por TDD, Paso 3)"}
# CP12 es un caso límite de redondeo: 99.99 x 15 % = 14.9985 -> descuento 15.00 -> cobro 84.99.
TIPO_POR_CASO = {"CP12": "Límite"}
PRUEBA = {"CP13": "test_cp13_pago_rechazado_con_mock",
          "CP14": "test_cp14_registro_visible_despues_de_commit",
          "CP15": "test_cp15_registro_ausente_despues_de_rollback"}


def leer(nombre):
    with (DATOS / nombre).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def tipo(escenario):
    return {"VALIDO": "Éxito", "DEUDA": "Error", "TOTAL_CERO": "Límite", "TOTAL_NEGATIVO": "Error",
            "LIMITE": "Límite", "YA_CONFIRMADO": "Error (TDD)"}.get(escenario, "Integración")


def ejecutar_confirmar(p):
    order = Order(float(p["total"]), p["es_vip"] == "1", p["estado_inicial"])
    try:
        cobro = order.confirm(customer_debt=float(p["deuda_cliente"]))
        return f"{order.status}, cobro {cobro:.2f}"
    except Exception as e:  # noqa: BLE001 - se registra el tipo real de la excepción
        return f"{type(e).__name__}: {e}"


def ejecutar_especial(caso_id):
    if caso_id == "CP13":
        gw = Mock()
        gw.charge.return_value = False
        try:
            OrderService(gw).checkout(Order(120))
            return "Sin excepción"
        except RuntimeError as e:
            return f"RuntimeError: {e} (mock llamado con {gw.charge.call_args.args[0]})"
    engine = make_engine()
    with Session(engine) as s:
        SqlOrderRepository(s).save(1, Order(120))
        s.commit() if caso_id == "CP14" else s.rollback()
    with Session(engine) as s:
        row = s.get(OrderRow, 1)
        return "Registro visible después de commit" if row else "Registro ausente después de rollback"


def coincide(esperado, real):
    if esperado.startswith("CONFIRMED"):
        return real.replace(" ", "") == esperado.replace(" ", "")
    return real.split(":")[0].split(" ")[0] == esperado.split(":")[0].split(" ")[0] or real.startswith(esperado)


def main():
    pedidos = {p["pedido_id"]: p for p in leer("pedidos_prueba.csv")}
    filas = []
    for c in leer("casos_de_prueba.csv"):
        cid = c["caso_id"]
        esperado = ACTUALIZADO.get(cid, c["resultado_esperado"])
        if c["pedido_id"]:
            p = pedidos[c["pedido_id"]]
            entrada = (f"total={p['total']}, vip={p['es_vip']}, deuda={p['deuda_cliente']}, "
                       f"estado={p['estado_inicial']}")
            real, prueba = ejecutar_confirmar(p), f"test_caso_de_dominio_desde_csv[{cid}]"
            t = TIPO_POR_CASO.get(cid, tipo(p["escenario"]))
        else:
            entrada, real, t, prueba = c["accion"], ejecutar_especial(cid), "Integración", PRUEBA[cid]
        filas.append({"caso_id": cid, "pedido_id": c["pedido_id"], "entrada": entrada, "tipo": t,
                      "resultado_esperado_original": c["resultado_esperado"], "resultado_esperado": esperado,
                      "resultado_real": real, "estado": "PASA" if coincide(esperado, real) else "FALLA",
                      "prueba_automatizada": prueba, "nota": c["nota"]})
    SALIDA.parent.mkdir(exist_ok=True)
    with SALIDA.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    for r in filas:
        print(f"{r['caso_id']:5} {r['estado']:5} esperado={r['resultado_esperado'][:40]:40} real={r['resultado_real']}")
    print(f"\nMatriz escrita en {SALIDA.relative_to(RAIZ.parent)}")


if __name__ == "__main__":
    main()

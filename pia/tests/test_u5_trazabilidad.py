"""U5 · La matriz de casos (tests/casos_pia.csv) y las pruebas no pueden desalinearse."""
import ast
import csv
from collections import Counter
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def _casos():
    with (TESTS / "casos_pia.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _funciones_de_prueba():
    nombres = set()
    for archivo in TESTS.glob("test_*.py"):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        nombres |= {n.name for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")}
    return nombres


def test_cada_caso_de_la_matriz_tiene_una_prueba_ejecutable():
    faltantes = [c["caso_id"] for c in _casos() if c["prueba"] not in _funciones_de_prueba()]
    assert faltantes == []


def test_la_matriz_cumple_el_minimo_de_la_guia():
    casos = _casos()
    reglas = {c["regla"].split(" ")[0] for c in casos if c["regla"].startswith("R")}
    por_tipo = Counter(c["tipo"] for c in casos)
    assert len(casos) >= 9 and len(reglas) >= 3
    assert por_tipo["Éxito"] >= 3 and por_tipo["Error"] >= 3 and por_tipo["Límite"] >= 3
    assert {"Unitaria", "Integración", "Flujo"} <= {c["nivel"] for c in casos}

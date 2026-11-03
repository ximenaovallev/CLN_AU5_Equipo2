"""Ejecuta las pruebas U5 del PIA y genera la matriz de casos con resultado REAL y estado.

Uso (desde pia/):  python scripts/generar_matriz_pia.py
Entrada: tests/casos_pia.csv (definición: regla, origen, entrada, esperado, tipo, nivel, prueba)
Salida:  ../evidencias/matriz_casos_pia.csv
El resultado real lo registra cada prueba con record_property (fixture `registrar`).
"""
import csv
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

PIA = Path(__file__).resolve().parent.parent
SALIDA = PIA.parent / "evidencias" / "matriz_casos_pia.csv"


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "junit.xml"
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-k", "pia",
                        f"--junitxml={xml}", "-o", "junit_family=xunit1"], cwd=PIA, check=False)
        reales = {}
        for tc in ET.parse(xml).iter("testcase"):
            props = {p.get("name"): p.get("value") for p in tc.iter("property")}
            fallo = tc.find("failure") is not None or tc.find("error") is not None
            if "caso" in props:
                reales[props["caso"]] = (props.get("resultado_real", ""), "FALLA" if fallo else "PASA")
            elif fallo:
                reales[tc.get("name")] = ("(falló antes de registrar)", "FALLA")
    with (PIA / "tests" / "casos_pia.csv").open(encoding="utf-8", newline="") as f:
        casos = list(csv.DictReader(f))
    for c in casos:
        real, estado = reales.get(c["caso_id"], reales.get(c["prueba"], ("NO EJECUTADO", "FALLA")))
        c["resultado_real"], c["estado"] = real, estado
    SALIDA.parent.mkdir(exist_ok=True)
    with SALIDA.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(casos[0]))
        w.writeheader()
        w.writerows(casos)
    for c in casos:
        print(f"{c['caso_id']}  {c['estado']:5}  {c['tipo']:7}  {c['resultado_real'][:90]}")
    fallas = sum(c["estado"] != "PASA" for c in casos)
    print(f"\n{len(casos)} casos · {len(casos) - fallas} PASA · {fallas} FALLA -> {SALIDA.relative_to(PIA.parent)}")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())

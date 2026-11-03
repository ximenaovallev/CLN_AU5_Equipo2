#!/usr/bin/env bash
# Reproduce localmente los MISMOS pasos de .github/workflows/ci.yml (ambos jobs).
# Uso: bash scripts/ci_local.sh      (requiere el .venv activado o python con las dependencias)
set -u
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
estado=0
paso() { echo "  \$ $*"; "$@" > /tmp/ci_paso.log 2>&1; local rc=$?; tail -n 4 /tmp/ci_paso.log | sed 's/^/    /'
         if [ $rc -ne 0 ]; then echo "    ✗ FALLÓ (exit $rc)"; return 1; fi; echo "    ✓ ok"; }
job() { local nombre=$1 dir=$2 cov=$3; shift 3
  echo "== job: $nombre (working-directory: $dir)"; cd "$RAIZ/$dir" || return 1
  paso ruff check src tests &&
  paso python -m pytest -q -p no:cacheprovider --cov="$cov" --cov-report=term-missing --cov-report=html --cov-fail-under=80 &&
  { [ "$dir" != pia ] || paso python scripts/generar_matriz_pia.py; } &&
  paso python -m compileall -q src
  local rc=$?; if [ $rc -eq 0 ]; then echo "== $nombre: ✅ VERDE"; else echo "== $nombre: ❌ ROJO"; fi; return $rc; }
echo "commit: $(git -C "$RAIZ" log -1 --format='%h %s')"
job laboratorio laboratorio src || estado=1
job pia pia rutanorte || estado=1
[ $estado -eq 0 ] && echo "RESULTADO PIPELINE: ✅ success" || echo "RESULTADO PIPELINE: ❌ failure"
exit $estado

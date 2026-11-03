#!/usr/bin/env bash
# Publica el repositorio en GitHub en TRES pushes para obtener en Actions las ejecuciones
# verde -> roja -> verde que pide la evidencia E8. Cada push dispara su propia ejecución.
# Uso:  bash scripts/publicar_en_github.sh https://github.com/USUARIO/CLN_U5_02_RutaNorte_Logistics.git
# Antes: crea el repositorio VACÍO en GitHub (sin README ni .gitignore).
set -euo pipefail
URL="${1:?Indica la URL del repositorio de GitHub}"
git remote remove origin 2>/dev/null || true
git remote add origin "$URL"

echo "1/3 · push del commit VERDE (ci-1-verde)"
git push -u origin "ci-1-verde^{commit}:refs/heads/main"
read -rp "Abre la pestaña Actions, espera la marca verde, toma la captura y presiona Enter... "

echo "2/3 · push del commit ROJO (ci-2-rojo: aserción falsa temporal)"
git push origin "ci-2-rojo^{commit}:refs/heads/main"
read -rp "Espera la marca roja (job Laboratorio falla en pytest), toma la captura y presiona Enter... "

echo "3/3 · push de main (revert + documentación) -> debe volver a VERDE"
git push origin main
echo "Listo. Captura la ejecución verde final y copia la URL del repositorio en docs (E8)."

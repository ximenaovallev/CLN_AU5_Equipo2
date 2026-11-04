# Unidad 5 · Integración, pruebas y calidad — RutaNorte Logistics

**Curso:** Componentes de Lógica de Negocio · **Profesor:** Miguel Ángel Gómez Marroquín
**Equipo 02:** Ximena Montserrat Ovalle Vallejo (1999238) · Santiago Almanza Moreno (2001903) · Javier Hernández Huerta (2089204)
**PIA:** RutaNorte Logistics (misma empresa y alcance de las Unidades 2 y 3 · repositorio U3: <https://github.com/ximenaovallev/CLN_02_RutaNorte_Logistics>)
**Repositorio U5:** <https://github.com/ximenaovallev/CLN_AU5_Equipo2>

Este repositorio contiene las dos partes del laboratorio guiado de la Unidad 5:

| Carpeta | Qué es | Pruebas | Cobertura |
|---|---|---|---|
| [`laboratorio/`](laboratorio) | Proyecto base de pedidos (Pasos 1–7) con las pruebas pedidas por la guía y los casos CP01–CP15 de los CSV | 51 + 1 xfail documentado | 100 % de `src/` |
| [`pia/`](pia) | Código U3 de RutaNorte (sin cambios de comportamiento) + suite U5 con 23 casos PIA-01…PIA-23 (Paso 9) | 56 (30 de U3 + 26 de U5) | 99.76 % de `rutanorte` |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | Pipeline con dos jobs: lint → pruebas → cobertura ≥80 % → (matriz PIA) → build | — | — |
| [`evidencias/`](evidencias) | Reporte de evidencias E1–E9 (`CLN_AU5_Equipo2_REPORTE.docx` y `.pdf`, con el plan de pruebas en la sección 2.1), matrices CSV (CP01–CP15: 5 éxito, 4 error, 3 límite y 3 integración; PIA-01…PIA-23) y capturas de cada paso | — | — |

## Instalación y comandos

Requiere Python 3.11 o superior.

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1           # macOS/Linux: source .venv/bin/activate
python -m pip install -r laboratorio/requirements.txt   # mismo archivo que pia/requirements.txt

# Laboratorio (pedidos)
cd laboratorio
python -m ruff check src tests
python -m pytest -v --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=80
python scripts/generar_matriz_resultados.py   # -> evidencias/matriz_resultados_laboratorio.csv

# PIA RutaNorte
cd ../pia
python -m ruff check src tests
python -m pytest -v --cov=rutanorte --cov-report=term-missing --cov-report=html --cov-fail-under=80
python -m pytest -m unitaria   # o -m integracion / -m flujo
python scripts/generar_matriz_pia.py          # -> evidencias/matriz_casos_pia.csv

# Pipeline completo en local (mismos pasos que GitHub Actions; requiere bash)
cd .. && bash scripts/ci_local.sh
```

Los reportes HTML quedan en `laboratorio/htmlcov/index.html` y `pia/htmlcov/index.html` (no se versionan; el CI los publica como artefactos).

## Arquitectura y niveles de prueba

```
Usuario/API (no existe aún) → Handlers (Service Layer) → OrdenDeServicio / Cotizacion / AsignadorDeRecursos
                                      ↓ puertos (IUnitOfWork, repositorios, IPublicadorDeEventos)
             EnMemoriaUnitOfWork  |  SqlAlchemyUnitOfWork (U5, pruebas)  |  Mock(spec=IPublicadorDeEventos)
```

| Nivel | Qué verifica | Dónde | Dependencias |
|---|---|---|---|
| **Unitaria** | Una regla del dominio aislada | `laboratorio/tests/test_order.py`, `test_security.py`; `pia/tests/test_u5_reglas_pia.py` (`-m unitaria`) | Ninguna: sin BD, red ni pasarela |
| **Integración** | Dominio + persistencia / servicio externo simulado | `test_repository.py`, `test_service.py`; `pia/tests/test_u5_persistencia_sqlalchemy.py`, `test_u5_publicador_mock.py` | SQLite **en memoria** (nunca producción), `unittest.mock` |
| **Flujo (sustituto de E2E)** | Proceso CU-01→CU-05 completo por la raíz de composición | `pia/tests/test_u5_flujo_completo.py` | Implementaciones en memoria |

**Sobre E2E.** Ni el proyecto base ni RutaNorte tienen API o interfaz; por eso no se finge una prueba E2E. El escenario E2E propuesto para cuando exista la API es: *cliente acepta la cotización por HTTP → Operaciones asigna unidad y operador → operador registra llegada y entrega con foto desde el móvil → Atención al Cliente consulta el estado en el navegador y ve “Entregado”*, ejecutado con Playwright contra un entorno de staging con base PostgreSQL desechable.

## Decisiones y hallazgos

1. **TDD (Paso 3).** Regla nueva “no confirmar dos veces”: primero se escribió `test_cannot_confirm_twice` y se ejecutó en RED (`DID NOT RAISE ValueError`), luego la implementación mínima (GREEN) y después el REFACTOR (validaciones en `_ensure_can_be_confirmed`), con la suite completa en verde. Las capturas de cada fase están en `evidencias/capturas/`. El caso CP08 del CSV se actualizó de `CONFIRMED` a `ValueError: already confirmed`.
2. **Riesgo de consistencia en el cobro (Paso 5).** `OrderService.checkout` confirma el pedido antes de cobrar; si la pasarela rechaza, el pedido queda `CONFIRMED`. Se documenta con una prueba del comportamiento actual y una prueba `xfail(strict=True)` con la mejora propuesta (confirmar solo tras pago aprobado o compensar a `PAYMENT_FAILED`).
3. **Riesgo equivalente en RutaNorte (PIA-22).** Los handlers confirman y luego publican eventos; si el bus falla, la asignación queda confirmada sin aviso a Operaciones. Propuesta: patrón *Outbox*.
4. **Ruff sin versión fija.** `ruff>=0.6` instala hoy la 0.17.3, que activa reglas nuevas (I001, UP017): el ZIP base **original** falla el lint (12 errores). Se aplicó `ruff --fix` y se fijaron las versiones en `requirements.txt` para que el CI sea reproducible.
5. **Adaptador SQLAlchemy del PIA.** ADR-002 sigue vigente (la tecnología de BD no está definida). `SqlAlchemyUnitOfWork` es una segunda implementación de los puertos solo para pruebas: comprueba commit/rollback reales y cierra el hallazgo SOLID #5 de la U3 (sustitución de Liskov no probada): PIA-18 ejecuta el mismo flujo sobre ambas implementaciones con resultados idénticos.
6. **Supuestos S-01 y S-04.** PIA-08 y PIA-13…15 prueban supuestos **pendientes de validar** como parámetros; los valores (p. ej. tope 4.0 m³) son de prueba, no del negocio.
7. **Cobertura ≠ corrección.** Las ramas no ejecutadas que quedan en el PIA son la propiedad `alto_valor_autorizado` (nadie la lee fuera del agregado) y `revertir()` llamado sin instantánea; están explicadas en el reporte (E9).

8. **`pythonpath` en el laboratorio.** El pipeline usa `pytest` y en la laptop usamos `python -m pytest`; solo el segundo agrega la carpeta actual a la ruta de importación. GitHub Actions detectó la diferencia en la primera ejecución y se corrigió en `laboratorio/pyproject.toml`.

## Pipeline CI y evidencia E8

`ci.yml` corre en cada `push` y `pull_request` con dos jobs independientes: **Laboratorio (pedidos)** y **PIA RutaNorte Logistics**. Cada uno hace checkout → Python 3.11 → dependencias → Ruff → pytest con `--cov-fail-under=80` → (matriz PIA) → `compileall`, y publica el reporte HTML de cobertura como artefacto.

Comprobación del bloqueo en GitHub Actions (pestaña **Actions**):

0. **Primera ejecución (roja, error real):** el job Laboratorio falló con exit code 2 porque el workflow llama a `pytest` (sin `python -m`) y el laboratorio no tenía `pythonpath`, así que no encontraba el paquete `src`. Se corrigió con `pythonpath = ["."]` en `laboratorio/pyproject.toml`.
1. **#2 · Verde:** ambos jobs pasan tras la corrección.
2. **#3 · Roja:** se cambió temporalmente `assert o.confirm() == 85` por `== 90` en `laboratorio/tests/test_order.py`; el job Laboratorio falló en pytest (`assert 85.0 == 90`) y el job PIA siguió en verde.
3. **#4 · Verde recuperada:** se revirtió la aserción y ambos jobs regresaron a verde.

Las capturas de estas ejecuciones están en `evidencias/capturas/` (`E8_github_*`) y en el reporte (Figuras 16 a 20).

Para que GitHub **bloquee** el merge hay que activar *branch protection / ruleset* en `main` exigiendo los checks `Laboratorio (pedidos)` y `PIA RutaNorte Logistics`; el YAML por sí solo no bloquea.

**URL del repositorio (E8):** <https://github.com/ximenaovallev/CLN_AU5_Equipo2>

## Datos

Todos los datos son ficticios. `laboratorio/datos/` contiene los CSV y la base SQLite didáctica del ZIP; las pruebas usan SQLite en memoria y nunca modifican ese archivo. No se incluyen `.venv`, tokens, claves ni datos personales.

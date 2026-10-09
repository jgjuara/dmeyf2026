# Versionado del pipeline FE

Los scripts `build_*_vN.py` son **inmutables**: si cambia la lógica de cálculo, copiar a `build_*_v(N+1).py` y escribir parquets con el token `_v(N+1)` en el nombre. No hay alias hacia nombres sin versión.

**Crudo (sin versión):** `competencia_01_crudo.csv` — [`download_competencia_crudo.py`](download_competencia_crudo.py).

## Convención de nombres

| Tipo | Patrón | Ejemplo |
|------|--------|---------|
| Script base | `build_<familia>_vN.py` | `build_rankings_v1.py` |
| Script derivado | `build_<familia>_vN_<capa>.py` | `build_rankings_v1_lag1.py`, `build_competencia_continuas_v1_delta1.py` |
| Parquet | `<familia>_vN[_<capa>].parquet` | `rankings_v1_lag1.parquet`, `competencia_01_nocontinuas_v1.parquet` |

El token `_vN` va **antes** de sufijos de capa (`_lag1`, `_delta2`, etc.).

## Cadena v1 (entrada FE = `competencia_01_clean_v1.parquet`)

| Script | Lee | Escribe |
|--------|-----|---------|
| `build_competencia_01_parquet_v1.py` | `competencia_01_crudo.csv` | `competencia_01_v1.parquet` |
| `build_competencia_01_clean_v1.py` | `competencia_01_v1.parquet` | `competencia_01_clean_v1.parquet` |
| `build_competencia_nocontinuas_v1.py` | clean v1 | `competencia_01_nocontinuas_v1.parquet` |
| `build_competencia_continuas_v1.py` | clean v1 | `competencia_01_continuas_v1.parquet` |
| `build_rankings_v1.py` | clean v1 | `rankings_v1.parquet` |
| `build_competencia_nocontinuas_v1_lag1.py` | nocontinuas v1 | `competencia_01_nocontinuas_v1_lag1.parquet` |
| `build_competencia_nocontinuas_v1_lag2.py` | nocontinuas v1 | `competencia_01_nocontinuas_v1_lag2.parquet` |
| `build_competencia_continuas_v1_lag1.py` | continuas v1 | `competencia_01_continuas_v1_lag1.parquet` |
| `build_competencia_continuas_v1_lag2.py` | continuas v1 | `competencia_01_continuas_v1_lag2.parquet` |
| `build_competencia_continuas_v1_delta1.py` | continuas v1 | `competencia_01_continuas_v1_delta1.parquet` |
| `build_competencia_continuas_v1_delta2.py` | continuas v1 | `competencia_01_continuas_v1_delta2.parquet` |
| `build_rankings_v1_lag1.py` | `rankings_v1.parquet` | `rankings_v1_lag1.parquet` |
| `build_rankings_v1_lag2.py` | `rankings_v1.parquet` | `rankings_v1_lag2.parquet` |
| `build_rankings_v1_delta1.py` | `rankings_v1.parquet` | `rankings_v1_delta1.parquet` |
| `build_rankings_v1_delta2.py` | `rankings_v1.parquet` | `rankings_v1_delta2.parquet` |
| `build_rankings_v2.py` | clean v1 | `rankings_v2.parquet` |
| `build_competencia_continuas_v2.py` | clean v1 | `competencia_01_continuas_v2.parquet` |
| `build_rankings_v2_delta2.py` | `rankings_v2.parquet` | `rankings_v2_delta2.parquet` |
| `build_competencia_continuas_v2_delta2.py` | continuas v2 | `competencia_01_continuas_v2_delta2.parquet` |

**Semántica delta2:** en v1, `delta2 = t0 − lag2` (histórico). En v2, `delta2 = lag1 − lag2`. `delta1` sigue siendo `t0 − lag1` en ambas versiones.

Lags y deltas de una versión **solo** leen la capa base de la **misma** versión (p. ej. `build_rankings_v2_lag1.py` leería `rankings_v2.parquet`, no `rankings_v1.parquet`).

Rutas centralizadas: [`paths.py`](paths.py).

## Crear v2 (ejemplo)

1. Copiar `build_rankings_v1.py` → `build_rankings_v2.py` y ajustar lógica.
2. Cambiar destino a `rankings_v2.parquet` y fuentes a `competencia_parquet_v2()` / clean v2 según corresponda.
3. Añadir `rankings_v2_parquet()`, `rankings_v2_lag1_parquet()`, … en `paths.py`.
4. Copiar scripts derivados (`build_rankings_v2_lag1.py`, …) si aplica.
5. Experimentos nuevos referencian explícitamente capas v2 en `layers.py` / `compe1_layers.R`.

Alternativa labeled: `Rscript juara/generar_clase_ternaria_parquet.R` escribe `competencia_01_v1.parquet` (misma semántica que el builder Python de parquet v1).

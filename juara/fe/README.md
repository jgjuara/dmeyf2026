# Ingeniería de variables (`juara/fe`)

Scripts DuckDB para materializar artefactos Parquet de la competencia 01 en `juara/data` (o `JUARA_DATA_DIR`). La cadena activa es **v1**; convenciones de versionado y tabla entrada/salida en [`nota.md`](nota.md).

Ejecución desde `juara/`:

```powershell
uv run fe/<script>.py
```

## Índice

1. [Flujo v1](#flujo-v1)
2. [Ingesta](#ingesta)
3. [Base y limpieza](#base-y-limpieza)
4. [Capas desde clean v1](#capas-desde-clean-v1)
5. [Lags y deltas](#lags-y-deltas)
6. [Módulos compartidos](#módulos-compartidos)
7. [Variables de entorno](#variables-de-entorno)

---

## Flujo v1

```text
competencia_01_crudo.csv
  → build_competencia_01_parquet_v1.py → competencia_01_v1.parquet
  → build_competencia_01_clean_v1.py   → competencia_01_clean_v1.parquet  ← entrada FE (competencia_parquet_v1)
       ├→ build_competencia_nocontinuas_v1.py → competencia_01_nocontinuas_v1.parquet
       ├→ build_competencia_continuas_v1.py   → competencia_01_continuas_v1.parquet
       └→ build_rankings_v1.py                → rankings_v1.parquet
            └→ lag/delta sobre cada familia (misma versión v1)
```

Alternativa al primer paso Python: `Rscript juara/generar_clase_ternaria_parquet.R` produce `competencia_01_v1.parquet` con semántica equivalente al builder labeled.

---

## Ingesta

| Script | Descripción |
|--------|-------------|
| [`download_competencia_crudo.py`](download_competencia_crudo.py) | Descarga `competencia_01_crudo.csv` a `juara/data` vía HTTP (`JUARA_DATA_BASE_URL`) y, si está configurado GCS, sincroniza con el bucket. |

---

## Base y limpieza

| Script | Lee | Escribe | Descripción |
|--------|-----|---------|-------------|
| [`build_competencia_01_parquet_v1.py`](build_competencia_01_parquet_v1.py) | `competencia_01_crudo.csv` | `competencia_01_v1.parquet` | CSV crudo → Parquet con `clase_ternaria` (labeled); sin reglas de limpieza de variables. |
| [`build_competencia_01_clean_v1.py`](build_competencia_01_clean_v1.py) | `competencia_01_v1.parquet` | `competencia_01_clean_v1.parquet` | Limpieza puntual (p. ej. imputaciones/reglas documentadas en el script); salida usada como `competencia_parquet_v1()` en el resto del pipeline. |

---

## Capas desde clean v1

| Script | Lee | Escribe | Descripción |
|--------|-----|---------|-------------|
| [`build_competencia_nocontinuas_v1.py`](build_competencia_nocontinuas_v1.py) | clean v1 | `competencia_01_nocontinuas_v1.parquet` | Claves, `clase_ternaria` y columnas listadas en `juara/docs/vars_nocontinuas.md`. |
| [`build_competencia_continuas_v1.py`](build_competencia_continuas_v1.py) | clean v1 | `competencia_01_continuas_v1.parquet` | Claves y métricas continuas (columnas del parquet que no son nocontinuas ni claves). |
| [`build_rankings_v1.py`](build_rankings_v1.py) | clean v1 | `rankings_v1.parquet` | Percentiles por `foto_mes` (`pct_<variable>`) sobre métricas continuas; procesamiento por lotes (`RANKINGS_PCT_BATCH`, límites DuckDB). |

---

## Lags y deltas

Por cliente (`PARTITION BY numero_de_cliente ORDER BY foto_mes`):

- **lag1 / lag2**: valor de la foto anterior (1 o 2 meses).
- **delta1**: `t0 − lag1` (`col - LAG(col, 1)`).
- **delta2 v1** (histórico): `t0 − lag2`. **delta2 v2**: `lag1 − lag2` (`LAG(col, 1) - LAG(col, 2)`).

Cada derivado lee solo la capa base de la **misma** versión de su familia (no mezcla versiones).

### Rankings v2 (delta2 corregido)

| Script | Salida |
|--------|--------|
| [`build_rankings_v2.py`](build_rankings_v2.py) | `rankings_v2.parquet` (misma lógica que v1) |
| [`build_rankings_v2_delta2.py`](build_rankings_v2_delta2.py) | `rankings_v2_delta2.parquet` |

### Continuas v2 (delta2 corregido)

| Script | Salida |
|--------|--------|
| [`build_competencia_continuas_v2.py`](build_competencia_continuas_v2.py) | `competencia_01_continuas_v2.parquet` |
| [`build_competencia_continuas_v2_delta2.py`](build_competencia_continuas_v2_delta2.py) | `competencia_01_continuas_v2_delta2.parquet` |

### Rankings (`pct_*`)

| Script | Salida |
|--------|--------|
| [`build_rankings_v1_lag1.py`](build_rankings_v1_lag1.py) | `rankings_v1_lag1.parquet` (`lag1_pct_*`) |
| [`build_rankings_v1_lag2.py`](build_rankings_v1_lag2.py) | `rankings_v1_lag2.parquet` |
| [`build_rankings_v1_delta1.py`](build_rankings_v1_delta1.py) | `rankings_v1_delta1.parquet` (`delta1_pct_*`) |
| [`build_rankings_v1_delta2.py`](build_rankings_v1_delta2.py) | `rankings_v1_delta2.parquet` |

### Nocontinuas

| Script | Salida |
|--------|--------|
| [`build_competencia_nocontinuas_v1_lag1.py`](build_competencia_nocontinuas_v1_lag1.py) | `competencia_01_nocontinuas_v1_lag1.parquet` |
| [`build_competencia_nocontinuas_v1_lag2.py`](build_competencia_nocontinuas_v1_lag2.py) | `competencia_01_nocontinuas_v1_lag2.parquet` |

### Continuas

| Script | Salida |
|--------|--------|
| [`build_competencia_continuas_v1_lag1.py`](build_competencia_continuas_v1_lag1.py) | `competencia_01_continuas_v1_lag1.parquet` |
| [`build_competencia_continuas_v1_lag2.py`](build_competencia_continuas_v1_lag2.py) | `competencia_01_continuas_v1_lag2.parquet` |
| [`build_competencia_continuas_v1_delta1.py`](build_competencia_continuas_v1_delta1.py) | `competencia_01_continuas_v1_delta1.parquet` |
| [`build_competencia_continuas_v1_delta2.py`](build_competencia_continuas_v1_delta2.py) | `competencia_01_continuas_v1_delta2.parquet` |

---

## Módulos compartidos

| Archivo | Descripción |
|---------|-------------|
| [`paths.py`](paths.py) | Rutas de `DATA_DIR` y funciones `*_parquet()` por artefacto versionado. |
| [`columns.py`](columns.py) | Listado nocontinuas, columnas a rankear y reglas de exclusión en lags. |
| [`column_buckets.py`](column_buckets.py) | Taxonomía de buckets por nombre de columna (uso en capas de modelado / `layers.py`). |
| [`gcs_upload.py`](gcs_upload.py) | Subida y descarga opcional de artefactos con `gcloud` cuando `JUARA_GCS_BUCKET` o `COMPE1_GCS_BUCKET` está definido. |
| [`nota.md`](nota.md) | Política de versionado inmutable de scripts `build_*_vN` y guía para crear v2+. |

---

## Variables de entorno

| Variable | Uso |
|----------|-----|
| `JUARA_DATA_DIR` | Directorio de datos (default: `juara/data`). |
| `JUARA_DATA_BASE_URL` | URL base del CSV crudo en `download_competencia_crudo.py`. |
| `JUARA_FORCE_DOWNLOAD` | Forzar re-descarga del crudo. |
| `JUARA_GCS_BUCKET` / `COMPE1_GCS_BUCKET` | Habilita sync GCS en ingest y builders. |
| `JUARA_GCS_PREFIX` | Prefijo en el bucket (default `data`). |
| `RANKINGS_PCT_BATCH` | Tamaño de lote de percentiles en `build_rankings_v1.py`. |
| `DUCKDB_MEMORY_LIMIT`, `DUCKDB_THREADS`, `DUCKDB_TEMP_DIRECTORY` | Ajuste de recursos DuckDB en rankings. |

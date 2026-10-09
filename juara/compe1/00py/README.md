# 00py

Port Python del protocolo [`00`](../00/README.md): capa `competencia_01_v1.parquet`, split temporal mar–may / test junio, BO con **Optuna** en lugar de mlrMBO. Sin script `3_escalar` (no aplica a este experimento).

Convención intento–iteración: ver [`README.md`](../README.md#intentos-python-py). En la iteración `00`, **`experiment_id` = `00py-00`** (definido en [`00/_bootstrap.py`](00/_bootstrap.py)).

**Capas:** `competencia_01_v1.parquet`.

**Resultados:** `juara/compe1/00py-00/resultados/` (`bo/`, `produccion/`, `top20/`, `agosto/`, `estudio/top20_bo_semillas/`).

**Utilidades:** [`common/layers.py`](../common/layers.py), [`common/data.py`](../common/data.py), [`common/lgb_train.py`](../common/lgb_train.py), [`common/bo_space.py`](../common/bo_space.py), [`common/gcs_upload.py`](../common/gcs_upload.py).

## Comandos

Desde `juara/` (proyecto `uv`):

```bash
cd juara
uv run python compe1/00py/00/1_bayesiana_lightgbm.py
uv run python compe1/00py/00/2_produccion_lightgbm.py
uv run python compe1/00py/00/4_produccion_top20_bo_semillas.py
uv run python compe1/00py/00/5_analisis_top20_bo_semillas.py
uv run python compe1/00py/00/6_prediccion_agosto_top20_semillas.py
```

Variables útiles:

- `COMPE1_BO_ITER` — iteraciones Optuna (default `150`, como R script 1).

## VM spot y GCS (`--vm`)

En GCE, añadir `--vm` al comando activa lectura de parquets desde `gs://<bucket>/data/` y sync de resultados con `gs://<bucket>/compe1/00py-00/resultados/`. Sin `--vm`, solo disco local (aunque exista `COMPE1_GCS_BUCKET` en el entorno).

```bash
export JUARA_GCS_BUCKET=juarajuangabriel_buckito2026
cd juara
uv run python compe1/00py/00/1_bayesiana_lightgbm.py --vm
```

| Variable | Default | Uso |
|----------|---------|-----|
| `JUARA_GCS_BUCKET` / `COMPE1_GCS_BUCKET` | — | Bucket (obligatorio con `--vm`) |
| `JUARA_GCS_PREFIX` | `data` | Parquets de entrada |
| `COMPE1_GCS_PREFIX` | `compe1/00py-00/resultados` | Salidas del experimento |
| `COMPE1_GCS_SYNC_EVERY_TRIALS` | `1` | Script 1: rsync de `bo/` cada N trials |

Requisitos: `gcloud` en PATH; scope `devstorage.read_write` (ver [`juara/gce.md`](../../gce.md)).

## Paridad

| Componente | Paridad |
|------------|---------|
| Split temporal vs R | Mismo criterio por `foto_mes` |
| Objetivo BO | `temporal_cv_auc_mar_may` (2 folds mar→abr, mar–abr→may) |
| BO | No bit-a-bit (Optuna ≠ mlrMBO) |
| `3_escalar` | No incluido |

Checkpoint BO: `00py-00/resultados/bo/optuna.db`.

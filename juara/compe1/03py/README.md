# 03py

Port Python del protocolo [`00py`](../00py/README.md) con alcance FE de [`03_rank_nocont_lag1_delta1`](../archivo/03_rank_nocont_lag1_delta1/README.md): nocontinuas + rankings del mes, lag1 (nocontinuas + `pct_*` lag1) y `rankings_v1_delta1`. Split temporal mar–may / test junio, BO con **Optuna** (PR-AUC). Sin script `3_escalar`.

Convención intento–iteración: ver [`README.md`](../README.md#intentos-python-py). En la iteración `00`, **`experiment_id` = `03py-00`** (definido en [`00/_bootstrap.py`](00/_bootstrap.py)).

**Capas parquet** (orden de join; ver capas del intento `03py` en [`common/layers.py`](../common/layers.py)):

- `competencia_01_nocontinuas_v1.parquet`
- `rankings_v1.parquet`
- `competencia_01_nocontinuas_v1_lag1.parquet`
- `rankings_v1_lag1.parquet`
- `rankings_v1_delta1.parquet`

**Resultados:** `juara/compe1/03py-00/resultados/` (`bo/`, `produccion/`, `top20/`, `agosto/`, `estudio/top20_bo_semillas/`).

**Utilidades:** [`common/layers.py`](../common/layers.py), [`common/data.py`](../common/data.py), [`common/lgb_train.py`](../common/lgb_train.py), [`common/bo_space.py`](../common/bo_space.py), [`common/gcs_upload.py`](../common/gcs_upload.py).

## Prerequisitos FE

Desde `juara/`, con `competencia_01_clean_v1.parquet` en `juara/data/` (ver [`fe/nota.md`](../../fe/nota.md)):

```bash
cd juara
uv run python fe/build_competencia_nocontinuas_v1.py
uv run python fe/build_competencia_nocontinuas_v1_lag1.py
uv run python fe/build_rankings_v1.py
uv run python fe/build_rankings_v1_lag1.py
uv run python fe/build_rankings_v1_delta1.py
```

## Comandos pipeline

```bash
cd juara
uv run python compe1/03py/00/1_bayesiana_lightgbm.py
uv run python compe1/03py/00/2_produccion_lightgbm.py
uv run python compe1/03py/00/4_produccion_top20_bo_semillas.py
uv run python compe1/03py/00/5_analisis_top20_bo_semillas.py
uv run python compe1/03py/00/6_prediccion_agosto_top20_semillas.py
```

Variables útiles:

- `COMPE1_BO_ITER` — iteraciones Optuna (default `150`).

## VM spot y GCS (`--vm`)

Con `--vm`, los scripts bajan parquets desde `gs://<bucket>/data/` y sincronizan resultados con `gs://<bucket>/compe1/03py-00/resultados/`. Sin `--vm`, solo disco local (las variables de bucket no activan GCS por sí solas).

```bash
export JUARA_GCS_BUCKET=juarajuangabriel_buckito2026
cd juara
uv run python compe1/03py/00/1_bayesiana_lightgbm.py --vm
```

| Variable | Default | Uso |
|----------|---------|-----|
| `JUARA_GCS_BUCKET` / `COMPE1_GCS_BUCKET` | — | Bucket (obligatorio con `--vm`) |
| `JUARA_GCS_PREFIX` | `data` | Parquets de entrada |
| `COMPE1_GCS_PREFIX` | `compe1/03py-00/resultados` | Salidas del experimento |
| `COMPE1_GCS_SYNC_EVERY_TRIALS` | `1` | Script 1: rsync de `bo/` cada N trials Optuna |

Subidas incrementales: script 1 (cada trial según `COMPE1_GCS_SYNC_EVERY_TRIALS`), script 4 (cada `rank_##` y metadatos de estudio). Al terminar cada script se vuelve a sincronizar el directorio correspondiente.

Requisitos en la VM: `gcloud` en PATH; scope de almacenamiento con escritura e IAM de escritura sobre el bucket (ver [`juara/gce.md`](../../gce.md)).

## Paridad

| Componente | Paridad |
|------------|---------|
| Split temporal vs R `03_rank_nocont_lag1_delta1` | No (este intento usa holdout mar–may / jun como `00py`) |
| Undersampling 70/30 estratificado R | No (protocolo temporal `*py`) |
| Objetivo BO | `temporal_cv_average_precision_mar_may` (PR-AUC; 2 folds mar→abr, mar–abr→may) |
| Features | 5 capas (mismo join que `03_rank_nocont_lag1_delta1`) |
| BO | No bit-a-bit (Optuna ≠ mlrMBO) |
| `3_escalar` | No incluido |
| Agosto (`6_`) | Usa `rank_ganador` de `ganador.yml` (paso `5_`); fallback rank `3` |

Checkpoint BO: `03py-00/resultados/bo/optuna.db`.

# 04py

**Entrega final:** BO + `6_` con rank **1** y **3 semillas** (sin `4_`/`5_`); detalle en [`ENTREGA_FINAL.md`](ENTREGA_FINAL.md).

Port Python del protocolo [`00py`](../00py/README.md) con **FE completo** (8 capas parquet, equivalente a [`01_full_fe`](../archivo/01_full_fe/README.md) y [`01py`](../01py/README.md)): split temporal mar–may / test junio, BO con **Optuna** maximizando PR-AUC temporal. Sin script `3_escalar`.

Convención intento–iteración: ver [`README.md`](../README.md#intentos-python-py). En la iteración `00`, **`experiment_id` = `04py-00`** (definido en [`00/_bootstrap.py`](00/_bootstrap.py)).

**Capas parquet** (orden de join; ver capas del intento `04py` en [`common/layers.py`](../common/layers.py)):

- `competencia_01_nocontinuas_v1.parquet`
- `competencia_01_nocontinuas_v1_lag1.parquet`
- `competencia_01_nocontinuas_v1_lag2.parquet`
- `rankings_v1.parquet`
- `rankings_v1_lag1.parquet`
- `rankings_v1_lag2.parquet`
- `rankings_v1_delta1.parquet`
- `rankings_v1_delta2_v2.parquet`

**Resultados:** `juara/compe1/04py-00/resultados/` (`bo/`, `produccion/`, `top20/`, `agosto/`, `estudio/top20_bo_semillas/`).

**Utilidades:** [`common/layers.py`](../common/layers.py), [`common/data.py`](../common/data.py), [`common/lgb_train.py`](../common/lgb_train.py), [`common/bo_space.py`](../common/bo_space.py), [`common/gcs_upload.py`](../common/gcs_upload.py).

## Prerequisitos FE

Desde `juara/`, con `competencia_01_clean_v1.parquet` en `juara/data/` (ver [`fe/nota.md`](../../fe/nota.md)):

```bash
cd juara
uv run python fe/build_competencia_nocontinuas_v1.py
uv run python fe/build_competencia_nocontinuas_v1_lag1.py
uv run python fe/build_competencia_nocontinuas_v1_lag2.py
uv run python fe/build_rankings_v1.py
uv run python fe/build_rankings_v1_lag1.py
uv run python fe/build_rankings_v1_lag2.py
uv run python fe/build_rankings_v1_delta1.py
uv run python fe/build_rankings_v1_delta2_v2.py
```

## Comandos pipeline

**Entrega (acortada):** ver [`ENTREGA_FINAL.md`](ENTREGA_FINAL.md) — `1_` BO, luego `6_` con `COMPE1_AGOSTO_RANKS=1` y `COMPE1_N_SEMILLAS_PRIMOS=3`.

**Protocolo completo (holdout top-20 + `ganador.yml` + `6_`):**

```bash
cd juara
uv run python compe1/04py/00/1_bayesiana_lightgbm.py
uv run python compe1/04py/00/2_produccion_lightgbm.py
uv run python compe1/04py/00/4_produccion_top20_bo_semillas.py
uv run python compe1/04py/00/5_analisis_top20_bo_semillas.py
uv run python compe1/04py/00/6_prediccion_agosto_top20_semillas.py
```

**Sin holdout top-20** (top-N BO directo a agosto, 10 semillas):

```bash
COMPE1_BO_TOP_N=1 uv run python compe1/04py/00/7_prediccion_agosto_bo_topN_semillas.py
```

Variables útiles:

- `COMPE1_BO_ITER` — iteraciones Optuna (default `150`).
- `COMPE1_BO_EXPORT_AT_LAST_COMPLETE=1` — no corre trials nuevos; exporta `BO_log.txt` y `PARAM.yml` con **todos** los trials COMPLETE presentes en `optuna.db` al ejecutar (corte en el último completado, sin fijar un número a mano).

## VM spot y GCS (`--vm`)

Con `--vm`, los scripts bajan parquets desde `gs://<bucket>/data/` y sincronizan resultados con `gs://<bucket>/compe1/04py-00/resultados/`. Sin `--vm`, solo disco local (las variables de bucket no activan GCS por sí solas).

```bash
export JUARA_GCS_BUCKET=juarajuangabriel_buckito2026
cd juara
uv run python compe1/04py/00/1_bayesiana_lightgbm.py --vm
```

| Variable | Default | Uso |
|----------|---------|-----|
| `JUARA_GCS_BUCKET` / `COMPE1_GCS_BUCKET` | — | Bucket (obligatorio con `--vm`) |
| `JUARA_GCS_PREFIX` | `data` | Parquets de entrada |
| `COMPE1_GCS_PREFIX` | `compe1/04py-00/resultados` | Salidas del experimento |
| `COMPE1_GCS_SYNC_EVERY_TRIALS` | `1` | Script 1: rsync de `bo/` cada N trials Optuna |

Subidas incrementales: script 1 (cada trial según `COMPE1_GCS_SYNC_EVERY_TRIALS`), script 4 (cada `rank_##` y metadatos de estudio). Al terminar cada script se vuelve a sincronizar el directorio correspondiente.

Requisitos en la VM: `gcloud` en PATH; scope de almacenamiento con escritura e IAM de escritura sobre el bucket (ver [`juara/gce.md`](../../gce.md)).

## Paridad

| Componente | Paridad |
|------------|---------|
| Split temporal vs R | Mismo criterio por `foto_mes` (protocolo `*py`) |
| Objetivo BO | `temporal_cv_average_precision_mar_may` (PR-AUC; 2 folds mar→abr, mar–abr→may) |
| Features | 8 capas (mismo join que `01py` / `01_full_fe`) |
| BO | No bit-a-bit (Optuna ≠ mlrMBO) |
| `3_escalar` | No incluido |
| Agosto (`6_`) | Usa `rank_ganador` de `ganador.yml` (paso `5_`); fallback rank `3` |

Checkpoint BO: `04py-00/resultados/bo/optuna.db`.

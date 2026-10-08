# 01py

Port Python del protocolo [`00py`](../00py/README.md) con **FE completo** (8 capas parquet, equivalente a [`01_full_fe`](../archivo/01_full_fe/README.md)): split temporal mar–may / test junio, BO con **Optuna**, exp **1991**. Sin script `3_escalar`.

**Capas parquet** (orden de join; ver `layers_paths("01py")` en [`common/layers.py`](../common/layers.py)):

- `competencia_01_nocontinuas_v1.parquet`
- `competencia_01_nocontinuas_v1_lag1.parquet`
- `competencia_01_nocontinuas_v1_lag2.parquet`
- `rankings_v1.parquet`
- `rankings_v1_lag1.parquet`
- `rankings_v1_lag2.parquet`
- `rankings_v1_delta1.parquet`
- `rankings_v1_delta2.parquet`

**Resultados:** `juara/compe1/01py/00/resultados/` (`HT1991/`, `exp1991/`, `exp1991_top20/`, `exp1991_agosto/`, `estudio/top20_bo_semillas/`).

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
uv run python fe/build_rankings_v1_delta2.py
```

## Comandos pipeline

```bash
cd juara
uv run python compe1/01py/00/1_bayesiana_lightgbm.py
uv run python compe1/01py/00/2_produccion_lightgbm.py
uv run python compe1/01py/00/4_produccion_top20_bo_semillas.py
uv run python compe1/01py/00/5_analisis_top20_bo_semillas.py
uv run python compe1/01py/00/6_prediccion_agosto_top20_semillas.py
```

Variables útiles:

- `COMPE1_BO_ITER` — iteraciones Optuna (default `150`).

## VM spot y copia a GCS

Si `COMPE1_GCS_BUCKET` está definido, cada script hace `gcloud storage rsync -r` de sus salidas bajo `00/resultados/` al bucket (sin la variable, no se llama a `gcloud`).

Destino por defecto: `gs://<bucket>/compe1/01py/00/resultados/<subcarpeta>/`.

```bash
export COMPE1_GCS_BUCKET=juarajuangabriel_buckito2026
cd juara
uv run python compe1/01py/00/1_bayesiana_lightgbm.py
```

| Variable | Default | Uso |
|----------|---------|-----|
| `COMPE1_GCS_BUCKET` | — | Activa la subida (obligatoria en VM) |
| `COMPE1_GCS_PREFIX` | `compe1/01py/00/resultados` | Prefijo bajo el bucket |
| `COMPE1_GCS_SYNC_EVERY_TRIALS` | `1` | Script 1: rsync de `HT1991/` cada N trials Optuna |

Subidas incrementales: script 1 (cada trial según `COMPE1_GCS_SYNC_EVERY_TRIALS`), script 4 (cada `rank_##` y metadatos de estudio). Al terminar cada script se vuelve a sincronizar el directorio correspondiente.

Requisitos en la VM: `gcloud` en PATH; scope de almacenamiento con escritura e IAM de escritura sobre el bucket (ver [`juara/gce.md`](../../gce.md)).

## Paridad

| Componente | Paridad |
|------------|---------|
| Split temporal vs R | Mismo criterio por `foto_mes` |
| Objetivo BO | `temporal_cv_auc_mar_may` (2 folds mar→abr, mar–abr→may) |
| Features | 8 capas (mismo join que `01_full_fe`) |
| BO | No bit-a-bit (Optuna ≠ mlrMBO) |
| `3_escalar` | No incluido |

Checkpoint BO: `01py/00/resultados/HT1991/optuna.db`.

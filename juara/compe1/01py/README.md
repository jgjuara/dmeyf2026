# 01py

Port Python del protocolo [`00py`](../00py/README.md) con **FE completo** (8 capas parquet, equivalente a [`01_full_fe`](../archivo/01_full_fe/README.md)): split temporal mar–may / test junio, BO con **Optuna**, exp **1991**. Sin script `3_escalar`.

**Capas parquet** (orden de join; ver `layers_paths("01py")` en [`common/layers.py`](../common/layers.py)):

- `competencia_01_nocontinuas.parquet`
- `competencia_01_nocontinuas_lag1.parquet`
- `competencia_01_nocontinuas_lag2.parquet`
- `rankings.parquet`
- `rankings_lag1.parquet`
- `rankings_lag2.parquet`
- `rankings_delta1.parquet`
- `rankings_delta2.parquet`

**Resultados:** `juara/compe1/01py/00/resultados/` (`HT1991/`, `exp1991/`, `exp1991_top20/`, `exp1991_agosto/`, `estudio/top20_bo_semillas/`).

**Utilidades:** [`common/layers.py`](../common/layers.py), [`common/data.py`](../common/data.py), [`common/lgb_train.py`](../common/lgb_train.py), [`common/bo_space.py`](../common/bo_space.py).

## Prerequisitos FE

Desde `juara/`, con `competencia_01.parquet` en `juara/data/`:

```bash
cd juara
uv run python fe/build_competencia_nocontinuas.py
uv run python fe/build_competencia_nocontinuas_lag1.py
uv run python fe/build_competencia_nocontinuas_lag2.py
uv run python fe/build_rankings.py
uv run python fe/build_rankings_lag1.py
uv run python fe/build_rankings_lag2.py
uv run python fe/build_rankings_delta1.py
uv run python fe/build_rankings_delta2.py
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

## Paridad

| Componente | Paridad |
|------------|---------|
| Split temporal vs R | Mismo criterio por `foto_mes` |
| Objetivo BO | `temporal_cv_auc_mar_may` (2 folds mar→abr, mar–abr→may) |
| Features | 8 capas (mismo join que `01_full_fe`) |
| BO | No bit-a-bit (Optuna ≠ mlrMBO) |
| `3_escalar` | No incluido |

Checkpoint BO: `01py/00/resultados/HT1991/optuna.db`.

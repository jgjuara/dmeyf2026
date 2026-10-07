# 00py

Port Python del protocolo [`00`](../00/README.md) (exp **1990**): capa `competencia_01.parquet`, split temporal mar–may / test junio, BO con **Optuna** en lugar de mlrMBO. Sin script `3_escalar` (no aplica a este experimento).

**Capas:** `competencia_01.parquet`.

**Resultados:** `juara/compe1/00py/00/resultados/` (`HT1990/`, `exp1990/`, `exp1990_top20/`, `exp1990_agosto/`, `estudio/top20_bo_semillas/`).

**Utilidades:** [`common/layers.py`](../common/layers.py), [`common/data.py`](../common/data.py), [`common/lgb_train.py`](../common/lgb_train.py), [`common/bo_space.py`](../common/bo_space.py).

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

## Paridad

| Componente | Paridad |
|------------|---------|
| Split temporal vs R | Mismo criterio por `foto_mes` |
| Objetivo BO | `temporal_cv_auc_mar_may` (2 folds mar→abr, mar–abr→may) |
| BO | No bit-a-bit (Optuna ≠ mlrMBO) |
| `3_escalar` | No incluido |

Checkpoint BO: `00/resultados/HT1990/optuna.db`.

# 02_rank_nocount_py

Port Python del protocolo [`02_rank_nocont`](../02_rank_nocont/README.md) (exp **2102**): mismas capas parquet, mismos artefactos bajo `00/resultados/`. Partición y undersampling en [`common/partition.py`](../common/partition.py) (solo Python/numpy). BO con **Optuna** (`HT2102/optuna.db`) en lugar de mlrMBO.

**Capas:** `competencia_01_nocontinuas.parquet`, `rankings.parquet`.

**Utilidades:** [`common/layers.py`](../common/layers.py), [`common/data.py`](../common/data.py), [`common/partition.py`](../common/partition.py), [`common/lgb_train.py`](../common/lgb_train.py).

## Comandos

Desde `juara/` (proyecto `uv`):

```bash
cd juara
uv run python compe1/02_rank_nocount_py/00/1_bayesiana_lightgbm.py
uv run python compe1/02_rank_nocount_py/00/2_produccion_lightgbm.py
uv run python compe1/02_rank_nocount_py/00/4_produccion_top20_bo_semillas.py
uv run python compe1/02_rank_nocount_py/00/5_analisis_top20_bo_semillas.py
uv run python compe1/02_rank_nocount_py/00/3_escalar_ganancia_mes.py
```

Variables útiles:

- `COMPE1_BO_ITER` — iteraciones Optuna (default `500`).

## Verificación

```bash
uv run python compe1/02_rank_nocount_py/00/verify_split_repro.py
```

Comprueba reproducibilidad del split (semilla `427417`). Tras cambiar `partition.py`, borrar `00/cache/split_*.tsv` para regenerar caché.

**Paridad esperada**

| Componente | Paridad |
|------------|---------|
| Folds / undersampling vs R | No garantizado (RNG Python); mismo protocolo |
| `lgb.cv` / `lgb.train` | Misma API LightGBM; tolerancia numérica en prob |
| BO | No bit-a-bit (Optuna ≠ mlrMBO); opcional validar producción con `PARAM.yml` de R |

**Checkpoint BO:** `00/resultados/HT2102/optuna.db` (no `bayesiana.RDATA`).

Salidas: mismas rutas que en [`02_rank_nocont/README.md`](../02_rank_nocont/README.md) pero bajo `juara/compe1/02_rank_nocount_py/00/resultados/`.

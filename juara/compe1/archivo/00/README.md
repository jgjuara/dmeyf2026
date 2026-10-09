# 00

**Alcance:** columnas de [`juara/data/competencia_01_v1.parquet`](../../data/competencia_01_v1.parquet) sin capas de feature engineering (sin nocontinuas derivadas, rankings, lags ni deltas).

**Capas parquet:**

- `competencia_01_v1.parquet`

Generación: `Rscript juara/generar_clase_ternaria_parquet.R` (desde `competencia_01_crudo.csv`).

**RESULTADOS_DIR:** `juara/compe1/00/00/resultados/` (`HT1990/`, `exp1990/`, `exp1990_top20/`, `exp1990_agosto/`, `estudio/top20_bo_semillas/`).

Plantilla del protocolo común: [`../README.md`](../README.md#estructura-del-modelo-experimental).

## Protocolo (experimento 1990)

| Elemento | Valor |
|----------|--------|
| Ventana lectura | `foto_mes` 202103–202106 (mar–jun 2021) |
| Split | **Temporal:** train mar–may (`202103`–`202105`) / test **junio completo** (`202106`) |
| Target binario | `clase01 = 1` si `BAJA+1` o `BAJA+2`, else `0` |
| BO (`1_…`) | 3 HP en mlrMBO (`num_iterations`, `num_leaves`, `min_sum_hessian_in_leaf`; `min_data_in_leaf` fijo; default `COMPE1_BO_ITER=200`); **sin undersampling**; objetivo = media AUC de **2 folds temporales** en train: fit mar → AUC abr; fit mar–abr → AUC may (`compe1_lgb_temporal_cv_auc_mar_may`) |
| Producción (`2_…`) | Train **mar–may** con mejor HP; evaluación en **junio** |
| Top-20 × semillas (`4_…`) | 20 mejores filas de `BO_log.txt`; 10 semillas-primo; test junio; prob media → cortes oficiales |
| Re-ranking (`5_…`) | Wilcoxon sobre ganancia en junio por semilla |
| Agosto (`6_…`) | Train mar–jun completo; predict `202108` |
| Ganancia test | Directa sobre junio (`cortes_ganancia*.txt`); sin escalado a mes completo |

Código numérico de carpetas: **1990**. El protocolo 70/30 de [`03_rank_nocont_lag1_delta1`](../03_rank_nocont_lag1_delta1/README.md) no aplica aquí; `3_escalar_ganancia_mes.R` queda obsoleto para este experimento.

## Pipeline de scripts (orden lógico)

```text
1_bayesiana          → HT1990/
2_produccion         → exp1990/
4_top20_semillas     → exp1990_top20/rank_XX/
5_analisis_top20     → estudio/top20_bo_semillas/
6_agosto_semillas    → exp1990_agosto/
```

## Comandos

Desde la raíz del repo:

```bash
Rscript juara/compe1/00/00/1_bayesiana_lightgbm.R
Rscript juara/compe1/00/00/2_produccion_lightgbm.R
Rscript juara/compe1/00/00/4_produccion_top20_bo_semillas.R
Rscript juara/compe1/00/00/5_analisis_top20_bo_semillas.R
Rscript juara/compe1/00/00/6_prediccion_agosto_top20_semillas.R
```

Utilidades compartidas: [`common/compe1_data.R`](../common/compe1_data.R), [`common/compe1_layers.R`](../common/compe1_layers.R).

Estructura detallada de cada script en [`00/README.md`](00/README.md).

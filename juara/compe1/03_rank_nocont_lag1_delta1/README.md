# 03_rank_nocont_lag1_delta1

**Alcance:** nocontinuas y rankings del mes, más lag1 (nocontinuas + `pct_*` de `rankings_lag1.parquet`) y delta1 (`rankings_delta1.parquet`); sin lag2, delta2 ni capas asociadas.

**Capas parquet:**

- `competencia_01_nocontinuas.parquet`
- `rankings.parquet`
- `competencia_01_nocontinuas_lag1.parquet`
- `rankings_lag1.parquet`
- `rankings_delta1.parquet`

Generación: pasos 2, 3, 5, 6 y 8 de [`../README.md`](../README.md) (`build_competencia_nocontinuas.py`, `build_competencia_nocontinuas_lag1.py`, `build_rankings.py`, `build_rankings_lag1.py`, `build_rankings_delta1.py`).

**RESULTADOS_DIR:** `juara/compe1/03_rank_nocont_lag1_delta1/00/resultados/` (`HT2103/`, `exp2103/`, `exp2103_top20/`, `exp2103_agosto/`, `estudio/top20_bo_semillas/`).

Plantilla del protocolo común: [`../README.md`](../README.md#estructura-del-modelo-experimental).

## Protocolo (experimento 2103)

| Elemento | Valor |
|----------|--------|
| Ventana | `foto_mes` 202103–202106 (mar–jun 2021) |
| Split | 70 % desarrollo (BO + train) / 30 % test producción, estratificado por `clase_ternaria` y `foto_mes`, semilla `427417` |
| Target binario | `clase01 = 1` si `BAJA+1` o `BAJA+2`, else `0` |
| BO (`1_…`) | 4 HP en mlrMBO (default `COMPE1_BO_ITER=500`); **CV 2 folds** en el 70 % vía `lgb.cv` (`cv_auc`); undersampling **0,1** solo **CONTINUA** en dev (BAJA+1/2 siempre); el 30 % no se usa en BO |
| Producción (`2_…`) | Train con **todo** el 70 % (sin undersampling); `min_data_in_leaf` reescalado `/ undersampling`; evaluación en el 30 % reservado (mejor HP único de la BO) |
| Top-20 × semillas (`4_…`) | 20 mejores filas de `BO_log.txt`; cada HP con **10 semillas-primo** (`compe1_semillas_primos`); test en holdout 30 %; **prob media** de las 10 semillas → `curva_ganancia_media` y `cortes_ganancia_media` |
| Re-ranking (`5_…`) | Wilcoxon emparejado por semilla sobre ganancia holdout en cada corte; Holm (19 contrastes); ranking por `max(mean(ganancia))` en holdout (`ranking_por_max_holdout.tsv`) |
| Ganancia | `1072500` si `BAJA+2`, `-27500` en caso contrario (top-N por `prob`) |
| Cortes | `seq(4000, 19000, by = 500)` |
| Métrica comparable | Ganancia **escalada a mes completo** y **promedio** mar–jun (`3_…`, opcional); inferencia top-20 usa holdout crudo por semilla |

## Pipeline de scripts (orden lógico)

```text
1_bayesiana          → HT2103/     (CV 2-fold en 70% undersampled; 30% intacto)
2_produccion         → exp2103/    (mejor HP; train 70% full; test 30%)
3_escalar_ganancia   → exp2103/    (opcional; métrica mensual del paso 2)
4_top20_semillas     → exp2103_top20/rank_XX/  (20 HP × 10 primos; prob_media en test)
5_analisis_top20     → estudio/top20_bo_semillas/  (ranking + Wilcoxon; sin train)
6_agosto_semillas    → exp2103_agosto/  (HP top-20; train mar-jun completo; predict 202108; prob media ordenada)
```

**Tres usos del 70 %**

| Uso | Undersampling | CV / train |
|-----|---------------|------------|
| BO (`1_`) | Sí (`0.1` CONTINUA) | `lgb.cv` 2 folds sobre filas `training==1` |
| Producción (`2_`, `4_`) | No | `lgb.train` con todas las filas `fold==1` |

**Test (30 %):** una sola partición fija. En `4_`, cada primo genera probabilidades en ese mismo holdout; la curva publicada del rank promedia esas 10 probabilidades **antes** de ordenar por `prob` y calcular ganancia.

**Semillas:** BO y partición usan `semilla_primigenia` (`427417`). El script `2_` deja la semilla LightGBM en `param_fijos$seed`. El script `4_` fija **10 primos** derivados de `compe1_semillas_primos` (misma lista para los 20 ranks, para comparabilidad Wilcoxon).

## Comandos

Desde la raíz del repo:

Tras cambiar el objetivo de BO (holdout → CV en dev), borrar `00/resultados/HT2103/bayesiana.RDATA` antes de re-correr la BO.

```bash
Rscript juara/compe1/03_rank_nocont_lag1_delta1/00/1_bayesiana_lightgbm.R
Rscript juara/compe1/03_rank_nocont_lag1_delta1/00/2_produccion_lightgbm.R
Rscript juara/compe1/03_rank_nocont_lag1_delta1/00/4_produccion_top20_bo_semillas.R
Rscript juara/compe1/03_rank_nocont_lag1_delta1/00/5_analisis_top20_bo_semillas.R
# scoring agosto (train mar-jun completo; RANKS_BO en script, default rank 03)
Rscript juara/compe1/03_rank_nocont_lag1_delta1/00/6_prediccion_agosto_top20_semillas.R
# opcional: escalado mar–jun del mejor HP único
Rscript juara/compe1/03_rank_nocont_lag1_delta1/00/3_escalar_ganancia_mes.R
```

**Salidas principales**

- `00/resultados/HT2103/` — `bayesiana.RDATA`, `BO_log.txt`, `PARAM.yml`
- `00/resultados/exp2103/` — `modelo.txt`, `prediccion.txt` (solo test 30 %), `cortes_ganancia.txt` (holdout sin escalar)
- `00/resultados/exp2103_top20/rank_XX/` — por rank BO: 10× `modelo_<primo>.txt`, `prediccion_<primo>.txt`, `cortes_ganancia_<primo>.txt`; agregado `prediccion_media.txt`, `curva_ganancia_media.pdf`, `cortes_ganancia_media.txt`
- `00/resultados/estudio/top20_bo_semillas/` — `top20_hiperparametros.tsv`, `semillas_train.txt`, tablas Wilcoxon, `ranking_por_max_holdout.tsv`, `ganador.yml`, gráficos PDF
- `00/resultados/exp2103_agosto/` — `prediccion_agosto_media_ordenada.tsv`, `prediccion_agosto_media.tsv`, `prediccion_agosto_por_rank_semilla.tsv`, `meta.yml`

Utilidades compartidas: [`common/compe1_data.R`](../common/compe1_data.R), [`common/compe1_layers.R`](../common/compe1_layers.R).

Estructura detallada de cada script en [`00/README.md`](00/README.md).

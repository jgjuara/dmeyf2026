# 4.06–4.08 GBDT LightGBM (`z470_GBDT_LightGBM`)

Extracción de `ensembles/z470_GBDT_LightGBM.ipynb` a partir de **§4.07 LightGBM, una corrida** y **§4.08 optimización de hiperparámetros**. Quedan fuera Colab, descarga de `competencia_01_crudo.csv`, generación de `clase_ternaria` y material introductorio (papers, videos).

**Premisa:** existe `juara/data/competencia_01.csv.gz` con `clase_ternaria` (salida de `generar_clase_ternaria.R`).

Scripts en `00/`:

| Script | Contenido |
|---|---|
| `1_lightgbm_corrida.R` | Entrenamiento con hiperparámetros fijos (post-BO), scoring en `202106`, corte `prob > 1/40`, ganancia public/private. |
| `2_bayesiana_lightgbm.R` | BO con mlrMBO maximizando AUC en `lgb.cv` (5 folds); undersampling 1.0 (todos los registros). |

Artefactos:

| Carpeta | Archivos |
|---|---|
| `00/resultados/KA4070/` | `impo.txt`, `modelo.txt`, `prediccion.txt`, `KA4070.csv` |
| `00/resultados/HT4080/` | `bayesiana.RDATA`, `BO_log.txt` |

## §4.07 — Una corrida

- `PARAM$experimento <- 4070`, entrenamiento en `foto_mes == 202104`, aplicación en `202106`.
- Clase binaria: solo `BAJA+2` es positiva (`clase01 = 1`).
- Hiperparámetros de ejemplo (del notebook, “surgidos de una BO”): `num_iterations = 1000`, `learning_rate = 0.027`, `feature_fraction = 0.8`, `min_data_in_leaf = 76`, `num_leaves = 8`, `max_bin = 31`.
- Envío Kaggle: clientes con `prob > 1/40`.
- Ganancia en futuro: partición estratificada 30/70 (`semilla_kaggle = 314159`) con la misma fórmula de campaña (+1 072 500 / −27 500).

Tras §4.08, copiar los mejores hiperparámetros de `BO_log.txt` (fila 1) en `PARAM$lgb` de `1_lightgbm_corrida.R` y volver a ejecutar la corrida.

## §4.08 — Bayesian Optimization

- `PARAM$experimento <- 4080`, solo mes `202104`.
- `PARAM$trainingstrategy$undersampling <- 1.0` (sin reducir `CONTINUA`).
- Clase binaria: únicamente `BAJA+2` es 1 (igual criterio que en §4.07).
- Tunables: `learning_rate`, `feature_fraction`, `num_leaves`, `min_data_in_leaf`; `num_iterations` efectivo vía early stopping (`early_stopping_rounds = 200`, tope 2048).
- Checkpoint cada 600 s en `bayesiana.RDATA`; retoma con `mboContinue` si existe.
- Salida tabular en `BO_log.txt`; imprime `PARAM$out$lgbm$mejores_hiperparametros`.

| Paquete | Uso |
|---|---|
| `data.table` | Datos y log. |
| `lightgbm` | `lgb.Dataset`, `lgb.cv`, `lgb.train`. |
| `mlrMBO` | `mbo`, `mboContinue`. |
| `DiceKriging` | Surrogate `regr.km`. |

## Orden de ejecución

```powershell
Rscript juara/jueves/generar_clase_ternaria.R
Rscript juara/jueves/z470/00/2_bayesiana_lightgbm.R
Rscript juara/jueves/z470/00/1_lightgbm_corrida.R
```

La BO puede tardar (30 iteraciones por defecto). Flujo pedagógico del notebook: primero §4.08, luego actualizar `PARAM$lgb` en §4.07 y correr `1_lightgbm_corrida.R`.

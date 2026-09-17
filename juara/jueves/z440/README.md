# Random Forest con ranger (`z440_RandomForest`)

Explicación de `ensembles/z440_RandomForest.ipynb` a partir de **§4.04 Random Forest, una corrida** y **§4.05 optimización de hiperparámetros**. Quedan fuera Colab, descarga de `competencia_01_crudo.csv` y generación de `clase_ternaria`.

**Premisa:** existe `juara/data/competencia_01.csv.gz` con `clase_ternaria` (salida de `generar_clase_ternaria.R`).

Scripts en `00/`:

| Script | Contenido |
|---|---|
| `1_random_forest_corrida.R` | Entrenamiento ranger sobre `train`, scoring en `future`, ganancia con umbral `prob > 1/40`. |
| `2_bayesiana_ranger.R` | BO (mlrMBO) maximizando ganancia en CV 5-fold sobre clase binaria POS/NEG. |

Artefactos:

| Ubicación | Archivos |
|---|---|
| Consola (`1_...`) | TOTAL, Public, Private (no se persisten en disco en el notebook). |
| `00/resultados/HT450/` | `HT450.RDATA`, `HT450.txt`, `HT450_mejor.txt` |

## Objetivo

Implementar **Random Forest** con la librería **ranger** (paralelo en CPU): una corrida pedagógica con hiperparámetros fijos y, opcionalmente, búsqueda bayesiana de `num.trees`, `max.depth`, `min.node.size` y `mtry`. El notebook advierte que la BO puede demandar muchas horas; el ejemplo usa solo 5 iteraciones.

## 1. Parámetros — corrida simple (`1_random_forest_corrida.R`)

```r
PARAM$experimento <- 440
PARAM$semilla_primigenia <- 290497   # cambiar por la semilla propia
PARAM$train <- c(202104)
PARAM$future <- c(202106)
PARAM$ranger$num.trees <- 300
PARAM$ranger$mtry <- 13
PARAM$ranger$min.node.size <- 50
PARAM$ranger$max.depth <- 10
PARAM$semilla_kaggle <- 314159
```

- **Imputación:** `na.roughfix` (paquete `randomForest`) porque ranger no acepta NA.
- **Data drifting:** `Master_Finiciomora` y `Visa_Finiciomora` NA → `-999`.
- **Métrica de campaña:** probabilidad de `BAJA+2`; envío si `prob > 1/40`. Ganancia vía `particionar` 3/7 (public/private) sobre el futuro.

## 2. Bayesian Optimization (`2_bayesiana_ranger.R`)

```r
PARAM$experimento <- 450
PARAM$hyperparametertuning$iteraciones <- 5
PARAM$hyperparametertuning$xval_folds <- 5
```

| Paquete | Uso |
|---|---|
| `data.table` | Datos y log tabular. |
| `ranger` | Modelo en cada fold. |
| `randomForest` | `na.roughfix`. |
| `R.utils` | Dependencia de imputación / utilidades. |
| `primes` | Semillas auxiliares para CV. |
| `parallel` | `mcmapply` con `mc.cores = 1` (ranger ya paraleliza). |
| `mlrMBO`, `DiceKriging` | BO y surrogate `regr.km`. |

- Clase binaria: POS = `BAJA+2`, NEG = resto; objetivo = ganancia normalizada en CV.
- Checkpoint cada 600 s en `HT450.RDATA`; si existe, `mboContinue`.
- Tras la corrida: ordenar `HT450.txt` por `ganancia` y copiar los mejores hiperparámetros a `PARAM$ranger` en `1_random_forest_corrida.R`.

## Orden de ejecución

```powershell
Rscript juara/jueves/generar_clase_ternaria.R
Rscript juara/jueves/z440/00/1_random_forest_corrida.R
Rscript juara/jueves/z440/00/2_bayesiana_ranger.R
```

La corrida simple tarda del orden de ~8 minutos en el entorno del notebook; la BO con pocas iteraciones sigue siendo costosa si se aumenta `iteraciones`.

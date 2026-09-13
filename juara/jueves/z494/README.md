# Tarea para el Hogar 04 — LightGBM y Bayesian Optimization (`z494_TareaHogar_04`)

Explicación de `ensembles/z494_TareaHogar_04.ipynb` a partir de **§2.2 Optimización hiperparámetros** y **§2.3 Producción**. Quedan fuera Colab, descarga de `competencia_01_crudo.csv` y generación de `clase_ternaria`.

**Premisa:** existe `juara/data/competencia_01.csv.gz` con `clase_ternaria` (salida de `generar_clase_ternaria.R`).

Scripts en `00/`:

| Script | Contenido |
|---|---|
| `1_bayesiana_lightgbm.R` | Parámetros, undersampling, `lgb.cv`, mlrMBO (30 iteraciones por defecto). |
| `2_produccion_lightgbm.R` | Modelo final, scoring, curva de ganancia, cortes public/private. |

Artefactos:

| Carpeta | Archivos |
|---|---|
| `00/resultados/HT4940/` | `bayesiana.RDATA`, `BO_log.txt`, `PARAM.yml` |
| `00/resultados/exp4940/` | `modelo.txt`, `impo.txt`, `prediccion.txt`, `curva_ganancia.pdf`, `cortes_ganancia.txt`, `PARAM.yml` |

## Objetivo de la tarea

Optimizar hiperparámetros de LightGBM con **Bayesian Optimization** (mlrMBO + DiceKriging) maximizando AUC en cross-validation, luego entrenar el modelo final con los mejores valores y evaluar ganancia de campaña en `foto_mes == 202106`.

La tarea conceptual pide investigar qué hiperparámetros conviene incluir en la BO y rangos razonables; el notebook de partida optimiza cinco: `num_iterations`, `learning_rate`, `feature_fraction`, `num_leaves`, `min_data_in_leaf`.

## 1. Parámetros globales

```r
PARAM$experimento <- 4940
PARAM$semilla_primigenia <- 290497   # cambiar por la semilla propia
PARAM$train <- c(202104)             # mes para BO (con undersampling)
PARAM$train_final <- c(202104)       # mes para modelo final (sin undersampling)
PARAM$future <- c(202106)
PARAM$semilla_kaggle <- 314159
PARAM$cortes <- seq(4000, 19000, by = 500)
PARAM$trainingstrategy$undersampling <- 0.1
```

- **Undersampling 0.1:** en el entrenamiento para BO se usa el 10% de `CONTINUA` y todos los `BAJA+1` / `BAJA+2`.
- **Clase binaria:** `clase01 = 1` para bajas, `0` para `CONTINUA`; objetivo LightGBM `binary` con métrica `auc`.

## 2. LightGBM — fijos vs BO

Muchos hiperparámetros quedan fijos en `PARAM$lgbm$param_fijos` (boosting `gbdt`, `max_bin = 31`, regularización en cero, etc.). Los valores iniciales de los cinco tunables son los del notebook (`num_iterations = 1200`, `learning_rate = 0.02`, …).

La BO usa `lgb.cv` con `nfold = 5` y `stratified = TRUE`. Cada evaluación devuelve `best_score` (AUC).

## 3. Bayesian Optimization (`1_bayesiana_lightgbm.R`)

| Paquete | Uso |
|---|---|
| `data.table` | Datos y log tabular. |
| `lightgbm` | `lgb.Dataset`, `lgb.cv`. |
| `mlrMBO` | `mbo`, `mboContinue`, control de infill. |
| `DiceKriging` | Surrogate `regr.km` (dependencia de mlrMBO). |
| `yaml` | Persistir `PARAM` tras la BO. |

- Checkpoint cada 600 s en `bayesiana.RDATA`; si existe, `mboContinue` retoma.
- Tras la corrida: `BO_log.txt` (tabla ordenada por AUC) y mejores hiperparámetros en `PARAM$out$lgbm`.

**Tiempo:** 30 iteraciones es un valor mínimo del notebook; en producción de la tarea conviene 50–100.

## 4. Producción (`2_produccion_lightgbm.R`)

1. Lee `HT4940/PARAM.yml` (incluye `campos_buenos` y mejores hiperparámetros).
2. Entrena sobre **todo** `train_final` **sin** undersampling.
3. **Normalización sutil:** `min_data_in_leaf` del modelo final se divide por el factor de undersampling usado en BO (clase 05).
4. Scoring en `future`; `prediccion.txt` con probabilidades.
5. Curva de ganancia acumulada (top 30 000 por prob) → `curva_ganancia.pdf`.
6. Para cada corte en `PARAM$cortes`, marca los top-N envíos y calcula ganancia total, public (30%) y private (70%) vía `particionar` 3/7 sobre el futuro.

Funciones auxiliares: `particionar`, `realidad_inicializar`, `realidad_evaluar` (misma lógica de ganancia que en competencias: +1 072 500 por `BAJA+2` contactado, −27 500 en caso contrario).

## Orden de ejecución

```powershell
Rscript juara/jueves/generar_clase_ternaria.R
Rscript juara/jueves/z494/00/1_bayesiana_lightgbm.R
Rscript juara/jueves/z494/00/2_produccion_lightgbm.R
```

La BO puede tardar horas. Ajustar `PARAM$hyperparametertuning$iteraciones` y el espacio en `PARAM$hypeparametertuning$hs` antes de corridas largas.

Resultados de la cohorte: hoja **TareaHogar04** en la planilla colaborativa del curso.

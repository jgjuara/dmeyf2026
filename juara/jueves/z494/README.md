# Tarea para el Hogar 04 — LightGBM y Bayesian Optimization (`z494_TareaHogar_04`)

Explicación de `ensembles/z494_TareaHogar_04.ipynb` a partir de **§2.2 Optimización hiperparámetros** y **§2.3 Producción**. Quedan fuera Colab, descarga de `competencia_01_crudo.csv` y generación de `clase_ternaria`.

**Premisa:** existe `juara/data/competencia_01.csv.gz` con `clase_ternaria` (salida de `generar_clase_ternaria.R`).

## Variantes `00`–`03`

Cuatro carpetas paralelas con scripts y `resultados/` propios. Comparten `semilla_primigenia = 427417` y `semilla_kaggle = 314159` salvo que se indique lo contrario. La diferencia operativa relevante está en la BO y en cuántos conjuntos de hiperparámetros y entrenamientos finales se ejecutan.

### Semillas (todas las variantes)

| Semilla | Rol |
|---|---|
| `427417` (`semilla_primigenia`) | Undersampling de `CONTINUA` en la BO (`set.seed(..., "L'Ecuyer-CMRG")`); `seed` de LightGBM en cada evaluación `lgb.cv` de la BO y en `2_produccion` (vía `param_fijos`); `set.seed` para elegir los 10 primos de entrenamiento en `2_1` y `6`. |
| `314159` (`semilla_kaggle`) | Solo la partición public/private (3/7) al evaluar cortes de ganancia; **no** fija el entrenamiento del modelo. |

En `2_1_produccion_lightgbm_semillas.R` y `6_produccion_top10_bo_semillas.R`, cada corrida de `lgb.train` usa como `seed` un primo distinto (10 en total), muestreado una vez con `set.seed(427417)` sobre primos en `[10000, 1e6]`. Con la configuración actual del repo, ese vector es siempre:

`405157, 152267, 166297, 141871, 862307, 542981, 188179, 817111, 491299, 531911`

(registrado en `resultados/estudio/top10_bo_semillas/semillas_train.txt` tras correr `6`, o implícito al correr `2_1`).

### Espacio de búsqueda y corrida de la BO

- **`00`:**
  - Hiperparámetros tunables: **5**
  - Rangos (`makeParamSet` en `1_bayesiana_lightgbm.R`):
    - `num_iterations`: 8–2048 (entero)
    - `learning_rate`: 0.01–0.3
    - `feature_fraction`: 0.1–1.0
    - `num_leaves`: 8–2048 (entero)
    - `min_data_in_leaf`: 1–8000 (entero)
  - Iteraciones mlrMBO (infill): **30**
  - Folds `lgb.cv` en la objetivo: **5** (estratificado)
  - Semilla(s) de la BO: **`427417`** (`semilla_primigenia`; undersampling + `seed` en cada evaluación)

- **`01`:**
  - Hiperparámetros tunables: **5**
  - Rangos: **iguales a `00`**
  - Iteraciones mlrMBO: **300**
  - Folds `lgb.cv`: **5**
  - Semilla(s) de la BO: **`427417`**

- **`02`:**
  - Hiperparámetros tunables: **6**
  - Rangos:
    - `num_iterations`: 8–2048 (entero)
    - `learning_rate`: 0.01–0.3
    - `feature_fraction`: 0.1–1.0
    - `num_leaves`: 8–2048 (entero)
    - `min_data_in_leaf`: 1–8000 (entero)
    - `min_sum_hessian_in_leaf`: el surrogate explora **log₁₀** en `[-5, 1]` (`trafo`: `10^x` → valor físico **1e-5–10**)
  - Iteraciones mlrMBO: **300**
  - Folds `lgb.cv`: **5**
  - Semilla(s) de la BO: **`427417`**

- **`03`:**
  - Hiperparámetros tunables: **6**
  - Rangos: **iguales a `02`**
  - Iteraciones mlrMBO: **300**
  - Folds `lgb.cv`: **3** (único cambio respecto de `02`; menos costo por evaluación, más varianza del AUC en CV)
  - Semilla(s) de la BO: **`427417`**

`00` es la línea base del notebook (BO corta). `01` extiende el mismo espacio de cinco parámetros a 300 iteraciones y añade scripts de producción y estudio.

### Tiempo de BO: `02` (5 folds) vs `03` (3 folds)

Comparación empírica entre corridas completas (324 evaluaciones: 24 init + 300 infill), leyendo la columna `exec.time` de mlrMBO en `02/resultados/HT4940/BO_log.txt` y `03/resultados/HT4940/BO_log.txt` (`exec.time` ≈ duración de cada `lgb.cv` objetivo). Las trayectorias de hiperparámetros no son idénticas; el ratio no es solo 3/5 folds.

| Métrica | `02` (5 CV) | `03` (3 CV) |
|---|---:|---:|
| Suma `exec.time` (324 eval.) | 5744 s (~1,60 h) | 2751 s (~0,76 h) |
| Media `exec.time` / eval. | 17,7 s | 8,5 s |
| `exec.time` + `train.time` + `propose.time` (aprox.) | ~6245 s (~1,73 h) | ~3267 s (~0,91 h) |

Reducción observada del costo de evaluación objetivo: **~52 %** (≈ **50 min** menos en `exec.time` acumulado). El overhead del surrogate (`propose.time`, `train.time`) es del mismo orden en ambas (~8–9 min); casi todo el ahorro viene del CV. `03` aumenta la varianza del AUC en la objetivo a cambio de ese tiempo.

### Producción: cuántos hiperparámetros de la BO y cuántos trains

Los mejores valores globales de la BO quedan en `HT4940/PARAM.yml` (`out.lgbm.mejores_hiperparametros`). El ranking completo está en `HT4940/BO_log.txt` (ordenado por AUC `y` descendente).

| Script | Qué toma de la BO | Entrenamientos finales (`lgb.train`) | Semilla(s) de train |
|---|---|---|---|
| `2_produccion_lightgbm.R` | **1** conjunto: el mejor en `PARAM.yml` | **1** | `427417` (desde hiperparámetros fijos / YAML) |
| `2_1_produccion_lightgbm_semillas.R` | **1** conjunto: el mejor en `PARAM.yml` | **10** (mismos HP, distinto `seed`) | Los 10 primos listados arriba |
| `6_produccion_top10_bo_semillas.R` | **10** conjuntos: las **10** primeras filas de `BO_log.txt` | **10 × 10 = 100** (cada rank × cada primo) | Mismos 10 primos por rank |

Presencia por carpeta:

| Carpeta | `1` BO | `2` (1×1) | `2_1` (1×10) | `6` (10×10) | Otros |
|---|---|---|---|---|---|
| `00` | sí | sí | — | — | — |
| `01` | sí | sí | sí | sí | `3`, `4`, `5`, `7` (estudio BO / cortes / surrogate / inferencia top-10) |
| `02` | sí | sí | sí | sí | Igual `01` |
| `03` | sí | — | sí | sí | `3`, `5`, `7` (sin `2_produccion` ni `4_cortes_...`) |

Salidas típicas: un solo modelo en `resultados/exp4940/` (`2` o `2_1` con sufijos `_<primo>`); estudio top-10 en `resultados/exp4940_top10/rank_XX/` y metadatos en `resultados/estudio/top10_bo_semillas/`.

---

Scripts base en `00/`:

| Script | Contenido |
|---|---|
| `1_bayesiana_lightgbm.R` | Parámetros, undersampling, `lgb.cv`, mlrMBO (30 iteraciones en `00`; 300 en `01`–`03`). |
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
PARAM$semilla_primigenia <- 427417   # cohorte z494; cambiar por la semilla propia
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

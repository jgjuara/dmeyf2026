# Optimización de hiperparámetros (`z0333_OptimizacionHiperparametros`)

Explicación del notebook `arboles/z0333_OptimizacionHiperparametros.ipynb` a partir de los experimentos en R. Quedan fuera la descarga de datos y la generación de `clase_ternaria`.

**Premisa:** existe `juara/jueves/data/competencia_01.csv.gz` con `clase_ternaria` ya calculada.

Scripts locales (ambos en `00/`):

- `00/1_curva_ganancia.R` — sección 3.04 (overfitting / curva de ganancia).
- `00/2_bayesiana_rpart.R` — sección 3.08 (Bayesian Optimization).

Artefactos en `00/resultados/`.

El overfitting usa `foto_mes == 202106`. La Bayesian Optimization usa `foto_mes == 202104`. No unificar.

## 3.01 Introducción

Los algoritmos de modelos predictivos tienen hiperparámetros que, dado un dataset, deben optimizarse. Invocarlos “sin hiperparámetros” es usar los defaults del fabricante. En `rpart`: `cp=0.01`, `maxdepth=30`, `minsplit=20`, `minbucket=6`. En este dataset eso suele producir un árbol de un solo nodo (no se abre), por la proporción de `BAJA+1` y `BAJA+2`.

En el mundo real no se dispone de la clase del futuro. Estimar la bondad de un set de hiperparámetros se hace con alguna combinación de:

- una sola partición `<training, testing>`
- múltiples particiones `<training, testing>`
- k-fold Cross Validation (en general `n >= 5`)
- n-repeated k-fold Cross Validation
- Leave One Out, si el tamaño del dataset y el cómputo lo permiten

El curso invita a extender un esqueleto de **Grid Search**.

## 3.02 Conceptos

El notebook cubre:

- origen del overfitting en un árbol de decisión
- *la maldición del ganador*, overfitting en los hiperparámetros ganadores, Selective Inference
- Data Drifting
- alternativas de búsqueda: Grid Search (fuerza bruta) y Bayesian Optimization (heurística)

## 3.04 Origen del overfitting — `1_curva_ganancia.R`

Pregunta: qué combinación de hiperparámetros overfitea un árbol en este dataset, y cómo se ve en las curvas de ganancia.

Objetivo: jugar con hiperparámetros de `rpart`, observar las curvas en una partición `<training=50%, testing=50%>` y extraer conclusiones.

**Curva de ganancia:** el modelo asigna una probabilidad a cada registro; cada registro aporta ganancia o pérdida. Se ordena por probabilidad descendente y se acumula la ganancia.

Overfitting **no** es la diferencia entre las curvas. Lo que separa underfitting de overfitting, al aumentar la complejidad, es el punto donde se alcanza la métrica máxima.

Combinaciones mínimas a probar (el script usa otros valores, los del notebook ejecutado):

| | `cp` | `maxdepth` | `minsplit` | `minbucket` |
|---|---|---|---|---|
| Crecimiento descontrolado | -1 | 30 | 2 | 1 |
| Talla reducida | -1 | 3 | 20000 | 10000 |
| Valores del notebook | -1 | 11 | 300 | 20 |

### Librerías

| Paquete | Uso |
|---|---|
| `data.table` | Lectura, filtro, curva acumulada. |
| `rpart` | Entrenamiento CART. |
| `ggplot2` | Curva train vs test. |

`R.utils` se carga en el notebook y no se usa en este tramo.

### Parámetros

```r
PARAM$semilla_primigenia <- 102191
PARAM$minsplit <- 300
PARAM$minbucket <- 20
PARAM$maxdepth <- 11
```

### Datos y partición

Se lee `competencia_01.csv.gz` y se filtra `foto_mes == 202106`.

`particionar` agrega `fold` estratificado por `clase_ternaria`. `division = c(1, 1)` es 50/50. Semilla: `PARAM$semilla_primigenia`.

### Algoritmo

1. `rpart("clase_ternaria ~ . -fold")` en `fold == 1`, `xval = 0`, `cp = -1`, resto desde `PARAM`.
2. `predict(..., type = "prob")` sobre **todo** el dataset (train y test).
3. Ordenar por `fold` y `-prob_baja2`.
4. Ganancia por fila: `2 * (1072500` si `BAJA+2`, `-27500` si no`)`. El `2` normaliza porque cada fold es el 50%.
5. `ganancia_acumulada = cumsum(gan)` por fold; `pos` es el ranking dentro del fold.
6. Graficar las primeras `amostrar = 20000` posiciones.

El notebook imprime el gráfico en Colab. El script guarda PDF y un log con `max(ganancia_acumulada)` de train (`fold==1`) y test (`fold==2`).

### Artefactos (`00/resultados/`)

| Archivo | Contenido |
|---|---|
| `curva_ganancia.pdf` | Curva de ganancia acumulada train vs test. |
| `ganancia_max.txt` | `PARAM` y máximos de ganancia train/test. |

## 3.05 Análisis de la salida de Grid Search

Texto de clase, sin código. En el aula cada mesa analiza las salidas de Grid Search de la Tarea para el Hogar. Se espera análisis de esos datos y, al final, un criterio para marcar dónde están las mayores ganancias.

## 3.06 La maldición del ganador

Pregunta: ¿los hiperparámetros ganadores de toda la cohorte están overfiteando?

Trabajo con la hoja **C3-GS Overfitting** de la Google Sheet colaborativa:

1. Determinar quién obtuvo la mayor ganancia y con qué hiperparámetros.
2. Copiarlos a **C3-GS Overfitting**.
3. Quien obtuvo esa ganancia no hace nada.
4. El resto modifica su Grid Search, calcula la ganancia de esos hiperparámetros con **su** semilla primigenia y registra el valor en la fila de su nombre.

Comparar la ganancia del ganador versus las ganancias recién calculadas.

Bibliografía citada en el notebook:

- Selective Inference — the silent killer of replicability (video).
- Ioannidis, J. P. A. Why most published research findings are false. *PLoS Med.* 2, e124 (2005).

## 3.07 Bayesian Optimization

Texto de clase, sin código. Se explica cómo, a partir del Grid Search, se deriva la Bayesian Optimization.

## 3.08 Bayesian Optimization — `2_bayesiana_rpart.R`

### Librerías

| Paquete | Uso |
|---|---|
| `data.table` | Lectura, filtro, `fwrite` del log. |
| `rpart` | Árbol en cada fold. |
| `parallel` | `mcmapply` / `detectCores` en la CV. |
| `DiceKriging` | Learner `regr.km` (surrogate). |
| `mlrMBO` | `makeParamSet`, `mbo`, `mboContinue`. |

`rlist` y `R.utils` se cargan en el notebook y no se usan. El markdown menciona `rpart.plot`; el código de BO no lo invoca.

`mcmapply(..., mc.cores = detectCores())` se deja igual que el notebook. El entorno de ejecución previsto es Linux.

### Parámetros

```r
PARAM$semilla_primigenia <- 102191
PARAM$experimento <- "HT308"
PARAM$BO_iter <- 40

PARAM$hs <- makeParamSet(
    makeNumericParam("cp", lower= -1, upper= 0.1),
    makeIntegerParam("minsplit", lower= 1L, upper= 8000L),
    makeIntegerParam("minbucket", lower= 1L, upper= 4000L),
    makeIntegerParam("maxdepth", lower= 3L, upper= 20L),
    forbidden= quote(minbucket > 0.5 * minsplit)
)
```

`minbucket` no puede ser mayor que la mitad de `minsplit`.

### Datos

Se lee `competencia_01.csv.gz` y se filtra `foto_mes == 202104`.

### Funciones

- `ArbolSimple(fold_test, param_rpart)`: entrena en todos los folds excepto `fold_test`; predice en ese fold; ganancia si `P(BAJA+2) > 1/40` (`1072500` / `-27500`). La ganancia del fold **no** está normalizada.
- `ArbolesCrossValidation`: partición en `qfolds` (cinco unos), `mcmapply` de `ArbolSimple`, promedio × `qfolds` (normalización al tamaño del dataset).
- `EstimarGanancia(x)`: objetivo de `mlrMBO`. Solo recibe los hiperparámetros a optimizar; el resto va por variables globales (`dataset`, `PARAM`). Incrementa `GLOBAL_iteracion`. CV de 5 folds, semilla `PARAM$semilla_primigenia`.

### Bayesian Optimization

Surrogate: Kriging `matern3_2` con error estándar. Infill: Expected Improvement. `minimize = FALSE` (se maximiza ganancia). `noisy = TRUE`. Checkpoint a disco cada 600 s.

Si existe `bayesian.RDATA`, se llama `mboContinue`. Si existe `BO_log.txt`, se restauran `GLOBAL_iteracion` y `GLOBAL_mejor`.

Al terminar, `opt.path` se ordena por `y` descendente y se escribe `BO_log.txt`. El primer registro se guarda en `PARAM$out$lgbm$mejores_hiperparametros` (nombre heredado del notebook; el modelo es `rpart`). El comentario del notebook habla de AUC; `y` es ganancia.

### Artefactos (`00/resultados/`)

| Archivo | Contenido |
|---|---|
| `BO_log.txt` | Camino de la BO (`opt.path`), tabulado. |
| `bayesian.RDATA` | Estado de `mlrMBO` para reanudar. |

Reejecutar con `bayesian.RDATA` presente **continúa** la búsqueda; no arranca de cero.

## Secuencia de ejecución

```powershell
Rscript juara/jueves/generar_clase_ternaria.R
Rscript juara/jueves/z333/00/1_curva_ganancia.R
Rscript juara/jueves/z333/00/2_bayesiana_rpart.R
```

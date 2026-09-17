# Ensembles — Árboles Azarosos (`z420_ArbolesAzarosos`)

Explicación de `ensembles/z420_ArbolesAzarosos.ipynb` a partir de **§4.02 Árboles Azarosos**. Quedan fuera Colab, descarga de `competencia_01_crudo.csv`, generación de `clase_ternaria`, limpieza con `rm(list=ls())` y marcas de tiempo.

**Premisa:** existe `juara/data/competencia_01.csv.gz` con `clase_ternaria` (salida de `generar_clase_ternaria.R`).

Scripts en `00/`:

| Script | Contenido |
|---|---|
| `1_arboles_azarosos.R` | Funciones de partición y ganancia, entrenamiento de 512 `rpart` con subconjuntos aleatorios de campos, demo de 5 árboles y métricas en puntos de control. |

Artefactos:

| Carpeta | Archivos |
|---|---|
| `00/resultados/exp4020/` | Carpeta de trabajo del notebook (sin escrituras a disco en el tramo extraído). |
| Consola | Ganancia TOTAL, Public y Private al llegar a 1, 2, 4, …, 512 árboles. |

## Objetivo

Construir un **ensemble de árboles de decisión** donde cada árbol usa el mismo algoritmo (`rpart`) pero un **subconjunto aleatorio de predictores** (perturbación del dataset, sin perturbar el algoritmo). Se promedia la probabilidad de clase `BAJA+2` y se evalúa ganancia de campaña en `foto_mes == 202106`.

## 1. Parámetros globales

```r
PARAM$semilla_primigenia <- 290497   # cambiar por la semilla propia
PARAM$train <- c(202104)
PARAM$future <- c(202106)
PARAM$feature_fraction <- 0.1        # fracción de campos por árbol
PARAM$rpart$cp <- -1
PARAM$rpart$minsplit <- 50
PARAM$rpart$minbucket <- 20
PARAM$rpart$maxdepth <- 6
PARAM$num_trees_max <- 512
PARAM$semilla_kaggle <- 314159
```

- **feature_fraction:** en el código del notebook es `0.1` (10% de los campos por árbol); el texto introductorio menciona 50% como primera corrida conceptual.
- **Corte de envío:** en cada punto de control, `Predicted = 1` si `prob_acumulada > arbolito/40` (promedio de prob. de `BAJA+2` frente a umbral creciente con el tamaño del ensemble).

## 2. Librerías

| Paquete | Uso |
|---|---|
| `data.table` | Lectura, filtros por `foto_mes`, tablas de predicción. |
| `rpart` | Un árbol por iteración; fórmula con campos muestreados al azar. |
| `here` | Rutas al dataset y a `00/resultados`. |

## 3. Flujo del script

1. **particionar**, **realidad_inicializar**, **realidad_evaluar:** partición 30/70 estratificada sobre el futuro (semilla Kaggle) para public/private de ganancia.
2. Entrenamiento en abril 2021; scoring en junio 2021 sin `clase_ternaria` en `dfuture`.
3. Bucle de demostración (5 árboles): gráficos base `plot`/`text` para ver diversidad de estructuras.
4. Bucle principal hasta 512 árboles: acumula `prob_acumulada`; en `grabar = c(1, 2, 4, 8, 16, 32, 64, 128, 256, 384, 512)` imprime ganancias.

Funciones de ganancia: +1 072 500 por `BAJA+2` contactado, −27 500 en caso contrario (misma convención que otras tareas de competencia).

## Orden de ejecución

```powershell
Rscript juara/jueves/generar_clase_ternaria.R
Rscript juara/jueves/z420/00/1_arboles_azarosos.R
```

**Tiempo:** 512 árboles con `rpart` sobre el train completo puede tardar bastante; conviene probar antes con un `PARAM$num_trees_max` menor.

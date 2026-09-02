# Árbol de impresión (`z0301_arbol_impresion`)

Explicación del notebook `arboles/z0301_arbol_impresion.ipynb` a partir de la sección **Impresión del árbol**. Quedan fuera la descarga de datos y la generación de `clase_ternaria`.

**Premisa:** existe `competencia_01.csv.gz` con `clase_ternaria` ya calculada.

## 1. Limpieza del ambiente

```r
rm(list = ls(all.names = TRUE))
gc(full = TRUE, verbose = FALSE)
```

Elimina todos los objetos de la sesión de R y fuerza recolección de basura. Evita que objetos de celdas anteriores (por ejemplo, el dataset crudo o `dsimple`) contaminen el experimento.

## 2. Librerías

| Paquete | Uso |
|---|---|
| `data.table` | Lectura del CSV comprimido (`fread`). |
| `rpart` | Entrenamiento del árbol de decisión. |
| `parallel` | Cargada en el notebook; no se usa en este tramo. |
| `rpart.plot` | Dibujo del árbol con `prp`. Se instala si no está. |
| `R.utils` | Cargada en el notebook; no se usa en este tramo. |

## 3. Parámetros del experimento

```r
PARAM <- list()
PARAM$experimento <- "arbol0301"

PARAM$param_basicos <- list(
  "cp" = -1,
  "maxdepth" = 4,
  "minsplit" = 20,
  "minbucket" = 5
)
```

- `experimento`: nombre de la carpeta de salida.
- `cp = -1`: no poda por complejidad de costo. Cualquier split que mejore el criterio se acepta, hasta los otros límites.
- `maxdepth = 4`: profundidad máxima del árbol (cuatro niveles de splits).
- `minsplit = 20`: no se intenta un split si el nodo tiene menos de 20 observaciones.
- `minbucket = 5`: cada hoja debe tener al menos 5 observaciones.

## 4. Carpeta de trabajo

```r
setwd("/content/buckets/b1/exp")
dir.create(PARAM$experimento, showWarnings = FALSE)
setwd(paste0("/content/buckets/b1/exp/", PARAM$experimento))
```

Crea `exp/arbol0301` (si no existe) y deja el directorio de trabajo ahí. El PDF del árbol se escribe en esa carpeta.

En Colab, `/content/buckets/b1` suele ser un enlace a Google Drive. Fuera de Colab hay que ajustar estas rutas.

## 5. Lectura del dataset

```r
dataset <- fread("/content/datasets/competencia_01.csv.gz")
```

Carga el dataset ya etiquetado. `clase_ternaria` es la variable objetivo (`CONTINUA`, `BAJA+1`, `BAJA+2`). El resto de columnas entran como predictores, salvo las que `rpart` descarte (identificadores, constantes, etc.).

## 6. Entrenamiento del árbol

```r
modelo <- rpart(
  "clase_ternaria ~ .",
  data = dataset,
  xval = 0,
  control = PARAM$param_basicos
)
```

- Fórmula `"clase_ternaria ~ ."`: clasificar `clase_ternaria` usando todas las demás columnas.
- `xval = 0`: sin validación cruzada interna de `rpart`. El árbol se ajusta sobre todo el `dataset`.
- `control`: hiperparámetros del paso 3.

El objeto `modelo` es un árbol de clasificación CART.

No hay partición train/test ni filtro por `foto_mes`. El árbol se entrena sobre todas las filas del archivo.

## 7. Impresión a PDF

```r
arch_arbol <- "arbol.pdf"
pdf(file = arch_arbol, width = 28, height = 4)
prp(modelo, extra = 101, digits = 5, branch = 1, type = 4, varlen = 0, faclen = 0)
dev.off()
```

1. Abre un dispositivo gráfico PDF de 28 × 4 pulgadas (ancho grande para un árbol poco profundo pero con muchas hojas).
2. `prp` dibuja el árbol.
3. `dev.off()` cierra el PDF.

Argumentos de `prp`:

| Argumento | Efecto |
|---|---|
| `extra = 101` | En cada nodo: recuento de clases y porcentaje de observaciones. |
| `digits = 5` | Precisión numérica de umbrales y estadísticas. |
| `branch = 1` | Ramas verticales (estilo “cuadrado”). |
| `type = 4` | Etiquetas en nodos internos y hojas. |
| `varlen = 0` | Nombres de variables sin recortar. |
| `faclen = 0` | Niveles de factores sin recortar. |

Salida: `arbol.pdf` en la carpeta del experimento.

## Orden de ejecución

1. Limpiar memoria.
2. Cargar librerías.
3. Definir `PARAM`.
4. Crear y entrar a la carpeta del experimento.
5. Leer `competencia_01.csv.gz`.
6. Ajustar `rpart`.
7. Exportar `arbol.pdf`.

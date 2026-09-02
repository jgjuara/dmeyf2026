# El árbol de Marga (`z0312_el_arbol_de_Marga`)

Explicación del notebook `arboles/z0312_el_arbol_de_Marga.ipynb` a partir de **El Arbol de Marga**. Quedan fuera descarga de datos y generación de `clase_ternaria`.

**Premisa:** existe `juara/lunes/data/competencia_01.csv.gz` con `clase_ternaria` ya calculada.

El script local es `00/arbol_marga.R`. Los artefactos van a `00/resultados/`.

## 1. Librerías

| Paquete | Uso |
|---|---|
| `data.table` | Lectura, filtros, `fwrite` de tablas. |
| `rpart` | Entrenamiento CART y `rpart:::tree.depth`. |
| `rpart.plot` | Dibujo del árbol (`prp`). |
| `primes` | `generate_primes` para muestrear semillas. |

`parallel` y `R.utils` se cargan en el notebook y no se usan en este tramo.

## 2. Parámetros

```r
PARAM$experimento <- "marga0312"
PARAM$semilla_primigenia <- 265621
PARAM$qsemillas <- 3
PARAM$peso_baja2 <- 1.0
PARAM$training_pct <- 70L
PARAM$param_basicos <- list(a1, a2)
```

- `semilla_primigenia`: semilla del muestreo de primos (no es la semilla de cada `rpart` de forma directa).
- `qsemillas`: cantidad de semillas de partición.
- `peso_baja2`: peso de observaciones `BAJA+2` en training y umbral de ganancia.
- `training_pct`: porcentaje del fold de entrenamiento (70 / 30).

Dos controles de árbol:

| | `cp` | `maxdepth` | `minsplit` | `minbucket` |
|---|---|---|---|---|
| a1 | -1 | 7 | 1500 | 500 |
| a2 | -1 | 9 | 1000 | 300 |

`cp = -1` desactiva la poda por complejidad de costo.

## 3. Semillas

Se generan primos en `[1e5, 1e6]`, se fija `set.seed(semilla_primigenia)` y se extraen `qsemillas` valores. Cada semilla se usa en `particionar` (reparto train/test), no como semilla interna de `rpart`.

## 4. Partición estratificada

`particionar` agrega `fold` al `data.table`:

- `fold == 1`: training (`training_pct` %).
- `fold == 2`: test (el resto).

El reparto es aleatorio **dentro de cada valor de** `clase_ternaria`. La misma semilla produce la misma partición para a1 y a2.

## 5. Datos

Se lee `competencia_01.csv.gz` y se filtra `foto_mes == 202106` (último mes con `clase_ternaria` completa). El modelo no usa el resto de meses.

## 6. Tabla de corridas

Si existe `00/resultados/tb_marga_detalle.txt`, se reanuda y `corrida` pasa a `max(corrida)+1`. Si no, se crea la tabla vacía y `corrida <- 1`.

Reejecutar el script **añade** filas; no borra corridas previas.

## 7. Bucle semilla × árbol

Para cada semilla y cada elemento de `PARAM$param_basicos`:

1. Particionar con esa semilla.
2. Pesos en training: `peso_baja2` si `BAJA+2`, si no `1.0`.
3. `rpart("clase_ternaria ~ .")` en `fold == 1`, `xval = 0`, `weights = pesos`.
4. PDF `arbol_{corrida}_{semilla}.pdf` (`prp` con `extra=101`, `type=4`, etc.).
5. Tabla del `modelo$frame` en `arbol_{corrida}_{semilla}.txt`.
6. `predict(..., type = "prob")` en `fold == 2`.
7. Ganancia: si `P(BAJA+2) > peso_baja2 / (peso_baja2 + 39)`, sumar `1072500` si es `BAJA+2` y `-27500` si no.
8. Ganancia normalizada: se divide por la fracción de test (`0.30` si `training_pct = 70`), como si el test fuera el dataset entero.
9. Métricas del árbol (`profundidad_real`, `minsplit_real`, `minbucket_real`, hojas, `complexity`) y append a `tb_marga_detalle.txt`.

Nombres de PDF/TXT: el notebook **no** incluye `iarbol`. Para una misma semilla, a2 **sobrescribe** los archivos de a1. Las dos filas sí quedan en `tb_marga_detalle.txt`.

## 8. Artefactos (`00/resultados/`)

| Archivo | Contenido |
|---|---|
| `arbol_{corrida}_{semilla}.pdf` | Dibujo del último árbol de esa semilla en la corrida. |
| `arbol_{corrida}_{semilla}.txt` | `modelo$frame` de ese mismo árbol. |
| `tb_marga_detalle.txt` | Una fila por (corrida, semilla, hiperparámetros). |

## Secuencia de ejecución

```powershell
Rscript juara/lunes/generar_clase_ternaria.R
Rscript juara/lunes/z312/00/arbol_marga.R
```

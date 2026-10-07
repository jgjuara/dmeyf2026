# Informe: cotas teóricas vs. profundidad efectiva en el grid search HT2900

## Resumen

El script `ht2900_grid_search.R` calcula cotas para `minsplit` y `minbucket` antes de ejecutar el grid search con `rpart`. Esas cotas **no son incorrectas aritméticamente**, pero modelan un árbol en **cadena** (path tree), no un árbol **binario** como el que construye `rpart`.

Consecuencia observada en los resultados: combinaciones como `(minsplit=1090, minbucket=502, maxdepth ∈ {8, 14, 20})` pasan los filtros del script, pero producen **exactamente la misma ganancia** porque la profundidad efectiva (~7) queda muy por debajo del techo `maxdepth`.

---

## 1. Contexto del experimento

### Datos y entrenamiento

```r
dataset <- fread("data/competencia_01.csv.gz")
dataset <- dataset[foto_mes == 202106]

N <- nrow(dataset)          # 164 114 observaciones
# Entrenamiento: 70%  →  N_train ≈ 114 879
# Test:          30%  →  N_test  ≈  49 235
```

El árbol se ajusta solo sobre `dataset[fold == 1]` (70%), pero las cotas del script usan `N` completo.

### Hiperparámetros relevantes de `rpart`

| Parámetro   | Rol |
|-------------|-----|
| `maxdepth`  | Techo de profundidad. No garantiza que el árbol llegue ahí. |
| `minsplit`  | Mínimo de observaciones en un nodo para **intentar** un split. |
| `minbucket` | Mínimo de observaciones en **cada hoja** terminal. |
| `cp`        | Penalización por complejidad (podado). |

---

## 2. Qué hace el script: cotas actuales

### Código relevante

```r
N <- nrow(dataset)

# Cota superior de minbucket para profundidad d
# minbucket <= N / (1 + d)
vminbucket <- N / (1 + depths)

# Relación derivada en comentarios:
# r_max(mb) = N/mb - (D - 1)
# minsplit_max = r_max * minbucket
r_options[, minsplit_max := r_max * minbucket]

# En el loop del grid search:
for (vmax_depth in seq(from = 14, to = 30, by = 2)) {
  max_mb_depth <- N / (1 + vmax_depth)
  mb_validos <- minbucket[minbucket <= max_mb_depth]

  for (vminbucket in mb_validos) {
    minsplit_max_admitido <- N - vminbucket * (vmax_depth - 1)
    split_validos <- minsplit[minsplit <= minsplit_max_admitido]
    # ...
  }
}
```

### Pseudocódigo del modelo implícito

```
MODELO_CADENA(N, maxdepth, minbucket, minsplit):

  # Supone un árbol degenerado: un camino principal de profundidad maxdepth
  # donde en cada nivel se "descarta" una hoja de tamaño minbucket.

  # Condición 1: repartir N en (maxdepth + 1) bloques iguales
  SI minbucket > N / (1 + maxdepth):
    RECHAZAR combinación

  # Condición 2: lo "consumido" en hojas del camino + lo mínimo para partir
  minsplit_max <- N - minbucket * (maxdepth - 1)
  SI minsplit > minsplit_max:
    RECHAZAR combinación

  ACEPTAR combinación
```

### Ejemplo numérico con las cotas del script

Parámetros: `N = 164 114`, `maxdepth = 14`, `minbucket = 502`, `minsplit = 1090`.

```
max_mb_depth = 164114 / (1 + 14) = 10 940.9
502 <= 10 940.9                          → minbucket OK

minsplit_max = 164114 - 502 * 13 = 157 588
1090 <= 157 588                          → minsplit OK
```

**Conclusión del script:** la combinación es válida.

---

## 3. Qué hace `rpart` en la práctica: árbol binario

### Pseudocódigo simplificado de crecimiento CART

```
CRECER_NODO(nodo, profundidad_actual):

  SI profundidad_actual >= maxdepth:
    RETORNAR hoja

  SI nodo.n < minsplit:
    RETORNAR hoja

  (izq, der) <- MEJOR_SPLIT_BINARIO(nodo)

  SI izq.n < minbucket O der.n < minbucket:
    RETORNAR hoja

  SI cp impide mejora suficiente:
    RETORNAR hoja

  nodo.izq  <- CRECER_NODO(izq,  profundidad_actual + 1)
  nodo.der  <- CRECER_NODO(der,  profundidad_actual + 1)
  RETORNAR nodo
```

Cada split **divide** el nodo en dos. En el caso balanceado, el tamaño se reduce aproximadamente a la mitad por nivel.

### Modelo binario balanceado (contraste con el script)

```
PROFUNDIDAD_EFECTIVA_BINARIA(N_train, minsplit, minbucket):

  PARA d DESDE 0 HASTA maxdepth:
    tam_nodo_promedio <- N_train / 2^d

    SI tam_nodo_promedio < minsplit:
      RETORNAR d - 1    # ya no se puede partir

    SI N_train < minbucket * 2^d:
      RETORNAR d - 1    # no caben hojas de tamaño minbucket

  RETORNAR maxdepth
```

### Mismo ejemplo, modelo binario

Con `N_train = 114 879`, `minsplit = 1090`, `minbucket = 502`:

| Profundidad d | N / 2^d (nodo medio) | ¿Puede partir? (≥ minsplit) | minbucket × 2^d |
|---------------|----------------------|-----------------------------|-----------------|
| 6             | 1 795                | sí                          | 32 128          |
| 7             | 898                  | **no**                      | 64 256          |
| 8             | 449                  | no                          | 128 512         |
| 14            | 7                    | no                          | 8 192 000       |

La profundidad efectiva queda en **~6–7**, no en 14.

Para alcanzar profundidad 14 con `minbucket = 502` harían falta del orden de:

```
502 * 2^14 ≈ 8,2 millones de observaciones de entrenamiento
```

Hay ~115 mil. **Imposible** en un árbol binario balanceado.

---

## 4. Evidencia empírica del grid search

### Caso top: posiciones 1, 2 y 3 del ranking

Parámetros compartidos: `cp = -1`, `minsplit = 1090`, `minbucket = 502`.  
Solo cambia `maxdepth ∈ {8, 14, 20}`.

Extracto de `gridsearch_detalle_unificado.txt` (semilla 514049):

```
514049  -1  8   1090  502  352366666.67
514049  -1  14  1090  502  352366666.67
514049  -1  20  1090  502  352366666.67
```

Las cinco semillas repiten el mismo patrón. Promedio: **353 870 000** en los tres casos.

### Interpretación

```
maxdepth = 8   → techo en profundidad 8
maxdepth = 14  → techo en profundidad 14
maxdepth = 20  → techo en profundidad 20

profundidad_efectiva ≈ 7  → los tres techos son irrelevantes
```

No es que `minbucket = 502` sea "grande" en escala absoluta (502 / 114 879 ≈ 0,4%).  
Es que **cada nivel reduce el tamaño del nodo** y `minsplit = 1090` impide seguir partiendo alrededor de la profundidad 7.

---

## 5. Comparación visual de modelos

### Modelo del script: árbol en cadena

```
                    [N = 164114]
                         |
              hoja(mb=502) + resto
                              |
                   hoja(mb=502) + resto
                              |
                            ...
                              |
                   hoja(mb=502) + resto (minsplit)
```

Consume `minbucket` **linealmente** con la profundidad: `(maxdepth - 1) * minbucket`.

### Modelo real de `rpart`: árbol binario

```
                         [N]
                        /   \
                    [N/2]   [N/2]
                    /  \     /  \
                 [N/4] ...  ...  [N/4]
                  ...
            nodos ~ N/2^d  →  cuando N/2^d < minsplit, STOP
```

Consume capacidad de split **exponencialmente** con la profundidad.

---

## 6. Dos problemas adicionales del script

### 6.1 Usa N total en lugar de N de entrenamiento

```r
N <- nrow(dataset)   # 164 114

# Pero el árbol entrena sobre:
dataset[fold == 1]   # ~114 879
```

Las cotas deberían calcularse con `N_train`, no con `N`. Usar `N` completo hace las cotas **aún más laxas**.

### 6.2 Las cotas filtran factibilidad, no relevancia de `maxdepth`

El script responde: *"¿existe algún árbol de profundidad D con estos parámetros?"*  
No responde: *"¿maxdepth va a ser el parámetro que limite el crecimiento?"*

Muchas combinaciones aceptadas son **redundantes** en `maxdepth`: variar el techo no cambia el árbol ni la ganancia.

---

## 7. Propuesta: cotas para árbol binario

### Pseudocódigo mejorado

```
ES_COMBINACION_RELEVANTE(N_train, maxdepth, minsplit, minbucket):

  # Profundidad máxima alcanzable por minsplit (árbol balanceado)
  d_minsplit <- floor(log2(N_train / minsplit))

  # Profundidad máxima alcanzable por minbucket (hojas balanceadas)
  d_minbucket <- floor(log2(N_train / minbucket))

  # Profundidad efectiva sin considerar maxdepth
  d_natural <- min(d_minsplit, d_minbucket)

  # Si maxdepth está por encima de lo que la grilla puede usar, es redundante
  SI maxdepth > d_natural + margen:
    MARCAR como "maxdepth no activo" (opcional: skip o agrupar)

  # Cotas más estrictas para filtrar
  SI minsplit > N_train / 2:
    RECHAZAR

  SI minbucket > N_train / 2:
    RECHAZAR

  ACEPTAR
```

### Ejemplo en R

```r
N_train <- floor(nrow(dataset) * PARAM$training_pct / 100)

profundidad_natural <- function(N, minsplit, minbucket) {
  d_split  <- floor(log2(N / minsplit))
  d_bucket <- floor(log2(N / minbucket))
  min(d_split, d_bucket)
}

# Para el caso top del grid search:
profundidad_natural(114879, minsplit = 1090, minbucket = 502)
# → min(floor(log2(105.4)), floor(log2(228.8)))
# → min(6, 7) = 6

# maxdepth = 8, 14 o 20  →  todos > 6  →  maxdepth no activo
```

### Tabla comparativa de cotas

| Combinación | Cota script (cadena) | Cota binaria (natural) | maxdepth activo |
|-------------|----------------------|------------------------|-----------------|
| mb=502, ms=1090, depth=14 | Acepta | d_natural ≈ 6 | No |
| mb=502, ms=1090, depth=8  | Acepta | d_natural ≈ 6 | No (8 > 6) |
| mb=10941, ms=21882, depth=14 | Acepta (justo) | d_natural ≈ 0–1 | Posiblemente sí |

---

## 8. Implicancias para interpretar el grid search

1. **Empates en `maxdepth`** con igual ganancia no son sorprendentes: el parámetro no está limitando el árbol.
2. **Ranking por `(cp, maxdepth, minsplit, minbucket)`** puede contener combinaciones redundantes que inflan el espacio de búsqueda sin aportar diversidad estructural.
3. **`minsplit` suele ser el freno dominante** cuando es del orden de N / 2^d para profundidades alcanzables.
4. Las cotas del script son útiles como **filtro de sanidad mínima**, no como **garantía de que `maxdepth` importe**.

---

## 9. Conclusiones

| Pregunta | Respuesta |
|----------|-----------|
| ¿Están mal las fórmulas del script? | No, para el modelo en cadena que asumen. |
| ¿Modelan correctamente a `rpart`? | No; `rpart` es binario y reduce nodos exponencialmente. |
| ¿Por qué maxdepth 8 = 14 = 20? | La profundidad efectiva (~7) queda bajo los tres techos. |
| ¿502 es un minbucket "grande"? | No en absoluto; es pequeño vs. N, pero crece el efecto por profundidad. |
| ¿Qué corregir? | Usar N_train y un modelo binario para cotas y/o detectar `maxdepth` redundante. |

---

## Referencias en el repositorio

- Script del grid search: `ht2900_grid_search.R`
- Detalle unificado: `exp/HT2900/gridsearch_detalle_unificado.txt`
- Promedios por parámetros: `exp/HT2900/gridsearch_promedio_por_params.csv`
- Cotas generadas: `exp/HT2900/r_options.csv`

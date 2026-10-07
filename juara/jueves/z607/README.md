# Paradigm Shift — árbol, canaritos y clase binaria (`z607_ParadigmShift`)

Extracción de `arboles/z0607_ParadigmShift.ipynb` desde **§6.3** (fenómeno que no debería suceder), **§6.4** (`rpart` con hiperparámetros de Bayesian Optimization) y **§6.6** (paradigm shift: clase binaria, canaritos y pruning). Quedan fuera Colab, descarga de `competencia_01_crudo.csv`, generación de `clase_ternaria` y celdas solo narrativas.

**Premisa:** existe `juara/data/competencia_01.csv.gz` con `clase_ternaria` (salida de `generar_clase_ternaria.R`).

## Scripts en `00/`

| Orden | Archivo | Contenido |
|---|---|---|
| 1 | `1_canaritos_clase_ternaria.R` | Entrena `rpart` sobre `clase_ternaria` en `foto_mes==202104` con 154 variables canarito; escribe `exp6300/arbol_canaritos.pdf`. |
| 2 | `2_rpart_binario_bayes_optimo.R` | Clase binaria POS/NEG, pesos de la BO, hiperparámetros óptimos; entrena en 202104, puntúa 202106 y reporta `max(gan_suave)`; salida bajo `exp6400/`. |
| 3 | `3_paradigm_shift_pruning_canaritos.R` | Canaritos en todo el dataset, árbol binario con peso 500, pruning por hack en `$frame`, PDF `exp6600/stopping_at_canaritos.pdf` y ganancia suavizada en 202106. |

`PARAM$semilla_primigenia` es `102191` en los tres tramos (como en el notebook).

### Hiperparámetros destacados

- **§6.3:** `cp=-1`, `maxdepth=6`, `minsplit=50`, `minbucket=5`; fórmula `clase_ternaria ~ .`.
- **§6.4:** `peso≈15.97`, `maxdepth=27`, `minsplit=1684`, `minbucket=447`; se eliminan `cprestamos_personales` y `mprestamos_personales` por data drifting.
- **§6.6:** `peso=500`, `maxdepth=16` (en clase el notebook sugiere 31), `minsplit=2`, `minbucket=1`; 155 canaritos; pruning con `complexity <- -666` en splits sobre `canarito*`.

### Artefactos

- `00/resultados/exp6300/arbol_canaritos.pdf`
- `00/resultados/exp6400/` (métrica impresa en consola; sin PDF en el notebook)
- `00/resultados/exp6600/stopping_at_canaritos.pdf`

## Secuencia de ejecución

```powershell
Rscript juara/jueves/generar_clase_ternaria.R
Rscript juara/jueves/z607/00/1_canaritos_clase_ternaria.R
Rscript juara/jueves/z607/00/2_rpart_binario_bayes_optimo.R
Rscript juara/jueves/z607/00/3_paradigm_shift_pruning_canaritos.R
```

Los tiempos indicados en el notebook (≈4 min, ≈2 min, ≈6 min) dependen del hardware.

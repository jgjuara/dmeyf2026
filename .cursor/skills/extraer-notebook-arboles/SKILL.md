---
name: extraer-notebook-arboles
description: >-
  Extrae el código R sustantivo de un notebook en arboles/ a un README y
  scripts Rscript numerados (1_...R, 2_...R) en juara/lunes/zNNN/00, con
  salida en 00/resultados. Usar cuando el usuario pida extraer, portar, localizar o replicar un notebook
  z0XXX de arboles, o invoque extraer-notebook-arboles.
---

# Extraer notebook de `arboles/` a `juara/lunes`

## Objetivo

Convertir un `.ipynb` de `arboles/` en:

1. `juara/lunes/zNNN/README.md` — explicación del tramo útil
2. `juara/lunes/zNNN/00/<N>_<script>.R` — uno o más scripts ejecutables con `Rscript`, numerados según el orden en el notebook (`1_...R`, `2_...R`, …)

Patrón de referencia: `juara/lunes/z301/` y `juara/lunes/generar_clase_ternaria.R`.

## Inventario

Leer el notebook completo. Identificar:

- Título / id (`z0301_...` → carpeta `z301`)
- Sección donde empieza el experimento (tras Colab, descarga y `clase_ternaria`)
- Paquetes realmente usados (no los que solo se cargan)
- Artefactos de salida (PDF, `fwrite`, logs)

Si el usuario no nombra el notebook, preguntar cuál de `arboles/*.ipynb`.

## Destino

| Notebook | Carpeta |
|---|---|
| `arboles/z0NNN_*.ipynb` | `juara/lunes/zNNN/` (quitar el 0 tras `z`) |

Ejemplos: `z0301` → `z301`, `z0312` → `z312`, `z0333` → `z333`.

Crear `juara/lunes/zNNN/` y `juara/lunes/zNNN/00/` si no existen.

Si `zNNN` ya existe y no corresponde a este notebook, no sobrescribir: preguntar.

Nombre del script: prefijo numérico según el orden en el notebook de origen, seguido de un slug descriptivo: `1_arbol_impresion.R`, `2_arbol_marga.R`, etc. El número refleja la secuencia de bloques de código sustantivos incluidos (no el índice de celda del `.ipynb`). Un script por bloque/experimento sustantivo; si el tramo útil es un solo bloque continuo, un solo script `1_<slug>.R`.

`00/resultados` no se crea a mano: el script hace `dir.create`.

## Qué incluir / excluir

**Excluir siempre**

- Runtime Python/Colab, `drive.mount`, `%%shell`
- Descarga de `competencia_01_crudo.csv`
- Generación de `clase_ternaria` (ya está en `generar_clase_ternaria.R`)
- Celdas que solo imprimen tablas o `getwd()` sin lógica

**Incluir**

Todo lo posterior a la sección de experimento: `PARAM`, semillas, filtros (`foto_mes`), funciones (`particionar`, etc.), bucles, `rpart`/`prp`, métricas, escrituras.

## README

Paso a paso del tramo incluido: librerías, `PARAM`, datos, algoritmo, artefactos. Premisa: existe `competencia_01.csv.gz` con `clase_ternaria`. Rutas locales (`00/resultados`), no Colab.

No copiar el README de `z301`; adaptar al notebook actual.

## Script R

Plantilla de rutas (obligatoria):

```r
script_dir <- dirname(normalizePath(sub(
  "^--file=",
  "",
  commandArgs(trailingOnly = FALSE)[grep("^--file=", commandArgs(trailingOnly = FALSE))]
)))
DATA_DIR <- file.path(dirname(dirname(script_dir)), "data")
RESULTADOS_DIR <- file.path(script_dir, "resultados")
dir.create(RESULTADOS_DIR, recursive = TRUE, showWarnings = FALSE)
```

- Dataset: `file.path(DATA_DIR, "competencia_01.csv.gz")` (u otro archivo que el notebook lea **después** de `clase_ternaria`).
- Conservar lógica e hiperparámetros del notebook.
- Conservar los comentarios presentes en los bloques de código de origen del notebook, como comentarios R (`# ...`), en la misma posición relativa respecto al código que acompañan. No omitirlos ni parafrasearlos.
- No `setwd`. Toda escritura con `file.path(RESULTADOS_DIR, ...)`.
- Si el notebook reanuda desde un archivo (p. ej. `tb_marga_detalle.txt`), leerlo y escribirlo en `RESULTADOS_DIR`.
- No `rm(list = ls())`.
- No cargar paquetes no usados.
- Ejecutable con `Rscript` desde cualquier cwd.

## Secuencia de ejecución (documentar, no correr)

```powershell
Rscript juara/lunes/generar_clase_ternaria.R
Rscript juara/lunes/zNNN/00/1_<script>.R
Rscript juara/lunes/zNNN/00/2_<script>.R
```

No ejecutar esos comandos ni commitear salvo pedido explícito.

## Checklist

- [ ] Directorios `zNNN/` y `zNNN/00/` creados
- [ ] README cubre el tramo útil, sin descarga ni `clase_ternaria`
- [ ] Scripts nombrados con prefijo de orden (`1_...R`, `2_...R`, …) según el notebook de origen
- [ ] Script usa `DATA_DIR` / `RESULTADOS_DIR` como arriba
- [ ] Comentarios de los bloques de código del notebook preservados en el script R
- [ ] Artefactos van a `00/resultados`
- [ ] Paquetes solo los usados
- [ ] Sin `setwd` ni Colab

# Grid search de hiperparametros rpart sobre competencia_01

# script_dir <- dirname(normalizePath(sub(
#   "^--file=",
#   "",
#   commandArgs(trailingOnly = FALSE)[grep("^--file=", commandArgs(trailingOnly = FALSE))]
# )))
JUARA_DIR <- getwd()
DATA_DIR <- file.path(JUARA_DIR, "data")
EXP_DIR <- file.path(JUARA_DIR, "exp")
# dir.create(DATA_DIR, recursive = TRUE, showWarnings = FALSE)
# dir.create(EXP_DIR, recursive = TRUE, showWarnings = FALSE)

require("data.table")
require("rpart")
require("parallel")

if (!require("R.utils")) install.packages("R.utils")
require("R.utils")

if (!require("primes")) install.packages("primes")
require("primes")

PARAM <- list()
PARAM$semilla_primigenia <- 427417
PARAM$qsemillas <- 10
PARAM$training_pct <- 70L

particionar <- function(data, division, agrupa = "", campo = "fold", start = 1, seed = NA) {
  if (!is.na(seed)) set.seed(seed)

  bloque <- unlist(mapply(function(x, y) {
    rep(y, x)
  }, division, seq(from = start, length.out = length(division))))

  data[, (campo) := sample(rep(bloque, ceiling(.N / length(bloque))))[1:.N],
    by = agrupa
  ]
}

ArbolEstimarGanancia <- function(semilla, training_pct, param_basicos) {
  particionar(dataset,
    division = c(training_pct, 100L - training_pct),
    agrupa = "clase_ternaria",
    seed = semilla
  )

  modelo <- rpart("clase_ternaria ~ .",
    data = dataset[fold == 1],
    xval = 0,
    control = param_basicos
  )

  prediccion <- predict(modelo,
    dataset[fold == 2],
    type = "prob"
  )

  ganancia_test <- dataset[
    fold == 2,
    sum(ifelse(prediccion[, "BAJA+2"] > 0.025,
      ifelse(clase_ternaria == "BAJA+2", 1072500, -27500),
      0
    ))
  ]

  ganancia_test_normalizada <- ganancia_test / ((100 - PARAM$training_pct) / 100)

  return(
    c(
      list("semilla" = semilla),
      param_basicos,
      list("ganancia_test" = ganancia_test_normalizada)
    )
  )
}

ArbolesMontecarlo <- function(semillas, param_basicos) {
  salida <- mcmapply(ArbolEstimarGanancia,
    semillas,
    MoreArgs = list(PARAM$training_pct, param_basicos),
    SIMPLIFY = FALSE,
    mc.cores = detectCores()
  )

  return(salida)
}

experimento <- "HT2900"
dir.create(file.path(EXP_DIR, experimento), recursive = TRUE, showWarnings = FALSE)
# setwd(file.path(EXP_DIR, experimento))

dataset <- fread(file.path(DATA_DIR, "competencia_01.csv.gz"))
dataset <- dataset[foto_mes == 202106]

invisible(gc(full = TRUE, verbose = FALSE))

print(nrow(dataset))
print(dataset[, .N, clase_ternaria])

primos <- generate_primes(min = 100000, max = 1000000)
set.seed(PARAM$semilla_primigenia)
PARAM$semillas <- sample(primos, PARAM$qsemillas)

DETALLE_FILE <- "gridsearch_detalle.txt"
es_primera_escritura <- !file.exists(DETALLE_FILE)

if (file.exists(DETALLE_FILE)) {
  tb_previo <- fread(DETALLE_FILE)
  tuplas_hechas <- unique(tb_previo[, .(cp, maxdepth, minsplit, minbucket)])
} else {
  tb_previo <- NULL
  tuplas_hechas <- data.table(
    cp = numeric(),
    maxdepth = integer(),
    minsplit = integer(),
    minbucket = integer()
  )
}

print(if (is.null(tb_previo)) 0L else nrow(tb_previo))

# cuales son los rangos de minbucket teoricamente max y min?
# el minimo es 0
# el maximo esta dado por  N / (1 +Dmin) donde Dmin es la minimo profundidad a probar

# entonces puedo armar el rango de minbucket entre ambas cotas
# y luego puedo calcular minsplit en funcion de r
# r_max(mb) = N/mb-(D-1) => minsplit_max = r_max * minbucket
N <- nrow(dataset)
depths <- 14:30
vminbucket <- N / (1 + depths)

r_options <- rbindlist(lapply(depths, function(d) {
  mb_validos <- vminbucket[vminbucket <= N / (1 + d)]
  data.table(
    d = d,
    minbucket = mb_validos,
    r_max = N / mb_validos - (d - 1)
  )
}))

r_options[, minsplit_max := r_max * minbucket]
data.table::fwrite(r_options, "exp/HT2900/r_options.csv")


minsplit <- seq( 0, max(r_options$minsplit_max), (max(r_options$minsplit_max)/20))
minbucket <- seq( 0, max(r_options$minbucket), (max(r_options$minbucket)/20))
  

iter <- 0
tiempo_loop_inicio <- proc.time()

for (vmax_depth in seq(from = 14, to = 30, by = 2)) {
  max_mb_depth <- N / (1 + vmax_depth)
  mb_validos <- minbucket[minbucket <= max_mb_depth]

  for (vminbucket in mb_validos) {
    if (vminbucket > 0) {
      minsplit_max_admitido <- N - vminbucket * (vmax_depth - 1)
      split_validos <- minsplit[minsplit <= minsplit_max_admitido]
    } else {
      split_validos <- minsplit
    }

    for (vmin_split in split_validos) {
      for (c in c(-1, -0.5, 0, 0.5, 1)) {
        iter <- iter + 1
        header <- sprintf(
          "[iter %4d] depth=%2d  minbucket=%8.0f  minsplit=%10.0f  cp=%+5.1f",
          iter, vmax_depth, vminbucket, vmin_split, c
        )

        if (nrow(tuplas_hechas[
          cp == c & maxdepth == vmax_depth &
            minsplit == vmin_split & minbucket == vminbucket
        ]) > 0) {
          cat(header, " | skip\n")
          flush.console()
          next
        }

        cat(header, " | run\n")
        flush.console()

        param_basicos <- list(
          "cp" = c,
          "maxdepth" = vmax_depth,
          "minsplit" = vmin_split,
          "minbucket" = vminbucket
        )

        ganancias <- ArbolesMontecarlo(PARAM$semillas, param_basicos)
        nuevas <- rbindlist(ganancias)

        fwrite(
          nuevas,
          file = DETALLE_FILE,
          sep = "\t",
          append = !es_primera_escritura,
          col.names = es_primera_escritura
        )
        es_primera_escritura <- FALSE
        tuplas_hechas <- rbindlist(list(
          tuplas_hechas,
          unique(nuevas[, .(cp, maxdepth, minsplit, minbucket)])
        ))
        cat(sprintf(
          "           ganancia_mean=%.0f  (semillas=%d)\n",
          mean(nuevas$ganancia_test),
          nrow(nuevas)
        ))
        flush.console()
      }
    }
  }
}

tiempo_loop <- proc.time() - tiempo_loop_inicio
cat(sprintf(
  "\n[loop] tiempo total: %.1f s (%.2f min) | iteraciones=%d | user=%.1f s system=%.1f s\n",
  tiempo_loop["elapsed"],
  tiempo_loop["elapsed"] / 60,
  iter,
  tiempo_loop["user.self"],
  tiempo_loop["sys.self"]
))
flush.console()

tb_grid_search_detalle <- fread(DETALLE_FILE)

print(nrow(tb_grid_search_detalle))
print(tb_grid_search_detalle)

tb_grid_search <- tb_grid_search_detalle[,
  list(
    "ganancia_mean" = mean(ganancia_test),
    "qty" = .N
  ),
  list(cp, maxdepth, minsplit, minbucket)
]

setorder(tb_grid_search, -ganancia_mean)
print(tb_grid_search[1:10])

tb_grid_search[, id := .I]

fwrite(
  tb_grid_search,
  file = "gridsearch.txt",
  sep = "\t"
)

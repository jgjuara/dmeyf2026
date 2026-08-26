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
setwd(file.path(EXP_DIR, experimento))

dataset <- fread(file.path(DATA_DIR, "competencia_01.csv.gz"))
dataset <- dataset[foto_mes == 202106]

invisible(gc(full = TRUE, verbose = FALSE))

print(nrow(dataset))
print(dataset[, .N, clase_ternaria])

primos <- generate_primes(min = 100000, max = 1000000)
set.seed(PARAM$semilla_primigenia)
PARAM$semillas <- sample(primos, PARAM$qsemillas)

if (file.exists("gridsearch_detalle.txt")) {
  tb_grid_search_detalle <- fread("gridsearch_detalle.txt")
} else {
  tb_grid_search_detalle <- data.table(
    semilla = integer(),
    cp = numeric(),
    maxdepth = integer(),
    minsplit = integer(),
    minbucket = integer(),
    ganancia_test = numeric()
  )
}

print(nrow(tb_grid_search_detalle))

iter <- 0

for (vmax_depth in c(4, 6, 8, 10, 12, 14)) {
  for (vmin_split in c(1000, 800, 600, 400, 200, 100, 50, 20, 10)) {
    iter <- iter + 1
    cat(iter, " ")
    flush.console()
    if (iter * PARAM$qsemillas < nrow(tb_grid_search_detalle) + 1) next

    param_basicos <- list(
      "cp" = -0.5,
      "maxdepth" = vmax_depth,
      "minsplit" = vmin_split,
      "minbucket" = 5
    )

    ganancias <- ArbolesMontecarlo(PARAM$semillas, param_basicos)

    tb_grid_search_detalle <- rbindlist(
      list(
        tb_grid_search_detalle,
        rbindlist(ganancias)
      )
    )
  }

  fwrite(
    tb_grid_search_detalle,
    file = "gridsearch_detalle.txt",
    sep = "\t"
  )
}

fwrite(
  tb_grid_search_detalle,
  file = "gridsearch_detalle.txt",
  sep = "\t"
)

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

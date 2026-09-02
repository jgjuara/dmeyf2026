# Entrena arboles rpart (dos grids) sobre 202106, estima ganancia en test
# e imprime cada arbol (PDF + tabla).
#
# Asume juara/lunes/data/competencia_01.csv.gz (generar_clase_ternaria.R).
# Escribe PDF, TXT y tb_marga_detalle.txt en resultados/.

script_dir <- dirname(normalizePath(sub(
  "^--file=",
  "",
  commandArgs(trailingOnly = FALSE)[grep("^--file=", commandArgs(trailingOnly = FALSE))]
)))
DATA_DIR <- file.path(dirname(dirname(script_dir)), "data")
RESULTADOS_DIR <- file.path(script_dir, "resultados")
dir.create(RESULTADOS_DIR, recursive = TRUE, showWarnings = FALSE)

require("data.table")
require("rpart")
if (!require("rpart.plot")) install.packages("rpart.plot")
require("rpart.plot")
if (!require("primes")) install.packages("primes")
require("primes")

PARAM <- list()
PARAM$experimento <- "marga0312"
PARAM$semilla_primigenia <- 265621
PARAM$qsemillas <- 3
PARAM$peso_baja2 <- 1.0
PARAM$training_pct <- 70L

a1 <- list(
  "cp" = -1,
  "maxdepth" = 7,
  "minsplit" = 1500,
  "minbucket" = 500
)

a2 <- list(
  "cp" = -1,
  "maxdepth" = 9,
  "minsplit" = 1000,
  "minbucket" = 300
)

PARAM$param_basicos <- list(a1, a2)

primos <- generate_primes(min = 100000, max = 1000000)
set.seed(PARAM$semilla_primigenia)
PARAM$semillas <- sample(primos, PARAM$qsemillas)

particionar <- function(data, division, agrupa = "", campo = "fold", start = 1, seed = NA) {
  if (!is.na(seed)) set.seed(seed)

  bloque <- unlist(mapply(function(x, y) {
    rep(y, x)
  }, division, seq(from = start, length.out = length(division))))

  data[, (campo) := sample(rep(bloque, ceiling(.N / length(bloque))))[1:.N],
    by = agrupa
  ]
}

dataset <- fread(file.path(DATA_DIR, "competencia_01.csv.gz"))
dataset <- dataset[foto_mes == 202106]
invisible(gc(full = TRUE, verbose = FALSE))

arch_detalle <- file.path(RESULTADOS_DIR, "tb_marga_detalle.txt")
if (file.exists(arch_detalle)) {
  tb_marga_detalle <- fread(arch_detalle)
} else {
  tb_marga_detalle <- data.table(
    corrida = integer(),
    semilla = integer(),
    peso_baja2 = numeric(),
    cp = numeric(),
    maxdepth = integer(),
    minsplit = integer(),
    minbucket = integer(),
    ganancia_test = numeric(),
    profundidad_real = numeric(),
    minsplit_real = numeric(),
    minbucket_real = numeric(),
    hojas_cantidad = numeric(),
    complexity_raiz = numeric(),
    complexity_min = numeric()
  )
}

if (0 == nrow(tb_marga_detalle)) {
  corrida <- 1
} else {
  corrida <- 1 + tb_marga_detalle[, max(corrida)]
}

for (semilla in PARAM$semillas) {
  for (iarbol in seq(length(PARAM$param_basicos))) {
    particionar(
      dataset,
      division = c(PARAM$training_pct, 100L - PARAM$training_pct),
      agrupa = "clase_ternaria",
      seed = semilla
    )

    pesos <- dataset[fold == 1, ifelse(clase_ternaria == "BAJA+2", PARAM$peso_baja2, 1.0)]

    modelo <- rpart(
      "clase_ternaria ~ .",
      data = dataset[fold == 1],
      xval = 0,
      control = PARAM$param_basicos[[iarbol]],
      weights = pesos
    )

    arch_arbol <- file.path(RESULTADOS_DIR, paste0("arbol_", corrida, "_", semilla, ".pdf"))
    pdf(file = arch_arbol, width = 28, height = 4)
    prp(modelo, extra = 101, digits = 5, branch = 1, type = 4, varlen = 0, faclen = 0)
    dev.off()

    tb_arbol_tabla <- as.data.table(modelo$frame, keep.rownames = "nodo")
    arch_tabla <- file.path(RESULTADOS_DIR, paste0("arbol_", corrida, "_", semilla, ".txt"))
    fwrite(tb_arbol_tabla, file = arch_tabla, sep = "\t")

    prediccion <- predict(modelo, dataset[fold == 2], type = "prob")

    ganancia_test <- dataset[
      fold == 2,
      sum(ifelse(
        prediccion[, "BAJA+2"] > (PARAM$peso_baja2 / (PARAM$peso_baja2 + 39.0)),
        ifelse(clase_ternaria == "BAJA+2", 1072500, -27500),
        0
      ))
    ]

    ganancia_test_normalizada <- ganancia_test / ((100 - PARAM$training_pct) / 100)

    resultado <- c(
      list("corrida" = corrida, "semilla" = semilla, "peso_baja2" = PARAM$peso_baja2),
      PARAM$param_basicos[[iarbol]],
      list(
        "ganancia_test" = ganancia_test_normalizada,
        "profundidad_real" = max(rpart:::tree.depth(as.numeric(rownames(modelo$frame)))),
        "minsplit_real" = tb_arbol_tabla[var != "<leaf>", min(yval2.V2 + yval2.V3 / PARAM$peso_baja2 + yval2.V4)],
        "minbucket_real" = tb_arbol_tabla[var == "<leaf>", min(yval2.V2 + yval2.V3 / PARAM$peso_baja2 + yval2.V4)],
        "hojas_cantidad" = tb_arbol_tabla[var == "<leaf>", .N],
        "complexity_raiz" = tb_arbol_tabla[nodo == 1, complexity],
        "complexity_min" = tb_arbol_tabla[var != "<leaf>", min(complexity)]
      )
    )

    tb_marga_detalle <- rbindlist(list(tb_marga_detalle, resultado))
    fwrite(tb_marga_detalle, arch_detalle, sep = "\t")
  }
}

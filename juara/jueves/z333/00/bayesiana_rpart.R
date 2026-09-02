# Optimiza hiperparametros de rpart con mlrMBO sobre 202104 (5-fold CV).
#
# Asume juara/lunes/data/competencia_01.csv.gz (generar_clase_ternaria.R).
# Escribe BO_log.txt y bayesian.RDATA en resultados/.
# Si esos archivos existen, reanuda la corrida.

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
require("parallel")
if (!require("DiceKriging")) install.packages("DiceKriging")
require("DiceKriging")
if (!require("mlrMBO")) install.packages("mlrMBO")
require("mlrMBO")

PARAM <- list()
PARAM$semilla_primigenia <- 102191
PARAM$experimento <- "HT308"
PARAM$BO_iter <- 40

PARAM$hs <- makeParamSet(
  makeNumericParam("cp", lower = -1, upper = 0.1),
  makeIntegerParam("minsplit", lower = 1L, upper = 8000L),
  makeIntegerParam("minbucket", lower = 1L, upper = 4000L),
  makeIntegerParam("maxdepth", lower = 3L, upper = 20L),
  forbidden = quote(minbucket > 0.5 * minsplit)
)

particionar <- function(data, division, agrupa = "", campo = "fold",
                        start = 1, seed = NA) {
  if (!is.na(seed)) set.seed(seed)

  bloque <- unlist(mapply(
    function(x, y) {
      rep(y, x)
    }, division,
    seq(from = start, length.out = length(division))
  ))

  data[, (campo) := sample(rep(bloque, ceiling(.N / length(bloque))))[1:.N],
    by = agrupa
  ]
}

ArbolSimple <- function(fold_test, param_rpart) {
  modelo <- rpart("clase_ternaria ~ .",
    data = dataset[fold != fold_test, ],
    xval = 0,
    control = param_rpart
  )

  prediccion <- predict(modelo,
    dataset[fold == fold_test, ],
    type = "prob"
  )

  prob_baja2 <- prediccion[, "BAJA+2"]

  ganancia_testing <- dataset[fold == fold_test][
    prob_baja2 > 1 / 40,
    sum(ifelse(clase_ternaria == "BAJA+2",
      1072500, -27500
    ))
  ]

  return(ganancia_testing)
}

ArbolesCrossValidation <- function(param_rpart, qfolds, pagrupa, semilla) {
  divi <- rep(1, qfolds)

  particionar(dataset, divi, seed = semilla, agrupa = pagrupa)

  ganancias <- mcmapply(ArbolSimple,
    seq(qfolds),
    MoreArgs = list(param_rpart),
    SIMPLIFY = FALSE,
    mc.cores = detectCores()
  )

  dataset[, fold := NULL]

  ganancia_promedio <- mean(unlist(ganancias))
  ganancia_promedio_normalizada <- ganancia_promedio * qfolds

  return(ganancia_promedio_normalizada)
}

EstimarGanancia <- function(x) {
  message(format(Sys.time(), "%a %b %d %X %Y"))
  GLOBAL_iteracion <<- GLOBAL_iteracion + 1

  xval_folds <- 5
  ganancia <- ArbolesCrossValidation(
    param_rpart = x,
    qfolds = xval_folds,
    pagrupa = "clase_ternaria",
    semilla = PARAM$semilla_primigenia
  )

  return(ganancia)
}

dataset <- fread(file.path(DATA_DIR, "competencia_01.csv.gz"))
dataset <- dataset[foto_mes == 202104]

archivo_log <- file.path(RESULTADOS_DIR, "BO_log.txt")
archivo_BO <- file.path(RESULTADOS_DIR, "bayesian.RDATA")

GLOBAL_iteracion <- 0
GLOBAL_mejor <- -Inf

if (file.exists(archivo_log)) {
  tabla_log <- fread(archivo_log)
  GLOBAL_iteracion <- nrow(tabla_log)
  GLOBAL_mejor <- tabla_log[, max(y)]
}

funcion_optimizar <- EstimarGanancia

configureMlr(show.learner.output = FALSE)

obj.fun <- makeSingleObjectiveFunction(
  fn = funcion_optimizar,
  minimize = FALSE,
  noisy = TRUE,
  par.set = PARAM$hs,
  has.simple.signature = FALSE
)

ctrl <- makeMBOControl(
  save.on.disk.at.time = 600,
  save.file.path = archivo_BO
)

ctrl <- setMBOControlTermination(ctrl, iters = PARAM$BO_iter)
ctrl <- setMBOControlInfill(ctrl, crit = makeMBOInfillCritEI())

surr.km <- makeLearner("regr.km",
  predict.type = "se",
  covtype = "matern3_2", control = list(trace = TRUE)
)

if (!file.exists(archivo_BO)) {
  bayesiana_salida <- mbo(
    fun = obj.fun,
    learner = surr.km,
    control = ctrl
  )
} else {
  bayesiana_salida <- mboContinue(archivo_BO)
}

tb_bayesiana <- as.data.table(bayesiana_salida$opt.path)

setorder(tb_bayesiana, -y)

fwrite(tb_bayesiana,
  file = archivo_log,
  sep = "\t"
)

PARAM$out$lgbm$mejores_hiperparametros <- tb_bayesiana[
  1,
  list(cp, minsplit, minbucket, maxdepth)
]

print(PARAM$out$lgbm$mejores_hiperparametros)
print(format(Sys.time(), "%a %b %d %X %Y"))

# Bayesian Optimization de hiperparametros ranger (experimento HT450).
#
# Asume juara/data/competencia_01.csv.gz (generar_clase_ternaria.R).
# Escribe HT450.RDATA, HT450.txt y HT450_mejor.txt en 00/resultados/HT450/.

require("here")
here::i_am("juara/jueves/z440/00/2_bayesiana_ranger.R")
DATA_DIR <- here("juara", "data")
RESULTADOS_DIR <- here("juara", "jueves", "z440", "00", "resultados")
dir.create(RESULTADOS_DIR, recursive = TRUE, showWarnings = FALSE)

# cargo las librerias que necesito
require("data.table")
require("parallel")

if (!require("R.utils")) install.packages("R.utils")
require("R.utils")

if (!require("primes")) install.packages("primes")
require("primes")

# ranger se usa para procesar
if (!require("ranger")) install.packages("ranger")
require("ranger")

# randomForest  solo se usa para imputar nulos
if (!require("randomForest")) install.packages("randomForest")
require("randomForest")

if (!require("DiceKriging")) install.packages("DiceKriging")
require("DiceKriging")

if (!require("mlrMBO")) install.packages("mlrMBO")
require("mlrMBO")

# Aqui debe cargar SU semilla primigenia y
PARAM <- list()
PARAM$experimento <- 450
PARAM$semilla_primigenia <- 290497

PARAM$hyperparametertuning$iteraciones <- 5
PARAM$hyperparametertuning$xval_folds <- 5
PARAM$hyperparametertuning$POS_ganancia <- 1072500
PARAM$hyperparametertuning$NEG_ganancia <- -27500

# Estructura que define los hiperparámetros y sus rangos
#  la letra L al final significa ENTERO
# max.depth 0 significa profundidad infinita
PARAM$hyperparametertuning$hs <- makeParamSet(
  makeIntegerParam("num.trees", lower = 20L, upper = 500L),
  makeIntegerParam("max.depth", lower = 1L, upper = 30L),
  makeIntegerParam("min.node.size", lower = 1L, upper = 1000L),
  makeIntegerParam("mtry", lower = 2L, upper = 50L)
)

# training
PARAM$train <- c(202104)

# graba a un archivo los componentes de lista
# para el primer registro, escribe antes los titulos

loguear <- function(
    reg, arch = NA, folder = "./work/",
    ext = ".txt", verbose = TRUE) {
  archivo <- arch
  if (is.na(arch)) archivo <- paste0(folder, substitute(reg), ext)

  if (!file.exists(archivo)) {
    # Escribo los titulos
    linea <- paste0(
      "fecha\t",
      paste(list.names(reg), collapse = "\t"), "\n"
    )

    cat(linea, file = archivo)
  }

  linea <- paste0(
    format(Sys.time(), "%Y%m%d %H%M%S"), "\t", # la fecha y hora
    gsub(", ", "\t", toString(reg)), "\n"
  )

  cat(linea, file = archivo, append = TRUE) # grabo al archivo

  if (verbose) cat(linea) # imprimo por pantalla
}

# particionar agrega una columna llamada fold a un dataset
#  que consiste en una particion estratificada segun agrupa
# particionar( data=dataset, division=c(70,30),
#  agrupa=clase_ternaria, seed=semilla)   crea una particion 70, 30
# particionar( data=dataset, division=c(1,1,1,1,1),
#   agrupa=clase_ternaria, seed=semilla)   divide el dataset en 5 particiones

particionar <- function(
    data, division, agrupa = "",
    campo = "fold", start = 1, seed = NA) {
  if (!is.na(seed)) set.seed(seed)

  bloque <- unlist(mapply(function(x, y) {
    rep(y, x)
  }, division, seq(from = start, length.out = length(division))))

  data[, (campo) := sample(rep(bloque, ceiling(.N / length(bloque))))[1:.N],
    by = agrupa
  ]
}

# es un paso del Cross Validation
# utiliza el fold  fold_test para testear y el resto para entrenar

ranger_Simple <- function(fold_test, pdata, param) {
  # genero el modelo

  set.seed(PARAM$semillas[2])

  modelo <- ranger(
    formula = "clase_binaria ~ .",
    data = pdata[fold != fold_test],
    probability = TRUE, # para que devuelva las probabilidades
    num.trees = param$num.trees,
    mtry = param$mtry,
    min.node.size = param$min.node.size,
    max.depth = param$max.depth
  )

  prediccion <- predict(modelo, pdata[fold == fold_test])

  ganancia_testing <- pdata[
    fold == fold_test,
    sum((prediccion$predictions[, "POS"] > 1 / 40) *
      ifelse(clase_binaria == "POS",
        PARAM$hyperparametertuning$POS_ganancia,
        PARAM$hyperparametertuning$NEG_ganancia
      ))
  ]

  return(ganancia_testing)
}

# realiza Cross Validation, promediando las ganancias de los folds de testing

ranger_CrossValidation <- function(
    data, param,
    pcampos_buenos, qfolds, pagrupa, semilla) {
  divi <- rep(1, qfolds)
  particionar(data, divi, seed = semilla, agrupa = pagrupa)

  ganancias <- mcmapply(ranger_Simple,
    seq(qfolds), # 1 2 3 4 5
    MoreArgs = list(data, param),
    SIMPLIFY = FALSE,
    mc.cores = 1
  ) # dejar esto en  1, porque ranger ya corre en paralelo

  data[, fold := NULL] # elimino el campo fold

  # devuelvo la ganancia promedio normalizada
  ganancia_promedio <- mean(unlist(ganancias))
  ganancia_promedio_normalizada <- ganancia_promedio * qfolds

  return(ganancia_promedio_normalizada)
}

# esta funcion solo puede recibir los parametros que se estan optimizando
# el resto de los parametros se pasan como variables globales

EstimarGanancia_ranger <- function(x) {
  GLOBAL_iteracion <<- GLOBAL_iteracion + 1

  xval_folds <- PARAM$hyperparametertuning$xval_folds

  ganancia <- ranger_CrossValidation(dataset,
    param = x,
    qfolds = xval_folds,
    pagrupa = "clase_binaria",
    semilla = PARAM$semillas[1]
  )

  # logueo
  xx <- x
  xx$xval_folds <- xval_folds
  xx$ganancia <- ganancia
  xx$iteracion <- GLOBAL_iteracion
  loguear(xx, arch = klog)

  # si es ganancia superadora la almaceno en mejor
  if (ganancia > GLOBAL_mejor) {
    GLOBAL_mejor <<- ganancia
    loguear(xx, arch = klog_mejor)
  }

  return(ganancia)
}

HT_DIR <- file.path(RESULTADOS_DIR, paste0("HT", PARAM$experimento))
dir.create(HT_DIR, recursive = TRUE, showWarnings = FALSE)

# genero numeros primos
primos <- generate_primes(min = 100000, max = 1000000)
set.seed(PARAM$semilla_primigenia) # inicializo
# me quedo con PARAM$qsemillas   semillas
PARAM$semillas <- sample(primos, 2)

# lectura del dataset
dataset <- fread(file.path(DATA_DIR, "competencia_01.csv.gz"))

# solo trabajo con  training
dataset <- dataset[foto_mes %in% PARAM$train]

#  estas dos lineas estan relacionadas con el Data Drifting
# asigno un valor muy negativo

if ("Master_Finiciomora" %in% colnames(dataset)) {
  dataset[is.na(Master_Finiciomora), Master_Finiciomora := -999]
}

if ("Visa_Finiciomora" %in% colnames(dataset)) {
  dataset[is.na(Visa_Finiciomora), Visa_Finiciomora := -999]
}

set.seed(PARAM$semilla_primigenia, "L'Ecuyer-CMRG") # Establezco la semilla aleatoria

# en estos archivos quedan los resultados
kbayesiana <- file.path(HT_DIR, paste0("HT", PARAM$experimento, ".RDATA"))
klog <- file.path(HT_DIR, paste0("HT", PARAM$experimento, ".txt"))
klog_mejor <- file.path(HT_DIR, paste0("HT", PARAM$experimento, "_mejor.txt"))

GLOBAL_iteracion <- 0 # inicializo la variable global
GLOBAL_mejor <- -Inf

# si ya existe el archivo log, traigo hasta donde llegue
if (file.exists(klog)) {
  tabla_log <- fread(klog)
  GLOBAL_iteracion <- nrow(tabla_log)
}

# paso a trabajar con clase binaria POS={BAJA+2}   NEG={BAJA+1, CONTINUA}
dataset[, clase_binaria :=
  as.factor(ifelse(clase_ternaria == "BAJA+2", "POS", "NEG"))]

dataset[, clase_ternaria := NULL] # elimino la clase_ternaria, ya no la necesito

# Ranger NO acepta valores nulos
# Leo Breiman, ¿por que le temias a los nulos?
# imputo los nulos, ya que ranger no acepta nulos

dataset <- na.roughfix(dataset)

# Aqui comienza la configuracion de la Bayesian Optimization

configureMlr(show.learner.output = FALSE)

funcion_optimizar <- EstimarGanancia_ranger

# configuro la busqueda bayesiana,  los hiperparametros que se van a optimizar
# por favor, no desesperarse por lo complejo
obj.fun <- makeSingleObjectiveFunction(
  fn = funcion_optimizar,
  minimize = FALSE, # estoy Maximizando la ganancia
  noisy = TRUE,
  par.set = PARAM$hyperparametertuning$hs,
  has.simple.signature = FALSE
)

ctrl <- makeMBOControl(save.on.disk.at.time = 600, save.file.path = kbayesiana)

ctrl <- setMBOControlTermination(
  ctrl,
  iters = PARAM$hyperparametertuning$iteraciones
)

ctrl <- setMBOControlInfill(ctrl, crit = makeMBOInfillCritEI())

surr.km <- makeLearner(
  "regr.km",
  predict.type = "se",
  covtype = "matern3_2",
  control = list(trace = TRUE)
)

# inicio la optimizacion bayesiana

if (!file.exists(kbayesiana)) {
  run <- mbo(obj.fun, learner = surr.km, control = ctrl)
} else {
  run <- mboContinue(kbayesiana)
} # retomo en caso que ya exista

# analizo la salida de la bayesiana

tb_bayesiana <- fread(klog)
setorder(tb_bayesiana, -ganancia)
print(tb_bayesiana)

# mejores parametros

print(tb_bayesiana[1])

# LightGBM — optimizacion bayesiana de hiperparametros (experimento HT4080). Seccion 4.08.

require("here")
here::i_am("juara/jueves/z470/00/2_bayesiana_lightgbm.R")
DATA_DIR <- here("juara", "data")
RESULTADOS_DIR <- here("juara", "jueves", "z470", "00", "resultados")
dir.create(RESULTADOS_DIR, recursive = TRUE, showWarnings = FALSE)

# cargo las librerias que necesito
require("data.table")

if (!require("lightgbm")) install.packages("lightgbm")
require("lightgbm")

if (!require("DiceKriging")) install.packages("DiceKriging")
require("DiceKriging")

if (!require("mlrMBO")) install.packages("mlrMBO")
require("mlrMBO")

# Aqui debe cargar SU semilla primigenia

PARAM <- list()
PARAM$experimento <- 4080
PARAM$semilla_primigenia <- 290497

# training y future
PARAM$train <- c(202104)

# un undersampling de 0.1  toma solo el 10% de los CONTINUA
# undersampling de 1.0  implica tomar TODOS los datos
PARAM$trainingstrategy$undersampling <- 1.0

PARAM$hyperparametertuning$iteraciones <- 30 # iteracines bayesianas

PARAM$hyperparametertuning$xval_folds <- 5

# parametros fijos del LightGBM
PARAM$lgbm$param_fijos <- list(
  objective = "binary",
  metric = "auc",
  first_metric_only = TRUE,
  boost_from_average = TRUE,
  feature_pre_filter = FALSE,
  verbosity = -100,
  force_row_wise = TRUE, # para evitar warning
  seed = PARAM$semilla_primigenia,
  max_bin = 31,
  num_iterations = 2048, # valor grande, lo limita early_stopping_rounds
  early_stopping_rounds = 200
)

# Aqui se cargan los bordes de los hiperparametros
PARAM$hypeparametertuning$hs <- makeParamSet(
  makeNumericParam("learning_rate", lower = 0.01, upper = 0.3),
  makeNumericParam("feature_fraction", lower = 0.1, upper = 1.0),
  makeIntegerParam("num_leaves", lower = 8L, upper = 2048L),
  makeIntegerParam("min_data_in_leaf", lower = 1L, upper = 8000L)
)

# En el argumento x llegan los parmaetros de la bayesiana
#  devuelve la AUC de cross validation del modelo entrenado

EstimarGanancia_AUC_lightgbm <- function(x) {

  message(format(Sys.time(), "%a %b %d %X %Y"))

  # uno la lista de hiperparametros : fijos + variables
  param_completo <- c(PARAM$lgbm$param_fijos, x)

  # entreno LightGBM
  modelocv <- lgb.cv(
    data = dtrain,
    nfold = PARAM$hyperparametertuning$xval_folds,
    stratified = TRUE,
    param = param_completo,
    verbose = -100
  )

  # obtengo la ganancia
  AUC <- modelocv$best_score

  # esta es la forma de devolver un parametro extra
  attr(AUC, "extras") <- list("num_iterations" = modelocv$best_iter)

  # hago espacio en la memoria
  rm(modelocv)
  gc(full = TRUE, verbose = FALSE)

  message("AUC: ", AUC)
  return(AUC)
}

# carpeta de trabajo

HT_DIR <- file.path(RESULTADOS_DIR, paste0("HT", PARAM$experimento))
dir.create(HT_DIR, recursive = TRUE, showWarnings = FALSE)

# en este archivo quedan la evolucion binaria de la BO

kbayesiana <- file.path(HT_DIR, "bayesiana.RDATA")

# lectura del dataset
dataset <- fread(
  file.path(DATA_DIR, "competencia_01.csv.gz"),
  stringsAsFactors = TRUE
)

dataset <- dataset[foto_mes %in% PARAM$train]

# paso la clase a binaria que tome valores {0,1}  enteros

dataset[, clase01 := ifelse(clase_ternaria == "BAJA+2", 1L, 0L)]

# los campos que se van a utilizar

campos_buenos <- copy(setdiff(
  colnames(dataset),
  c("clase_ternaria", "clase01", "azar", "training")
))

# defino los datos que forma parte del training
# aqui se hace el undersampling de los CONTINUA
# notar que para esto utilizo la SEGUNDA semilla

set.seed(PARAM$semilla_primigenia, kind = "L'Ecuyer-CMRG")
dataset[, azar := runif(nrow(dataset))]
dataset[, training := 0L]

dataset[
  foto_mes %in% PARAM$train &
    (azar <= PARAM$trainingstrategy$undersampling | clase_ternaria %in% c("BAJA+1", "BAJA+2")),
  training := 1L
]

# dejo los datos en el formato que necesita LightGBM

dtrain <- lgb.Dataset(
  data = data.matrix(dataset[training == 1L, campos_buenos, with = FALSE]),
  label = dataset[training == 1L, clase01],
  free_raw_data = FALSE
)

# Aqui comienza la configuracion de la Bayesian Optimization

funcion_optimizar <- EstimarGanancia_AUC_lightgbm # la funcion que voy a maximizar

configureMlr(show.learner.output = FALSE)

# configuro la busqueda bayesiana,  los hiperparametros que se van a optimizar
# por favor, no desesperarse por lo complejo

obj.fun <- makeSingleObjectiveFunction(
  fn = funcion_optimizar, # la funcion que voy a maximizar
  minimize = FALSE, # estoy Maximizando la ganancia
  noisy = TRUE,
  par.set = PARAM$hypeparametertuning$hs, # definido al comienzo del programa
  has.simple.signature = FALSE # paso los parametros en una lista
)

# cada 600 segundos guardo el resultado intermedio
ctrl <- makeMBOControl(
  save.on.disk.at.time = 600, # se graba cada 600 segundos
  save.file.path = kbayesiana
) # se graba cada 600 segundos

# indico la cantidad de iteraciones que va a tener la Bayesian Optimization
ctrl <- setMBOControlTermination(
  ctrl,
  iters = PARAM$hyperparametertuning$iteraciones
) # cantidad de iteraciones

# defino el método estandar para la creacion de los puntos iniciales,
# los "No Inteligentes"
ctrl <- setMBOControlInfill(ctrl, crit = makeMBOInfillCritEI())

# establezco la funcion que busca el maximo
surr.km <- makeLearner(
  "regr.km",
  predict.type = "se",
  covtype = "matern3_2",
  control = list(trace = TRUE)
)

# inicio la optimizacion bayesiana, retomando si ya existe

if (!file.exists(kbayesiana)) {
  bayesiana_salida <- mbo(obj.fun, learner = surr.km, control = ctrl)
} else {
  bayesiana_salida <- mboContinue(kbayesiana) # retomo en caso que ya exista
}

# almaceno los resultados de la Bayesian Optimization
# y capturo los mejores hiperparametros encontrados

tb_bayesiana <- as.data.table(bayesiana_salida$opt.path)

tb_bayesiana[, iter := .I]
# ordeno en forma descendente por AUC = y
setorder(tb_bayesiana, -y, -num_iterations)

# grabo para eventualmente poder utilizarlos en OTRA corrida
fwrite(tb_bayesiana,
  file = file.path(HT_DIR, "BO_log.txt"),
  sep = "\t"
)

# los mejores hiperparámetros son los que quedaron en el registro 1 de la tabla
PARAM$out$lgbm$mejores_hiperparametros <- tb_bayesiana[
  1, # el primero es el de mejor AUC
  list(learning_rate, feature_fraction, num_leaves, min_data_in_leaf, num_iterations)
]

print(PARAM$out$lgbm$mejores_hiperparametros)

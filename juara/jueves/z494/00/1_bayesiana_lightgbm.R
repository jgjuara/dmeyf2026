# Bayesian Optimization de hiperparametros LightGBM (experimento HT4940).
#
# Asume juara/data/competencia_01.csv.gz (generar_clase_ternaria.R).
# Escribe bayesiana.RDATA, BO_log.txt y PARAM.yml en 00/resultados/HT4940/.

require("here")
here::i_am("juara/jueves/z494/00/1_bayesiana_lightgbm.R")
DATA_DIR <- here("juara", "data")
RESULTADOS_DIR <- here("juara", "jueves", "z494", "00", "resultados")

dir.create(RESULTADOS_DIR, recursive = TRUE, showWarnings = FALSE)

# cargo las librerias que necesito
require("data.table")

if (!require("yaml")) install.packages("yaml")
require("yaml")

if (!require("lightgbm")) install.packages("lightgbm")
require("lightgbm")

if (!require("DiceKriging")) install.packages("DiceKriging")
require("DiceKriging")

if (!require("mlrMBO")) install.packages("mlrMBO")
require("mlrMBO")

PARAM <- list()
PARAM$experimento <- 4940
PARAM$semilla_primigenia <- 427417

# training y future
PARAM$train <- c(202104)
PARAM$train_final <- c(202104)
PARAM$future <- c(202106)
PARAM$semilla_kaggle <- 314159
PARAM$cortes <- seq(4000, 19000, by = 500)

# un undersampling de 0.1  toma solo el 10% de los CONTINUA
# undersampling de 1.0  implica tomar TODOS los datos

PARAM$trainingstrategy$undersampling <- 0.1

# Parametros LightGBM

PARAM$hyperparametertuning$xval_folds <- 5

# parametros fijos del LightGBM que se pisaran con la parte variable de la BO
PARAM$lgbm$param_fijos <- list(
  boosting = "gbdt", # puede ir  dart  , ni pruebe random_forest
  objective = "binary",
  metric = "auc",
  first_metric_only = FALSE,
  boost_from_average = TRUE,
  feature_pre_filter = FALSE,
  force_row_wise = TRUE, # para reducir warnings
  verbosity = -100,

  seed = PARAM$semilla_primigenia,

  max_depth = -1L, # -1 significa no limitar,  por ahora lo dejo fijo
  min_gain_to_split = 0, # min_gain_to_split >= 0
  min_sum_hessian_in_leaf = 0.001, #  min_sum_hessian_in_leaf >= 0.0
  lambda_l1 = 0.0, # lambda_l1 >= 0.0
  lambda_l2 = 0.0, # lambda_l2 >= 0.0
  max_bin = 31L, # lo debo dejar fijo, no participa de la BO

  bagging_fraction = 1.0, # 0.0 < bagging_fraction <= 1.0
  pos_bagging_fraction = 1.0, # 0.0 < pos_bagging_fraction <= 1.0
  neg_bagging_fraction = 1.0, # 0.0 < neg_bagging_fraction <= 1.0
  is_unbalance = FALSE, #
  scale_pos_weight = 1.0, # scale_pos_weight > 0.0

  drop_rate = 0.1, # 0.0 < neg_bagging_fraction <= 1.0
  max_drop = 50, # <=0 means no limit
  skip_drop = 0.5, # 0.0 <= skip_drop <= 1.0

  extra_trees = FALSE,

  num_iterations = 1200,
  learning_rate = 0.02,
  feature_fraction = 0.5,
  num_leaves = 750,
  min_data_in_leaf = 5000
)

# Aqui se cargan los bordes de los hiperparametros de la BO
PARAM$hypeparametertuning$hs <- makeParamSet(
  makeIntegerParam("num_iterations", lower = 8L, upper = 2048L),
  makeNumericParam("learning_rate", lower = 0.01, upper = 0.3),
  makeNumericParam("feature_fraction", lower = 0.1, upper = 1.0),
  makeIntegerParam("num_leaves", lower = 8L, upper = 2048L),
  makeIntegerParam("min_data_in_leaf", lower = 1L, upper = 8000L)
)

PARAM$hyperparametertuning$iteraciones <- 30 # iteraciones bayesianas

HT_DIR <- file.path(RESULTADOS_DIR, paste0("HT", PARAM$experimento))
dir.create(HT_DIR, recursive = TRUE, showWarnings = FALSE)

# lectura del dataset
dataset <- fread(
  file.path(DATA_DIR, "competencia_01.csv.gz"),
  stringsAsFactors = TRUE
)

dataset_train <- dataset[foto_mes %in% PARAM$train]

# paso la clase a binaria que tome valores {0,1}  enteros
#  BAJA+1 y BAJA+2  son  1,   CONTINUA es 0
#  a partir de ahora ya NO puedo cortar  por prob(BAJA+2) > 1/40

dataset_train[,
  clase01 := ifelse(clase_ternaria %in% c("BAJA+2", "BAJA+1"), 1L, 0L)
]

# defino los datos que forma parte del training
# aqui se hace el undersampling de los CONTINUA
# notar que para esto utilizo la SEGUNDA semilla

set.seed(PARAM$semilla_primigenia, kind = "L'Ecuyer-CMRG")
dataset_train[, azar := runif(nrow(dataset_train))]
dataset_train[, training := 0L]

dataset_train[
  foto_mes %in% PARAM$train &
    (azar <= PARAM$trainingstrategy$undersampling | clase_ternaria %in% c("BAJA+1", "BAJA+2")),
  training := 1L
]

# los campos que se van a utilizar

campos_buenos <- setdiff(
  colnames(dataset_train),
  c("clase_ternaria", "clase01", "azar", "training")
)

# dejo los datos en el formato que necesita LightGBM

dtrain <- lgb.Dataset(
  data = data.matrix(dataset_train[training == 1L, campos_buenos, with = FALSE]),
  label = dataset_train[training == 1L, clase01],
  free_raw_data = FALSE
)

# En el argumento x llegan los parmaetros de la bayesiana
#  devuelve la AUC en cross validation del modelo entrenado

EstimarGanancia_AUC_lightgbm <- function(x) {

  # x pisa (o agrega) a param_fijos
  param_completo <- modifyList(PARAM$lgbm$param_fijos, x)

  # entreno LightGBM
  modelocv <- lgb.cv(
    data = dtrain,
    nfold = PARAM$hyperparametertuning$xval_folds,
    stratified = TRUE,
    param = param_completo
  )

  # obtengo la ganancia
  AUC <- modelocv$best_score

  # hago espacio en la memoria
  rm(modelocv)
  gc(full = TRUE, verbose = FALSE)

  message(format(Sys.time(), "%a %b %d %X %Y"), " AUC ", AUC)

  return(AUC)
}

# Aqui comienza la configuracion de la Bayesian Optimization

# en este archivo quedan la evolucion binaria de la BO
kbayesiana <- file.path(HT_DIR, "bayesiana.RDATA")

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
# es la celda mas lenta de todo el notebook

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
setorder(tb_bayesiana, -y)

# grabo para eventualmente poder utilizarlos en OTRA corrida
fwrite(
  tb_bayesiana,
  file = file.path(HT_DIR, "BO_log.txt"),
  sep = "\t"
)

# los mejores hiperparámetros son los que quedaron en el registro 1 de la tabla
PARAM$out$lgbm$mejores_hiperparametros <- tb_bayesiana[
  1, # el primero es el de mejor AUC
  setdiff(
    colnames(tb_bayesiana),
    c(
      "y", "dob", "eol", "error.message", "exec.time", "ei", "error.model",
      "train.time", "prop.type", "propose.time", "se", "mean", "iter"
    )
  ),
  with = FALSE
]

PARAM$out$lgbm$y <- tb_bayesiana[1, y]

PARAM$campos_buenos <- campos_buenos

write_yaml(PARAM, file = file.path(HT_DIR, "PARAM.yml"))

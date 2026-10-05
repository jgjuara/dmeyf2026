# Bayesian Optimization LightGBM — CV AUC en el 70% dev (experimento HT2103, 03_rank_nocont_lag1_delta1).
# min_sum_hessian_in_leaf se optimiza linealmente en [0.001, 0.01] (no log10).
#
# Split 70/30: BO y train final en fold_train; test producción en fold_test (30%, no usado en BO).
# BO: undersampling 10% CONTINUA solo en dev; lgb.cv con 2 folds estratificados.
# Escribe bayesiana.RDATA, BO_log.txt y PARAM.yml en 00/resultados/HT2103/.

require("here")
here::i_am("juara/compe1/03_rank_nocont_lag1_delta1/00/1_bayesiana_lightgbm.R")
source(here("juara", "compe1", "common", "compe1_layers.R"))
source(here("juara", "compe1", "common", "compe1_data.R"))

EXPERIMENT_ID <- "03_rank_nocont_lag1_delta1"
RESULTADOS_DIR <- compe1_resultados_dir(EXPERIMENT_ID)
EXPERIMENTO <- 2103L
HT_DIR <- file.path(RESULTADOS_DIR, paste0("HT", EXPERIMENTO))

dir.create(RESULTADOS_DIR, recursive = TRUE, showWarnings = FALSE)
dir.create(HT_DIR, recursive = TRUE, showWarnings = FALSE)

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
PARAM$experimento <- EXPERIMENTO
PARAM$experiment_id <- EXPERIMENT_ID
PARAM$semilla_primigenia <- 427417

set.seed(PARAM$semilla_primigenia)

PARAM$foto_mes <- c(202103L, 202104L, 202105L, 202106L)
PARAM$cortes <- seq(4000, 19000, by = 500)

PARAM$trainingstrategy$undersampling <- 0.1

PARAM$holdout$division <- c(70L, 30L)
PARAM$holdout$fold_train <- 1L
PARAM$holdout$fold_test <- 2L
PARAM$holdout$agrupa <- COMPE1_PARTICION_AGRUPA

PARAM$lgbm$param_fijos <- list(
  boosting = "gbdt",
  objective = "binary",
  metric = "auc",
  first_metric_only = FALSE,
  boost_from_average = TRUE,
  feature_pre_filter = FALSE,
  force_row_wise = TRUE,
  verbosity = -100,

  seed = PARAM$semilla_primigenia,

  max_depth = -1L,
  min_gain_to_split = 0,
  min_sum_hessian_in_leaf = 0.001,
  lambda_l1 = 0.0,
  lambda_l2 = 0.0,
  max_bin = 31L,

  bagging_fraction = 1.0,
  pos_bagging_fraction = 1.0,
  neg_bagging_fraction = 1.0,
  is_unbalance = FALSE,
  scale_pos_weight = 1.0,

  extra_trees = FALSE,

  num_iterations = 1200,
  learning_rate = 0.009,
  feature_fraction = 0.5,
  num_leaves = 750,
  min_data_in_leaf = 5000
)

MIN_SUM_HESSIAN_LO <- 0.001
MIN_SUM_HESSIAN_HI <- 0.01

PARAM$hypeparametertuning$hs <- makeParamSet(
  makeIntegerParam("num_iterations", lower = 2000L, upper = 8000L),
  makeIntegerParam("num_leaves", lower = 10, upper = 400L),
  makeIntegerParam("min_data_in_leaf", lower = 50L, upper = 500L),
  makeNumericParam(
    "min_sum_hessian_in_leaf",
    lower = MIN_SUM_HESSIAN_LO,
    upper = MIN_SUM_HESSIAN_HI
  )
)

PARAM$hypeparametertuning$limites_fisicos <- list(
  min_sum_hessian_in_leaf = list(
    lower = MIN_SUM_HESSIAN_LO,
    upper = MIN_SUM_HESSIAN_HI
  )
)

PARAM$hyperparametertuning$xval_folds <- 2L
PARAM$hyperparametertuning$iteraciones <- as.integer(
  Sys.getenv("COMPE1_BO_ITER", unset = "500")
)
PARAM$hyperparametertuning$objetivo <- "cv_auc"

dataset <- compe1_read_joined(EXPERIMENT_ID, foto_mes = PARAM$foto_mes)

dataset[, clase01 := ifelse(clase_ternaria %in% c("BAJA+2", "BAJA+1"), 1L, 0L)]

particionar(
  dataset,
  division = PARAM$holdout$division,
  agrupa = PARAM$holdout$agrupa,
  seed = PARAM$semilla_primigenia
)

fold_train <- PARAM$holdout$fold_train
fold_test <- PARAM$holdout$fold_test

PARAM$holdout$n_train <- nrow(dataset[fold == fold_train])
PARAM$holdout$n_test <- nrow(dataset[fold == fold_test])

compe1_aplicar_undersampling_train(
  dataset,
  fold_train = fold_train,
  undersampling = PARAM$trainingstrategy$undersampling,
  seed = PARAM$semilla_primigenia
)

campos_buenos <- compe1_campos_buenos(dataset)

train_bo <- dataset[fold == fold_train & training == 1L]

dtrain <- lgb.Dataset(
  data = data.matrix(train_bo[, campos_buenos, with = FALSE]),
  label = train_bo$clase01,
  free_raw_data = FALSE
)

BO_eval_idx <- 0L
BO_mejor_auc <- -Inf

EstimarGanancia_AUC_lightgbm <- function(x) {

  BO_eval_idx <<- BO_eval_idx + 1L

  param_completo <- modifyList(PARAM$lgbm$param_fijos, x)
  nfold <- PARAM$hyperparametertuning$xval_folds

  cat(
    sprintf(
      "[%s] eval #%d — lgb.cv nfold=%d (pool dev 70%%) ...\n",
      format(Sys.time(), "%H:%M:%S"),
      BO_eval_idx,
      nfold
    )
  )
  flush.console()

  AUC <- compe1_lgb_cv_best_auc(dtrain, param_completo, nfold = nfold)
  if (AUC > BO_mejor_auc) {
    BO_mejor_auc <<- AUC
  }

  gc(full = TRUE, verbose = FALSE)

  cat(
    sprintf(
      paste0(
        "[%s] eval #%d | AUC=%.6f | mejor=%.6f | ",
        "num_iterations=%d lr=%.4g ff=%.4g num_leaves=%d min_data_in_leaf=%d ",
        "min_sum_hessian=%.4g\n"
      ),
      format(Sys.time(), "%H:%M:%S"),
      BO_eval_idx,
      AUC,
      BO_mejor_auc,
      as.integer(x$num_iterations),
      as.numeric(x$learning_rate),
      as.numeric(x$feature_fraction),
      as.integer(x$num_leaves),
      as.integer(x$min_data_in_leaf),
      as.numeric(x$min_sum_hessian_in_leaf)
    )
  )
  flush.console()

  AUC
}

kbayesiana <- file.path(HT_DIR, "bayesiana.RDATA")
funcion_optimizar <- EstimarGanancia_AUC_lightgbm

configureMlr(show.learner.output = FALSE)

obj.fun <- makeSingleObjectiveFunction(
  fn = funcion_optimizar,
  minimize = FALSE,
  noisy = TRUE,
  par.set = PARAM$hypeparametertuning$hs,
  has.simple.signature = FALSE
)

ctrl <- makeMBOControl(
  save.on.disk.at.time = 600,
  save.file.path = kbayesiana
)
ctrl <- setMBOControlTermination(ctrl, iters = PARAM$hyperparametertuning$iteraciones)
ctrl <- setMBOControlInfill(ctrl, crit = makeMBOInfillCritEI())

surr.km <- makeLearner(
  "regr.km",
  predict.type = "se",
  covtype = "matern3_2",
  control = list(trace = TRUE)
)

options(mlrMBO.show.info = TRUE)

cat(
  "\n=== Bayesian Optimization HT", EXPERIMENTO, "===\n",
  "Objetivo: ", PARAM$hyperparametertuning$objetivo,
  " (nfold=", PARAM$hyperparametertuning$xval_folds, " en 70% dev)\n",
  "Iteraciones MBO (infill): ", PARAM$hyperparametertuning$iteraciones, "\n",
  "Checkpoint: ", kbayesiana, "\n",
  sep = ""
)
if (file.exists(kbayesiana)) {
  cat("Modo: mboContinue (retomar corrida existente)\n\n")
} else {
  cat("Modo: mbo (corrida nueva)\n\n")
}
flush.console()

if (!file.exists(kbayesiana)) {
  bayesiana_salida <- mbo(
    obj.fun,
    learner = surr.km,
    control = ctrl,
    show.info = TRUE
  )
} else {
  bayesiana_salida <- mboContinue(kbayesiana, show.info = TRUE)
}

cat(
  "\n=== BO finalizada ===\n",
  "Evaluaciones en esta sesion: ", BO_eval_idx, "\n",
  "Mejor AUC (sesion): ", BO_mejor_auc, "\n\n",
  sep = ""
)
flush.console()

tb_bayesiana <- as.data.table(bayesiana_salida$opt.path)
tb_bayesiana[, iter := .I]
setorder(tb_bayesiana, -y)

fwrite(
  tb_bayesiana,
  file = file.path(HT_DIR, "BO_log.txt"),
  sep = "\t"
)

PARAM$out$lgbm$mejores_hiperparametros <- tb_bayesiana[
  1,
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

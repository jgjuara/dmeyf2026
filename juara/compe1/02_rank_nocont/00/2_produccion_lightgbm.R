# Entrenamiento final LightGBM y evaluación en test producción 30% (exp2102, 02_rank_nocont).
#
# Requiere HT2102/PARAM.yml (1_bayesiana_lightgbm.R). El 30% no participó de la BO
# (hiperparámetros con CV 2 folds solo en el 70% undersampled). Train: todo el 70%
# sin undersampling; min_data_in_leaf reescalado / undersampling; test: fold_test (30%).

require("here")
here::i_am("juara/compe1/02_rank_nocont/00/2_produccion_lightgbm.R")
source(here("juara", "compe1", "common", "compe1_layers.R"))
source(here("juara", "compe1", "common", "compe1_data.R"))

EXPERIMENT_ID <- "02_rank_nocont"
RESULTADOS_DIR <- compe1_resultados_dir(EXPERIMENT_ID)
EXPERIMENTO <- 2102L
HT_DIR <- file.path(RESULTADOS_DIR, paste0("HT", EXPERIMENTO))
PROD_DIR <- file.path(RESULTADOS_DIR, paste0("exp", EXPERIMENTO))

dir.create(RESULTADOS_DIR, recursive = TRUE, showWarnings = FALSE)
dir.create(PROD_DIR, recursive = TRUE, showWarnings = FALSE)

require("data.table")

if (!require("yaml")) install.packages("yaml")
require("yaml")

if (!require("lightgbm")) install.packages("lightgbm")
require("lightgbm")

if (!require("ggplot2")) install.packages("ggplot2")
require("ggplot2")

PARAM <- read_yaml(file.path(HT_DIR, "PARAM.yml"))
campos_buenos <- unlist(PARAM$campos_buenos)

fold_train <- as.integer(PARAM$holdout$fold_train)
fold_test <- as.integer(PARAM$holdout$fold_test)

dataset <- compe1_read_joined(EXPERIMENT_ID, foto_mes = unlist(PARAM$foto_mes))

dataset[, clase01 := ifelse(clase_ternaria %in% c("BAJA+1", "BAJA+2"), 1L, 0L)]

agrupa_holdout <- PARAM$holdout$agrupa
if (is.null(agrupa_holdout)) {
  agrupa_holdout <- COMPE1_PARTICION_AGRUPA
}

particionar(
  dataset,
  division = unlist(PARAM$holdout$division),
  agrupa = unlist(agrupa_holdout),
  seed = PARAM$semilla_primigenia
)

dataset_train <- dataset[fold == fold_train]

dtrain_final <- lgb.Dataset(
  data = data.matrix(dataset_train[, campos_buenos, with = FALSE]),
  label = dataset_train$clase01
)

param_final <- modifyList(
  PARAM$lgbm$param_fijos,
  PARAM$out$lgbm$mejores_hiperparametros
)
param_final <- compe1_decodificar_min_sum_hessian(param_final, PARAM)

param_normalizado <- copy(param_final)
param_normalizado$min_data_in_leaf <- round(
  param_final$min_data_in_leaf / PARAM$trainingstrategy$undersampling
)

modelo_final <- lgb.train(
  data = dtrain_final,
  param = param_normalizado
)

tb_importancia <- as.data.table(lgb.importance(modelo_final))
fwrite(tb_importancia, file = file.path(PROD_DIR, "impo.txt"), sep = "\t")

lgb.save(modelo_final, file.path(PROD_DIR, "modelo.txt"))

dataset_test <- dataset[fold == fold_test]

prediccion <- predict(
  modelo_final,
  data.matrix(dataset_test[, campos_buenos, with = FALSE])
)

tb_prediccion <- dataset_test[, list(numero_de_cliente, foto_mes, clase_ternaria)]
tb_prediccion[, prob := prediccion]

fwrite(
  tb_prediccion[, list(numero_de_cliente, foto_mes, prob)],
  file = file.path(PROD_DIR, "prediccion.txt"),
  sep = "\t"
)

setorder(tb_prediccion, -prob)
tb_prediccion[, gan := ifelse(clase_ternaria == "BAJA+2", 1072500, -27500)]
tb_prediccion[, ganancia_acumulada := cumsum(gan)]
tb_prediccion[, pos := seq_len(.N)]

amostrar <- 30000L
gra <- ggplot(
  data = tb_prediccion[pos <= amostrar],
  aes(x = pos, y = ganancia_acumulada)
) + geom_line()
gra <- gra + theme(text = element_text(size = 16))

ggsave(
  filename = file.path(PROD_DIR, "curva_ganancia.pdf"),
  plot = gra,
  width = 16,
  height = 9
)

setorder(tb_prediccion, -prob)

sink(file.path(PROD_DIR, "cortes_ganancia.txt"))
for (envios in unlist(PARAM$cortes)) {
  tb_prediccion[, Predicted := 0L]
  n_env <- min(as.integer(envios), nrow(tb_prediccion))
  if (n_env > 0L) {
    tb_prediccion[seq_len(n_env), Predicted := 1L]
  }
  total <- tb_prediccion[
    Predicted == 1L,
    sum(ifelse(clase_ternaria == "BAJA+2", 1072500, -27500))
  ]
  options(scipen = 999)
  cat("Envios=", envios, "\t", " TOTAL=", total, "\n", sep = "")
}
sink()

write_yaml(PARAM, file = file.path(PROD_DIR, "PARAM.yml"))

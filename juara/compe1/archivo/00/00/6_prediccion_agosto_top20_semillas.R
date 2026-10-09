# HP top-20 BO x semillas-primo: train mar-jun completo, predict foto_mes agosto (exp1990_agosto).
#
# Promedia prob sobre (rank x semilla) configurados y escribe ranking por prob descendente.
# Una prediccion por par rank x semilla: modelo_XX_<semilla>_<aniomesdia>.tsv (dia=01 del foto_mes).
# Requiere HT1990/PARAM.yml y top20_hiperparametros.tsv o BO_log.txt (4_ o 1_).

require("here")
here::i_am("juara/compe1/00/00/6_prediccion_agosto_top20_semillas.R")
source(here("juara", "compe1", "common", "compe1_layers.R"))
source(here("juara", "compe1", "common", "compe1_data.R"))

EXPERIMENT_ID <- "00"
RESULTADOS_DIR <- compe1_resultados_dir(EXPERIMENT_ID)
EXPERIMENTO <- 1990L
N_SEMILLAS_PRIMOS <- 10L

# Ranks BO a usar (indice en top20_hiperparametros / BO_log); varios ranks -> media conjunta.
RANKS_BO <- 3L

FOTO_MES_TRAIN <- COMPE1_FOTO_MES_MAR_JUN
FOTO_MES_PRED <- 202108L

HT_DIR <- file.path(RESULTADOS_DIR, paste0("HT", EXPERIMENTO))
TOP20_ESTUDIO_DIR <- file.path(RESULTADOS_DIR, "estudio", "top20_bo_semillas")
OUT_DIR <- file.path(RESULTADOS_DIR, paste0("exp", EXPERIMENTO, "_agosto"))

dir.create(OUT_DIR, recursive = TRUE, showWarnings = FALSE)

require("data.table")

if (!require("yaml")) install.packages("yaml")
require("yaml")

if (!require("lightgbm")) install.packages("lightgbm")
require("lightgbm")

PARAM <- read_yaml(file.path(HT_DIR, "PARAM.yml"))
campos_buenos <- unlist(PARAM$campos_buenos)

hiperparams <- c(
  "num_iterations",
  "num_leaves",
  "min_data_in_leaf",
  "min_sum_hessian_in_leaf"
)

TOP20_META <- file.path(TOP20_ESTUDIO_DIR, "top20_hiperparametros.tsv")
BO_LOG <- file.path(HT_DIR, "BO_log.txt")

if (file.exists(TOP20_META)) {
  tb_top20 <- fread(TOP20_META)
} else if (file.exists(BO_LOG)) {
  tb_top20 <- fread(BO_LOG)
  tb_top20 <- head(tb_top20, 20L)
  tb_top20[, rank := seq_len(.N)]
} else {
  stop("No existe ", TOP20_META, " ni ", BO_LOG, " — ejecutar 1_ o 4_ primero.")
}

faltantes <- setdiff(c("rank", hiperparams), colnames(tb_top20))
if (length(faltantes) > 0L) {
  stop("tabla top-20 sin columnas: ", paste(faltantes, collapse = ", "))
}

ranks_usar <- as.integer(RANKS_BO)
if (length(ranks_usar) == 0L) {
  stop("RANKS_BO vacio.")
}
if (any(!ranks_usar %in% tb_top20$rank)) {
  stop(
    "RANKS_BO fuera de rango: ",
    paste(setdiff(ranks_usar, tb_top20$rank), collapse = ", ")
  )
}

tb_ranks <- tb_top20[rank %in% ranks_usar]

semillas_train <- compe1_semillas_primos(N_SEMILLAS_PRIMOS, PARAM$semilla_primigenia)
cat("RANKS_BO:", paste(ranks_usar, collapse = ", "), "\n")
cat("semillas_train:", paste(semillas_train, collapse = ", "), "\n")

hp_de_fila <- function(fila) {
  as.list(fila[1L, ..hiperparams])
}

foto_mes_a_aniomesdia <- function(foto_mes) {
  fm <- as.integer(foto_mes)
  sprintf("%d%02d01", fm %/% 100L, fm %% 100L)
}

ANIOMESDIA_PRED <- foto_mes_a_aniomesdia(FOTO_MES_PRED)

nombre_tsv_modelo_semilla <- function(rank_id, semilla) {
  sprintf(
    "modelo_%02d_%d_%s.tsv",
    as.integer(rank_id),
    as.integer(semilla),
    ANIOMESDIA_PRED
  )
}

meses_leer <- unique(c(FOTO_MES_TRAIN, FOTO_MES_PRED))
dataset <- compe1_read_joined(EXPERIMENT_ID, foto_mes = meses_leer)

dataset_train <- dataset[foto_mes %in% FOTO_MES_TRAIN]
dataset_train[, clase01 := compe1_clase01(clase_ternaria)]

dataset_agosto <- dataset[foto_mes == FOTO_MES_PRED]
if (nrow(dataset_agosto) == 0L) {
  stop("Sin filas para foto_mes=", FOTO_MES_PRED)
}

n_train <- nrow(dataset_train)
n_agosto_rows <- nrow(dataset_agosto)
cat(
  "train filas=", n_train,
  " | agosto filas=", n_agosto_rows, "\n",
  sep = ""
)

dtrain_final <- lgb.Dataset(
  data = data.matrix(dataset_train[, campos_buenos, with = FALSE]),
  label = dataset_train$clase01
)

mat_agosto <- data.matrix(dataset_agosto[, campos_buenos, with = FALSE])
tb_agosto_ids <- dataset_agosto[, .(numero_de_cliente, foto_mes)]
n_agosto <- nrow(tb_agosto_ids)

rm(dataset, dataset_train)
gc(full = TRUE, verbose = FALSE)

prob_sum <- rep(0, n_agosto)
n_modelos <- 0L

for (k in seq_len(nrow(tb_ranks))) {
  fila <- tb_ranks[k]
  rank_id <- fila$rank[[1L]]
  param_hp <- hp_de_fila(fila)

  param_final <- modifyList(PARAM$lgbm$param_fijos, param_hp)
  param_final <- compe1_decodificar_min_sum_hessian(param_final, PARAM)

  cat("\n=== rank_", sprintf("%02d", rank_id), " ===\n", sep = "")

  for (primo in semillas_train) {
    param_normalizado <- copy(param_final)
    param_normalizado$min_data_in_leaf <- compe1_min_data_in_leaf_produccion(
      param_final,
      PARAM$trainingstrategy$undersampling
    )
    param_normalizado$seed <- primo

    modelo_final <- lgb.train(
      data = dtrain_final,
      param = param_normalizado
    )

    prediccion <- predict(modelo_final, mat_agosto)
    n_modelos <- n_modelos + 1L
    prob_sum <- prob_sum + prediccion

    tb_piece <- data.table(
      numero_de_cliente = tb_agosto_ids$numero_de_cliente,
      foto_mes = tb_agosto_ids$foto_mes,
      prob = prediccion
    )
    fwrite(
      tb_piece,
      file.path(OUT_DIR, nombre_tsv_modelo_semilla(rank_id, primo)),
      sep = "\t"
    )

    rm(modelo_final, prediccion, param_normalizado, tb_piece)
    gc(full = TRUE, verbose = FALSE)
  }

  rm(fila, param_hp, param_final)
  gc(full = TRUE, verbose = FALSE)
}

if (n_modelos != nrow(tb_ranks) * length(semillas_train)) {
  stop(
    "Conteo de modelos inconsistente: n_modelos=", n_modelos,
    " esperado=", nrow(tb_ranks) * length(semillas_train)
  )
}

rm(dtrain_final, mat_agosto, dataset_agosto)
gc(full = TRUE, verbose = FALSE)

tb_media <- data.table(
  numero_de_cliente = tb_agosto_ids$numero_de_cliente,
  foto_mes = tb_agosto_ids$foto_mes,
  prob = prob_sum / n_modelos
)
rm(prob_sum, tb_agosto_ids)
gc(full = TRUE, verbose = FALSE)
fwrite(
  tb_media,
  file.path(OUT_DIR, "prediccion_agosto_media.tsv"),
  sep = "\t"
)

tb_ordenada <- copy(tb_media)
setorder(tb_ordenada, -prob)
tb_ordenada[, orden := seq_len(.N)]

fwrite(
  tb_ordenada,
  file.path(OUT_DIR, "prediccion_agosto_media_ordenada.tsv"),
  sep = "\t"
)

meta <- list(
  experiment_id = EXPERIMENT_ID,
  experimento = EXPERIMENTO,
  ranks_bo = as.list(ranks_usar),
  n_semillas_primos = N_SEMILLAS_PRIMOS,
  semillas_train = as.list(semillas_train),
  foto_mes_train = as.list(FOTO_MES_TRAIN),
  foto_mes_pred = FOTO_MES_PRED,
  aniomesdia_pred = ANIOMESDIA_PRED,
  prediccion_tsv_patron = "modelo_%02d_<semilla>_<aniomesdia>.tsv",
  n_train = n_train,
  n_agosto = n_agosto_rows,
  n_predicciones_agregadas = nrow(tb_media)
)
write_yaml(meta, file.path(OUT_DIR, "meta.yml"))

cat("\nFinalizado en ", OUT_DIR, "\n", sep = "")

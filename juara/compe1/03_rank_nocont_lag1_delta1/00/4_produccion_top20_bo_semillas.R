# Top-20 hiperparametros BO x 10 semillas-primo (exp2103_top20).
#
# Lee las 20 mejores filas de BO_log.txt; entrena en 70% y evalua en holdout 30%.
# Por rank: 10 modelos (semillas primo), prob media -> curva/cortes oficiales.
# Requiere HT2103/PARAM.yml y BO_log.txt (1_bayesiana_lightgbm.R).

require("here")
here::i_am("juara/compe1/03_rank_nocont_lag1_delta1/00/4_produccion_top20_bo_semillas.R")
source(here("juara", "compe1", "common", "compe1_layers.R"))
source(here("juara", "compe1", "common", "compe1_data.R"))

EXPERIMENT_ID <- "03_rank_nocont_lag1_delta1"
RESULTADOS_DIR <- compe1_resultados_dir(EXPERIMENT_ID)
EXPERIMENTO <- 2103L
N_RANKS <- 20L
N_SEMILLAS_PRIMOS <- 10L

HT_DIR <- file.path(RESULTADOS_DIR, paste0("HT", EXPERIMENTO))
TOP20_ESTUDIO_DIR <- file.path(RESULTADOS_DIR, "estudio", "top20_bo_semillas")
RANK_BASE <- file.path(RESULTADOS_DIR, paste0("exp", EXPERIMENTO, "_top20"))

dir.create(TOP20_ESTUDIO_DIR, recursive = TRUE, showWarnings = FALSE)
dir.create(RANK_BASE, recursive = TRUE, showWarnings = FALSE)

require("data.table")

if (!require("yaml")) install.packages("yaml")
require("yaml")

if (!require("lightgbm")) install.packages("lightgbm")
require("lightgbm")

if (!require("ggplot2")) install.packages("ggplot2")
require("ggplot2")

if (!require("primes")) install.packages("primes")
require("primes")

PARAM <- read_yaml(file.path(HT_DIR, "PARAM.yml"))
campos_buenos <- unlist(PARAM$campos_buenos)

fold_train <- as.integer(PARAM$holdout$fold_train)
fold_test <- as.integer(PARAM$holdout$fold_test)

hiperparams <- c(
  "num_iterations",
  "num_leaves",
  "min_data_in_leaf",
  "min_sum_hessian_in_leaf"
)

BO_LOG <- file.path(HT_DIR, "BO_log.txt")
if (!file.exists(BO_LOG)) {
  stop("No existe ", BO_LOG, " — ejecutar 1_bayesiana_lightgbm.R primero.")
}

tb_bo <- fread(BO_LOG)
if (nrow(tb_bo) < N_RANKS) {
  stop("BO_log tiene menos de ", N_RANKS, " filas.")
}

tb_top20 <- head(tb_bo, N_RANKS)
tb_top20[, rank := seq_len(.N)]

faltantes <- setdiff(hiperparams, colnames(tb_top20))
if (length(faltantes) > 0L) {
  stop("BO_log.txt no tiene columnas: ", paste(faltantes, collapse = ", "))
}

fwrite(
  tb_top20[, c("rank", hiperparams, "y", "iter"), with = FALSE],
  file.path(TOP20_ESTUDIO_DIR, "top20_hiperparametros.tsv"),
  sep = "\t"
)

semillas_train <- compe1_semillas_primos(N_SEMILLAS_PRIMOS, PARAM$semilla_primigenia)
cat("semillas_train:", paste(semillas_train, collapse = ", "), "\n")

writeLines(
  as.character(semillas_train),
  file.path(TOP20_ESTUDIO_DIR, "semillas_train.txt")
)

sufijo_primo <- function(p) paste0("_", p)

hp_de_fila <- function(fila) {
  as.list(fila[1L, ..hiperparams])
}

escribir_curva_cortes_media <- function(tb_pred, out_dir, clase_col = "clase_ternaria") {
  fwrite(
    tb_pred[, list(numero_de_cliente, foto_mes, prob)],
    file = file.path(out_dir, "prediccion_media.txt"),
    sep = "\t"
  )

  tb_plot <- copy(tb_pred)
  setorder(tb_plot, -prob)
  tb_plot[, gan := compe1_ganancia_por_fila(tb_plot[[clase_col]])]
  tb_plot[, ganancia_acumulada := cumsum(gan)]
  tb_plot[, pos := seq_len(.N)]

  amostrar <- 30000L
  gra <- ggplot(
    data = tb_plot[pos <= amostrar],
    aes(x = pos, y = ganancia_acumulada)
  ) +
    geom_line() +
    theme(text = element_text(size = 16))

  ggsave(
    filename = file.path(out_dir, "curva_ganancia_media.pdf"),
    plot = gra,
    width = 16,
    height = 9
  )

  setorder(tb_plot, -prob)
  filas_cortes <- vector("list", length(unlist(PARAM$cortes)))
  sink(file.path(out_dir, "cortes_ganancia_media.txt"))
  cat("prob_media=10_semillas_primo\n")
  idx <- 0L
  for (envios in unlist(PARAM$cortes)) {
    idx <- idx + 1L
    total <- compe1_ganancia_envio(tb_plot, envios, prob_col = "prob")
    options(scipen = 999)
    cat("Envios=", envios, "\t", " TOTAL=", total, "\n", sep = "")
    filas_cortes[[idx]] <- data.table(envios = envios, total = total)
  }
  sink()

  fwrite(
    rbindlist(filas_cortes),
    file.path(out_dir, "cortes_ganancia_media.tsv"),
    sep = "\t"
  )
}

producir_primos_en_dir <- function(out_dir, param_hp, semillas, dtrain_final, dataset_test) {
  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

  param_final <- modifyList(PARAM$lgbm$param_fijos, param_hp)
  param_final <- compe1_decodificar_min_sum_hessian(param_final, PARAM)

  probs_pieces <- vector("list", length(semillas))

  for (i in seq_along(semillas)) {
    primo <- semillas[[i]]
    suf <- sufijo_primo(primo)

    param_normalizado <- copy(param_final)
    param_normalizado$min_data_in_leaf <- round(
      param_final$min_data_in_leaf / PARAM$trainingstrategy$undersampling
    )
    param_normalizado$seed <- primo

    modelo_final <- lgb.train(
      data = dtrain_final,
      param = param_normalizado
    )

    tb_importancia <- as.data.table(lgb.importance(modelo_final))
    fwrite(
      tb_importancia,
      file = file.path(out_dir, paste0("impo", suf, ".txt")),
      sep = "\t"
    )

    lgb.save(modelo_final, file.path(out_dir, paste0("modelo", suf, ".txt")))

    prediccion <- predict(
      modelo_final,
      data.matrix(dataset_test[, campos_buenos, with = FALSE])
    )

    tb_prediccion <- dataset_test[, list(numero_de_cliente, foto_mes, clase_ternaria)]
    tb_prediccion[, prob := prediccion]

    fwrite(
      tb_prediccion[, list(numero_de_cliente, foto_mes, prob)],
      file = file.path(out_dir, paste0("prediccion", suf, ".txt")),
      sep = "\t"
    )

    probs_pieces[[i]] <- tb_prediccion[, .(numero_de_cliente, foto_mes, prob)]

    setorder(tb_prediccion, -prob)
    tb_prediccion[, gan := compe1_ganancia_por_fila(clase_ternaria)]
    tb_prediccion[, ganancia_acumulada := cumsum(gan)]
    tb_prediccion[, pos := seq_len(.N)]

    amostrar <- 30000L
    gra <- ggplot(
      data = tb_prediccion[pos <= amostrar],
      aes(x = pos, y = ganancia_acumulada)
    ) +
      geom_line() +
      theme(text = element_text(size = 16))

    ggsave(
      filename = file.path(out_dir, paste0("curva_ganancia", suf, ".pdf")),
      plot = gra,
      width = 16,
      height = 9
    )

    sink(file.path(out_dir, paste0("cortes_ganancia", suf, ".txt")))
    cat("semilla_train=", primo, "\n", sep = "")
    for (envios in unlist(PARAM$cortes)) {
      total <- compe1_ganancia_envio(tb_prediccion, envios, prob_col = "prob")
      options(scipen = 999)
      cat("Envios=", envios, "\t", " TOTAL=", total, "\n", sep = "")
    }
    sink()

    rm(modelo_final)
    gc(full = TRUE, verbose = FALSE)
  }

  tb_all_probs <- rbindlist(probs_pieces, idcol = "idx_semilla")
  tb_media <- tb_all_probs[, .(prob = mean(prob)), by = .(numero_de_cliente, foto_mes)]
  tb_media <- merge(
    dataset_test[, list(numero_de_cliente, foto_mes, clase_ternaria)],
    tb_media,
    by = c("numero_de_cliente", "foto_mes"),
    all = FALSE
  )
  escribir_curva_cortes_media(tb_media, out_dir)
  invisible(tb_media)
}

dataset <- compe1_read_joined(EXPERIMENT_ID, foto_mes = unlist(PARAM$foto_mes))
dataset[, clase01 := compe1_clase01(clase_ternaria)]

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
dataset_test <- dataset[fold == fold_test]

dtrain_final <- lgb.Dataset(
  data = data.matrix(dataset_train[, campos_buenos, with = FALSE]),
  label = dataset_train$clase01
)

for (k in seq_len(N_RANKS)) {
  fila <- tb_top20[k]
  rank_label <- sprintf("rank_%02d", k)
  out_dir <- file.path(RANK_BASE, rank_label)
  param_hp <- hp_de_fila(fila)

  cat(
    "\n=== ", rank_label, " | AUC BO y=", fila$y, " iter=", fila$iter, " ===\n",
    sep = ""
  )

  producir_primos_en_dir(
    out_dir,
    param_hp,
    semillas_train,
    dtrain_final,
    dataset_test
  )

  param_rank <- PARAM
  param_rank$out$lgbm$mejores_hiperparametros <- param_hp
  param_rank$out$lgbm$y <- fila$y
  param_rank$top20_bo <- list(
    rank = k,
    bo_iter = fila$iter,
    bo_y = fila$y
  )
  param_rank$semillas_train <- as.list(semillas_train)
  write_yaml(param_rank, file = file.path(out_dir, "PARAM.yml"))
}

cat("\nFinalizado top-20 en ", RANK_BASE, "\n", sep = "")

# Top-10 hiperparametros BO x 10 semillas-primo (exp4940_top10).
#
# Lee las 10 mejores filas de BO_log.txt y entrena cada combinacion con las mismas
# semillas que 2_1. Artefactos en resultados/exp4940_top10/rank_XX/.
# Requiere 03/resultados/HT4940/PARAM.yml y BO_log.txt.

require("here")
here::i_am("juara/jueves/z494/03/6_produccion_top10_bo_semillas.R")
DATA_DIR <- here("juara", "data")
RESULTADOS_DIR <- here("juara", "jueves", "z494", "03", "resultados")
dir.create(RESULTADOS_DIR, recursive = TRUE, showWarnings = FALSE)

require("data.table")

if (!require("yaml")) install.packages("yaml")
require("yaml")

if (!require("lightgbm")) install.packages("lightgbm")
require("lightgbm")

if (!require("ggplot2")) install.packages("ggplot2")
require("ggplot2")

if (!require("primes")) install.packages("primes")
require("primes")

EXPERIMENTO <- 4940L
N_RANKS <- 10L
N_SEMILLAS_PRIMOS <- 10L

HT_DIR <- file.path(RESULTADOS_DIR, paste0("HT", EXPERIMENTO))
TOP10_ESTUDIO_DIR <- file.path(RESULTADOS_DIR, "estudio", "top10_bo_semillas")
RANK_BASE <- file.path(RESULTADOS_DIR, "exp4940_top10")

dir.create(TOP10_ESTUDIO_DIR, recursive = TRUE, showWarnings = FALSE)
dir.create(RANK_BASE, recursive = TRUE, showWarnings = FALSE)

PARAM <- read_yaml(file.path(HT_DIR, "PARAM.yml"))
campos_buenos <- unlist(PARAM$campos_buenos)

decodificar_min_sum_hessian <- function(param, pparam) {
  v <- as.numeric(param$min_sum_hessian_in_leaf)
  if (is.na(v)) {
    return(param)
  }
  lf <- pparam$hypeparametertuning$limites_fisicos$min_sum_hessian_in_leaf
  if (!is.null(lf)) {
    lo <- as.numeric(lf$lower)
    hi <- as.numeric(lf$upper)
    if (v >= lo && v <= hi) {
      return(param)
    }
  } else if (v >= 0) {
    return(param)
  }
  param$min_sum_hessian_in_leaf <- 10^v
  param
}

BO_LOG <- file.path(HT_DIR, "BO_log.txt")
if (!file.exists(BO_LOG)) {
  stop("No existe ", BO_LOG, " — ejecutar 1_bayesiana_lightgbm.R primero.")
}

tb_bo <- fread(BO_LOG)
if (nrow(tb_bo) < N_RANKS) {
  stop("BO_log tiene menos de ", N_RANKS, " filas.")
}

tb_top10 <- head(tb_bo, N_RANKS)
tb_top10[, rank := seq_len(.N)]

hiperparams <- c(
  "num_iterations",
  "learning_rate",
  "feature_fraction",
  "num_leaves",
  "min_data_in_leaf",
  "min_sum_hessian_in_leaf"
)
faltantes <- setdiff(hiperparams, colnames(tb_top10))
if (length(faltantes) > 0L) {
  stop("BO_log.txt no tiene columnas: ", paste(faltantes, collapse = ", "))
}

fwrite(
  tb_top10[, c("rank", hiperparams, "y", "iter"), with = FALSE],
  file.path(TOP10_ESTUDIO_DIR, "top10_hiperparametros.tsv"),
  sep = "\t"
)

primos <- generate_primes(min = 10000, max = 1000000)
set.seed(PARAM$semilla_primigenia)
semillas_train <- sample(primos, N_SEMILLAS_PRIMOS)
cat("semillas_train:", paste(semillas_train, collapse = ", "), "\n")

writeLines(
  as.character(semillas_train),
  file.path(TOP10_ESTUDIO_DIR, "semillas_train.txt")
)

sufijo_primo <- function(p) paste0("_", p)

particionar <- function(data, division, agrupa = "", campo = "fold", start = 1, seed = NA) {
  if (!is.na(seed)) set.seed(seed, "L'Ecuyer-CMRG")

  bloque <- unlist(mapply(
    function(x, y) {
      rep(y, x)
    }, division,
    seq(from = start, length.out = length(division))
  ))

  data[, (campo) := sample(rep(bloque, ceiling(.N / length(bloque))))[1:.N], by = agrupa]
}

realidad_inicializar <- function(pfuture, pparam) {
  drealidad <- pfuture[, list(numero_de_cliente, foto_mes, clase_ternaria)]

  particionar(
    drealidad,
    division = c(3, 7),
    agrupa = "clase_ternaria",
    seed = pparam$semilla_kaggle
  )

  drealidad
}

realidad_evaluar <- function(prealidad, pprediccion) {
  prealidad[pprediccion,
    on = c("numero_de_cliente", "foto_mes"),
    predicted := i.Predicted
  ]

  tbl <- prealidad[, list("qty" = .N), list(fold, predicted, clase_ternaria)]

  res <- list()
  res$public <- tbl[fold == 1 & predicted == 1L, sum(qty * ifelse(clase_ternaria == "BAJA+2", 1072500, -27500))] / 0.3
  res$private <- tbl[fold == 2 & predicted == 1L, sum(qty * ifelse(clase_ternaria == "BAJA+2", 1072500, -27500))] / 0.7
  res$total <- tbl[predicted == 1L, sum(qty * ifelse(clase_ternaria == "BAJA+2", 1072500, -27500))]

  prealidad[, predicted := NULL]
  res
}

hp_de_fila <- function(fila) {
  as.list(fila[1L, ..hiperparams])
}

producir_primos_en_dir <- function(out_dir, param_hp, semillas) {
  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

  param_final <- modifyList(PARAM$lgbm$param_fijos, param_hp)
  param_final <- decodificar_min_sum_hessian(param_final, PARAM)

  for (primo in semillas) {
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
      data.matrix(dfuture[, campos_buenos, with = FALSE])
    )

    tb_prediccion <- dfuture[, list(numero_de_cliente, foto_mes, clase_ternaria)]
    tb_prediccion[, prob := prediccion]

    fwrite(
      tb_prediccion[, list(numero_de_cliente, foto_mes, prob)],
      file = file.path(out_dir, paste0("prediccion", suf, ".txt")),
      sep = "\t"
    )

    setorder(tb_prediccion, -prob)
    tb_prediccion[, gan := ifelse(clase_ternaria == "BAJA+2", 1072500, -27500)]
    tb_prediccion[, ganancia_acumulada := cumsum(gan)]
    tb_prediccion[, pos := sequence(.N)]

    amostrar <- 30000L
    gra <- ggplot(
      data = tb_prediccion[pos <= amostrar],
      aes(x = pos, y = ganancia_acumulada)
    ) + geom_line()
    gra <- gra + theme(text = element_text(size = 16))

    ggsave(
      filename = file.path(out_dir, paste0("curva_ganancia", suf, ".pdf")),
      plot = gra,
      width = 16,
      height = 9
    )

    setorder(tb_prediccion, -prob)

    sink(file.path(out_dir, paste0("cortes_ganancia", suf, ".txt")))
    cat("semilla_train=", primo, "\n", sep = "")
    for (envios in unlist(PARAM$cortes)) {
      tb_prediccion[, Predicted := 0L]
      tb_prediccion[1:envios, Predicted := 1L]

      res <- realidad_evaluar(drealidad, tb_prediccion)

      options(scipen = 999)
      cat(
        "Envios=", envios, "\t",
        " TOTAL=", res$total,
        "  Public=", res$public,
        "  Private=", res$private,
        "\n",
        sep = ""
      )
    }
    sink()

    rm(modelo_final)
    gc(full = TRUE, verbose = FALSE)
  }
}

dataset <- fread(
  file.path(DATA_DIR, "competencia_01.csv.gz"),
  stringsAsFactors = TRUE
)

dataset[, clase01 := ifelse(clase_ternaria %in% c("BAJA+1", "BAJA+2"), 1L, 0L)]

dataset_train <- dataset[foto_mes %in% unlist(PARAM$train_final)]

dtrain_final <- lgb.Dataset(
  data = data.matrix(dataset_train[, campos_buenos, with = FALSE]),
  label = dataset_train[, clase01]
)

dfuture <- dataset[foto_mes %in% unlist(PARAM$future)]
drealidad <- realidad_inicializar(dfuture, PARAM)

for (k in seq_len(N_RANKS)) {
  fila <- tb_top10[k]
  rank_label <- sprintf("rank_%02d", k)
  out_dir <- file.path(RANK_BASE, rank_label)
  param_hp <- hp_de_fila(fila)

  cat("\n=== ", rank_label, " | AUC BO y=", fila$y, " iter=", fila$iter, " ===\n", sep = "")

  producir_primos_en_dir(out_dir, param_hp, semillas_train)

  param_rank <- PARAM
  param_rank$out$lgbm$mejores_hiperparametros <- param_hp
  param_rank$out$lgbm$y <- fila$y
  param_rank$top10_bo <- list(
    rank = k,
    bo_iter = fila$iter,
    bo_y = fila$y
  )
  param_rank$semillas_train <- as.list(semillas_train)
  write_yaml(param_rank, file = file.path(out_dir, "PARAM.yml"))
}

cat("\nFinalizado top-10 en ", RANK_BASE, "\n", sep = "")

# Escala ganancia del test producción (30%) a mes completo; salida = promedio mensual.

require("here")
here::i_am("juara/compe1/03_rank_nocont_lag1_delta1/00/3_escalar_ganancia_mes.R")
source(here("juara", "compe1", "common", "compe1_layers.R"))
source(here("juara", "compe1", "common", "compe1_data.R"))

EXPERIMENT_ID <- "03_rank_nocont_lag1_delta1"
EXPERIMENTO <- 2103L
RESULTADOS_DIR <- compe1_resultados_dir(EXPERIMENT_ID)
PROD_DIR <- file.path(RESULTADOS_DIR, paste0("exp", EXPERIMENTO))

require("data.table")

if (!require("yaml")) install.packages("yaml")
require("yaml")

param_prod <- file.path(PROD_DIR, "PARAM.yml")
if (file.exists(param_prod)) {
  PARAM <- read_yaml(param_prod)
} else {
  PARAM <- read_yaml(file.path(RESULTADOS_DIR, paste0("HT", EXPERIMENTO), "PARAM.yml"))
}

holdout <- PARAM$holdout
FOLD_TEST <- as.integer(holdout$fold_test)
division <- as.integer(unlist(holdout$division))

prep <- compe1_preparar_holdout_split(
  EXPERIMENT_ID,
  semilla_primigenia = PARAM$semilla_primigenia,
  division = division,
  fold_train = as.integer(holdout$fold_train),
  foto_mes = as.integer(unlist(PARAM$foto_mes))
)
dataset <- prep$data

pred <- fread(file.path(PROD_DIR, "prediccion.txt"))
dataset_test <- dataset[fold == FOLD_TEST]
dataset_test[pred, prob := i.prob, on = c("numero_de_cliente", "foto_mes")]

if (any(is.na(dataset_test$prob))) {
  stop("prediccion.txt no alinea con el holdout test", call. = FALSE)
}

conteos <- dataset[, .(n_total = .N), by = foto_mes]
conteos_test <- dataset_test[, .(n_test = .N), by = foto_mes]
conteos <- merge(conteos, conteos_test, by = "foto_mes", all.x = TRUE)
conteos[is.na(n_test), n_test := 0L]

meses <- sort(unique(dataset_test$foto_mes))
cortes <- unlist(PARAM$cortes)

filas <- list()
idx <- 0L
for (mes in meses) {
  dm <- dataset_test[foto_mes == mes]
  n_test <- conteos[foto_mes == mes, n_test]
  n_total <- conteos[foto_mes == mes, n_total]
  for (envios in cortes) {
    idx <- idx + 1L
    gan_obs <- compe1_ganancia_envio(dm, envios, prob_col = "prob")
    gan_esc <- compe1_escalar_ganancia_mes(gan_obs, n_test, n_total)
    filas[[idx]] <- data.table(
      foto_mes = mes,
      envios = as.integer(envios),
      gan_obs = gan_obs,
      n_test = n_test,
      n_total = n_total,
      gan_escalada_mes = gan_esc
    )
  }
}

tb_detalle <- rbindlist(filas)
fwrite(
  tb_detalle,
  file = file.path(PROD_DIR, "cortes_ganancia_por_mes_escalada.tsv"),
  sep = "\t"
)

tb_prom <- tb_detalle[
  ,
  .(gan_promedio_mes = mean(gan_escalada_mes, na.rm = TRUE)),
  by = envios
]
setorder(tb_prom, envios)

sink(file.path(PROD_DIR, "cortes_ganancia_escalada_promedio_mes.txt"))
for (i in seq_len(nrow(tb_prom))) {
  options(scipen = 999)
  cat(
    "Envios=", tb_prom$envios[i],
    "\t", " TOTAL=", tb_prom$gan_promedio_mes[i],
    "\n",
    sep = ""
  )
}
sink()

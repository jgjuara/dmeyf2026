# Entrenamiento final LightGBM con 10 semillas-primo (exp4940).
#
# Variante de 2_produccion_lightgbm.R: mismos hiperparametros, bucle sobre primos
# muestreados con primes + semilla_primigenia. Artefactos con sufijo _<primo>.
# Requiere 02/resultados/HT4940/PARAM.yml (salida de 1_bayesiana_lightgbm.R).

require("here")
here::i_am("juara/jueves/z494/02/2_1_produccion_lightgbm_semillas.R")
DATA_DIR <- here("juara", "data")
RESULTADOS_DIR <- here("juara", "jueves", "z494", "02", "resultados")
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
HT_DIR <- file.path(RESULTADOS_DIR, paste0("HT", EXPERIMENTO))
PROD_DIR <- file.path(RESULTADOS_DIR, paste0("exp", EXPERIMENTO))
dir.create(PROD_DIR, recursive = TRUE, showWarnings = FALSE)

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

N_SEMILLAS_PRIMOS <- 10L
primos <- generate_primes(min = 10000, max = 1000000)
set.seed(PARAM$semilla_primigenia)
semillas_train <- sample(primos, N_SEMILLAS_PRIMOS)
cat("semillas_train:", paste(semillas_train, collapse = ", "), "\n")

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

# iniciliazo el dataset de realidad, para medir ganancia
realidad_inicializar <- function(pfuture, pparam) {

  # datos para verificar la ganancia
  drealidad <- pfuture[, list(numero_de_cliente, foto_mes, clase_ternaria)]

  particionar(
    drealidad,
    division = c(3, 7),
    agrupa = "clase_ternaria",
    seed = PARAM$semilla_kaggle
  )

  return(drealidad)
}

# evaluo ganancia en los datos de la realidad

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
  return(res)
}

dataset <- fread(
  file.path(DATA_DIR, "competencia_01.csv.gz"),
  stringsAsFactors = TRUE
)

# clase01
dataset[, clase01 := ifelse(clase_ternaria %in% c("BAJA+1", "BAJA+2"), 1L, 0L)]

dataset_train <- dataset[foto_mes %in% unlist(PARAM$train_final)]

# dejo los datos en el formato que necesita LightGBM

dtrain_final <- lgb.Dataset(
  data = data.matrix(dataset_train[, campos_buenos, with = FALSE]),
  label = dataset_train[, clase01]
)

param_final <- modifyList(
  PARAM$lgbm$param_fijos,
  PARAM$out$lgbm$mejores_hiperparametros
)
param_final <- decodificar_min_sum_hessian(param_final, PARAM)

dfuture <- dataset[foto_mes %in% unlist(PARAM$future)]
drealidad <- realidad_inicializar(dfuture, PARAM)

for (primo in semillas_train) {

  suf <- sufijo_primo(primo)

  # este punto es muy SUTIL  y será revisado en la Clase 05

  param_normalizado <- copy(param_final)
  param_normalizado$min_data_in_leaf <- round(
    param_final$min_data_in_leaf / PARAM$trainingstrategy$undersampling
  )
  param_normalizado$seed <- primo

  # entreno LightGBM

  modelo_final <- lgb.train(
    data = dtrain_final,
    param = param_normalizado
  )

  # ahora imprimo la importancia de variables

  tb_importancia <- as.data.table(lgb.importance(modelo_final))

  fwrite(
    tb_importancia,
    file = file.path(PROD_DIR, paste0("impo", suf, ".txt")),
    sep = "\t"
  )

  # grabo a disco el modelo en un formato para seres humanos ... ponele ...
  lgb.save(modelo_final, file.path(PROD_DIR, paste0("modelo", suf, ".txt")))

  # aplico el modelo a los datos nuevos
  prediccion <- predict(
    modelo_final,
    data.matrix(dfuture[, campos_buenos, with = FALSE])
  )

  # tabla de prediccion
  tb_prediccion <- dfuture[, list(numero_de_cliente, foto_mes, clase_ternaria)]
  tb_prediccion[, prob := prediccion]

  # grabo las probabilidad del modelo
  fwrite(
    tb_prediccion[, list(numero_de_cliente, foto_mes, prob)],
    file = file.path(PROD_DIR, paste0("prediccion", suf, ".txt")),
    sep = "\t"
  )

  # Dibujo la curva de ganancia acumulada
  setorder(tb_prediccion, -prob)

  tb_prediccion[, gan := ifelse(clase_ternaria == "BAJA+2", 1072500, -27500)]
  tb_prediccion[, ganancia_acumulada := cumsum(gan)]
  tb_prediccion[, pos := sequence(.N)]

  # defino hasta donde muestra el grafico
  amostrar <- 30000

  # observamos la curva de ganancia
  gra <- ggplot(
    data = tb_prediccion[pos <= amostrar],
    aes(x = pos, y = ganancia_acumulada)
  ) + geom_line()

  gra <- gra + theme(text = element_text(size = 16))

  ggsave(
    filename = file.path(PROD_DIR, paste0("curva_ganancia", suf, ".pdf")),
    plot = gra,
    width = 16,
    height = 9
  )

  # genero archivos con los  "envios" mejores

  # ordeno por probabilidad descendente
  setorder(tb_prediccion, -prob)

  sink(file.path(PROD_DIR, paste0("cortes_ganancia", suf, ".txt")))
  cat("semilla_train=", primo, "\n", sep = "")
  for (envios in unlist(PARAM$cortes)) {

    tb_prediccion[, Predicted := 0L] # seteo inicial a 0
    tb_prediccion[1:envios, Predicted := 1L] # marco los primeros

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

PARAM$semillas_train <- as.list(semillas_train)
write_yaml(PARAM, file = file.path(PROD_DIR, "PARAM.yml"))

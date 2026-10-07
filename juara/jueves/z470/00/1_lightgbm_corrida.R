# LightGBM — una corrida (experimento KA4070). Seccion 4.07 del notebook z470.
#
# Asume juara/data/competencia_01.csv.gz (generar_clase_ternaria.R).

require("here")
here::i_am("juara/jueves/z470/00/1_lightgbm_corrida.R")
DATA_DIR <- here("juara", "data")
RESULTADOS_DIR <- here("juara", "jueves", "z470", "00", "resultados")
dir.create(RESULTADOS_DIR, recursive = TRUE, showWarnings = FALSE)

# cargo las librerias que necesito
require("data.table")

if (!require("lightgbm")) install.packages("lightgbm")
require("lightgbm")

# Aqui debe cargar SU semilla primigenia

PARAM <- list()
PARAM$experimento <- 4070
PARAM$semilla_primigenia <- 290497

# training y future
PARAM$train <- c(202104)
PARAM$future <- c(202106)

# estos hiperparametros de LightGBM surgieron de una Bayesian Optimization
PARAM$lgb$num_iterations <- 1000 # cantidad de arbolitos
PARAM$lgb$learning_rate <- 0.027
PARAM$lgb$feature_fraction <- 0.8
PARAM$lgb$min_data_in_leaf <- 76
PARAM$lgb$num_leaves <- 8
PARAM$lgb$max_bin <- 31

PARAM$semilla_kaggle <- 314159

# particionar agrega una columna llamada fold a un dataset
#   que consiste en una particion estratificada segun agrupa
# particionar( data=dataset, division=c(70,30),
#  agrupa=clase_ternaria, seed=semilla)   crea una particion 70, 30

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

  particionar(drealidad,
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

# carpeta de trabajo
KA_DIR <- file.path(RESULTADOS_DIR, paste0("KA", PARAM$experimento))
dir.create(KA_DIR, recursive = TRUE, showWarnings = FALSE)

# lectura del dataset
dataset <- fread(
  file.path(DATA_DIR, "competencia_01.csv.gz"),
  stringsAsFactors = TRUE
)

# paso la clase a binaria

dataset[, clase01 := ifelse(clase_ternaria %in% c("BAJA+2"), 1L, 0L)]

# los campos que se van a utilizar

campos_buenos <- copy(setdiff(colnames(dataset), c("clase_ternaria", "clase01")))

# establezco donde entreno

dataset[, train := 0L]
dataset[foto_mes %in% PARAM$train, train := 1L]

# dejo los datos en el formato que necesita LightGBM

dtrain <- lgb.Dataset(
  data = data.matrix(dataset[train == 1L, campos_buenos, with = FALSE]),
  label = dataset[train == 1L, clase01]
)

# genero el modelo
# estos hiperparametros  salieron de una laaarga Optmizacion Bayesiana

set.seed(PARAM$semilla_primigenia, kind = "L'Ecuyer-CMRG") # Establezco la semilla aleatoria

modelo <- lgb.train(
  data = dtrain,
  param = list(
    objective = "binary",
    max_bin = PARAM$lgb$max_bin,
    learning_rate = PARAM$lgb$learning_rate,
    num_iterations = PARAM$lgb$num_iterations,
    num_leaves = PARAM$lgb$num_leaves,
    min_data_in_leaf = PARAM$lgb$min_data_in_leaf,
    feature_fraction = PARAM$lgb$feature_fraction,
    seed = PARAM$semilla_primigenia
  )
)

# ahora imprimo la importancia de variables
tb_importancia <- as.data.table(lgb.importance(modelo))
archivo_importancia <- file.path(KA_DIR, "impo.txt")

fwrite(tb_importancia,
  file = archivo_importancia,
  sep = "\t"
)

# grabo a disco el modelo en un formato para seres humanos ... ponele ...

lgb.save(modelo, file.path(KA_DIR, "modelo.txt"))

# mes donde voy a aplicar el modelo
dfuture <- dataset[foto_mes %in% PARAM$future]
setorder(dfuture, numero_de_cliente, foto_mes)

# inicilizo el dataset  drealidad
drealidad <- realidad_inicializar(dfuture, PARAM)

# aplico el modelo a los datos nuevos
prediccion <- predict(
  modelo,
  data.matrix(dfuture[, campos_buenos, with = FALSE])
)

# tabla de prediccion

tb_prediccion <- dfuture[, list(numero_de_cliente, foto_mes)]
tb_prediccion[, prob := prediccion]

# grabo las probabilidad del modelo
fwrite(tb_prediccion,
  file = file.path(KA_DIR, "prediccion.txt"),
  sep = "\t"
)

# ordeno por probabilidad descendente

setorder(tb_prediccion, -prob)

# genero la prediccion

tb_prediccion[, Predicted := 0L]
tb_prediccion[prob > (1 / 40), Predicted := 1L]

archivo_kaggle <- file.path(KA_DIR, paste0("KA", PARAM$experimento, ".csv"))

# grabo el archivo
fwrite(tb_prediccion[, list(numero_de_cliente, Predicted)],
  file = archivo_kaggle,
  sep = ","
)

# calculo la ganancia en los datos del futuro
res <- realidad_evaluar(drealidad, tb_prediccion)

cat("TOTAL=", res$total,
  " Public=", res$public,
  " Private=", res$private,
  "\n",
  sep = ""
)

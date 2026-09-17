# Random Forest con ranger — una corrida (experimento KA440).
#
# Asume juara/data/competencia_01.csv.gz (generar_clase_ternaria.R).
# Imprime ganancia TOTAL / Public / Private en consola.

require("here")
here::i_am("juara/jueves/z440/00/1_random_forest_corrida.R")
DATA_DIR <- here("juara", "data")
RESULTADOS_DIR <- here("juara", "jueves", "z440", "00", "resultados")
dir.create(RESULTADOS_DIR, recursive = TRUE, showWarnings = FALSE)

# cargo las librerias que necesito
require("data.table")

if (!require("R.utils")) install.packages("R.utils")
require("R.utils")

# ranger se usa para procesar
if (!require("ranger")) install.packages("ranger")
require("ranger")

# randomForest  solo se usa para imputar nulos
if (!require("randomForest")) install.packages("randomForest")
require("randomForest")

# Aqui debe cargar SU semilla primigenia y
PARAM <- list()
PARAM$experimento <- 440
PARAM$semilla_primigenia <- 290497

# training y future
PARAM$train <- c(202104)
PARAM$future <- c(202106)

PARAM$ranger$num.trees <- 300 # cantidad de arboles
PARAM$ranger$mtry <- 13 # cantidad de atributos que participan en cada split
PARAM$ranger$min.node.size <- 50 # tamaño minimo de las hojas
PARAM$ranger$max.depth <- 10 # 0 significa profundidad infinita

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
    }, division, seq(from = start, length.out = length(division))
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

# lectura del dataset
dataset <- fread(file.path(DATA_DIR, "competencia_01.csv.gz"))

#  estas dos lineas estan relacionadas con el Data Drifting
# asigno un valor muy negativo

if ("Master_Finiciomora" %in% colnames(dataset)) {
  dataset[is.na(Master_Finiciomora), Master_Finiciomora := -999]
}

if ("Visa_Finiciomora" %in% colnames(dataset)) {
  dataset[is.na(Visa_Finiciomora), Visa_Finiciomora := -999]
}

# defino los dataset de entrenamiento y aplicacion
dtrain <- dataset[foto_mes %in% PARAM$train]

# mes donde voy a aplicar el modelo
dfuture <- dataset[foto_mes %in% PARAM$future]
setorder(dfuture, numero_de_cliente, foto_mes)

# inicilizo el dataset  drealidad
drealidad <- realidad_inicializar(dfuture, PARAM)

# quito clase ternaria de donde voy a aplicar el modelo
dfuture[, clase_ternaria := NULL]

set.seed(PARAM$semilla_primigenia, "L'Ecuyer-CMRG") # Establezco la semilla aleatoria

# ranger necesita la clase de tipo factor
factorizado <- as.factor(dtrain$clase_ternaria)
dtrain[, clase_ternaria := factorizado]

# Ranger NO acepta valores nulos
# Leo Breiman, ¿por que le temias a los nulos?
# imputo los nulos, ya que ranger no acepta nulos
dtrain <- na.roughfix(dtrain)

setorder(dtrain, clase_ternaria) # primero quedan los BAJA+1, BAJA+2, CONTINUA

# genero el modelo de Random Forest llamando a ranger()
modelo <- ranger(
  formula = "clase_ternaria ~ .",
  data = dtrain,
  probability = TRUE, # para que devuelva las probabilidades
  num.trees = PARAM$ranger$num.trees,
  mtry = PARAM$ranger$mtry,
  min.node.size = PARAM$ranger$min.node.size,
  max.depth = PARAM$ranger$max.depth
)

# Carpinteria necesaria sobre  dfuture
# como quiere la Estadistica Clasica, imputar nulos por separado
# ( aunque en este caso ya tengo los datos del futuro de antemano
#  pero bueno, sigamos el librito de estos fundamentalistas a rajatabla ...

dfuture <- na.roughfix(dfuture)

tb_prediccion <- dfuture[, list(numero_de_cliente, foto_mes)]

# aplico el modelo a los datos que no tienen clase
# aplico el modelo recien creado a los datos del futuro
prediccion <- predict(modelo, dfuture)

tb_prediccion[, prob := prediccion$predictions[, "BAJA+2"]]

tb_prediccion[, Predicted := as.numeric(prob > (1 / 40))]

res <- realidad_evaluar(drealidad, tb_prediccion)

cat(
  " TOTAL=", res$total,
  " Public=", res$public,
  " Private=", res$private,
  "\n",
  sep = ""
)

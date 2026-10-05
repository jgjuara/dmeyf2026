require("here")
here::i_am("juara/jueves/z607/00/2_rpart_binario_bayes_optimo.R")
DATA_DIR <- here("juara", "data")
RESULTADOS_DIR <- here("juara", "jueves", "z607", "00", "resultados")
dir.create(RESULTADOS_DIR, recursive = TRUE, showWarnings = FALSE)

# cargo las librerias que necesito
require("data.table")
require("rpart")
if (!require("rpart.plot")) install.packages("rpart.plot")
require("rpart.plot")

PARAM <- list()
PARAM$semilla_primigenia <- 102191

# Hiperparametros optimos encontrados en una Bayesian Optimization
PARAM$peso <- 15.9742385635332
PARAM$rpart$cp <- -1
PARAM$rpart$maxdepth <- 27
PARAM$rpart$minsplit <- 1684
PARAM$rpart$minbucket <- 447

experimento <- "exp6400"
EXP_DIR <- file.path(RESULTADOS_DIR, experimento)
dir.create(EXP_DIR, recursive = TRUE, showWarnings = FALSE)

# lectura del dataset
dataset <- fread(file.path(DATA_DIR, "competencia_01.csv.gz"))

# elimino los campos que causan Data Drifting
dataset[, cprestamos_personales := NULL]
dataset[, mprestamos_personales := NULL]

# Final Train
dfinal_train <- dataset[foto_mes == 202104, ]

# clase binaria
dfinal_train[, clase_binaria2 := ifelse(clase_ternaria == "CONTINUA", "NEG", "POS")]
dfinal_train[, clase_ternaria := NULL]

pesos <- dfinal_train[, ifelse(clase_binaria2 == "POS", PARAM$peso, 1.0)]

modelo_final <- rpart(
  formula = "clase_binaria2 ~ .",
  data = dfinal_train,
  model = TRUE,
  xval = 0,
  control = PARAM$rpart,
  weights = pesos
)

#  future
dfuture <- dataset[foto_mes == 202106, ]

# aplico el modelo a los datos del futuro
prediccion <- predict(
  modelo_final,
  dfuture,
  type = "prob"
)

dfuture[, prob := prediccion[, "POS"]]
dfuture[, gan := ifelse(clase_ternaria == "BAJA+2", 1.0725, -0.0275)]

setorder(dfuture, -prob)
dfuture[, gan_acum := cumsum(gan)]
dfuture[, gan_suave := frollmean(gan_acum, n = 501, align = "center", na.rm = TRUE)]

# Mejor Ganancia
mejor_gan <- dfuture[, max(gan_suave, na.rm = TRUE)]
cat("max(gan_suave):", mejor_gan, "\n")

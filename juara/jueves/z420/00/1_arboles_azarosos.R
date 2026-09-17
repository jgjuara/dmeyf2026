# Arboles Azarosos: ensemble de rpart con subconjuntos aleatorios de campos.
#
# Asume juara/data/competencia_01.csv.gz (generar_clase_ternaria.R).
# Salida principal por consola; carpeta exp4020 bajo resultados por convencion del notebook.

require("here")
here::i_am("juara/jueves/z420/00/1_arboles_azarosos.R")
DATA_DIR <- here("juara", "data")
RESULTADOS_DIR <- here("juara", "jueves", "z420", "00", "resultados")
dir.create(RESULTADOS_DIR, recursive = TRUE, showWarnings = FALSE)

# cargo las librerias que necesito
require("data.table")
require("rpart")

# particionar agrega una columna llamada fold a un dataset
#   que consiste en una particion estratificada segun agrupa
# particionar( data=dataset, division=c(70,30),
#  agrupa=clase_ternaria, seed=semilla)   crea una particion 70, 30

particionar <- function(data, division, agrupa= "", campo= "fold", start= 1, seed= NA) {
  if (!is.na(seed)) set.seed(seed, "L'Ecuyer-CMRG")

  bloque <- unlist(mapply(
    function(x, y) {rep(y, x)},division, seq(from= start, length.out= length(division))))

  data[, (campo) := sample(rep(bloque,ceiling(.N / length(bloque))))[1:.N],by= agrupa]
}


# iniciliazo el dataset de realidad, para medir ganancia
realidad_inicializar <- function( pfuture, pparam) {

  # datos para verificar la ganancia
  drealidad <- pfuture[, list(numero_de_cliente, foto_mes, clase_ternaria)]

  particionar(drealidad,
    division= c(3, 7),
    agrupa= "clase_ternaria",
    seed= PARAM$semilla_kaggle
  )

  return( drealidad )
}


# evaluo ganancia en los datos de la realidad

realidad_evaluar <- function( prealidad, pprediccion) {

  prealidad[ pprediccion,
    on= c("numero_de_cliente", "foto_mes"),
    predicted:= i.Predicted
  ]

  tbl <- prealidad[, list("qty"=.N), list(fold, predicted, clase_ternaria)]

  res <- list()
  res$public  <- tbl[fold==1 & predicted==1L, sum(qty*ifelse(clase_ternaria=="BAJA+2", 1072500, -27500))]/0.3
  res$private <- tbl[fold==2 & predicted==1L, sum(qty*ifelse(clase_ternaria=="BAJA+2", 1072500, -27500))]/0.7
  res$total <- tbl[predicted==1L, sum(qty*ifelse(clase_ternaria=="BAJA+2", 1072500, -27500))]

  prealidad[, predicted:=NULL]
  return( res )
}


PARAM <- list()
PARAM$semilla_primigenia <- 290497


# training y future
PARAM$train <- c(202104)
PARAM$future <- c(202106)

# parametros  arbol
# entreno cada arbol con solo 50% de las variables variables
#  por ahora, es fijo
PARAM$feature_fraction <- 0.1

PARAM$rpart$cp <- -1
PARAM$rpart$minsplit <- 50
PARAM$rpart$minbucket <- 20
PARAM$rpart$maxdepth <- 6

# voy a generar 512 arboles,
#  a mas arboles mas tiempo de proceso y MEJOR MODELO,
#  pero ganancias marginales
PARAM$num_trees_max <- 512

PARAM$semilla_kaggle <- 314159


# carpeta de trabajo
experimento <- "exp4020"
EXP_DIR <- file.path(RESULTADOS_DIR, experimento)
dir.create(EXP_DIR, recursive = TRUE, showWarnings = FALSE)


# lectura del dataset
dataset <- fread(file.path(DATA_DIR, "competencia_01.csv.gz"))


# defino los dataset de entrenamiento y aplicacion
dtrain <- dataset[foto_mes %in% PARAM$train]


# mes donde voy a aplicar el modelo
dfuture <- dataset[foto_mes %in% PARAM$future]
setorder(dfuture, numero_de_cliente, foto_mes)


# inicilizo el dataset  drealidad
drealidad <- realidad_inicializar( dfuture, PARAM)


# quito clase ternaria de donde voy a aplicar el modelo
dfuture[, clase_ternaria:= NULL]


# Establezco cuales son los campos que puedo usar para la prediccion
# el copy() es por la Lazy Evaluation
campos_buenos <- copy(setdiff(colnames(dtrain), c("clase_ternaria")))


# vean qué diversas las formas de nuestros ents!
for (n in 1:5) {
  qty_campos_a_utilizar <- as.integer(length(campos_buenos)
    * PARAM$feature_fraction)

  # elijo los campos al azar
  campos_random <- sample(campos_buenos, qty_campos_a_utilizar)

  # armo la formula para rpart
  formulita <- paste0("clase_ternaria ~ ", campos_random)

  # genero el arbol de decision
  modelo <- rpart(formulita,
    data= dtrain,
    xval= 0,
    control= PARAM$rpart
  )


# Plot structure and add text labels
plot(modelo, uniform = TRUE, main = paste0("Ent n°",n))
text(modelo, use.n = TRUE, all = TRUE, cex = 0.8)

}


# que tamanos de ensemble grabo a disco
grabar <- c(1, 2, 4, 8, 16, 32, 64, 128, 256, 384, 512)


tb_prediccion <- dfuture[, list(numero_de_cliente, foto_mes)]
# aqui se va acumulando la probabilidad del ensemble
tb_prediccion[, prob_acumulada := 0]

set.seed(PARAM$semilla_primigenia,"L'Ecuyer-CMRG" ) # Establezco la semilla aleatoria

for (arbolito in seq(PARAM$num_trees_max) ) {

  qty_campos_a_utilizar <- as.integer(length(campos_buenos)
    * PARAM$feature_fraction)

  # elijo los campos al azar
  campos_random <- sample(campos_buenos, qty_campos_a_utilizar)

  # paso de un vector a un string con los elementos
  # separados por un signo de "+"
  # este hace falta para la formula
  campos_random <- paste(campos_random, collapse= " + ")

  # armo la formula para rpart
  formulita <- paste0("clase_ternaria ~ ", campos_random)

  # genero el arbol de decision
  modelo <- rpart(formulita,
    data= dtrain,
    xval= 0,
    control= PARAM$rpart
  )

  # aplico el modelo a los datos que no tienen clase
  prediccion <- predict(modelo, dfuture, type= "prob")

  tb_prediccion[, prob_acumulada := prob_acumulada + prediccion[, "BAJA+2"]]

  if( arbolito %in% grabar ) {
    umbral_corte <-  arbolito * (1/40)
    tb_prediccion[, Predicted := as.numeric(prob_acumulada > umbral_corte)]
    res <- realidad_evaluar( drealidad, tb_prediccion)

    cat("'\n",
      "arbolitos=", arbolito,
      " TOTAL=", res$total,
      " Public=", res$public,
      " Private=", res$private,
      "\n",
      sep= ""
    )
  } else {
    cat( arbolito, " ")
  }

  flush.console()
}

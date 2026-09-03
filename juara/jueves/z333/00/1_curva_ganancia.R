script_dir <- dirname(normalizePath(sub(
  "^--file=",
  "",
  commandArgs(trailingOnly = FALSE)[grep("^--file=", commandArgs(trailingOnly = FALSE))]
)))
DATA_DIR <- file.path(dirname(dirname(script_dir)), "data")
RESULTADOS_DIR <- file.path(script_dir, "resultados")
dir.create(RESULTADOS_DIR, recursive = TRUE, showWarnings = FALSE)

# cargo las librerias que necesito
require("data.table")
require("rpart")
require("ggplot2")

# cambiar aqui los parametros
PARAM <- list()
PARAM$semilla_primigenia <- 102191


PARAM$minsplit <- 300
PARAM$minbucket <- 20
PARAM$maxdepth <- 11

# particionar agrega una columna llamada fold a un dataset
#   que consiste en una particion estratificada segun agrupa
# particionar( data=dataset, division=c(70,30),
#  agrupa=clase_ternaria, seed=semilla)   crea una particion 70, 30

particionar <- function(data, division, agrupa= "", campo= "fold", start= 1, seed= NA) {
  if (!is.na(seed)) set.seed(seed)

  bloque <- unlist(mapply(
    function(x, y) {rep(y, x)},division, seq(from= start, length.out= length(division))))

  data[, (campo) := sample(rep(bloque,ceiling(.N / length(bloque))))[1:.N],by= agrupa]
}


# lectura del dataset
dataset <- fread(file.path(DATA_DIR, "competencia_01.csv.gz"))

# a partir de ahora solo trabajo con 202106, el ultimo mes que tiene clase

dataset <- dataset[foto_mes == 202106] # defino donde voy a entrenar

# La division training/testing es 50%, 50%
#  que sea 50/50 se indica con el c(1,1)

particionar(dataset,
  division= c(1, 1),
  agrupa= "clase_ternaria",
  seed= PARAM$semilla_primigenia
)

# Entreno el modelo
# los datos donde voy a entrenar
# aqui es donde se deben probar distintos hiperparametros

modelo <- rpart(
  formula= "clase_ternaria ~ . -fold",
  data= dataset[fold == 1, ],
  xval= 0,
  cp= -1,
  minsplit= PARAM$minsplit,
  minbucket= PARAM$minbucket,
  maxdepth= PARAM$maxdepth
)

# aplico el modelo a TODOS los datos, inclusive los de training
prediccion <- predict(modelo, dataset, type= "prob")

# Pego la probabilidad de  BAJA+2
tb_prediccion <- dataset[, list(fold,clase_ternaria)]
tb_prediccion[, prob_baja2 := prediccion[, "BAJA+2"]]

# Dibujo la curva de ganancia acumulada
setorder(tb_prediccion, fold, -prob_baja2)

# agrego una columna que es la de las ganancias
# la multiplico por 2 para que ya este normalizada
#  es 2 porque cada fold es el 50%

tb_prediccion[, gan := 2 *ifelse(clase_ternaria == "BAJA+2", 1072500, -27500)]
tb_prediccion[, ganancia_acumulada := cumsum(gan), by= fold]
tb_prediccion[, pos := sequence(.N), by= fold]

# defino hasta donde muestra el grafico
amostrar <- 20000

# Esta hermosa curva muestra como en el mentiroso training
#   la ganancia es siempre mejor que en el real testing

# options( repr.plot.width=10, repr.plot.height=10)

gra <- ggplot(
           data= tb_prediccion[pos <= amostrar],
           aes( x= pos, y= ganancia_acumulada,
                color= ifelse(fold == 1, "train", "test") )
             ) + geom_line()

gra <- gra + theme(text = element_text(size = 16))

# options(repr.plot.width=16, repr.plot.height=9)
# print( gra )

ggsave(
  filename = file.path(RESULTADOS_DIR, "curva_ganancia.pdf"),
  plot = gra,
  width = 16,
  height = 9
)

# veo los resultados

sink(file.path(RESULTADOS_DIR, "ganancia_max.txt"))
print(PARAM)
cat( "Train gan max: ", tb_prediccion[fold==1, max(ganancia_acumulada)], "\n" )
cat( "Test  gan max: ", tb_prediccion[fold==2, max(ganancia_acumulada)], "\n" )
sink()

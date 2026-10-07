require("here")
here::i_am("juara/jueves/z607/00/1_canaritos_clase_ternaria.R")
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

PARAM$rpart$cp <- -1
PARAM$rpart$maxdepth <- 6
PARAM$rpart$minsplit <- 50
PARAM$rpart$minbucket <- 5

experimento <- "exp6300"
EXP_DIR <- file.path(RESULTADOS_DIR, experimento)
dir.create(EXP_DIR, recursive = TRUE, showWarnings = FALSE)

# lectura del dataset
dataset <- fread(file.path(DATA_DIR, "competencia_01.csv.gz"))

# datos entrenamiento
dtrain <- dataset[foto_mes == 202104, ]

# uso esta semilla para los canaritos
set.seed(PARAM$semilla_primigenia)

# agrego los siguientes canaritos
for (i in 1:154) dtrain[, paste0("canarito", i) := runif(nrow(dtrain))]

# Entreno el modelo

modelo <- rpart(
  formula = "clase_ternaria ~ .",
  data = dtrain,
  model = TRUE,
  xval = 0,
  control = PARAM$rpart
)

# genero un pdf con el dibujo del arbol

pdf(file = file.path(EXP_DIR, "arbol_canaritos.pdf"), width = 28, height = 4)
prp(modelo, extra = 101, digits = 5, branch = 1, type = 4, varlen = 0, faclen = 0)
dev.off()

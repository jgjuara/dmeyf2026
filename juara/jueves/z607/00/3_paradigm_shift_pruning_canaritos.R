require("here")
here::i_am("juara/jueves/z607/00/3_paradigm_shift_pruning_canaritos.R")
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

PARAM$peso <- 500

# Dejo crecer el arbol sin ninguna limitacion
# sin limite de altura ( 30 es el maximo que permite rpart )
# sin limite de minsplit ( 2 es el minimo natural )
# sin limite de minbukcet( 1 es el minimo natural )
# ya aprendimos que cp debe ser negativo
PARAM$rpart$cp <- -1
PARAM$rpart$maxdepth <- 31 # deberia ser 31, por velocidad en clase se baja  16
PARAM$rpart$minsplit <- 2
PARAM$rpart$minbucket <- 1

experimento <- "exp6600"
EXP_DIR <- file.path(RESULTADOS_DIR, experimento)
dir.create(EXP_DIR, recursive = TRUE, showWarnings = FALSE)

# lectura del dataset
dataset <- fread(file.path(DATA_DIR, "competencia_01.csv.gz"))

# elimino los campos que causan Data Drifting
dataset[, cprestamos_personales := NULL]
dataset[, mprestamos_personales := NULL]

# uso esta semilla para los canaritos
set.seed(PARAM$semilla_primigenia)

for (i in 1:155) {
  dataset[, paste0("canarito", i) := runif(nrow(dataset))]
}

# datos de training
dtrain <- dataset[foto_mes == 202104]

# clase binaria
dtrain[, clase_binaria2 := ifelse(clase_ternaria == "CONTINUA", "NEG", "POS")]
dtrain[, clase_ternaria := NULL]

# Entreno el modelo
pesos <- dtrain[, ifelse(clase_binaria2 == "POS", PARAM$peso, 1.0)]

modelo_original <- rpart(
  formula = "clase_binaria2 ~ .",
  data = dtrain,
  model = TRUE,
  xval = 0,
  control = PARAM$rpart,
  weights = pesos
)

# hago el pruning de los canaritos
# haciendo un hackeo a la estructura  modelo_original$frame
# -666 es un valor arbritrariamente negativo que jamas es generado por rpart

modelo_original$frame[
  modelo_original$frame$var %like% "canarito",
  "complexity"
] <- -666

modelo_pruned <- prune(modelo_original, -666)

# genero un pdf con el dibujo del arbol

pdf(file = file.path(EXP_DIR, "stopping_at_canaritos.pdf"), width = 28, height = 4)
prp(modelo_pruned, extra = 101, digits = 5, branch = 1, type = 4, varlen = 0, faclen = 0)
dev.off()

# datos del futuro
dfuturePS <- dataset[foto_mes == 202106]

# scoring, aplico el modelo a los datos del futuro
prediccion <- predict(
  modelo_pruned,
  dfuturePS,
  type = "prob"
)

dfuturePS[, prob := prediccion[, "POS"]]
dfuturePS[, gan := ifelse(clase_ternaria == "BAJA+2", 1.0725, -0.0275)]

setorder(dfuturePS, -prob)
dfuturePS[, gan_acum := cumsum(gan)]
dfuturePS[, gan_suave := frollmean(gan_acum, n = 501, align = "center", na.rm = TRUE)]

# Mejor Ganancia
mejor_gan <- dfuturePS[, max(gan_suave, na.rm = TRUE)]
cat("max(gan_suave):", mejor_gan, "\n")

# Entrena un rpart en 202106 (particion 50/50) y dibuja la curva de ganancia
# acumulada train vs test.
#
# Asume juara/lunes/data/competencia_01.csv.gz (generar_clase_ternaria.R).
# Escribe curva_ganancia.pdf y ganancia_max.txt en resultados/.

script_dir <- dirname(normalizePath(sub(
  "^--file=",
  "",
  commandArgs(trailingOnly = FALSE)[grep("^--file=", commandArgs(trailingOnly = FALSE))]
)))
DATA_DIR <- file.path(dirname(dirname(script_dir)), "data")
RESULTADOS_DIR <- file.path(script_dir, "resultados")
dir.create(RESULTADOS_DIR, recursive = TRUE, showWarnings = FALSE)

require("data.table")
require("rpart")
require("ggplot2")

PARAM <- list()
PARAM$semilla_primigenia <- 102191
PARAM$minsplit <- 300
PARAM$minbucket <- 20
PARAM$maxdepth <- 11

particionar <- function(data, division, agrupa = "", campo = "fold", start = 1, seed = NA) {
  if (!is.na(seed)) set.seed(seed)

  bloque <- unlist(mapply(
    function(x, y) {
      rep(y, x)
    },
    division, seq(from = start, length.out = length(division))
  ))

  data[, (campo) := sample(rep(bloque, ceiling(.N / length(bloque))))[1:.N], by = agrupa]
}

dataset <- fread(file.path(DATA_DIR, "competencia_01.csv.gz"))
dataset <- dataset[foto_mes == 202106]

particionar(
  dataset,
  division = c(1, 1),
  agrupa = "clase_ternaria",
  seed = PARAM$semilla_primigenia
)

modelo <- rpart(
  formula = "clase_ternaria ~ . -fold",
  data = dataset[fold == 1, ],
  xval = 0,
  cp = -1,
  minsplit = PARAM$minsplit,
  minbucket = PARAM$minbucket,
  maxdepth = PARAM$maxdepth
)

prediccion <- predict(modelo, dataset, type = "prob")

tb_prediccion <- dataset[, list(fold, clase_ternaria)]
tb_prediccion[, prob_baja2 := prediccion[, "BAJA+2"]]
setorder(tb_prediccion, fold, -prob_baja2)

tb_prediccion[, gan := 2 * ifelse(clase_ternaria == "BAJA+2", 1072500, -27500)]
tb_prediccion[, ganancia_acumulada := cumsum(gan), by = fold]
tb_prediccion[, pos := sequence(.N), by = fold]

amostrar <- 20000

gra <- ggplot(
  data = tb_prediccion[pos <= amostrar],
  aes(
    x = pos, y = ganancia_acumulada,
    color = ifelse(fold == 1, "train", "test")
  )
) +
  geom_line() +
  theme(text = element_text(size = 16))

ggsave(
  filename = file.path(RESULTADOS_DIR, "curva_ganancia.pdf"),
  plot = gra,
  width = 16,
  height = 9
)

gan_train <- tb_prediccion[fold == 1, max(ganancia_acumulada)]
gan_test <- tb_prediccion[fold == 2, max(ganancia_acumulada)]

sink(file.path(RESULTADOS_DIR, "ganancia_max.txt"))
print(PARAM)
cat("Train gan max: ", gan_train, "\n")
cat("Test  gan max: ", gan_test, "\n")
sink()

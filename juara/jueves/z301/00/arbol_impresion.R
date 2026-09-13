# Entrena un arbol rpart sobre competencia_01 e imprime el arbol en PDF.
#
# Asume juara/data/competencia_01.csv.gz (generar_clase_ternaria.R).
# Escribe arbol.pdf en 00/resultados.

require("here")
here::i_am("juara/jueves/z301/00/arbol_impresion.R")
DATA_DIR <- here("juara", "data")
RESULTADOS_DIR <- here("juara", "jueves", "z301", "00", "resultados")
dir.create(RESULTADOS_DIR, recursive = TRUE, showWarnings = FALSE)

require("data.table")
require("rpart")
if (!require("rpart.plot")) install.packages("rpart.plot")
require("rpart.plot")

PARAM <- list()
PARAM$param_basicos <- list(
  "cp" = -1,
  "maxdepth" = 4,
  "minsplit" = 20,
  "minbucket" = 5
)

dataset <- fread(file.path(DATA_DIR, "competencia_01.csv.gz"))

modelo <- rpart(
  "clase_ternaria ~ .",
  data = dataset,
  xval = 0,
  control = PARAM$param_basicos
)

arch_arbol <- file.path(RESULTADOS_DIR, "arbol.pdf")
pdf(file = arch_arbol, width = 28, height = 4)
prp(modelo, extra = 101, digits = 5, branch = 1, type = 4, varlen = 0, faclen = 0)
dev.off()

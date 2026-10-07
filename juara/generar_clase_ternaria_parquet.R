# Genera clase_ternaria a partir de competencia_01_crudo.csv; salida Parquet sin compresión.

require("here")
here::i_am("juara/generar_clase_ternaria_parquet.R")
DATA_DIR <- here("juara", "data")
dir.create(DATA_DIR, recursive = TRUE, showWarnings = FALSE)

require("data.table")

dataset <- fread(file.path(DATA_DIR, "competencia_01_crudo.csv"))

dsimple <- dataset[, list(
  "pos" = .I,
  numero_de_cliente,
  periodo0 = as.integer(foto_mes / 100) * 12 + foto_mes %% 100
)]

setorder(dsimple, numero_de_cliente, periodo0)

periodo_ultimo <- dsimple[, max(periodo0)]
periodo_anteultimo <- periodo_ultimo - 1

dsimple[, c("periodo1", "periodo2") :=
  shift(periodo0, n = 1:2, fill = NA, type = "lead"), numero_de_cliente]

dsimple[periodo0 < periodo_anteultimo, clase_ternaria := "CONTINUA"]

dsimple[periodo0 < periodo_ultimo &
  (is.na(periodo1) | periodo0 + 1 < periodo1),
clase_ternaria := "BAJA+1"]

dsimple[periodo0 < periodo_anteultimo & (periodo0 + 1 == periodo1) &
  (is.na(periodo2) | periodo0 + 2 < periodo2),
clase_ternaria := "BAJA+2"]

setorder(dsimple, pos)
dataset[, clase_ternaria := dsimple$clase_ternaria]

require("arrow")
arrow::write_parquet(
  dataset,
  sink = file.path(DATA_DIR, "competencia_01.parquet"),
  compression = "uncompressed"
)

setorder(dataset, foto_mes, clase_ternaria, numero_de_cliente)
print(dataset[, .N, list(foto_mes, clase_ternaria)])

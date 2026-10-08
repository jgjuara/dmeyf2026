# Capas parquet y rutas para experimentos juara/compe1 (R + lightgbm).
# Requiere el paquete here; el script llamador debe fijar el proyecto con here::i_am(...).

COMPE1_EXPERIMENT_IDS <- c(
  "00",
  "01py",
  "01_full_fe",
  "02_rank_nocont",
  "02_rank_nocount_py",
  "03_rank_nocont_lag1_delta1",
  "03_cont_nocont_lag1_delta1"
)

.compe1_layers_by_id <- list(
  "00" = c("competencia_01_v1.parquet"),
  "01py" = c(
    "competencia_01_nocontinuas_v1.parquet",
    "competencia_01_nocontinuas_v1_lag1.parquet",
    "competencia_01_nocontinuas_v1_lag2.parquet",
    "rankings_v1.parquet",
    "rankings_v1_lag1.parquet",
    "rankings_v1_lag2.parquet",
    "rankings_v1_delta1.parquet",
    "rankings_v1_delta2.parquet"
  ),
  "01_full_fe" = c(
    "competencia_01_nocontinuas_v1.parquet",
    "competencia_01_nocontinuas_v1_lag1.parquet",
    "competencia_01_nocontinuas_v1_lag2.parquet",
    "rankings_v1.parquet",
    "rankings_v1_lag1.parquet",
    "rankings_v1_lag2.parquet",
    "rankings_v1_delta1.parquet",
    "rankings_v1_delta2.parquet"
  ),
  "02_rank_nocont" = c(
    "competencia_01_nocontinuas_v1.parquet",
    "rankings_v1.parquet"
  ),
  "02_rank_nocount_py" = c(
    "competencia_01_nocontinuas_v1.parquet",
    "rankings_v1.parquet"
  ),
  "03_rank_nocont_lag1_delta1" = c(
    "competencia_01_nocontinuas_v1.parquet",
    "rankings_v1.parquet",
    "competencia_01_nocontinuas_v1_lag1.parquet",
    "rankings_v1_lag1.parquet",
    "rankings_v1_delta1.parquet"
  ),
  "03_cont_nocont_lag1_delta1" = c(
    "competencia_01_nocontinuas_v1.parquet",
    "competencia_01_continuas_v1.parquet",
    "competencia_01_nocontinuas_v1_lag1.parquet",
    "competencia_01_continuas_v1_lag1.parquet",
    "competencia_01_continuas_v1_delta1.parquet"
  )
)

# Fase siguiente (join materializado): here("juara", "compe1", experiment_id, "00", "cache", "features.parquet")

.compe1_assert_experiment_id <- function(experiment_id) {
  if (!experiment_id %in% COMPE1_EXPERIMENT_IDS) {
    stop(
      "experiment_id debe ser uno de: ",
      paste(COMPE1_EXPERIMENT_IDS, collapse = ", "),
      call. = FALSE
    )
  }
}

compe1_data_dir <- function() {
  here::here("juara", "data")
}

compe1_resultados_dir <- function(experiment_id) {
  .compe1_assert_experiment_id(experiment_id)
  here::here("juara", "compe1", experiment_id, "00", "resultados")
}

compe1_parquet_path <- function(filename) {
  file.path(compe1_data_dir(), filename)
}

compe1_layers <- function(experiment_id) {
  .compe1_assert_experiment_id(experiment_id)
  .compe1_layers_by_id[[experiment_id]]
}

compe1_layers_paths <- function(experiment_id) {
  file.path(compe1_data_dir(), compe1_layers(experiment_id))
}

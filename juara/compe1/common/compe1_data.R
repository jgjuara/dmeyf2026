# Lectura/join parquet, partición, undersampling (BO) y métricas de ganancia (compe1).
#
# Partición 70/30 estratificada por COMPE1_PARTICION_AGRUPA (clase_ternaria + foto_mes):
# fold_train = desarrollo (BO + train final); fold_test = test producción (no BO).
# La BO arma dtrain solo desde fold_train (training==1 si hay undersampling)
# y evalúa con compe1_lgb_cv_best_auc.

COMPE1_JOIN_KEYS <- c("numero_de_cliente", "foto_mes")
COMPE1_PARTICION_AGRUPA <- c("clase_ternaria", "foto_mes")
COMPE1_FOTO_MES_MAR_JUN <- c(202103L, 202104L, 202105L, 202106L)
COMPE1_GAN_BAJA2 <- 1072500L
COMPE1_GAN_OTRO <- -27500L

compe1_read_joined <- function(experiment_id, foto_mes = NULL) {
  if (!requireNamespace("arrow", quietly = TRUE)) {
    stop("paquete 'arrow' requerido para leer parquets", call. = FALSE)
  }
  if (!requireNamespace("data.table", quietly = TRUE)) {
    stop("paquete 'data.table' requerido", call. = FALSE)
  }
  paths <- compe1_layers_paths(experiment_id)
  missing <- paths[!file.exists(paths)]
  if (length(missing) > 0L) {
    stop(
      "parquet inexistente: ",
      paste(missing, collapse = ", "),
      call. = FALSE
    )
  }

  dt <- data.table::as.data.table(arrow::read_parquet(paths[[1L]]))
  if (length(paths) > 1L) {
    for (path in paths[-1L]) {
      layer <- data.table::as.data.table(arrow::read_parquet(path))
      if (!all(COMPE1_JOIN_KEYS %in% names(layer))) {
        stop("capa sin claves de join: ", path, call. = FALSE)
      }
      extra <- setdiff(names(layer), COMPE1_JOIN_KEYS)
      extra <- setdiff(extra, "clase_ternaria")
      layer <- layer[, c(COMPE1_JOIN_KEYS, extra), with = FALSE]
      dt <- merge(dt, layer, by = COMPE1_JOIN_KEYS, all = FALSE)
    }
  }

  if (!is.null(foto_mes)) {
    meses_keep <- foto_mes
    dt <- dt[foto_mes %in% meses_keep]
  }
  dt
}

compe1_campos_buenos <- function(dt, extra_drop = character()) {
  auxiliares <- c(
    COMPE1_JOIN_KEYS,
    "clase_ternaria",
    "clase01",
    "fold",
    "azar",
    "training",
    "prob",
    "Predicted",
    "gan",
    "ganancia_acumulada",
    "pos"
  )
  setdiff(names(dt), c(auxiliares, extra_drop))
}

particionar <- function(
    data,
    division,
    agrupa = "",
    campo = "fold",
    start = 1L,
    seed = NA
) {
  if (!is.na(seed)) {
    set.seed(seed, kind = "L'Ecuyer-CMRG")
  }

  bloque <- unlist(mapply(
    function(x, y) {
      rep(y, x)
    },
    division,
    seq(from = start, length.out = length(division))
  ))

  data[, (campo) := sample(rep(bloque, ceiling(.N / length(bloque))))[1:.N], by = agrupa]
}

compe1_aplicar_undersampling_train <- function(
    dt,
    fold_train,
    undersampling,
    seed
) {
  set.seed(seed, kind = "L'Ecuyer-CMRG")
  dt[, azar := stats::runif(.N)]
  dt[, training := 0L]
  dt[
    fold == fold_train &
      (
        azar <= undersampling |
          clase_ternaria %in% c("BAJA+1", "BAJA+2")
      ),
    training := 1L
  ]
  invisible(dt)
}

compe1_decodificar_min_sum_hessian <- function(param, pparam) {
  v <- as.numeric(param$min_sum_hessian_in_leaf)
  if (is.na(v)) {
    return(param)
  }
  lf <- pparam$hypeparametertuning$limites_fisicos$min_sum_hessian_in_leaf
  if (!is.null(lf)) {
    lo <- as.numeric(lf$lower)
    hi <- as.numeric(lf$upper)
    if (v >= lo && v <= hi) {
      return(param)
    }
  } else if (v >= 0) {
    return(param)
  }
  param$min_sum_hessian_in_leaf <- 10^v
  param
}

# n semillas de entrenamiento LightGBM (primos) reproducibles desde semilla_primigenia.
compe1_semillas_primos <- function(n, semilla_primigenia) {
  if (!requireNamespace("primes", quietly = TRUE)) {
    stop("paquete 'primes' requerido", call. = FALSE)
  }
  primos <- primes::generate_primes(min = 10000L, max = 1000000L)
  set.seed(semilla_primigenia, kind = "L'Ecuyer-CMRG")
  sample(primos, as.integer(n))
}

compe1_ganancia_envio <- function(dt, envios, prob_col = "prob") {
  ord <- data.table::copy(dt)
  data.table::setorderv(ord, prob_col, order = -1L)
  n <- min(as.integer(envios), nrow(ord))
  if (n <= 0L) {
    return(0)
  }
  top <- ord[seq_len(n)]
  sum(ifelse(top$clase_ternaria == "BAJA+2", 1072500, -27500))
}

compe1_escalar_ganancia_mes <- function(ganancia_obs, n_test_mes, n_total_mes) {
  if (n_test_mes <= 0L) {
    return(NA_real_)
  }
  ganancia_obs * (n_total_mes / n_test_mes)
}

compe1_ganancia_por_fila <- function(clase_ternaria) {
  ifelse(clase_ternaria == "BAJA+2", COMPE1_GAN_BAJA2, COMPE1_GAN_OTRO)
}

compe1_clase01 <- function(clase_ternaria) {
  ifelse(clase_ternaria %in% c("BAJA+1", "BAJA+2"), 1L, 0L)
}

# AUC en valids holdout de lgb.train; la BO compe1 usa compe1_lgb_cv_best_auc, no esta función.
compe1_auc_holdout_lgb <- function(model) {
  evals <- model$record_evals$holdout$auc$eval
  if (is.null(evals)) {
    stop("El modelo no tiene metricas holdout$auc", call. = FALSE)
  }
  max(unlist(evals), na.rm = TRUE)
}

compe1_lgb_cv_best_auc <- function(dtrain, param_completo, nfold = 2L) {
  nrounds <- as.integer(param_completo$num_iterations)
  param_train <- param_completo
  param_train$num_iterations <- NULL
  modelocv <- lightgbm::lgb.cv(
    params = param_train,
    data = dtrain,
    nrounds = nrounds,
    nfold = as.integer(nfold),
    stratified = TRUE,
    verbose = -1L
  )
  as.numeric(modelocv$best_score)
}

compe1_semillas_primos <- function(n, semilla_primigenia) {
  if (!requireNamespace("primes", quietly = TRUE)) {
    stop("paquete 'primes' requerido para compe1_semillas_primos", call. = FALSE)
  }
  primos <- primes::generate_primes(min = 10000, max = 1000000)
  set.seed(semilla_primigenia)
  sample(primos, as.integer(n))
}

# Exporta fold/azar/training (R L'Ecuyer) para el bridge Python.
compe1_export_split_training <- function(
    experiment_id,
    out_path,
    semilla_primigenia,
    division = c(70L, 30L),
    fold_train = 1L,
    undersampling = 0.1,
    foto_mes = COMPE1_FOTO_MES_MAR_JUN) {
  if (!requireNamespace("arrow", quietly = TRUE)) {
    stop("paquete 'arrow' requerido", call. = FALSE)
  }
  dt <- compe1_read_joined(experiment_id, foto_mes = foto_mes)
  dt[, clase01 := compe1_clase01(clase_ternaria)]
  particionar(
    dt,
    division = division,
    agrupa = COMPE1_PARTICION_AGRUPA,
    seed = semilla_primigenia
  )
  compe1_aplicar_undersampling_train(
    dt,
    fold_train = fold_train,
    undersampling = undersampling,
    seed = semilla_primigenia
  )
  out <- dt[, .(numero_de_cliente, foto_mes, fold, azar, training)]
  arrow::write_parquet(out, out_path)
  invisible(out_path)
}

compe1_preparar_holdout_split <- function(
    experiment_id,
    semilla_primigenia,
    division = c(70L, 30L),
    fold_train = 1L,
    foto_mes = COMPE1_FOTO_MES_MAR_JUN) {
  dt <- compe1_read_joined(experiment_id, foto_mes = foto_mes)
  dt[, clase01 := compe1_clase01(clase_ternaria)]
  particionar(
    dt,
    division = division,
    agrupa = COMPE1_PARTICION_AGRUPA,
    seed = semilla_primigenia
  )
  fold_test <- fold_train + length(division) - 1L
  list(
    data = dt,
    fold_train = fold_train,
    fold_test = fold_test,
    campos_buenos = compe1_campos_buenos(dt)
  )
}

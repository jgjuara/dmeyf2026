# Perfiles 1D empiricos y del surrogate (GP refit, matern3_2 como mlrMBO) sobre HT4940.
#
# Lee BO_log.txt y limites originales en PARAM.yml; excluye fallos (y<=0.5).
# Incluye max(mu) y mean(mu) MC (PDP) por coordenada. Extrapolacion fuera del
# dominio de entrenamiento es solo senal de presion en frontera, no AUC literal.
# Escribe TSV, PNG y gp_fit.rds en resultados/estudio/perfil_surrogate/.

require("here")
here::i_am("juara/jueves/z494/02/5_perfil_surrogate_fronteras_bo.R")

RESULTADOS_DIR <- here("juara", "jueves", "z494", "02", "resultados")
EXPERIMENTO <- 4940L
HT_DIR <- file.path(RESULTADOS_DIR, paste0("HT", EXPERIMENTO))
ESTUDIO_SURR_DIR <- file.path(RESULTADOS_DIR, "estudio", "perfil_surrogate")

N_GRID <- 80L
N_MC <- 20000L
EXPANSION_FACTOR <- 2
K_EMPIRICAL <- 15L
COVTYPE <- "matern3_2"
SEMILLA_MC <- 494001L
BORDER_WINDOW_FRAC <- 0.10
Y_BO_FAILURE <- 0.5

dir.create(ESTUDIO_SURR_DIR, recursive = TRUE, showWarnings = FALSE)

require("data.table")
if (!require("yaml")) install.packages("yaml")
require("yaml")
if (!require("ggplot2")) install.packages("ggplot2")
require("ggplot2")
if (!require("DiceKriging")) install.packages("DiceKriging")
require("DiceKriging")

HIPERPARAMS <- c(
  "num_iterations",
  "learning_rate",
  "feature_fraction",
  "num_leaves",
  "min_data_in_leaf",
  "min_sum_hessian_in_leaf"
)

INTEGER_PARAMS <- c("num_iterations", "num_leaves", "min_data_in_leaf")

leer_limites_bo <- function(PARAM, vars) {
  lower <- numeric(length(vars))
  upper <- numeric(length(vars))
  names(lower) <- names(upper) <- vars
  lf <- PARAM$hypeparametertuning$limites_fisicos
  for (hp in vars) {
    if (!is.null(lf) && !is.null(lf[[hp]])) {
      lower[[hp]] <- as.numeric(lf[[hp]]$lower)
      upper[[hp]] <- as.numeric(lf[[hp]]$upper)
      next
    }
    hp_bounds <- PARAM$hypeparametertuning$hs$pars[[hp]]
    if (is.null(hp_bounds$lower) || is.null(hp_bounds$upper)) {
      stop("PARAM.yml no define lower/upper para ", hp)
    }
    lower[[hp]] <- as.numeric(hp_bounds$lower)
    upper[[hp]] <- as.numeric(hp_bounds$upper)
  }
  list(lower = lower, upper = upper)
}

scale_to_unit <- function(X, lower, upper) {
  M <- as.matrix(X)
  sweep(
    sweep(M, 2, lower, "-"),
    2,
    upper - lower,
    "/"
  )
}

expected_improvement <- function(mean, sd, y_best, xi = 0) {
  sd <- pmax(sd, 1e-12)
  z <- (mean - y_best - xi) / sd
  ei <- (mean - y_best - xi) * pnorm(z) + sd * dnorm(z)
  ei[sd < 1e-12] <- 0
  ei
}

fit_surrogate_gp <- function(Xs, y) {
  km(
    formula = ~1,
    design = Xs,
    response = y,
    covtype = COVTYPE,
    nugget.estim = TRUE,
    control = list(trace = FALSE)
  )
}

profile_surrogate <- function(model, j, grid_scaled, n_mc, y_best) {
  p <- ncol(model@X)
  n_grid <- length(grid_scaled)
  profile_mean <- numeric(n_grid)
  profile_mean_pdp <- numeric(n_grid)
  profile_ei <- numeric(n_grid)

  for (k in seq_len(n_grid)) {
    Z <- matrix(runif(n_mc * p), nrow = n_mc, ncol = p)
    Z[, j] <- grid_scaled[k]
    pred <- predict(
      model,
      newdata = Z,
      type = "UK",
      se.compute = TRUE
    )
    mu <- as.numeric(pred$mean)
    sd <- as.numeric(pred$sd)
    profile_mean[k] <- max(mu)
    profile_mean_pdp[k] <- mean(mu)
    profile_ei[k] <- max(expected_improvement(mu, sd, y_best))
  }

  data.frame(
    grid_scaled = grid_scaled,
    profile_mean = profile_mean,
    profile_mean_pdp = profile_mean_pdp,
    profile_ei = profile_ei
  )
}

empirical_profile <- function(d, variable, grid_real, k) {
  x <- d[[variable]]
  y <- d$y
  out <- numeric(length(grid_real))
  for (i in seq_along(grid_real)) {
    distance <- abs(x - grid_real[i])
    idx <- order(distance)[seq_len(min(k, length(distance)))]
    out[i] <- max(y[idx])
  }
  data.frame(
    x_original = grid_real,
    best_observed_auc = out
  )
}

expand_limits <- function(lower, upper, hp_name, factor) {
  lo <- lower[[hp_name]]
  hi <- upper[[hp_name]]
  lo_ext <- lo / factor
  hi_ext <- hi * factor
  if (hp_name %in% INTEGER_PARAMS) {
    lo_ext <- max(1L, floor(lo_ext))
    hi_ext <- ceiling(hi_ext)
  } else if (hp_name == "learning_rate") {
    lo_ext <- max(lo_ext, 1e-4)
  } else if (hp_name == "feature_fraction") {
    lo_ext <- max(lo_ext, 0.01)
    hi_ext <- min(hi_ext, 1.0)
  }
  c(lower_ext = lo_ext, upper_ext = hi_ext)
}

make_profile_one_param <- function(
    model,
    d,
    hp_name,
    j,
    lower,
    upper,
    y_best,
    n_grid,
    n_mc
) {
  ext <- expand_limits(lower, upper, hp_name, EXPANSION_FACTOR)
  grid_real <- seq(
    unname(ext["lower_ext"]),
    unname(ext["upper_ext"]),
    length.out = n_grid
  )
  grid_scaled <- (grid_real - lower[[hp_name]]) / (upper[[hp_name]] - lower[[hp_name]])

  surr <- profile_surrogate(model, j, grid_scaled, n_mc, y_best)
  emp <- empirical_profile(d, hp_name, grid_real, K_EMPIRICAL)

  stopifnot(
    length(grid_real) == n_grid,
    length(surr$profile_mean) == n_grid,
    length(surr$profile_mean_pdp) == n_grid,
    length(emp$best_observed_auc) == n_grid
  )

  data.frame(
    parameter = hp_name,
    x_original = as.numeric(grid_real),
    grid_scaled = as.numeric(surr$grid_scaled),
    profile_mean = as.numeric(surr$profile_mean),
    profile_mean_pdp = as.numeric(surr$profile_mean_pdp),
    profile_ei = as.numeric(surr$profile_ei),
    best_observed_auc = as.numeric(emp$best_observed_auc),
    inside_original = grid_real >= lower[[hp_name]] & grid_real <= upper[[hp_name]],
    stringsAsFactors = FALSE
  )
}

slope_toward_border <- function(x, y, border_val, side) {
  inside <- if (side == "upper") {
    x <= border_val
  } else {
    x >= border_val
  }
  if (sum(inside) < 3L) {
    return(NA_real_)
  }
  xi <- x[inside]
  yi <- y[inside]
  n_tail <- max(3L, ceiling(length(xi) * BORDER_WINDOW_FRAC))
  if (side == "upper") {
    ord <- order(xi, decreasing = TRUE)
  } else {
    ord <- order(xi, decreasing = FALSE)
  }
  idx <- ord[seq_len(min(n_tail, length(ord)))]
  coef(lm(yi[idx] ~ xi[idx]))[[2L]]
}

boundary_signals <- function(profile, hp_name, lower_j, upper_j) {
  x <- profile$x_original
  span <- upper_j - lower_j
  win <- span * BORDER_WINDOW_FRAC

  emp_upper <- max(profile$best_observed_auc[x >= upper_j - win & x <= upper_j], na.rm = TRUE)
  emp_lower <- max(profile$best_observed_auc[x >= lower_j & x <= lower_j + win], na.rm = TRUE)
  emp_global <- max(profile$best_observed_auc[profile$inside_original], na.rm = TRUE)
  sig_emp_upper <- is.finite(emp_upper) && emp_upper >= emp_global - 1e-6
  sig_emp_lower <- is.finite(emp_lower) && emp_lower >= emp_global - 1e-6

  slope_mu_upper <- slope_toward_border(x, profile$profile_mean, upper_j, "upper")
  slope_mu_lower <- slope_toward_border(x, profile$profile_mean, lower_j, "lower")
  sig_mu_upper <- is.finite(slope_mu_upper) && slope_mu_upper > 0
  sig_mu_lower <- is.finite(slope_mu_lower) && slope_mu_lower < 0

  slope_pdp_upper <- slope_toward_border(x, profile$profile_mean_pdp, upper_j, "upper")
  slope_pdp_lower <- slope_toward_border(x, profile$profile_mean_pdp, lower_j, "lower")
  sig_pdp_upper <- is.finite(slope_pdp_upper) && slope_pdp_upper > 0
  sig_pdp_lower <- is.finite(slope_pdp_lower) && slope_pdp_lower < 0

  inside <- profile$inside_original
  ei_in <- max(profile$profile_ei[inside], na.rm = TRUE)
  ei_out_upper <- max(profile$profile_ei[x > upper_j], na.rm = TRUE)
  ei_out_lower <- max(profile$profile_ei[x < lower_j], na.rm = TRUE)
  ratio_upper <- if (ei_in > 0) ei_out_upper / ei_in else NA_real_
  ratio_lower <- if (ei_in > 0) ei_out_lower / ei_in else NA_real_
  sig_ei_upper <- is.finite(ratio_upper) && ratio_upper > 1
  sig_ei_lower <- is.finite(ratio_lower) && ratio_lower > 1
  ratio_ei_finite_upper <- is.finite(ratio_upper)
  ratio_ei_finite_lower <- is.finite(ratio_lower)

  rbind(
    data.frame(
      parameter = hp_name,
      frontera = "upper",
      best_ei_inside = ei_in,
      best_ei_outside = ei_out_upper,
      ratio_ei = ratio_upper,
      ratio_ei_finite = ratio_ei_finite_upper,
      signal_empirical = sig_emp_upper,
      signal_surrogate_mean = sig_mu_upper,
      signal_surrogate_mean_pdp = sig_pdp_upper,
      signal_ei = sig_ei_upper,
      aligned_three = sig_emp_upper && sig_mu_upper && sig_ei_upper,
      aligned_three_pdp = sig_emp_upper && sig_pdp_upper && sig_ei_upper
    ),
    data.frame(
      parameter = hp_name,
      frontera = "lower",
      best_ei_inside = ei_in,
      best_ei_outside = ei_out_lower,
      ratio_ei = ratio_lower,
      ratio_ei_finite = ratio_ei_finite_lower,
      signal_empirical = sig_emp_lower,
      signal_surrogate_mean = sig_mu_lower,
      signal_surrogate_mean_pdp = sig_pdp_lower,
      signal_ei = sig_ei_lower,
      aligned_three = sig_emp_lower && sig_mu_lower && sig_ei_lower,
      aligned_three_pdp = sig_emp_lower && sig_pdp_lower && sig_ei_lower
    )
  )
}

plot_profile <- function(profile, hp_name, lower_j, upper_j, experimento) {
  if (!"x_original" %in% names(profile) || nrow(profile) < 2L) {
    stop("Perfil invalido para ", hp_name, " — reejecutar tras actualizar el script.")
  }
  dlong <- rbind(
    data.frame(
      x = profile$x_original,
      y = profile$best_observed_auc,
      serie = "AUC observado (k-vecinos)"
    ),
    data.frame(
      x = profile$x_original,
      y = profile$profile_mean,
      serie = "max mu surrogate"
    ),
    data.frame(
      x = profile$x_original,
      y = profile$profile_mean_pdp,
      serie = "mean mu surrogate (PDP)"
    )
  )
  ei_max <- max(profile$profile_ei, na.rm = TRUE)
  y_ref <- max(
    c(profile$profile_mean, profile$profile_mean_pdp),
    na.rm = TRUE
  )
  ei_scale <- if (ei_max > 0) y_ref / ei_max else 1
  dlong_ei <- data.frame(
    x = profile$x_original,
    y = profile$profile_ei * ei_scale,
    serie = "max EI (escala AUC)"
  )
  dlong <- rbind(dlong, dlong_ei)

  ggplot() +
    annotate(
      "rect",
      xmin = -Inf,
      xmax = lower_j,
      ymin = -Inf,
      ymax = Inf,
      fill = "grey90",
      alpha = 0.35
    ) +
    annotate(
      "rect",
      xmin = upper_j,
      xmax = Inf,
      ymin = -Inf,
      ymax = Inf,
      fill = "grey90",
      alpha = 0.35
    ) +
    geom_line(
      data = dlong,
      aes(x = x, y = y, colour = serie, linetype = serie),
      linewidth = 1
    ) +
    geom_vline(xintercept = lower_j, linetype = "dashed", colour = "grey40") +
    geom_vline(xintercept = upper_j, linetype = "dashed", colour = "grey40") +
    scale_colour_manual(
      values = c(
        "AUC observado (k-vecinos)" = "steelblue",
        "max mu surrogate" = "darkorange",
        "mean mu surrogate (PDP)" = "purple",
        "max EI (escala AUC)" = "forestgreen"
      )
    ) +
    scale_linetype_manual(
      values = c(
        "AUC observado (k-vecinos)" = "solid",
        "max mu surrogate" = "solid",
        "mean mu surrogate (PDP)" = "longdash",
        "max EI (escala AUC)" = "dotted"
      )
    ) +
    labs(
      x = hp_name,
      y = "AUC / EI escalado",
      title = paste0("HT", experimento, ": perfil surrogate — ", hp_name),
      subtitle = "Gris: extrapolacion virtual | lineas: limites BO originales",
      colour = NULL,
      linetype = NULL
    ) +
    theme(text = element_text(size = 12), legend.position = "bottom")
}

PARAM_FILE <- file.path(HT_DIR, "PARAM.yml")
BO_LOG <- file.path(HT_DIR, "BO_log.txt")
if (!file.exists(PARAM_FILE)) {
  stop("No existe ", PARAM_FILE, " — ejecutar 1_bayesiana_lightgbm.R primero.")
}
if (!file.exists(BO_LOG)) {
  stop("No existe ", BO_LOG, " — ejecutar 1_bayesiana_lightgbm.R primero.")
}

PARAM <- read_yaml(PARAM_FILE)
tb_bo <- fread(BO_LOG)

faltantes <- setdiff(HIPERPARAMS, colnames(tb_bo))
if (length(faltantes) > 0L) {
  stop("BO_log.txt no tiene columnas: ", paste(faltantes, collapse = ", "))
}

if ("error.message" %in% colnames(tb_bo)) {
  tb_bo <- tb_bo[is.na(error.message) | error.message == ""]
}
tb_bo <- tb_bo[is.finite(y)]
n_pre_failure <- nrow(tb_bo)
tb_bo <- tb_bo[y > Y_BO_FAILURE]
if (nrow(tb_bo) < n_pre_failure) {
  cat(
    "Excluidas evaluaciones con y <=", Y_BO_FAILURE, ":",
    n_pre_failure - nrow(tb_bo), "\n"
  )
}
if (nrow(tb_bo) < 10L) {
  stop("Quedan muy pocas evaluaciones tras filtrar fallos; revisar BO_log.txt.")
}

limits <- leer_limites_bo(PARAM, HIPERPARAMS)
lower <- limits$lower
upper <- limits$upper

n_eval <- nrow(tb_bo)
y_best <- max(tb_bo$y)
cat("Evaluaciones BO (validas):", n_eval, "| y_best =", y_best, "\n")

X <- tb_bo[, ..HIPERPARAMS]
Xs <- scale_to_unit(X, lower, upper)

t0 <- proc.time()
gp_fit <- fit_surrogate_gp(Xs, tb_bo$y)
cat("GP refit (", COVTYPE, ") en ", round((proc.time() - t0)[3L], 1), " s\n", sep = "")

saveRDS(gp_fit, file.path(ESTUDIO_SURR_DIR, "gp_fit.rds"))

set.seed(SEMILLA_MC)
profiles <- list()
all_scores <- list()

for (j in seq_along(HIPERPARAMS)) {
  hp_name <- HIPERPARAMS[j]
  t1 <- proc.time()
  prof <- make_profile_one_param(
    model = gp_fit,
    d = tb_bo,
    hp_name = hp_name,
    j = j,
    lower = lower,
    upper = upper,
    y_best = y_best,
    n_grid = N_GRID,
    n_mc = N_MC
  )
  profiles[[hp_name]] <- prof
  cat(
    "Perfil ", hp_name, ": ",
    round((proc.time() - t1)[3L], 1), " s\n",
    sep = ""
  )

  fwrite(
    prof,
    file = file.path(ESTUDIO_SURR_DIR, paste0("profile_", hp_name, ".tsv")),
    sep = "\t"
  )

  gra <- plot_profile(prof, hp_name, lower[[hp_name]], upper[[hp_name]], EXPERIMENTO)
  ggsave(
    file.path(ESTUDIO_SURR_DIR, paste0("profile_", hp_name, ".png")),
    gra,
    width = 10,
    height = 6,
    dpi = 120
  )

  all_scores[[hp_name]] <- boundary_signals(
    prof, hp_name, lower[[hp_name]], upper[[hp_name]]
  )
}

scores <- rbindlist(all_scores)
setorder(scores, -ratio_ei_finite, -ratio_ei)
fwrite(scores, file.path(ESTUDIO_SURR_DIR, "boundary_scores.tsv"), sep = "\t")

cat("\n=== boundary_scores (ratio_ei finito primero, luego desc) ===\n")
print(scores)

cat("\nFronteras con alineacion de tres senales (max mu):\n")
aligned <- scores[aligned_three == TRUE]
if (nrow(aligned) > 0L) {
  print(aligned[, .(parameter, frontera, ratio_ei)])
} else {
  cat("(ninguna)\n")
}

cat("\nFronteras con alineacion de tres senales (PDP mean mu):\n")
aligned_pdp <- scores[aligned_three_pdp == TRUE]
if (nrow(aligned_pdp) > 0L) {
  print(aligned_pdp[, .(parameter, frontera, ratio_ei)])
} else {
  cat("(ninguna)\n")
}

cat("\nSalida en:", ESTUDIO_SURR_DIR, "\n")

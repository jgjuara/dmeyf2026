# Scatter AUC vs cada hiperparametro tunado en la BO (HT4940).
#
# Lee BO_log.txt y PARAM.yml (rangos de BO); escribe PNG en resultados/estudio/.
# Scatter hiperparam vs AUC: solo evaluaciones con AUC > umbral; OLS en el grafico.
# Además: AUC vs intento (iter); por hiperparam, intento vs valor coloreado por AUC.

require("here")
here::i_am("juara/jueves/z494/02/3_estudio_hiperparametros_auc.R")

RESULTADOS_DIR <- here("juara", "jueves", "z494", "02", "resultados")
EXPERIMENTO <- 4940L
HT_DIR <- file.path(RESULTADOS_DIR, paste0("HT", EXPERIMENTO))
ESTUDIO_DIR <- file.path(RESULTADOS_DIR, "estudio")

AUC_MIN <- 0.7

dir.create(ESTUDIO_DIR, recursive = TRUE, showWarnings = FALSE)

require("data.table")

if (!require("ggplot2")) install.packages("ggplot2")
require("ggplot2")

if (!require("yaml")) install.packages("yaml")
require("yaml")

PARAM_FILE <- file.path(HT_DIR, "PARAM.yml")
if (!file.exists(PARAM_FILE)) {
  stop("No existe ", PARAM_FILE, " — ejecutar 1_bayesiana_lightgbm.R primero.")
}
PARAM <- read_yaml(PARAM_FILE)

BO_LOG <- file.path(HT_DIR, "BO_log.txt")
if (!file.exists(BO_LOG)) {
  stop("No existe ", BO_LOG, " — ejecutar 1_bayesiana_lightgbm.R primero.")
}

tb_bo <- fread(BO_LOG)

hiperparams <- c(
  "num_iterations",
  "learning_rate",
  "feature_fraction",
  "num_leaves",
  "min_data_in_leaf",
  "min_sum_hessian_in_leaf"
)

faltantes <- setdiff(hiperparams, colnames(tb_bo))
if (length(faltantes) > 0L) {
  stop("BO_log.txt no tiene columnas: ", paste(faltantes, collapse = ", "))
}

tb_plot <- tb_bo[y > AUC_MIN]
n_total <- nrow(tb_bo)
n_plot <- nrow(tb_plot)
cat(
  "Evaluaciones BO:", n_total,
  "| con AUC >", AUC_MIN, ":", n_plot,
  "| excluidas:", n_total - n_plot, "\n"
)
if (n_plot < 3L) {
  stop("Quedan menos de 3 puntos con AUC > ", AUC_MIN, "; no se puede ajustar tendencia.")
}

tb_mejor <- tb_plot[which.max(y)]

limites_fisicos_bo <- function(PARAM, hp) {
  lf <- PARAM$hypeparametertuning$limites_fisicos
  if (!is.null(lf) && !is.null(lf[[hp]])) {
    return(c(as.numeric(lf[[hp]]$lower), as.numeric(lf[[hp]]$upper)))
  }
  hp_bounds <- PARAM$hypeparametertuning$hs$pars[[hp]]
  if (is.null(hp_bounds$lower) || is.null(hp_bounds$upper)) {
    stop("PARAM.yml no define lower/upper para ", hp)
  }
  c(as.numeric(hp_bounds$lower), as.numeric(hp_bounds$upper))
}

etiqueta_lm <- function(x_vec, y_vec, nombre_x) {
  fit <- lm(y_vec ~ x_vec)
  b <- coef(fit)
  r2 <- summary(fit)$r.squared
  sprintf(
    "AUC = %.4g + (%.4g) * %s\nR² = %.4f",
    b[[1L]], b[[2L]], nombre_x, r2
  )
}

for (hp in hiperparams) {
  xlim_bo <- limites_fisicos_bo(PARAM, hp)

  x_vals <- tb_plot[[hp]]
  lbl_tendencia <- etiqueta_lm(x_vals, tb_plot$y, hp)

  gra <- ggplot(tb_plot, aes(x = .data[[hp]], y = y)) +
    geom_point(alpha = 0.55, size = 2, colour = "steelblue") +
    geom_smooth(method = "lm", formula = y ~ x, colour = "darkorange", linewidth = 1) +
    geom_point(
      data = tb_mejor,
      aes(x = .data[[hp]], y = y),
      colour = "firebrick",
      size = 4,
      inherit.aes = FALSE
    ) +
    annotate(
      "label",
      x = xlim_bo[1L],
      y = Inf,
      hjust = 0,
      vjust = 1.1,
      label = lbl_tendencia,
      size = 4,
      fill = alpha("white", 0.85),
      label.size = 0
    ) +
    labs(
      x = hp,
      y = "AUC (lgb.cv, 5 folds)",
      title = paste0("HT", EXPERIMENTO, ": AUC vs ", hp),
      subtitle = sprintf(
        "AUC > %.1f (%d eval.) | mejor AUC = %.6f (rojo)",
        AUC_MIN, n_plot, tb_mejor$y
      )
    ) +
    scale_x_continuous(limits = xlim_bo, expand = c(0, 0)) +
    theme(text = element_text(size = 14))

  out_png <- file.path(ESTUDIO_DIR, paste0("auc_vs_", hp, ".png"))
  ggsave(
    filename = out_png,
    plot = gra,
    width = 10,
    height = 6,
    dpi = 120
  )
  cat("Escrito:", out_png, "\n")
}

if (!"iter" %in% colnames(tb_bo)) {
  stop("BO_log.txt no tiene columna iter (regenerar con 1_bayesiana_lightgbm.R).")
}

tb_progreso <- tb_bo[order(iter)]
tb_progreso <- tb_progreso[tb_progreso$y >= 0.7, ]
tb_mejor_bo <- tb_bo[which.max(y)]

for (hp in hiperparams) {
  ylim_bo <- limites_fisicos_bo(PARAM, hp)

  gra_iter_hp <- ggplot(tb_progreso, aes(x = iter, y = .data[[hp]], colour = y)) +
    geom_point(size = 2.5, alpha = 0.85) +
    scale_colour_viridis_c(option = "plasma", name = "AUC") +
    labs(
      x = "Intento (evaluacion en la BO)",
      y = hp,
      title = paste0("HT", EXPERIMENTO, ": ", hp, " vs intento (color AUC)"),
      subtitle = sprintf("%d evaluaciones | escala AUC en leyenda", n_total)
    ) +
    scale_y_continuous(limits = ylim_bo, expand = c(0, 0)) +
    theme(text = element_text(size = 14))

  out_png_iter_hp <- file.path(ESTUDIO_DIR, paste0("iter_vs_", hp, "_color_auc.png"))
  ggsave(
    filename = out_png_iter_hp,
    plot = gra_iter_hp,
    width = 10,
    height = 6,
    dpi = 120
  )
  cat("Escrito:", out_png_iter_hp, "\n")
}


gra_progreso <- ggplot(tb_progreso, aes(x = iter, y = y)) +
  geom_line(colour = "grey75", linewidth = 0.35) +
  geom_point(alpha = 0.55, size = 2, colour = "steelblue") +
  geom_point(
    data = tb_mejor_bo,
    aes(x = iter, y = y),
    colour = "firebrick",
    size = 4,
    inherit.aes = FALSE
  ) +
  labs(
    x = "Intento (evaluacion en la BO)",
    y = "AUC (lgb.cv, 5 folds)",
    title = paste0("HT", EXPERIMENTO, ": AUC vs intento en busqueda bayesiana"),
    subtitle = sprintf(
      "%d evaluaciones | mejor AUC = %.6f (rojo, intento %d)",
      n_total, tb_mejor_bo$y, tb_mejor_bo$iter
    )
  ) +
  theme(text = element_text(size = 14))

out_png_progreso <- file.path(ESTUDIO_DIR, "auc_vs_intento_bo.png")
ggsave(
  filename = out_png_progreso,
  plot = gra_progreso,
  width = 10,
  height = 6,
  dpi = 120
)
cat("Escrito:", out_png_progreso, "\n")

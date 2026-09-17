# Agrega cortes_ganancia_<primo>.txt (salida de 2_1_produccion_lightgbm_semillas.R).
# Graficos: ganancia vs envios (color por primo); varianza vs envios (public/private).
# Estima varianza muestral entre primos en cada envio y resume por conjunto public/private.

require("here")
here::i_am("juara/jueves/z494/02/4_cortes_ganancia_semillas_primos.R")

RESULTADOS_DIR <- here("juara", "jueves", "z494", "02", "resultados")
EXPERIMENTO <- 4940L
PROD_DIR <- file.path(RESULTADOS_DIR, paste0("exp", EXPERIMENTO))
ESTUDIO_DIR <- file.path(RESULTADOS_DIR, "estudio")

dir.create(ESTUDIO_DIR, recursive = TRUE, showWarnings = FALSE)

require("data.table")

if (!require("ggplot2")) install.packages("ggplot2")
require("ggplot2")

if (!require("yaml")) install.packages("yaml")
require("yaml")

parse_cortes_primo <- function(path) {
  lines <- readLines(path, warn = FALSE)
  if (length(lines) < 2L) {
    stop("Archivo vacio o sin cortes: ", path)
  }

  primo <- if (grepl("^semilla_train=", lines[[1L]])) {
    as.integer(sub("^semilla_train=", "", lines[[1L]]))
  } else {
    as.integer(sub("^cortes_ganancia_(\\d+)\\.txt$", "\\1", basename(path)))
  }

  body <- lines[grepl("^Envios=", lines)]
  if (length(body) == 0L) {
    stop("Sin lineas Envios= en ", path)
  }

  envios <- vapply(
    regmatches(body, regexec("Envios=([0-9]+)", body)),
    function(m) as.integer(m[[2L]]),
    integer(1L)
  )
  public <- vapply(
    regmatches(body, regexec("Public=([0-9]+)", body)),
    function(m) as.numeric(m[[2L]]),
    numeric(1L)
  )
  private <- vapply(
    regmatches(body, regexec("Private=([0-9]+)", body)),
    function(m) as.numeric(m[[2L]]),
    numeric(1L)
  )

  rbindlist(list(
    data.table(primo = primo, envios = envios, tipo = "public", ganancia = public),
    data.table(primo = primo, envios = envios, tipo = "private", ganancia = private)
  ))
}

archivos <- list.files(
  PROD_DIR,
  pattern = "^cortes_ganancia_[0-9]+\\.txt$",
  full.names = TRUE
)
if (length(archivos) == 0L) {
  stop(
    "No hay cortes_ganancia_<primo>.txt en ", PROD_DIR,
    " — ejecutar 2_1_produccion_lightgbm_semillas.R primero."
  )
}

tb_curvas <- rbindlist(lapply(archivos, parse_cortes_primo))
tb_curvas[, tipo := factor(tipo, levels = c("public", "private"))]
tb_curvas[, primo := factor(primo)]

n_primos <- uniqueN(tb_curvas$primo)
cat("Archivos:", length(archivos), "| primos:", n_primos, "\n")

tb_var <- tb_curvas[, .(
  var_ganancia = var(ganancia),
  sd_ganancia = sd(ganancia),
  n = .N
), by = .(envios, tipo)]

if (any(tb_var$n < 2L)) {
  stop("Se necesitan al menos 2 curvas por tipo para estimar varianza.")
}

tb_resumen_var <- tb_var[, .(
  var_media = mean(var_ganancia),
  var_mediana = median(var_ganancia),
  sd_media_de_sd_por_envio = mean(sd_ganancia),
  envios_con_var_max = envios[which.max(var_ganancia)],
  var_max = max(var_ganancia)
), by = tipo]

fwrite(tb_var, file.path(ESTUDIO_DIR, "cortes_semillas_varianza_por_envio.txt"), sep = "\t")
fwrite(tb_resumen_var, file.path(ESTUDIO_DIR, "cortes_semillas_varianza_resumen.txt"), sep = "\t")

print(tb_resumen_var)

etiq_var <- tb_resumen_var[, sprintf(
  "%s: var media=%.4g (max=%.4g en envios=%s)",
  tipo, var_media, var_max, envios_con_var_max
)]
etiqueta_var <- paste(etiq_var, collapse = "  |  ")

gra <- ggplot(tb_curvas, aes(x = envios, y = ganancia, color = primo, linetype = tipo)) +
  geom_line(linewidth = 0.7) +
  scale_linetype_manual(
    values = c(public = "solid", private = "dashed"),
    labels = c(public = "Public", private = "Private")
  ) +
  labs(
    title = "Ganancia por envios — robustez de semillas (primos)",
    subtitle = etiqueta_var,
    x = "Envios",
    y = "Ganancia",
    color = "Semilla (primo)",
    linetype = "Conjunto"
  ) +
  theme(text = element_text(size = 14))

ggsave(
  filename = file.path(ESTUDIO_DIR, "cortes_semillas_public_private.pdf"),
  plot = gra,
  width = 16,
  height = 9
)

ggsave(
  filename = file.path(ESTUDIO_DIR, "cortes_semillas_public_private.png"),
  plot = gra,
  width = 16,
  height = 9,
  dpi = 120
)

cat("Escrito:", file.path(ESTUDIO_DIR, "cortes_semillas_public_private.pdf"), "\n")

gra_var <- ggplot(tb_var, aes(x = envios, y = var_ganancia, color = tipo, linetype = tipo)) +
  geom_line(linewidth = 1) +
  geom_point(size = 2) +
  scale_color_manual(
    values = c(public = "#2166ac", private = "#b2182b"),
    labels = c(public = "Public", private = "Private")
  ) +
  scale_linetype_manual(
    values = c(public = "solid", private = "dashed"),
    labels = c(public = "Public", private = "Private")
  ) +
  labs(
    title = "Varianza de ganancia entre semillas vs envios",
    subtitle = "Varianza muestral entre primos en cada corte de envios",
    x = "Envios",
    y = "Varianza de ganancia",
    color = "Conjunto",
    linetype = "Conjunto"
  ) +
  theme(text = element_text(size = 14))

ggsave(
  filename = file.path(ESTUDIO_DIR, "cortes_semillas_varianza_vs_envios.pdf"),
  plot = gra_var,
  width = 16,
  height = 9
)

ggsave(
  filename = file.path(ESTUDIO_DIR, "cortes_semillas_varianza_vs_envios.png"),
  plot = gra_var,
  width = 16,
  height = 9,
  dpi = 120
)

cat("Escrito:", file.path(ESTUDIO_DIR, "cortes_semillas_varianza_vs_envios.pdf"), "\n")

# Analisis inferencial post hoc del top-10 BO x semillas (sin entrenamiento).
#
# Evidencia condicional al shortlist: ganador por max mean(ganancia publica) sobre cortes.
# Bloques: mejor vs 2do; top vs cada rank del resto (Holm); top vs mediana del resto;
# winrate/sign test; Friedman opcional. Requiere salida de 6_produccion_top10_bo_semillas.R.

require("here")
here::i_am("juara/jueves/z494/02/7_analisis_top10_bo_semillas.R")

RESULTADOS_DIR <- here("juara", "jueves", "z494", "02", "resultados")
EXPERIMENTO <- 4940L
N_RANKS <- 10L
N_SEMILLAS <- 10L
DO_FRIEDMAN <- TRUE

# Etiquetas de inferencia para graficos de p-valor (Wilcoxon emparejado, dos colas).
WILCOX_H0_LABEL <- "H0: mediana(ganancia_A - ganancia_B) = 0"
WILCOX_H1_LABEL <- "H1: mediana(ganancia_A - ganancia_B) != 0 (bilateral / dos colas)"

ESTUDIO_DIR <- file.path(RESULTADOS_DIR, "estudio", "top10_bo_semillas")
RANK_BASE <- file.path(RESULTADOS_DIR, "exp4940_top10")
HT_DIR <- file.path(RESULTADOS_DIR, paste0("HT", EXPERIMENTO))

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

wilcox_paired_ganancias <- function(y_a, y_b) {
  if (length(y_a) != length(y_b)) {
    stop("Vectores de distinta longitud para Wilcoxon emparejado.")
  }
  wt <- wilcox.test(
    y_a,
    y_b,
    paired = TRUE,
    exact = FALSE,
    alternative = "two.sided"
  )
  list(
    statistic = unname(wt$statistic),
    p.value = wt$p.value,
    mean_a = mean(y_a),
    mean_b = mean(y_b)
  )
}

merge_paired <- function(tb, rank_a, rank_b, envio_e, tipo_f = "public") {
  va <- tb[rank == rank_a & envios == envio_e & tipo == tipo_f, .(primo, ganancia)]
  vb <- tb[rank == rank_b & envios == envio_e & tipo == tipo_f, .(primo, ganancia)]
  merge(va, vb, by = "primo", suffixes = c("_a", "_b"))
}

TOP10_META <- file.path(ESTUDIO_DIR, "top10_hiperparametros.tsv")
if (!file.exists(TOP10_META)) {
  stop("No existe ", TOP10_META, " — ejecutar 6_produccion_top10_bo_semillas.R primero.")
}
tb_meta <- fread(TOP10_META)

semillas_path <- file.path(ESTUDIO_DIR, "semillas_train.txt")
if (!file.exists(semillas_path)) {
  stop("No existe ", semillas_path)
}
semillas_train <- as.integer(readLines(semillas_path, warn = FALSE))

rank_dirs <- sprintf("rank_%02d", seq_len(N_RANKS))
for (rd in rank_dirs) {
  pdir <- file.path(RANK_BASE, rd)
  if (!dir.exists(pdir)) {
    stop("Falta ", pdir, " — ejecutar script 6 primero.")
  }
  archivos <- list.files(pdir, pattern = "^cortes_ganancia_[0-9]+\\.txt$", full.names = TRUE)
  if (length(archivos) < N_SEMILLAS) {
    stop("En ", pdir, " hay ", length(archivos), " cortes; se esperan ", N_SEMILLAS, ".")
  }
}

tb_pieces <- vector("list", N_RANKS)
for (k in seq_len(N_RANKS)) {
  pdir <- file.path(RANK_BASE, rank_dirs[[k]])
  archivos <- list.files(pdir, pattern = "^cortes_ganancia_[0-9]+\\.txt$", full.names = TRUE)
  tb_k <- rbindlist(lapply(archivos, parse_cortes_primo))
  tb_k[, rank := k]
  tb_pieces[[k]] <- tb_k
}

tb_long <- rbindlist(tb_pieces)
tb_long[, tipo := factor(tipo, levels = c("public", "private"))]

if (!setequal(tb_long[tipo == "public", unique(primo)], semillas_train)) {
  stop("Primos en cortes no coinciden con semillas_train.txt")
}

fwrite(tb_long, file.path(ESTUDIO_DIR, "curvas_por_semilla.tsv"), sep = "\t")

tb_media_sd <- tb_long[, .(
  mean = mean(ganancia),
  sd = sd(ganancia),
  n = .N
), by = .(rank, envios, tipo)]

fwrite(tb_media_sd, file.path(ESTUDIO_DIR, "curvas_media_sd.tsv"), sep = "\t")

tb_public_mean <- tb_media_sd[tipo == "public"]
tb_rank_score <- tb_public_mean[, .(
  max_mean_public = max(mean),
  envios_argmax = envios[which.max(mean)]
), by = rank]

tb_rank_score <- merge(
  tb_rank_score,
  tb_meta[, .(rank, y_bo = y, iter_bo = iter)],
  by = "rank",
  all.x = TRUE
)
setorder(tb_rank_score, -max_mean_public)
fwrite(tb_rank_score, file.path(ESTUDIO_DIR, "ranking_por_max_public.tsv"), sep = "\t")

rank_ganador <- tb_rank_score[1L, rank]
rank_subcampeon <- tb_rank_score[2L, rank]
envios_argmax_ganador <- tb_rank_score[rank == rank_ganador, envios_argmax]
score_ganador <- tb_rank_score[1L, max_mean_public]
score_subcampeon <- tb_rank_score[2L, max_mean_public]

ganador_yaml <- list(
  rank_ganador = rank_ganador,
  rank_subcampeon = rank_subcampeon,
  envios_argmax_ganador = envios_argmax_ganador,
  max_mean_public_ganador = score_ganador,
  max_mean_public_subcampeon = score_subcampeon
)
write_yaml(ganador_yaml, file.path(ESTUDIO_DIR, "ganador.yml"))

cat(
  "Ganador rank=", rank_ganador,
  " envios_argmax=", envios_argmax_ganador,
  " | Subcampeon rank=", rank_subcampeon, "\n",
  sep = ""
)

envios_levels <- sort(unique(tb_long$envios))

tb_wx_mejor_segundo <- rbindlist(lapply(envios_levels, function(e) {
  m <- merge_paired(tb_long, rank_ganador, rank_subcampeon, e, "public")
  w <- wilcox_paired_ganancias(m$ganancia_a, m$ganancia_b)
  data.table(
    envios = e,
    rank_mejor = rank_ganador,
    rank_segundo = rank_subcampeon,
    statistic = w$statistic,
    p.value = w$p.value,
    mean_ganador = w$mean_a,
    mean_subcampeon = w$mean_b
  )
}))
fwrite(
  tb_wx_mejor_segundo,
  file.path(ESTUDIO_DIR, "wilcoxon_mejor_vs_segundo_public.tsv"),
  sep = "\t"
)

ranks_resto <- setdiff(seq_len(N_RANKS), rank_ganador)
tb_wx_top_resto <- rbindlist(lapply(envios_levels, function(e) {
  filas <- lapply(ranks_resto, function(j) {
    m <- merge_paired(tb_long, rank_ganador, j, e, "public")
    w <- wilcox_paired_ganancias(m$ganancia_a, m$ganancia_b)
    data.table(
      envios = e,
      rank_ganador = rank_ganador,
      rank_resto = j,
      statistic = w$statistic,
      p.value = w$p.value,
      mean_ganador = w$mean_a,
      mean_resto = w$mean_b
    )
  })
  tb_e <- rbindlist(filas)
  tb_e[, p_adj_holm := p.adjust(p.value, method = "holm")]
  tb_e
}))
fwrite(
  tb_wx_top_resto,
  file.path(ESTUDIO_DIR, "wilcoxon_top_vs_resto_por_rank.tsv"),
  sep = "\t"
)

tb_argmax_wx <- tb_wx_top_resto[envios == envios_argmax_ganador]
cat("\n--- Top vs resto en envios_argmax_ganador=", envios_argmax_ganador, " ---\n", sep = "")
print(tb_argmax_wx[, .(rank_resto, p.value, p_adj_holm, mean_ganador, mean_resto)])

aggregate_resto_por_semilla <- function(tb, envio_e, agg_fun) {
  wide <- dcast(
    tb[envios == envio_e & tipo == "public"],
    primo ~ rank,
    value.var = "ganancia"
  )
  cols_resto <- as.character(setdiff(seq_len(N_RANKS), rank_ganador))
  mat_resto <- as.matrix(wide[, ..cols_resto])
  y_top <- wide[[as.character(rank_ganador)]]
  if (identical(agg_fun, median)) {
    y_rest <- apply(mat_resto, 1L, median)
  } else {
    y_rest <- apply(mat_resto, 1L, max)
  }
  list(y_top = y_top, y_rest = y_rest, primo = wide$primo)
}

tb_wx_mediana <- rbindlist(lapply(envios_levels, function(e) {
  ag <- aggregate_resto_por_semilla(tb_long, e, median)
  w <- wilcox_paired_ganancias(ag$y_top, ag$y_rest)
  data.table(
    envios = e,
    comparador = "mediana_resto",
    statistic = w$statistic,
    p.value = w$p.value,
    mean_top = w$mean_a,
    mean_comparador = w$mean_b
  )
}))

tb_wx_max <- rbindlist(lapply(envios_levels, function(e) {
  ag <- aggregate_resto_por_semilla(tb_long, e, max)
  w <- wilcox_paired_ganancias(ag$y_top, ag$y_rest)
  data.table(
    envios = e,
    comparador = "max_resto",
    statistic = w$statistic,
    p.value = w$p.value,
    mean_top = w$mean_a,
    mean_comparador = w$mean_b
  )
}))

tb_wx_resto_agg <- rbindlist(list(tb_wx_mediana, tb_wx_max))
fwrite(
  tb_wx_resto_agg,
  file.path(ESTUDIO_DIR, "wilcoxon_top_vs_resto_mediana_public.tsv"),
  sep = "\t"
)

tb_winrate <- rbindlist(lapply(envios_levels, function(e) {
  filas <- lapply(ranks_resto, function(j) {
    m <- merge_paired(tb_long, rank_ganador, j, e, "public")
    wins <- sum(m$ganancia_a > m$ganancia_b)
    bt <- binom.test(wins, N_SEMILLAS, 0.5)
    data.table(
      envios = e,
      rank_resto = j,
      wins = wins,
      n = N_SEMILLAS,
      p_sign_exact = bt$p.value
    )
  })
  tb_e <- rbindlist(filas)
  tb_e[, p_adj_holm := p.adjust(p_sign_exact, method = "holm")]
  tb_e
}))
fwrite(tb_winrate, file.path(ESTUDIO_DIR, "winrate_top_vs_rank.tsv"), sep = "\t")

wins_argmax <- tb_winrate[envios == envios_argmax_ganador & wins == N_SEMILLAS, rank_resto]
cat(
  "Ranks con winrate 10/10 vs ganador en argmax:",
  if (length(wins_argmax) == 0L) "(ninguno)" else paste(wins_argmax, collapse = ", "),
  "\n"
)

tb_friedman <- NULL
if (isTRUE(DO_FRIEDMAN)) {
  tb_friedman <- rbindlist(lapply(envios_levels, function(e) {
    wide <- dcast(
      tb_long[envios == e & tipo == "public"],
      primo ~ rank,
      value.var = "ganancia"
    )
    mat <- as.matrix(wide[, as.character(seq_len(N_RANKS)), with = FALSE])
    ft <- friedman.test(mat)
    data.table(
      envios = e,
      statistic = unname(ft$statistic),
      p.value = ft$p.value,
      df = unname(ft$parameter)
    )
  }))
  fwrite(tb_friedman, file.path(ESTUDIO_DIR, "friedman_por_envio.tsv"), sep = "\t")
}

gra_top10 <- ggplot(
  tb_media_sd,
  aes(x = envios, y = mean, color = factor(rank), linetype = tipo)
) +
  geom_line(linewidth = 0.7) +
  scale_linetype_manual(
    values = c(public = "solid", private = "dashed"),
    labels = c(public = "Public", private = "Private")
  ) +
  labs(
    title = "Top-10 BO: ganancia media +/- sd por rank y semillas",
    x = "Envios",
    y = "Ganancia",
    color = "Rank",
    linetype = "Conjunto"
  ) +
  theme(text = element_text(size = 14))

ggsave(
  file.path(ESTUDIO_DIR, "curvas_top10_public_private_media_sd.pdf"),
  gra_top10,
  width = 16,
  height = 9
)

tb_cmp <- tb_media_sd[rank %in% c(rank_ganador, rank_subcampeon) & tipo == "public"]
gra_cmp <- ggplot(tb_cmp, aes(x = envios, y = mean, color = factor(rank))) +
  geom_line(linewidth = 1) +
  geom_ribbon(aes(ymin = mean - sd, ymax = mean + sd, fill = factor(rank)), alpha = 0.15, color = NA) +
  labs(
    title = "Ganador vs subcampeon (ganancia publica media +/- sd)",
    subtitle = paste0(
      "rank ", rank_ganador, " vs ", rank_subcampeon,
      " | argmax ganador envios=", envios_argmax_ganador
    ),
    x = "Envios",
    y = "Ganancia publica"
  ) +
  theme(text = element_text(size = 14))

ggsave(
  file.path(ESTUDIO_DIR, "curvas_mejor_vs_segundo_public.pdf"),
  gra_cmp,
  width = 16,
  height = 9
)

gra_wx12 <- ggplot(tb_wx_mejor_segundo, aes(x = envios, y = p.value)) +
  geom_line(linewidth = 1) +
  geom_point(size = 2) +
  geom_hline(yintercept = 0.05, linetype = "dashed", color = "gray40") +
  scale_y_continuous(limits = c(0, 1), expand = expansion(mult = c(0.02, 0.02))) +
  labs(
    title = paste0(
      "Wilcoxon signed-rank emparejado (dos colas): rank ganador vs subcampeon | ganancia Public | ",
      WILCOX_H0_LABEL, " | ", WILCOX_H1_LABEL
    ),
    x = "Envios",
    y = "p-value (escala lineal)"
  ) +
  theme(text = element_text(size = 14))

ggsave(
  file.path(ESTUDIO_DIR, "wilcoxon_pvalue_vs_envios.pdf"),
  gra_wx12,
  width = 16,
  height = 9
)

tb_heat <- copy(tb_wx_top_resto)
tb_heat[, rank_resto := factor(rank_resto)]
gra_heat <- ggplot(tb_heat, aes(x = envios, y = rank_resto, fill = p_adj_holm)) +
  geom_tile() +
  scale_fill_gradient(low = "darkred", high = "white", limits = c(0, 1)) +
  labs(
    title = paste0(
      "Wilcoxon signed-rank emparejado (dos colas): rank ganador vs cada rank del resto | ",
      "ganancia Public | p-value ajustado Holm (9 contrastes por envio) | ",
      WILCOX_H0_LABEL, " | ", WILCOX_H1_LABEL
    ),
    x = "Envios",
    y = "Rank resto",
    fill = "p_adj Holm (lineal)"
  ) +
  theme(text = element_text(size = 12))

ggsave(
  file.path(ESTUDIO_DIR, "heatmap_padj_top_vs_resto.pdf"),
  gra_heat,
  width = 16,
  height = 9
)

tb_winrate[, winrate := wins / n]
gra_win <- ggplot(tb_winrate, aes(x = envios, y = factor(rank_resto), fill = winrate)) +
  geom_tile() +
  scale_fill_gradient2(low = "blue", mid = "white", high = "red", midpoint = 0.5, limits = c(0, 1)) +
  labs(
    title = "Proporcion de semillas donde gana el rank top (public)",
    x = "Envios",
    y = "Rank resto",
    fill = "Winrate"
  ) +
  theme(text = element_text(size = 12))

ggsave(
  file.path(ESTUDIO_DIR, "winrate_heatmap.pdf"),
  gra_win,
  width = 16,
  height = 9
)

tb_med_plot <- tb_wx_mediana
gra_med <- ggplot(tb_med_plot, aes(x = envios, y = p.value)) +
  geom_line(linewidth = 1, color = "#2166ac") +
  geom_point(size = 2) +
  geom_hline(yintercept = 0.05, linetype = "dashed", color = "gray40") +
  scale_y_continuous(limits = c(0, 1), expand = expansion(mult = c(0.02, 0.02))) +
  labs(
    title = paste0(
      "Wilcoxon signed-rank emparejado (dos colas): rank ganador vs mediana del resto ",
      "(por semilla) | ganancia Public | ",
      WILCOX_H0_LABEL, " | ", WILCOX_H1_LABEL
    ),
    x = "Envios",
    y = "p-value (escala lineal)"
  ) +
  theme(text = element_text(size = 14))

ggsave(
  file.path(ESTUDIO_DIR, "wilcoxon_top_vs_mediana_resto.pdf"),
  gra_med,
  width = 16,
  height = 9
)

n_dominados_holm <- tb_argmax_wx[p_adj_holm < 0.05, .N]
n_dominados_win10 <- length(wins_argmax)

param_resumen <- list(
  interpretacion = paste(
    "Evidencia condicional al shortlist top-10 BO;",
    "ganador por max mean(ganancia publica) sobre cortes, no por AUC BO."
  ),
  rank_ganador = rank_ganador,
  rank_subcampeon = rank_subcampeon,
  envios_reporte_principal = envios_argmax_ganador,
  semillas_train = as.list(semillas_train),
  inferencia_primaria = list(
    metodo = "Wilcoxon emparejado top vs cada uno de 9 ranks",
    correccion = "Holm sobre 9 contrastes por envio",
    claim_fuerte_en = paste0("envios = ", envios_argmax_ganador)
  ),
  inferencia_secundaria = list(
    metodo = "Wilcoxon emparejado top vs mediana del resto por semilla",
    comparador_max_resto = "tabla wilcoxon_top_vs_resto_mediana_public.tsv fila max_resto"
  ),
  n_contrastes_top_vs_resto_por_envio = length(ranks_resto),
  n_envios = length(envios_levels),
  n_tests_wilcox_top_vs_resto_total = length(ranks_resto) * length(envios_levels),
  friedman_ejecutado = isTRUE(DO_FRIEDMAN),
  argmax_resumen = list(
    n_resto_p_adj_holm_lt_0_05 = n_dominados_holm,
    ranks_winrate_10_de_10 = as.list(wins_argmax)
  )
)

if (!is.null(tb_friedman)) {
  fr_argmax <- tb_friedman[envios == envios_argmax_ganador]
  param_resumen$friedman_en_argmax <- as.list(fr_argmax)
}

write_yaml(param_resumen, file.path(ESTUDIO_DIR, "PARAM_resumen.yml"))

cat("\nAnalisis escrito en ", ESTUDIO_DIR, "\n", sep = "")

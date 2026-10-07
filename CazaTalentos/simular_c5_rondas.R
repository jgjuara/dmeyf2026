# Cazatalentos 5 — proyeccion con sesiones de 100 tiros
#
# A partir de las 10 rondas observadas (701/1000), estima p y simula:
#   - 100 intentos de 100 tiros cada uno
#   - 200 intentos de 100 tiros cada uno
#
# Supuestos:
# - p = 701/1000 (tasa muestral de las 10 rondas).
# - Cada intento es una sesion independiente de 100 tiros Bernoulli(p).

set.seed(102191)

RONDAS_OBSERVADAS <- c(68L, 74L, 78L, 70L, 68L, 63L, 80L, 68L, 67L, 65L)
TOTAL_ENCESTES <- sum(RONDAS_OBSERVADAS)
TIROS_POR_SESION <- 100L
P <- TOTAL_ENCESTES / (length(RONDAS_OBSERVADAS) * TIROS_POR_SESION)

N_INTENTOS <- c(`100 intentos` = 100L, `200 intentos` = 200L)
UMBRAL <- 80L

simular_bloque <- function(n_intentos, p, tiros) {
  encestes <- rbinom(n_intentos, tiros, p)
  list(
    encestes = encestes,
    n_con_80_o_mas = sum(encestes >= UMBRAL),
    max_encestes = max(encestes),
    prob_un_intento = 1 - pbinom(UMBRAL - 1L, tiros, p),
    prob_al_menos_uno = 1 - (1 - (1 - pbinom(UMBRAL - 1L, tiros, p)))^n_intentos
  )
}

reportar_bloque <- function(etiqueta, res) {
  cat("\n=== ", etiqueta, " (", length(res$encestes),
      " sesiones de ", TIROS_POR_SESION, " tiros) ===\n", sep = "")
  cat("p usado:", round(P, 4), "\n")
  cat("Encestes por sesion:", paste(head(res$encestes, 20), collapse = ", "))
  if (length(res$encestes) > 20L) {
    cat(", ...")
  }
  cat("\n")
  cat("Sesiones con >= ", UMBRAL, " encestes: ", res$n_con_80_o_mas,
      " de ", length(res$encestes), "\n", sep = "")
  cat("Maximo encestes en el bloque:", res$max_encestes, "\n")
  cat("Media de encestes:", round(mean(res$encestes), 2), "\n")
  cat("P(>= ", UMBRAL, " en un intento | p): ",
      round(res$prob_un_intento, 4), "\n", sep = "")
  cat("P(al menos una sesion >= ", UMBRAL, " | ", length(res$encestes),
      " intentos): ", round(res$prob_al_menos_uno, 4), "\n", sep = "")
}

cat("Datos observados (Cazatalentos 5)\n")
cat("Rondas:", paste(RONDAS_OBSERVADAS, collapse = ", "), "\n")
cat("Total:", TOTAL_ENCESTES, "encestes en", length(RONDAS_OBSERVADAS) * TIROS_POR_SESION, "tiros\n")
cat("Tasa p =", P, "\n")
cat("En las 10 rondas reales, sesiones con >= 80:", sum(RONDAS_OBSERVADAS >= UMBRAL), "de 10\n")

for (nombre in names(N_INTENTOS)) {
  res <- simular_bloque(N_INTENTOS[[nombre]], P, TIROS_POR_SESION)
  reportar_bloque(nombre, res)
}

cat("\n")
cat("Lectura: con p ~ 0.701, una sesion de 100 tiros rara vez alcanza 80.\n")
cat("Pero al repetir 100 o 200 veces, es probable aparecer al menos una sesion de 80+,\n")
cat("como hizo la cazatalentos al elegir la mejor de 10 rondas.\n")

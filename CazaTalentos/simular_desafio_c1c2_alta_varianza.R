# Desafio Cazatalentos: C1 y C2 con p heterogeneos y sigma variable.
# Mantiene el recuento del enunciado (maximo unico igual a 80) y estima,
# para cada sigma, la media del pueblo y el p de la candidata.
#
# Cantidades:
# - mu: centro del pueblo, mu ~ Unif[0, P_MAX)
# - p_bar: media realizada de los p_i del pueblo
# - p_star: p de la unica jugadora con 80 encestes
#
# Supuestos:
# - p_i ~ N(mu, sigma) truncada a (0, P_MAX). Taurasi (0.85) es estrictamente
#   superior a todas las evaluadas.
# - Cada tiro es independiente: X_j ~ Bin(TIROS, p_j).
# - Se acepta un pueblo solo si max X = 80 y el maximo es unico.

set.seed(102191)

encestes_grupo <- function(probs, qty) {
  rbinom(length(probs), qty, probs)
}

P_MAX <- 0.85
TIROS <- 100
N_ACEPTADOS <- 10000
SIGMAS <- c(0.02, 0.08, 0.15)

# Normal truncada por rechazo (misma ley que rnorm, restringida al intervalo).
rnorm_trunc <- function(n, mean, sd, lo, hi) {
  out <- numeric(n)
  llenos <- 0L
  while (llenos < n) {
    z <- rnorm(n - llenos, mean, sd)
    z <- z[z > lo & z < hi]
    if (length(z) == 0L) {
      next
    }
    tomar <- min(length(z), n - llenos)
    out[(llenos + 1L):(llenos + tomar)] <- z[seq_len(tomar)]
    llenos <- llenos + tomar
  }
  out
}

generar_pueblo <- function(n, sigma) {
  mu <- runif(1, min = 0, max = P_MAX)
  p <- rnorm_trunc(n, mu, sigma, lo = 0, hi = P_MAX)
  list(mu = mu, p = p)
}

# Devuelve mu, p_bar y p_star si el pueblo reproduce el recuento; si no, NULL.
sim_maximo_unico_80 <- function(n_jugadoras, sigma) {
  pueblo <- generar_pueblo(n_jugadoras, sigma)
  vaciertos <- encestes_grupo(pueblo$p, TIROS)
  mejor <- which.max(vaciertos)
  if (vaciertos[mejor] != 80) {
    return(NULL)
  }
  if (sum(vaciertos == 80) != 1) {
    return(NULL)
  }
  list(
    mu = pueblo$mu,
    p_bar = mean(pueblo$p),
    p_star = pueblo$p[mejor]
  )
}

recolectar <- function(n_jugadoras, sigma, n_aceptados) {
  mu <- numeric(n_aceptados)
  p_bar <- numeric(n_aceptados)
  p_star <- numeric(n_aceptados)
  n <- 0
  intentos <- 0
  while (n < n_aceptados) {
    intentos <- intentos + 1
    rec <- sim_maximo_unico_80(n_jugadoras, sigma)
    if (!is.null(rec)) {
      n <- n + 1
      mu[n] <- rec$mu
      p_bar[n] <- rec$p_bar
      p_star[n] <- rec$p_star
    }
  }
  list(mu = mu, p_bar = p_bar, p_star = p_star, intentos = intentos)
}

casos <- list(
  C1 = 100,
  C2 = 200
)

n_filas <- length(casos) * length(SIGMAS)
resultados <- data.frame(
  caso = character(n_filas),
  sigma = numeric(n_filas),
  E_mu = numeric(n_filas),
  E_p_bar = numeric(n_filas),
  E_p_star = numeric(n_filas),
  intentos = integer(n_filas),
  stringsAsFactors = FALSE
)

k <- 0
for (nombre in names(casos)) {
  n_jugadoras <- casos[[nombre]]
  for (sigma in SIGMAS) {
    k <- k + 1
    cat("Simulando ", nombre, " sigma=", sigma, " ...\n", sep = "")
    rec <- recolectar(n_jugadoras, sigma, N_ACEPTADOS)
    resultados$caso[k] <- nombre
    resultados$sigma[k] <- sigma
    resultados$E_mu[k] <- mean(rec$mu)
    resultados$E_p_bar[k] <- mean(rec$p_bar)
    resultados$E_p_star[k] <- mean(rec$p_star)
    resultados$intentos[k] <- rec$intentos
  }
}

cat("\n")
cat("Pueblos aceptados por celda: ", N_ACEPTADOS, "\n", sep = "")
cat("Prior de mu: Unif[0, ", P_MAX, ")\n", sep = "")
print(transform(
  resultados,
  E_mu = round(E_mu, 4),
  E_p_bar = round(E_p_bar, 4),
  E_p_star = round(E_p_star, 4)
), row.names = FALSE)

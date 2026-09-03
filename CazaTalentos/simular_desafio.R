# Desafio Cazatalentos Ordenamiento
# Simula los procedimientos del enunciado (secciones 4.1-4.2) y estima, para cada
# candidata, el valor esperado de encestes en una nueva ronda de 100 tiros.
#
# Ci < Cj  sii  P( encestes_Ci < encestes_Cj | 100 tiros ) > 0.5
#
# Supuestos:
# - Cada pueblo tiene un unico indice de enceste p desconocido, compartido por
#   todas las adolescentes de ese pueblo. Distintos pueblos son independientes.
#   Esto replica el bloque del script original con jugadoras <- rep(p, n).
# - p se genera con runif en [0, 0.85). Taurasi (0.85) es estrictamente superior
#   a todas las evaluadas.
# - Cada tiro es independiente: acierto sii runif(1) < p, via ftirar.
# - Se acepta un experimento solo si reproduce el recuento del enunciado.
# - En C5 la entrenadora conoce las 10 rondas; el estadistico suficiente es la
#   suma 701 encestes en 1000 tiros.

set.seed(102191)

# calcula cuantos encestes logra una jugadora con indice de enceste prob
# haciendo qty tiros libres
ftirar <- function(prob, qty) {
  return(sum(runif(qty) < prob))
}

# n jugadoras con el mismo p, qty tiros independientes cada una.
# rbinom(n, qty, p) cuenta aciertos Bernoulli; es la misma ley que
# mapply(ftirar, rep(p, n), qty).
encestes_grupo <- function(prob, qty, n) {
  rbinom(n, qty, prob)
}

P_MAX <- 0.85
TIROS <- 100
N_ACEPTADOS <- 10000

generar_p <- function() {
  runif(1, min = 0, max = P_MAX)
}

# recolecta N_ACEPTADOS valores de p que pasan el filtro del caso
recolectar_p <- function(sim_una, n_aceptados) {
  p_ok <- numeric(n_aceptados)
  n <- 0
  intentos <- 0
  while (n < n_aceptados) {
    intentos <- intentos + 1
    p <- sim_una()
    if (!is.na(p)) {
      n <- n + 1
      p_ok[n] <- p
    }
  }
  list(p = p_ok, intentos = intentos)
}


# Cazatalentos 1: 100 adolescentes, 100 tiros cada una.
# Solo una obtuvo 80; esa es la candidata.
sim_c1 <- function() {
  p <- generar_p()
  vaciertos <- encestes_grupo(p, TIROS, 100)
  mejor <- which.max(vaciertos)
  if (vaciertos[mejor] != 80) {
    return(NA_real_)
  }
  if (sum(vaciertos == 80) != 1) {
    return(NA_real_)
  }
  p
}


# Cazatalentos 2: 200 adolescentes, 100 tiros cada una.
# Solo una obtuvo 80; esa es la candidata.
sim_c2 <- function() {
  p <- generar_p()
  vaciertos <- encestes_grupo(p, TIROS, 200)
  mejor <- which.max(vaciertos)
  if (vaciertos[mejor] != 80) {
    return(NA_real_)
  }
  if (sum(vaciertos == 80) != 1) {
    return(NA_real_)
  }
  p
}


# Cazatalentos 3: elige a la numero 13 sin verla tirar, luego 100 tiros, 80 aciertos.
# La eleccion no depende del resultado; 80/100 no esta sesgado por maximo.
sim_c3 <- function() {
  p <- generar_p()
  aciertos <- ftirar(p, TIROS)
  if (aciertos != 80) {
    return(NA_real_)
  }
  p
}


# Cazatalentos 4: 2 adolescentes, 100 tiros cada una, 80 y 75. Candidata: la de 80.
sim_c4 <- function() {
  p <- generar_p()
  vaciertos <- encestes_grupo(p, TIROS, 2)
  if (max(vaciertos) != 80) {
    return(NA_real_)
  }
  if (min(vaciertos) != 75) {
    return(NA_real_)
  }
  p
}


# Cazatalentos 5: una sola adolescente, 10 rondas de 100. La entrenadora conoce
# la tabla completa (suma 701). La candidata no es "la de 80", es la misma
# jugadora evaluada con las 10 rondas.
sim_c5 <- function() {
  p <- generar_p()
  rondas <- encestes_grupo(p, TIROS, 10)
  if (sum(rondas) != 701) {
    return(NA_real_)
  }
  p
}


# Cazatalentos 6: elige a la numero 43 de antemano; esa hizo 79 de 100.
sim_c6 <- function() {
  p <- generar_p()
  aciertos <- ftirar(p, TIROS)
  if (aciertos != 79) {
    return(NA_real_)
  }
  p
}


# Cazatalentos 7: candidata del paraje, unica adolescente, 79 de 100.
# Independiente del torneo de 100 que habia dejado en 80.
sim_c7 <- function() {
  p <- generar_p()
  aciertos <- ftirar(p, TIROS)
  if (aciertos != 79) {
    return(NA_real_)
  }
  p
}


casos <- list(
  C1 = sim_c1,
  C2 = sim_c2,
  C3 = sim_c3,
  C4 = sim_c4,
  C5 = sim_c5,
  C6 = sim_c6,
  C7 = sim_c7
)

p_posterior <- list()
intentos_por_caso <- integer(length(casos))
names(intentos_por_caso) <- names(casos)

for (nombre in names(casos)) {
  cat("Simulando ", nombre, " ...\n", sep = "")
  rec <- recolectar_p(casos[[nombre]], N_ACEPTADOS)
  p_posterior[[nombre]] <- rec$p
  intentos_por_caso[[nombre]] <- rec$intentos
}

# Nueva ronda en la gran ciudad: 100 tiros de cada candidata (su p del pueblo)
nueva_ronda <- list()
for (nombre in names(p_posterior)) {
  nueva_ronda[[nombre]] <- vapply(
    p_posterior[[nombre]],
    ftirar,
    integer(1),
    qty = TIROS
  )
}

cat("\n")
cat("Intentos hasta reunir ", N_ACEPTADOS, " pueblos compatibles con el enunciado\n", sep = "")
print(intentos_por_caso)

cat("\n")
cat("Candidata", "\t", "E[p]", "\t", "E[encestes nueva ronda]", "\n", sep = "")
medias_p <- sapply(p_posterior, mean)
medias_nueva <- sapply(nueva_ronda, mean)
for (nombre in names(casos)) {
  cat(nombre, "\t\t", round(medias_p[[nombre]], 4), "\t", round(medias_nueva[[nombre]], 4), "\n", sep = "")
}

# Comparaciones a pares: P(encestes_Ci < encestes_Cj) en la nueva ronda
cat("\n")
cat("P(encestes_fila < encestes_columna) en 100 tiros de la gran ciudad\n")
nombres <- names(casos)
n_casos <- length(nombres)
prob_menor <- matrix(NA_real_, n_casos, n_casos, dimnames = list(nombres, nombres))
for (i in seq_len(n_casos)) {
  for (j in seq_len(n_casos)) {
    if (i == j) {
      prob_menor[i, j] <- 0.5
    } else {
      prob_menor[i, j] <- mean(nueva_ronda[[nombres[i]]] < nueva_ronda[[nombres[j]]])
    }
  }
}
print(round(prob_menor, 4))

# Ordenamiento: Ci < Cj si la probabilidad de menos encestes supera 0.5
orden <- names(sort(medias_nueva))
cat("\n")
cat("Ordenamiento por E[encestes] en la nueva ronda de 100 tiros:\n")
cat(paste(orden, collapse = " < "), "\n")

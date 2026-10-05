# 01_full_fe

**Alcance:** nocontinuas + todos los lags nocontinuas + rankings del mes, lag1, lag2, delta1 y delta2 (FE completo para LGB).

**Capas parquet** (orden de join sugerido; ver `compe1_layers("01_full_fe")`):

- `competencia_01_nocontinuas.parquet`
- `competencia_01_nocontinuas_lag1.parquet`
- `competencia_01_nocontinuas_lag2.parquet`
- `rankings.parquet`
- `rankings_lag1.parquet`
- `rankings_lag2.parquet`
- `rankings_delta1.parquet`
- `rankings_delta2.parquet`

**RESULTADOS_DIR:** `juara/compe1/01_full_fe/00/resultados/` (creado por los scripts en `00/`).

Scripts futuros: `juara/compe1/01_full_fe/00/`.

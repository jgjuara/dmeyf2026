# Informe descriptivo: CONTINUA (20% por mes, junio 2021)

Generado: 2026-10-04 15:38 UTC

Fuente: `dataset_continua_20_junio.parquet` (construido con `prep/join_continua_20_junio.py`).

## 1. Criterios de selección

| regla | descripcion |
| --- | --- |
| mes | foto_mes % 100 = 6 (junio 2021) |
| clase | solo CONTINUA |
| muestra | 20% de casos por foto_mes (ceil(n×0.2), hash reproducible) |
| clave_grano | (numero_de_cliente, foto_mes) único por fila |
| analisis | cohorte unificada CONTINUA muestreada |

Cohorte `CONTINUA` en junio 2021; el join aplica ~20% de casos **por** `foto_mes` (misma lógica que `join_continua_20_junio.py`).

## 2. Volumen y grano

| metrica | valor |
| --- | --- |
| filas | 32429 |
| columnas | 711 |
| clientes_distintos | 32429 |
| foto_mes_distintos | 1 |

32429 observaciones cliente–mes (`CONTINUA`); 32429 clientes distintos (32429 con una sola foto en la muestra).

### Conteo por foto_mes

| foto_mes | n_casos |
| --- | --- |
| 202106 | 32429 |

- `202106`: 32429 casos.

![Conteos por foto_mes](plots/conteos_foto_mes.png)

## 3. Validación del parquet

| chequeo | ok | detalle |
| --- | --- | --- |
| filas_igual_suma_por_mes | True | 32429 vs 32429 |
| claves_unicas | True | duplicados=0 |
| solo_junio | True | [202106] |
| columnas_esperadas_711 | True | 711 |
| solo_clase_continua | True | 32429/32429 |
| clientes_distintos_leq_filas | True | clientes=32429, filas=32429 |

## 4. Estructura de columnas

| grupo | n_columnas |
| --- | --- |
| claves | 3 |
| nocontinuas_base | 26 |
| nocontinuas_lag1 | 26 |
| nocontinuas_lag2 | 26 |
| rankings_delta1_pct | 126 |
| rankings_delta2_pct | 126 |
| rankings_lag1_pct | 126 |
| rankings_lag2_pct | 126 |
| rankings_pct | 126 |

Las columnas `pct_*` son `PERCENT_RANK` **por** `foto_mes` (ver `build_rankings.py`). No se promedian entre meses en una sola escala: los estadísticos de la sección 6 se calculan por `foto_mes`. Los prefijos `lag1_` / `lag2_` y `delta1_pct_` / `delta2_pct_` provienen de capas de historia y variación.

## 5. Variables nocontinuas (capa base)

Flags estrictamente 0/1 (`max_val <= 1` en la cohorte); las doce mayores prevalencias:

| variable | prevalencia |
| --- | --- |
| active_quarter | 0.990 |
| cdescubierto_preacordado | 0.968 |
| cmobile_app_trx | 0.769 |
| thomebanking | 0.728 |
| tcallcenter | 0.085 |
| ccajas_transacciones | 0.080 |
| tmobile_app | 0.028 |
| Visa_delinquency | 0.006 |
| cliente_vip | 0.006 |
| Master_delinquency | 0.004 |

Variables con valores múltiples (media y máximo en la cohorte):

| variable | media | max_val |
| --- | --- | --- |
| ctarjeta_debito | 1.485 | 13 |
| tcuentas | 1.004 | 2 |
| ccuenta_corriente | 1.003 | 2 |
| ctarjeta_visa | 0.956 | 3 |
| ctarjeta_master | 0.900 | 2 |
| cseguro_accidentes_personales | 0.137 | 5 |
| cseguro_vivienda | 0.131 | 4 |
| cseguro_vida | 0.116 | 3 |

![Prevalencia flags 0/1](plots/prevalencia_flags_01.png)

Medias y prevalencias por `foto_mes` y cohorte `todos` (variables brutas): `tablas/resumen_nocontinuas.csv`.

## 6. Percentiles de variables continuas

Por `foto_mes` (cada valor `pct_*` es relativo al universo de competencia de ese mes):

| foto_mes | variable | media | p50 | p90 |
| --- | --- | --- | --- | --- |
| 202106 | pct_chomebanking_transacciones | 0.487 | 0.496 | 0.902 |
| 202106 | pct_cliente_antiguedad | 0.497 | 0.499 | 0.900 |
| 202106 | pct_cliente_edad | 0.487 | 0.482 | 0.889 |
| 202106 | pct_cproductos | 0.398 | 0.238 | 0.775 |
| 202106 | pct_ctrx_quarter | 0.504 | 0.506 | 0.901 |
| 202106 | pct_mautoservicio | 0.464 | 0.507 | 0.900 |
| 202106 | pct_mcomisiones | 0.500 | 0.497 | 0.901 |
| 202106 | pct_mcuentas_saldo | 0.503 | 0.505 | 0.899 |
| 202106 | pct_mpayroll | 0.401 | 0.505 | 0.900 |
| 202106 | pct_mrentabilidad | 0.500 | 0.500 | 0.900 |
| 202106 | pct_mrentabilidad_annual | 0.500 | 0.500 | 0.900 |

No son montos absolutos. Mezclar filas de distintos `foto_mes` en un solo histograma o media global distorsionaría la interpretación.

![Histogramas por foto_mes](plots/hist_pct_por_foto_mes.png)

Tabla completa: `tablas/percentiles_variables_pct.csv`.

## 7. Ejecución

Desde `juara/miranda/junio/`:

```bash
uv run python prep/join_continua_20_junio.py
cd pipelines/describe_casos && uv run python run_descriptivo_continua_20.py
```

| Artefacto | Descripción |
| --- | --- |
| `tablas/*.csv` | Tablas del análisis |
| `plots/*.png` | Gráficos referenciados |
| `informe_casos_continua_20_junio.md` | Este informe |

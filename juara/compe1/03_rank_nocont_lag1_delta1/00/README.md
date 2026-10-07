# Scripts — `03_rank_nocont_lag1_delta1/00`

Protocolo del experimento 2103 (ventana, split, BO, ganancia): [`../README.md`](../README.md).

Salidas bajo `resultados/` (`HT2103/`, `exp2103/`, `exp2103_top20/`, `exp2103_agosto/`, `estudio/top20_bo_semillas/`).

## Pipeline (orden lógico)

```text
1_bayesiana          → resultados/HT2103/
2_produccion         → resultados/exp2103/
3_escalar_ganancia   → resultados/exp2103/   (opcional)
4_top20_semillas     → resultados/exp2103_top20/rank_XX/
5_analisis_top20     → resultados/estudio/top20_bo_semillas/
6_agosto_semillas    → resultados/exp2103_agosto/
```

**Orden sugerido:** `1` → `2` → (`3` opcional) → `4` → `5` → `6` (en `6_`, `RANKS_BO` acorde al ganador de `5_`).

## Convenciones comunes

| Bloque | Contenido |
|--------|-----------|
| Anclaje | `here::i_am(...)` + `source` de `compe1_layers.R` y `compe1_data.R` (salvo `5_`, que no usa `compe1_data.R`) |
| Constantes | `EXPERIMENT_ID`, `RESULTADOS_DIR`, `EXPERIMENTO <- 2103L`, rutas bajo `resultados/` |
| Datos | `compe1_read_joined(EXPERIMENT_ID, foto_mes = ...)`; target `clase01` vía `clase_ternaria` o `compe1_clase01` |
| Partición | `particionar(...)` con `PARAM$holdout` y `semilla_primigenia` (salvo `6_`, que no hace holdout) |

Utilidades: [`../../common/compe1_data.R`](../../common/compe1_data.R), [`../../common/compe1_layers.R`](../../common/compe1_layers.R).

---

### `1_bayesiana_lightgbm.R`

| | |
|--|--|
| **Rol** | Optimización bayesiana (mlrMBO) de 4 HP LightGBM; objetivo = AUC medio de `lgb.cv` con 2 folds en el 70 % dev. |
| **Requiere** | Parquets del experimento; sin salidas previas. |
| **Escribe** | `resultados/HT2103/bayesiana.RDATA`, `BO_log.txt`, `PARAM.yml` |

**Flujo**

1. Define `PARAM` (ventana mar–jun, cortes, undersampling 0,1, `param_fijos` LGBM, espacio MBO: `num_iterations`, `num_leaves`, `min_data_in_leaf`, `min_sum_hessian_in_leaf` lineal [0,001–0,01]).
2. Carga dataset, `clase01`, `particionar`, `compe1_aplicar_undersampling_train` solo en `fold_train`.
3. `compe1_campos_buenos` → `lgb.Dataset` con filas `fold == fold_train & training == 1`.
4. Función objetivo `EstimarGanancia_AUC_lightgbm` → `compe1_lgb_cv_best_auc`; logging por evaluación.
5. `mbo` / `mboContinue` sobre checkpoint `bayesiana.RDATA` (`COMPE1_BO_ITER`, default 500).
6. Ordena path por `y`, guarda log completo; mejor fila → `PARAM$out$lgbm$mejores_hiperparametros` + `campos_buenos` en YAML.

**No hace:** train final, test 30 %, ganancia por envíos.

---

### `2_produccion_lightgbm.R`

| | |
|--|--|
| **Rol** | Un solo HP (mejor de BO): entrena en 70 % completo y evalúa holdout 30 %. |
| **Requiere** | `resultados/HT2103/PARAM.yml` (`1_`). |
| **Escribe** | `resultados/exp2103/impo.txt`, `modelo.txt`, `prediccion.txt`, `curva_ganancia.pdf`, `cortes_ganancia.txt`, `PARAM.yml` |

**Flujo**

1. Lee YAML; reproduce partición con mismos `foto_mes` y semilla.
2. `modifyList(param_fijos, mejores_hiperparametros)` + `compe1_decodificar_min_sum_hessian`.
3. Reescala `min_data_in_leaf` ÷ `undersampling` (0,1); `lgb.train` sin undersampling en filas.
4. Importancia y modelo en disco; `predict` en `fold_test`.
5. Curva de ganancia acumulada (top 30k por `prob`); bucle de cortes `PARAM$cortes` con regla BAJA+2 / resto.

**No hace:** BO, top-20, escalado mensual (eso es `3_`).

---

### `3_escalar_ganancia_mes.R`

| | |
|--|--|
| **Rol** | Convierte ganancia del holdout a “mes completo” y promedia mar–jun por corte de envíos. |
| **Requiere** | `resultados/exp2103/prediccion.txt` y `PARAM.yml` (`2_`); si falta prod YAML, usa `HT2103/PARAM.yml`. |
| **Escribe** | `cortes_ganancia_por_mes_escalada.tsv`, `cortes_ganancia_escalada_promedio_mes.txt` en `exp2103/` |

**Flujo**

1. `compe1_preparar_holdout_split` para alinear test con la partición original.
2. Join `prediccion.txt` por `(numero_de_cliente, foto_mes)`.
3. Por cada `foto_mes` en test y cada corte: `compe1_ganancia_envio` → `compe1_escalar_ganancia_mes` (ratio `n_total` / `n_test`).
4. Agrega media de `gan_escalada_mes` por `envios`.

**No hace:** entrenamiento ni inferencia estadística.

---

### `4_produccion_top20_bo_semillas.R`

| | |
|--|--|
| **Rol** | Replica los 20 mejores HP de `BO_log.txt`, cada uno con 10 semillas-primo; métrica oficial = prob media en holdout. |
| **Requiere** | `HT2103/PARAM.yml`, `BO_log.txt` (`1_`). |
| **Escribe** | `estudio/top20_bo_semillas/top20_hiperparametros.tsv`, `semillas_train.txt`; por `exp2103_top20/rank_XX/`: 10× `modelo_<primo>.txt`, `prediccion_<primo>.txt`, `cortes_ganancia_<primo>.txt`; agregado `prediccion_media.txt`, `curva_ganancia_media.pdf`, `cortes_ganancia_media.txt` / `.tsv`, `PARAM.yml` |

**Funciones internas**

| Función | Uso |
|---------|-----|
| `hp_de_fila` | Extrae los 4 HP de una fila del log |
| `escribir_curva_cortes_media` | Tras promediar 10 probs: `prediccion_media.txt`, PDF/TXT/TSV de cortes agregados |
| `producir_primos_en_dir` | Bucle 10×: train, impo, modelo, predicción, curva y cortes por primo; luego media de probabilidades |

**Flujo global**

1. Cabecera top-20 y semillas (`compe1_semillas_primos`).
2. Dataset + partición; un `lgb.Dataset` del 70 % reutilizado en el bucle `k = 1..20`.
3. Por rank: `producir_primos_en_dir` + `PARAM.yml` con metadata BO (`top20_bo`, `semillas_train`).

**Detalle clave:** la ganancia “oficial” del rank promedia probabilidades **antes** de ordenar y cortar (`escribir_curva_cortes_media`).

---

### `5_analisis_top20_bo_semillas.R`

| | |
|--|--|
| **Rol** | Post hoc sobre cortes holdout por semilla; elige ganador y contrastes Wilcoxon/Holm; sin `lgb.train`. |
| **Requiere** | Salida completa de `4_` (`cortes_ganancia_<primo>.txt`, `cortes_ganancia_media.txt`, meta en `estudio/`). |
| **Escribe** | Tablas TSV, `ganador.yml`, `PARAM_resumen.yml`, PDFs en `estudio/top20_bo_semillas/` |

**Funciones internas**

| Función | Uso |
|---------|-----|
| `parse_cortes_primo` | Lee TXT de cortes por semilla → `data.table(primo, envios, ganancia)` |
| `parse_cortes_media` | Lee `cortes_ganancia_media.txt` |
| `wilcox_paired_ganancias` | Wilcoxon emparejado bilateral |
| `merge_paired` | Alinea ganancias por `primo` entre dos ranks y un `envios` |
| `aggregate_resto_por_semilla` | Mediana o máximo del resto de ranks por semilla (para contrastes agregados) |

**Flujo**

1. Valida 20 directorios y 10 archivos `cortes_ganancia_*.txt` por rank; arma `tb_long`.
2. Media/SD por rank y envío; **ranking** = `max(mean(ganancia))` en holdout → `ranking_por_max_holdout.tsv`, `ganador.yml`.
3. Wilcoxon: ganador vs subcampeón; ganador vs cada uno de 19 (Holm); vs mediana/máximo del resto; winrate + sign test; Friedman opcional (`DO_FRIEDMAN`).
4. Gráficos (curvas top-20, ganador vs 2º, p-values, heatmaps).
5. Curvas de `prob_media` parseadas a `curvas_prob_media_por_rank.tsv`.

---

### `6_prediccion_agosto_top20_semillas.R`

| | |
|--|--|
| **Rol** | Producción agosto: train en mar–jun **completo** (sin split 70/30), predict `foto_mes = 202108`. |
| **Requiere** | `HT2103/PARAM.yml`; `top20_hiperparametros.tsv` o `BO_log.txt`. |
| **Config en script** | `RANKS_BO` (default `3L`; admite varios ranks → media conjunta); `FOTO_MES_TRAIN` / `FOTO_MES_PRED`. |
| **Escribe** | `exp2103_agosto/prediccion_agosto_media.tsv`, `prediccion_agosto_media_ordenada.tsv`, `modelo_XX_<semilla>_20210801.tsv`, `meta.yml` |

**Flujo**

1. Filtra ranks BO; mismas 10 semillas-primo que `4_`.
2. Lee train + agosto en un solo `compe1_read_joined`; un `lgb.Dataset` de entrenamiento.
3. Bucle rank × semilla: train, predict agosto, TSV individual; acumula `prob_sum`.
4. `prob = prob_sum / n_modelos`; salida ordenada y YAML de metadatos.

**No hace:** holdout, ganancia, Wilcoxon. El script actual no escribe `prediccion_agosto_por_rank_semilla.tsv` (sí TSV por par rank×semilla y la media).

# Scripts — `00/00`

Protocolo del experimento 1990 (ventana, split temporal, BO, ganancia): [`../README.md`](../README.md).

Salidas bajo `resultados/` (`HT1990/`, `exp1990/`, `exp1990_top20/`, `exp1990_agosto/`, `estudio/top20_bo_semillas/`).

## Pipeline (orden lógico)

```text
1_bayesiana          → resultados/HT1990/
2_produccion         → resultados/exp1990/
4_top20_semillas     → resultados/exp1990_top20/rank_XX/
5_analisis_top20     → resultados/estudio/top20_bo_semillas/
6_agosto_semillas    → resultados/exp1990_agosto/
```

**Orden sugerido:** `1` → `2` → `4` → `5` → `6` (en `6_`, `RANKS_BO` acorde al ganador de `5_`).

## Convenciones comunes

| Bloque | Contenido |
|--------|-----------|
| Anclaje | `here::i_am(...)` + `source` de `compe1_layers.R` y `compe1_data.R` (salvo `5_`, que no usa `compe1_data.R`) |
| Constantes | `EXPERIMENT_ID`, `RESULTADOS_DIR`, `EXPERIMENTO <- 1990L`, rutas bajo `resultados/` |
| Datos | `compe1_read_joined(EXPERIMENT_ID, foto_mes = ...)`; target `clase01` vía `clase_ternaria` o `compe1_clase01` |
| Partición | `compe1_asignar_fold_temporal_mar_may_jun` / `compe1_reproducir_holdout` según `PARAM$holdout$tipo` (salvo `6_`, que no hace holdout) |

Utilidades: [`../../common/compe1_data.R`](../../common/compe1_data.R), [`../../common/compe1_layers.R`](../../common/compe1_layers.R).

---

### `1_bayesiana_lightgbm.R`

| | |
|--|--|
| **Rol** | Optimización bayesiana (mlrMBO) de 3 HP (`num_iterations`, `num_leaves`, `min_sum_hessian_in_leaf`); `min_data_in_leaf` fijo; objetivo = media AUC de 2 folds temporales en train mar–may. |
| **Requiere** | Parquets del experimento; sin salidas previas. |
| **Escribe** | `resultados/HT1990/bayesiana.RDATA`, `BO_log.txt`, `PARAM.yml` |

**Flujo**

1. Define `PARAM` (ventana mar–jun, cortes, sin undersampling, holdout temporal, espacio MBO).
2. Carga dataset, `clase01`, `compe1_asignar_fold_temporal_mar_may_jun`.
3. Función objetivo → `compe1_lgb_temporal_cv_auc_mar_may` (mar→abr, mar–abr→may).
4. `mbo` / `mboContinue` sobre checkpoint `bayesiana.RDATA` (`COMPE1_BO_ITER`, default 200).
5. Mejor fila → `PARAM$out$lgbm$mejores_hiperparametros` + `campos_buenos` en YAML.

**No hace:** train final, test junio, ganancia por envíos.

---

### `2_produccion_lightgbm.R`

| | |
|--|--|
| **Rol** | Un solo HP (mejor de BO): entrena en mar–may y evalúa junio (test). |
| **Requiere** | `resultados/HT1990/PARAM.yml` (`1_`). |
| **Escribe** | `resultados/exp1990/impo.txt`, `modelo.txt`, `prediccion.txt`, `curva_ganancia.pdf`, `cortes_ganancia.txt`, `PARAM.yml` |

**Flujo**

1. Lee YAML; reproduce split con `compe1_reproducir_holdout`.
2. `modifyList(param_fijos, mejores_hiperparametros)` + `compe1_decodificar_min_sum_hessian`.
3. `lgb.train` en mar–may; `predict` en junio.
4. Curva de ganancia y cortes `PARAM$cortes`.

**No hace:** BO, top-20.

---

### `3_escalar_ganancia_mes.R` (no usado en protocolo 1990)

Pertenece al experimento con holdout 70/30 estratificado (p. ej. `03_`). Con test = junio completo, la ganancia en `2_`/`4_` ya es la del mes entero; este script no forma parte del pipeline 1990.

---

### `4_produccion_top20_bo_semillas.R`

| | |
|--|--|
| **Rol** | Replica los 20 mejores HP de `BO_log.txt`, cada uno con 10 semillas-primo; métrica oficial = prob media en test junio. |
| **Requiere** | `HT1990/PARAM.yml`, `BO_log.txt` (`1_`). |
| **Escribe** | `estudio/top20_bo_semillas/top20_hiperparametros.tsv`, `semillas_train.txt`; por `exp1990_top20/rank_XX/`: modelos, predicciones y cortes; agregados `prediccion_media.txt`, `cortes_ganancia_media.*`, `PARAM.yml` |

**Flujo global**

1. Cabecera top-20 y semillas (`compe1_semillas_primos`).
2. Dataset + `compe1_reproducir_holdout`; un `lgb.Dataset` de mar–may reutilizado en el bucle `k = 1..20`.
3. Por rank: `producir_primos_en_dir` + `PARAM.yml` con metadata BO.

**Detalle clave:** la ganancia “oficial” del rank promedia probabilidades **antes** de ordenar y cortar.

---

### `5_analisis_top20_bo_semillas.R`

| | |
|--|--|
| **Rol** | Post hoc sobre cortes de test junio por semilla; elige ganador y contrastes Wilcoxon/Holm; sin `lgb.train`. |
| **Requiere** | Salida completa de `4_`. |
| **Escribe** | Tablas TSV, `ganador.yml`, `PARAM_resumen.yml`, PDFs en `estudio/top20_bo_semillas/` |

---

### `6_prediccion_agosto_top20_semillas.R`

| | |
|--|--|
| **Rol** | Producción agosto: train en mar–jun completo, predict `foto_mes = 202108`. |
| **Requiere** | `HT1990/PARAM.yml`; `top20_hiperparametros.tsv` o `BO_log.txt`. |
| **Config en script** | `RANKS_BO` (default `3L`); `FOTO_MES_TRAIN` / `FOTO_MES_PRED`. |
| **Escribe** | `exp1990_agosto/prediccion_agosto_media.tsv`, `prediccion_agosto_media_ordenada.tsv`, TSV por rank×semilla, `meta.yml` |

**No hace:** holdout, ganancia, Wilcoxon.

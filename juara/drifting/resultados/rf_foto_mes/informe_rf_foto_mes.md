# Informe: RF multiclass `foto_mes` (drifting)

## Diseño

- **Datos:** `dataset_nocont_rank.parquet` (nocontinuas + rankings, todas las filas y clases).
- **Predictores:** 152 columnas (`nocontinuas_base` + `pct_*`, sin lag/delta).
- **Etiqueta:** `foto_mes` (multiclass).
- **Modelo:** RandomForestClassifier, `n_estimators=300`, `min_samples_leaf=50`, `max_features=sqrt`, `random_state=2026`.
- **Partición:** holdout estratificado 80/20 (seed=2026).

## Conteos por `foto_mes` (dataset completo)

- 202103: 162900
- 202104: 163284
- 202105: 163768
- 202106: 164114
- 202107: 164348
- 202108: 164647

## Métricas holdout vs baseline

| Métrica | Valor |
| --- | --- |
| Accuracy | 0.9999 |
| Balanced accuracy | 0.9999 |
| Macro-F1 | 0.9999 |
| Baseline clase mayoritaria (dataset completo) | 0.1675 |
| Azar uniforme (1/k, k=6) | 0.1667 |

Un accuracy holdout claramente por encima de 1/k sugiere que las features portan estructura asociada al mes calendario; no implica causalidad ni estabilidad fuera del panel.

## Matriz de confusión

Ver `confusion_matrix.csv` y `plots/confusion_matrix.png`.

| pred_202103 | pred_202104 | pred_202105 | pred_202106 | pred_202107 | pred_202108 | true_foto_mes |
| --- | --- | --- | --- | --- | --- | --- |
| 32576 | 0 | 2 | 0 | 2 | 0 | 202103 |
| 0 | 32656 | 0 | 1 | 0 | 0 | 202104 |
| 0 | 0 | 32753 | 1 | 0 | 0 | 202105 |
| 0 | 0 | 0 | 32821 | 2 | 0 | 202106 |
| 0 | 0 | 0 | 0 | 32870 | 0 | 202107 |
| 1 | 0 | 0 | 0 | 1 | 32927 | 202108 |


## Top permutation importance (holdout)

Muestra usada: 20000 filas (máx. configurado: 20000).

| feature | importance_mean | importance_std |
| --- | --- | --- |
| pct_mcuenta_corriente_adicional | 0.017166517201404097 | 0.0006249826220806612 |
| pct_mcaja_ahorro_adicional | 0.0044044692848713264 | 0.00024107256419604605 |
| pct_Visa_msaldodolares | 0.0001906115718979695 | 4.9115527704586435e-05 |
| pct_mcomisiones_mantenimiento | 0.00010018055567619921 | 4.465295493631583e-05 |
| pct_ccomisiones_mantenimiento | 7.990734488343421e-05 | 4.009266847391785e-05 |
| pct_Master_msaldodolares | 6.998112376461751e-05 | 5.098605411582452e-05 |
| pct_mcaja_ahorro_dolares | 5.0095763783120084e-05 | 5.499275926431116e-05 |
| pct_ccuenta_debitos_automaticos | 9.971083856807894e-06 | 1.9942167713615788e-05 |
| active_quarter | 0.0 | 0.0 |
| cliente_vip | 0.0 | 0.0 |
| internet | 0.0 | 0.0 |
| tcuentas | 0.0 | 0.0 |
| ccuenta_corriente | 0.0 | 0.0 |
| cdescubierto_preacordado | 0.0 | 0.0 |
| ctarjeta_visa | 0.0 | 0.0 |
| ctarjeta_master | 0.0 | 0.0 |
| cseguro_vida | 0.0 | 0.0 |
| cseguro_vivienda | 0.0 | 0.0 |
| cseguro_accidentes_personales | 0.0 | 0.0 |
| tcallcenter | 0.0 | 0.0 |
| thomebanking | 0.0 | 0.0 |
| ccajas_transacciones | 0.0 | 0.0 |
| tmobile_app | 0.0 | 0.0 |
| cmobile_app_trx | 0.0 | 0.0 |
| Master_delinquency | 0.0 | 0.0 |
| Master_status | 0.0 | 0.0 |
| Visa_delinquency | 0.0 | 0.0 |
| Visa_status | 0.0 | 0.0 |
| ctarjeta_debito | 0.0 | 0.0 |
| cseguro_auto | 0.0 | 0.0 |


Muchas variables `pct_*` reflejan posición relativa intra-mes; un cambio de mezcla de clientes entre meses puede elevar su importancia sin indicar un nivel absoluto estable.

## Auditoría de leakage (exploratoria)

- **Fuga directa:** no. `foto_mes`, `clase_ternaria` y `numero_de_cliente` quedan fuera de X; el join por clave no duplica filas (983 061 filas alineadas).
- **`pct_*`:** percentiles con `PARTITION BY foto_mes` en `fe/build_rankings.py`; no usan meses futuros. No es lookahead, pero la etiqueta es el estrato de partición de esas features: el modelo aprende a qué cohorte mensual pertenece el vector de ranks.
- **Ablation (50k, 100 árboles):** accuracy holdout ≈ 0,999 con solo `pct_*`; solo nocontinuas numéricas ≈ 0,18 (cercano a 1/6). La señal casi total está en rankings, no en niveles nocontinuas.
- **Split 80/20 por fila:** ~121 600 clientes aparecen en train y test en **meses distintos** (0 filas repetidas). Explora drift de cohorte; no mide generalización a clientes ausentes del train.

## Contraste con nivel crudo (sin `pct_*`)

Mismo panel y protocolo RF en [`resultados/rf_foto_mes_nivel/`](../rf_foto_mes_nivel/informe_rf_foto_mes_nivel.md) (nocontinuas + 126 continuas en escala original). Holdout: accuracy **≈ 0,89** vs **≈ 1,00** con `pct_*`. El mes también es predecible por niveles absolutos (por encima de 1/6), pero la separación casi total del run con rankings refleja el acoplamiento rank–cohorte mensual, no solo drift de magnitudes.

## Conclusión exploratoria

El RF separa `foto_mes` casi por completo vía **`pct_*` intra-mes**, coherente con drift fuerte de la copula/composición del panel entre meses. No implica que nocontinuas en nivel absoluto predigan el calendario; sí que el ranking relativo del mes es altamente específico de cada cohorte y debe tratarse en modelado (p. ej. no usar `pct_*` crudos como si fueran invariantes temporales).

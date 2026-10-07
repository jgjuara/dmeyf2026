# Informe: RF multiclass `foto_mes` — nivel crudo (drifting)

## Diseño

- **Datos:** `dataset_nocont_nivel.parquet` (nocontinuas + continuas en escala original).
- **Predictores:** 152 columnas (`nocontinuas_base`=26, `continuas_nivel`=126; sin `pct_*`, lag ni delta).
- **Etiqueta:** `foto_mes` (multiclass).
- **Modelo:** RandomForestClassifier, `n_estimators=300`, `min_samples_leaf=50`, `max_features=sqrt`, `random_state=2026`.
- **Partición:** holdout estratificado 80/20 (seed=2026).

## Comparación vs `rf_foto_mes` (rankings `pct_*`)

| Métrica | Nivel crudo (este pipeline) | Rankings `pct_*` (`rf_foto_mes`) |
| --- | --- | --- |
| Accuracy | 0.8851 | 0.9999 |
| Balanced accuracy | 0.8850 | 0.9999 |
| Macro-F1 | 0.8876 | 0.9999 |

Misma hipérbola RF, mismo split 80/20 estratificado (seed 2026) y mismo panel (983 061 filas). La diferencia aísla el efecto de usar **niveles absolutos** frente a **percentiles intra-mes**.

## Conteos por `foto_mes` (dataset completo)

- 202103: 162900
- 202104: 163284
- 202105: 163768
- 202106: 164114
- 202107: 164348
- 202108: 164647

## Métricas holdout vs baseline (nivel)

| Métrica | Valor |
| --- | --- |
| Accuracy | 0.8851 |
| Balanced accuracy | 0.8850 |
| Macro-F1 | 0.8876 |
| Baseline clase mayoritaria (dataset completo) | 0.1675 |
| Azar uniforme (1/k, k=6) | 0.1667 |

## Matriz de confusión

Ver `confusion_matrix.csv` y `plots/confusion_matrix.png`.

| pred_202103 | pred_202104 | pred_202105 | pred_202106 | pred_202107 | pred_202108 | true_foto_mes |
| --- | --- | --- | --- | --- | --- | --- |
| 27610 | 402 | 1602 | 184 | 185 | 2597 | 202103 |
| 265 | 27883 | 1714 | 174 | 247 | 2374 | 202104 |
| 210 | 354 | 30731 | 196 | 175 | 1088 | 202105 |
| 262 | 267 | 1608 | 27621 | 211 | 2854 | 202106 |
| 124 | 217 | 479 | 147 | 28289 | 3614 | 202107 |
| 97 | 170 | 316 | 157 | 304 | 31885 | 202108 |


## Top permutation importance (holdout)

Muestra usada: 20000 filas (máx. configurado: 20000).

| feature | importance_mean | importance_std |
| --- | --- | --- |
| Visa_fultimo_cierre | 0.2720690134188956 | 0.00226881550337313 |
| Master_fultimo_cierre | 0.26579434541687147 | 0.0006074125961321333 |
| mcomisiones_mantenimiento | 0.02142722590956838 | 0.0009352023468926773 |
| Visa_mpagado | 0.010490507843524965 | 0.000897657473261695 |
| Visa_mlimitecompra | 0.006844321393060371 | 0.0002730345273597312 |
| Visa_mfinanciacion_limite | 0.006023818536688585 | 0.0003560863152577502 |
| Master_mfinanciacion_limite | 0.005571416415313601 | 0.00017980024298755204 |
| Visa_fechaalta | 0.004680043440209713 | 0.00046592062963803267 |
| Master_fechaalta | 0.004507543518808954 | 0.00030146074148750847 |
| Master_mlimitecompra | 0.003407411576399455 | 0.0003669509338159695 |
| cliente_antiguedad | 0.003331580215127139 | 0.0002511641073791716 |
| mpayroll | 0.0030587325489511707 | 0.00035976354089036926 |
| mcuentas_saldo | 0.00264933795452007 | 0.0005117342166851191 |
| mcomisiones_otras | 0.0014690284814230735 | 0.0003405693410574751 |
| mcaja_ahorro | 0.0014507547346748416 | 0.00032496747701298104 |
| cpayroll_trx | 0.0013889145747468135 | 0.00028018849245223655 |
| Visa_Fvencimiento | 0.001036350861718871 | 0.00047547658852422936 |
| mcomisiones | 0.0007675528015385735 | 0.00032067184712462573 |
| Visa_Finiciomora | 0.0007500763204519201 | 7.700506375492388e-05 |
| mrentabilidad | 0.0006680657633709952 | 0.00025775301121280347 |
| ccajas_depositos | 0.0006410512088736109 | 9.716728193760797e-05 |
| ccomisiones_otras | 0.0005865100157233183 | 0.00020138297124891393 |
| ctrx_quarter | 0.0005632915639104397 | 6.503403898447201e-05 |
| mpasivos_margen | 0.000534070140081222 | 0.00037776550254719305 |
| mactivos_margen | 0.0004030576255765306 | 0.0003543385916249451 |
| Master_Fvencimiento | 0.0003821171547139457 | 0.0002448606184562751 |
| internet | 0.00038074803551499945 | 0.0001470692819705205 |
| mextraccion_autoservicio | 0.0003788601609139741 | 6.812932216065141e-05 |
| ccaja_seguridad | 0.00036119859621634997 | 3.752512661114692e-05 |
| ccomisiones_mantenimiento | 0.00021253394531299817 | 0.00039841216174785134 |


## Auditoría de leakage (exploratoria)

- **Fuga directa:** no. `foto_mes`, `clase_ternaria` y `numero_de_cliente` quedan fuera de X; el join por clave no duplica filas (983 061 filas).
- **Continuas en nivel:** no hay `PARTITION BY foto_mes` en estas columnas; no acoplan la etiqueta vía percentil intra-cohorte como `pct_*`. Sí pueden codificar drift de **escala absoluta** (inflación de saldos, cambios de producto, recorte de outliers) entre meses calendario.
- **Contraste con `pct_*`:** en `rf_foto_mes`, la etiqueta coincide con el estrato usado para calcular ranks; aquí esa vía está ausente. Un accuracy mucho menor que ~0,999 apuntaría a que la separación casi total del baseline ranking venía del acoplamiento rank–mes, no de nocontinuas solas.
- **Split 80/20 por fila:** igual que el pipeline con rankings; no mide generalización a clientes ausentes del train.

## Conclusión exploratoria

El RF en **nivel crudo** separa `foto_mes` mucho peor que con `pct_*`: la cohorte mensual no queda marcada por ranks relativos, sino que la señal temporal (si existe) debe venir de cambios de nivel absoluto o de nocontinuas, no del percentil intra-mes.

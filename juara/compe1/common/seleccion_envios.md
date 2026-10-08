# Selección de envíos (promedio de semillas)

Procedimiento operativo para elegir el corte **Envios** en la curva de ganancia de negocio, cuando la evaluación usa **varias semillas de entrenamiento** y, opcionalmente, **varios modelos** (p. ej. ranks del top-20 BO).

Referencia de implementación: `4_produccion_top20_bo_semillas` (genera cortes) y `5_analisis_top20_bo_semillas` (elige envíos y contrasta ranks). Utilidad de ganancia: `compe1_ganancia_envio` en [`compe1_data.R`](compe1_data.R).

## Definiciones

| Término | Significado |
|---------|-------------|
| **Envios** | Cantidad de clientes contactados (top-N por probabilidad descendente). |
| **Semilla (`primo`)** | `seed` de LightGBM en entrenamiento; en compe1 suelen ser 10 primos (`compe1_semillas_primos`). |
| **Holdout** | Conjunto de evaluación offline (en exp 1990: test **junio**; en protocolo 70/30: `fold_test`). |
| **Modelo** | Una configuración de HP fija (un `rank_XX` del top-20, o un único run de `2_produccion_lightgbm`). |
| **Prob media** | Por fila `(numero_de_cliente, foto_mes)`, media de `prob` sobre las semillas **antes** de ordenar y cortar (`prediccion_media.txt` → `cortes_ganancia_media.*`). |

La grilla de cortes viene de `PARAM$cortes` (típicamente `seq(4000, 19000, by = 500)`).

## Entradas mínimas

### Un modelo, promedio de semillas

Tras `4_produccion_top20_bo_semillas` (o equivalente Python):

- `cortes_ganancia_media.tsv` (o `.txt`) en el directorio del modelo.
- Opcional para robustez: `cortes_ganancia_<primo>.txt` por cada semilla.

### Varios modelos

- Lo anterior **por modelo** (p. ej. `exp####_top20/rank_01/`, …, `rank_20/`).
- Para el protocolo top-20: salida de `5_analisis_top20_bo_semillas` (`curvas_por_semilla.tsv`, `curvas_media_sd.tsv`, `ranking_por_max_holdout.tsv`, `ganador.yml`).

## Métrica objetivo (criterio primario)

Para cada **modelo** \(m\) y cada **envíos** \(e\):

1. Si solo importa el **promedio de probabilidades** (recomendado en producción del rank):
   - Leer `TOTAL` en `cortes_ganancia_media` → \( \bar{G}_m(e) \).
2. Si se quiere alinear con la inferencia del script `5_`:
   - Por semilla \(s\), leer ganancia holdout \(G_{m,s}(e)\) desde `cortes_ganancia_<s>.txt`.
   - Definir \( \bar{G}_m(e) = \frac{1}{S}\sum_s G_{m,s}(e) \) (media sobre semillas).

En el pipeline estándar, (1) y (2) coinciden en intención: el rank se opera con prob media; `5_` usa (2) para Wilcoxon emparejado por `primo`.

**Envíos óptimo del modelo** (criterio del estudio compe1):

```text
e*_m = argmax_e  Ḡ_m(e)
```

En empate numérico en `which.max`, gana el **primer** envío de la grilla con ese valor (comportamiento de R en `5_`).

## Procedimiento paso a paso

### A. Un solo modelo

1. Generar predicciones por semilla y **prob media** (`4_` o flujo manual equivalente).
2. Construir curva de ganancia acumulada en holdout y barrer `PARAM$cortes` → `cortes_ganancia_media.tsv`.
3. **Selección primaria:** `e* = argmax` de columna `total` / `TOTAL` vs `envios`.
4. **Revisión de meseta (recomendada):**
   - Graficar \( \bar{G}(e) \) vs `envios`.
   - Si varios \(e\) están a menos de un umbral de negocio (p. ej. &lt; 0,1–0,2 % del máximo), preferir el **menor envíos** en la meseta (menor costo operativo).
5. **Robustez por semilla (opcional):**
   - Por cada `primo`, calcular su argmax \( e^*_s \).
   - Si la moda de \( \{ e^*_s \} \) difiere mucho de \( e^* \), la curva media puede ocultar discordancia; revisar `curvas_por_semilla` o bandas ± sd.

No hay contraste inferencial entre ranks en este caso; Wilcoxon/Friedman no aplican.

### B. Varios modelos (shortlist)

Objetivo: elegir **modelo ganador** y **envíos de reporte** (pueden ser distintos por rank).

1. **Apilar datos largos** `(modelo/rank, primo, envios, ganancia)` desde cortes por semilla (como `curvas_por_semilla.tsv` en `5_`).
2. **Por modelo** \(m\): calcular `curvas_media_sd` = media y sd de `ganancia` sobre semillas, por `envios`.
3. **Score del modelo** (ranking operativo compe1):
   - \( \text{score}_m = \max_e \bar{G}_m(e) \)
   - \( e^*_m = \arg\max_e \bar{G}_m(e) \)
   - Ordenar modelos por `score` descendente → `ranking_por_max_holdout.tsv`.
4. **Ganador:** modelo con mayor `score`; **envíos de reporte principal:** \( e^*_{\text{ganador}} \) → `envios_argmax_ganador` en `ganador.yml`.
5. **Meseta:** repetir paso A.4 sobre la curva media del **ganador** (no sobre el subcampeón salvo análisis de sensibilidad).
6. **Inferencia secundaria** (mismo holdout, mismas semillas; no elige envíos por sí sola):
   - En \( e = e^*_{\text{ganador}} \): Wilcoxon emparejado ganador vs subcampeón; ganador vs cada rank del resto con **Holm**; ganador vs mediana/máximo del resto por semilla; winrate binomial 10/10.
   - **Friedman por envío:** por cada `envios`, test omnibus de igualdad entre modelos bloqueado por `primo`. Sirve para detectar envíos donde los modelos **no** son equivalentes entre semillas; **no** sustituye el argmax de la media.
7. **Decisión final:**
   - **Envíos para producción del ganador:** \( e^*_{\text{ganador}} \) salvo meseta/robustez (pasos 5 y A.5).
   - **Modelo:** el de mayor `max_mean_holdout`; si inferencia es débil (Holm / winrate sin significación), la elección sigue siendo por media holdout, con la limitación documentada en `PARAM_resumen.yml`.

## Caso especial: un HP, una semilla (`2_produccion_lightgbm`)

Un solo `cortes_ganancia.txt` sin promedio: \( e^* = \arg\max \) de la curva en holdout. No hay bloque `primo`; la robustez exige repetir con varias semillas (fase `4_`) o aceptar riesgo de una sola trayectoria.

## Salidas de referencia (top-20)

| Archivo | Uso en selección de envíos |
|---------|----------------------------|
| `cortes_ganancia_media.tsv` | Argmax rápido por rank (un modelo). |
| `curvas_media_sd.tsv` | Curva media ± sd por rank y envíos. |
| `ranking_por_max_holdout.tsv` | `envios_argmax` y pico por rank. |
| `ganador.yml` | `rank_ganador`, `envios_argmax_ganador`. |
| `wilcoxon_mejor_vs_segundo_holdout.tsv` | Sensibilidad del par líder al barrido de envíos. |
| `friedman_por_envio.tsv` | Heterogeneidad entre modelos en cada envío (secundario). |

## Errores frecuentes

1. **Argmax sobre una sola semilla** y presentarlo como “promedio de semillas”.
2. **Promediar ganancias ya cortadas por semilla con distinto orden** en lugar de promediar probabilidades y luego cortar (sesgo de composición).
3. **Usar Friedman** para fijar envíos (responde otra pregunta).
4. **Elegir envíos del subcampeón** cuando el ganador ya está fijado por `ranking_por_max_holdout` (cada rank tiene su propio \( e^*_m \); en producción se usa el del rank elegido).
5. **Optimizar en BO (AUC)** en lugar de en ganancia holdout sobre la grilla de envíos.

## Resumen operativo

```text
Por modelo:  e*_m = argmax_e  media_semillas( ganancia_holdout(m, e) )
Varios:      ganador = argmax_m  max_e  media_semillas( ganancia_holdout(m, e) )
Reporte:     envíos = e*_ganador  (+ meseta / menor envíos si empate práctico)
Validar:     curva, sd por semilla, Wilcoxon en e*_ganador (varios modelos)
```

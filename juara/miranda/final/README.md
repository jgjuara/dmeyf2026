# Informe multimensual de bajas (`miranda/final`)

Pipeline reproducible para comparar BAJA+1 y BAJA+2 con CONTINUA en las fotos
202103–202108. Analiza anclas 202103–202106 y alinea cada episodio con su mes
de evento esperado.

## Ejecución

Desde el directorio `juara/`:

```bash
uv run python miranda/final/run_pipeline.py
```

La ejecución reconstruye cohorte, métricas, gráficos, validación de perfiles e
informe. Requiere `data/competencia_01_v1.parquet`.

## Diseño

- BAJA se deduplica por `(numero_de_cliente, mes_evento_esperado)`.
- CONTINUA se selecciona determinísticamente por ancla y horizonte, con 20
  controles por episodio BAJA y exclusión de cualquier cliente BAJA.
- `mes_relativo=0` representa el evento esperado para ambos grupos; la réplica
  de controles sólo define esa referencia temporal.
- La segmentación se publica únicamente si supera validación temporal, tamaño,
  silueta y estabilidad. Si no, el informe declara que no hay perfiles
  defendibles.

## Salidas

Todo bajo `miranda/final/resultados/`:

- `informe_final.md` — informe ejecutivo sustentado en tablas y gráficos.
- `destacados.md` — gráficos seleccionados y su propósito.
- `tablas/auditoria_*.parquet`, `candidatos_evento.parquet` y
  `miembros_cohorte.parquet` — trazabilidad de fuente, cohorte y controles.
- `panel/panel_longitudinal.parquet` — panel por episodio y foto.
- `tablas/cohorte_*.csv`, `contrastes_*.csv`, `persistencia_senales.csv`,
  `trayectorias_*.csv` y `denominadores_metricas.csv` — soporte numérico.
- `tablas/cluster_*.csv` y `cluster_metadata.json` — validación, o perfiles
  cuantitativos cuando la segmentación es aceptada.
- `plots/etapa_01/` a `plots/etapa_04/` — diez gráficos por etapa.

El informe describe asociaciones observadas; no establece causalidad, no
verifica cancelaciones efectivas y no extrapola fuera de la ventana disponible.

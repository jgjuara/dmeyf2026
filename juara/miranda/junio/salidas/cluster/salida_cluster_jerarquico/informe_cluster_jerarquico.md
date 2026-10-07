# Clustering jerárquico — cohorte BAJA (Miranda)

Generado: 2026-10-04 15:39 UTC

## Fuente

- Distancia RF: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/junio/salidas/cluster/salida_cluster_rf_proximity/distancia.npz`
- Parquet: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/junio/datos/dataset_junio.parquet`
- Enlace: **average** (no Ward; disimilitud 1 − proximidad RF).

## Parámetros

- k evaluado: 2–15
- tamaño mínimo de clúster: 50
- **k elegido**: 2 (silueta = 0.0946)

## Limitaciones

- Segmentación exploratoria basada en proximidad de hojas RF; no implica causalidad ni regla operativa.
- La silueta con matriz grande es costosa; el corte es un compromiso global, no validado externamente.

## Perfiles (resumen)

Ver `tablas/perfiles_cluster.csv`. Primeras filas:

```
cluster,n,pct_202105,pct_202106,n_clase_BAJA+1,n_clase_BAJA+2,mean_cliente_vip,mean_internet,mean_pct_mrentabilidad,mean_pct_mcuentas_saldo,mean_pct_ctrx_quarter,mean_lag1_pct_mrentabilidad,mean_delta1_pct_mrentabilidad
1,971,0.0,1.0,416,555,0.0,0.3573635427394439,0.5397877404737385,0.159843236869207,0.07323600411946449,0.5558902587991719,-0.015883629399585916
2,1001,0.0,1.0,458,543,0.001998001998001998,0.11288711288711288,0.5200057052947054,0.27450409790209795,0.24659259040959045,0.5025769530469532,0.01742875224775225
```

## Artefactos

| Ruta | Descripción |
| --- | --- |
| `tablas/evaluacion_cortes.csv` | Silueta y tamaños por k |
| `tablas/asignaciones_cluster.csv` | Etiqueta por fila |
| `tablas/perfiles_cluster.csv` | Medias y conteos por clúster |
| `plots/*.png` | Dendrograma, tamaños, silueta |

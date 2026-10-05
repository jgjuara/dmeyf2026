# Clustering jerárquico — cohorte BAJA (Miranda)

Generado: 2026-10-03 22:48 UTC

## Fuente

- Distancia RF: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/mayo_junio/salidas/cluster/salida_cluster_rf_proximity/distancia.npz`
- Parquet: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/mayo_junio/datos/dataset_mayo_junio.parquet`
- Enlace: **average** (no Ward; disimilitud 1 − proximidad RF).

## Parámetros

- k evaluado: 2–15
- tamaño mínimo de clúster: 50
- **k elegido**: 2 (silueta = 0.1130)

## Limitaciones

- Segmentación exploratoria basada en proximidad de hojas RF; no implica causalidad ni regla operativa.
- La silueta con matriz grande es costosa; el corte es un compromiso global, no validado externamente.

## Perfiles (resumen)

Ver `tablas/perfiles_cluster.csv`. Primeras filas:

```
cluster,n,pct_202105,pct_202106,n_clase_BAJA+1,n_clase_BAJA+2,mean_cliente_vip,mean_internet,mean_pct_mrentabilidad,mean_pct_mcuentas_saldo,mean_pct_ctrx_quarter,mean_lag1_pct_mrentabilidad,mean_delta1_pct_mrentabilidad
1,1508,0.3229442970822281,0.6770557029177718,954,554,0.001989389920424403,0.10543766578249338,0.5183935563660477,0.2807596220159151,0.2404273799734748,0.5031168766578249,0.015276679708222812
2,1607,0.40821406347230865,0.5917859365276914,1063,544,0.0,0.2955818294959552,0.5644971095208463,0.15691521530802738,0.06685721032980708,0.5797812440550689,-0.01484457697121402
```

## Artefactos

| Ruta | Descripción |
| --- | --- |
| `tablas/evaluacion_cortes.csv` | Silueta y tamaños por k |
| `tablas/asignaciones_cluster.csv` | Etiqueta por fila |
| `tablas/perfiles_cluster.csv` | Medias y conteos por clúster |
| `plots/*.png` | Dendrograma, tamaños, silueta |

# Clustering jerárquico — cohorte BAJA (Miranda)

Generado: 2026-10-04 15:40 UTC

## Fuente

- Distancia RF: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/junio/salidas/cluster/salida_cluster_rf_proximity_baja12/distancia.npz`
- Parquet: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/junio/datos/dataset_junio.parquet`
- Enlace: **average** (no Ward; disimilitud 1 − proximidad RF).

## Parámetros

- k evaluado: 2–15
- tamaño mínimo de clúster: 50
- **k elegido**: 2 (silueta = 0.0658)

## Limitaciones

- Segmentación exploratoria basada en proximidad de hojas RF; no implica causalidad ni regla operativa.
- La silueta con matriz grande es costosa; el corte es un compromiso global, no validado externamente.

## Perfiles (resumen)

Ver `tablas/perfiles_cluster.csv`. Primeras filas:

```
cluster,n,pct_202105,pct_202106,n_clase_BAJA+1,n_clase_BAJA+2,mean_cliente_vip,mean_internet,mean_pct_mrentabilidad,mean_pct_mcuentas_saldo,mean_pct_ctrx_quarter,mean_lag1_pct_mrentabilidad,mean_delta1_pct_mrentabilidad
1,525,0.0,1.0,185,340,0.0,0.6190476190476191,0.5563000076190476,0.1187377523809524,0.07672362476190477,0.5901283923809523,-0.03382838476190477
2,1447,0.0,1.0,689,758,0.00138217000691085,0.09329647546648238,0.5201120269523151,0.25407675535590885,0.1918945680718728,0.5064161678224689,0.013774269764216364
```

## Artefactos

| Ruta | Descripción |
| --- | --- |
| `tablas/evaluacion_cortes.csv` | Silueta y tamaños por k |
| `tablas/asignaciones_cluster.csv` | Etiqueta por fila |
| `tablas/perfiles_cluster.csv` | Medias y conteos por clúster |
| `plots/*.png` | Dendrograma, tamaños, silueta |

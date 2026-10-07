# Clustering jerárquico — cohorte BAJA (Miranda)

Generado: 2026-10-04 16:08 UTC

## Fuente

- Distancia RF: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/mayo_junio/salidas/cluster/salida_cluster_rf_proximity_baja12_sin_lag_delta/distancia.npz`
- Parquet: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/mayo_junio/datos/dataset_mayo_junio.parquet`
- Enlace: **average** (no Ward; disimilitud 1 − proximidad RF).

## Parámetros

- k evaluado: 2–15
- tamaño mínimo de clúster: 50
- **k elegido**: 5 (silueta = 0.1884)

## Limitaciones

- Segmentación exploratoria basada en proximidad de hojas RF; no implica causalidad ni regla operativa.
- La silueta con matriz grande es costosa; el corte es un compromiso global, no validado externamente.

## Perfiles (resumen)

Ver `tablas/perfiles_cluster.csv`. Primeras filas:

```
cluster,n,pct_202105,pct_202106,n_clase_BAJA+1,mean_cliente_vip,mean_internet,mean_pct_mrentabilidad,mean_pct_mcuentas_saldo,mean_pct_ctrx_quarter,mean_lag1_pct_mrentabilidad,mean_delta1_pct_mrentabilidad,n_clase_BAJA+2
1,1145,0.9982532751091703,0.0017467248908296944,1145,0.0008733624454148472,0.15196506550218342,0.5634096148471616,0.21501393362445412,0.13291293537117907,0.5664442804557407,-0.0027164627519719563,
2,503,0.0,1.0,173,0.0,0.6302186878727635,0.5543517972166999,0.1202022584493042,0.06763754075546721,0.5835000357852883,-0.029148238568588475,330
3,856,0.0,1.0,387,0.002336448598130841,0.08294392523364486,0.5208220175233645,0.28503813901869157,0.2672318352803739,0.4932295692488263,0.02773864553990611,469
4,396,0.0,1.0,189,0.0,0.07828282828282829,0.5190874545454545,0.213582345959596,0.07655697222222223,0.5148207037974684,0.004242253164556967,207
5,215,0.0,1.0,123,0.0,0.19069767441860466,0.5281818418604651,0.1875549534883721,0.1150233488372093,0.566471930232558,-0.03829008837209302,92
```

## Artefactos

| Ruta | Descripción |
| --- | --- |
| `tablas/evaluacion_cortes.csv` | Silueta y tamaños por k |
| `tablas/asignaciones_cluster.csv` | Etiqueta por fila |
| `tablas/perfiles_cluster.csv` | Medias y conteos por clúster |
| `plots/*.png` | Dendrograma, tamaños, silueta |

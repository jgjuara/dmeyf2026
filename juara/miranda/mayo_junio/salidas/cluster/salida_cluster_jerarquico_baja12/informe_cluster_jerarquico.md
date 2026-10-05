# Clustering jerárquico — cohorte BAJA (Miranda)

Generado: 2026-10-04 15:21 UTC

## Fuente

- Distancia RF: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/mayo_junio/salidas/cluster/salida_cluster_rf_proximity_baja12/distancia.npz`
- Parquet: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/mayo_junio/datos/dataset_mayo_junio.parquet`
- Enlace: **average** (no Ward; disimilitud 1 − proximidad RF).

## Parámetros

- k evaluado: 2–15
- tamaño mínimo de clúster: 50
- **k elegido**: 8 (silueta = 0.2417)

## Limitaciones

- Segmentación exploratoria basada en proximidad de hojas RF; no implica causalidad ni regla operativa.
- La silueta con matriz grande es costosa; el corte es un compromiso global, no validado externamente.

## Perfiles (resumen)

Ver `tablas/perfiles_cluster.csv`. Primeras filas:

```
cluster,n,pct_202105,pct_202106,n_clase_BAJA+1,n_clase_BAJA+2,mean_cliente_vip,mean_internet,mean_pct_mrentabilidad,mean_pct_mcuentas_saldo,mean_pct_ctrx_quarter,mean_lag1_pct_mrentabilidad,mean_delta1_pct_mrentabilidad
1,1157,0.9878997407087294,0.012100259291270527,1154,3,0.000864304235090752,0.15038893690579083,0.5619142160760587,0.21582677355229038,0.13301190924805537,0.565103418118467,-0.002597593205574915
2,296,0.0,1.0,152,144,0.0,0.30743243243243246,0.5718035405405406,0.13761869594594592,0.07868946283783784,0.5808609695945947,-0.009057429054054053
3,266,0.0,1.0,51,215,0.0,0.9135338345864662,0.5522837894736842,0.1074088082706767,0.09383494736842106,0.6076563834586468,-0.0553725939849624
4,215,0.0,1.0,104,111,0.0,0.04186046511627907,0.5979904372093022,0.2661343674418605,0.22969559534883718,0.3931892744186047,0.20480116279069768
5,351,0.0,1.0,170,181,0.0,0.13105413105413105,0.5210089544159543,0.17324231054131053,0.14860780626780629,0.537010264957265,-0.01600131054131055
6,370,0.0,1.0,144,226,0.005405405405405406,0.051351351351351354,0.4917519648648648,0.40046025945945946,0.34511401081081083,0.5076312162162162,-0.015879251351351348
7,158,0.0,1.0,89,69,0.0,0.1518987341772152,0.5470493417721519,0.1944552848101266,0.11725876582278481,0.5681449936708861,-0.021095651898734174
8,302,0.0,1.0,153,149,0.0,0.09271523178807947,0.47272895364238415,0.19738290066225164,0.06653015894039734,0.5041846125827814,-0.03145565894039735
```

## Artefactos

| Ruta | Descripción |
| --- | --- |
| `tablas/evaluacion_cortes.csv` | Silueta y tamaños por k |
| `tablas/asignaciones_cluster.csv` | Etiqueta por fila |
| `tablas/perfiles_cluster.csv` | Medias y conteos por clúster |
| `plots/*.png` | Dendrograma, tamaños, silueta |

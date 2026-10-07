# Informe de clústeres agrupados — cohorte BAJA (Miranda)

Generado: 2026-10-04 15:40 UTC

## Metodología

1. Se carga el enlace jerárquico ya calculado (`average linkage` sobre distancia RF).
2. Se aplica un corte fijo **k=7** (`fcluster`, `maxclust`).
3. Reclasificación analítica (no reoptimiza k):
   - se conservan por separado los clústeres k7 **1, 3, 6 y 7** → perfiles **C1, C3, C6, C7**;
   - se fusionan los clústeres k7 **2, 4 y 5** → perfil **C2_4_5**.

Fuente enlace: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/junio/salidas/cluster/salida_cluster_jerarquico/linkage.npz`
Cohorte: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/junio/datos/dataset_junio.parquet`

## Limitaciones

- El corte k=7 incluye subgrupos pequeños (p. ej. n=14–22); la fusión 2+4+5 los agrupa a propósito.
- No sustituye la partición automática k=2 del pipeline principal; es una lectura alternativa del dendrograma.

## Perfiles (tabla)

```
perfil_agrupado,cluster_k7_componentes,n,pct_202105,pct_202106,n_clase_BAJA+1,n_clase_BAJA+2,mean_cliente_vip,mean_internet,mean_pct_mrentabilidad,mean_pct_mcuentas_saldo,mean_pct_ctrx_quarter,mean_lag1_pct_mrentabilidad,mean_delta1_pct_mrentabilidad
C1,1,13,0.0,1.0,7,6,0.0,0.23076923076923078,0.5166996923076923,0.3177036923076923,0.24878730769230772,0.36835307692307695,0.14834661538461538
C3,3,12,0.0,1.0,9,3,0.0,0.0,0.41922824999999997,0.29338525,0.14245566666666665,0.34654285714285715,0.016778142857142846
C6,6,119,0.0,1.0,64,55,0.0,0.24369747899159663,0.5330731428571428,0.21448470588235294,0.15885845378151262,0.5472691008403361,-0.014195957983193275
C7,7,879,0.0,1.0,394,485,0.0022753128555176336,0.08532423208191127,0.5199488828213881,0.2824514823663254,0.25879115017064847,0.4962981422070536,0.02365074061433447
C2_4_5,"2,4,5",949,0.0,1.0,400,549,0.0,0.3719704952581665,0.5399799789251845,0.15651957955742887,0.07020659957850371,0.5600464067439409,-0.020066427818756588
```

## Lectura comparativa

- **C1** (n=13, k7=1): junio 202106 100.0%; mean pct_mrentabilidad=0.517.
- **C3** (n=12, k7=3): junio 202106 100.0%; mean pct_mrentabilidad=0.419.
- **C6** (n=119, k7=6): junio 202106 100.0%; mean pct_mrentabilidad=0.533.
- **C7** (n=879, k7=7): junio 202106 100.0%; mean pct_mrentabilidad=0.520.
- **C2_4_5** (n=949, k7=2,4,5): junio 202106 100.0%; mean pct_mrentabilidad=0.540.

## Artefactos

| Ruta | Descripción |
| --- | --- |
| `tablas/asignaciones_agrupadas.csv` | `cluster_k7` y `perfil_agrupado` por fila |
| `tablas/perfiles_agrupados.csv` | Resumen por perfil |
| `plots/tamanos_perfil.png` | Tamaños |
| `plots/composicion_foto_mes.png` | Fracción en 202106 por perfil |

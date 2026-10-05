# Informe de clústeres agrupados — cohorte BAJA (Miranda)

Generado: 2026-10-04 15:21 UTC

## Metodología

1. Se carga el enlace jerárquico ya calculado (`average linkage` sobre distancia RF).
2. Se aplica un corte fijo **k=7** (`fcluster`, `maxclust`).
3. Reclasificación analítica (no reoptimiza k):
   - se conservan por separado los clústeres k7 **1, 3, 6 y 7** → perfiles **C1, C3, C6, C7**;
   - se fusionan los clústeres k7 **2, 4 y 5** → perfil **C2_4_5**.

Fuente enlace: `../../salidas/cluster/salida_cluster_jerarquico_baja12/linkage.npz`
Cohorte: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/mayo_junio/datos/dataset_mayo_junio.parquet`

## Limitaciones

- El corte k=7 incluye subgrupos pequeños (p. ej. n=14–22); la fusión 2+4+5 los agrupa a propósito.
- No sustituye la partición automática k=2 del pipeline principal; es una lectura alternativa del dendrograma.

## Perfiles (tabla)

```
perfil_agrupado,cluster_k7_componentes,n,pct_202105,pct_202106,n_clase_BAJA+1,n_clase_BAJA+2,mean_cliente_vip,mean_internet,mean_pct_mrentabilidad,mean_pct_mcuentas_saldo,mean_pct_ctrx_quarter,mean_lag1_pct_mrentabilidad,mean_delta1_pct_mrentabilidad
C1,1,1157,0.9878997407087294,0.012100259291270527,1154,3,0.000864304235090752,0.15038893690579083,0.5619142160760587,0.21582677355229038,0.13301190924805537,0.565103418118467,-0.002597593205574915
C3,3,266,0.0,1.0,51,215,0.0,0.9135338345864662,0.5522837894736842,0.1074088082706767,0.09383494736842106,0.6076563834586468,-0.0553725939849624
C6,6,158,0.0,1.0,89,69,0.0,0.1518987341772152,0.5470493417721519,0.1944552848101266,0.11725876582278481,0.5681449936708861,-0.021095651898734174
C7,7,302,0.0,1.0,153,149,0.0,0.09271523178807947,0.47272895364238415,0.19738290066225164,0.06653015894039734,0.5041846125827814,-0.03145565894039735
C2_4_5,"2,4,5",1232,0.0,1.0,570,662,0.0016233766233766235,0.13392857142857142,0.537860521103896,0.2491334172077922,0.20497577759740257,0.5136239399350649,0.024236581168831175
```

## Lectura comparativa

- **C1** (n=1157, k7=1): mayo 98.8%, junio 1.2%; mean pct_mrentabilidad=0.562.
- **C3** (n=266, k7=3): mayo 0.0%, junio 100.0%; mean pct_mrentabilidad=0.552.
- **C6** (n=158, k7=6): mayo 0.0%, junio 100.0%; mean pct_mrentabilidad=0.547.
- **C7** (n=302, k7=7): mayo 0.0%, junio 100.0%; mean pct_mrentabilidad=0.473.
- **C2_4_5** (n=1232, k7=2,4,5): mayo 0.0%, junio 100.0%; mean pct_mrentabilidad=0.538.

## Artefactos

| Ruta | Descripción |
| --- | --- |
| `tablas/asignaciones_agrupadas.csv` | `cluster_k7` y `perfil_agrupado` por fila |
| `tablas/perfiles_agrupados.csv` | Resumen por perfil |
| `plots/tamanos_perfil.png` | Tamaños |
| `plots/composicion_foto_mes.png` | Mayo vs junio por perfil |

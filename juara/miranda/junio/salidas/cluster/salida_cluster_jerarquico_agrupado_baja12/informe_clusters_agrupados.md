# Informe de clústeres agrupados — cohorte BAJA (Miranda)

Generado: 2026-10-04 15:40 UTC

## Metodología

1. Se carga el enlace jerárquico ya calculado (`average linkage` sobre distancia RF).
2. Se aplica un corte fijo **k=7** (`fcluster`, `maxclust`).
3. Reclasificación analítica (no reoptimiza k):
   - se conservan por separado los clústeres k7 **1, 3, 6 y 7** → perfiles **C1, C3, C6, C7**;
   - se fusionan los clústeres k7 **2, 4 y 5** → perfil **C2_4_5**.

Fuente enlace: `../../salidas/cluster/salida_cluster_jerarquico_baja12/linkage.npz`
Cohorte: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/junio/datos/dataset_junio.parquet`

## Limitaciones

- El corte k=7 incluye subgrupos pequeños (p. ej. n=14–22); la fusión 2+4+5 los agrupa a propósito.
- No sustituye la partición automática k=2 del pipeline principal; es una lectura alternativa del dendrograma.

## Perfiles (tabla)

```
perfil_agrupado,cluster_k7_componentes,n,pct_202105,pct_202106,n_clase_BAJA+1,n_clase_BAJA+2,mean_cliente_vip,mean_internet,mean_pct_mrentabilidad,mean_pct_mcuentas_saldo,mean_pct_ctrx_quarter,mean_lag1_pct_mrentabilidad,mean_delta1_pct_mrentabilidad
C1,1,525,0.0,1.0,185,340,0.0,0.6190476190476191,0.5563000076190476,0.1187377523809524,0.07672362476190477,0.5901283923809523,-0.03382838476190477
C3,3,359,0.0,1.0,182,177,0.0,0.1392757660167131,0.5577980779944289,0.15489284401114206,0.1592762896935933,0.5144727353760447,0.043325342618384395
C6,6,164,0.0,1.0,90,74,0.0,0.17073170731707318,0.5478574390243902,0.1889428780487805,0.11372196951219513,0.5761104817073169,-0.028253042682926825
C7,7,361,0.0,1.0,177,184,0.0,0.07202216066481995,0.514228351800554,0.2156732382271468,0.07605552077562328,0.5025081828254848,0.011720168975069247
C2_4_5,"2,4,5",563,0.0,1.0,240,323,0.003552397868561279,0.055062166962699825,0.49177182593250446,0.36091982770870334,0.3097421065719361,0.4832774713261649,0.008443041218637998
```

## Lectura comparativa

- **C1** (n=525, k7=1): junio 202106 100.0%; mean pct_mrentabilidad=0.556.
- **C3** (n=359, k7=3): junio 202106 100.0%; mean pct_mrentabilidad=0.558.
- **C6** (n=164, k7=6): junio 202106 100.0%; mean pct_mrentabilidad=0.548.
- **C7** (n=361, k7=7): junio 202106 100.0%; mean pct_mrentabilidad=0.514.
- **C2_4_5** (n=563, k7=2,4,5): junio 202106 100.0%; mean pct_mrentabilidad=0.492.

## Artefactos

| Ruta | Descripción |
| --- | --- |
| `tablas/asignaciones_agrupadas.csv` | `cluster_k7` y `perfil_agrupado` por fila |
| `tablas/perfiles_agrupados.csv` | Resumen por perfil |
| `plots/tamanos_perfil.png` | Tamaños |
| `plots/composicion_foto_mes.png` | Fracción en 202106 por perfil |

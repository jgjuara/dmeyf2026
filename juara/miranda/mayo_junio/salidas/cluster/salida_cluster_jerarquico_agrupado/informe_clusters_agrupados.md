# Informe de clústeres agrupados — cohorte BAJA (Miranda)

Generado: 2026-10-03 22:55 UTC

## Metodología

1. Se carga el enlace jerárquico ya calculado (`average linkage` sobre distancia RF).
2. Se aplica un corte fijo **k=7** (`fcluster`, `maxclust`).
3. Reclasificación analítica (no reoptimiza k):
   - se conservan por separado los clústeres k7 **1, 3, 6 y 7** → perfiles **C1, C3, C6, C7**;
   - se fusionan los clústeres k7 **2, 4 y 5** → perfil **C2_4_5**.

Fuente enlace: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/mayo_junio/salidas/cluster/salida_cluster_jerarquico/linkage.npz`
Cohorte: `/home/fdevlocal/server/projects/dmeyf2026/juara/miranda/mayo_junio/datos/dataset_mayo_junio.parquet`

## Limitaciones

- El corte k=7 incluye subgrupos pequeños (p. ej. n=14–22); la fusión 2+4+5 los agrupa a propósito.
- No sustituye la partición automática k=2 del pipeline principal; es una lectura alternativa del dendrograma.

## Perfiles (tabla)

```
perfil_agrupado,cluster_k7_componentes,n,pct_202105,pct_202106,n_clase_BAJA+1,n_clase_BAJA+2,mean_cliente_vip,mean_internet,mean_pct_mrentabilidad,mean_pct_mcuentas_saldo,mean_pct_ctrx_quarter,mean_lag1_pct_mrentabilidad,mean_delta1_pct_mrentabilidad
C1,1,174,0.3160919540229885,0.6839080459770115,119,55,0.0,0.20689655172413793,0.5355430057471264,0.2272095287356322,0.15958790229885053,0.5428884540229886,-0.007345448275862068
C3,3,1312,0.32240853658536583,0.6775914634146342,819,493,0.0022865853658536584,0.09146341463414634,0.5171400030487805,0.2872584024390245,0.2518321234756098,0.4997781806402438,0.017361822408536582
C6,6,113,0.3185840707964602,0.6814159292035398,75,38,0.0,0.6902654867256637,0.6258731327433629,0.12142628318584069,0.08124865486725664,0.5991516637168142,0.02672146902654868
C7,7,1458,0.411522633744856,0.588477366255144,957,501,0.0,0.26886145404663925,0.562605719478738,0.15752154115226336,0.06487179080932784,0.5799969410150894,-0.017391221536351174
C2_4_5,"2,4,5",58,0.5,0.5,47,11,0.0,0.13793103448275862,0.45188565517241375,0.2714345172413793,0.1391002758620689,0.44243746938775513,0.003099408163265299
```

## Lectura comparativa

- **C1** (n=174, k7=1): mayo 31.6%, junio 68.4%; mean pct_mrentabilidad=0.536.
- **C3** (n=1312, k7=3): mayo 32.2%, junio 67.8%; mean pct_mrentabilidad=0.517.
- **C6** (n=113, k7=6): mayo 31.9%, junio 68.1%; mean pct_mrentabilidad=0.626.
- **C7** (n=1458, k7=7): mayo 41.2%, junio 58.8%; mean pct_mrentabilidad=0.563.
- **C2_4_5** (n=58, k7=2,4,5): mayo 50.0%, junio 50.0%; mean pct_mrentabilidad=0.452.

## Artefactos

| Ruta | Descripción |
| --- | --- |
| `tablas/asignaciones_agrupadas.csv` | `cluster_k7` y `perfil_agrupado` por fila |
| `tablas/perfiles_agrupados.csv` | Resumen por perfil |
| `plots/tamanos_perfil.png` | Tamaños |
| `plots/composicion_foto_mes.png` | Mayo vs junio por perfil |

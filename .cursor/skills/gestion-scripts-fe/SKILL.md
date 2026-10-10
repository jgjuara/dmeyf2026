---
name: gestion-scripts-fe
description: >-
  Gestiona scripts DuckDB en juara/fe según versionado inmutable (build_*_vN),
  nombres alineados script/Parquet, ramificación por paso (lag/delta) y wiring en
  paths.py y capas de modelado. Usar al crear, copiar, versionar o modificar
  builders FE, parquets de competencia 01, rankings, lags/deltas, o al citar
  nota.md / juara/fe/README.md.
---

# Gestión de scripts FE (`juara/fe`)

## Fuentes canónicas

Antes de actuar, leer (o revalidar) según el alcance:

| Archivo | Contenido |
|---------|-----------|
| `juara/fe/nota.md` | Inmutabilidad, ramificación, tabla lee/escribe, checklist |
| `juara/fe/README.md` | Flujo v1, índice de scripts, módulos compartidos, env vars |
| `juara/fe/paths.py` | Rutas `*_parquet()` por artefacto |
| `juara/fe/columns.py` | Nocontinuas, columnas a rankear, exclusiones en lags |

Ejecución desde `juara/`:

```powershell
uv run fe/<script>.py
```

Datos: `JUARA_DATA_DIR` o default `juara/data`.

## Regla central

Los scripts `build_*` son **inmutables**. Si cambia la **lógica de cálculo** o las **entradas** materializadas:

1. **No** editar el script existente para cambiar semántica de salida.
2. **Copiar** a un nombre con nuevo token de versión (rama `_vN` o paso `_v<step>`).
3. Escribir Parquet con el mismo token en el nombre.
4. **No** crear alias hacia nombres sin versión.

Excepciones razonables sin bump: corrección de bug que restaura la semántica documentada; typos que no alteran salida; comentarios. Si hay duda, bump de versión.

El crudo sigue sin versión: `competencia_01_crudo.csv` (`download_competencia_crudo.py`).

## Convención de nombres

| Tipo | Script | Parquet |
|------|--------|---------|
| Base | `build_<familia>_vN.py` | `<familia>_vN.parquet` |
| Derivado capa | `build_<familia>_vN_<capa>.py` | `<familia>_vN_<capa>.parquet` |
| Derivado paso versionado | `build_<familia>_v<branch>_<capa>_v<step>.py` | `<familia>_v<branch>_<capa>_v<step>.parquet` |

- `_v<branch>`: versión del artefacto base de la familia (rankings v1, continuas v1, …).
- `_v<step>` final: versión del **proceso** de esa capa (ej. `delta2_v1` vs `delta2_v2`).
- Ejemplos: `build_rankings_v1_lag1.py` → `rankings_v1_lag1.parquet`; `build_rankings_v1_delta2_v2.py` → `rankings_v1_delta2_v2.parquet`.

## Ramificación por paso (no cadena “misma N” global)

- Cada script declara entradas vía `paths.py`; cambiar input ⇒ nuevo script + nuevo Parquet.
- **No** es obligatorio que toda la cadena comparta la misma versión de rama: un paso puede leer artefactos ya materializados de otra rama si su versión de proceso no cambió (ej. `delta2_v2` lee `rankings_v1_lag1` + `rankings_v1_lag2`).
- Lags y `delta1` leen la base de su familia/rama documentada en `nota.md`.
- **delta2** (`delta2_v1`, `delta2_v2`, …): JOIN entre capas lag; ejecutar `lag1` y `lag2` antes que cualquier `delta2_v*`.
- Ventana en builders con `LAG()`: `PARTITION BY numero_de_cliente ORDER BY foto_mes`.

| Paso delta2 | Fórmula | Entradas típicas (rankings v1) |
|-------------|---------|--------------------------------|
| v1 | t0 − lag2 | `rankings_v1` + `rankings_v1_lag2` |
| v2 | lag1 − lag2 | `rankings_v1_lag1` + `rankings_v1_lag2` |

Si cambia la **base** de la familia (nuevo `rankings_v2`), re-versionar solo los downstream que se re-materialicen; el número de paso delta2 en esa rama es independiente.

## Decidir qué hacer

```
¿Cambia la lógica o entradas de un build_* existente?
  Sí → copiar con nuevo token, nueva salida Parquet, checklist abajo
  No → ¿Nueva capa derivada (lag/delta) en una rama existente?
         Sí → nuevo script; misma rama _v<branch> salvo que también cambie la base
         No → ¿Nueva familia base desde clean?
                build_<familia>_vN.py + documentar en nota.md
```

Entrada FE estándar: `competencia_01_clean_v1.parquet` (`competencia_parquet_v1()`).

## Checklist: nuevo paso o rama

```
- [ ] Copiar script hermano; ajustar lógica y helpers paths de entrada/salida
- [ ] Parquet alineado al nombre del script
- [ ] paths.py: helpers nuevos; no dejar referencias a artefactos eliminados
- [ ] nota.md (tabla lee/escribe) y README.md si cambia el índice
- [ ] layers.py / compe1_layers.R si un experimento usará el artefacto
- [ ] columns.py / vars_nocontinuas.md si cambian columnas
- [ ] Probar: uv run fe/<script>.py desde juara/
```

## Checklist: nuevo derivado lag/delta1 (misma rama)

```
- [ ] Copiar derivado hermano (p. ej. _lag1)
- [ ] paths.py: helper si falta
- [ ] Imports: solo helpers documentados para ese script
- [ ] Fila en nota.md / README
```

## Patrón de implementación

- DuckDB; imports relativos al paquete `fe` (`from paths import …`, `from columns import …`, `from gcs_upload import …`).
- Rutas **siempre** mediante `paths.py`.
- GCS opcional: `ensure_local_parquet`, `upload_parquet`.
- Referencia lag: `build_rankings_v1_lag1.py`. Referencia delta2 JOIN: `build_rankings_v1_delta2_v1.py`.

## Qué no hacer

- Asumir “v2 de todo” cuando solo cambia un paso (ej. delta2).
- Renombrar Parquet de salida sin alinear script y `paths.py`.
- Sustituir silenciosamente qué versión usa un experimento en `layers.py`.
- Añadir documentación extra salvo `nota.md` / `README.md` del FE cuando el flujo cambia.

## Entrega al usuario

Resumir: scripts creados/eliminados, Parquets producidos, funciones nuevas en `paths.py`, capas de modelado tocadas.

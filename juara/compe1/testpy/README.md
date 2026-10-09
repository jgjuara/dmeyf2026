# testpy

Copia de trabajo del protocolo [`00py`](../00py/README.md) (misma capa `competencia_01_v1.parquet`) para pruebas locales o en VM sin mezclar artefactos con `00py`.

Convención intento–iteración: ver [`README.md`](../README.md#intentos-python-py). En la iteración `00`, **`experiment_id` = `testpy-00`** (no comparte resultados ni prefijo GCS con `00py-00`; definido en [`00/_bootstrap.py`](00/_bootstrap.py)).

**Resultados:** `juara/compe1/testpy-00/resultados/` (`bo/`, `produccion/`, `top20/`, `agosto/`, `estudio/top20_bo_semillas/`).

**Utilidades:** mismas que [`00py`](../00py/README.md).

## Comandos

```bash
cd juara
uv run python compe1/testpy/00/1_bayesiana_lightgbm.py
uv run python compe1/testpy/00/2_produccion_lightgbm.py
uv run python compe1/testpy/00/4_produccion_top20_bo_semillas.py
uv run python compe1/testpy/00/5_analisis_top20_bo_semillas.py
uv run python compe1/testpy/00/6_prediccion_agosto_top20_semillas.py
```

Variables útiles:

- `COMPE1_BO_ITER` — iteraciones Optuna (default `150`).

## VM spot y GCS (`--vm`)

En GCE, añadir `--vm` activa lectura de parquets desde `gs://<bucket>/data/` y sync con `gs://<bucket>/compe1/testpy-00/resultados/`. Sin `--vm`, solo disco local.

```bash
export JUARA_GCS_BUCKET=juarajuangabriel_buckito2026
cd juara
uv run python compe1/testpy/00/1_bayesiana_lightgbm.py --vm
```

| Variable | Default | Uso |
|----------|---------|-----|
| `JUARA_GCS_BUCKET` / `COMPE1_GCS_BUCKET` | — | Bucket (obligatorio con `--vm`) |
| `JUARA_GCS_PREFIX` | `data` | Parquets de entrada |
| `COMPE1_GCS_PREFIX` | `compe1/testpy-00/resultados` | Salidas (`experiment_id` `testpy-00`) |
| `COMPE1_GCS_SYNC_EVERY_TRIALS` | `1` | Script 1: rsync de `bo/` cada N trials |

Requisitos: `gcloud` en PATH; scope `devstorage.read_write` (ver [`juara/gce.md`](../../gce.md)).

Checkpoint BO: `testpy-00/resultados/bo/optuna.db`.

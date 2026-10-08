# nueva instance

Para subir resultados del pipeline `compe1/01py` con `COMPE1_GCS_BUCKET`, o los parquets de `juara/fe` con `JUARA_GCS_BUCKET`, la VM necesita scope de **escritura** en GCS (`devstorage.read_write` en lugar de `read_only`) y el service account debe tener permiso de objetos en el bucket (p. ej. `roles/storage.objectAdmin` en `juarajuangabriel_buckito2026`).

## Feature engineering (`juara/fe`) en VM spot

Destino por defecto: `gs://<bucket>/data/<archivo>` (p. ej. `gs://juarajuangabriel_buckito2026/data/competencia_01_v1.parquet`).

```bash
export JUARA_GCS_BUCKET=juarajuangabriel_buckito2026
cd juara
uv sync
# repo con juara/docs/vars_nocontinuas.md

uv run python fe/download_competencia_crudo.py
uv run python fe/build_competencia_01_parquet_v1.py
uv run python fe/build_competencia_01_clean_v1.py
uv run python fe/build_competencia_nocontinuas_v1.py
uv run python fe/build_competencia_nocontinuas_v1_lag1.py
uv run python fe/build_competencia_nocontinuas_v1_lag2.py
uv run python fe/build_competencia_continuas_v1.py
uv run python fe/build_competencia_continuas_v1_lag1.py
uv run python fe/build_competencia_continuas_v1_lag2.py
uv run python fe/build_competencia_continuas_v1_delta1.py
uv run python fe/build_competencia_continuas_v1_delta2.py
uv run python fe/build_rankings_v1.py
uv run python fe/build_rankings_v1_lag1.py
uv run python fe/build_rankings_v1_lag2.py
uv run python fe/build_rankings_v1_delta1.py
uv run python fe/build_rankings_v1_delta2.py
```

| Variable | Default | Uso |
|----------|---------|-----|
| `JUARA_GCS_BUCKET` | — | Activa sync GCS en FE |
| `COMPE1_GCS_BUCKET` | — | Fallback si no hay `JUARA_GCS_BUCKET` |
| `JUARA_GCS_PREFIX` | `data` | Prefijo bajo el bucket |
| `JUARA_DATA_DIR` | `juara/data` | Directorio local de datos |
| `JUARA_DATA_BASE_URL` | URL open-courses | Descarga HTTP del CSV crudo |
| `JUARA_FORCE_DOWNLOAD` | — | Re-descargar CSV (`1` / `true`) |

Requisitos: `gcloud` en PATH; cada script sube su salida con `gcloud storage cp` si el bucket está definido. Entradas parquet/CSV faltantes se bajan del mismo prefijo `data/` antes de procesar.

gcloud beta compute instances create instance-20261008-035912 \
    --project=proj-uba-261006214318442 \
    --zone=us-central1-a \
    --machine-type=e2-standard-2 \
    --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
    --metadata=enable-osconfig=TRUE \
    --no-restart-on-failure \
    --maintenance-policy=TERMINATE \
    --provisioning-model=SPOT \
    --preemption-notice-duration=120s \
    --instance-termination-action=STOP \
    --max-run-duration=172800s \
    --graceful-shutdown \
    --service-account=334185517448-compute@developer.gserviceaccount.com \
    --scopes=https://www.googleapis.com/auth/devstorage.read_write,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/trace.append \
    --tags=https-server \
    --create-disk=auto-delete=yes,boot=yes,device-name=instance-20261008-035912,image=projects/ubuntu-os-cloud/global/images/ubuntu-minimal-2404-noble-amd64-v20260918,mode=rw,size=50,type=pd-ssd \
    --no-shielded-secure-boot \
    --shielded-vtpm \
    --shielded-integrity-monitoring \
    --labels=goog-ops-agent-policy=v2-template-1-7-0,goog-ec-src=vm_add-gcloud \
    --reservation-affinity=none \
&& \
printf 'agentsRule:\n  packageState: installed\n  version: latest\ninstanceFilter:\n  inclusionLabels:\n  - labels:\n      goog-ops-agent-policy: v2-template-1-7-0\n' > config.yaml \
&& \
gcloud compute instances ops-agents policies create goog-ops-agent-v2-template-1-7-0-us-central1-a \
    --project=proj-uba-261006214318442 \
    --zone=us-central1-a \
    --file=config.yaml

## Pipeline FE en VM (prep + capas parquet)

Requisitos en la VM: `git`, `uv`, `gcloud` con acceso al bucket. Clonar el repo (incluye `juara/docs/vars_nocontinuas.md`).

```bash
export JUARA_GCS_BUCKET=juarajuangabriel_buckito2026
cd juara
uv sync

# Prep: crudo + competencia_01_v1.parquet (clase_ternaria) + clean v1
uv run python fe/download_competencia_crudo.py
uv run python fe/build_competencia_01_parquet_v1.py
uv run python fe/build_competencia_01_clean_v1.py

# FE (orden alineado con compe1/README.md)
uv run python fe/build_competencia_nocontinuas_v1.py
uv run python fe/build_competencia_nocontinuas_v1_lag1.py
uv run python fe/build_competencia_nocontinuas_v1_lag2.py
uv run python fe/build_rankings_v1.py
uv run python fe/build_rankings_v1_lag1.py
uv run python fe/build_rankings_v1_lag2.py
uv run python fe/build_rankings_v1_delta1.py
uv run python fe/build_rankings_v1_delta2.py
uv run python fe/build_competencia_continuas_v1.py
uv run python fe/build_competencia_continuas_v1_lag1.py
uv run python fe/build_competencia_continuas_v1_lag2.py
uv run python fe/build_competencia_continuas_v1_delta1.py
uv run python fe/build_competencia_continuas_v1_delta2.py
```

Sin `JUARA_GCS_BUCKET` / `COMPE1_GCS_BUCKET`, los scripts solo leen y escriben en disco local (`juara/data/` por defecto).

### Variables de entorno (datos y GCS)

| Variable | Default | Uso |
|----------|---------|-----|
| `JUARA_GCS_BUCKET` | — | Activa sync GCS (`gcloud storage cp`) |
| `COMPE1_GCS_BUCKET` | — | Fallback si no hay `JUARA_GCS_BUCKET` |
| `JUARA_GCS_PREFIX` | `data` | Prefijo en el bucket (`gs://<bucket>/<prefix>/<archivo>`) |
| `JUARA_DATA_DIR` | `juara/data` | Directorio local de parquets y CSV |
| `JUARA_DATA_BASE_URL` | `https://storage.googleapis.com/open-courses/dmeyf2026-9c6f/` | Base HTTP para `competencia_01_crudo.csv` |
| `JUARA_FORCE_DOWNLOAD` | — | `1` / `true` fuerza re-descarga del CSV aunque exista local |

Objetos en bucket (misma estructura plana que `juara/data/`): `competencia_01_crudo.csv`, `competencia_01_v1.parquet`, `competencia_01_clean_v1.parquet`, y el resto de salidas `build_*_v1*.py` (`*_v1.parquet`).

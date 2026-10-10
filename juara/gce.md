# VM nueva (spot, labo-image)

Flujo asumido: **crear instancia nueva** con el comando de abajo; no hay pasos de migración ni reparación de VMs existentes.

## Requisitos (proyecto GCP)

- Scope OAuth: `devstorage.read_write` (incluido en el `create` de abajo).
- IAM del service account de compute sobre el bucket (una vez):

```bash
gcloud storage buckets add-iam-policy-binding gs://juarajuangabriel_buckito2026 --member="serviceAccount:334185517448-compute@developer.gserviceaccount.com" --role="roles/storage.objectAdmin" --project=proj-uba-261006214318442
```

## Crear instancia

Desde la **raíz de un clon local** del repo (para resolver `juara/gce-startup.sh`).

`gcloud compute instances create` **exige** un nombre de instancia; Compute no asigna uno automáticamente (la consola web sugiere uno, pero hay que fijarlo). Para spot desechable suele bastar un nombre generado (minúsculas, números y guiones; máx. 63 caracteres). El disco de arranque no necesita `device-name` aparte.

```bash
INSTANCE_NAME="fe-spot-$(date -u +%Y%m%d-%H%M%S)"
gcloud beta compute instances create "$INSTANCE_NAME" \
    --project=proj-uba-261006214318442 \
    --zone=us-west4-b \
    --machine-type=e2-highmem-4 \
    --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
    --no-restart-on-failure \
    --maintenance-policy=TERMINATE \
    --provisioning-model=SPOT \
    --instance-termination-action=DELETE \
    --max-run-duration=21600s \
    --service-account=334185517448-compute@developer.gserviceaccount.com \
    --scopes=https://www.googleapis.com/auth/devstorage.read_write,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/trace.append \
    --tags=http-server,https-server \
    --create-disk=auto-delete=yes,boot=yes,image=projects/proj-uba-261006214318442/global/images/labo-image,mode=rw,size=70,type=pd-balanced \
    --no-shielded-secure-boot \
    --shielded-vtpm \
    --shielded-integrity-monitoring \
    --labels=goog-ec-src=vm_add-gcloud \
    --reservation-affinity=none \
    --metadata-from-file=startup-script=juara/gce-startup.sh
echo "Instancia creada: $INSTANCE_NAME"
```

PowerShell (misma raíz del repo). **No** pegar el `create` en una sola línea sin comillas: PowerShell trocea en cada coma y `gcloud` recibe argumentos inválidos (`stack-type=…`, `https-server`, `boot=yes`, etc.). Copiar el bloque completo; los flags con comas van entre **comillas simples** `'…'`.

```powershell
$InstanceName = "fe-spot-{0:yyyyMMdd-HHmmss}" -f (Get-Date).ToUniversalTime()
gcloud beta compute instances create $InstanceName `
    --project=proj-uba-261006214318442 `
    --zone=us-west4-b `
    --machine-type=e2-highmem-4 `
    '--network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default' `
    --no-restart-on-failure `
    --maintenance-policy=TERMINATE `
    --provisioning-model=SPOT `
    --instance-termination-action=DELETE `
    --max-run-duration=21600s `
    --service-account=334185517448-compute@developer.gserviceaccount.com `
    '--scopes=https://www.googleapis.com/auth/devstorage.read_write,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/trace.append' `
    '--tags=http-server,https-server' `
    '--create-disk=auto-delete=yes,boot=yes,image=projects/proj-uba-261006214318442/global/images/labo-image,mode=rw,size=70,type=pd-balanced' `
    --no-shielded-secure-boot `
    --shielded-vtpm `
    --shielded-integrity-monitoring `
    --labels=goog-ec-src=vm_add-gcloud `
    --reservation-affinity=none `
    --metadata-from-file=startup-script=juara/gce-startup.sh
Write-Host "Instancia creada: $InstanceName"
```

### Primer arranque (`juara/gce-startup.sh`)

En el **primer** boot (como root): instala `git` y `uv` (`/usr/local/bin/uv`), clona [dmeyf2026](https://github.com/jgjuara/dmeyf2026.git) en `~/dmeyf2026` del usuario de la imagen (p. ej. `juarajuangabriel`). Deja marca en `/var/lib/dmeyf2026-gce-bootstrap.done`; en reinicios posteriores no hace nada.

Log: `journalctl -t gce-startup`. Si solo aparece «instalando uv» y no «bootstrap completado», revisar `/usr/local/uv` (instalación fallida con `UV_INSTALL_DIR=/usr/local` en versiones viejas del script) o repetir el bootstrap borrando la marca y ejecutando el script como root.

Comprobación tras SSH:

```bash
uv --version
ls ~/dmeyf2026/juara
```

## Trabajo en la VM

```bash
cd ~/dmeyf2026/juara
uv sync
export JUARA_GCS_BUCKET=juarajuangabriel_buckito2026
```

`gcloud` en la imagen labo; auth vía service account de la VM (scopes + IAM del bucket).

### compe1 (`--vm`)

Entradas: `gs://<bucket>/data/`. Salidas: `gs://<bucket>/compe1/<experiment_id>/resultados/`.

```bash
uv run python compe1/00py/00/1_bayesiana_lightgbm.py --vm
# compe1/01py/00/... --vm  |  compe1/testpy/00/... --vm
```

### Feature engineering (`juara/fe`)

Artefactos en `gs://<bucket>/data/<archivo>` (misma lista plana que `juara/data/`).

```bash
uv run python fe/download_competencia_crudo.py
uv run python fe/build_competencia_01_parquet_v1.py
uv run python fe/build_competencia_01_clean_v1.py
uv run python fe/build_competencia_nocontinuas_v1.py
uv run python fe/build_competencia_nocontinuas_v1_lag1.py
uv run python fe/build_competencia_nocontinuas_v1_lag2.py
uv run python fe/build_rankings_v1.py
uv run python fe/build_rankings_v1_lag1.py
uv run python fe/build_rankings_v1_lag2.py
uv run python fe/build_rankings_v1_delta1.py
uv run python fe/build_rankings_v1_delta2_v1.py
uv run python fe/build_rankings_v1_delta2_v2.py
uv run python fe/build_competencia_continuas_v1.py
uv run python fe/build_competencia_continuas_v1_lag1.py
uv run python fe/build_competencia_continuas_v1_lag2.py
uv run python fe/build_competencia_continuas_v1_delta1.py
uv run python fe/build_competencia_continuas_v1_delta2_v1.py
uv run python fe/build_competencia_continuas_v1_delta2_v2.py
```

Cada builder con bucket definido sube con `gcloud storage cp`; si falta un parquet local, lo baja del prefijo `data/` antes de procesar.

## Variables de entorno

| Variable | Default | Uso |
|----------|---------|-----|
| `JUARA_GCS_BUCKET` | — | Activa sync GCS en FE / compe1 `--vm` |
| `COMPE1_GCS_BUCKET` | — | Fallback si no hay `JUARA_GCS_BUCKET` |
| `JUARA_GCS_PREFIX` | `data` | Prefijo en el bucket |
| `JUARA_DATA_DIR` | `juara/data` | Datos locales |
| `JUARA_DATA_BASE_URL` | open-courses GCS | HTTP del CSV crudo |
| `JUARA_FORCE_DOWNLOAD` | — | `1` / `true` re-descarga el crudo |

Sin `JUARA_GCS_BUCKET` / `COMPE1_GCS_BUCKET`, solo disco local bajo `JUARA_DATA_DIR`.

## ejemplo acceso ssh

gcloud compute ssh juarajuangabriel@fe-spot-20261009-223316 `
  --project=proj-uba-261006214318442 `
  --zone=us-west4-b

## ejemplo cierre y eliminacion 

gcloud compute instances delete fe-spot-20261009-223316 `
  --project=proj-uba-261006214318442 `
  --zone=us-west4-b `
  --quiet

## listar instacnias

gcloud compute instances list --project=proj-uba-261006214318442
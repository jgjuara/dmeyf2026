"""Sincroniza salidas de resultados a GCS vía gcloud (opt-in por COMPE1_GCS_BUCKET)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from common.layers import resultados_dir


def gcs_enabled() -> bool:
    return bool(os.environ.get("COMPE1_GCS_BUCKET", "").strip())


def _default_prefix(experiment_id: str) -> str:
    override = os.environ.get("COMPE1_GCS_PREFIX", "").strip()
    if override:
        return override.rstrip("/")
    return f"compe1/{experiment_id}/00/resultados"


def gcs_uri(experiment_id: str, *parts: str) -> str:
    bucket = os.environ["COMPE1_GCS_BUCKET"].strip()
    prefix = _default_prefix(experiment_id)
    rel = "/".join(p.strip("/").replace("\\", "/") for p in parts if p)
    if rel:
        return f"gs://{bucket}/{prefix}/{rel}"
    return f"gs://{bucket}/{prefix}"


def sync_every_trials() -> int:
    raw = os.environ.get("COMPE1_GCS_SYNC_EVERY_TRIALS", "1").strip()
    try:
        n = int(raw)
    except ValueError:
        raise ValueError(f"COMPE1_GCS_SYNC_EVERY_TRIALS inválido: {raw}") from None
    if n < 1:
        raise ValueError(f"COMPE1_GCS_SYNC_EVERY_TRIALS debe ser >= 1, recibido: {n}")
    return n


def sync_local_dir(local_dir: Path, destination_uri: str) -> None:
    if not gcs_enabled():
        return
    local = Path(local_dir).resolve()
    if not local.is_dir():
        raise FileNotFoundError(f"No existe directorio local para sync GCS: {local}")
    dest = destination_uri.rstrip("/") + "/"
    print(f"[gcs] rsync {local} → {dest}", flush=True)
    subprocess.run(
        ["gcloud", "storage", "rsync", "-r", str(local), dest],
        check=True,
    )


def sync_resultados_subdir(experiment_id: str, subpath: str) -> None:
    if not gcs_enabled():
        return
    local = resultados_dir(experiment_id) / subpath
    sync_local_dir(local, gcs_uri(experiment_id, subpath))

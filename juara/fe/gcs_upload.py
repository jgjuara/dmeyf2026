"""Sync juara/data artifacts with GCS via gcloud (opt-in by JUARA_GCS_BUCKET or COMPE1_GCS_BUCKET)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def gcs_enabled() -> bool:
    return bool(
        os.environ.get("JUARA_GCS_BUCKET", "").strip()
        or os.environ.get("COMPE1_GCS_BUCKET", "").strip()
    )


def _bucket() -> str:
    bucket = os.environ.get("JUARA_GCS_BUCKET", "").strip()
    if bucket:
        return bucket
    bucket = os.environ.get("COMPE1_GCS_BUCKET", "").strip()
    if not bucket:
        raise RuntimeError("GCS bucket no configurado")
    return bucket


def gcs_prefix() -> str:
    override = os.environ.get("JUARA_GCS_PREFIX", "").strip()
    if override:
        return override.rstrip("/")
    return "data"


def gcs_uri(basename: str) -> str:
    name = Path(basename).name
    bucket = _bucket()
    prefix = gcs_prefix()
    return f"gs://{bucket}/{prefix}/{name}"


def ensure_local_file(path: Path) -> None:
    if not gcs_enabled():
        return
    local = Path(path).resolve()
    if local.is_file():
        return
    local.parent.mkdir(parents=True, exist_ok=True)
    uri = gcs_uri(local.name)
    print(f"[gcs] cp {uri} → {local}", flush=True)
    subprocess.run(
        ["gcloud", "storage", "cp", uri, str(local)],
        check=True,
    )


def upload_file(path: Path) -> None:
    if not gcs_enabled():
        return
    local = Path(path).resolve()
    if not local.is_file():
        raise FileNotFoundError(f"No existe archivo local para subir a GCS: {local}")
    uri = gcs_uri(local.name)
    print(f"[gcs] cp {local} → {uri}", flush=True)
    subprocess.run(
        ["gcloud", "storage", "cp", str(local), uri],
        check=True,
    )


def ensure_local_parquet(path: Path) -> None:
    ensure_local_file(path)


def upload_parquet(path: Path) -> None:
    upload_file(path)

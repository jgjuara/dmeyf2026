"""Sync datos y resultados compe1 con GCS vía gcloud (solo con --vm)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from common.layers import cache_dir, experiment_storage_prefix, resultados_dir
from common.vm_runtime import vm_mode


def _bucket() -> str:
    bucket = os.environ.get("JUARA_GCS_BUCKET", "").strip()
    if bucket:
        return bucket
    bucket = os.environ.get("COMPE1_GCS_BUCKET", "").strip()
    if bucket:
        return bucket
    raise RuntimeError(
        "Modo --vm requiere JUARA_GCS_BUCKET o COMPE1_GCS_BUCKET en el entorno"
    )


def gcs_enabled() -> bool:
    if not vm_mode():
        return False
    return bool(
        os.environ.get("JUARA_GCS_BUCKET", "").strip()
        or os.environ.get("COMPE1_GCS_BUCKET", "").strip()
    )


def _require_vm_bucket() -> None:
    if not vm_mode():
        return
    _bucket()


def _data_prefix() -> str:
    override = os.environ.get("JUARA_GCS_PREFIX", "").strip()
    if override:
        return override.rstrip("/")
    return "data"


def data_gcs_uri(basename: str) -> str:
    name = Path(basename).name
    return f"gs://{_bucket()}/{_data_prefix()}/{name}"


def _default_resultados_prefix(experiment_id: str) -> str:
    override = os.environ.get("COMPE1_GCS_PREFIX", "").strip()
    if override:
        return override.rstrip("/")
    return f"{experiment_storage_prefix(experiment_id)}/resultados"


def _cache_prefix(experiment_id: str) -> str:
    return f"{experiment_storage_prefix(experiment_id)}/cache"


def gcs_uri(experiment_id: str, *parts: str) -> str:
    bucket = _bucket()
    prefix = _default_resultados_prefix(experiment_id)
    rel = "/".join(p.strip("/").replace("\\", "/") for p in parts if p)
    if rel:
        return f"gs://{bucket}/{prefix}/{rel}"
    return f"gs://{bucket}/{prefix}"


def cache_gcs_uri(experiment_id: str, *parts: str) -> str:
    bucket = _bucket()
    prefix = _cache_prefix(experiment_id)
    rel = "/".join(p.strip("/").replace("\\", "/") for p in parts if p)
    if rel:
        return f"gs://{bucket}/{prefix}/{rel}"
    return f"gs://{bucket}/{prefix}"


def _remote_prefix_exists(uri: str) -> bool:
    prefix = uri.rstrip("/") + "/"
    proc = subprocess.run(
        ["gcloud", "storage", "ls", prefix],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0 and bool(proc.stdout.strip())


def ensure_data_file(path: Path) -> None:
    if not vm_mode():
        return
    _require_vm_bucket()
    local = Path(path).resolve()
    if local.is_file():
        return
    local.parent.mkdir(parents=True, exist_ok=True)
    uri = data_gcs_uri(local.name)
    print(f"[gcs] cp {uri} → {local}", flush=True)
    subprocess.run(["gcloud", "storage", "cp", uri, str(local)], check=True)


def upload_data_file(path: Path) -> None:
    if not vm_mode():
        return
    _require_vm_bucket()
    local = Path(path).resolve()
    if not local.is_file():
        raise FileNotFoundError(f"No existe archivo local para subir a GCS: {local}")
    uri = data_gcs_uri(local.name)
    print(f"[gcs] cp {local} → {uri}", flush=True)
    subprocess.run(["gcloud", "storage", "cp", str(local), uri], check=True)


def sync_every_trials() -> int:
    raw = os.environ.get("COMPE1_GCS_SYNC_EVERY_TRIALS", "1").strip()
    try:
        n = int(raw)
    except ValueError:
        raise ValueError(f"COMPE1_GCS_SYNC_EVERY_TRIALS inválido: {raw}") from None
    if n < 1:
        raise ValueError(f"COMPE1_GCS_SYNC_EVERY_TRIALS debe ser >= 1, recibido: {n}")
    return n


def _rsync_upload(local_dir: Path, destination_uri: str) -> None:
    local = Path(local_dir).resolve()
    if not local.is_dir():
        raise FileNotFoundError(f"No existe directorio local para sync GCS: {local}")
    dest = destination_uri.rstrip("/") + "/"
    print(f"[gcs] rsync {local} → {dest}", flush=True)
    subprocess.run(
        ["gcloud", "storage", "rsync", "-r", str(local), dest],
        check=True,
    )


def _rsync_download(source_uri: str, local_dir: Path) -> None:
    local = Path(local_dir).resolve()
    local.mkdir(parents=True, exist_ok=True)
    src = source_uri.rstrip("/") + "/"
    print(f"[gcs] rsync {src} → {local}", flush=True)
    subprocess.run(
        ["gcloud", "storage", "rsync", "-r", src, str(local)],
        check=True,
    )


def sync_local_dir(local_dir: Path, destination_uri: str) -> None:
    if not vm_mode():
        return
    _require_vm_bucket()
    _rsync_upload(local_dir, destination_uri)


def pull_local_dir(local_dir: Path, source_uri: str, optional: bool = False) -> None:
    if not vm_mode():
        return
    _require_vm_bucket()
    if optional and not _remote_prefix_exists(source_uri):
        return
    _rsync_download(source_uri, local_dir)


def sync_resultados_subdir(experiment_id: str, subpath: str) -> None:
    if not vm_mode():
        return
    local = resultados_dir(experiment_id) / subpath
    sync_local_dir(local, gcs_uri(experiment_id, subpath))


def pull_resultados_subdir(
    experiment_id: str, subpath: str, optional: bool = False
) -> None:
    if not vm_mode():
        return
    local = resultados_dir(experiment_id) / subpath
    pull_local_dir(local, gcs_uri(experiment_id, subpath), optional=optional)


def sync_cache_subdir(experiment_id: str) -> None:
    if not vm_mode():
        return
    local = cache_dir(experiment_id)
    sync_local_dir(local, cache_gcs_uri(experiment_id))


def pull_cache_subdir(experiment_id: str, optional: bool = True) -> None:
    if not vm_mode():
        return
    local = cache_dir(experiment_id)
    pull_local_dir(local, cache_gcs_uri(experiment_id), optional=optional)


def upload_cache_file(experiment_id: str, filename: str) -> None:
    if not vm_mode():
        return
    _require_vm_bucket()
    local = cache_dir(experiment_id) / filename
    if not local.is_file():
        raise FileNotFoundError(f"No existe cache local: {local}")
    uri = cache_gcs_uri(experiment_id, filename)
    print(f"[gcs] cp {local} → {uri}", flush=True)
    subprocess.run(["gcloud", "storage", "cp", str(local), uri], check=True)


def pull_cache_file(experiment_id: str, filename: str, optional: bool = True) -> None:
    if not vm_mode():
        return
    _require_vm_bucket()
    local = cache_dir(experiment_id) / filename
    if local.is_file():
        return
    uri = cache_gcs_uri(experiment_id, filename)
    local.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["gcloud", "storage", "cp", uri, str(local)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        if optional:
            return
        raise subprocess.CalledProcessError(
            proc.returncode, proc.args, proc.stdout, proc.stderr
        )
    print(f"[gcs] cp {uri} → {local}", flush=True)

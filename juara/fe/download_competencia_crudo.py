"""Download competencia_01_crudo.csv to juara/data (HTTP + optional GCS cache)."""

from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

from gcs_upload import ensure_local_file, gcs_enabled, upload_file
from paths import DATA_DIR, competencia_crudo_csv

DEFAULT_BASE_URL = "https://storage.googleapis.com/open-courses/dmeyf2026-9c6f/"
CRUDO_BASENAME = "competencia_01_crudo.csv"


def _base_url() -> str:
    raw = os.environ.get("JUARA_DATA_BASE_URL", DEFAULT_BASE_URL).strip()
    return raw if raw.endswith("/") else f"{raw}/"


def _force_download() -> bool:
    return os.environ.get("JUARA_FORCE_DOWNLOAD", "").strip() in ("1", "true", "yes", "TRUE")


def download_competencia_crudo() -> Path:
    dest = competencia_crudo_csv()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if gcs_enabled():
        ensure_local_file(dest)

    if _force_download() and dest.is_file():
        dest.unlink()

    if not dest.is_file():
        url = f"{_base_url()}{CRUDO_BASENAME}"
        print(f"descargando {url} → {dest}", flush=True)
        urllib.request.urlretrieve(url, dest)

    if gcs_enabled():
        upload_file(dest)

    return dest


def main() -> None:
    dest = download_competencia_crudo()
    print(dest)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

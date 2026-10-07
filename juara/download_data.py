"""Descarga datasets de la tarea hogar 02 a juara/data."""

from pathlib import Path
import urllib.request

JUARA_DIR = Path.cwd() if Path.cwd().name == "juara" else Path.cwd() / "juara"
DATA_DIR = JUARA_DIR / "data"
EXP_DIR = JUARA_DIR / "exp"
BASE_URL = "https://storage.googleapis.com/open-courses/dmeyf2026-9c6f/"


def descargar(archivo: str) -> Path:
    destino = DATA_DIR / archivo
    if not destino.exists():
        urllib.request.urlretrieve(f"{BASE_URL}{archivo}", destino)
    return destino


def main() -> None:
    for directory in (DATA_DIR, EXP_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    destino = descargar("competencia_01_crudo.csv")
    print(destino)


if __name__ == "__main__":
    main()

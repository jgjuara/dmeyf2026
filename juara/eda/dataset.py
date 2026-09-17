"""CSV de EDA: FILENAME en eda/.env o en el entorno."""

from pathlib import Path
import os

from dotenv import load_dotenv

EDA_DIR = Path(__file__).resolve().parent
JUARA_DIR = EDA_DIR.parent

load_dotenv(EDA_DIR / ".env")


def filename() -> str:
    name = os.environ.get("FILENAME", "").strip()
    if not name:
        raise SystemExit(
            "Definí FILENAME en juara/eda/.env (copiá desde .env.example)."
        )
    if not (name.endswith(".csv.gz") or name.endswith(".csv")):
        raise SystemExit("FILENAME debe ser .csv o .csv.gz")
    return name


def input_path() -> Path:
    path = JUARA_DIR / "data" / filename()
    if not path.is_file():
        raise SystemExit(f"Archivo inexistente: {path}")
    return path

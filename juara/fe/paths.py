"""Rutas de datos para ingeniería de variables en juara."""

from pathlib import Path

FE_DIR = Path(__file__).resolve().parent
JUARA_DIR = FE_DIR.parent
DATA_DIR = JUARA_DIR / "data"
NOCONTINUAS_PATH = JUARA_DIR / "docs" / "vars_nocontinuas.md"


def competencia_parquet() -> Path:
    return DATA_DIR / "competencia_01.parquet"


def rankings_parquet() -> Path:
    return DATA_DIR / "rankings.parquet"


def rankings_lag1_parquet() -> Path:
    return DATA_DIR / "rankings_lag1.parquet"


def rankings_lag2_parquet() -> Path:
    return DATA_DIR / "rankings_lag2.parquet"


def rankings_delta1_parquet() -> Path:
    return DATA_DIR / "rankings_delta1.parquet"


def rankings_delta2_parquet() -> Path:
    return DATA_DIR / "rankings_delta2.parquet"


def competencia_nocontinuas_parquet() -> Path:
    return DATA_DIR / "competencia_01_nocontinuas.parquet"


def competencia_nocontinuas_lag1_parquet() -> Path:
    return DATA_DIR / "competencia_01_nocontinuas_lag1.parquet"


def competencia_nocontinuas_lag2_parquet() -> Path:
    return DATA_DIR / "competencia_01_nocontinuas_lag2.parquet"


def competencia_continuas_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas.parquet"


def competencia_continuas_lag1_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas_lag1.parquet"


def competencia_continuas_lag2_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas_lag2.parquet"


def competencia_continuas_delta1_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas_delta1.parquet"


def competencia_continuas_delta2_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas_delta2.parquet"


def competencia_continuas_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas.parquet"


def competencia_continuas_lag1_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas_lag1.parquet"


def competencia_continuas_lag2_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas_lag2.parquet"


def competencia_continuas_delta1_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas_delta1.parquet"


def competencia_continuas_delta2_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas_delta2.parquet"

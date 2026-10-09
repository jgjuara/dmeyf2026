"""Rutas de datos para ingeniería de variables en juara (artefactos versionados)."""

import os
from pathlib import Path

FE_DIR = Path(__file__).resolve().parent
JUARA_DIR = FE_DIR.parent
_data_dir_override = os.environ.get("JUARA_DATA_DIR", "").strip()
DATA_DIR = Path(_data_dir_override).resolve() if _data_dir_override else JUARA_DIR / "data"
NOCONTINUAS_PATH = JUARA_DIR / "docs" / "vars_nocontinuas.md"


def competencia_crudo_csv() -> Path:
    return DATA_DIR / "competencia_01_crudo.csv"


def competencia_parquet_labeled_v1() -> Path:
    return DATA_DIR / "competencia_01_v1.parquet"


def competencia_parquet_clean_v1() -> Path:
    return DATA_DIR / "competencia_01_clean_v1.parquet"


def competencia_parquet_v1() -> Path:
    return competencia_parquet_clean_v1()


def rankings_v1_parquet() -> Path:
    return DATA_DIR / "rankings_v1.parquet"


def rankings_v1_lag1_parquet() -> Path:
    return DATA_DIR / "rankings_v1_lag1.parquet"


def rankings_v1_lag2_parquet() -> Path:
    return DATA_DIR / "rankings_v1_lag2.parquet"


def rankings_v1_delta1_parquet() -> Path:
    return DATA_DIR / "rankings_v1_delta1.parquet"


def rankings_v1_delta2_parquet() -> Path:
    return DATA_DIR / "rankings_v1_delta2.parquet"


def rankings_v2_parquet() -> Path:
    return DATA_DIR / "rankings_v2.parquet"


def rankings_v2_delta2_parquet() -> Path:
    return DATA_DIR / "rankings_v2_delta2.parquet"


def competencia_nocontinuas_v1_parquet() -> Path:
    return DATA_DIR / "competencia_01_nocontinuas_v1.parquet"


def competencia_nocontinuas_v1_lag1_parquet() -> Path:
    return DATA_DIR / "competencia_01_nocontinuas_v1_lag1.parquet"


def competencia_nocontinuas_v1_lag2_parquet() -> Path:
    return DATA_DIR / "competencia_01_nocontinuas_v1_lag2.parquet"


def competencia_continuas_v1_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas_v1.parquet"


def competencia_continuas_v1_lag1_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas_v1_lag1.parquet"


def competencia_continuas_v1_lag2_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas_v1_lag2.parquet"


def competencia_continuas_v1_delta1_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas_v1_delta1.parquet"


def competencia_continuas_v1_delta2_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas_v1_delta2.parquet"


def competencia_continuas_v2_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas_v2.parquet"


def competencia_continuas_v2_delta2_parquet() -> Path:
    return DATA_DIR / "competencia_01_continuas_v2_delta2.parquet"

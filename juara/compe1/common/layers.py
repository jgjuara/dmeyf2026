"""Rutas de capas parquet y resultados para experimentos compe1."""

from __future__ import annotations

from pathlib import Path

JUARA_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = JUARA_DIR / "data"
COMPE1_DIR = JUARA_DIR / "compe1"

COMPE1_EXPERIMENT_IDS = (
    "00",
    "01_full_fe",
    "02_rank_nocont",
    "02_rank_nocount_py",
    "03_rank_nocont_lag1_delta1",
    "03_cont_nocont_lag1_delta1",
)

_LAYERS_BY_ID: dict[str, tuple[str, ...]] = {
    "00": ("competencia_01.parquet",),
    "01_full_fe": (
        "competencia_01_nocontinuas.parquet",
        "competencia_01_nocontinuas_lag1.parquet",
        "competencia_01_nocontinuas_lag2.parquet",
        "rankings.parquet",
        "rankings_lag1.parquet",
        "rankings_lag2.parquet",
        "rankings_delta1.parquet",
        "rankings_delta2.parquet",
    ),
    "02_rank_nocont": (
        "competencia_01_nocontinuas.parquet",
        "rankings.parquet",
    ),
    "02_rank_nocount_py": (
        "competencia_01_nocontinuas.parquet",
        "rankings.parquet",
    ),
    "03_rank_nocont_lag1_delta1": (
        "competencia_01_nocontinuas.parquet",
        "rankings.parquet",
        "competencia_01_nocontinuas_lag1.parquet",
        "rankings_lag1.parquet",
        "rankings_delta1.parquet",
    ),
    "03_cont_nocont_lag1_delta1": (
        "competencia_01_nocontinuas.parquet",
        "competencia_01_continuas.parquet",
        "competencia_01_nocontinuas_lag1.parquet",
        "competencia_01_continuas_lag1.parquet",
        "competencia_01_continuas_delta1.parquet",
    ),
}


def assert_experiment_id(experiment_id: str) -> None:
    if experiment_id not in COMPE1_EXPERIMENT_IDS:
        raise ValueError(
            f"experiment_id debe ser uno de: {', '.join(COMPE1_EXPERIMENT_IDS)}"
        )


def resultados_dir(experiment_id: str) -> Path:
    assert_experiment_id(experiment_id)
    return COMPE1_DIR / experiment_id / "00" / "resultados"


def cache_dir(experiment_id: str) -> Path:
    return COMPE1_DIR / experiment_id / "00" / "cache"


def layers_paths(experiment_id: str) -> list[Path]:
    assert_experiment_id(experiment_id)
    return [DATA_DIR / name for name in _LAYERS_BY_ID[experiment_id]]

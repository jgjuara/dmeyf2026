"""Rutas de capas parquet y resultados para experimentos compe1.

Intentos Python activos usan ``experiment_id`` compuesto ``{intento}-{iter}``
(p. ej. ``testpy-00``); ver ``compe1/README.md`` (Intentos Python).
"""

from __future__ import annotations

import re
from pathlib import Path

JUARA_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = JUARA_DIR / "data"
COMPE1_DIR = JUARA_DIR / "compe1"

# Ids legados (R / archivo): sin guión intento-iteración.
COMPE1_EXPERIMENT_IDS = (
    "00",
    "01_full_fe",
    "02_rank_nocont",
    "02_rank_nocount_py",
    "03_rank_nocont_lag1_delta1",
    "03_cont_nocont_lag1_delta1",
)

_ITER_SUFFIX = re.compile(r"^\d{2}$")

_PY_ATTEMPT_IDS = frozenset({"00py", "01py", "testpy"})

_LAYERS_BY_ID: dict[str, tuple[str, ...]] = {
    "00": ("competencia_01_v1.parquet",),
    "00py": ("competencia_01_v1.parquet",),
    "testpy": ("competencia_01_v1.parquet",),
    "01py": (
        "competencia_01_nocontinuas_v1.parquet",
        "competencia_01_nocontinuas_v1_lag1.parquet",
        "competencia_01_nocontinuas_v1_lag2.parquet",
        "rankings_v1.parquet",
        "rankings_v1_lag1.parquet",
        "rankings_v1_lag2.parquet",
        "rankings_v1_delta1.parquet",
        "rankings_v1_delta2_v2.parquet",
    ),
    "01_full_fe": (
        "competencia_01_nocontinuas_v1.parquet",
        "competencia_01_nocontinuas_v1_lag1.parquet",
        "competencia_01_nocontinuas_v1_lag2.parquet",
        "rankings_v1.parquet",
        "rankings_v1_lag1.parquet",
        "rankings_v1_lag2.parquet",
        "rankings_v1_delta1.parquet",
        "rankings_v1_delta2_v2.parquet",
    ),
    "02_rank_nocont": (
        "competencia_01_nocontinuas_v1.parquet",
        "rankings_v1.parquet",
    ),
    "02_rank_nocount_py": (
        "competencia_01_nocontinuas_v1.parquet",
        "rankings_v1.parquet",
    ),
    "03_rank_nocont_lag1_delta1": (
        "competencia_01_nocontinuas_v1.parquet",
        "rankings_v1.parquet",
        "competencia_01_nocontinuas_v1_lag1.parquet",
        "rankings_v1_lag1.parquet",
        "rankings_v1_delta1.parquet",
    ),
    "03_cont_nocont_lag1_delta1": (
        "competencia_01_nocontinuas_v1.parquet",
        "competencia_01_continuas_v1.parquet",
        "competencia_01_nocontinuas_v1_lag1.parquet",
        "competencia_01_continuas_v1_lag1.parquet",
        "competencia_01_continuas_v1_delta1.parquet",
    ),
}


def is_compound_experiment_id(experiment_id: str) -> bool:
    if "-" not in experiment_id:
        return False
    attempt, iteration = experiment_id.rsplit("-", 1)
    return bool(attempt) and _ITER_SUFFIX.match(iteration) is not None


def parse_experiment_id(experiment_id: str) -> tuple[str, str]:
    """Devuelve (intento, iteración). Legado: iteración fija ``00``."""
    if is_compound_experiment_id(experiment_id):
        attempt, iteration = experiment_id.rsplit("-", 1)
        return attempt, iteration
    return experiment_id, "00"


def attempt_layer_id(experiment_id: str) -> str:
    return parse_experiment_id(experiment_id)[0]


def _uses_attempt_iteration_layout(experiment_id: str) -> bool:
    if is_compound_experiment_id(experiment_id):
        return True
    attempt, _ = parse_experiment_id(experiment_id)
    return experiment_id == attempt and attempt.endswith("py")


def assert_experiment_id(experiment_id: str) -> None:
    attempt, iteration = parse_experiment_id(experiment_id)
    if attempt not in _LAYERS_BY_ID:
        raise ValueError(
            f"experiment_id desconocido (intento '{attempt}' sin capas parquet)"
        )
    if attempt in _PY_ATTEMPT_IDS:
        if not is_compound_experiment_id(experiment_id):
            raise ValueError(
                f"Los intentos Python requieren experiment_id compuesto "
                f"(p. ej. {attempt}-{iteration}); recibido: {experiment_id}"
            )
        return
    if is_compound_experiment_id(experiment_id):
        return
    if experiment_id in COMPE1_EXPERIMENT_IDS:
        return
    if _uses_attempt_iteration_layout(experiment_id):
        return
    raise ValueError(
        f"experiment_id debe ser legado ({', '.join(COMPE1_EXPERIMENT_IDS)}) "
        f"o intento-iter (p. ej. 00py-00); recibido: {experiment_id}"
    )


def assert_param_experiment_id(param: dict, experiment_id: str) -> None:
    """Falla si ``PARAM.yml`` pertenece a otro intento-iteración."""
    stored = param.get("experiment_id")
    if stored is not None and stored != experiment_id:
        raise ValueError(
            f"PARAM.yml experiment_id={stored!r} no coincide con {experiment_id!r}"
        )


SUBDIR_BO = "bo"
SUBDIR_PRODUCCION = "produccion"
SUBDIR_TOP20 = "top20"
SUBDIR_AGOSTO = "agosto"


def resultados_dir(experiment_id: str) -> Path:
    assert_experiment_id(experiment_id)
    if _uses_attempt_iteration_layout(experiment_id):
        return COMPE1_DIR / experiment_id / "resultados"
    return COMPE1_DIR / experiment_id / "00" / "resultados"


def cache_dir(experiment_id: str) -> Path:
    assert_experiment_id(experiment_id)
    if _uses_attempt_iteration_layout(experiment_id):
        return COMPE1_DIR / experiment_id / "cache"
    return COMPE1_DIR / experiment_id / "00" / "cache"


def bo_dir(experiment_id: str) -> Path:
    return resultados_dir(experiment_id) / SUBDIR_BO


def produccion_dir(experiment_id: str) -> Path:
    return resultados_dir(experiment_id) / SUBDIR_PRODUCCION


def top20_dir(experiment_id: str) -> Path:
    return resultados_dir(experiment_id) / SUBDIR_TOP20


def agosto_dir(experiment_id: str) -> Path:
    return resultados_dir(experiment_id) / SUBDIR_AGOSTO


def layers_paths(experiment_id: str) -> list[Path]:
    assert_experiment_id(experiment_id)
    attempt = attempt_layer_id(experiment_id)
    return [DATA_DIR / name for name in _LAYERS_BY_ID[attempt]]


def experiment_storage_prefix(experiment_id: str) -> str:
    """Prefijo GCS relativo al bucket (sin ``resultados`` ni ``cache``)."""
    assert_experiment_id(experiment_id)
    if _uses_attempt_iteration_layout(experiment_id):
        return f"compe1/{experiment_id}"
    return f"compe1/{experiment_id}/00"

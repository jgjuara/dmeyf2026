"""Taxonomía: nocontinuas_base + continuas_nivel (escala cruda, sin pct/lag/delta)."""

from __future__ import annotations

import sys
from pathlib import Path

META_COLS = frozenset({"numero_de_cliente", "foto_mes", "clase_ternaria"})
_ALLOWED_BUCKETS = frozenset({"nocontinuas_base", "continuas_nivel"})

_FE_DIR = Path(__file__).resolve().parents[3] / "fe"
if str(_FE_DIR) not in sys.path:
    sys.path.insert(0, str(_FE_DIR))
from column_buckets import bucket_for_column as _bucket_base  # noqa: E402
from column_buckets import continuous_metric_names as continuas_nivel_names  # noqa: E402

_FORBIDDEN_BUCKETS = frozenset(
    {
        "rankings_pct",
        "rankings_lag1_pct",
        "rankings_lag2_pct",
        "rankings_delta1_pct",
        "rankings_delta2_pct",
        "nocontinuas_lag1",
        "nocontinuas_lag2",
        "continuas_lag1",
        "continuas_lag2",
        "continuas_delta1",
        "continuas_delta2",
    }
)


def bucket_for_column(name: str) -> str:
    base = _bucket_base(name)
    if base == "claves":
        return "claves"
    if base in _FORBIDDEN_BUCKETS:
        return "forbidden_transform"
    if base == "continuas_nivel":
        return "continuas_nivel"
    if base == "nocontinuas_base":
        return "nocontinuas_base"
    return "forbidden_transform"


def filter_feature_names(names: list[str]) -> list[str]:
    filtered = [name for name in names if bucket_for_column(name) in _ALLOWED_BUCKETS]
    if not filtered:
        raise ValueError("El filtro nivel dejó el conjunto de features vacío")
    forbidden = [n for n in names if bucket_for_column(n) == "forbidden_transform"]
    if forbidden:
        raise ValueError(f"Columnas transformadas no permitidas: {forbidden[:5]}...")
    return filtered


def feature_columns_from_schema(columns: list[str]) -> list[str]:
    return [c for c in columns if c not in META_COLS and bucket_for_column(c) != "claves"]

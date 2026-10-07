"""Taxonomía de columnas y filtro sin_lag_delta (nocontinuas_base + rankings_pct)."""

from __future__ import annotations

import sys
from pathlib import Path

_FE_DIR = Path(__file__).resolve().parents[3] / "fe"
if str(_FE_DIR) not in sys.path:
    sys.path.insert(0, str(_FE_DIR))
from column_buckets import bucket_for_column  # noqa: E402

META_COLS = frozenset({"numero_de_cliente", "foto_mes", "clase_ternaria"})
_ALLOWED_BUCKETS_SIN_LAG_DELTA = frozenset({"nocontinuas_base", "rankings_pct"})


def filter_feature_names(names: list[str]) -> list[str]:
    """Conserva solo nocontinuas_base y rankings_pct; mantiene orden relativo."""
    filtered = [name for name in names if bucket_for_column(name) in _ALLOWED_BUCKETS_SIN_LAG_DELTA]
    if not filtered:
        raise ValueError("El filtro sin_lag_delta dejó el conjunto de features vacío")
    return filtered


def feature_columns_from_schema(columns: list[str]) -> list[str]:
    """Predictores numéricos excluyendo meta y claves."""
    return [c for c in columns if c not in META_COLS and bucket_for_column(c) != "claves"]

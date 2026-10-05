"""Alcance de predictores para proximidad RF."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

_PIPELINES = Path(__file__).resolve().parent.parent
if str(_PIPELINES) not in sys.path:
    sys.path.insert(0, str(_PIPELINES))

from describe_comparativo._columns import bucket_for_column

FeatureScope = Literal["all", "sin_lag_delta"]

_ALLOWED_BUCKETS_SIN_LAG_DELTA = frozenset({"nocontinuas_base", "rankings_pct"})


def filter_feature_names(names: list[str], scope: FeatureScope) -> list[str]:
    """Reduce la lista de predictores según el alcance; conserva el orden relativo."""
    if scope == "all":
        return names
    filtered = [name for name in names if bucket_for_column(name) in _ALLOWED_BUCKETS_SIN_LAG_DELTA]
    if not filtered:
        raise ValueError(f"feature_scope={scope!r} dejó el conjunto de features vacío")
    return filtered

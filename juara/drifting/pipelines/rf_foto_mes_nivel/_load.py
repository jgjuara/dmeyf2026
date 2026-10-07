"""Carga parquet nivel → X (NaN nativos), y (foto_mes), nombres de features."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import polars.selectors as cs

from _features import filter_feature_names

EXCLUDED_FROM_X = frozenset({"numero_de_cliente", "foto_mes", "clase_ternaria"})
LABEL_COLUMN = "foto_mes"


def load_dataset(parquet_path: Path) -> tuple[pl.DataFrame, np.ndarray, np.ndarray, list[str]]:
    if not parquet_path.is_file():
        raise FileNotFoundError(f"No existe el parquet: {parquet_path}")

    frame = pl.read_parquet(parquet_path)
    for col in ("numero_de_cliente", LABEL_COLUMN):
        if col not in frame.columns:
            raise ValueError(f"Falta columna requerida: {col}")

    numeric_cols = frame.select(cs.numeric()).columns
    feature_names = [c for c in numeric_cols if c not in EXCLUDED_FROM_X]
    feature_names = filter_feature_names(feature_names)

    X = (
        frame.select(
            pl.col(name).cast(pl.Float32, strict=True).fill_null(float("nan"))
            for name in feature_names
        )
        .to_numpy()
        .astype(np.float32, copy=False)
    )
    y = frame[LABEL_COLUMN].to_numpy()
    return frame, X, y, feature_names

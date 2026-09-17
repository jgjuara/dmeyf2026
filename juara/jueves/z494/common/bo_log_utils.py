"""Utilidades compartidas para comparar BO_log.txt (mlrMBO)."""

from __future__ import annotations

import math
from pathlib import Path

import polars as pl

TUNABLE_CANDIDATES = (
    "num_iterations",
    "learning_rate",
    "feature_fraction",
    "num_leaves",
    "min_data_in_leaf",
    "min_sum_hessian_in_leaf",
)

MIN_SUM_HESSIAN_LO = 1e-5
MIN_SUM_HESSIAN_HI = 10.0

INFILL_TYPE = "infill_ei"


def default_label(path: Path) -> str:
    parts = path.resolve().parts
    if "z494" in parts:
        idx = parts.index("z494")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return path.stem


def unique_labels(labels: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for label in labels:
        n = seen.get(label, 0)
        seen[label] = n + 1
        out.append(label if n == 0 else f"{label}_{n + 1}")
    return out


def decode_min_sum_hessian(value: float) -> float:
    if MIN_SUM_HESSIAN_LO <= value <= MIN_SUM_HESSIAN_HI:
        return value
    return 10.0**value


def decode_hp_value(col: str, raw: object) -> float:
    value = float(raw)
    if col == "min_sum_hessian_in_leaf":
        return decode_min_sum_hessian(value)
    return value


def common_hp_columns(paths: list[Path]) -> list[str]:
    headers: list[set[str]] = []
    for path in paths:
        header = pl.read_csv(path, separator="\t", n_rows=0).columns
        headers.append(set(header))
    shared = set.intersection(*headers)
    return [c for c in TUNABLE_CANDIDATES if c in shared]


def read_bo_frame(path: Path, *, infill_only: bool) -> pl.DataFrame:
    frame = pl.read_csv(path, separator="\t")
    if infill_only:
        if "prop.type" not in frame.columns:
            raise ValueError(f"{path}: no tiene columna prop.type para filtrar infill.")
        frame = frame.filter(pl.col("prop.type") == INFILL_TYPE)
        if frame.is_empty():
            raise ValueError(f"{path}: sin filas {INFILL_TYPE}.")
    return frame


def row_id_column(frame: pl.DataFrame) -> str:
    if "iter" in frame.columns:
        return "iter"
    if "dob" in frame.columns:
        return "dob"
    raise ValueError("BO_log sin columna iter ni dob para identificar evaluaciones.")


def load_hp_cloud(
    path: Path, hp_cols: list[str], *, infill_only: bool
) -> tuple[list[str], list[tuple[float, ...]]]:
    frame = read_bo_frame(path, infill_only=infill_only)
    missing = [c for c in hp_cols if c not in frame.columns]
    if missing:
        raise ValueError(f"{path}: faltan columnas {missing}")

    id_col = row_id_column(frame)
    ids: list[str] = []
    points: list[tuple[float, ...]] = []
    for record in frame.select([id_col, *hp_cols]).iter_rows():
        row_id, *raws = record
        ids.append(str(row_id))
        points.append(
            tuple(decode_hp_value(col, raw) for col, raw in zip(hp_cols, raws, strict=True))
        )
    return ids, points


def min_max_bounds(
    clouds: list[list[tuple[float, ...]]], n_dim: int
) -> list[tuple[float, float]]:
    lows = [math.inf] * n_dim
    highs = [-math.inf] * n_dim
    for cloud in clouds:
        for point in cloud:
            for j, v in enumerate(point):
                lows[j] = min(lows[j], v)
                highs[j] = max(highs[j], v)
    bounds: list[tuple[float, float]] = []
    for lo, hi in zip(lows, highs, strict=True):
        if math.isclose(lo, hi):
            bounds.append((lo, lo + 1.0))
        else:
            bounds.append((lo, hi))
    return bounds


def normalize_cloud(
    cloud: list[tuple[float, ...]], bounds: list[tuple[float, float]]
) -> list[tuple[float, ...]]:
    return [
        tuple((v - lo) / (hi - lo) for v, (lo, hi) in zip(point, bounds, strict=True))
        for point in cloud
    ]


def euclidean(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def chamfer_distance(a: list[tuple[float, ...]], b: list[tuple[float, ...]]) -> float:
    if not a or not b:
        raise ValueError("nube vacia")

    def mean_min(from_pts: list[tuple[float, ...]], to_pts: list[tuple[float, ...]]) -> float:
        total = 0.0
        for p in from_pts:
            total += min(euclidean(p, q) for q in to_pts)
        return total / len(from_pts)

    return 0.5 * (mean_min(a, b) + mean_min(b, a))


def write_bounds_meta(meta_path: Path, hp_cols: list[str], bounds: list[tuple[float, float]]) -> None:
    lines = ["hp\tlo_fisico\thi_fisico"]
    for hp, (lo, hi) in zip(hp_cols, bounds, strict=True):
        lines.append(f"{hp}\t{lo}\t{hi}")
    meta_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

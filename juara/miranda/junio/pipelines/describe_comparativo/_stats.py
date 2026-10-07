"""Tests univariados y corrección FDR por lote de p-values."""

from __future__ import annotations

import numpy as np
import polars as pl
from scipy import stats


def is_binary_01(values: np.ndarray) -> bool:
    if values.size == 0:
        return False
    vmax = float(np.nanmax(values))
    vmin = float(np.nanmin(values))
    return vmax <= 1.0 and vmin >= 0.0


def test_binary_two_sample(baja: np.ndarray, continua: np.ndarray) -> tuple[float, str]:
    """Contraste de proporciones 2×2 (baja vs continua × 0 vs 1)."""
    baja = baja[~np.isnan(baja)]
    continua = continua[~np.isnan(continua)]
    a1 = int(np.sum(baja == 1))
    a0 = int(baja.size - a1)
    b1 = int(np.sum(continua == 1))
    b0 = int(continua.size - b1)
    table = np.array([[a1, a0], [b1, b0]])
    if table.min() < 5:
        _, p = stats.fisher_exact(table)
        return float(p), "fisher"
    chi2, p, _, _ = stats.chi2_contingency(table)
    if np.isnan(p):
        _, p = stats.fisher_exact(table)
        return float(p), "fisher"
    return float(p), "chi2"


def test_mann_whitney(baja: np.ndarray, continua: np.ndarray) -> float:
    baja = baja[~np.isnan(baja)]
    continua = continua[~np.isnan(continua)]
    if baja.size < 1 or continua.size < 1:
        return float("nan")
    res = stats.mannwhitneyu(baja, continua, alternative="two-sided")
    return float(res.pvalue)


def rank_biserial_from_u(u: float, n1: int, n2: int) -> float:
    if n1 < 1 or n2 < 1:
        return float("nan")
    return float(1.0 - (2.0 * u) / (n1 * n2))


def mann_whitney_u_and_r(baja: np.ndarray, continua: np.ndarray) -> tuple[float, float]:
    baja = baja[~np.isnan(baja)]
    continua = continua[~np.isnan(continua)]
    if baja.size < 1 or continua.size < 1:
        return float("nan"), float("nan")
    res = stats.mannwhitneyu(baja, continua, alternative="two-sided")
    r = rank_biserial_from_u(float(res.statistic), int(baja.size), int(continua.size))
    return float(res.pvalue), r


def fdr_benjamini_hochberg(p_values: list[float]) -> list[float]:
    n = len(p_values)
    if n == 0:
        return []
    arr = np.array(p_values, dtype=float)
    nan_mask = np.isnan(arr)
    q_out = np.full(n, np.nan)
    valid_idx = np.where(~nan_mask)[0]
    if valid_idx.size == 0:
        return q_out.tolist()
    p_valid = arr[valid_idx]
    order = np.argsort(p_valid)
    ranked = p_valid[order]
    m = len(ranked)
    q_sorted = np.empty(m)
    prev = 1.0
    for i in range(m - 1, -1, -1):
        rank = i + 1
        val = ranked[i] * m / rank
        prev = min(prev, val)
        q_sorted[i] = prev
    q_valid = np.empty(m)
    q_valid[order] = np.minimum(q_sorted, 1.0)
    q_out[valid_idx] = q_valid
    return q_out.tolist()


def attach_fdr_batch(
    frame: pl.DataFrame,
    p_col: str = "p_value",
    q_col: str = "q_value",
) -> pl.DataFrame:
    """Benjamini–Hochberg sobre todas las filas del lote (p. ej. una etapa pooled)."""
    ps = frame[p_col].to_list()
    qs = fdr_benjamini_hochberg([float(p) if p is not None else float("nan") for p in ps])
    sort_cols = [c for c in ("grupo_columnas", "variable", "foto_mes") if c in frame.columns]
    return frame.with_columns(pl.Series(q_col, qs)).sort(sort_cols)


def attach_fdr_by_foto_mes(frame: pl.DataFrame, p_col: str = "p_value", q_col: str = "q_value") -> pl.DataFrame:
    rows: list[pl.DataFrame] = []
    for fm in sorted(frame["foto_mes"].unique().to_list()):
        sub = frame.filter(pl.col("foto_mes") == fm)
        ps = sub[p_col].to_list()
        qs = fdr_benjamini_hochberg([float(p) if p is not None else float("nan") for p in ps])
        rows.append(sub.with_columns(pl.Series(q_col, qs)))
    return pl.concat(rows).sort("grupo_columnas", "variable", "foto_mes")

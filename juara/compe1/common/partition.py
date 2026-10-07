"""Partición estratificada y undersampling (port de particionar + compe1_aplicar_undersampling_train)."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import polars as pl

from common.layers import cache_dir

PARTICION_AGRUPA = ("clase_ternaria", "foto_mes")
BAJA_KEEP = frozenset({"BAJA+1", "BAJA+2"})


def _bloque_folds(division: tuple[int, ...], start: int = 1) -> np.ndarray:
    parts: list[int] = []
    for i, weight in enumerate(division):
        parts.extend([start + i] * int(weight))
    return np.asarray(parts, dtype=np.int32)


def _sample_fold_block(rng: np.random.Generator, bloque: np.ndarray, n: int) -> np.ndarray:
    """Equivalente a sample(rep(bloque, ceiling(n/len)))))[1:n] con replace=FALSE en R."""
    expanded = np.tile(bloque, int(np.ceil(n / len(bloque))))
    perm = rng.permutation(len(expanded))[:n]
    return expanded[perm]


def _group_indices_in_interaction_order(
    df: pl.DataFrame, agrupa: tuple[str, ...]
) -> list[np.ndarray]:
    """Orden de grupos alineado con interaction(..., drop=TRUE) en R."""
    clase_levels = df[agrupa[0]].unique(maintain_order=True).to_list()
    mes_levels = df[agrupa[1]].unique(maintain_order=True).to_list()
    indices: list[np.ndarray] = []
    for c in clase_levels:
        for m in mes_levels:
            mask = (df[agrupa[0]] == c) & (df[agrupa[1]] == m)
            idx = np.flatnonzero(mask.to_numpy())
            if idx.size > 0:
                indices.append(idx)
    return indices


def assign_split_training(
    df: pl.DataFrame,
    seed: int,
    division: tuple[int, ...],
    fold_train: int,
    undersampling: float,
    apply_undersampling: bool,
    agrupa: tuple[str, ...] = PARTICION_AGRUPA,
) -> pl.DataFrame:
    """
    Añade columnas fold, azar, training a df (debe incluir agrupa).
    Usa un Generator numpy por fase (partición; luego undersampling con nueva semilla).
    """
    n = df.height
    fold = np.zeros(n, dtype=np.int32)
    bloque = _bloque_folds(division)

    rng_part = np.random.default_rng(seed)
    for idx in _group_indices_in_interaction_order(df, agrupa):
        fold[idx] = _sample_fold_block(rng_part, bloque, len(idx))

    if apply_undersampling:
        rng_u = np.random.default_rng(seed)
        azar = rng_u.random(n)
        training = np.zeros(n, dtype=np.int32)
        clase = df["clase_ternaria"].to_list()
        is_train_fold = fold == fold_train
        for i in range(n):
            if not is_train_fold[i]:
                continue
            if azar[i] <= undersampling or clase[i] in BAJA_KEEP:
                training[i] = 1
        return df.with_columns(
            pl.Series("fold", fold),
            pl.Series("azar", azar),
            pl.Series("training", training),
        )

    return df.with_columns(
        pl.Series("fold", fold),
        pl.Series("azar", [None] * n, dtype=pl.Float64),
        pl.Series("training", [None] * n, dtype=pl.Int32),
    )


def split_cache_path(
    experiment_id: str,
    semilla_primigenia: int,
    apply_undersampling: bool,
    undersampling: float | None,
) -> Path:
    u_tag = "nou" if not apply_undersampling else f"u{undersampling}"
    return cache_dir(experiment_id) / f"split_{semilla_primigenia}_{u_tag}.tsv"


def load_or_export_split(
    experiment_id: str,
    semilla_primigenia: int,
    division: tuple[int, ...],
    fold_train: int,
    foto_mes: tuple[int, ...],
    undersampling: float | None = None,
    apply_undersampling: bool = False,
    refresh: bool = False,
) -> pl.DataFrame:
    from common.data import read_joined

    path = split_cache_path(
        experiment_id, semilla_primigenia, apply_undersampling, undersampling
    )
    if not path.exists() or refresh:
        path.parent.mkdir(parents=True, exist_ok=True)
        df = read_joined(experiment_id, foto_mes=foto_mes).select(
            "numero_de_cliente", "foto_mes", "clase_ternaria"
        )
        u = 0.1 if undersampling is None else undersampling
        out = assign_split_training(
            df,
            semilla_primigenia,
            division,
            fold_train,
            u,
            apply_undersampling,
        )
        out.select("numero_de_cliente", "foto_mes", "fold", "azar", "training").write_csv(
            path, separator="\t"
        )
    return pl.read_csv(
        path,
        separator="\t",
        null_values=["NA"],
        schema_overrides={
            "numero_de_cliente": pl.Int64,
            "foto_mes": pl.Int32,
            "fold": pl.Int32,
            "azar": pl.Float64,
            "training": pl.Int64,
        },
    )


def _primes_between(lo: int, hi: int) -> list[int]:
    if hi < 2:
        return []
    is_prime = [True] * (hi + 1)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(hi**0.5) + 1):
        if is_prime[i]:
            for j in range(i * i, hi + 1, i):
                is_prime[j] = False
    return [i for i in range(lo, hi + 1) if is_prime[i]]


def semillas_primos(n: int, semilla_primigenia: int) -> list[int]:
    primos = _primes_between(10_000, 1_000_000)
    rng = random.Random(semilla_primigenia)
    return rng.sample(primos, n)

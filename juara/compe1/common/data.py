"""Lectura parquet, features y métricas de ganancia (port de compe1_data.R)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

from common.layers import layers_paths
from common.partition import load_or_export_split

JOIN_KEYS = ("numero_de_cliente", "foto_mes")
PARTICION_AGRUPA = ("clase_ternaria", "foto_mes")
FOTO_MES_MAR_JUN = (202103, 202104, 202105, 202106)
GAN_BAJA2 = 1_072_500
GAN_OTRO = -27_500

AUXILIARES = {
    *JOIN_KEYS,
    "clase_ternaria",
    "clase01",
    "fold",
    "azar",
    "training",
    "prob",
    "Predicted",
    "gan",
    "ganancia_acumulada",
    "pos",
}


def read_joined(
    experiment_id: str,
    foto_mes: tuple[int, ...] | None = None,
) -> pl.DataFrame:
    paths = layers_paths(experiment_id)
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "parquet inexistente: " + ", ".join(str(p) for p in missing)
        )

    df = pl.read_parquet(paths[0])
    for path in paths[1:]:
        layer = pl.read_parquet(path)
        if not all(k in layer.columns for k in JOIN_KEYS):
            raise ValueError(f"capa sin claves de join: {path}")
        extra = [c for c in layer.columns if c not in JOIN_KEYS and c != "clase_ternaria"]
        layer = layer.select([*JOIN_KEYS, *extra])
        df = df.join(layer, on=list(JOIN_KEYS), how="inner")

    if foto_mes is not None:
        df = df.filter(pl.col("foto_mes").is_in(list(foto_mes)))
    return df


def feature_columns(df: pl.DataFrame, extra_drop: tuple[str, ...] = ()) -> list[str]:
    drop = AUXILIARES | set(extra_drop)
    return [c for c in df.columns if c not in drop]


def clase01_expr() -> pl.Expr:
    return (
        pl.when(pl.col("clase_ternaria").is_in(["BAJA+1", "BAJA+2"]))
        .then(1)
        .otherwise(0)
        .alias("clase01")
    )


def decode_min_sum_hessian(param: dict, limits: tuple[float, float] = (0.001, 0.01)) -> dict:
    out = dict(param)
    v = out.get("min_sum_hessian_in_leaf")
    if v is None:
        return out
    v = float(v)
    lo, hi = limits
    if lo <= v <= hi:
        return out
    if v >= 0:
        return out
    out["min_sum_hessian_in_leaf"] = 10**v
    return out


def ganancia_por_fila(clase_ternaria: pl.Series) -> pl.Series:
    return pl.when(clase_ternaria == "BAJA+2").then(GAN_BAJA2).otherwise(GAN_OTRO)


def ganancia_envio(
    df: pl.DataFrame,
    envios: int,
    prob_col: str = "prob",
) -> int:
    ord_df = df.sort(prob_col, descending=True)
    n = min(int(envios), ord_df.height)
    if n <= 0:
        return 0
    top = ord_df.head(n)
    return int(
        top.select(
            pl.when(pl.col("clase_ternaria") == "BAJA+2")
            .then(GAN_BAJA2)
            .otherwise(GAN_OTRO)
            .sum()
        ).item()
    )


def escalar_ganancia_mes(ganancia_obs: float, n_test_mes: int, n_total_mes: int) -> float:
    if n_test_mes <= 0:
        return float("nan")
    return ganancia_obs * (n_total_mes / n_test_mes)


def preparar_holdout_split(
    experiment_id: str,
    semilla_primigenia: int,
    division: tuple[int, ...] = (70, 30),
    fold_train: int = 1,
    foto_mes: tuple[int, ...] = FOTO_MES_MAR_JUN,
    undersampling: float | None = None,
    apply_undersampling: bool = False,
) -> dict:
    df = read_joined(experiment_id, foto_mes=foto_mes)
    split_cols = load_or_export_split(
        experiment_id,
        semilla_primigenia,
        division,
        fold_train,
        foto_mes,
        undersampling=undersampling,
        apply_undersampling=apply_undersampling,
    )
    df = df.join(split_cols, on=list(JOIN_KEYS), how="left")
    if df["fold"].null_count() > 0:
        raise ValueError("split R no alinea con dataset join")
    df = df.with_columns(clase01_expr())

    fold_test = fold_train + len(division) - 1
    campos = feature_columns(df)
    return {
        "data": df,
        "fold_train": fold_train,
        "fold_test": fold_test,
        "campos_buenos": campos,
    }


def feature_matrix(df: pl.DataFrame, campos_buenos: list[str]) -> np.ndarray:
    return df.select(campos_buenos).to_numpy().astype(np.float32, copy=False)

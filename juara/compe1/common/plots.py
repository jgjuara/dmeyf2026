"""Gráficos matplotlib para curvas de ganancia."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import polars as pl

from common.data import GAN_BAJA2, GAN_OTRO


def write_gain_curve_pdf(
    df: pl.DataFrame,
    out_path: Path,
    prob_col: str = "prob",
    clase_col: str = "clase_ternaria",
    amostrar: int = 30_000,
) -> None:
    tb = df.sort(prob_col, descending=True).with_columns(
        pl.when(pl.col(clase_col) == "BAJA+2")
        .then(GAN_BAJA2)
        .otherwise(GAN_OTRO)
        .alias("gan")
    )
    tb = tb.with_columns(pl.col("gan").cum_sum().alias("ganancia_acumulada"))
    tb = tb.with_columns(pl.int_range(0, pl.len()).alias("pos"))
    plot_df = tb.filter(pl.col("pos") < amostrar)

    fig, ax = plt.subplots(figsize=(16, 9))
    ax.plot(plot_df["pos"].to_numpy(), plot_df["ganancia_acumulada"].to_numpy())
    ax.set_xlabel("pos")
    ax.set_ylabel("ganancia_acumulada")
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)

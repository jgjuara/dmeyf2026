#!/usr/bin/env python3
"""Análisis inferencial top-20 BO × semillas (sin entrenamiento)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import yaml
from scipy.stats import binomtest, friedmanchisquare, wilcoxon

import _bootstrap  # noqa: F401

from common.cortes import parse_cortes_media, parse_cortes_primo
from common.layers import resultados_dir

EXPERIMENT_ID = "02_rank_nocount_py"
EXPERIMENTO = 2102
N_RANKS = 20
N_SEMILLAS = 10
DO_FRIEDMAN = True

WILCOX_H0 = "H0: mediana(ganancia_A - ganancia_B) = 0"
WILCOX_H1 = "H1: mediana(ganancia_A - ganancia_B) != 0 (bilateral / dos colas)"


def wilcox_paired(y_a: np.ndarray, y_b: np.ndarray) -> dict:
    if len(y_a) != len(y_b):
        raise ValueError("Vectores de distinta longitud para Wilcoxon emparejado.")
    stat, p = wilcoxon(y_a, y_b, alternative="two-sided", method="approx")
    return {
        "statistic": float(stat),
        "p.value": float(p),
        "mean_a": float(np.mean(y_a)),
        "mean_b": float(np.mean(y_b)),
    }


def holm_adjust(pvals: list[float]) -> list[float]:
    n = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(n)
    for i, idx in enumerate(order):
        adj[idx] = min(1.0, pvals[idx] * (n - i))
    return adj.tolist()


def merge_paired(tb: pl.DataFrame, rank_a: int, rank_b: int, envio: int) -> pl.DataFrame:
    va = tb.filter(
        (pl.col("rank") == rank_a) & (pl.col("envios") == envio) & (pl.col("tipo") == "holdout")
    ).select("primo", pl.col("ganancia").alias("ganancia_a"))
    vb = tb.filter(
        (pl.col("rank") == rank_b) & (pl.col("envios") == envio) & (pl.col("tipo") == "holdout")
    ).select("primo", pl.col("ganancia").alias("ganancia_b"))
    return va.join(vb, on="primo", how="inner")


def main() -> None:
    res_dir = resultados_dir(EXPERIMENT_ID)
    estudio_dir = res_dir / "estudio" / "top20_bo_semillas"
    rank_base = res_dir / "exp2102_top20"
    estudio_dir.mkdir(parents=True, exist_ok=True)

    meta_path = estudio_dir / "top20_hiperparametros.tsv"
    if not meta_path.exists():
        raise FileNotFoundError(f"No existe {meta_path}")

    tb_meta = pl.read_csv(meta_path, separator="\t")
    semillas = [
        int(x)
        for x in (estudio_dir / "semillas_train.txt").read_text().splitlines()
        if x.strip()
    ]

    rank_dirs = [f"rank_{k:02d}" for k in range(1, N_RANKS + 1)]
    pieces = []
    for k, rd in enumerate(rank_dirs, start=1):
        pdir = rank_base / rd
        archivos = sorted(pdir.glob("cortes_ganancia_[0-9]*.txt"))
        if len(archivos) < N_SEMILLAS:
            raise FileNotFoundError(f"En {pdir} hay {len(archivos)} cortes; se esperan {N_SEMILLAS}")
        tb_k = pl.concat([parse_cortes_primo(p) for p in archivos]).with_columns(
            pl.lit(k).alias("rank")
        )
        pieces.append(tb_k)

    tb_long = pl.concat(pieces, how="vertical")
    if set(tb_long["primo"].unique().to_list()) != set(semillas):
        raise ValueError("Primos en cortes no coinciden con semillas_train.txt")

    tb_long.write_csv(estudio_dir / "curvas_por_semilla.tsv", separator="\t")

    tb_media_sd = (
        tb_long.group_by("rank", "envios", "tipo")
        .agg(
            pl.col("ganancia").mean().alias("mean"),
            pl.col("ganancia").std().alias("sd"),
            pl.len().alias("n"),
        )
    )
    tb_media_sd.write_csv(estudio_dir / "curvas_media_sd.tsv", separator="\t")

    tb_holdout = tb_media_sd.filter(pl.col("tipo") == "holdout")
    tb_rank_score = (
        tb_holdout.sort("mean", descending=True)
        .group_by("rank")
        .first()
        .rename({"mean": "max_mean_holdout"})
        .join(
            tb_meta.select("rank", pl.col("y").alias("y_bo"), pl.col("iter").alias("iter_bo")),
            on="rank",
        )
        .sort("max_mean_holdout", descending=True)
    )
    tb_rank_score.write_csv(estudio_dir / "ranking_por_max_holdout.tsv", separator="\t")

    rank_ganador = int(tb_rank_score["rank"][0])
    rank_subcampeon = int(tb_rank_score["rank"][1])
    envios_argmax = int(
        tb_rank_score.filter(pl.col("rank") == rank_ganador)["envios_argmax"][0]
    )

    ganador_yaml = {
        "rank_ganador": rank_ganador,
        "rank_subcampeon": rank_subcampeon,
        "envios_argmax_ganador": envios_argmax,
        "max_mean_holdout_ganador": float(tb_rank_score["max_mean_holdout"][0]),
        "max_mean_holdout_subcampeon": float(tb_rank_score["max_mean_holdout"][1]),
    }
    with (estudio_dir / "ganador.yml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(ganador_yaml, f, sort_keys=False)

    print(
        f"Ganador rank={rank_ganador} envios_argmax={envios_argmax} | "
        f"Subcampeon rank={rank_subcampeon}"
    )

    envios_levels = sorted(tb_long["envios"].unique().to_list())
    ranks_resto = [r for r in range(1, N_RANKS + 1) if r != rank_ganador]

    wx12_rows = []
    for e in envios_levels:
        m = merge_paired(tb_long, rank_ganador, rank_subcampeon, e)
        w = wilcox_paired(m["ganancia_a"].to_numpy(), m["ganancia_b"].to_numpy())
        wx12_rows.append(
            {
                "envios": e,
                "rank_mejor": rank_ganador,
                "rank_segundo": rank_subcampeon,
                **w,
                "mean_ganador": w["mean_a"],
                "mean_subcampeon": w["mean_b"],
            }
        )
    pl.DataFrame(wx12_rows).write_csv(
        estudio_dir / "wilcoxon_mejor_vs_segundo_holdout.tsv", separator="\t"
    )

    wx_resto_rows = []
    for e in envios_levels:
        filas = []
        for j in ranks_resto:
            m = merge_paired(tb_long, rank_ganador, j, e)
            w = wilcox_paired(m["ganancia_a"].to_numpy(), m["ganancia_b"].to_numpy())
            filas.append(
                {
                    "envios": e,
                    "rank_ganador": rank_ganador,
                    "rank_resto": j,
                    "statistic": w["statistic"],
                    "p.value": w["p.value"],
                    "mean_ganador": w["mean_a"],
                    "mean_resto": w["mean_b"],
                }
            )
        pvals = [f["p.value"] for f in filas]
        adj = holm_adjust(pvals)
        for f, p_adj in zip(filas, adj):
            f["p_adj_holm"] = p_adj
            wx_resto_rows.append(f)

    tb_wx_top_resto = pl.DataFrame(wx_resto_rows)
    tb_wx_top_resto.write_csv(
        estudio_dir / "wilcoxon_top_vs_resto_por_rank.tsv", separator="\t"
    )

    def aggregate_resto(envio: int, agg: str) -> tuple[np.ndarray, np.ndarray]:
        wide = tb_long.filter(
            (pl.col("envios") == envio) & (pl.col("tipo") == "holdout")
        ).pivot(on="rank", index="primo", values="ganancia")
        cols_resto = [str(j) for j in ranks_resto]
        mat = wide.select(cols_resto).to_numpy()
        y_top = wide[str(rank_ganador)].to_numpy()
        if agg == "median":
            y_rest = np.median(mat, axis=1)
        else:
            y_rest = np.max(mat, axis=1)
        return y_top, y_rest

    med_rows, max_rows = [], []
    for e in envios_levels:
        yt, yr = aggregate_resto(e, "median")
        w = wilcox_paired(yt, yr)
        med_rows.append(
            {
                "envios": e,
                "comparador": "mediana_resto",
                **w,
                "mean_top": w["mean_a"],
                "mean_comparador": w["mean_b"],
            }
        )
        yt, yr = aggregate_resto(e, "max")
        w = wilcox_paired(yt, yr)
        max_rows.append(
            {
                "envios": e,
                "comparador": "max_resto",
                **w,
                "mean_top": w["mean_a"],
                "mean_comparador": w["mean_b"],
            }
        )
    pl.concat([pl.DataFrame(med_rows), pl.DataFrame(max_rows)]).write_csv(
        estudio_dir / "wilcoxon_top_vs_resto_mediana_holdout.tsv", separator="\t"
    )

    win_rows = []
    for e in envios_levels:
        filas = []
        for j in ranks_resto:
            m = merge_paired(tb_long, rank_ganador, j, e)
            wins = int((m["ganancia_a"] > m["ganancia_b"]).sum())
            bt = binomtest(wins, N_SEMILLAS, 0.5, alternative="two-sided")
            filas.append(
                {
                    "envios": e,
                    "rank_resto": j,
                    "wins": wins,
                    "n": N_SEMILLAS,
                    "p_sign_exact": float(bt.pvalue),
                }
            )
        pvals = [f["p_sign_exact"] for f in filas]
        adj = holm_adjust(pvals)
        for f, p_adj in zip(filas, adj):
            f["p_adj_holm"] = p_adj
            win_rows.append(f)
    tb_winrate = pl.DataFrame(win_rows)
    tb_winrate.write_csv(estudio_dir / "winrate_top_vs_rank.tsv", separator="\t")

    tb_friedman = None
    if DO_FRIEDMAN:
        fr_rows = []
        for e in envios_levels:
            wide = tb_long.filter(
                (pl.col("envios") == e) & (pl.col("tipo") == "holdout")
            ).pivot(on="rank", index="primo", values="ganancia")
            cols = [str(k) for k in range(1, N_RANKS + 1)]
            mat = [wide[c].to_numpy() for c in cols]
            stat, p = friedmanchisquare(*mat)
            fr_rows.append(
                {
                    "envios": e,
                    "statistic": float(stat),
                    "p.value": float(p),
                    "df": len(cols) - 1,
                }
            )
        tb_friedman = pl.DataFrame(fr_rows)
        tb_friedman.write_csv(estudio_dir / "friedman_por_envio.tsv", separator="\t")

    # PDFs
    fig, ax = plt.subplots(figsize=(16, 9))
    for r in tb_media_sd["rank"].unique().to_list():
        sub = tb_media_sd.filter((pl.col("rank") == r) & (pl.col("tipo") == "holdout"))
        ax.plot(sub["envios"].to_numpy(), sub["mean"].to_numpy(), label=str(r), linewidth=0.7)
    ax.set_title("Top-20 BO: ganancia media por rank y semillas (holdout 30%)")
    ax.set_xlabel("Envios")
    ax.set_ylabel("Ganancia")
    ax.legend(title="Rank", fontsize=8, ncol=4)
    fig.savefig(estudio_dir / "curvas_top20_holdout_media_sd.pdf", bbox_inches="tight")
    plt.close(fig)

    tb_cmp = tb_media_sd.filter(pl.col("rank").is_in([rank_ganador, rank_subcampeon]))
    fig, ax = plt.subplots(figsize=(16, 9))
    for r in (rank_ganador, rank_subcampeon):
        sub = tb_cmp.filter((pl.col("rank") == r) & (pl.col("tipo") == "holdout"))
        ax.plot(sub["envios"].to_numpy(), sub["mean"].to_numpy(), label=f"rank {r}", linewidth=1)
    ax.set_title("Ganador vs subcampeon (ganancia holdout media)")
    fig.savefig(estudio_dir / "curvas_mejor_vs_segundo_holdout.pdf", bbox_inches="tight")
    plt.close(fig)

    tb_wx12 = pl.read_csv(
        estudio_dir / "wilcoxon_mejor_vs_segundo_holdout.tsv", separator="\t"
    )
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.plot(tb_wx12["envios"], tb_wx12["p.value"], linewidth=1)
    ax.axhline(0.05, linestyle="--", color="gray")
    ax.set_ylim(0, 1)
    ax.set_title(f"Wilcoxon ganador vs subcampeon | {WILCOX_H0} | {WILCOX_H1}")
    fig.savefig(estudio_dir / "wilcoxon_pvalue_vs_envios.pdf", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(16, 9))
    heat = tb_wx_top_resto
    ranks_y = sorted(heat["rank_resto"].unique().to_list())
    env_x = envios_levels
    grid = np.zeros((len(ranks_y), len(env_x)))
    for i, ry in enumerate(ranks_y):
        for j, ex in enumerate(env_x):
            v = heat.filter((pl.col("rank_resto") == ry) & (pl.col("envios") == ex))[
                "p_adj_holm"
            ]
            grid[i, j] = float(v[0]) if len(v) else np.nan
    im = ax.imshow(grid, aspect="auto", vmin=0, vmax=1, cmap="RdYlGn_r")
    ax.set_xticks(range(len(env_x)))
    ax.set_xticklabels(env_x, rotation=90, fontsize=8)
    ax.set_yticks(range(len(ranks_y)))
    ax.set_yticklabels(ranks_y)
    fig.colorbar(im, ax=ax, label="p_adj Holm")
    fig.savefig(estudio_dir / "heatmap_padj_top_vs_resto.pdf", bbox_inches="tight")
    plt.close(fig)

    tb_winrate = tb_winrate.with_columns((pl.col("wins") / pl.col("n")).alias("winrate"))
    fig, ax = plt.subplots(figsize=(16, 9))
    ranks_y = sorted(tb_winrate["rank_resto"].unique().to_list())
    grid = np.zeros((len(ranks_y), len(env_x)))
    for i, ry in enumerate(ranks_y):
        for j, ex in enumerate(env_x):
            v = tb_winrate.filter(
                (pl.col("rank_resto") == ry) & (pl.col("envios") == ex)
            )["winrate"]
            grid[i, j] = float(v[0]) if len(v) else np.nan
    im = ax.imshow(grid, aspect="auto", vmin=0, vmax=1, cmap="coolwarm")
    fig.colorbar(im, ax=ax, label="Winrate")
    fig.savefig(estudio_dir / "winrate_heatmap.pdf", bbox_inches="tight")
    plt.close(fig)

    tb_med = pl.read_csv(
        estudio_dir / "wilcoxon_top_vs_resto_mediana_holdout.tsv", separator="\t"
    ).filter(pl.col("comparador") == "mediana_resto")
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.plot(tb_med["envios"], tb_med["p.value"], color="#2166ac")
    ax.axhline(0.05, linestyle="--", color="gray")
    ax.set_ylim(0, 1)
    fig.savefig(estudio_dir / "wilcoxon_top_vs_mediana_resto.pdf", bbox_inches="tight")
    plt.close(fig)

    curvas_oficial = []
    for k in range(1, N_RANKS + 1):
        path = rank_base / rank_dirs[k - 1] / "cortes_ganancia_media.txt"
        if path.exists():
            tb = parse_cortes_media(path).with_columns(pl.lit(k).alias("rank"))
            curvas_oficial.append(tb)
    if curvas_oficial:
        tb_of = pl.concat(curvas_oficial)
        tb_of.write_csv(estudio_dir / "curvas_prob_media_por_rank.tsv", separator="\t")
        fig, ax = plt.subplots(figsize=(16, 9))
        for r in tb_of["rank"].unique().to_list():
            sub = tb_of.filter(pl.col("rank") == r)
            ax.plot(sub["envios"], sub["ganancia"], label=str(r), linewidth=0.7)
        ax.set_title("Curvas oficiales (prob promediada sobre 10 semillas) por rank")
        fig.savefig(estudio_dir / "curvas_prob_media_oficial.pdf", bbox_inches="tight")
        plt.close(fig)

    tb_argmax = tb_wx_top_resto.filter(pl.col("envios") == envios_argmax)
    n_dominados = int((tb_argmax["p_adj_holm"] < 0.05).sum())
    wins_argmax = tb_winrate.filter(
        (pl.col("envios") == envios_argmax) & (pl.col("wins") == N_SEMILLAS)
    )["rank_resto"].to_list()

    resumen = {
        "interpretacion": (
            "Evidencia condicional al shortlist top-20 BO; "
            "ganador por max mean(ganancia holdout) sobre cortes por semilla, no por AUC BO."
        ),
        "rank_ganador": rank_ganador,
        "rank_subcampeon": rank_subcampeon,
        "envios_reporte_principal": envios_argmax,
        "semillas_train": semillas,
        "friedman_ejecutado": DO_FRIEDMAN,
        "argmax_resumen": {
            "n_resto_p_adj_holm_lt_0_05": n_dominados,
            "ranks_winrate_10_de_10": wins_argmax,
        },
    }
    if tb_friedman is not None:
        fr = tb_friedman.filter(pl.col("envios") == envios_argmax).to_dicts()
        if fr:
            resumen["friedman_en_argmax"] = fr[0]

    with (estudio_dir / "PARAM_resumen.yml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(resumen, f, sort_keys=False, allow_unicode=True)

    print(f"\nAnálisis escrito en {estudio_dir}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Compara distribucion y maximos de y entre dos BO_log."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import polars as pl
from scipy.stats import mannwhitneyu

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bo_log_utils import (
    TUNABLE_CANDIDATES,
    common_hp_columns,
    decode_hp_value,
    default_label,
)

LABEL_02 = "02_cv5"
LABEL_03 = "03_cv3"


def parse_args(argv: list[str]) -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    z494 = here.parent
    parser = argparse.ArgumentParser(description="Comparar objetivo y entre dos corridas BO.")
    parser.add_argument("--bo-02", type=Path, default=z494 / "02/resultados/HT4940/BO_log.txt")
    parser.add_argument("--bo-03", type=Path, default=z494 / "03/resultados/HT4940/BO_log.txt")
    parser.add_argument("--out-dir", type=Path, default=here / "estudio")
    parser.add_argument("--top-k", nargs="+", type=int, default=[10, 30])
    parser.add_argument("--n-quantile-bins", type=int, default=10)
    return parser.parse_args(argv)


def summary_row(label: str, frame: pl.DataFrame, hp_cols: list[str]) -> dict[str, object]:
    y = frame["y"]
    best_idx = int(frame["y"].arg_max())
    best = frame.row(best_idx, named=True)
    exec_col = "exec.time" if "exec.time" in frame.columns else None
    exec_sum = float(frame[exec_col].sum()) if exec_col else None
    exec_mean = float(frame[exec_col].mean()) if exec_col else None
    row: dict[str, object] = {
        "corrida": label,
        "n": frame.height,
        "y_max": float(y.max()),
        "y_p50": float(y.quantile(0.5)),
        "y_p90": float(y.quantile(0.9)),
        "y_std": float(y.std()),
        "best_iter": best.get("iter"),
        "best_y": float(best["y"]),
        "exec_time_sum": exec_sum,
        "exec_time_mean": exec_mean,
    }
    for col in hp_cols:
        row[f"best_{col}"] = decode_hp_value(col, best[col])
    return row


def subset_summary(label: str, prop_type: str, frame: pl.DataFrame) -> dict[str, object]:
    sub = frame.filter(pl.col("prop.type") == prop_type)
    if sub.is_empty():
        return {"corrida": label, "prop_type": prop_type, "n": 0}
    y = sub["y"]
    return {
        "corrida": label,
        "prop_type": prop_type,
        "n": sub.height,
        "y_max": float(y.max()),
        "y_p50": float(y.quantile(0.5)),
        "y_mean": float(y.mean()),
    }


def quantile_edges(union: pl.DataFrame, hp_cols: list[str], n_bins: int) -> dict[str, list[float]]:
    edges: dict[str, list[float]] = {}
    for col in hp_cols:
        vals = [decode_hp_value(col, v) for v in union[col].to_list()]
        s = pl.Series(vals)
        qs = [float(s.quantile(i / n_bins)) for i in range(n_bins + 1)]
        edges[col] = sorted(set(qs))
    return edges


def discretize_hp_bins(
    frame: pl.DataFrame, hp_cols: list[str], edges: dict[str, list[float]]
) -> list[frozenset[tuple[str, int]]]:
    """Un conjunto de bins (hp, bin_id) por fila."""

    def bin_id(col: str, val: float) -> int:
        v = decode_hp_value(col, val)
        e = edges[col]
        for i in range(len(e) - 1):
            if v <= e[i + 1] or i == len(e) - 2:
                return i
        return len(e) - 2

    out: list[frozenset[tuple[str, int]]] = []
    for record in frame.select(hp_cols).iter_rows():
        cells = frozenset((col, bin_id(col, raw)) for col, raw in zip(hp_cols, record, strict=True))
        out.append(cells)
    return out


def plot_y_distribution(
    y02: list[float], y03: list[float], out_path: Path, label02: str, label03: str
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].hist(y02, bins=40, alpha=0.55, label=label02, density=True, color="#1f77b4")
    axes[0].hist(y03, bins=40, alpha=0.55, label=label03, density=True, color="#ff7f0e")
    axes[0].set_xlabel("y (AUC CV)")
    axes[0].set_ylabel("densidad")
    axes[0].legend()
    axes[0].set_title("Histograma superpuesto")

    def ecdf(vals: list[float]) -> tuple[list[float], list[float]]:
        s = sorted(vals)
        n = len(s)
        xs = s
        ys = [(i + 1) / n for i in range(n)]
        return xs, ys

    x2, c2 = ecdf(y02)
    x3, c3 = ecdf(y03)
    axes[1].plot(x2, c2, label=label02)
    axes[1].plot(x3, c3, label=label03)
    axes[1].set_xlabel("y (AUC CV)")
    axes[1].set_ylabel("F empirica")
    axes[1].legend()
    axes[1].set_title("ECDF")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def write_tsv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    cols = list(rows[0].keys())
    lines = ["\t".join(cols)]
    for row in rows:
        lines.append("\t".join("" if row[c] is None else str(row[c]) for c in cols))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    path02 = args.bo_02.resolve()
    path03 = args.bo_03.resolve()
    for p in (path02, path03):
        if not p.is_file():
            print(f"No existe: {p}", file=sys.stderr)
            return 1

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    f02 = pl.read_csv(path02, separator="\t")
    f03 = pl.read_csv(path03, separator="\t")
    hp_cols = common_hp_columns([path02, path03])

    summaries = [
        summary_row(LABEL_02, f02, hp_cols),
        summary_row(LABEL_03, f03, hp_cols),
    ]
    write_tsv(out_dir / "objetivo_resumen.tsv", summaries)

    prop_rows: list[dict[str, object]] = []
    for label, frame in ((LABEL_02, f02), (LABEL_03, f03)):
        for pt in ("initdesign", "infill_ei"):
            prop_rows.append(subset_summary(label, pt, frame))
    write_tsv(out_dir / "objetivo_por_prop_type.tsv", prop_rows)

    y02 = f02["y"].to_list()
    y03 = f03["y"].to_list()
    plot_y_distribution(y02, y03, out_dir / "objetivo_y_distribucion.png", LABEL_02, LABEL_03)

    mw_rows: list[dict[str, object]] = []
    for scope, a, b in (
        ("todas", y02, y03),
        (
            "infill_ei",
            f02.filter(pl.col("prop.type") == "infill_ei")["y"].to_list(),
            f03.filter(pl.col("prop.type") == "infill_ei")["y"].to_list(),
        ),
    ):
        stat, pval = mannwhitneyu(a, b, alternative="two-sided")
        mw_rows.append({"scope": scope, "n_02": len(a), "n_03": len(b), "statistic": stat, "p_value": pval})
    write_tsv(out_dir / "objetivo_mann_whitney.tsv", mw_rows)

    union_hp = pl.concat([f02.select(hp_cols), f03.select(hp_cols)])
    hp_edges = quantile_edges(union_hp, hp_cols, args.n_quantile_bins)
    jaccard_rows: list[dict[str, object]] = []
    top_hp_lines: list[str] = []
    for k in args.top_k:
        top02 = f02.sort("y", descending=True).head(k)
        top03 = f03.sort("y", descending=True).head(k)
        bins02 = discretize_hp_bins(top02, hp_cols, hp_edges)
        bins03 = discretize_hp_bins(top03, hp_cols, hp_edges)
        set02 = set(bins02)
        set03 = set(bins03)
        union_bins = set02 | set03
        jac = len(set02 & set03) / len(union_bins) if union_bins else 0.0
        jaccard_rows.append({"k": k, "jaccard_bins": jac})

        top_hp_lines.append(f"# top {k} {LABEL_02}")
        top_hp_lines.append("\t".join(["iter", "y", *hp_cols]))
        for row in top02.select(["iter", "y", *hp_cols]).iter_rows():
            iter_v, y_v, *hp = row
            hp_fmt = [str(decode_hp_value(c, v)) for c, v in zip(hp_cols, hp, strict=True)]
            top_hp_lines.append("\t".join([str(iter_v), str(y_v), *hp_fmt]))
        top_hp_lines.append(f"# top {k} {LABEL_03}")
        top_hp_lines.append("\t".join(["iter", "y", *hp_cols]))
        for row in top03.select(["iter", "y", *hp_cols]).iter_rows():
            iter_v, y_v, *hp = row
            hp_fmt = [str(decode_hp_value(c, v)) for c, v in zip(hp_cols, hp, strict=True)]
            top_hp_lines.append("\t".join([str(iter_v), str(y_v), *hp_fmt]))
        top_hp_lines.append("")

    write_tsv(out_dir / "objetivo_topk_jaccard.tsv", jaccard_rows)
    (out_dir / "objetivo_topk_hp.tsv").write_text("\n".join(top_hp_lines) + "\n", encoding="utf-8")

    print(f"Resumen: {out_dir / 'objetivo_resumen.tsv'}")
    print(f"y_max {LABEL_02}={summaries[0]['y_max']:.6f} {LABEL_03}={summaries[1]['y_max']:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

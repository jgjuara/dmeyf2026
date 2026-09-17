#!/usr/bin/env python3
"""Regiones de alto rendimiento: empirico (BO_log) y perfiles surrogate 1D."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bo_log_utils import TUNABLE_CANDIDATES, decode_hp_value

LABEL_02 = "02_cv5"
LABEL_03 = "03_cv3"

HP_RANGE: dict[str, tuple[float, float]] = {
    "num_iterations": (8.0, 2048.0),
    "learning_rate": (0.01, 0.3),
    "feature_fraction": (0.1, 1.0),
    "num_leaves": (8.0, 2048.0),
    "min_data_in_leaf": (1.0, 8000.0),
    "min_sum_hessian_in_leaf": (1e-5, 10.0),
}


def parse_args(argv: list[str]) -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    z494 = here.parent
    parser = argparse.ArgumentParser(description="Comparar regiones de alto y entre BO y surrogate.")
    parser.add_argument("--bo-02", type=Path, default=z494 / "02/resultados/HT4940/BO_log.txt")
    parser.add_argument("--bo-03", type=Path, default=z494 / "03/resultados/HT4940/BO_log.txt")
    parser.add_argument(
        "--perfil-02",
        type=Path,
        default=z494 / "02/resultados/estudio/perfil_surrogate",
    )
    parser.add_argument(
        "--perfil-03",
        type=Path,
        default=z494 / "03/resultados/estudio/perfil_surrogate",
    )
    parser.add_argument("--out-dir", type=Path, default=here / "estudio")
    parser.add_argument("--frac", type=float, default=0.15, help="Fraccion superior por y (default 15%).")
    return parser.parse_args(argv)


def top_fraction(frame: pl.DataFrame, frac: float) -> pl.DataFrame:
    thr = float(frame["y"].quantile(1.0 - frac))
    return frame.filter(pl.col("y") >= thr)


def interval_overlap(lo1: float, hi1: float, lo2: float, hi2: float, span_lo: float, span_hi: float) -> float:
    inter = max(0.0, min(hi1, hi2) - max(lo1, lo2))
    union = max(hi1, hi2) - min(lo1, lo2)
    norm = span_hi - span_lo
    if union <= 0 or norm <= 0:
        return 0.0
    return inter / union


def empirical_regions(
    f02: pl.DataFrame, f03: pl.DataFrame, hp_cols: list[str], frac: float, out_dir: Path
) -> None:
    t02 = top_fraction(f02, frac)
    t03 = top_fraction(f03, frac)
    rows: list[dict[str, object]] = []
    overlap_rows: list[dict[str, object]] = []

    for col in hp_cols:
        v02 = [decode_hp_value(col, v) for v in t02[col].to_list()]
        v03 = [decode_hp_value(col, v) for v in t03[col].to_list()]
        s02 = pl.Series(v02)
        s03 = pl.Series(v03)
        lo2, hi2 = float(s02.quantile(0.1)), float(s02.quantile(0.9))
        lo3, hi3 = float(s03.quantile(0.1)), float(s03.quantile(0.9))
        span = HP_RANGE.get(col, (min(lo2, lo3), max(hi2, hi3)))
        rows.append(
            {
                "hp": col,
                "corrida": LABEL_02,
                "n_top": t02.height,
                "p10": lo2,
                "p50": float(s02.quantile(0.5)),
                "p90": hi2,
            }
        )
        rows.append(
            {
                "hp": col,
                "corrida": LABEL_03,
                "n_top": t03.height,
                "p10": lo3,
                "p50": float(s03.quantile(0.5)),
                "p90": hi3,
            }
        )
        overlap_rows.append(
            {
                "hp": col,
                "overlap_norm": interval_overlap(lo2, hi2, lo3, hi3, span[0], span[1]),
            }
        )

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.scatter(
            [decode_hp_value(col, v) for v in f02[col].to_list()],
            f02["y"].to_list(),
            s=8,
            alpha=0.35,
            label=LABEL_02,
        )
        ax.scatter(
            [decode_hp_value(col, v) for v in f03[col].to_list()],
            f03["y"].to_list(),
            s=8,
            alpha=0.35,
            label=LABEL_03,
        )
        ax.axhspan(float(f02["y"].quantile(1 - frac)), float(f02["y"].max()), alpha=0.08, color="blue")
        ax.axhspan(float(f03["y"].quantile(1 - frac)), float(f03["y"].max()), alpha=0.08, color="orange")
        ax.set_xlabel(col)
        ax.set_ylabel("y")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(out_dir / f"regiones_empiricas_{col}.png", dpi=120)
        plt.close(fig)

    cols = list(rows[0].keys())
    lines = ["\t".join(cols)]
    for row in rows:
        lines.append("\t".join(str(row[c]) for c in cols))
    (out_dir / "regiones_empiricas_top.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    cols_o = list(overlap_rows[0].keys())
    lines_o = ["\t".join(cols_o)]
    for row in overlap_rows:
        lines_o.append("\t".join(str(row[c]) for c in cols_o))
    (out_dir / "regiones_empiricas_overlap.tsv").write_text("\n".join(lines_o) + "\n", encoding="utf-8")


def load_profile(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, separator="\t")


def surrogate_compare(perfil02: Path, perfil03: Path, out_dir: Path) -> None:
    files02 = sorted(perfil02.glob("profile_*.tsv"))
    if not files02:
        raise FileNotFoundError(f"Sin profile_*.tsv en {perfil02}")

    argmax_rows: list[dict[str, object]] = []
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    axes_flat = axes.flatten()

    for idx, path02 in enumerate(files02):
        param = path02.stem.replace("profile_", "")
        path03 = perfil03 / path02.name
        if not path03.is_file():
            print(f"Falta perfil 03: {path03}", file=sys.stderr)
            continue
        p02 = load_profile(path02)
        p03 = load_profile(path03)
        x02 = p02["x_original"].to_list()
        m02 = p02["profile_mean"].to_list()
        x03 = p03["x_original"].to_list()
        m03 = p03["profile_mean"].to_list()
        i02 = int(max(range(len(m02)), key=lambda i: m02[i]))
        i03 = int(max(range(len(m03)), key=lambda i: m03[i]))
        x_arg02 = float(x02[i02])
        x_arg03 = float(x03[i03])
        span = HP_RANGE.get(param, (min(x_arg02, x_arg03), max(x_arg02, x_arg03)))
        dist = abs(x_arg02 - x_arg03) / (span[1] - span[0]) if span[1] > span[0] else 0.0
        argmax_rows.append(
            {
                "parameter": param,
                "x_argmax_02": x_arg02,
                "x_argmax_03": x_arg03,
                "dist_norm": dist,
                "profile_max_02": m02[i02],
                "profile_max_03": m03[i03],
            }
        )
        ax = axes_flat[idx]
        ax.plot(x02, m02, label=LABEL_02, linewidth=1.2)
        ax.plot(x03, m03, label=LABEL_03, linewidth=1.2, alpha=0.85)
        ax.axvline(x_arg02, color="#1f77b4", linestyle="--", linewidth=0.8)
        ax.axvline(x_arg03, color="#ff7f0e", linestyle="--", linewidth=0.8)
        ax.set_title(param, fontsize=9)
        ax.set_xlabel("x_original")
        if idx % 3 == 0:
            ax.set_ylabel("profile_mean")
        if idx == 0:
            ax.legend(fontsize=7)

    fig.suptitle("profile_mean (surrogate refit por corrida)")
    fig.tight_layout()
    fig.savefig(out_dir / "regiones_surrogate_profile_mean.png", dpi=150)
    plt.close(fig)

    cols = list(argmax_rows[0].keys())
    lines = ["\t".join(cols)]
    for row in argmax_rows:
        lines.append("\t".join(str(row[c]) for c in cols))
    (out_dir / "regiones_surrogate_argmax.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    for p in (args.bo_02, args.bo_03):
        if not p.is_file():
            print(f"No existe: {p}", file=sys.stderr)
            return 1
    if not args.perfil_02.is_dir() or not args.perfil_03.is_dir():
        print("Directorios perfil_surrogate invalidos.", file=sys.stderr)
        return 1

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    f02 = pl.read_csv(args.bo_02.resolve(), separator="\t")
    f03 = pl.read_csv(args.bo_03.resolve(), separator="\t")
    hp_cols = [c for c in TUNABLE_CANDIDATES if c in f02.columns and c in f03.columns]

    empirical_regions(f02, f03, hp_cols, args.frac, out_dir)
    surrogate_compare(args.perfil_02.resolve(), args.perfil_03.resolve(), out_dir)
    print(f"Salida: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Compara trayectorias BO: cummax, distancia infill alineada por dob, resumen Chamfer."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import plotly.graph_objects as go
import polars as pl
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bo_log_utils import (
    chamfer_distance,
    common_hp_columns,
    decode_hp_value,
    euclidean,
    load_hp_cloud,
    min_max_bounds,
    normalize_cloud,
    read_bo_frame,
)

LABEL_02 = "02_cv5"
LABEL_03 = "03_cv3"


def parse_args(argv: list[str]) -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    z494 = here.parent
    parser = argparse.ArgumentParser(description="Comparar trayectorias de dos BO_log.")
    parser.add_argument("--bo-02", type=Path, default=z494 / "02/resultados/HT4940/BO_log.txt")
    parser.add_argument("--bo-03", type=Path, default=z494 / "03/resultados/HT4940/BO_log.txt")
    parser.add_argument("--out-dir", type=Path, default=here / "estudio")
    parser.add_argument("--parallel-top", type=int, default=30)
    return parser.parse_args(argv)


def sort_chronological(frame: pl.DataFrame) -> pl.DataFrame:
    if "dob" in frame.columns:
        return frame.sort("dob")
    return frame.sort("iter")


def cummax_series(frame: pl.DataFrame) -> tuple[list[int], list[float]]:
    ordered = sort_chronological(frame)
    ys = ordered["y"].to_list()
    best = []
    cur = float("-inf")
    for v in ys:
        cur = max(cur, float(v))
        best.append(cur)
    return list(range(1, len(best) + 1)), best


def infill_by_dob(path: Path, hp_cols: list[str]) -> pl.DataFrame:
    frame = read_bo_frame(path, infill_only=True)
    if "dob" not in frame.columns:
        raise ValueError(f"{path}: falta columna dob para alinear infill.")
    return frame.sort("dob")


def plot_cummax(
    idx02: list[int],
    cm02: list[float],
    idx03: list[int],
    cm03: list[float],
    out_all: Path,
    out_infill: Path,
    f02: pl.DataFrame,
    f03: pl.DataFrame,
) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(idx02, cm02, label=LABEL_02)
    ax.plot(idx03, cm03, label=LABEL_03)
    ax.set_xlabel("indice evaluacion (dob)")
    ax.set_ylabel("max y acumulado")
    ax.legend()
    ax.set_title("Mejor y acumulado (todas las evaluaciones)")
    fig.tight_layout()
    fig.savefig(out_all, dpi=150)
    plt.close(fig)

    i02 = sort_chronological(f02.filter(pl.col("prop.type") == "infill_ei"))
    i03 = sort_chronological(f03.filter(pl.col("prop.type") == "infill_ei"))
    ys02, ys03 = [], []
    b02, b03 = float("-inf"), float("-inf")
    for v in i02["y"].to_list():
        b02 = max(b02, float(v))
        ys02.append(b02)
    for v in i03["y"].to_list():
        b03 = max(b03, float(v))
        ys03.append(b03)
    fig2, ax2 = plt.subplots(figsize=(8, 4.5))
    ax2.plot(range(1, len(ys02) + 1), ys02, label=LABEL_02)
    ax2.plot(range(1, len(ys03) + 1), ys03, label=LABEL_03)
    ax2.set_xlabel("indice infill (orden dob)")
    ax2.set_ylabel("max y acumulado (solo infill)")
    ax2.legend()
    fig2.tight_layout()
    fig2.savefig(out_infill, dpi=150)
    plt.close(fig2)


def step_distances(
    inf02: pl.DataFrame, inf03: pl.DataFrame, hp_cols: list[str], out_tsv: Path, out_png: Path
) -> None:
    n = min(inf02.height, inf03.height)
    ids_p, raw_p = load_hp_cloud_from_frame(inf02.head(n), hp_cols)
    ids_q, raw_q = load_hp_cloud_from_frame(inf03.head(n), hp_cols)
    bounds = min_max_bounds([raw_p, raw_q], len(hp_cols))
    norm_p = normalize_cloud(raw_p, bounds)
    norm_q = normalize_cloud(raw_q, bounds)
    dists = [euclidean(a, b) for a, b in zip(norm_p, norm_q, strict=True)]

    lines = ["step\tdob_02\tdob_03\tdist_norm"]
    for i, d in enumerate(dists, start=1):
        lines.append(
            f"{i}\t{inf02['dob'][i - 1]}\t{inf03['dob'][i - 1]}\t{d:.8f}"
        )
    out_tsv.write_text("\n".join(lines) + "\n", encoding="utf-8")

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(range(1, len(dists) + 1), dists, linewidth=0.8)
    ax.set_xlabel("paso infill (orden dob)")
    ax.set_ylabel("distancia euclidea normalizada")
    ax.set_title("Distancia HP alineada por orden dob (infill)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def load_hp_cloud_from_frame(
    frame: pl.DataFrame, hp_cols: list[str]
) -> tuple[list[str], list[tuple[float, ...]]]:
    id_col = "iter" if "iter" in frame.columns else "dob"
    ids: list[str] = []
    points: list[tuple[float, ...]] = []
    for record in frame.select([id_col, *hp_cols]).iter_rows():
        row_id, *raws = record
        ids.append(str(row_id))
        points.append(
            tuple(decode_hp_value(col, raw) for col, raw in zip(hp_cols, raws, strict=True))
        )
    return ids, points


def infill_matrix_stats(matrix_path: Path) -> dict[str, float]:
    lines = matrix_path.read_text(encoding="utf-8").splitlines()
    row_mins: list[float] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        vals = [float(x) for x in line.split("\t")[1:]]
        row_mins.append(min(vals))
    row_mins.sort()
    n = len(row_mins)
    cost = [[0.0] * n for _ in range(n)]
    for i, line in enumerate(lines[1:]):
        if not line.strip():
            continue
        vals = [float(x) for x in line.split("\t")[1:]]
        cost[i] = vals
    row_ind, col_ind = linear_sum_assignment(cost)
    match_costs = [cost[i][j] for i, j in zip(row_ind, col_ind, strict=True)]
    return {
        "row_min_mean": sum(row_mins) / n,
        "row_min_median": row_mins[n // 2],
        "lsa_mean_cost": sum(match_costs) / len(match_costs),
        "lsa_median_cost": sorted(match_costs)[len(match_costs) // 2],
    }


def parallel_coords_html(
    f02: pl.DataFrame, f03: pl.DataFrame, hp_cols: list[str], out_path: Path, top: int
) -> None:
    t02 = f02.sort("y", descending=True).head(top)
    t03 = f03.sort("y", descending=True).head(top)
    dims = []
    for col in hp_cols:
        vals02 = [decode_hp_value(col, v) for v in t02[col].to_list()]
        vals03 = [decode_hp_value(col, v) for v in t03[col].to_list()]
        lo = min(vals02 + vals03)
        hi = max(vals02 + vals03)
        if hi == lo:
            hi = lo + 1.0
        dims.append(
            dict(
                label=col,
                range=[lo, hi],
                values=[decode_hp_value(col, v) for v in t02[col].to_list()]
                + [decode_hp_value(col, v) for v in t03[col].to_list()],
            )
        )
    labels = [LABEL_02] * t02.height + [LABEL_03] * t03.height
    fig = go.Figure(
        data=go.Parcoords(
            line=dict(
                color=[0] * t02.height + [1] * t03.height,
                colorscale=[[0, "#1f77b4"], [1, "#ff7f0e"]],
                showscale=False,
            ),
            dimensions=dims,
            customdata=labels,
        )
    )
    fig.update_layout(title=f"Coordenadas paralelas top-{top} por y")
    fig.write_html(out_path, include_plotlyjs="cdn")


def write_resumen(path: Path, rows: list[dict[str, object]]) -> None:
    cols = list(rows[0].keys())
    lines = ["\t".join(cols)]
    for row in rows:
        lines.append("\t".join(str(row[c]) for c in cols))
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
    here = Path(__file__).resolve().parent

    f02 = pl.read_csv(path02, separator="\t")
    f03 = pl.read_csv(path03, separator="\t")
    hp_cols = common_hp_columns([path02, path03])

    idx02, cm02 = cummax_series(f02)
    idx03, cm03 = cummax_series(f03)
    plot_cummax(
        idx02,
        cm02,
        idx03,
        cm03,
        out_dir / "trayectoria_cummax_y.png",
        out_dir / "trayectoria_cummax_y_infill.png",
        f02,
        f03,
    )

    inf02 = infill_by_dob(path02, hp_cols)
    inf03 = infill_by_dob(path03, hp_cols)
    step_distances(
        inf02,
        inf03,
        hp_cols,
        out_dir / "trayectoria_distancia_paso_infill.tsv",
        out_dir / "trayectoria_distancia_paso_infill.png",
    )

    dist_name = "02_03_distancia_infill.tsv"
    subprocess.run(
        [
            sys.executable,
            str(here / "bo_distancia_infill.py"),
            str(path02),
            str(path03),
            "--label-p",
            "02",
            "--label-q",
            "03",
            "--out-dir",
            str(out_dir),
            "--out-name",
            dist_name,
        ],
        check=True,
    )
    matrix_path = out_dir / dist_name
    stats = infill_matrix_stats(matrix_path)

    chamfer_script = here / "bo_distancia_chamfer.py"
    subprocess.run(
        [
            sys.executable,
            str(chamfer_script),
            str(path02),
            str(path03),
            "--infill-only",
            "--labels",
            "02",
            "03",
            "--out-dir",
            str(out_dir),
            "--out-name",
            "02_03_distancia_chamfer.tsv",
        ],
        check=True,
    )
    chamfer_lines = (out_dir / "02_03_distancia_chamfer.tsv").read_text(encoding="utf-8").splitlines()
    chamfer_val = float(chamfer_lines[1].split("\t")[2])

    _, raw02 = load_hp_cloud(path02, hp_cols, infill_only=True)
    _, raw03 = load_hp_cloud(path03, hp_cols, infill_only=True)
    bounds = min_max_bounds([raw02, raw03], len(hp_cols))
    chamfer_check = chamfer_distance(
        normalize_cloud(raw02, bounds), normalize_cloud(raw03, bounds)
    )

    resumen = [
        {"metrica": "chamfer_infill_norm", "valor": chamfer_val},
        {"metrica": "chamfer_recheck", "valor": chamfer_check},
        {"metrica": "infill_row_min_mean", "valor": stats["row_min_mean"]},
        {"metrica": "infill_row_min_median", "valor": stats["row_min_median"]},
        {"metrica": "infill_lsa_mean", "valor": stats["lsa_mean_cost"]},
        {"metrica": "infill_lsa_median", "valor": stats["lsa_median_cost"]},
    ]
    write_resumen(out_dir / "trayectoria_resumen.tsv", resumen)

    subprocess.run(
        [
            sys.executable,
            str(here / "bo_similitud_infill.py"),
            str(matrix_path),
            "--out-dir",
            str(out_dir),
        ],
        check=True,
    )
    sim_path = out_dir / "02_03_similitud_infill.tsv"
    subprocess.run(
        [
            sys.executable,
            str(here / "bo_similitud_infill_plot.py"),
            str(sim_path),
            "--bo-log-p",
            str(path02),
            "--bo-log-q",
            str(path03),
            "--top-k",
            "10",
            "--out-dir",
            str(out_dir),
            "--out-name",
            "02_03_top10_similitud_infill.html",
        ],
        check=True,
    )

    parallel_coords_html(
        f02, f03, hp_cols, out_dir / "trayectoria_parallel_coords_top30.html", args.parallel_top
    )

    print(f"Chamfer infill: {chamfer_val:.6f}")
    print(f"Resumen: {out_dir / 'trayectoria_resumen.tsv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

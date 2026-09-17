#!/usr/bin/env python3
"""HTML interactivo (Plotly) para matriz de similitud infill P x Q."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import plotly.graph_objects as go
import polars as pl


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Heatmap Plotly de similitud infill (submatriz opcional top-K BO)."
    )
    parser.add_argument(
        "similitud_infill",
        type=Path,
        help="Ruta al *_similitud_infill.tsv.",
    )
    parser.add_argument(
        "--bo-log-p",
        type=Path,
        default=None,
        help="BO_log de P (filas); requerido con --top-k.",
    )
    parser.add_argument(
        "--bo-log-q",
        type=Path,
        default=None,
        help="BO_log de Q (columnas); requerido con --top-k.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Filtrar a los K mejores modelos por AUC (y) en cada BO_log.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Directorio de salida (default: mismo que el TSV).",
    )
    parser.add_argument(
        "--out-name",
        default=None,
        help="HTML de salida.",
    )
    return parser.parse_args(argv)


def read_matrix(path: Path) -> tuple[list[str], list[str], list[list[float]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("archivo vacio")
    header = lines[0].split("\t")
    col_ids = header[1:]
    row_ids: list[str] = []
    z: list[list[float]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        row_ids.append(parts[0])
        z.append([float(v) for v in parts[1:]])
    if not row_ids or not col_ids:
        raise ValueError("matriz sin datos")
    return row_ids, col_ids, z


def top_iters_from_bo_log(path: Path, k: int) -> list[str]:
    frame = pl.read_csv(path, separator="\t")
    if "y" not in frame.columns or "iter" not in frame.columns:
        raise ValueError(f"{path}: requiere columnas y e iter.")
    ranked = frame.sort("y", descending=True).head(k)
    return [str(v) for v in ranked["iter"].to_list()]


def iter_from_axis_id(axis_id: str) -> str:
    return axis_id.rsplit("_", 1)[-1]


def filter_top_k(
    row_ids: list[str],
    col_ids: list[str],
    z: list[list[float]],
    top_p: list[str],
    top_q: list[str],
) -> tuple[list[str], list[str], list[list[float]]]:
    row_by_iter = {iter_from_axis_id(rid): idx for idx, rid in enumerate(row_ids)}
    col_by_iter = {iter_from_axis_id(cid): idx for idx, cid in enumerate(col_ids)}

    missing_p = [it for it in top_p if it not in row_by_iter]
    missing_q = [it for it in top_q if it not in col_by_iter]
    if missing_p:
        print(f"Aviso: top P sin fila infill en matriz: {missing_p}", file=sys.stderr)
    if missing_q:
        print(f"Aviso: top Q sin columna infill en matriz: {missing_q}", file=sys.stderr)

    row_order = [row_by_iter[it] for it in top_p if it in row_by_iter]
    col_order = [col_by_iter[it] for it in top_q if it in col_by_iter]

    new_row_ids = [row_ids[i] for i in row_order]
    new_col_ids = [col_ids[j] for j in col_order]
    new_z = [[z[i][j] for j in col_order] for i in row_order]
    return new_row_ids, new_col_ids, new_z


def build_figure(
    row_ids: list[str],
    col_ids: list[str],
    z: list[list[float]],
    *,
    title: str,
) -> go.Figure:
    z_flat = [v for row in z for v in row]
    z_min = min(z_flat)
    z_max = max(z_flat)
    n_rows = len(row_ids)
    n_cols = len(col_ids)

    customdata = [
        [[row_ids[i], col_ids[j]] for j in range(n_cols)] for i in range(n_rows)
    ]
    text = [[f"{v:.3f}" for v in row] for row in z]

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=col_ids,
            y=row_ids,
            text=text,
            texttemplate="%{text}",
            textfont={"size": 10},
            colorscale="Viridis",
            zmin=z_min,
            zmax=z_max,
            colorbar=dict(title="Similitud"),
            customdata=customdata,
            hovertemplate=(
                "P: %{customdata[0]}<br>"
                "Q: %{customdata[1]}<br>"
                "Similitud: %{z:.6f}<extra></extra>"
            ),
            xgap=1,
            ygap=1,
        )
    )

    fig.update_layout(
        title=title,
        xaxis=dict(title="Q (top por AUC BO)", tickangle=-45, side="bottom"),
        yaxis=dict(title="P (top por AUC BO)", autorange="reversed"),
        width=950,
        height=850,
        margin=dict(l=120, r=80, t=80, b=180),
    )
    return fig


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    sim_path = args.similitud_infill.resolve()
    if not sim_path.is_file():
        print(f"No existe: {sim_path}", file=sys.stderr)
        return 1

    if (args.top_k is None) != (args.bo_log_p is None or args.bo_log_q is None):
        if args.top_k is not None:
            print("--top-k requiere --bo-log-p y --bo-log-q.", file=sys.stderr)
            return 1

    row_ids, col_ids, z = read_matrix(sim_path)
    title_suffix = ""

    if args.top_k is not None:
        assert args.bo_log_p is not None and args.bo_log_q is not None
        path_p = args.bo_log_p.resolve()
        path_q = args.bo_log_q.resolve()
        for path in (path_p, path_q):
            if not path.is_file():
                print(f"No existe: {path}", file=sys.stderr)
                return 1
        top_p = top_iters_from_bo_log(path_p, args.top_k)
        top_q = top_iters_from_bo_log(path_q, args.top_k)
        row_ids, col_ids, z = filter_top_k(row_ids, col_ids, z, top_p, top_q)
        title_suffix = f" — top {args.top_k} modelos BO (rank AUC global)"

    title = f"Similitud infill ({len(row_ids)} × {len(col_ids)}){title_suffix}"
    fig = build_figure(row_ids, col_ids, z, title=title)

    out_dir = (args.out_dir or sim_path.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.out_name:
        out_name = args.out_name
    elif args.top_k is not None:
        stem = sim_path.stem.replace("_similitud_infill", "")
        out_name = f"{stem}_top{args.top_k}_similitud_infill.html"
    else:
        out_name = f"{sim_path.stem}.html"
    out_path = out_dir / out_name
    fig.write_html(out_path, include_plotlyjs="cdn")
    print(f"Celdas: {len(row_ids) * len(col_ids)}")
    print(f"HTML: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Matriz N x N de distancia de Chamfer entre nubes de evaluaciones de BO_log."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bo_log_utils import (
    chamfer_distance,
    common_hp_columns,
    default_label,
    load_hp_cloud,
    min_max_bounds,
    normalize_cloud,
    unique_labels,
    write_bounds_meta,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Distancia de Chamfer entre corridas BO (HP fisicos, [0,1])."
    )
    parser.add_argument(
        "bo_logs",
        nargs="+",
        type=Path,
        help="Rutas a BO_log.txt (minimo 2).",
    )
    parser.add_argument(
        "--infill-only",
        action="store_true",
        help="Usar solo filas prop.type=infill_ei (default: todas las evaluaciones).",
    )
    parser.add_argument(
        "--labels",
        nargs="*",
        default=None,
        help="Etiquetas por log; por defecto carpeta z494/NN.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=here / "estudio",
        help="Directorio de salida (default: common/estudio).",
    )
    parser.add_argument(
        "--out-name",
        default=None,
        help="TSV de salida (default: <labels>_distancia_chamfer.tsv).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    paths = [p.resolve() for p in args.bo_logs]
    for path in paths:
        if not path.is_file():
            print(f"No existe: {path}", file=sys.stderr)
            return 1
    if len(paths) < 2:
        print("Se necesitan al menos 2 BO_log.", file=sys.stderr)
        return 1

    hp_cols = common_hp_columns(paths)
    if not hp_cols:
        print("No hay hiperparametros tunables en comun.", file=sys.stderr)
        return 1

    if args.labels is not None and len(args.labels) not in (0, len(paths)):
        print("--labels debe tener la misma cantidad que bo_logs.", file=sys.stderr)
        return 1

    labels = unique_labels(
        args.labels if args.labels else [default_label(p) for p in paths]
    )

    infill_only = args.infill_only
    raw_clouds = [
        load_hp_cloud(path, hp_cols, infill_only=infill_only)[1] for path in paths
    ]
    bounds = min_max_bounds(raw_clouds, len(hp_cols))
    norm_clouds = [normalize_cloud(cloud, bounds) for cloud in raw_clouds]

    n = len(paths)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = chamfer_distance(norm_clouds[i], norm_clouds[j])
            dist[i][j] = d
            dist[j][i] = d

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = "_".join(labels)
    out_name = args.out_name or f"{slug}_distancia_chamfer.tsv"
    matrix_path = out_dir / out_name

    lines = ["label\t" + "\t".join(labels)]
    for i, row_label in enumerate(labels):
        row = [row_label] + [f"{dist[i][j]:.8f}" for j in range(n)]
        lines.append("\t".join(row))
    matrix_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    meta_path = out_dir / (Path(out_name).stem + "_meta.tsv")
    write_bounds_meta(meta_path, hp_cols, bounds)

    scope = "infill" if infill_only else "todas las evaluaciones"
    print(f"HP comunes ({len(hp_cols)}): {', '.join(hp_cols)}")
    print(f"Alcance: {scope}")
    for label, cloud in zip(labels, raw_clouds, strict=True):
        print(f"  {label}: {len(cloud)} puntos")
    print(f"Matriz Chamfer: {matrix_path}")
    print(f"Normalizacion: {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

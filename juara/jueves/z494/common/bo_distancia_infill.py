#!/usr/bin/env python3
"""Matriz |P| x |Q| de distancias euclideas entre evaluaciones infill de dos BO_log."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bo_log_utils import (
    common_hp_columns,
    default_label,
    euclidean,
    load_hp_cloud,
    min_max_bounds,
    normalize_cloud,
    unique_labels,
    write_bounds_meta,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Distancia infill P x infill Q (HP fisicos, normalizados a [0,1])."
    )
    parser.add_argument("bo_log_p", type=Path, help="BO_log de P (filas de la matriz).")
    parser.add_argument("bo_log_q", type=Path, help="BO_log de Q (columnas de la matriz).")
    parser.add_argument("--label-p", default=None, help="Etiqueta de P (default: carpeta z494).")
    parser.add_argument("--label-q", default=None, help="Etiqueta de Q.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=here / "estudio",
        help="Directorio de salida (default: common/estudio).",
    )
    parser.add_argument(
        "--out-name",
        default=None,
        help="TSV de salida (default: <p>_<q>_distancia_infill.tsv).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    path_p = args.bo_log_p.resolve()
    path_q = args.bo_log_q.resolve()
    for path in (path_p, path_q):
        if not path.is_file():
            print(f"No existe: {path}", file=sys.stderr)
            return 1

    hp_cols = common_hp_columns([path_p, path_q])
    if not hp_cols:
        print("No hay hiperparametros tunables en comun.", file=sys.stderr)
        return 1

    label_p, label_q = unique_labels(
        [
            args.label_p or default_label(path_p),
            args.label_q or default_label(path_q),
        ]
    )

    ids_p, raw_p = load_hp_cloud(path_p, hp_cols, infill_only=True)
    ids_q, raw_q = load_hp_cloud(path_q, hp_cols, infill_only=True)
    bounds = min_max_bounds([raw_p, raw_q], len(hp_cols))
    norm_p = normalize_cloud(raw_p, bounds)
    norm_q = normalize_cloud(raw_q, bounds)

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = args.out_name or f"{label_p}_{label_q}_distancia_infill.tsv"
    matrix_path = out_dir / out_name

    header = [f"{label_p}_id"] + [f"{label_q}_{qid}" for qid in ids_q]
    lines = ["\t".join(header)]
    for pid, point_p in zip(ids_p, norm_p, strict=True):
        row = [f"{label_p}_{pid}"]
        row.extend(f"{euclidean(point_p, point_q):.8f}" for point_q in norm_q)
        lines.append("\t".join(row))
    matrix_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    meta_path = out_dir / (Path(out_name).stem + "_meta.tsv")
    write_bounds_meta(meta_path, hp_cols, bounds)

    print(f"HP comunes ({len(hp_cols)}): {', '.join(hp_cols)}")
    print(f"  P ({label_p}): {len(norm_p)} infill")
    print(f"  Q ({label_q}): {len(norm_q)} infill")
    print(f"Matriz: {matrix_path} ({len(norm_p)} x {len(norm_q)})")
    print(f"Normalizacion: {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

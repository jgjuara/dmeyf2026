#!/usr/bin/env python3
"""Similitud a partir de una matriz de distancia infill (salida de bo_distancia_infill)."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path


def distance_to_similarity(d: float, method: str) -> float:
    if d < 0:
        raise ValueError(f"distancia negativa: {d}")
    if method == "inv1p":
        return 1.0 / (1.0 + d)
    if method == "exp":
        return math.exp(-d)
    raise ValueError(f"metodo desconocido: {method}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Convierte TSV distancia infill P x Q en similitud (misma forma)."
    )
    parser.add_argument(
        "distancia_infill",
        type=Path,
        help="Ruta al *_distancia_infill.tsv.",
    )
    parser.add_argument(
        "--method",
        choices=("inv1p", "exp"),
        default="inv1p",
        help="inv1p: 1/(1+d); exp: exp(-d).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Directorio de salida (default: mismo que el TSV de entrada).",
    )
    parser.add_argument(
        "--out-name",
        default=None,
        help="Nombre de salida (default: reemplaza distancia por similitud en el nombre).",
    )
    return parser.parse_args(argv)


def default_out_path(dist_path: Path, out_name: str | None) -> Path:
    if out_name:
        return dist_path.parent / out_name
    stem = dist_path.stem
    if "_distancia_infill" in stem:
        stem = stem.replace("_distancia_infill", "_similitud_infill", 1)
    else:
        stem = f"{stem}_similitud_infill"
    return dist_path.parent / f"{stem}.tsv"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    dist_path = args.distancia_infill.resolve()
    if not dist_path.is_file():
        print(f"No existe: {dist_path}", file=sys.stderr)
        return 1

    text = dist_path.read_text(encoding="utf-8").splitlines()
    if not text:
        print("Archivo vacio.", file=sys.stderr)
        return 1

    header = text[0].split("\t")
    if len(header) < 2:
        print("Formato invalido: se esperaba matriz con encabezados.", file=sys.stderr)
        return 1

    out_lines = ["\t".join(header)]
    n_rows = 0
    n_cols = len(header) - 1
    for line in text[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != len(header):
            print(f"Fila con ancho incorrecto: {parts[0]}", file=sys.stderr)
            return 1
        row_id = parts[0]
        sims = [f"{distance_to_similarity(float(v), args.method):.8f}" for v in parts[1:]]
        out_lines.append("\t".join([row_id, *sims]))
        n_rows += 1

    out_dir = (args.out_dir or dist_path.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (args.out_name or default_out_path(dist_path, None).name)

    out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"Metodo: {args.method}")
    print(f"Entrada: {dist_path} ({n_rows} x {n_cols})")
    print(f"Salida: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

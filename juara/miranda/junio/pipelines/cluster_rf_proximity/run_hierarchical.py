"""Ejecuta clustering jerárquico sobre la distancia RF de la cohorte baja."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from _hierarchical import run_hierarchical
from _paths import DEFAULT_PARQUET, HIERARCHICAL_OUT_DIR, OUT_DIR as PROXIMITY_OUT_DIR


def parse_args() -> argparse.Namespace:
    """Parámetros del análisis jerárquico."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proximity-dir", type=Path, default=PROXIMITY_OUT_DIR)
    parser.add_argument("--parquet", type=Path, default=DEFAULT_PARQUET)
    parser.add_argument("--out-dir", type=Path, default=HIERARCHICAL_OUT_DIR)
    parser.add_argument("--k-min", type=int, default=2)
    parser.add_argument("--k-max", type=int, default=15)
    parser.add_argument(
        "--min-cluster-size",
        type=int,
        default=50,
        help="Cortes con algún clúster más chico se marcan degenerados",
    )
    return parser.parse_args()


def main() -> None:
    """Corre el pipeline y lista artefactos generados."""
    args = parse_args()
    started = time.monotonic()
    artifacts = run_hierarchical(
        proximity_dir=args.proximity_dir,
        parquet_path=args.parquet,
        out_dir=args.out_dir,
        k_min=args.k_min,
        k_max=args.k_max,
        min_cluster_size=args.min_cluster_size,
    )
    elapsed = time.monotonic() - started
    print(f"completado en {elapsed:.1f}s")
    for label, path in artifacts.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()

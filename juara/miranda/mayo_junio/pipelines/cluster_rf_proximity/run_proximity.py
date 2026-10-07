"""Genera proximidad RF (no supervisada o BAJA+1/BAJA+2) para la cohorte baja mayo–junio."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from _paths import DEFAULT_PARQUET, OUT_DIR
from _rf_proximity import run_proximity


def parse_args() -> argparse.Namespace:
    """Lee los parámetros reproducibles del pipeline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, default=DEFAULT_PARQUET)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--n-trees", type=int, default=300)
    parser.add_argument("--min-samples-leaf", type=int, default=50)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--forest-mode",
        choices=("unsupervised", "supervised_baja12"),
        default="unsupervised",
        help="unsupervised: RF real-vs-sintético; supervised_baja12: RF sobre BAJA+1/BAJA+2",
    )
    parser.add_argument(
        "--feature-scope",
        choices=("all", "sin_lag_delta"),
        default="all",
        help="all: todas las numéricas; sin_lag_delta: nocontinuas_base + pct_* del mes (sin lag/delta)",
    )
    return parser.parse_args()


def main() -> None:
    """Ejecuta el pipeline y comunica las rutas de los artefactos creados."""
    args = parse_args()
    started_at = time.monotonic()
    artifacts = run_proximity(
        parquet_path=args.parquet,
        out_dir=args.out_dir,
        n_trees=args.n_trees,
        min_samples_leaf=args.min_samples_leaf,
        seed=args.seed,
        forest_mode=args.forest_mode,
        feature_scope=args.feature_scope,
    )
    elapsed = time.monotonic() - started_at
    print(f"completado en {elapsed:.1f}s")
    for label, path in artifacts.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()

"""Entrena RF multiclass para predecir foto_mes (drifting)."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from _model import run_pipeline
from _paths import DEFAULT_PARQUET, OUT_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, default=DEFAULT_PARQUET)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--n-trees", type=int, default=300)
    parser.add_argument("--min-samples-leaf", type=int, default=50)
    parser.add_argument(
        "--importance-max-samples",
        type=int,
        default=20_000,
        help="Submuestra estratificada del test para permutation importance (None = test completo)",
    )
    parser.add_argument(
        "--no-importance-cap",
        action="store_true",
        help="Usar todo el conjunto de test para permutation importance",
    )
    parser.add_argument("--oob-score", action="store_true", help="Activar oob_score en el bosque (solo train)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    imp_max = None if args.no_importance_cap else args.importance_max_samples
    started = time.monotonic()
    artifacts = run_pipeline(
        parquet_path=args.parquet,
        out_dir=args.out_dir,
        test_size=args.test_size,
        seed=args.seed,
        n_trees=args.n_trees,
        min_samples_leaf=args.min_samples_leaf,
        importance_max_samples=imp_max,
        oob_score=args.oob_score,
    )
    elapsed = time.monotonic() - started
    print(f"completado en {elapsed:.1f}s")
    for label, path in artifacts.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()

"""Genera informe de perfiles agrupados (k=7 con fusión 2+4+5)."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from _grouped_report import run_grouped_report
from _paths import (
    DEFAULT_PARQUET,
    GROUPED_OUT_DIR,
    HIERARCHICAL_OUT_DIR,
    OUT_DIR as PROXIMITY_OUT_DIR,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hierarchical-dir", type=Path, default=HIERARCHICAL_OUT_DIR)
    parser.add_argument("--proximity-dir", type=Path, default=PROXIMITY_OUT_DIR)
    parser.add_argument("--parquet", type=Path, default=DEFAULT_PARQUET)
    parser.add_argument("--out-dir", type=Path, default=GROUPED_OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.monotonic()
    artifacts = run_grouped_report(
        hierarchical_dir=args.hierarchical_dir,
        proximity_dir=args.proximity_dir,
        parquet_path=args.parquet,
        out_dir=args.out_dir,
    )
    print(f"completado en {time.monotonic() - started:.1f}s")
    for label, path in artifacts.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Verifica esquema target tras read_joined para intentos Python (*py)."""

from __future__ import annotations

import sys
from pathlib import Path

_COMPE1 = Path(__file__).resolve().parents[1]
if str(_COMPE1) not in sys.path:
    sys.path.insert(0, str(_COMPE1))

from common.data import (  # noqa: E402
    FOTO_MES_MAR_JUN,
    TARGET_COL,
    feature_columns,
    is_target_derivative,
    read_joined,
)
from common.layers import DATA_DIR, _LAYERS_BY_ID, _PY_ATTEMPT_IDS  # noqa: E402


def _layers_available(attempt: str) -> bool:
    for name in _LAYERS_BY_ID[attempt]:
        if not (DATA_DIR / name).is_file():
            return False
    return True


def main() -> None:
    failed = False
    for attempt in sorted(_PY_ATTEMPT_IDS):
        experiment_id = f"{attempt}-00"
        if attempt not in _LAYERS_BY_ID:
            print(f"SKIP {experiment_id}: sin capas en layers.py")
            continue
        if not _layers_available(attempt):
            missing = [
                name
                for name in _LAYERS_BY_ID[attempt]
                if not (DATA_DIR / name).is_file()
            ]
            print(f"SKIP {experiment_id}: parquets faltantes ({len(missing)})")
            continue

        df = read_joined(experiment_id, foto_mes=FOTO_MES_MAR_JUN)
        n_feat = len(feature_columns(df))
        deriv_in_features = [c for c in feature_columns(df) if is_target_derivative(c)]
        if deriv_in_features:
            print(f"FAIL {experiment_id}: derivadas en campos_buenos: {deriv_in_features}")
            failed = True
            continue
        print(
            f"OK {experiment_id}: filas={df.height}, columnas={len(df.columns)}, "
            f"target={TARGET_COL} (única), features={n_feat}"
        )

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

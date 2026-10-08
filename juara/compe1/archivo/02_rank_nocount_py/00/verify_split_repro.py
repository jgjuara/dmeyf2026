#!/usr/bin/env python3
"""Comprueba que el split Python es determinista (misma semilla → mismos folds)."""

from __future__ import annotations

import _bootstrap  # noqa: F401

from common.data import FOTO_MES_MAR_JUN, read_joined
from common.partition import assign_split_training

SEED = 427417


def main() -> None:
    base = read_joined("02_rank_nocount_py", foto_mes=FOTO_MES_MAR_JUN).select(
        "numero_de_cliente", "foto_mes", "clase_ternaria"
    )
    a = assign_split_training(base, SEED, (70, 30), 1, 0.1, True)
    b = assign_split_training(base, SEED, (70, 30), 1, 0.1, True)
    if not a.select("fold", "azar", "training").equals(b.select("fold", "azar", "training")):
        raise SystemExit("split no reproducible")
    print(f"OK: {a.height} filas, split determinista (seed={SEED})")


if __name__ == "__main__":
    main()

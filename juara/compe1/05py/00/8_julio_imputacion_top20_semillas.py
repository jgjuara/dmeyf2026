#!/usr/bin/env python3
"""Mar–jun → predict julio → imputar clase01 (05py pseudo-julio fase 8)."""

from __future__ import annotations

import _bootstrap  # noqa: F401
from _bootstrap import EXPERIMENT_ID

from common.pseudo_julio import main_fase_julio_imputacion


def main() -> None:
    main_fase_julio_imputacion(EXPERIMENT_ID)


if __name__ == "__main__":
    main()

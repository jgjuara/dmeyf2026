#!/usr/bin/env python3
"""Train mar–jul (julio imputado) → predict agosto (05py pseudo-julio fase 9)."""

from __future__ import annotations

import _bootstrap  # noqa: F401
from _bootstrap import EXPERIMENT_ID

from common.pseudo_julio import main_fase_agosto_mar_jul


def main() -> None:
    main_fase_agosto_mar_jul(EXPERIMENT_ID)


if __name__ == "__main__":
    main()

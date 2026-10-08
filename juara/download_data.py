"""Descarga datasets de la tarea hogar 02 a juara/data."""

from __future__ import annotations

import sys
from pathlib import Path

_JUARA = Path(__file__).resolve().parent
_FE = _JUARA / "fe"
if str(_FE) not in sys.path:
    sys.path.insert(0, str(_FE))

from download_competencia_crudo import download_competencia_crudo, main

__all__ = ["download_competencia_crudo", "main"]

if __name__ == "__main__":
    main()

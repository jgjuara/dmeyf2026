"""Añade juara/compe1 al sys.path para imports `common.*`."""

import sys
from pathlib import Path

_COMPE1 = Path(__file__).resolve().parents[2]
if str(_COMPE1) not in sys.path:
    sys.path.insert(0, str(_COMPE1))

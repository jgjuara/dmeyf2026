"""Añade juara/compe1 al sys.path; define ``EXPERIMENT_ID`` = ``{intento}-{iteración}``."""

import sys
from pathlib import Path

_COMPE1 = Path(__file__).resolve().parents[2]
if str(_COMPE1) not in sys.path:
    sys.path.insert(0, str(_COMPE1))

import common.vm_runtime  # noqa: E402, F401

_ATTEMPT = Path(__file__).resolve().parents[1].name
_ITERATION = Path(__file__).resolve().parent.name
ATTEMPT_ID = _ATTEMPT
ITERATION = _ITERATION
EXPERIMENT_ID = f"{_ATTEMPT}-{_ITERATION}"

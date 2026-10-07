"""Preset de cohorte para el análisis descriptivo (env MIRANDA_COHORT)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CohortPreset:
    key: str
    dataset_name: str
    out_dir_name: str
    informe_name: str
    join_script: str
    run_script: str


_PRESETS: dict[str, CohortPreset] = {
    "baja": CohortPreset(
        key="baja",
        dataset_name="datos/dataset_junio.parquet",
        out_dir_name="salidas/descriptivo/informe_casos_junio",
        informe_name="informe_casos_junio.md",
        join_script="prep/join_junio.py",
        run_script="run_descriptivo.py",
    ),
    "continua_20": CohortPreset(
        key="continua_20",
        dataset_name="datos/dataset_continua_20_junio.parquet",
        out_dir_name="salidas/descriptivo/informe_casos_continua_20_junio",
        informe_name="informe_casos_continua_20_junio.md",
        join_script="prep/join_continua_20_junio.py",
        run_script="run_descriptivo_continua_20.py",
    ),
}


def active_preset() -> CohortPreset:
    key = os.environ.get("MIRANDA_COHORT", "baja")
    if key not in _PRESETS:
        raise SystemExit(f"MIRANDA_COHORT no soportado: {key} (opciones: {', '.join(_PRESETS)})")
    return _PRESETS[key]

"""Rutas del análisis descriptivo (preset vía MIRANDA_COHORT en _cohort)."""

from pathlib import Path

from _cohort import active_preset

MIRANDA_DIR = Path(__file__).resolve().parent.parent.parent
_PRESET = active_preset()
DATASET_PARQUET = MIRANDA_DIR / _PRESET.dataset_name
OUT_DIR = MIRANDA_DIR / _PRESET.out_dir_name
TABLAS_DIR = OUT_DIR / "tablas"
PLOTS_DIR = OUT_DIR / "plots"
INFORME_MD = OUT_DIR / _PRESET.informe_name
COHORT_PRESET = _PRESET

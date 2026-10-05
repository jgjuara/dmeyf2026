"""Rutas del pipeline RF foto_mes en nivel crudo (drifting)."""

from pathlib import Path

DRIFTING_DIR = Path(__file__).resolve().parent.parent.parent
JUARA_DIR = DRIFTING_DIR.parent
DEFAULT_PARQUET = DRIFTING_DIR / "datos" / "dataset_nocont_nivel.parquet"
OUT_DIR = DRIFTING_DIR / "resultados" / "rf_foto_mes_nivel"
BASELINE_METRICAS = DRIFTING_DIR / "resultados" / "rf_foto_mes" / "metricas.json"

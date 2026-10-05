"""Rutas del módulo autónomo de análisis final."""

from __future__ import annotations

from pathlib import Path


FINAL_DIR = Path(__file__).resolve().parent
JUARA_DIR = FINAL_DIR.parents[1]
SOURCE_PARQUET = JUARA_DIR / "data" / "competencia_01.parquet"
RESULTADOS_DIR = FINAL_DIR / "resultados"
RESULTS_DIR = RESULTADOS_DIR
TABLAS_DIR = RESULTADOS_DIR / "tablas"
TABLES_DIR = TABLAS_DIR
PANEL_DIR = RESULTADOS_DIR / "panel"
PLOTS_DIR = RESULTADOS_DIR / "plots"
PERFILES_CLIENTES_PLOTS_DIR = PLOTS_DIR / "perfiles_clientes"


def ensure_output_directories() -> None:
    """Crea únicamente los directorios de salida propios del módulo."""

    for directory in (TABLAS_DIR, PANEL_DIR, PLOTS_DIR, PERFILES_CLIENTES_PLOTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)

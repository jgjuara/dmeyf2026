"""Rutas del pipeline RF por proximidad (cohorte baja mayo–junio)."""

from pathlib import Path

MIRANDA_DIR = Path(__file__).resolve().parent.parent.parent
_CLUSTER = MIRANDA_DIR / "salidas" / "cluster"
DEFAULT_PARQUET = MIRANDA_DIR / "datos" / "dataset_mayo_junio.parquet"
OUT_DIR = _CLUSTER / "salida_cluster_rf_proximity"
HIERARCHICAL_OUT_DIR = _CLUSTER / "salida_cluster_jerarquico"
GROUPED_OUT_DIR = _CLUSTER / "salida_cluster_jerarquico_agrupado"
OUT_DIR_BAJA12 = _CLUSTER / "salida_cluster_rf_proximity_baja12"
HIERARCHICAL_OUT_DIR_BAJA12 = _CLUSTER / "salida_cluster_jerarquico_baja12"
GROUPED_OUT_DIR_BAJA12 = _CLUSTER / "salida_cluster_jerarquico_agrupado_baja12"
OUT_DIR_BAJA12_SIN_LAG_DELTA = _CLUSTER / "salida_cluster_rf_proximity_baja12_sin_lag_delta"
HIERARCHICAL_OUT_DIR_BAJA12_SIN_LAG_DELTA = (
    _CLUSTER / "salida_cluster_jerarquico_baja12_sin_lag_delta"
)

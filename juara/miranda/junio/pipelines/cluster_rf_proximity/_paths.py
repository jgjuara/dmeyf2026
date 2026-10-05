"""Rutas del pipeline RF por proximidad (cohorte baja junio 2021)."""

from pathlib import Path

MIRANDA_DIR = Path(__file__).resolve().parent.parent.parent
_CLUSTER = MIRANDA_DIR / "salidas" / "cluster"
DEFAULT_PARQUET = MIRANDA_DIR / "datos" / "dataset_junio.parquet"
OUT_DIR = _CLUSTER / "salida_cluster_rf_proximity"
HIERARCHICAL_OUT_DIR = _CLUSTER / "salida_cluster_jerarquico"
GROUPED_OUT_DIR = _CLUSTER / "salida_cluster_jerarquico_agrupado"
OUT_DIR_BAJA12 = _CLUSTER / "salida_cluster_rf_proximity_baja12"
HIERARCHICAL_OUT_DIR_BAJA12 = _CLUSTER / "salida_cluster_jerarquico_baja12"
GROUPED_OUT_DIR_BAJA12 = _CLUSTER / "salida_cluster_jerarquico_agrupado_baja12"

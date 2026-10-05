"""Parámetros reproducibles del pipeline de bajas."""

from __future__ import annotations

ALL_FOTO_MESES: tuple[int, ...] = (202103, 202104, 202105, 202106, 202107, 202108)
ANCHOR_MONTHS: tuple[int, ...] = (202103, 202104, 202105, 202106)
BAJA_CLASSES: frozenset[str] = frozenset({"BAJA+1", "BAJA+2"})
CONTINUA_CLASS = "CONTINUA"
EVENT_HORIZONS: tuple[int, ...] = (1, 2)

# Compatibilidad temporal para consumidores aún no migrados. La construcción de
# cohorte usa CONTROL_RATIO, no este parámetro.
SAMPLE_FRAC = 0.2
SAMPLE_SEED = 2026
CONTROL_RATIO = 20
MIN_BAJAS_PER_STRATUM = 10
BOOTSTRAP_SEED = 42
BOOTSTRAP_N = 500

CLUSTER_SEED = 7
K_MIN = 2
K_MAX = 8
MIN_CLUSTER_FRAC = 0.05
STABILITY_BOOTSTRAPS = 25

LGBM_PARAMS: dict = {
    "objective": "binary",
    "metric": "auc",
    "verbosity": -1,
    "seed": CLUSTER_SEED,
    "num_leaves": 31,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "min_child_samples": 50,
    "lambda_l1": 0.1,
    "lambda_l2": 0.1,
    "n_estimators": 200,
}

MIN_BAJA_N = 100
MIN_CONTINUA_N = 500

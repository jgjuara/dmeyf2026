"""Espacio de hiperparámetros Optuna (equivalente a mlrMBO makeParamSet)."""

from __future__ import annotations

from typing import Any

import optuna

MIN_SUM_HESSIAN_LO = 0.001
MIN_SUM_HESSIAN_HI = 0.01


def suggest_params(trial: optuna.Trial) -> dict[str, Any]:
    return {
        "num_iterations": trial.suggest_int("num_iterations", 2000, 8000),
        "num_leaves": trial.suggest_int("num_leaves", 10, 400),
        "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 50, 500),
        "min_sum_hessian_in_leaf": trial.suggest_float(
            "min_sum_hessian_in_leaf",
            MIN_SUM_HESSIAN_LO,
            MIN_SUM_HESSIAN_HI,
        ),
    }


def hyperparametertuning_meta() -> dict[str, Any]:
    return {
        "limites_fisicos": {
            "min_sum_hessian_in_leaf": {
                "lower": MIN_SUM_HESSIAN_LO,
                "upper": MIN_SUM_HESSIAN_HI,
            }
        }
    }

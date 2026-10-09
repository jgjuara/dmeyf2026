"""Utilidades Optuna: espacio de búsqueda declarado por script."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import optuna

BoParamSpec = dict[str, Any]
BoSpace = Mapping[str, BoParamSpec]


def suggest_from_bo_space(trial: optuna.Trial, space: BoSpace) -> dict[str, Any]:
    """Muestra hiperparámetros según ``space`` (claves ``type``, ``low``, ``high``)."""
    hp: dict[str, Any] = {}
    for name, spec in space.items():
        kind = spec["type"]
        if kind == "int":
            low, high = int(spec["low"]), int(spec["high"])
            step = int(spec.get("step", 1))
            hp[name] = trial.suggest_int(name, low, high, step=step)
        elif kind == "float":
            low, high = float(spec["low"]), float(spec["high"])
            hp[name] = trial.suggest_float(
                name,
                low,
                high,
                log=bool(spec.get("log", False)),
            )
        else:
            raise ValueError(f"tipo BO desconocido {kind!r} en {name!r}")
    return hp


def hyperparametertuning_meta(bo_space: BoSpace) -> dict[str, Any]:
    """Metadatos del espacio para ``PARAM.yml`` (``bo_space`` + ``limites_fisicos``)."""
    limites: dict[str, dict[str, float]] = {}
    for name, spec in bo_space.items():
        if spec.get("type") == "float":
            limites[name] = {"lower": float(spec["low"]), "upper": float(spec["high"])}
    meta: dict[str, Any] = {"bo_space": {k: dict(v) for k, v in bo_space.items()}}
    if limites:
        meta["limites_fisicos"] = limites
    return meta

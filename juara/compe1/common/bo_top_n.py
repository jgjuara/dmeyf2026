"""Top-N COMPLETE BO trials from ``BO_log.txt`` or ``optuna.db``."""

from __future__ import annotations

from pathlib import Path

import optuna
import polars as pl
import yaml

HP_COLS = (
    "num_iterations",
    "num_leaves",
    "min_data_in_leaf",
    "min_sum_hessian_in_leaf",
)
HIPERPARAMS = HP_COLS

OUTPUT_COLS = ("rank", "y", "iter", *HP_COLS)


def study_name_for_experiment(experiment_id: str) -> str:
    return f"{experiment_id.replace('-', '_')}_temporal_cv_auc"


def resolve_bo_fuente(ht_dir: Path) -> str:
    """``bo_log`` if ``BO_log.txt`` exists, else ``optuna.db``."""
    if (ht_dir / "BO_log.txt").exists():
        return "bo_log"
    if (ht_dir / "optuna.db").exists():
        return "optuna.db"
    raise FileNotFoundError(f"No hay BO_log.txt ni optuna.db en {ht_dir}")


def _min_data_in_leaf_from_param(ht_dir: Path) -> int:
    param_path = ht_dir / "PARAM.yml"
    if not param_path.exists():
        raise FileNotFoundError(f"No existe {param_path}")
    with param_path.open(encoding="utf-8") as f:
        param = yaml.safe_load(f)
    return int(param["lgbm"]["param_fijos"]["min_data_in_leaf"])


def _trials_from_optuna(ht_dir: Path, experiment_id: str, mdil_default: int) -> pl.DataFrame:
    storage = f"sqlite:///{ht_dir / 'optuna.db'}"
    study = optuna.load_study(
        study_name=study_name_for_experiment(experiment_id),
        storage=storage,
    )
    rows: list[dict] = []
    for t in study.trials:
        if t.state != optuna.trial.TrialState.COMPLETE:
            continue
        row = dict(t.params)
        row.setdefault("min_data_in_leaf", mdil_default)
        row["y"] = t.value
        row["iter"] = t.number + 1
        rows.append(row)
    if not rows:
        return pl.DataFrame()
    return pl.DataFrame(rows).sort("y", descending=True)


def _ensure_hp_columns(tb: pl.DataFrame, mdil_default: int) -> pl.DataFrame:
    if "min_data_in_leaf" not in tb.columns:
        tb = tb.with_columns(pl.lit(mdil_default).alias("min_data_in_leaf"))
    return tb


def load_top_n_trials(ht_dir: Path, experiment_id: str, n: int) -> pl.DataFrame:
    """Top ``n`` COMPLETE trials by ``y`` desc, with ``rank`` 1..n."""
    if n < 1:
        raise ValueError(f"n debe ser >= 1, recibido {n}")

    mdil_default = _min_data_in_leaf_from_param(ht_dir)
    fuente = resolve_bo_fuente(ht_dir)

    if fuente == "bo_log":
        tb = pl.read_csv(ht_dir / "BO_log.txt", separator="\t")
    else:
        tb = _trials_from_optuna(ht_dir, experiment_id, mdil_default)

    tb = _ensure_hp_columns(tb, mdil_default)
    if "y" in tb.columns:
        tb = tb.sort("y", descending=True)

    if tb.height < n:
        raise ValueError(
            f"Solo hay {tb.height} trials COMPLETE en {fuente}; se requieren {n}."
        )

    tb = tb.head(n)
    if "rank" in tb.columns:
        tb = tb.drop("rank")
    tb = tb.with_columns(pl.arange(1, n + 1).alias("rank"))

    faltantes = [c for c in HP_COLS if c not in tb.columns]
    if faltantes:
        raise ValueError(f"Trials sin columnas HP: {faltantes}")
    for col in ("y", "iter"):
        if col not in tb.columns:
            raise ValueError(f"Trials sin columna: {col}")

    return tb.select(list(OUTPUT_COLS))


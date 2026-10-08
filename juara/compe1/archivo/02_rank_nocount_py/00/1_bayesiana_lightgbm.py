#!/usr/bin/env python3
"""BO Optuna + CV AUC LightGBM (HT2102, 02_rank_nocount_py)."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import optuna
import polars as pl
import yaml

import _bootstrap  # noqa: F401

from common.bo_space import hyperparametertuning_meta, suggest_params
from common.data import FOTO_MES_MAR_JUN, PARTICION_AGRUPA, feature_matrix, preparar_holdout_split
from common.layers import resultados_dir
from common.lgb_train import cv_best_auc, fixed_params, merge_tuned

EXPERIMENT_ID = "02_rank_nocount_py"
EXPERIMENTO = 2102
SEMILLA_PRIMIGENIA = 427417


def main() -> None:
    res_dir = resultados_dir(EXPERIMENT_ID)
    ht_dir = res_dir / f"HT{EXPERIMENTO}"
    ht_dir.mkdir(parents=True, exist_ok=True)

    n_iter = int(os.environ.get("COMPE1_BO_ITER", "500"))
    undersampling = 0.1
    division = (70, 30)
    fold_train = 1
    fold_test = 2
    cortes = list(range(4000, 19001, 500))

    prep = preparar_holdout_split(
        EXPERIMENT_ID,
        SEMILLA_PRIMIGENIA,
        division=division,
        fold_train=fold_train,
        foto_mes=FOTO_MES_MAR_JUN,
        undersampling=undersampling,
        apply_undersampling=True,
    )
    df: pl.DataFrame = prep["data"]
    campos_buenos = prep["campos_buenos"]

    train_bo = df.filter(
        (pl.col("fold") == fold_train) & (pl.col("training") == 1)
    )
    X = feature_matrix(train_bo, campos_buenos)
    y = train_bo["clase01"].to_numpy()

    fijos = fixed_params(SEMILLA_PRIMIGENIA)
    storage = f"sqlite:///{ht_dir / 'optuna.db'}"
    study = optuna.create_study(
        study_name="ht2102_cv_auc",
        storage=storage,
        load_if_exists=True,
        direction="maximize",
    )

    def objective(trial: optuna.Trial) -> float:
        hp = suggest_params(trial)
        params = merge_tuned(fijos, hp)
        auc = cv_best_auc(X, y, params, nfold=2)
        ts = datetime.now().strftime("%H:%M:%S")
        line = (
            f"[{ts}] trial={trial.number} | AUC={auc:.6f} | "
            f"num_iterations={hp['num_iterations']} num_leaves={hp['num_leaves']} "
            f"min_data_in_leaf={hp['min_data_in_leaf']} "
            f"min_sum_hessian={hp['min_sum_hessian_in_leaf']:.4g}\n"
        )
        print(line, end="", flush=True)
        return auc

    study.optimize(objective, n_trials=n_iter, show_progress_bar=True)

    log_path = ht_dir / "BO_log.txt"

    rows = []
    for t in study.trials:
        if t.state != optuna.trial.TrialState.COMPLETE:
            continue
        row = dict(t.params)
        row["y"] = t.value
        row["iter"] = t.number + 1
        rows.append(row)
    tb = pl.DataFrame(rows).sort("y", descending=True)
    tb.write_csv(log_path, separator="\t")

    best = tb.row(0, named=True)
    hp_cols = [
        c for c in tb.columns if c not in ("y", "iter")
    ]
    mejores = {k: best[k] for k in hp_cols}

    param = {
        "experimento": EXPERIMENTO,
        "experiment_id": EXPERIMENT_ID,
        "semilla_primigenia": SEMILLA_PRIMIGENIA,
        "foto_mes": list(FOTO_MES_MAR_JUN),
        "cortes": cortes,
        "trainingstrategy": {"undersampling": undersampling},
        "holdout": {
            "division": list(division),
            "fold_train": fold_train,
            "fold_test": fold_test,
            "agrupa": list(PARTICION_AGRUPA),
            "n_train": int(df.filter(pl.col("fold") == fold_train).height),
            "n_test": int(df.filter(pl.col("fold") == fold_test).height),
        },
        "lgbm": {"param_fijos": fijos},
        "hypeparametertuning": {
            **hyperparametertuning_meta(),
            "xval_folds": 2,
            "iteraciones": n_iter,
            "objetivo": "cv_auc",
            "optimizer": "optuna",
            "storage": str(ht_dir / "optuna.db"),
        },
        "hyperparametertuning": {
            "xval_folds": 2,
            "iteraciones": n_iter,
            "objetivo": "cv_auc",
        },
        "out": {
            "lgbm": {
                "mejores_hiperparametros": mejores,
                "y": float(best["y"]),
            }
        },
        "campos_buenos": campos_buenos,
    }

    with (ht_dir / "PARAM.yml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(param, f, sort_keys=False, allow_unicode=True)

    print(f"BO finalizada. Mejor AUC={best['y']:.6f} → {ht_dir}")


if __name__ == "__main__":
    main()

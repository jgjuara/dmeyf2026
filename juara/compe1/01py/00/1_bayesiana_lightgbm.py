#!/usr/bin/env python3
"""BO Optuna + CV temporal mar–may (HT1991, 01py, FE completo)."""

from __future__ import annotations

import os
from datetime import datetime

import optuna
import polars as pl
import yaml

import _bootstrap  # noqa: F401

from common.bo_space import hyperparametertuning_meta, suggest_params_00
from common.data import FOTO_MES_MAR_JUN, FOTO_MES_MAR_MAY, preparar_holdout_temporal
from common.gcs_upload import sync_every_trials, sync_resultados_subdir
from common.layers import resultados_dir
from common.lgb_train import fixed_params_00, merge_tuned, temporal_cv_auc_mar_may

EXPERIMENT_ID = "01py"
EXPERIMENTO = 1991
SEMILLA_PRIMIGENIA = 427417


def main() -> None:
    res_dir = resultados_dir(EXPERIMENT_ID)
    ht_dir = res_dir / f"HT{EXPERIMENTO}"
    ht_dir.mkdir(parents=True, exist_ok=True)

    n_iter = int(os.environ.get("COMPE1_BO_ITER", "150"))
    undersampling = 1.0
    fold_train = 1
    fold_test = 2
    cortes = list(range(4000, 19001, 500))

    prep = preparar_holdout_temporal(
        EXPERIMENT_ID,
        foto_mes=FOTO_MES_MAR_JUN,
        fold_train=fold_train,
        fold_test=fold_test,
    )
    df: pl.DataFrame = prep["data"]
    campos_buenos = prep["campos_buenos"]

    train_bo = df.filter(pl.col("fold") == fold_train)

    fijos = fixed_params_00(SEMILLA_PRIMIGENIA)
    mdil_fijo = int(fijos["min_data_in_leaf"])

    storage = f"sqlite:///{ht_dir / 'optuna.db'}"
    study = optuna.create_study(
        study_name="ht1991_temporal_cv_auc",
        storage=storage,
        load_if_exists=True,
        direction="maximize",
    )

    def objective(trial: optuna.Trial) -> float:
        hp = suggest_params_00(trial)
        params = merge_tuned(fijos, hp)
        auc = temporal_cv_auc_mar_may(train_bo, campos_buenos, params)
        ts = datetime.now().strftime("%H:%M:%S")
        line = (
            f"[{ts}] trial={trial.number} | AUC={auc:.6f} | "
            f"num_iterations={hp['num_iterations']} num_leaves={hp['num_leaves']} "
            f"min_sum_hessian={hp['min_sum_hessian_in_leaf']:.4g} "
            f"min_data_in_leaf={mdil_fijo}\n"
        )
        print(line, end="", flush=True)
        return auc

    every = sync_every_trials()

    def gcs_trial_callback(study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
        if (trial.number + 1) % every != 0:
            return
        sync_resultados_subdir(EXPERIMENT_ID, f"HT{EXPERIMENTO}")

    study.optimize(
        objective,
        n_trials=n_iter,
        show_progress_bar=True,
        callbacks=[gcs_trial_callback],
    )

    log_path = ht_dir / "BO_log.txt"
    rows = []
    for t in study.trials:
        if t.state != optuna.trial.TrialState.COMPLETE:
            continue
        row = dict(t.params)
        row.setdefault("min_data_in_leaf", mdil_fijo)
        row["y"] = t.value
        row["iter"] = t.number + 1
        rows.append(row)
    tb = pl.DataFrame(rows).sort("y", descending=True)
    tb.write_csv(log_path, separator="\t")

    best = tb.row(0, named=True)
    hp_cols = [c for c in tb.columns if c not in ("y", "iter")]
    mejores = {k: best[k] for k in hp_cols}

    n_train = int(df.filter(pl.col("fold") == fold_train).height)
    n_test = int(df.filter(pl.col("fold") == fold_test).height)

    param = {
        "experimento": EXPERIMENTO,
        "experiment_id": EXPERIMENT_ID,
        "semilla_primigenia": SEMILLA_PRIMIGENIA,
        "foto_mes": list(FOTO_MES_MAR_JUN),
        "cortes": cortes,
        "trainingstrategy": {
            "undersampling": undersampling,
            "apply_undersampling": False,
        },
        "holdout": {
            "tipo": "temporal_mar_may_jun",
            "foto_mes_train": list(FOTO_MES_MAR_MAY),
            "foto_mes_test": 202106,
            "fold_train": fold_train,
            "fold_test": fold_test,
            "n_train": n_train,
            "n_test": n_test,
        },
        "lgbm": {"param_fijos": fijos},
        "hypeparametertuning": {
            **hyperparametertuning_meta(),
            "xval_folds": 2,
            "iteraciones": n_iter,
            "objetivo": "temporal_cv_auc",
            "optimizer": "optuna",
            "storage": str(ht_dir / "optuna.db"),
        },
        "hyperparametertuning": {
            "xval_folds": 2,
            "iteraciones": n_iter,
            "objetivo": "temporal_cv_auc",
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

    sync_resultados_subdir(EXPERIMENT_ID, f"HT{EXPERIMENTO}")
    print(f"BO finalizada. Mejor AUC={best['y']:.6f} → {ht_dir}")


if __name__ == "__main__":
    main()

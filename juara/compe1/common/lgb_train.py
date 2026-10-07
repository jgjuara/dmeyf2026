"""Entrenamiento y CV LightGBM alineado con compe1 (R)."""

from __future__ import annotations

from typing import Any

import lightgbm as lgb
import numpy as np
import polars as pl

from common.data import FOTO_MES_MAR_MAY, decode_min_sum_hessian, feature_matrix


def fixed_params_00(semilla_primigenia: int = 427417) -> dict[str, Any]:
    return {
        "boosting": "gbdt",
        "objective": "binary",
        "metric": "auc",
        "first_metric_only": False,
        "boost_from_average": True,
        "feature_pre_filter": False,
        "force_row_wise": True,
        "verbosity": -100,
        "seed": semilla_primigenia,
        "max_depth": -1,
        "min_gain_to_split": 0,
        "min_sum_hessian_in_leaf": 0.001,
        "lambda_l1": 0.0,
        "lambda_l2": 0.0,
        "max_bin": 31,
        "bagging_fraction": 1.0,
        "pos_bagging_fraction": 1.0,
        "neg_bagging_fraction": 1.0,
        "is_unbalance": False,
        "scale_pos_weight": 1.0,
        "extra_trees": False,
        "num_iterations": 1200,
        "learning_rate": 0.005,
        "feature_fraction": 0.5,
        "feature_fraction_bynode": 0.20,
        "num_leaves": 750,
        "min_data_in_leaf": 0,
    }


def fixed_params(semilla_primigenia: int = 427417) -> dict[str, Any]:
    return {
        "boosting": "gbdt",
        "objective": "binary",
        "metric": "auc",
        "first_metric_only": False,
        "boost_from_average": True,
        "feature_pre_filter": False,
        "force_row_wise": True,
        "verbosity": -100,
        "seed": semilla_primigenia,
        "max_depth": -1,
        "min_gain_to_split": 0,
        "min_sum_hessian_in_leaf": 0.001,
        "lambda_l1": 0.0,
        "lambda_l2": 0.0,
        "max_bin": 31,
        "bagging_fraction": 1.0,
        "pos_bagging_fraction": 1.0,
        "neg_bagging_fraction": 1.0,
        "is_unbalance": False,
        "scale_pos_weight": 1.0,
        "extra_trees": False,
        "num_iterations": 1200,
        "learning_rate": 0.009,
        "feature_fraction": 0.5,
        "num_leaves": 750,
        "min_data_in_leaf": 5000,
    }


def merge_tuned(fixed: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    out = dict(fixed)
    for k, v in row.items():
        if k in ("y", "iter", "dob", "eol", "error.message", "exec.time"):
            continue
        out[k] = v
    return out


def _lgb_params_for_train(param_completo: dict[str, Any]) -> tuple[dict[str, Any], int]:
    p = dict(param_completo)
    nrounds = int(p.pop("num_iterations", 100))
    return p, nrounds


def auc_holdout_lgb(model: lgb.Booster) -> float:
    evals = model.evals_result_.get("holdout", {}).get("auc")
    if not evals:
        raise ValueError("El modelo no tiene metricas holdout auc")
    return float(max(evals))


def temporal_cv_auc_mar_may(
    df: pl.DataFrame,
    campos_buenos: list[str],
    params: dict[str, Any],
    meses: tuple[int, ...] = FOTO_MES_MAR_MAY,
) -> float:
    if len(meses) != 3:
        raise ValueError("se esperan 3 meses mar-may")
    param_train, nrounds = _lgb_params_for_train(dict(params))
    aucs: list[float] = []
    mes_list = list(meses)
    for k in (1, 2):
        mes_tr = mes_list[:k]
        mes_va = mes_list[k]
        tr = df.filter(pl.col("foto_mes").is_in(mes_tr))
        va = df.filter(pl.col("foto_mes") == mes_va)
        if tr.is_empty() or va.is_empty():
            raise ValueError("fold temporal sin filas")
        X_tr = feature_matrix(tr, campos_buenos)
        y_tr = tr["clase01"].to_numpy()
        X_va = feature_matrix(va, campos_buenos)
        y_va = va["clase01"].to_numpy()
        dtrain = lgb.Dataset(X_tr, label=y_tr, free_raw_data=False)
        dvalid = lgb.Dataset(X_va, label=y_va, free_raw_data=False)
        model = lgb.train(
            param_train,
            dtrain,
            num_boost_round=nrounds,
            valid_sets=[dvalid],
            valid_names=["holdout"],
        )
        aucs.append(auc_holdout_lgb(model))
    return float(np.mean(aucs))


def cv_best_auc(
    X: np.ndarray,
    y: np.ndarray,
    params: dict[str, Any],
    nfold: int = 2,
) -> float:
    param_train, nrounds = _lgb_params_for_train(params)
    dtrain = lgb.Dataset(X, label=y, free_raw_data=False)
    cv = lgb.cv(
        param_train,
        dtrain,
        num_boost_round=nrounds,
        nfold=nfold,
        stratified=True,
        seed=int(params.get("seed", 0)),
    )
    key = next(iter(cv))
    return float(max(cv[key]))


def train_full(
    X: np.ndarray,
    y: np.ndarray,
    params: dict[str, Any],
    seed: int | None = None,
) -> lgb.Booster:
    p = dict(params)
    if seed is not None:
        p["seed"] = seed
    param_train, nrounds = _lgb_params_for_train(p)
    dtrain = lgb.Dataset(X, label=y)
    return lgb.train(param_train, dtrain, num_boost_round=nrounds)


def production_params(
    param_yaml: dict,
    hp_row: dict,
    undersampling: float,
) -> dict[str, Any]:
    fixed = param_yaml["lgbm"]["param_fijos"]
    merged = merge_tuned(fixed, hp_row)
    merged = decode_min_sum_hessian(merged, limits=(0.001, 0.01))
    merged = dict(merged)
    merged["min_data_in_leaf"] = int(
        round(float(merged["min_data_in_leaf"]) / undersampling)
    )
    return merged

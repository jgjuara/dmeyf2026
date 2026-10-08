#!/usr/bin/env python3
"""Entrenamiento final LightGBM y evaluación holdout junio (exp1991, 01py)."""

from __future__ import annotations

import polars as pl
import yaml

import _bootstrap  # noqa: F401

from common.cortes import write_cortes_ganancia
from common.data import feature_matrix, preparar_holdout_desde_param
from common.layers import resultados_dir
from common.lgb_train import production_params, train_full
from common.plots import write_gain_curve_pdf

EXPERIMENT_ID = "01py"
EXPERIMENTO = 1991


def main() -> None:
    res_dir = resultados_dir(EXPERIMENT_ID)
    ht_dir = res_dir / f"HT{EXPERIMENTO}"
    prod_dir = res_dir / f"exp{EXPERIMENTO}"
    prod_dir.mkdir(parents=True, exist_ok=True)

    with (ht_dir / "PARAM.yml").open(encoding="utf-8") as f:
        param = yaml.safe_load(f)

    campos_buenos = list(param["campos_buenos"])
    fold_train = int(param["holdout"]["fold_train"])
    fold_test = int(param["holdout"]["fold_test"])
    undersampling = float(param["trainingstrategy"]["undersampling"])
    cortes = [int(x) for x in param["cortes"]]

    prep = preparar_holdout_desde_param(EXPERIMENT_ID, param)
    df = prep["data"]

    train_df = df.filter(pl.col("fold") == fold_train)
    test_df = df.filter(pl.col("fold") == fold_test)

    hp = param["out"]["lgbm"]["mejores_hiperparametros"]
    params = production_params(param, hp, undersampling)

    X_train = feature_matrix(train_df, campos_buenos)
    y_train = train_df["clase01"].to_numpy()
    model = train_full(X_train, y_train, params)

    imp = pl.DataFrame(
        {
            "Feature": model.feature_name(),
            "Gain": model.feature_importance(importance_type="gain"),
        }
    ).sort("Gain", descending=True)
    imp.write_csv(prod_dir / "impo.txt", separator="\t")

    X_test = feature_matrix(test_df, campos_buenos)
    pred = model.predict(X_test)

    pred_df = test_df.select("numero_de_cliente", "foto_mes", "clase_ternaria").with_columns(
        pl.Series("prob", pred)
    )
    pred_df.select("numero_de_cliente", "foto_mes", "prob").write_csv(
        prod_dir / "prediccion.txt", separator="\t"
    )

    write_gain_curve_pdf(pred_df, prod_dir / "curva_ganancia.pdf")
    tb_sorted = pred_df.sort("prob", descending=True)
    write_cortes_ganancia(tb_sorted, prod_dir / "cortes_ganancia.txt", cortes)

    with (prod_dir / "PARAM.yml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(param, f, sort_keys=False, allow_unicode=True)

    print(f"Producción escrita en {prod_dir}")


if __name__ == "__main__":
    main()

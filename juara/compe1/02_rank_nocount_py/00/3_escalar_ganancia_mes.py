#!/usr/bin/env python3
"""Escala ganancia del test 30% a mes completo; promedio mar–jun."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import yaml

import _bootstrap  # noqa: F401

from common.data import escalar_ganancia_mes, ganancia_envio, preparar_holdout_split
from common.layers import resultados_dir

EXPERIMENT_ID = "02_rank_nocount_py"
EXPERIMENTO = 2102


def main() -> None:
    res_dir = resultados_dir(EXPERIMENT_ID)
    prod_dir = res_dir / f"exp{EXPERIMENTO}"
    param_path = prod_dir / "PARAM.yml"
    if not param_path.exists():
        param_path = res_dir / f"HT{EXPERIMENTO}" / "PARAM.yml"
    with param_path.open(encoding="utf-8") as f:
        param = yaml.safe_load(f)

    holdout = param["holdout"]
    fold_test = int(holdout["fold_test"])
    division = tuple(int(x) for x in holdout["division"])
    fold_train = int(holdout["fold_train"])
    foto_mes = tuple(int(x) for x in param["foto_mes"])
    cortes = [int(x) for x in param["cortes"]]

    prep = preparar_holdout_split(
        EXPERIMENT_ID,
        int(param["semilla_primigenia"]),
        division=division,
        fold_train=fold_train,
        foto_mes=foto_mes,
        apply_undersampling=False,
    )
    df = prep["data"]
    pred = pl.read_csv(prod_dir / "prediccion.txt", separator="\t")

    test_df = df.filter(pl.col("fold") == fold_test).join(
        pred, on=["numero_de_cliente", "foto_mes"], how="left"
    )
    if test_df["prob"].null_count() > 0:
        raise ValueError("prediccion.txt no alinea con el holdout test")

    conteos = df.group_by("foto_mes").agg(pl.len().alias("n_total"))
    conteos_test = test_df.group_by("foto_mes").agg(pl.len().alias("n_test"))
    conteos = conteos.join(conteos_test, on="foto_mes", how="left").with_columns(
        pl.col("n_test").fill_null(0)
    )

    meses = sorted(test_df["foto_mes"].unique().to_list())
    filas = []
    for mes in meses:
        dm = test_df.filter(pl.col("foto_mes") == mes)
        row_c = conteos.filter(pl.col("foto_mes") == mes).row(0, named=True)
        n_test = int(row_c["n_test"])
        n_total = int(row_c["n_total"])
        for envios in cortes:
            gan_obs = ganancia_envio(dm, envios)
            gan_esc = escalar_ganancia_mes(gan_obs, n_test, n_total)
            filas.append(
                {
                    "foto_mes": mes,
                    "envios": envios,
                    "gan_obs": gan_obs,
                    "n_test": n_test,
                    "n_total": n_total,
                    "gan_escalada_mes": gan_esc,
                }
            )

    tb_detalle = pl.DataFrame(filas)
    tb_detalle.write_csv(
        prod_dir / "cortes_ganancia_por_mes_escalada.tsv", separator="\t"
    )

    tb_prom = (
        tb_detalle.group_by("envios")
        .agg(pl.col("gan_escalada_mes").mean().alias("gan_promedio_mes"))
        .sort("envios")
    )

    lines = []
    for row in tb_prom.iter_rows(named=True):
        lines.append(
            f"Envios={row['envios']}\t TOTAL={row['gan_promedio_mes']}"
        )
    (prod_dir / "cortes_ganancia_escalada_promedio_mes.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(f"Escalado escrito en {prod_dir}")


if __name__ == "__main__":
    main()

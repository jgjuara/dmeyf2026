#!/usr/bin/env python3
"""Train mar–jun, predict agosto; media rank×semilla (exp1991_agosto, 01py)."""

from __future__ import annotations

import numpy as np
import polars as pl
import yaml

import _bootstrap  # noqa: F401

from common.data import FOTO_MES_MAR_JUN, feature_matrix, read_joined
from common.gcs_upload import sync_resultados_subdir
from common.layers import resultados_dir
from common.lgb_train import decode_min_sum_hessian, merge_tuned, train_full
from common.partition import semillas_primos

EXPERIMENT_ID = "01py"
EXPERIMENTO = 1991
N_SEMILLAS_PRIMOS = 10
RANKS_BO = (3,)
FOTO_MES_PRED = 202108


def foto_mes_a_aniomesdia(foto_mes: int) -> str:
    return f"{foto_mes // 100}{foto_mes % 100:02d}01"


def nombre_tsv_modelo_semilla(rank_id: int, semilla: int, aniomesdia: str) -> str:
    return f"modelo_{rank_id:02d}_{semilla}_{aniomesdia}.tsv"


def main() -> None:
    res_dir = resultados_dir(EXPERIMENT_ID)
    ht_dir = res_dir / f"HT{EXPERIMENTO}"
    top20_estudio = res_dir / "estudio" / "top20_bo_semillas"
    out_dir = res_dir / f"exp{EXPERIMENTO}_agosto"
    out_dir.mkdir(parents=True, exist_ok=True)

    with (ht_dir / "PARAM.yml").open(encoding="utf-8") as f:
        param = yaml.safe_load(f)

    campos_buenos = list(param["campos_buenos"])
    hiperparams = (
        "num_iterations",
        "num_leaves",
        "min_data_in_leaf",
        "min_sum_hessian_in_leaf",
    )

    top20_meta = top20_estudio / "top20_hiperparametros.tsv"
    bo_log = ht_dir / "BO_log.txt"
    if top20_meta.exists():
        tb_top20 = pl.read_csv(top20_meta, separator="\t")
    elif bo_log.exists():
        tb_top20 = pl.read_csv(bo_log, separator="\t").head(20)
        tb_top20 = tb_top20.with_columns(pl.arange(1, tb_top20.height + 1).alias("rank"))
    else:
        raise FileNotFoundError(f"No existe {top20_meta} ni {bo_log}")

    faltantes = [c for c in ("rank", *hiperparams) if c not in tb_top20.columns]
    if faltantes:
        raise ValueError(f"tabla top-20 sin columnas: {faltantes}")

    ranks_usar = list(RANKS_BO)
    tb_ranks = tb_top20.filter(pl.col("rank").is_in(ranks_usar))
    if tb_ranks.height != len(ranks_usar):
        raise ValueError(f"RANKS_BO fuera de rango: {ranks_usar}")

    semillas = semillas_primos(N_SEMILLAS_PRIMOS, int(param["semilla_primigenia"]))
    print("RANKS_BO:", ", ".join(str(r) for r in ranks_usar))
    print("semillas_train:", ", ".join(str(s) for s in semillas))

    aniomesdia = foto_mes_a_aniomesdia(FOTO_MES_PRED)
    meses_leer = tuple(sorted(set(FOTO_MES_MAR_JUN) | {FOTO_MES_PRED}))
    dataset = read_joined(EXPERIMENT_ID, foto_mes=meses_leer)

    train_df = dataset.filter(pl.col("foto_mes").is_in(list(FOTO_MES_MAR_JUN)))
    train_df = train_df.with_columns(
        pl.when(pl.col("clase_ternaria").is_in(["BAJA+1", "BAJA+2"]))
        .then(1)
        .otherwise(0)
        .alias("clase01")
    )
    agosto_df = dataset.filter(pl.col("foto_mes") == FOTO_MES_PRED)
    if agosto_df.is_empty():
        raise ValueError(f"Sin filas para foto_mes={FOTO_MES_PRED}")

    n_train = train_df.height
    n_agosto = agosto_df.height
    print(f"train filas={n_train} | agosto filas={n_agosto}")

    undersampling = float(param["trainingstrategy"]["undersampling"])
    fixed = param["lgbm"]["param_fijos"]

    prob_sum = np.zeros(n_agosto, dtype=np.float64)
    n_modelos = 0

    X_tr = feature_matrix(train_df, campos_buenos)
    y_tr = train_df["clase01"].to_numpy()
    X_ag = feature_matrix(agosto_df, campos_buenos)

    for row in tb_ranks.iter_rows(named=True):
        rank_id = int(row["rank"])
        hp = {k: row[k] for k in hiperparams}
        param_final = decode_min_sum_hessian(merge_tuned(fixed, hp))
        print(f"\n=== rank_{rank_id:02d} ===")

        for primo in semillas:
            pnorm = dict(param_final)
            pnorm["min_data_in_leaf"] = int(
                round(float(param_final["min_data_in_leaf"]) / undersampling)
            )
            pnorm["seed"] = primo

            model = train_full(X_tr, y_tr, pnorm, seed=primo)
            pred = model.predict(X_ag)
            n_modelos += 1
            prob_sum += pred

            tb_piece = agosto_df.select("numero_de_cliente", "foto_mes").with_columns(
                pl.Series("prob", pred)
            )
            tb_piece.write_csv(
                out_dir / nombre_tsv_modelo_semilla(rank_id, primo, aniomesdia),
                separator="\t",
            )

    esperado = tb_ranks.height * len(semillas)
    if n_modelos != esperado:
        raise ValueError(f"Conteo de modelos inconsistente: {n_modelos} esperado={esperado}")

    tb_media = agosto_df.select("numero_de_cliente", "foto_mes").with_columns(
        (prob_sum / n_modelos).alias("prob")
    )
    tb_media.write_csv(out_dir / "prediccion_agosto_media.tsv", separator="\t")

    tb_ordenada = tb_media.sort("prob", descending=True).with_columns(
        pl.arange(1, tb_media.height + 1).alias("orden")
    )
    tb_ordenada.write_csv(out_dir / "prediccion_agosto_media_ordenada.tsv", separator="\t")

    meta = {
        "experiment_id": EXPERIMENT_ID,
        "experimento": EXPERIMENTO,
        "ranks_bo": list(ranks_usar),
        "n_semillas_primos": N_SEMILLAS_PRIMOS,
        "semillas_train": semillas,
        "foto_mes_train": list(FOTO_MES_MAR_JUN),
        "foto_mes_pred": FOTO_MES_PRED,
        "aniomesdia_pred": aniomesdia,
        "prediccion_tsv_patron": "modelo_%02d_<semilla>_<aniomesdia>.tsv",
        "n_train": n_train,
        "n_agosto": n_agosto,
        "n_predicciones_agregadas": tb_media.height,
    }
    with (out_dir / "meta.yml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(meta, f, sort_keys=False, allow_unicode=True)

    sync_resultados_subdir(EXPERIMENT_ID, f"exp{EXPERIMENTO}_agosto")
    print(f"\nFinalizado en {out_dir}")


if __name__ == "__main__":
    main()

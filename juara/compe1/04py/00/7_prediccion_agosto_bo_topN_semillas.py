#!/usr/bin/env python3
"""Mar–jun → agosto: top-N BO × 10 semillas primo, sin holdout junio (04py)."""

from __future__ import annotations

import os

import numpy as np
import polars as pl
import yaml

import _bootstrap  # noqa: F401
from _bootstrap import EXPERIMENT_ID

from common.agosto_artifacts import (
    MODELO_LGB_PATRON,
    PREDICCION_TSV_PATRON,
    foto_mes_a_aniomesdia,
    persist_model_and_upload,
    persist_pred_tsv_and_upload,
)
from common.bo_top_n import HP_COLS, load_top_n_trials, resolve_bo_fuente
from common.data import FOTO_MES_MAR_JUN, feature_matrix, read_joined
from common.gcs_upload import pull_resultados_subdir, sync_resultados_subdir
from common.layers import (
    SUBDIR_AGOSTO,
    SUBDIR_BO,
    agosto_dir,
    assert_param_experiment_id,
    bo_dir,
)
from common.lgb_train import decode_min_sum_hessian, merge_tuned, train_full
from common.partition import semillas_primos

N_SEMILLAS_PRIMOS = 10
FOTO_MES_PRED = 202108


def main() -> None:
    n_top = int(os.environ.get("COMPE1_BO_TOP_N", "10"))
    ht_dir = bo_dir(EXPERIMENT_ID)
    out_dir = agosto_dir(EXPERIMENT_ID)
    out_dir.mkdir(parents=True, exist_ok=True)

    pull_resultados_subdir(EXPERIMENT_ID, SUBDIR_BO)

    with (ht_dir / "PARAM.yml").open(encoding="utf-8") as f:
        param = yaml.safe_load(f)
    assert_param_experiment_id(param, EXPERIMENT_ID)

    fuente = resolve_bo_fuente(ht_dir)
    tb_ranks = load_top_n_trials(ht_dir, EXPERIMENT_ID, n_top)
    ranks_usar = tb_ranks["rank"].to_list()

    semillas = semillas_primos(N_SEMILLAS_PRIMOS, int(param["semilla_primigenia"]))
    print(f"COMPE1_BO_TOP_N={n_top} | fuente={fuente}")
    print("ranks:", ", ".join(str(r) for r in ranks_usar))
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

    X_tr = feature_matrix(train_df, list(param["campos_buenos"]))
    y_tr = train_df["clase01"].to_numpy()
    X_ag = feature_matrix(agosto_df, list(param["campos_buenos"]))

    for row in tb_ranks.iter_rows(named=True):
        rank_id = int(row["rank"])
        hp = {k: row[k] for k in HP_COLS}
        param_final = decode_min_sum_hessian(merge_tuned(fixed, hp))
        print(f"\n=== rank_{rank_id:02d} ===")

        for primo in semillas:
            pnorm = dict(param_final)
            pnorm["min_data_in_leaf"] = int(
                round(float(param_final["min_data_in_leaf"]) / undersampling)
            )
            pnorm["seed"] = primo

            model = train_full(X_tr, y_tr, pnorm, seed=primo)
            persist_model_and_upload(model, out_dir, EXPERIMENT_ID, rank_id, primo)
            pred = model.predict(X_ag)
            n_modelos += 1
            prob_sum += pred

            tb_piece = agosto_df.select("numero_de_cliente", "foto_mes").with_columns(
                pl.Series("prob", pred)
            )
            persist_pred_tsv_and_upload(
                tb_piece, out_dir, EXPERIMENT_ID, rank_id, primo, aniomesdia
            )

    esperado = tb_ranks.height * len(semillas)
    if n_modelos != esperado:
        raise ValueError(f"Conteo de modelos inconsistente: {n_modelos} esperado={esperado}")

    media_name = f"prediccion_agosto_media_top{n_top}_bo.tsv"
    media_ord_name = f"prediccion_agosto_media_top{n_top}_bo_ordenada.tsv"
    tb_media = agosto_df.select("numero_de_cliente", "foto_mes").with_columns(
        (prob_sum / n_modelos).alias("prob")
    )
    tb_media.write_csv(out_dir / media_name, separator="\t")

    tb_ordenada = tb_media.sort("prob", descending=True).with_columns(
        pl.arange(1, tb_media.height + 1).alias("orden")
    )
    tb_ordenada.write_csv(out_dir / media_ord_name, separator="\t")

    meta = {
        "experiment_id": EXPERIMENT_ID,
        "compe1_bo_top_n": n_top,
        "fuente": fuente,
        "ranks": ranks_usar,
        "n_semillas_primos": N_SEMILLAS_PRIMOS,
        "semillas": semillas,
        "foto_mes_train": list(FOTO_MES_MAR_JUN),
        "foto_mes_pred": FOTO_MES_PRED,
        "aniomesdia_pred": aniomesdia,
        "modelo_lgb_patron": MODELO_LGB_PATRON,
        "prediccion_tsv_patron": PREDICCION_TSV_PATRON,
        "n_train": n_train,
        "n_agosto": n_agosto,
        "n_predicciones_agregadas": tb_media.height,
        "n_modelos": n_modelos,
    }
    meta_path = out_dir / f"meta_top{n_top}_bo.yml"
    with meta_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(meta, f, sort_keys=False, allow_unicode=True)

    sync_resultados_subdir(EXPERIMENT_ID, SUBDIR_AGOSTO)
    print(f"\nFinalizado en {out_dir}")


if __name__ == "__main__":
    main()

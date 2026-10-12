#!/usr/bin/env python3
"""Train mar–jun, predict agosto; media rank×semilla (04py)."""

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
from common.data import FOTO_MES_MAR_JUN, feature_matrix, read_joined
from common.gcs_upload import pull_resultados_subdir, sync_resultados_subdir
from pathlib import Path

from common.layers import (
    SUBDIR_AGOSTO,
    SUBDIR_BO,
    agosto_dir,
    assert_param_experiment_id,
    bo_dir,
    resultados_dir,
)
from common.lgb_train import decode_min_sum_hessian, merge_tuned, train_full
from common.partition import semillas_primos

N_SEMILLAS_PRIMOS_DEFAULT = 10
RANKS_BO_DEFAULT = (3,)
FOTO_MES_PRED = 202108


def _ranks_desde_env_o_ganador(ganador_path: Path) -> list[int]:
    raw = os.environ.get("COMPE1_AGOSTO_RANKS", "").strip()
    if raw:
        return [int(x.strip()) for x in raw.split(",") if x.strip()]
    if ganador_path.exists():
        with ganador_path.open(encoding="utf-8") as f:
            ganador = yaml.safe_load(f) or {}
        rank_ganador = ganador.get("rank_ganador")
        if rank_ganador is not None:
            return [int(rank_ganador)]
    return list(RANKS_BO_DEFAULT)


def main() -> None:
    res_dir = resultados_dir(EXPERIMENT_ID)
    ht_dir = bo_dir(EXPERIMENT_ID)
    top20_estudio = res_dir / "estudio" / "top20_bo_semillas"
    out_dir = agosto_dir(EXPERIMENT_ID)
    out_dir.mkdir(parents=True, exist_ok=True)

    pull_resultados_subdir(EXPERIMENT_ID, SUBDIR_BO)
    pull_resultados_subdir(EXPERIMENT_ID, "estudio/top20_bo_semillas")

    with (ht_dir / "PARAM.yml").open(encoding="utf-8") as f:
        param = yaml.safe_load(f)
    assert_param_experiment_id(param, EXPERIMENT_ID)

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

    ganador_path = top20_estudio / "ganador.yml"
    ranks_usar = _ranks_desde_env_o_ganador(ganador_path)
    tb_ranks = tb_top20.filter(pl.col("rank").is_in(ranks_usar))
    if tb_ranks.height != len(ranks_usar):
        raise ValueError(f"Ranks BO fuera de rango: {ranks_usar}")

    n_semillas = int(
        os.environ.get("COMPE1_N_SEMILLAS_PRIMOS", N_SEMILLAS_PRIMOS_DEFAULT)
    )
    semillas = semillas_primos(n_semillas, int(param["semilla_primigenia"]))
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
        "ranks_bo": list(ranks_usar),
        "n_semillas_primos": n_semillas,
        "semillas_train": semillas,
        "foto_mes_train": list(FOTO_MES_MAR_JUN),
        "foto_mes_pred": FOTO_MES_PRED,
        "aniomesdia_pred": aniomesdia,
        "modelo_lgb_patron": MODELO_LGB_PATRON,
        "prediccion_tsv_patron": PREDICCION_TSV_PATRON,
        "n_train": n_train,
        "n_agosto": n_agosto,
        "n_predicciones_agregadas": tb_media.height,
    }
    with (out_dir / "meta.yml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(meta, f, sort_keys=False, allow_unicode=True)

    sync_resultados_subdir(EXPERIMENT_ID, SUBDIR_AGOSTO)
    print(f"\nFinalizado en {out_dir}")


if __name__ == "__main__":
    main()

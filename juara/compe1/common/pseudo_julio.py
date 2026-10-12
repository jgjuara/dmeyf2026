"""Pseudo-etiquetado de julio y predicción agosto con train mar–jul."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import polars as pl
import yaml

from common.agosto_artifacts import (
    MODELO_LGB_PATRON,
    PREDICCION_TSV_PATRON,
    foto_mes_a_aniomesdia,
    persist_model_and_upload,
    persist_pred_tsv_and_upload,
)
from common.data import (
    BAJA_TERNARIA,
    FOTO_MES_JUL,
    FOTO_MES_MAR_JUL,
    FOTO_MES_MAR_JUN,
    JOIN_KEYS,
    feature_matrix,
    read_joined,
    with_clase01_observada,
)
from common.gcs_upload import pull_resultados_subdir, sync_resultados_subdir
from common.layers import (
    SUBDIR_AGOSTO_MAR_JUL,
    SUBDIR_BO,
    SUBDIR_JULIO_PSEUDO,
    assert_param_experiment_id,
    agosto_mar_jul_dir,
    bo_dir,
    julio_pseudo_dir,
    resultados_dir,
)
from common.lgb_train import decode_min_sum_hessian, merge_tuned, train_full
from common.partition import semillas_primos

N_SEMILLAS_PRIMOS = 10
RANKS_BO_FALLBACK = (3,)
FOTO_MES_AGO = 202108
HIPERPARAM_COLS = (
    "num_iterations",
    "num_leaves",
    "min_data_in_leaf",
    "min_sum_hessian_in_leaf",
)
TOP20_ESTUDIO_REL = "estudio/top20_bo_semillas"


def load_top20_ranks(
    experiment_id: str,
    ranks_fallback: tuple[int, ...] = RANKS_BO_FALLBACK,
) -> tuple[list[str], pl.DataFrame, list[int], list[int], dict]:
    """Carga PARAM, tabla top-20 y ranks/semillas a usar (misma lógica que script 6)."""
    res_dir = resultados_dir(experiment_id)
    ht_dir = bo_dir(experiment_id)
    top20_estudio = res_dir / TOP20_ESTUDIO_REL

    with (ht_dir / "PARAM.yml").open(encoding="utf-8") as f:
        param = yaml.safe_load(f)
    assert_param_experiment_id(param, experiment_id)

    campos_buenos = list(param["campos_buenos"])
    top20_meta = top20_estudio / "top20_hiperparametros.tsv"
    bo_log = ht_dir / "BO_log.txt"
    if top20_meta.exists():
        tb_top20 = pl.read_csv(top20_meta, separator="\t")
    elif bo_log.exists():
        tb_top20 = pl.read_csv(bo_log, separator="\t").head(20)
        tb_top20 = tb_top20.with_columns(pl.arange(1, tb_top20.height + 1).alias("rank"))
    else:
        raise FileNotFoundError(f"No existe {top20_meta} ni {bo_log}")

    faltantes = [c for c in ("rank", *HIPERPARAM_COLS) if c not in tb_top20.columns]
    if faltantes:
        raise ValueError(f"tabla top-20 sin columnas: {faltantes}")

    ganador_path = top20_estudio / "ganador.yml"
    if ganador_path.exists():
        with ganador_path.open(encoding="utf-8") as f:
            ganador = yaml.safe_load(f) or {}
        rank_ganador = ganador.get("rank_ganador")
        ranks_usar = [int(rank_ganador)] if rank_ganador is not None else list(ranks_fallback)
    else:
        ranks_usar = list(ranks_fallback)

    tb_ranks = tb_top20.filter(pl.col("rank").is_in(ranks_usar))
    if tb_ranks.height != len(ranks_usar):
        raise ValueError(f"ranks fuera de rango: {ranks_usar}")

    semillas = semillas_primos(N_SEMILLAS_PRIMOS, int(param["semilla_primigenia"]))
    return campos_buenos, tb_ranks, ranks_usar, semillas, param


def mean_positive_rate_mar_jun(df: pl.DataFrame) -> float:
    """Media mensual de (BAJA+1+BAJA+2)/n_filas en mar–jun."""
    tasas: list[float] = []
    for mes in FOTO_MES_MAR_JUN:
        slice_m = df.filter(pl.col("foto_mes") == mes)
        n = slice_m.height
        if n <= 0:
            continue
        n_pos = slice_m.filter(pl.col("clase_ternaria").is_in(list(BAJA_TERNARIA))).height
        tasas.append(n_pos / n)
    if not tasas:
        raise ValueError("sin filas mar–jun para tasa de positivos")
    return float(sum(tasas) / len(tasas))


def impute_clase01_julio(
    julio_df: pl.DataFrame,
    prob_media: np.ndarray,
    tasa_objetivo: float,
) -> tuple[pl.DataFrame, dict]:
    """Imputa clase01 en julio: BAJA+1 observado; resto por ranking de prob_media."""
    if julio_df.height != len(prob_media):
        raise ValueError("julio_df y prob_media con distinta longitud")

    n_julio = julio_df.height
    n_obj = int(round(tasa_objetivo * n_julio))

    base = julio_df.with_columns(pl.Series("prob_media", prob_media.astype(np.float64)))
    es_baja1 = pl.col("clase_ternaria") == "BAJA+1"
    n_obs_baja1 = base.filter(es_baja1).height
    n_imputar_pos = max(0, n_obj - n_obs_baja1)

    pool = base.filter(pl.col("clase_ternaria").is_null()).sort("prob_media", descending=True)
    pool = pool.with_row_index("_pool_ix")
    pool = pool.with_columns(
        pl.when(pl.col("_pool_ix") < n_imputar_pos)
        .then(1)
        .otherwise(0)
        .alias("clase01_imput")
    )

    merged = base.join(
        pool.select(*JOIN_KEYS, "clase01_imput"),
        on=list(JOIN_KEYS),
        how="left",
    )

    out = merged.with_columns(
        pl.when(es_baja1)
        .then(1)
        .when(pl.col("clase01_imput").is_not_null())
        .then(pl.col("clase01_imput"))
        .otherwise(
            pl.when(pl.col("clase_ternaria").is_in(list(BAJA_TERNARIA)))
            .then(1)
            .otherwise(0)
        )
        .alias("clase01"),
        pl.when(es_baja1)
        .then(pl.lit("observado"))
        .when(pl.col("clase01_imput").is_not_null())
        .then(pl.lit("imputado"))
        .otherwise(pl.lit("observado"))
        .alias("origen"),
    ).drop("clase01_imput")

    n_imputado_pos = out.filter((pl.col("origen") == "imputado") & (pl.col("clase01") == 1)).height
    n_clase01_1 = out.filter(pl.col("clase01") == 1).height
    tasa_global = n_clase01_1 / n_julio if n_julio else 0.0

    n_baja1 = out.filter(pl.col("clase_ternaria") == "BAJA+1").height
    recall_top_k: dict[str, float] = {}
    if n_baja1 > 0:
        ordenada = out.sort("prob_media", descending=True)
        for k in (100, 500, 1000, n_julio):
            top_k = ordenada.head(min(k, n_julio))
            hit = top_k.filter(pl.col("clase_ternaria") == "BAJA+1").height
            recall_top_k[f"recall_baja1_top_{k}"] = hit / n_baja1

    auditoria = {
        "tasa_mar_jun_mean": tasa_objetivo,
        "n_julio": n_julio,
        "n_obj_clase01_1": n_obj,
        "n_observado_baja1": n_obs_baja1,
        "n_imputado_pos": n_imputado_pos,
        "n_clase01_1": n_clase01_1,
        "tasa_global_clase01": tasa_global,
        "prevalencia_modo": os.environ.get("COMPE1_JULIO_PSEUDO_PREVALENCIA", "mar_jun_mean"),
        **recall_top_k,
    }
    cols_out = [*JOIN_KEYS, "clase_ternaria", "prob_media", "clase01", "origen"]
    return out.select(cols_out), auditoria


def _train_predict_loop(
    train_df: pl.DataFrame,
    pred_df: pl.DataFrame,
    campos_buenos: list[str],
    tb_ranks: pl.DataFrame,
    semillas: list[int],
    param: dict,
    *,
    persist_models: bool,
    out_dir: Path | None,
    experiment_id: str,
    aniomesdia: str,
    subdir_upload: str | None,
) -> tuple[np.ndarray, int]:
    undersampling = float(param["trainingstrategy"]["undersampling"])
    fixed = param["lgbm"]["param_fijos"]
    n_pred = pred_df.height
    prob_sum = np.zeros(n_pred, dtype=np.float64)
    n_modelos = 0

    X_tr = feature_matrix(train_df, campos_buenos)
    y_tr = train_df["clase01"].to_numpy()
    X_pr = feature_matrix(pred_df, campos_buenos)

    for row in tb_ranks.iter_rows(named=True):
        rank_id = int(row["rank"])
        hp = {k: row[k] for k in HIPERPARAM_COLS}
        param_final = decode_min_sum_hessian(merge_tuned(fixed, hp))
        print(f"\n=== rank_{rank_id:02d} ===")

        for primo in semillas:
            pnorm = dict(param_final)
            pnorm["min_data_in_leaf"] = int(
                round(float(param_final["min_data_in_leaf"]) / undersampling)
            )
            pnorm["seed"] = primo

            model = train_full(X_tr, y_tr, pnorm, seed=primo)
            n_modelos += 1
            prob_sum += model.predict(X_pr)

            if persist_models and out_dir is not None and subdir_upload is not None:
                persist_model_and_upload(
                    model, out_dir, experiment_id, rank_id, primo, subdir=subdir_upload
                )
                tb_piece = pred_df.select("numero_de_cliente", "foto_mes").with_columns(
                    pl.Series("prob", model.predict(X_pr))
                )
                persist_pred_tsv_and_upload(
                    tb_piece,
                    out_dir,
                    experiment_id,
                    rank_id,
                    primo,
                    aniomesdia,
                    subdir=subdir_upload,
                )

    esperado = tb_ranks.height * len(semillas)
    if n_modelos != esperado:
        raise ValueError(f"Conteo de modelos inconsistente: {n_modelos} esperado={esperado}")
    return prob_sum, n_modelos


def main_fase_julio_imputacion(experiment_id: str) -> None:
    prevalencia_modo = os.environ.get("COMPE1_JULIO_PSEUDO_PREVALENCIA", "mar_jun_mean")
    if prevalencia_modo != "mar_jun_mean":
        raise ValueError(
            f"COMPE1_JULIO_PSEUDO_PREVALENCIA no soportado: {prevalencia_modo}"
        )

    pull_resultados_subdir(experiment_id, SUBDIR_BO)
    pull_resultados_subdir(experiment_id, TOP20_ESTUDIO_REL)

    campos_buenos, tb_ranks, ranks_usar, semillas, param = load_top20_ranks(experiment_id)
    out_dir = julio_pseudo_dir(experiment_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("RANKS:", ", ".join(str(r) for r in ranks_usar))
    print("semillas_train:", ", ".join(str(s) for s in semillas))

    meses_leer = tuple(sorted(set(FOTO_MES_MAR_JUN) | {FOTO_MES_JUL}))
    dataset = read_joined(experiment_id, foto_mes=meses_leer)
    train_df = with_clase01_observada(
        dataset.filter(pl.col("foto_mes").is_in(list(FOTO_MES_MAR_JUN)))
    )
    julio_df = dataset.filter(pl.col("foto_mes") == FOTO_MES_JUL)
    if julio_df.is_empty():
        raise ValueError(f"Sin filas para foto_mes={FOTO_MES_JUL}")

    tasa = mean_positive_rate_mar_jun(train_df)
    print(f"train filas={train_df.height} | julio filas={julio_df.height} | tasa_mar_jun={tasa:.6f}")

    prob_sum, n_modelos = _train_predict_loop(
        train_df,
        julio_df,
        campos_buenos,
        tb_ranks,
        semillas,
        param,
        persist_models=False,
        out_dir=None,
        experiment_id=experiment_id,
        aniomesdia=foto_mes_a_aniomesdia(FOTO_MES_JUL),
        subdir_upload=None,
    )
    prob_media = prob_sum / n_modelos

    tb_media = julio_df.select("numero_de_cliente", "foto_mes").with_columns(
        pl.Series("prob", prob_media)
    )
    tb_media.write_csv(out_dir / "prediccion_julio_media.tsv", separator="\t")

    imputado, auditoria = impute_clase01_julio(julio_df, prob_media, tasa)
    imputado.write_parquet(out_dir / "clase01_imputado.parquet")

    with (out_dir / "auditoria_imputacion.yml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(auditoria, f, sort_keys=False, allow_unicode=True)

    meta = {
        "experiment_id": experiment_id,
        "fase": "julio_imputacion",
        "ranks_bo": list(ranks_usar),
        "n_semillas_primos": N_SEMILLAS_PRIMOS,
        "semillas_train": semillas,
        "foto_mes_train": list(FOTO_MES_MAR_JUN),
        "foto_mes_pred": FOTO_MES_JUL,
        "n_train": train_df.height,
        "n_julio": julio_df.height,
        "n_modelos": n_modelos,
        "nota_train_mar_jul": (
            "v1 sin submuestreo extra de negativos julio; train mar–jul puede quedar "
            "dominado por negativos."
        ),
    }
    with (out_dir / "meta.yml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(meta, f, sort_keys=False, allow_unicode=True)

    sync_resultados_subdir(experiment_id, SUBDIR_JULIO_PSEUDO)
    print(f"\nFinalizado en {out_dir}")


def main_fase_agosto_mar_jul(experiment_id: str) -> None:
    pull_resultados_subdir(experiment_id, SUBDIR_BO)
    pull_resultados_subdir(experiment_id, TOP20_ESTUDIO_REL)
    pull_resultados_subdir(experiment_id, SUBDIR_JULIO_PSEUDO)

    campos_buenos, tb_ranks, ranks_usar, semillas, param = load_top20_ranks(experiment_id)
    jul_dir = julio_pseudo_dir(experiment_id)
    imput_path = jul_dir / "clase01_imputado.parquet"
    if not imput_path.exists():
        raise FileNotFoundError(f"Ejecutar fase 8 antes: falta {imput_path}")

    out_dir = agosto_mar_jul_dir(experiment_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("RANKS:", ", ".join(str(r) for r in ranks_usar))
    print("semillas_train:", ", ".join(str(s) for s in semillas))

    aniomesdia = foto_mes_a_aniomesdia(FOTO_MES_AGO)
    meses_leer = tuple(sorted(set(FOTO_MES_MAR_JUL) | {FOTO_MES_AGO}))
    dataset = read_joined(experiment_id, foto_mes=meses_leer)

    imputado = pl.read_parquet(imput_path)
    train_mar_jun = with_clase01_observada(
        dataset.filter(pl.col("foto_mes").is_in(list(FOTO_MES_MAR_JUN)))
    )
    julio_raw = dataset.filter(pl.col("foto_mes") == FOTO_MES_JUL)
    julio_train = julio_raw.join(
        imputado.select(*JOIN_KEYS, "clase01"),
        on=list(JOIN_KEYS),
        how="inner",
    )
    if julio_train.height != julio_raw.height:
        raise ValueError("imputación no alinea con julio en capas join")

    train_df = pl.concat([train_mar_jun, julio_train], how="vertical")
    agosto_df = dataset.filter(pl.col("foto_mes") == FOTO_MES_AGO)
    if agosto_df.is_empty():
        raise ValueError(f"Sin filas para foto_mes={FOTO_MES_AGO}")

    n_train = train_df.height
    n_agosto = agosto_df.height
    print(f"train filas={n_train} | agosto filas={n_agosto}")

    prob_sum, n_modelos = _train_predict_loop(
        train_df,
        agosto_df,
        campos_buenos,
        tb_ranks,
        semillas,
        param,
        persist_models=True,
        out_dir=out_dir,
        experiment_id=experiment_id,
        aniomesdia=aniomesdia,
        subdir_upload=SUBDIR_AGOSTO_MAR_JUL,
    )

    tb_media = agosto_df.select("numero_de_cliente", "foto_mes").with_columns(
        (prob_sum / n_modelos).alias("prob")
    )
    tb_media.write_csv(out_dir / "prediccion_agosto_media.tsv", separator="\t")

    tb_ordenada = tb_media.sort("prob", descending=True).with_columns(
        pl.arange(1, tb_media.height + 1).alias("orden")
    )
    tb_ordenada.write_csv(out_dir / "prediccion_agosto_media_ordenada.tsv", separator="\t")

    meta = {
        "experiment_id": experiment_id,
        "fase": "agosto_mar_jul",
        "ranks_bo": list(ranks_usar),
        "n_semillas_primos": N_SEMILLAS_PRIMOS,
        "semillas_train": semillas,
        "foto_mes_train": list(FOTO_MES_MAR_JUL),
        "foto_mes_pred": FOTO_MES_AGO,
        "imputacion": str(imput_path.name),
        "aniomesdia_pred": aniomesdia,
        "modelo_lgb_patron": MODELO_LGB_PATRON,
        "prediccion_tsv_patron": PREDICCION_TSV_PATRON,
        "n_train": n_train,
        "n_agosto": n_agosto,
        "n_predicciones_agregadas": tb_media.height,
        "n_modelos": n_modelos,
    }
    with (out_dir / "meta.yml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(meta, f, sort_keys=False, allow_unicode=True)

    sync_resultados_subdir(experiment_id, SUBDIR_AGOSTO_MAR_JUL)
    print(f"\nFinalizado en {out_dir}")

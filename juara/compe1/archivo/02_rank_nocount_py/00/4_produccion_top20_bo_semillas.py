#!/usr/bin/env python3
"""Top-20 HP BO × 10 semillas primo (exp2102_top20)."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import polars as pl
import yaml

import _bootstrap  # noqa: F401

from common.cortes import write_cortes_ganancia
from common.data import feature_matrix, preparar_holdout_split
from common.layers import resultados_dir
from common.lgb_train import decode_min_sum_hessian, merge_tuned, train_full
from common.partition import semillas_primos
from common.plots import write_gain_curve_pdf

EXPERIMENT_ID = "02_rank_nocount_py"
EXPERIMENTO = 2102
N_RANKS = 20
N_SEMILLAS = 10
HIPERPARAMS = (
    "num_iterations",
    "num_leaves",
    "min_data_in_leaf",
    "min_sum_hessian_in_leaf",
)


def _hp_from_row(row: dict) -> dict:
    return {k: row[k] for k in HIPERPARAMS}


def _producir_primos(
    out_dir: Path,
    param: dict,
    param_hp: dict,
    semillas: list[int],
    train_df: pl.DataFrame,
    test_df: pl.DataFrame,
    campos_buenos: list[str],
    cortes: list[int],
    undersampling: float,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fixed = param["lgbm"]["param_fijos"]
    param_final = decode_min_sum_hessian(merge_tuned(fixed, param_hp))

    pieces: list[pl.DataFrame] = []
    for primo in semillas:
        suf = f"_{primo}"
        pnorm = dict(param_final)
        pnorm["min_data_in_leaf"] = int(
            round(float(param_final["min_data_in_leaf"]) / undersampling)
        )
        pnorm["seed"] = primo

        X_tr = feature_matrix(train_df, campos_buenos)
        y_tr = train_df["clase01"].to_numpy()
        model = train_full(X_tr, y_tr, pnorm, seed=primo)

        imp = pl.DataFrame(
            {
                "Feature": model.feature_name(),
                "Gain": model.feature_importance(importance_type="gain"),
            }
        )
        imp.write_csv(out_dir / f"impo{suf}.txt", separator="\t")
        model.save_model(str(out_dir / f"modelo{suf}.txt"))

        X_te = feature_matrix(test_df, campos_buenos)
        pred = model.predict(X_te)
        tb = test_df.select("numero_de_cliente", "foto_mes", "clase_ternaria").with_columns(
            pl.Series("prob", pred)
        )
        tb.select("numero_de_cliente", "foto_mes", "prob").write_csv(
            out_dir / f"prediccion{suf}.txt", separator="\t"
        )
        pieces.append(tb.select("numero_de_cliente", "foto_mes", "prob"))

        write_gain_curve_pdf(tb, out_dir / f"curva_ganancia{suf}.pdf")
        tb_sorted = tb.sort("prob", descending=True)
        write_cortes_ganancia(
            tb_sorted,
            out_dir / f"cortes_ganancia{suf}.txt",
            cortes,
            header=f"semilla_train={primo}",
        )

    all_probs = pl.concat(pieces, how="vertical")
    media = (
        all_probs.group_by("numero_de_cliente", "foto_mes")
        .agg(pl.col("prob").mean().alias("prob"))
        .join(
            test_df.select("numero_de_cliente", "foto_mes", "clase_ternaria"),
            on=["numero_de_cliente", "foto_mes"],
            how="inner",
        )
    )
    media.select("numero_de_cliente", "foto_mes", "prob").write_csv(
        out_dir / "prediccion_media.txt", separator="\t"
    )
    write_gain_curve_pdf(media, out_dir / "curva_ganancia_media.pdf")
    tb_sorted = media.sort("prob", descending=True)
    write_cortes_ganancia(
        tb_sorted,
        out_dir / "cortes_ganancia_media.txt",
        cortes,
        header="prob_media=10_semillas_primo",
    )
    rows = []
    for envios in cortes:
        from common.data import ganancia_envio

        rows.append(
            {
                "envios": envios,
                "total": ganancia_envio(tb_sorted, envios),
            }
        )
    pl.DataFrame(rows).write_csv(out_dir / "cortes_ganancia_media.tsv", separator="\t")


def main() -> None:
    res_dir = resultados_dir(EXPERIMENT_ID)
    ht_dir = res_dir / f"HT{EXPERIMENTO}"
    estudio_dir = res_dir / "estudio" / "top20_bo_semillas"
    rank_base = res_dir / "exp2102_top20"
    estudio_dir.mkdir(parents=True, exist_ok=True)
    rank_base.mkdir(parents=True, exist_ok=True)

    with (ht_dir / "PARAM.yml").open(encoding="utf-8") as f:
        param = yaml.safe_load(f)

    bo_log = ht_dir / "BO_log.txt"
    if not bo_log.exists():
        raise FileNotFoundError(f"No existe {bo_log}")

    tb_bo = pl.read_csv(bo_log, separator="\t")
    if tb_bo.height < N_RANKS:
        raise ValueError(f"BO_log tiene menos de {N_RANKS} filas")

    tb_top20 = tb_bo.head(N_RANKS).with_columns(
        pl.arange(1, tb_bo.head(N_RANKS).height + 1).alias("rank")
    )
    faltantes = [c for c in HIPERPARAMS if c not in tb_top20.columns]
    if faltantes:
        raise ValueError(f"BO_log sin columnas: {faltantes}")

    tb_top20.select("rank", *HIPERPARAMS, "y", "iter").write_csv(
        estudio_dir / "top20_hiperparametros.tsv", separator="\t"
    )

    semillas = semillas_primos(N_SEMILLAS, int(param["semilla_primigenia"]))
    print("semillas_train:", ", ".join(str(s) for s in semillas))
    (estudio_dir / "semillas_train.txt").write_text(
        "\n".join(str(s) for s in semillas) + "\n", encoding="utf-8"
    )

    campos_buenos = list(param["campos_buenos"])
    fold_train = int(param["holdout"]["fold_train"])
    fold_test = int(param["holdout"]["fold_test"])
    division = tuple(int(x) for x in param["holdout"]["division"])
    foto_mes = tuple(int(x) for x in param["foto_mes"])
    undersampling = float(param["trainingstrategy"]["undersampling"])
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
    train_df = df.filter(pl.col("fold") == fold_train)
    test_df = df.filter(pl.col("fold") == fold_test)

    for k in range(1, N_RANKS + 1):
        row = tb_top20.filter(pl.col("rank") == k).row(0, named=True)
        rank_label = f"rank_{k:02d}"
        out_dir = rank_base / rank_label
        hp = _hp_from_row(row)
        print(f"\n=== {rank_label} | AUC BO y={row['y']} iter={row['iter']} ===")
        _producir_primos(
            out_dir,
            param,
            hp,
            semillas,
            train_df,
            test_df,
            campos_buenos,
            cortes,
            undersampling,
        )
        param_rank = deepcopy(param)
        param_rank["out"]["lgbm"]["mejores_hiperparametros"] = hp
        param_rank["out"]["lgbm"]["y"] = row["y"]
        param_rank["top20_bo"] = {
            "rank": k,
            "bo_iter": row["iter"],
            "bo_y": row["y"],
        }
        param_rank["semillas_train"] = semillas
        with (out_dir / "PARAM.yml").open("w", encoding="utf-8") as f:
            yaml.safe_dump(param_rank, f, sort_keys=False, allow_unicode=True)

    print(f"\nFinalizado top-20 en {rank_base}")


if __name__ == "__main__":
    main()

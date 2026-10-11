"""Nombres y persistencia incremental de modelos y predicciones agosto."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from common.gcs_upload import upload_resultados_file
from common.layers import SUBDIR_AGOSTO

MODELO_LGB_PATRON = "modelo_%02d_<semilla>.txt"
PREDICCION_TSV_PATRON = "modelo_%02d_<semilla>_<aniomesdia>.tsv"


def foto_mes_a_aniomesdia(foto_mes: int) -> str:
    return f"{foto_mes // 100}{foto_mes % 100:02d}01"


def nombre_modelo_lgb(rank_id: int, semilla: int) -> str:
    return f"modelo_{rank_id:02d}_{semilla}.txt"


def nombre_tsv_modelo_semilla(rank_id: int, semilla: int, aniomesdia: str) -> str:
    return f"modelo_{rank_id:02d}_{semilla}_{aniomesdia}.tsv"


def persist_model_and_upload(
    model,
    out_dir: Path,
    experiment_id: str,
    rank_id: int,
    semilla: int,
) -> None:
    name = nombre_modelo_lgb(rank_id, semilla)
    model.save_model(str(out_dir / name))
    upload_resultados_file(experiment_id, SUBDIR_AGOSTO, name)


def persist_pred_tsv_and_upload(
    tb_piece: pl.DataFrame,
    out_dir: Path,
    experiment_id: str,
    rank_id: int,
    semilla: int,
    aniomesdia: str,
) -> None:
    name = nombre_tsv_modelo_semilla(rank_id, semilla, aniomesdia)
    tb_piece.write_csv(out_dir / name, separator="\t")
    upload_resultados_file(experiment_id, SUBDIR_AGOSTO, name)

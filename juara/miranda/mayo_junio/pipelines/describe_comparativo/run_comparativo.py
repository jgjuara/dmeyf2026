"""Orquesta el comparativo BAJA vs CONTINUA (etapas 0–7)."""

from __future__ import annotations

import argparse
import os

import polars as pl


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Comparativo BAJA vs CONTINUA (mayo–junio).")
    parser.add_argument(
        "--pool-mes",
        action="store_true",
        help="Apila mayo+junio: un contraste por variable y etapa; FDR por etapa.",
    )
    return parser.parse_args()


def _apply_pool_env(pool_mes: bool) -> None:
    if pool_mes:
        os.environ["MIRANDA_POOL_MES"] = "1"
    elif os.environ.get("MIRANDA_POOL_MES", "").strip().lower() not in ("1", "true", "yes"):
        os.environ.pop("MIRANDA_POOL_MES", None)


def main() -> None:
    args = _parse_args()
    _apply_pool_env(args.pool_mes)

    from _etapas import run_all
    from _paths import INFORME_MD, PARQUET_BAJA, PARQUET_CONTINUA, POOL_MES, PLOTS_DIR, TABLAS_DIR

    if not PARQUET_BAJA.is_file():
        raise SystemExit(f"Falta parquet BAJA: {PARQUET_BAJA}")
    if not PARQUET_CONTINUA.is_file():
        raise SystemExit(f"Falta parquet CONTINUA: {PARQUET_CONTINUA}")

    df, resumen = run_all()
    n_baja = df.filter(pl.col("grupo") == "baja").height
    n_cont = df.filter(pl.col("grupo") == "continua").height

    modo = "pooled (mayo+junio)" if POOL_MES else "estratificado por foto_mes"
    print(f"modo: {modo}")
    print(f"filas total: {df.height} (baja={n_baja}, continua={n_cont})")
    print(f"tablas: {TABLAS_DIR}")
    print(f"plots: {PLOTS_DIR}")
    print(f"informe: {INFORME_MD}")
    print(f"resumen_top_efectos filas: {resumen.height}")


if __name__ == "__main__":
    main()

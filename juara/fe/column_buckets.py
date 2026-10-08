"""Clasificación de columnas por bucket (taxonomía FE centralizada)."""

from __future__ import annotations

from functools import lru_cache

import duckdb

from columns import columns_to_rank, load_nocontinuas
from paths import NOCONTINUAS_PATH, competencia_parquet_v1

META_COLS = frozenset({"numero_de_cliente", "foto_mes", "clase_ternaria", "grupo"})


@lru_cache(maxsize=1)
def nocontinuas_feature_names() -> frozenset[str]:
    names = load_nocontinuas(NOCONTINUAS_PATH)
    return names - META_COLS


@lru_cache(maxsize=1)
def continuous_metric_names() -> frozenset[str]:
    comp = competencia_parquet_v1()
    if not comp.is_file():
        raise FileNotFoundError(f"No existe competencia: {comp}")
    nocontinuas = nocontinuas_feature_names()
    path_sql = str(comp).replace("'", "''")
    con = duckdb.connect()
    try:
        rows = con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{path_sql}')"
        ).fetchall()
    finally:
        con.close()
    all_columns = [row[0] for row in rows]
    return frozenset(columns_to_rank(all_columns, nocontinuas))


def bucket_for_column(name: str) -> str:
    if name in META_COLS:
        return "claves"
    if name.startswith("lag1_pct"):
        return "rankings_lag1_pct"
    if name.startswith("lag2_pct"):
        return "rankings_lag2_pct"
    if name.startswith("delta1_pct"):
        return "rankings_delta1_pct"
    if name.startswith("delta2_pct"):
        return "rankings_delta2_pct"

    nocont = nocontinuas_feature_names()
    cont = continuous_metric_names()

    if name.startswith("lag1_") and not name.startswith("lag1_pct"):
        base = name[5:]
        if base in nocont:
            return "nocontinuas_lag1"
        if base in cont:
            return "continuas_lag1"
        return "nocontinuas_base"

    if name.startswith("lag2_") and not name.startswith("lag2_pct"):
        base = name[5:]
        if base in nocont:
            return "nocontinuas_lag2"
        if base in cont:
            return "continuas_lag2"
        return "nocontinuas_base"

    if name.startswith("delta1_") and not name.startswith("delta1_pct"):
        base = name[7:]
        if base in cont:
            return "continuas_delta1"
        return "nocontinuas_base"

    if name.startswith("delta2_") and not name.startswith("delta2_pct"):
        base = name[7:]
        if base in cont:
            return "continuas_delta2"
        return "nocontinuas_base"

    if name.startswith("pct_"):
        return "rankings_pct"
    if name in nocont:
        return "nocontinuas_base"
    if name in cont:
        return "continuas_nivel"
    return "nocontinuas_base"

"""Taxonomía de columnas (alineada con describe_casos/_lib)."""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

_FE_DIR = Path(__file__).resolve().parents[4] / "fe"
if str(_FE_DIR) not in sys.path:
    sys.path.insert(0, str(_FE_DIR))
from column_buckets import bucket_for_column  # noqa: E402

NOCONTINUAS_COLS = [
    "active_quarter",
    "cliente_vip",
    "internet",
    "tcuentas",
    "ccuenta_corriente",
    "cdescubierto_preacordado",
    "ctarjeta_visa",
    "ctarjeta_master",
    "cseguro_vida",
    "cseguro_vivienda",
    "cseguro_accidentes_personales",
    "tcallcenter",
    "thomebanking",
    "ccajas_transacciones",
    "tmobile_app",
    "cmobile_app_trx",
    "Master_delinquency",
    "Master_status",
    "Visa_delinquency",
    "Visa_status",
    "ctarjeta_debito",
    "cseguro_auto",
    "cforex",
    "cforex_buy",
    "cforex_sell",
    "ccheques_depositados_rechazados",
]

META_COLS = frozenset({"numero_de_cliente", "foto_mes", "clase_ternaria", "grupo"})
PCT_QUANTILES = (0.1, 0.5, 0.9)


def column_groups(columns: list[str]) -> pl.DataFrame:
    counts: dict[str, int] = {}
    for c in columns:
        b = bucket_for_column(c)
        counts[b] = counts.get(b, 0) + 1
    return pl.DataFrame({"grupo": list(counts.keys()), "n_columnas": list(counts.values())}).sort(
        "grupo"
    )


def columns_in_bucket(columns: list[str], bucket: str) -> list[str]:
    return sorted(c for c in columns if bucket_for_column(c) == bucket)


def feature_columns(columns: list[str]) -> list[str]:
    return sorted(c for c in columns if c not in META_COLS and bucket_for_column(c) != "claves")


def md_table(df: pl.DataFrame, float_fmt: str = ".4f") -> str:
    cols = df.columns
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for row in df.iter_rows():
        cells: list[str] = []
        for v in row:
            if v is None:
                cells.append("")
            elif isinstance(v, float):
                cells.append(format(v, float_fmt))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)

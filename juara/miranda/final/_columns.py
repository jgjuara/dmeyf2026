"""Taxonomía de columnas para métricas y gráficos."""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

_FE_DIR = Path(__file__).resolve().parents[2] / "fe"
if str(_FE_DIR) not in sys.path:
    sys.path.insert(0, str(_FE_DIR))
from column_buckets import bucket_for_column  # noqa: E402

META_COLS = frozenset({"numero_de_cliente", "foto_mes", "clase_ternaria"})
COHORT_META = frozenset(
    {
        "cohort_member_id",
        "grupo",
        "foto_mes_ancla",
        "clase_ancla",
        "horizonte_evento",
        "horizonte_meses",
        "mes_evento_esperado",
        "es_control_replicado",
        "mes_relativo",
    }
)

# Lista cerrada para el clasificador de etapa 04. Son medidas observadas al
# ancla; no se infieren columnas por nombre para impedir que una variable nueva
# (incluidos metadatos o etiquetas derivadas) entre silenciosamente al modelo.
ANCHOR_PREDICTORS = (
    "cliente_edad",
    "cliente_antiguedad",
    "active_quarter",
    "cliente_vip",
    "internet",
    "tcuentas",
    "ccuenta_corriente",
    "cdescubierto_preacordado",
    "ctarjeta_visa",
    "ctarjeta_master",
    "ctarjeta_debito",
    "cseguro_vida",
    "cseguro_auto",
    "thomebanking",
    "tmobile_app",
    "cproductos",
    "mrentabilidad",
    "mrentabilidad_annual",
    "mcomisiones",
    "mcuentas_saldo",
    "mpayroll",
    "ctrx_quarter",
    "ctarjeta_visa_transacciones",
    "ctarjeta_master_transacciones",
    "Visa_msaldototal",
    "Master_msaldototal",
    "mprestamos_personales",
    "mprestamos_prendarios",
)

_NON_PREDICTOR_PREFIXES = ("lag", "delta", "pct_")

NOCONTINUAS_ANCLA = [
    "internet",
    "cliente_vip",
    "active_quarter",
    "thomebanking",
    "tmobile_app",
    "ctarjeta_visa",
    "ctarjeta_master",
    "ctarjeta_debito",
    "cseguro_vida",
    "cseguro_auto",
]


def feature_columns(columns: list[str]) -> list[str]:
    return sorted(
        c
        for c in columns
        if c not in META_COLS
        and c not in COHORT_META
        and bucket_for_column(c) not in ("claves",)
    )


def numeric_features(df: pl.DataFrame) -> list[str]:
    feats = feature_columns(df.columns)
    numeric = []
    for c in feats:
        dtype = df.schema[c]
        if dtype in (pl.Float64, pl.Float32, pl.Int64, pl.Int32, pl.UInt32):
            numeric.append(c)
    return numeric


def anchor_predictor_features(df: pl.DataFrame) -> list[str]:
    """Devuelve sólo predictores explícitamente admitidos y numéricos al ancla."""

    numeric_types = {
        pl.Float64,
        pl.Float32,
        pl.Int64,
        pl.Int32,
        pl.UInt64,
        pl.UInt32,
        pl.UInt16,
        pl.Int16,
        pl.UInt8,
        pl.Int8,
    }
    return [
        name
        for name in ANCHOR_PREDICTORS
        if name in df.columns
        and name not in META_COLS
        and name not in COHORT_META
        and not name.startswith(_NON_PREDICTOR_PREFIXES)
        and df.schema[name] in numeric_types
    ]


PROFILE_DOMAINS = {
    "perfil_cliente": (
        "cliente_edad",
        "cliente_antiguedad",
        "mpayroll",
        "tcuentas",
    ),
    "rentabilidad": ("mrentabilidad", "mrentabilidad_annual", "mcomisiones"),
    "saldos": ("mcuentas_saldo", "Visa_msaldototal", "Master_msaldototal"),
    "financiero": ("deuda_total_operativa", "patrimonio_liquido_operativo"),
    "productos": (
        "cproductos",
        "ccuenta_corriente",
        "ctarjeta_visa",
        "ctarjeta_master",
        "ctarjeta_debito",
        "mprestamos_personales",
        "mprestamos_prendarios",
    ),
    "canales": (
        "internet",
        "thomebanking",
        "tmobile_app",
        "ctarjeta_visa_transacciones",
        "ctarjeta_master_transacciones",
        "ctrx_quarter",
    ),
}


def columns_by_bucket(columns: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for c in columns:
        b = bucket_for_column(c)
        out.setdefault(b, []).append(c)
    return {k: sorted(v) for k, v in sorted(out.items())}


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

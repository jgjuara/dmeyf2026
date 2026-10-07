"""Rutas del informe comparativo BAJA vs CONTINUA (junio 2021)."""

import os
from pathlib import Path

MIRANDA_DIR = Path(__file__).resolve().parent.parent.parent
_DATOS = MIRANDA_DIR / "datos"
_COMP = MIRANDA_DIR / "salidas" / "comparativo"
PARQUET_BAJA = _DATOS / "dataset_junio.parquet"
PARQUET_CONTINUA = _DATOS / "dataset_continua_20_junio.parquet"

POOL_MES = os.environ.get("MIRANDA_POOL_MES", "").strip().lower() in ("1", "true", "yes")
POOLED_FOTO_MES_LABEL = "junio_pooled"

if POOL_MES:
    OUT_DIR = _COMP / "informe_comparativo_baja_vs_continua_junio_pooled"
    INFORME_MD = OUT_DIR / "informe_comparativo_baja_vs_continua_junio_pooled.md"
else:
    OUT_DIR = _COMP / "informe_comparativo_baja_vs_continua_junio"
    INFORME_MD = OUT_DIR / "informe_comparativo_baja_vs_continua_junio.md"

TABLAS_DIR = OUT_DIR / "tablas"
PLOTS_DIR = OUT_DIR / "plots"

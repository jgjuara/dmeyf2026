"""Conteo de null por columna; tabla CSV en stdout."""

import sys

from dataset import input_path

import polars as pl

df = pl.read_csv(input_path(), infer_schema_length=0)

tabla = (
    df.null_count()
    .unpivot(on=df.columns, variable_name="columna", value_name="n_null")
    .sort("n_null", descending=True)
)

tabla.write_csv(sys.stdout)

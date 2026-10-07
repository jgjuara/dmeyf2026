"""Imprime shape del dataset y tipo inferido de cada columna."""

import sys

from dataset import input_path

import polars as pl

path = input_path()
df = pl.read_csv(path, infer_schema_length=0)
n_rows, n_cols = df.shape
print(f"shape: ({n_rows}, {n_cols})")

schema = pl.scan_csv(path, infer_schema_length=50_000).collect_schema()
tabla = pl.DataFrame(
    {
        "columna": schema.names(),
        "tipo": [str(schema[name]) for name in schema.names()],
    }
)
tabla.write_csv(sys.stdout)

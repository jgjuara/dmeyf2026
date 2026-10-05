"""Subconjunto de competencia_01.parquet: claves, clase_ternaria y vars nocontinuas."""

from __future__ import annotations

import sys

import duckdb

from columns import columns_competencia_nocontinuas
from paths import NOCONTINUAS_PATH, competencia_nocontinuas_parquet, competencia_parquet


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def main() -> None:
    src = competencia_parquet()
    dst = competencia_nocontinuas_parquet()
    if not src.is_file():
        raise SystemExit(f"Archivo inexistente: {src}")

    select_columns = columns_competencia_nocontinuas(NOCONTINUAS_PATH)
    src_sql = str(src).replace("'", "''")
    dst_sql = str(dst).replace("'", "''")

    con = duckdb.connect()
    schema_rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{src_sql}')"
    ).fetchall()
    source_columns = {row[0] for row in schema_rows}
    missing = [c for c in select_columns if c not in source_columns]
    if missing:
        raise SystemExit(f"Columnas ausentes en fuente: {missing}")

    col_list = ",\n    ".join(_quote_ident(c) for c in select_columns)

    con.execute(
        f"""
        COPY (
          SELECT
            {col_list}
          FROM read_parquet('{src_sql}')
        ) TO '{dst_sql}' (FORMAT PARQUET, COMPRESSION 'UNCOMPRESSED')
        """
    )

    n_src = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{src_sql}')"
    ).fetchone()[0]
    n_dst = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{dst_sql}')"
    ).fetchone()[0]
    n_cols = con.execute(
        f"SELECT COUNT(*) FROM (DESCRIBE SELECT * FROM read_parquet('{dst_sql}'))"
    ).fetchone()[0]

    print(f"columnas salida: {n_cols} (esperadas {len(select_columns)})")
    print(f"filas fuente: {n_src}")
    print(f"filas salida: {n_dst}")

    if n_src != n_dst:
        raise SystemExit("Validación fallida: distinto número de filas")
    if n_cols != len(select_columns):
        raise SystemExit("Validación fallida: distinto número de columnas")

    print(f"escrito: {dst}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

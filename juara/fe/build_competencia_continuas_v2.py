"""Subconjunto continuo desde clean v1 → competencia_01_continuas_v2.parquet (misma lógica que v1)."""

from __future__ import annotations

import sys

import duckdb

from columns import columns_competencia_continuas, load_nocontinuas
from gcs_upload import ensure_local_parquet, upload_parquet
from paths import NOCONTINUAS_PATH, competencia_continuas_v2_parquet, competencia_parquet_v1


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def main() -> None:
    src = competencia_parquet_v1()
    dst = competencia_continuas_v2_parquet()
    ensure_local_parquet(src)
    if not src.is_file():
        raise SystemExit(f"Archivo inexistente: {src}")

    src_sql = str(src).replace("'", "''")
    dst_sql = str(dst).replace("'", "''")

    con = duckdb.connect()
    schema_rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{src_sql}')"
    ).fetchall()
    all_columns = [row[0] for row in schema_rows]
    nocontinuas = load_nocontinuas(NOCONTINUAS_PATH)
    select_columns = columns_competencia_continuas(all_columns, nocontinuas)

    missing = [c for c in select_columns if c not in set(all_columns)]
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
    upload_parquet(dst)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

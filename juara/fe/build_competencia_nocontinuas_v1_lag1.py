"""lag1 por cliente desde competencia_01_nocontinuas_v1.parquet → competencia_01_nocontinuas_v1_lag1.parquet."""

from __future__ import annotations

import sys

import duckdb

from columns import columns_for_lag1
from gcs_upload import ensure_local_parquet, upload_parquet
from paths import competencia_nocontinuas_v1_lag1_parquet, competencia_nocontinuas_v1_parquet


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _window() -> str:
    return "PARTITION BY numero_de_cliente ORDER BY foto_mes ASC"


def _lag_expr(column: str) -> str:
    col = _quote_ident(column)
    alias = _quote_ident(f"lag1_{column}")
    return f"LAG({col}, 1) OVER ({_window()}) AS {alias}"


def main() -> None:
    src = competencia_nocontinuas_v1_parquet()
    dst = competencia_nocontinuas_v1_lag1_parquet()
    ensure_local_parquet(src)
    if not src.is_file():
        raise SystemExit(f"Archivo inexistente: {src}")

    src_sql = str(src).replace("'", "''")

    con = duckdb.connect()
    schema_rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{src_sql}')"
    ).fetchall()
    all_columns = [row[0] for row in schema_rows]
    metric_columns = columns_for_lag1(all_columns)

    print(f"columnas fuente: {len(all_columns)}")
    print(f"columnas lag1: {len(metric_columns)}")

    lag_exprs = ",\n  ".join(_lag_expr(c) for c in metric_columns)
    dst_sql = str(dst).replace("'", "''")

    con.execute(
        f"""
        COPY (
          SELECT
            numero_de_cliente,
            foto_mes,
            {lag_exprs}
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
    n_dup = con.execute(
        f"""
        SELECT COUNT(*) - COUNT(DISTINCT (numero_de_cliente, foto_mes))
        FROM read_parquet('{dst_sql}')
        """
    ).fetchone()[0]
    n_cols = con.execute(
        f"SELECT COUNT(*) FROM (DESCRIBE SELECT * FROM read_parquet('{dst_sql}'))"
    ).fetchone()[0]
    expected_cols = 2 + len(metric_columns)

    print(f"filas fuente: {n_src}")
    print(f"filas salida: {n_dst}")
    print(f"columnas salida: {n_cols} (esperadas {expected_cols})")

    if n_src != n_dst:
        raise SystemExit("Validación fallida: distinto número de filas")
    if n_dup != 0:
        raise SystemExit("Validación fallida: claves duplicadas en salida")
    if n_cols != expected_cols:
        raise SystemExit("Validación fallida: distinto número de columnas")

    sample_lag = f"lag1_{metric_columns[0]}"
    print(f"filas con {sample_lag} IS NULL por foto_mes:")
    rows = con.execute(
        f"""
        SELECT foto_mes, COUNT(*)
        FROM read_parquet('{dst_sql}')
        WHERE {_quote_ident(sample_lag)} IS NULL
        GROUP BY foto_mes
        ORDER BY foto_mes
        """
    ).fetchall()
    for foto_mes, n_null in rows:
        print(f"  {foto_mes}: {n_null}")

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

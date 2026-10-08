"""Limpieza puntual sobre competencia_01_v1.parquet → competencia_01_clean_v1.parquet (entrada FE)."""

from __future__ import annotations

import sys

import duckdb

from gcs_upload import ensure_local_parquet, upload_parquet
from paths import DATA_DIR, competencia_parquet_clean_v1, competencia_parquet_labeled_v1

CCA_DEPOSITOS_COL = "ccajas_depositos"
CCA_DEPOSITOS_NULL_FOTO_MES = 202105


def _sql_path(path) -> str:
    return str(path).replace("'", "''")


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def main() -> None:
    src = competencia_parquet_labeled_v1()
    dst = competencia_parquet_clean_v1()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    ensure_local_parquet(src)
    if not src.is_file():
        raise SystemExit(f"Archivo inexistente: {src}")

    src_sql = _sql_path(src)
    dst_sql = _sql_path(dst)
    col = _quote_ident(CCA_DEPOSITOS_COL)

    con = duckdb.connect()
    schema_rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{src_sql}')"
    ).fetchall()
    columns = {row[0] for row in schema_rows}
    if CCA_DEPOSITOS_COL not in columns:
        raise SystemExit(f"Columna ausente en fuente: {CCA_DEPOSITOS_COL}")

    print(f"ccajas_depositos no-nulos por foto_mes (fuente):")
    rows_before = con.execute(
        f"""
        SELECT foto_mes, count(*) AS n, count({col}) AS nn
        FROM read_parquet('{src_sql}')
        GROUP BY foto_mes
        ORDER BY foto_mes
        """
    ).fetchall()
    for foto_mes, n, nn in rows_before:
        print(f"  {foto_mes}: filas={n} nn={nn}")

    con.execute(
        f"""
        COPY (
          SELECT
            * EXCLUDE ({col}),
            CASE
              WHEN foto_mes = {CCA_DEPOSITOS_NULL_FOTO_MES} THEN NULL
              ELSE {col}
            END AS {col}
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
    if n_src != n_dst:
        raise SystemExit("Validación fallida: distinto número de filas")

    nn_202105 = con.execute(
        f"""
        SELECT COUNT(*) FROM read_parquet('{dst_sql}')
        WHERE foto_mes = {CCA_DEPOSITOS_NULL_FOTO_MES}
          AND {col} IS NOT NULL
        """
    ).fetchone()[0]
    if nn_202105 != 0:
        raise SystemExit(
            f"Validación fallida: {CCA_DEPOSITOS_COL} no nulo en "
            f"foto_mes={CCA_DEPOSITOS_NULL_FOTO_MES}: {nn_202105}"
        )

    mismatches = con.execute(
        f"""
        WITH src AS (
          SELECT
            foto_mes,
            count(*) AS n,
            count({col}) AS nn,
            sum({col}) AS s
          FROM read_parquet('{src_sql}')
          WHERE foto_mes != {CCA_DEPOSITOS_NULL_FOTO_MES}
          GROUP BY foto_mes
        ),
        dst AS (
          SELECT
            foto_mes,
            count(*) AS n,
            count({col}) AS nn,
            sum({col}) AS s
          FROM read_parquet('{dst_sql}')
          WHERE foto_mes != {CCA_DEPOSITOS_NULL_FOTO_MES}
          GROUP BY foto_mes
        )
        SELECT count(*)
        FROM src
        FULL OUTER JOIN dst USING (foto_mes)
        WHERE src.n IS DISTINCT FROM dst.n
           OR src.nn IS DISTINCT FROM dst.nn
           OR src.s IS DISTINCT FROM dst.s
        """
    ).fetchone()[0]
    if mismatches:
        raise SystemExit(
            "Validación fallida: agregados de ccajas_depositos difieren "
            "fuera de foto_mes 202105"
        )

    print(f"ccajas_depositos no-nulos por foto_mes (salida):")
    rows_after = con.execute(
        f"""
        SELECT foto_mes, count(*) AS n, count({col}) AS nn
        FROM read_parquet('{dst_sql}')
        GROUP BY foto_mes
        ORDER BY foto_mes
        """
    ).fetchall()
    for foto_mes, n, nn in rows_after:
        print(f"  {foto_mes}: filas={n} nn={nn}")

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

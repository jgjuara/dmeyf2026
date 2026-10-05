"""Percentiles por foto_mes desde competencia_01.parquet → rankings.parquet."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import duckdb

from columns import columns_to_rank, load_nocontinuas
from paths import NOCONTINUAS_PATH, competencia_parquet, rankings_parquet

# Ventanas encadenadas en un solo SELECT multiplican el pico de RAM; lotes más chicos = menos pico.
PCT_BATCH_SIZE = max(1, int(os.environ.get("RANKINGS_PCT_BATCH", "8")))
DUCKDB_MEMORY_LIMIT = os.environ.get("DUCKDB_MEMORY_LIMIT", "4GB")
DUCKDB_THREADS = os.environ.get("DUCKDB_THREADS")
DUCKDB_TEMP_DIRECTORY = os.environ.get("DUCKDB_TEMP_DIRECTORY")


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _pct_expr(column: str) -> str:
    col = _quote_ident(column)
    alias = _quote_ident(f"pct_{column}")
    return (
        f"CASE WHEN {col} IS NULL THEN NULL "
        f"ELSE ROUND(PERCENT_RANK() OVER ("
        f"PARTITION BY foto_mes ORDER BY {col} ASC"
        f"), 6) END AS {alias}"
    )


def _sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{DUCKDB_MEMORY_LIMIT}'")
    if DUCKDB_TEMP_DIRECTORY:
        con.execute(f"SET temp_directory='{_sql_path(Path(DUCKDB_TEMP_DIRECTORY))}'")
    if DUCKDB_THREADS is not None:
        con.execute(f"SET threads={int(DUCKDB_THREADS)}")
    return con


def _pct_select_sql(src_sql: str, columns: list[str]) -> str:
    pct_exprs = ",\n    ".join(_pct_expr(c) for c in columns)
    return f"""
    SELECT
      numero_de_cliente,
      foto_mes,
      {pct_exprs}
    FROM read_parquet('{src_sql}')
    """


def _copy_parquet(con: duckdb.DuckDBPyConnection, select_sql: str, path: Path) -> None:
    path_sql = _sql_path(path)
    con.execute(
        f"COPY ({select_sql}) TO '{path_sql}' (FORMAT PARQUET, COMPRESSION 'UNCOMPRESSED')"
    )


def _build_rankings_batched(
    con: duckdb.DuckDBPyConnection,
    src_sql: str,
    dst: Path,
    rank_columns: list[str],
) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="rankings_build_"))
    try:
        accum = tmp / "accum.parquet"
        for i in range(0, len(rank_columns), PCT_BATCH_SIZE):
            batch = rank_columns[i : i + PCT_BATCH_SIZE]
            batch_no = i // PCT_BATCH_SIZE + 1
            batch_total = (len(rank_columns) + PCT_BATCH_SIZE - 1) // PCT_BATCH_SIZE
            print(f"lote {batch_no}/{batch_total}: {len(batch)} columnas pct_*")
            batch_sql = _pct_select_sql(src_sql, batch)
            if i == 0:
                _copy_parquet(con, batch_sql, accum)
                continue
            next_accum = tmp / f"accum_{batch_no}.parquet"
            prev_sql = _sql_path(accum)
            out_sql = _sql_path(next_accum)
            pct_list = ", ".join(
                f'batch.{_quote_ident(f"pct_{c}")}' for c in batch
            )
            con.execute(
                f"""
                COPY (
                  SELECT
                    prev.*,
                    {pct_list}
                  FROM read_parquet('{prev_sql}') prev
                  JOIN ({batch_sql}) batch
                    USING (numero_de_cliente, foto_mes)
                ) TO '{out_sql}' (FORMAT PARQUET, COMPRESSION 'UNCOMPRESSED')
                """
            )
            accum.unlink(missing_ok=True)
            accum = next_accum

        dst_sql = _sql_path(dst)
        accum_sql = _sql_path(accum)
        con.execute(
            f"""
            COPY (SELECT * FROM read_parquet('{accum_sql}'))
            TO '{dst_sql}' (FORMAT PARQUET, COMPRESSION 'UNCOMPRESSED')
            """
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    src = competencia_parquet()
    dst = rankings_parquet()
    if not src.is_file():
        raise SystemExit(f"Archivo inexistente: {src}")

    nocontinuas = load_nocontinuas(NOCONTINUAS_PATH)
    src_sql = _sql_path(src)

    con = _connect()
    schema_rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{src_sql}')"
    ).fetchall()
    all_columns = [row[0] for row in schema_rows]
    rank_columns = columns_to_rank(all_columns, nocontinuas)

    print(f"columnas fuente: {len(all_columns)}")
    print(f"excluidas (nocontinuas + claves): {len(all_columns) - len(rank_columns)}")
    print(f"columnas pct_*: {len(rank_columns)}")
    print(f"duckdb memory_limit={DUCKDB_MEMORY_LIMIT}, pct_batch={PCT_BATCH_SIZE}")

    _build_rankings_batched(con, src_sql, dst, rank_columns)
    dst_sql = _sql_path(dst)

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
    n_pct_cols = con.execute(
        f"""
        SELECT COUNT(*)
        FROM (DESCRIBE SELECT * FROM read_parquet('{dst_sql}'))
        WHERE column_name LIKE 'pct_%'
        """
    ).fetchone()[0]

    print(f"filas fuente: {n_src}")
    print(f"filas salida: {n_dst}")
    print(f"columnas pct_* en parquet: {n_pct_cols}")

    if n_src != n_dst:
        raise SystemExit("Validación fallida: distinto número de filas")
    if n_dup != 0:
        raise SystemExit("Validación fallida: claves duplicadas en salida")

    sample_col = "pct_mactivos_margen"
    print(f"min/max {sample_col} por foto_mes:")
    rows = con.execute(
        f"""
        SELECT foto_mes,
               MIN({_quote_ident(sample_col)}),
               MAX({_quote_ident(sample_col)})
        FROM read_parquet('{dst_sql}')
        GROUP BY foto_mes
        ORDER BY foto_mes
        """
    ).fetchall()
    for foto_mes, vmin, vmax in rows:
        print(f"  {foto_mes}: {vmin} .. {vmax}")

    print(f"escrito: {dst}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

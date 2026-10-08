"""Une competencia_01_nocontinuas y rankings por (numero_de_cliente, foto_mes)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb

DRIFTING_DIR = Path(__file__).resolve().parent.parent
JUARA_DIR = DRIFTING_DIR.parent
FE_DIR = JUARA_DIR / "fe"
sys.path.insert(0, str(FE_DIR))

from paths import competencia_nocontinuas_v1_parquet, rankings_v1_parquet  # noqa: E402

DATOS_DIR = DRIFTING_DIR / "datos"
DEFAULT_OUTPUT = DATOS_DIR / "dataset_nocont_rank.parquet"
JOIN_KEYS = ("numero_de_cliente", "foto_mes")

DUCKDB_MEMORY_LIMIT = os.environ.get("DUCKDB_MEMORY_LIMIT", "4GB")
DUCKDB_THREADS = os.environ.get("DUCKDB_THREADS")
DUCKDB_TEMP_DIRECTORY = os.environ.get("DUCKDB_TEMP_DIRECTORY")


def _sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{DUCKDB_MEMORY_LIMIT}'")
    if DUCKDB_TEMP_DIRECTORY:
        con.execute(f"SET temp_directory='{_sql_path(Path(DUCKDB_TEMP_DIRECTORY))}'")
    if DUCKDB_THREADS is not None:
        con.execute(f"SET threads={int(DUCKDB_THREADS)}")
    return con


def build_dataset(con: duckdb.DuckDBPyConnection, dst: Path) -> None:
    nc_path = competencia_nocontinuas_v1_parquet()
    rk_path = rankings_v1_parquet()
    for path in (nc_path, rk_path):
        if not path.is_file():
            raise SystemExit(f"Archivo inexistente: {path}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    nc_sql = _sql_path(nc_path)
    rk_sql = _sql_path(rk_path)
    dst_sql = _sql_path(dst)
    keys = ", ".join(_quote_ident(k) for k in JOIN_KEYS)

    con.execute(
        f"""
        COPY (
          SELECT
            nc.*,
            rk.* EXCLUDE ({keys})
          FROM read_parquet('{nc_sql}') nc
          INNER JOIN read_parquet('{rk_sql}') rk
            USING ({keys})
        ) TO '{dst_sql}' (FORMAT PARQUET, COMPRESSION 'UNCOMPRESSED')
        """
    )


def _validate(con: duckdb.DuckDBPyConnection, dst: Path) -> None:
    dst_sql = _sql_path(dst)
    nc_sql = _sql_path(competencia_nocontinuas_v1_parquet())

    n_rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{dst_sql}')").fetchone()[0]
    n_ref = con.execute(f"SELECT COUNT(*) FROM read_parquet('{nc_sql}')").fetchone()[0]
    n_dup = con.execute(
        f"""
        SELECT COUNT(*) - COUNT(DISTINCT ({", ".join(JOIN_KEYS)}))
        FROM read_parquet('{dst_sql}')
        """
    ).fetchone()[0]
    n_cols = con.execute(
        f"SELECT COUNT(*) FROM (DESCRIBE SELECT * FROM read_parquet('{dst_sql}'))"
    ).fetchone()[0]
    meses = con.execute(
        f"""
        SELECT foto_mes, COUNT(*) AS n
        FROM read_parquet('{dst_sql}')
        GROUP BY foto_mes
        ORDER BY foto_mes
        """
    ).fetchall()

    print(f"filas salida: {n_rows} (nocontinuas: {n_ref})")
    print(f"columnas: {n_cols}")
    print("conteo por foto_mes:")
    for foto_mes, n in meses:
        print(f"  {foto_mes}: {n}")

    if n_rows != n_ref:
        raise SystemExit("Validación fallida: filas distintas a nocontinuas (join incompleto o duplicados en rankings)")
    if n_dup != 0:
        raise SystemExit("Validación fallida: claves duplicadas")


def main() -> None:
    dst = Path(os.environ.get("DRIFTING_OUTPUT", str(DEFAULT_OUTPUT)))
    print(f"duckdb memory_limit={DUCKDB_MEMORY_LIMIT}")

    con = _connect()
    build_dataset(con, dst)
    _validate(con, dst)
    print(f"escrito: {dst}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

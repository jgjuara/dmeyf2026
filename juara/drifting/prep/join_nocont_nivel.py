"""Une competencia_01_nocontinuas con continuas en escala cruda (sin pct/lag/delta).

Datasets con capas FE de continuas lag/delta (competencia_01_continuas_lag* / delta*)
requieren otro prep; este join no las incorpora y rechaza cualquier columna lag*/delta* en salida.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb

DRIFTING_DIR = Path(__file__).resolve().parent.parent
JUARA_DIR = DRIFTING_DIR.parent
FE_DIR = JUARA_DIR / "fe"
sys.path.insert(0, str(FE_DIR))

from columns import columns_to_rank, load_nocontinuas  # noqa: E402
from paths import NOCONTINUAS_PATH, competencia_nocontinuas_v1_parquet, competencia_parquet_v1  # noqa: E402

DATOS_DIR = DRIFTING_DIR / "datos"
DEFAULT_OUTPUT = DATOS_DIR / "dataset_nocont_nivel.parquet"
JOIN_KEYS = ("numero_de_cliente", "foto_mes")
EXPECTED_ROWS = 983_061

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


def _continuas_from_schema(con: duckdb.DuckDBPyConnection, comp_path: Path) -> list[str]:
    nocontinuas = load_nocontinuas(NOCONTINUAS_PATH)
    comp_sql = _sql_path(comp_path)
    schema_rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{comp_sql}')"
    ).fetchall()
    all_columns = [row[0] for row in schema_rows]
    return columns_to_rank(all_columns, nocontinuas)


def build_dataset(con: duckdb.DuckDBPyConnection, dst: Path) -> list[str]:
    nc_path = competencia_nocontinuas_v1_parquet()
    comp_path = competencia_parquet_v1()
    for path in (nc_path, comp_path):
        if not path.is_file():
            raise SystemExit(f"Archivo inexistente: {path}")

    continuas = _continuas_from_schema(con, comp_path)
    if not continuas:
        raise SystemExit("Sin columnas continuas a unir")

    dst.parent.mkdir(parents=True, exist_ok=True)
    nc_sql = _sql_path(nc_path)
    comp_sql = _sql_path(comp_path)
    dst_sql = _sql_path(dst)
    keys = ", ".join(_quote_ident(k) for k in JOIN_KEYS)
    cont_select = ", ".join(_quote_ident(c) for c in continuas)

    con.execute(
        f"""
        COPY (
          SELECT
            nc.*,
            c.* EXCLUDE ({keys})
          FROM read_parquet('{nc_sql}') nc
          INNER JOIN (
            SELECT {keys}, {cont_select}
            FROM read_parquet('{comp_sql}')
          ) c
            USING ({keys})
        ) TO '{dst_sql}' (FORMAT PARQUET, COMPRESSION 'UNCOMPRESSED')
        """
    )
    return continuas


def _validate(con: duckdb.DuckDBPyConnection, dst: Path, n_continuas: int) -> None:
    dst_sql = _sql_path(dst)

    n_rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{dst_sql}')").fetchone()[0]
    n_dup = con.execute(
        f"""
        SELECT COUNT(*) - COUNT(DISTINCT ({", ".join(JOIN_KEYS)}))
        FROM read_parquet('{dst_sql}')
        """
    ).fetchone()[0]
    n_cols = con.execute(
        f"SELECT COUNT(*) FROM (DESCRIBE SELECT * FROM read_parquet('{dst_sql}'))"
    ).fetchone()[0]
    # Sin pct/lag/delta: datasets con competencia_01_continuas_lag* requieren otro prep.
    forbidden = con.execute(
        f"""
        SELECT COUNT(*)
        FROM (DESCRIBE SELECT * FROM read_parquet('{dst_sql}'))
        WHERE column_name LIKE 'pct_%'
           OR column_name LIKE 'lag1_%'
           OR column_name LIKE 'lag2_%'
           OR column_name LIKE 'delta1_%'
           OR column_name LIKE 'delta2_%'
        """
    ).fetchone()[0]
    meses = con.execute(
        f"""
        SELECT foto_mes, COUNT(*) AS n
        FROM read_parquet('{dst_sql}')
        GROUP BY foto_mes
        ORDER BY foto_mes
        """
    ).fetchall()

    print(f"filas salida: {n_rows} (esperado {EXPECTED_ROWS})")
    print(f"columnas: {n_cols} (continuas unidas: {n_continuas})")
    print("conteo por foto_mes:")
    for foto_mes, n in meses:
        print(f"  {foto_mes}: {n}")

    if n_rows != EXPECTED_ROWS:
        raise SystemExit("Validación fallida: conteo de filas distinto de 983061")
    if n_dup != 0:
        raise SystemExit("Validación fallida: claves duplicadas")
    if forbidden != 0:
        raise SystemExit("Validación fallida: columnas pct/lag/delta presentes")


def main() -> None:
    dst = Path(os.environ.get("DRIFTING_OUTPUT", str(DEFAULT_OUTPUT)))
    print(f"duckdb memory_limit={DUCKDB_MEMORY_LIMIT}")

    con = _connect()
    continuas = build_dataset(con, dst)
    _validate(con, dst, len(continuas))
    print(f"escrito: {dst}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

"""Junio 2021: BAJA+1 y BAJA+2; une parquets por clave."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import duckdb

MIRANDA_DIR = Path(__file__).resolve().parent.parent
JUARA_DIR = MIRANDA_DIR.parent
_DATOS = MIRANDA_DIR / "datos"
FE_DIR = JUARA_DIR / "fe"
sys.path.insert(0, str(FE_DIR))

from paths import (  # noqa: E402
    competencia_nocontinuas_lag1_parquet,
    competencia_nocontinuas_lag2_parquet,
    competencia_nocontinuas_parquet,
    rankings_delta1_parquet,
    rankings_delta2_parquet,
    rankings_lag1_parquet,
    rankings_lag2_parquet,
    rankings_parquet,
)

DUCKDB_MEMORY_LIMIT = os.environ.get("DUCKDB_MEMORY_LIMIT", "4GB")
DUCKDB_THREADS = os.environ.get("DUCKDB_THREADS")
DUCKDB_TEMP_DIRECTORY = os.environ.get("DUCKDB_TEMP_DIRECTORY")
JOIN_KEYS = ("numero_de_cliente", "foto_mes")
MES_FILTER_SQL = "foto_mes % 100 = 6"
_ALLOWED_MONTHS = (6,)

COHORT = os.environ.get("MIRANDA_COHORT", "baja")
SAMPLE_FRAC = float(os.environ.get("MIRANDA_SAMPLE_FRAC", "0.2"))
SAMPLE_SEED = int(os.environ.get("MIRANDA_SAMPLE_SEED", "2026"))

_CLASE_BAJA_SQL = "clase_ternaria IN ('BAJA+1', 'BAJA+2')"
_CLASE_CONTINUA_SQL = "clase_ternaria = 'CONTINUA'"

if COHORT == "baja":
    CLASE_POR_MES_SQL = _CLASE_BAJA_SQL
    DEFAULT_OUTPUT = _DATOS / "dataset_junio.parquet"
elif COHORT == "continua_sample":
    CLASE_POR_MES_SQL = _CLASE_CONTINUA_SQL
    DEFAULT_OUTPUT = _DATOS / "dataset_continua_20_junio.parquet"
else:
    raise SystemExit(f"MIRANDA_COHORT no soportado: {COHORT}")

BASE_WHERE_SQL = f"{MES_FILTER_SQL} AND ({CLASE_POR_MES_SQL})"


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


def _sampled_base_sql(inner: str) -> str:
    """Muestra estratificada por foto_mes (~SAMPLE_FRAC) con orden reproducible."""
    return f"""
    (
      WITH base AS ({inner}),
      ranked AS (
        SELECT
          base.*,
          row_number() OVER (
            PARTITION BY foto_mes
            ORDER BY hash(numero_de_cliente, foto_mes, {SAMPLE_SEED})
          ) AS _rn,
          count(*) OVER (PARTITION BY foto_mes) AS _n
        FROM base
      )
      SELECT * EXCLUDE (_rn, _n)
      FROM ranked
      WHERE _rn <= CAST(ceil(_n * {SAMPLE_FRAC}) AS BIGINT)
    )
    """


def _filtered_source_sql(path: Path, *, base_layer: bool = False) -> str:
    p = _sql_path(path)
    where = BASE_WHERE_SQL if base_layer else MES_FILTER_SQL
    inner = f"SELECT * FROM read_parquet('{p}') WHERE {where}"
    if base_layer and COHORT == "continua_sample":
        return _sampled_base_sql(inner)
    return f"({inner})"


def _copy_join(
    con: duckdb.DuckDBPyConnection,
    left_sql: str,
    right_path: Path,
    out_path: Path,
) -> None:
    right_sql = _filtered_source_sql(right_path)
    out_sql = _sql_path(out_path)
    keys = ", ".join(_quote_ident(k) for k in JOIN_KEYS)
    con.execute(
        f"""
        COPY (
          SELECT
            left_tbl.*,
            right_tbl.* EXCLUDE ({keys})
          FROM ({left_sql}) left_tbl
          INNER JOIN {right_sql} right_tbl
            USING ({keys})
        ) TO '{out_sql}' (FORMAT PARQUET, COMPRESSION 'UNCOMPRESSED')
        """
    )


def _dataset_layers() -> list[tuple[str, Path]]:
    return [
        ("competencia_nocontinuas", competencia_nocontinuas_parquet()),
        ("competencia_nocontinuas_lag1", competencia_nocontinuas_lag1_parquet()),
        ("competencia_nocontinuas_lag2", competencia_nocontinuas_lag2_parquet()),
        ("rankings", rankings_parquet()),
        ("rankings_lag1", rankings_lag1_parquet()),
        ("rankings_lag2", rankings_lag2_parquet()),
        ("rankings_delta1", rankings_delta1_parquet()),
        ("rankings_delta2", rankings_delta2_parquet()),
    ]


def build_dataset(con: duckdb.DuckDBPyConnection, dst: Path) -> None:
    layers = _dataset_layers()
    for label, path in layers:
        if not path.is_file():
            raise SystemExit(f"Archivo inexistente: {path}")

    tmp = Path(tempfile.mkdtemp(prefix="miranda_jun_join_"))
    try:
        base_label, base_path = layers[0]
        accum = tmp / "accum_0.parquet"
        base_sql = _filtered_source_sql(base_path, base_layer=True)
        accum_sql = _sql_path(accum)
        con.execute(
            f"""
            COPY ({base_sql})
            TO '{accum_sql}' (FORMAT PARQUET, COMPRESSION 'UNCOMPRESSED')
            """
        )
        print(f"capa 1/{len(layers)}: {base_label}")

        left_sql = f"SELECT * FROM read_parquet('{accum_sql}')"
        for i, (label, path) in enumerate(layers[1:], start=2):
            next_accum = tmp / f"accum_{i - 1}.parquet"
            print(f"capa {i}/{len(layers)}: {label}")
            _copy_join(con, left_sql, path, next_accum)
            accum.unlink(missing_ok=True)
            accum = next_accum
            left_sql = f"SELECT * FROM read_parquet('{_sql_path(accum)}')"

        dst_sql = _sql_path(dst)
        con.execute(
            f"""
            COPY ({left_sql})
            TO '{dst_sql}' (FORMAT PARQUET, COMPRESSION 'UNCOMPRESSED')
            """
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _validate(con: duckdb.DuckDBPyConnection, dst: Path) -> None:
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
    meses = con.execute(
        f"""
        SELECT DISTINCT foto_mes
        FROM read_parquet('{dst_sql}')
        ORDER BY foto_mes
        """
    ).fetchall()

    ref_path = competencia_nocontinuas_parquet()
    base_ref_sql = _filtered_source_sql(ref_path, base_layer=True)
    n_ref = con.execute(f"SELECT COUNT(*) FROM {base_ref_sql}").fetchone()[0]
    n_bad_clase = con.execute(
        f"""
        SELECT COUNT(*) FROM read_parquet('{dst_sql}')
        WHERE NOT ({CLASE_POR_MES_SQL})
        """
    ).fetchone()[0]
    by_mes_clase = con.execute(
        f"""
        SELECT foto_mes, clase_ternaria, COUNT(*) AS n
        FROM read_parquet('{dst_sql}')
        GROUP BY foto_mes, clase_ternaria
        ORDER BY foto_mes, clase_ternaria
        """
    ).fetchall()

    print(f"filas salida: {n_rows} (referencia base filtrada: {n_ref})")
    print(f"columnas: {n_cols}")
    print(f"foto_mes distintos: {[m[0] for m in meses]}")
    print("conteo por foto_mes y clase_ternaria:")
    for foto_mes, clase, n in by_mes_clase:
        print(f"  {foto_mes} {clase}: {n}")

    if n_rows != n_ref:
        raise SystemExit("Validación fallida: filas distintas a la capa base filtrada")
    if n_dup != 0:
        raise SystemExit("Validación fallida: claves duplicadas")
    if len(meses) != 1 or meses[0][0] % 100 not in _ALLOWED_MONTHS:
        raise SystemExit("Validación fallida: se espera un único foto_mes de junio (mes % 100 = 6)")
    if n_bad_clase != 0:
        raise SystemExit("Validación fallida: clase no cumple reglas de cohorte")


def main() -> None:
    dst = Path(os.environ.get("MIRANDA_OUTPUT", str(DEFAULT_OUTPUT)))
    print(f"duckdb memory_limit={DUCKDB_MEMORY_LIMIT}")
    print(f"cohorte: {COHORT}")
    print(f"filtro mes: {MES_FILTER_SQL}")
    print(f"filtro clase (capa base): {CLASE_POR_MES_SQL}")
    if COHORT == "continua_sample":
        print(f"muestra: {SAMPLE_FRAC * 100:.0f}% por foto_mes (seed={SAMPLE_SEED})")

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

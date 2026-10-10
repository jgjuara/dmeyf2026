"""delta2_v2 (lag1 − lag2) desde continuas v1 lag1 + lag2 → competencia_01_continuas_v1_delta2_v2.parquet."""

from __future__ import annotations

import sys

import duckdb

from columns import KEY_COLUMNS
from gcs_upload import ensure_local_parquet, upload_parquet
from paths import (
    competencia_continuas_v1_delta2_v2_parquet,
    competencia_continuas_v1_lag1_parquet,
    competencia_continuas_v1_lag2_parquet,
)


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _metric_base_names(lag1_columns: list[str]) -> list[str]:
    bases: list[str] = []
    for column in lag1_columns:
        if column in KEY_COLUMNS:
            continue
        if not column.startswith("lag1_"):
            raise SystemExit(f"Columna lag1 inesperada: {column}")
        bases.append(column.removeprefix("lag1_"))
    return bases


def _delta_exprs(base_names: list[str]) -> str:
    parts: list[str] = []
    for base in base_names:
        lag1_col = _quote_ident(f"lag1_{base}")
        lag2_col = _quote_ident(f"lag2_{base}")
        alias = _quote_ident(f"delta2_{base}")
        parts.append(f"l1.{lag1_col} - l2.{lag2_col} AS {alias}")
    return ",\n  ".join(parts)


def main() -> None:
    lag1 = competencia_continuas_v1_lag1_parquet()
    lag2 = competencia_continuas_v1_lag2_parquet()
    dst = competencia_continuas_v1_delta2_v2_parquet()
    ensure_local_parquet(lag1)
    ensure_local_parquet(lag2)
    if not lag1.is_file():
        raise SystemExit(f"Archivo inexistente: {lag1}")
    if not lag2.is_file():
        raise SystemExit(f"Archivo inexistente: {lag2}")

    lag1_sql = str(lag1).replace("'", "''")
    lag2_sql = str(lag2).replace("'", "''")

    con = duckdb.connect()
    schema_rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{lag1_sql}')"
    ).fetchall()
    lag1_columns = [row[0] for row in schema_rows]
    base_names = _metric_base_names(lag1_columns)

    print(f"columnas lag1: {len(lag1_columns)}")
    print(f"columnas delta2: {len(base_names)}")

    delta_exprs = _delta_exprs(base_names)
    dst_sql = str(dst).replace("'", "''")

    con.execute(
        f"""
        COPY (
          SELECT
            l1.numero_de_cliente,
            l1.foto_mes,
            {delta_exprs}
          FROM read_parquet('{lag1_sql}') AS l1
          INNER JOIN read_parquet('{lag2_sql}') AS l2
            USING (numero_de_cliente, foto_mes)
        ) TO '{dst_sql}' (FORMAT PARQUET, COMPRESSION 'UNCOMPRESSED')
        """
    )

    n_lag1 = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{lag1_sql}')"
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
    expected_cols = 2 + len(base_names)

    print(f"filas lag1: {n_lag1}")
    print(f"filas salida: {n_dst}")
    print(f"columnas salida: {n_cols} (esperadas {expected_cols})")

    if n_lag1 != n_dst:
        raise SystemExit("Validación fallida: distinto número de filas")
    if n_dup != 0:
        raise SystemExit("Validación fallida: claves duplicadas en salida")
    if n_cols != expected_cols:
        raise SystemExit("Validación fallida: distinto número de columnas")

    sample_delta = "delta2_mactivos_margen"
    print(f"min/max {sample_delta} por foto_mes (no nulos):")
    rows = con.execute(
        f"""
        SELECT foto_mes,
               MIN({_quote_ident(sample_delta)}),
               MAX({_quote_ident(sample_delta)})
        FROM read_parquet('{dst_sql}')
        WHERE {_quote_ident(sample_delta)} IS NOT NULL
        GROUP BY foto_mes
        ORDER BY foto_mes
        """
    ).fetchall()
    for foto_mes, vmin, vmax in rows:
        print(f"  {foto_mes}: {vmin} .. {vmax}")

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

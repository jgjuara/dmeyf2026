"""delta2_v1 (t0 − lag2) desde continuas v1 + continuas v1 lag2 → competencia_01_continuas_v1_delta2_v1.parquet."""

from __future__ import annotations

import sys

import duckdb

from columns import KEY_COLUMNS
from gcs_upload import ensure_local_parquet, upload_parquet
from paths import (
    competencia_continuas_v1_delta2_v1_parquet,
    competencia_continuas_v1_lag2_parquet,
    competencia_continuas_v1_parquet,
)


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _delta_exprs(metric_columns: list[str]) -> str:
    parts: list[str] = []
    for column in metric_columns:
        col = _quote_ident(column)
        lag2_col = _quote_ident(f"lag2_{column}")
        alias = _quote_ident(f"delta2_{column}")
        parts.append(f"b.{col} - l2.{lag2_col} AS {alias}")
    return ",\n  ".join(parts)


def main() -> None:
    base = competencia_continuas_v1_parquet()
    lag2 = competencia_continuas_v1_lag2_parquet()
    dst = competencia_continuas_v1_delta2_v1_parquet()
    ensure_local_parquet(base)
    ensure_local_parquet(lag2)
    if not base.is_file():
        raise SystemExit(f"Archivo inexistente: {base}")
    if not lag2.is_file():
        raise SystemExit(f"Archivo inexistente: {lag2}")

    base_sql = str(base).replace("'", "''")
    lag2_sql = str(lag2).replace("'", "''")

    con = duckdb.connect()
    schema_rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{base_sql}')"
    ).fetchall()
    all_columns = [row[0] for row in schema_rows]
    metric_columns = [c for c in all_columns if c not in KEY_COLUMNS]

    print(f"columnas base: {len(all_columns)}")
    print(f"columnas delta2: {len(metric_columns)}")

    delta_exprs = _delta_exprs(metric_columns)
    dst_sql = str(dst).replace("'", "''")

    con.execute(
        f"""
        COPY (
          SELECT
            b.numero_de_cliente,
            b.foto_mes,
            {delta_exprs}
          FROM read_parquet('{base_sql}') AS b
          INNER JOIN read_parquet('{lag2_sql}') AS l2
            USING (numero_de_cliente, foto_mes)
        ) TO '{dst_sql}' (FORMAT PARQUET, COMPRESSION 'UNCOMPRESSED')
        """
    )

    n_base = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{base_sql}')"
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

    print(f"filas base: {n_base}")
    print(f"filas salida: {n_dst}")
    print(f"columnas salida: {n_cols} (esperadas {expected_cols})")

    if n_base != n_dst:
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

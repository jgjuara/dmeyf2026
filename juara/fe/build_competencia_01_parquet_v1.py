"""Build competencia_01_v1.parquet (labeled, sin limpieza de variables) from crudo (DuckDB)."""

from __future__ import annotations

import sys

import duckdb

from gcs_upload import ensure_local_file, upload_parquet
from paths import DATA_DIR, competencia_crudo_csv, competencia_parquet_labeled_v1


def _sql_path(path) -> str:
    return str(path).replace("'", "''")


def main() -> None:
    crudo = competencia_crudo_csv()
    dst = competencia_parquet_labeled_v1()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    ensure_local_file(crudo)
    if not crudo.is_file():
        raise SystemExit(f"Archivo inexistente: {crudo}")

    crudo_sql = _sql_path(crudo)
    dst_sql = _sql_path(dst)

    con = duckdb.connect()
    con.execute(
        f"""
        COPY (
          WITH raw AS (
            SELECT
              *,
              row_number() OVER () AS pos
            FROM read_csv('{crudo_sql}', header = true, all_varchar = false)
          ),
          dsimple AS (
            SELECT
              pos,
              numero_de_cliente,
              (CAST(foto_mes AS BIGINT) // 100) * 12
                + (CAST(foto_mes AS BIGINT) % 100) AS periodo0
            FROM raw
          ),
          globals AS (
            SELECT
              max(periodo0) AS periodo_ultimo,
              max(periodo0) - 1 AS periodo_anteultimo
            FROM dsimple
          ),
          ordered AS (
            SELECT
              d.pos,
              d.periodo0,
              LEAD(d.periodo0, 1) OVER (
                PARTITION BY d.numero_de_cliente ORDER BY d.periodo0
              ) AS periodo1,
              LEAD(d.periodo0, 2) OVER (
                PARTITION BY d.numero_de_cliente ORDER BY d.periodo0
              ) AS periodo2,
              g.periodo_ultimo,
              g.periodo_anteultimo
            FROM dsimple d
            CROSS JOIN globals g
          ),
          labeled AS (
            SELECT
              pos,
              CASE
                WHEN periodo0 < periodo_anteultimo
                  AND (periodo0 + 1 = periodo1)
                  AND (periodo2 IS NULL OR periodo0 + 2 < periodo2)
                  THEN 'BAJA+2'
                WHEN periodo0 < periodo_ultimo
                  AND (periodo1 IS NULL OR periodo0 + 1 < periodo1)
                  THEN 'BAJA+1'
                WHEN periodo0 < periodo_anteultimo THEN 'CONTINUA'
                ELSE NULL
              END AS clase_ternaria
            FROM ordered
          )
          SELECT
            r.* EXCLUDE (pos),
            l.clase_ternaria
          FROM raw r
          INNER JOIN labeled l USING (pos)
        ) TO '{dst_sql}' (FORMAT PARQUET, COMPRESSION 'UNCOMPRESSED')
        """
    )

    print("conteo foto_mes × clase_ternaria:")
    rows = con.execute(
        f"""
        SELECT foto_mes, clase_ternaria, count(*) AS n
        FROM read_parquet('{dst_sql}')
        GROUP BY foto_mes, clase_ternaria
        ORDER BY foto_mes, clase_ternaria
        """
    ).fetchall()
    for foto_mes, clase, n in rows:
        print(f"  {foto_mes} {clase}: {n}")

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

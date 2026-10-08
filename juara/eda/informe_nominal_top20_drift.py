"""Top columnas pct_* por drift KS: resumen nominal por mes, KDE y informe Markdown."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import polars as pl

from dataset import EDA_DIR, JUARA_DIR
from densidades_rankings_por_mes import grafico_kde_por_mes, orden_meses
from frecuencias_por_columna import col_safe, serie_float

MES_COL = "foto_mes"
ID_COL = "numero_de_cliente"
DEFAULT_DRIFT = EDA_DIR / "resultados" / "drift_rankings" / "drift_por_columna.csv"
DEFAULT_COMPETENCIA = JUARA_DIR / "data" / "competencia_01_v1.parquet"
DEFAULT_OUT = EDA_DIR / "resultados" / "drift_rankings_nominal"

MEDIAN_CHANGE_THRESH = 0.10
NULL_CHANGE_THRESH = 5.0
CERO_CHANGE_THRESH = 10.0


def pct_a_nominal(pct_col: str) -> str:
    if not pct_col.startswith("pct_"):
        raise ValueError(f"se esperaba prefijo pct_: {pct_col}")
    return pct_col[4:]


def cargar_top_drift(path: Path, top_k: int) -> pl.DataFrame:
    if not path.is_file():
        raise SystemExit(f"Archivo inexistente: {path}")
    drift = pl.read_csv(path)
    if "rank" in drift.columns:
        drift = drift.sort("rank")
    return drift.head(top_k)


def validar_nominales(drift: pl.DataFrame, schema_cols: set[str]) -> list[tuple[str, str]]:
    pares: list[tuple[str, str]] = []
    faltantes: list[str] = []
    for row in drift.iter_rows(named=True):
        pct_col = str(row["columna"])
        nominal = pct_a_nominal(pct_col)
        if nominal not in schema_cols:
            faltantes.append(nominal)
        else:
            pares.append((pct_col, nominal))
    if faltantes:
        raise SystemExit(
            "Columnas nominales ausentes en competencia_01_v1.parquet: "
            + ", ".join(faltantes)
        )
    return pares


def fila_resumen_mes(
    sub: pl.DataFrame,
    col: str,
    mes: int,
    pct_col: str,
    ks_mean: float,
    par_max_ks: str,
) -> dict[str, object]:
    n = sub.height
    raw = sub[col]
    n_null = raw.null_count()
    pct_null = (n_null / n * 100.0) if n else 0.0
    non_null = serie_float(raw.drop_nulls())
    nn = non_null.len()
    if nn == 0:
        stats = {
            "mean": "",
            "std": "",
            "min": "",
            "p25": "",
            "p50": "",
            "p75": "",
            "max": "",
            "pct_cero": "",
            "n_unique": 0,
        }
    else:
        arr = non_null.to_numpy()
        arr = arr[~np.isnan(arr)]
        n_zero = int(np.sum(arr == 0))
        stats = {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr, ddof=0)),
            "min": float(np.min(arr)),
            "p25": float(np.percentile(arr, 25)),
            "p50": float(np.percentile(arr, 50)),
            "p75": float(np.percentile(arr, 75)),
            "max": float(np.max(arr)),
            "pct_cero": (n_zero / len(arr) * 100.0) if len(arr) else 0.0,
            "n_unique": int(raw.n_unique()),
        }
    return {
        "columna_pct": pct_col,
        "columna_nominal": col,
        "foto_mes": mes,
        "ks_mean_consecutivos": ks_mean,
        "par_max_ks": par_max_ks,
        "n": n,
        "n_null": n_null,
        "pct_null": pct_null,
        **stats,
    }


def resumen_por_columna(
    df: pl.DataFrame,
    col: str,
    pct_col: str,
    ks_mean: float,
    par_max_ks: str,
    meses: list[int],
) -> pl.DataFrame:
    filas = [
        fila_resumen_mes(
            df.filter(pl.col(MES_COL) == mes),
            col,
            mes,
            pct_col,
            ks_mean,
            par_max_ks,
        )
        for mes in meses
    ]
    return pl.DataFrame(filas)


def _par_consecutivo_max_salto(
    meses: list[int],
    valores: list[float | None],
) -> tuple[str, float]:
    mejor_par = ""
    mejor = -1.0
    for i in range(len(meses) - 1):
        v0, v1 = valores[i], valores[i + 1]
        if v0 is None or v1 is None or v0 == 0:
            continue
        rel = abs(v1 - v0) / abs(v0)
        if rel > mejor:
            mejor = rel
            mejor_par = f"{meses[i]}-{meses[i + 1]}"
    return mejor_par, mejor


def narrativa_columna(
    resumen: pl.DataFrame,
    par_max_ks: str,
    rank: int,
) -> str:
    meses = resumen["foto_mes"].to_list()
    p50s = [
        float(x) if x != "" and x is not None else None
        for x in resumen["p50"].to_list()
    ]
    nulls = [float(x) for x in resumen["pct_null"].to_list()]
    ceros = [
        float(x) if x != "" and x is not None else None
        for x in resumen["pct_cero"].to_list()
    ]

    frases: list[str] = []
    par_med, salto_med = _par_consecutivo_max_salto(meses, p50s)
    if salto_med >= MEDIAN_CHANGE_THRESH and par_med:
        frases.append(
            f"La mediana varía un {salto_med * 100:.1f}% entre meses consecutivos "
            f"(mayor salto en {par_med})."
        )

    max_null_jump = 0.0
    par_null = ""
    for i in range(len(meses) - 1):
        jump = abs(nulls[i + 1] - nulls[i])
        if jump > max_null_jump:
            max_null_jump = jump
            par_null = f"{meses[i]}-{meses[i + 1]}"
    if max_null_jump >= NULL_CHANGE_THRESH and par_null:
        frases.append(
            f"El porcentaje de nulos cambia {max_null_jump:.1f} p.p. entre "
            f"{par_null.split('-')[0]} y {par_null.split('-')[1]}."
        )

    if ceros and all(c is not None for c in ceros):
        max_cero = max(ceros)
        if max_cero >= 50.0:
            frases.append(
                f"Concentración en cero: hasta {max_cero:.1f}% de los no-nulos en algún mes."
            )
        par_cero, salto_cero = _par_consecutivo_max_salto(meses, ceros)
        if salto_cero >= CERO_CHANGE_THRESH and par_cero and max_cero < 50.0:
            frases.append(
                f"El % en cero varía fuerte ({salto_cero * 100:.1f}% rel.) en {par_cero}."
            )

    if par_max_ks and par_med and par_max_ks.replace("-", "") in par_med.replace("-", ""):
        frases.append(
            f"Coincide con el par de mayor KS en percentiles ({par_max_ks})."
        )
    elif par_max_ks:
        frases.append(
            f"En espacio pct el par de mayor KS fue {par_max_ks} "
            f"(rank drift {rank})."
        )

    if not frases:
        frases.append(
            "Sin saltos marcados en mediana, nulos o cero entre meses consecutivos."
        )
    return " ".join(frases[:4])


def _fmt_num(v: object, dec: int = 4) -> str:
    if v == "" or v is None:
        return "—"
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return "—"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    return f"{float(v):.{dec}f}"


def tabla_md_por_mes(resumen: pl.DataFrame) -> str:
    header = "| Mes | n | % null | p50 | p25 | p75 | % cero |"
    sep = "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    lines = [header, sep]
    for row in resumen.iter_rows(named=True):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["foto_mes"]),
                    _fmt_num(row["n"], 0),
                    _fmt_num(row["pct_null"], 2),
                    _fmt_num(row["p50"], 4),
                    _fmt_num(row["p25"], 4),
                    _fmt_num(row["p75"], 4),
                    _fmt_num(row["pct_cero"], 2),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def sintesis_global(
    drift_top: pl.DataFrame,
    resumen_all: pl.DataFrame,
) -> str:
    grupos: dict[str, list[str]] = {
        "Productos adicionales (montos m*)": [],
        "Saldos USD tarjetas": [],
        "Mora y fechas codificadas": [],
        "Conteos (c*)": [],
        "Otros montos y comisiones": [],
    }
    for row in drift_top.iter_rows(named=True):
        nom = pct_a_nominal(str(row["columna"]))
        if "adicional" in nom or nom in ("mcuenta_corriente", "mcaja_ahorro_dolares"):
            grupos["Productos adicionales (montos m*)"].append(nom)
        elif "msaldodolares" in nom or "msaldopesos" in nom or "msaldototal" in nom:
            grupos["Saldos USD tarjetas"].append(nom)
        elif "Finiciomora" in nom or "fultimo_cierre" in nom:
            grupos["Mora y fechas codificadas"].append(nom)
        elif nom.startswith("c"):
            grupos["Conteos (c*)"].append(nom)
        else:
            grupos["Otros montos y comisiones"].append(nom)

    partes: list[str] = []
    for titulo, cols in grupos.items():
        if not cols:
            continue
        ks_vals = []
        for c in cols:
            sub = resumen_all.filter(pl.col("columna_nominal") == c)
            if sub.height:
                ks_vals.append(float(sub["ks_mean_consecutivos"][0]))
        ks_prom = float(np.mean(ks_vals)) if ks_vals else float("nan")
        partes.append(
            f"- **{titulo}** ({len(cols)} columnas en el top): "
            f"KS media pct ~{ks_prom:.3f}. "
            f"Ejemplos: {', '.join(f'`{c}`' for c in cols[:3])}."
        )
    return "\n".join(partes)


def generar_informe(
    out_root: Path,
    drift_top: pl.DataFrame,
    resumen_all: pl.DataFrame,
    pares: list[tuple[str, str]],
    n_filas: int,
    meses: list[int],
) -> None:
    md_path = out_root / "informe_top20_nominal.md"
    plots_rel = "plots"
    lines: list[str] = [
        "# Distribuciones nominales — top 20 drift (percentiles)",
        "",
        "## Metodología",
        "",
        "Valores leídos de `competencia_01_v1.parquet` (columnas sin prefijo `pct_`). "
        "El ranking por drift proviene del informe previo sobre columnas `pct_*` "
        "(`drift_por_columna.csv`): score principal = media de D de Kolmogorov–Smirnov "
        "entre meses consecutivos.",
        "",
        f"- Filas en competencia: {n_filas:,}",
        f"- Meses (`foto_mes`): {', '.join(str(m) for m in meses)}",
        f"- Columnas analizadas: {len(pares)}",
        "",
        "Métricas por mes en `resumen_por_mes.csv`: cobertura, cuantiles sobre no-nulos, "
        "% en cero y cardinalidad. Las KDE en `plots/` usan la misma grilla que "
        "`densidades_rankings_por_mes.py`; montos muy asimétricos pueden concentrar "
        "densidad cerca de 0 — los cuantiles del CSV complementan la lectura.",
        "",
        "## Índice",
        "",
        "| Rank | Columna nominal | KS media (pct) | Gráfico |",
        "| ---: | --- | ---: | --- |",
    ]

    rank_map = {
        str(r["columna"]): int(r["rank"])
        for r in drift_top.iter_rows(named=True)
    }

    for pct_col, nominal in pares:
        rank = rank_map.get(pct_col, 0)
        row_d = drift_top.filter(pl.col("columna") == pct_col)
        ks = float(row_d["ks_mean_consecutivos"][0]) if row_d.height else float("nan")
        png = f"{plots_rel}/plot_{col_safe(nominal)}.png"
        lines.append(
            f"| {rank} | `{nominal}` | {ks:.4f} | [{png}]({png}) |"
        )

    lines.extend(["", "---", ""])

    for pct_col, nominal in pares:
        rank = rank_map.get(pct_col, 0)
        resumen = resumen_all.filter(pl.col("columna_nominal") == nominal).sort(
            "foto_mes"
        )
        row_d = drift_top.filter(pl.col("columna") == pct_col)
        par_max = str(row_d["par_max_ks"][0]) if row_d.height else ""
        ks = float(row_d["ks_mean_consecutivos"][0]) if row_d.height else float("nan")
        png = f"{plots_rel}/plot_{col_safe(nominal)}.png"

        lines.append(f"## {rank}. `{nominal}` (`{pct_col}`)")
        lines.append("")
        lines.append(
            f"KS media en percentiles: {ks:.4f}; par máx. KS: {par_max}."
        )
        lines.append("")
        lines.append(f"![KDE por mes]({png})")
        lines.append("")
        lines.append(tabla_md_por_mes(resumen))
        lines.append("")
        lines.append(narrativa_columna(resumen, par_max, rank))
        lines.append("")

    lines.extend(
        [
            "## Síntesis",
            "",
            sintesis_global(drift_top, resumen_all),
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drift-csv", type=Path, default=DEFAULT_DRIFT)
    parser.add_argument("--competencia", type=Path, default=DEFAULT_COMPETENCIA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--kde-grid", type=int, default=200)
    args = parser.parse_args()

    if not args.competencia.is_file():
        raise SystemExit(f"Archivo inexistente: {args.competencia}")

    drift_top = cargar_top_drift(args.drift_csv, args.top_k)
    schema = pl.scan_parquet(args.competencia).collect_schema()
    pares = validar_nominales(drift_top, set(schema.names()))

    columnas_leer = [ID_COL, MES_COL] + [nom for _, nom in pares]
    df = pl.read_parquet(args.competencia, columns=columnas_leer)
    meses = orden_meses(df[MES_COL])
    n_filas = df.height

    out_root = args.out
    plots_dir = out_root / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    drift_meta = {
        str(row["columna"]): (
            float(row["ks_mean_consecutivos"]),
            str(row["par_max_ks"]),
        )
        for row in drift_top.iter_rows(named=True)
    }

    resumenes: list[pl.DataFrame] = []
    for pct_col, nominal in pares:
        print(nominal, file=sys.stderr)
        ks_mean, par_max = drift_meta[pct_col]
        res = resumen_por_columna(df, nominal, pct_col, ks_mean, par_max, meses)
        resumenes.append(res)

        titulo = f"{nominal} (nominal; drift {pct_col})"
        out_png = plots_dir / f"plot_{col_safe(nominal)}.png"
        try:
            grafico_kde_por_mes(df, nominal, meses, titulo, out_png, args.kde_grid)
        except ValueError as exc:
            print(f"  KDE omitida: {exc}", file=sys.stderr)

    resumen_all = pl.concat(resumenes)
    resumen_all.write_csv(out_root / "resumen_por_mes.csv")
    generar_informe(out_root, drift_top, resumen_all, pares, n_filas, meses)
    print(f"Salida: {out_root}", file=sys.stderr)


if __name__ == "__main__":
    main()

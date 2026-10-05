"""Drift de distribución por foto_mes en columnas pct_* de rankings.parquet."""

from __future__ import annotations

import argparse
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import ks_2samp

from dataset import EDA_DIR, JUARA_DIR
from frecuencias_por_columna import serie_float

MES_COL = "foto_mes"
RANKINGS_PATH = JUARA_DIR / "data" / "rankings.parquet"


def rankings_path() -> Path:
    if not RANKINGS_PATH.is_file():
        raise SystemExit(f"Archivo inexistente: {RANKINGS_PATH}")
    return RANKINGS_PATH


def orden_meses(series: pl.Series) -> list[int]:
    return sorted(series.unique().to_list())


def valores_mes(df: pl.DataFrame, col: str, mes: int) -> np.ndarray:
    mask = (pl.col(MES_COL) == mes) & pl.col(col).is_not_null()
    s = serie_float(df.filter(mask)[col])
    arr = s.to_numpy()
    return arr[~np.isnan(arr)]


def ks_par(a: np.ndarray, b: np.ndarray) -> float | None:
    if a.size == 0 or b.size == 0:
        return None
    stat, _ = ks_2samp(a, b, method="auto")
    return float(stat)


def drift_columna(
    df: pl.DataFrame,
    col: str,
    meses: list[int],
) -> dict[str, object]:
    por_mes = {mes: valores_mes(df, col, mes) for mes in meses}
    pares_consec = list(zip(meses[:-1], meses[1:], strict=True))
    ks_consec: list[float] = []
    for m0, m1 in pares_consec:
        v = ks_par(por_mes[m0], por_mes[m1])
        if v is not None:
            ks_consec.append(v)

    mean_consec = float(np.mean(ks_consec)) if ks_consec else float("nan")

    max_ks = -1.0
    max_par: str = ""
    for m0, m1 in combinations(meses, 2):
        v = ks_par(por_mes[m0], por_mes[m1])
        if v is None:
            continue
        if v > max_ks:
            max_ks = v
            max_par = f"{m0}-{m1}"

    if max_ks < 0:
        max_ks = float("nan")
        max_par = ""

    n_pares_consec = len(ks_consec)
    return {
        "columna": col,
        "ks_mean_consecutivos": mean_consec,
        "ks_max_par": max_ks if not np.isnan(max_ks) else "",
        "par_max_ks": max_par,
        "n_pares_consecutivos": n_pares_consec,
    }


def escribir_top20_md(
    ranked: pl.DataFrame,
    out_path: Path,
    meses: list[int],
    n_filas: int,
) -> None:
    top = ranked.head(20)
    lineas = [
        "# Drift de distribución por mes (rankings)",
        "",
        "## Metodología",
        "",
        "Para cada columna `pct_*` se extrajeron los valores por `foto_mes` "
        "(NaN omitidos). Entre cada par de meses consecutivos se calculó la "
        "estadística D de Kolmogorov–Smirnov (`scipy.stats.ks_2samp`); el "
        "**score principal** es la media de esos D sobre los pares consecutivos. "
        "Meses constantes o con una sola observación no interrumpen el cálculo. "
        "La columna `par_max_ks` indica el par de meses (cualquier combinación) "
        "con mayor D.",
        "",
        f"- Filas analizadas: {n_filas:,}",
        f"- Meses: {', '.join(str(m) for m in meses)}",
        f"- Columnas `pct_*`: {ranked.height}",
        "",
        "## Top 20 columnas con mayor drift",
        "",
        "| Rank | Columna | KS media (consec.) | KS máx. | Par máx. KS |",
        "| ---: | --- | ---: | ---: | --- |",
    ]
    for i, row in enumerate(top.iter_rows(named=True), start=1):
        mean_v = row["ks_mean_consecutivos"]
        mean_s = f"{mean_v:.4f}" if mean_v == mean_v else "—"
        max_v = row["ks_max_par"]
        if max_v == "" or max_v is None:
            max_s = "—"
        else:
            max_s = f"{float(max_v):.4f}"
        lineas.append(
            f"| {i} | `{row['columna']}` | {mean_s} | {max_s} | {row['par_max_ks']} |"
        )

    lineas.extend(
        [
            "",
            "## Interpretación (top 5)",
            "",
        ]
    )
    bullets = [
        "Mayor KS media implica que la función de distribución acumulada difiere "
        "más entre meses adyacentes; conviene revisar si el cambio es gradual o "
        "concentrado en un salto puntual (`par_max_ks`).",
        "En percentiles de ranking, drift alto suele reflejar cambios en la "
        "población activa, reglas de cálculo o missingness distinto por mes.",
        "Comparar con series de deltas/lags del mismo indicador ayuda a separar "
        "reordenamiento cross-sectional de nivel.",
        "Valores KS cercanos a 1 en un par aislado sugieren casi no solapamiento "
        "de soporte entre esos dos meses.",
        "Priorizar validación de negocio en las columnas top antes de usarlas "
        "como features estables en modelos multi-mes.",
    ]
    for i, row in enumerate(top.head(5).iter_rows(named=True), start=1):
        col = row["columna"]
        mean_v = row["ks_mean_consecutivos"]
        mean_s = f"{mean_v:.4f}" if mean_v == mean_v else "N/A"
        par = row["par_max_ks"] or "N/A"
        lineas.append(
            f"- **{i}. `{col}`**: KS media consecutiva {mean_s}; "
            f"mayor discrepancia entre meses {par}. {bullets[i - 1]}"
        )

    out_path.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=EDA_DIR / "resultados" / "drift_rankings",
        help="Directorio de salida",
    )
    args = parser.parse_args()

    df = pl.read_parquet(rankings_path())
    if MES_COL not in df.columns:
        raise SystemExit(f"Falta columna {MES_COL!r} en {RANKINGS_PATH}")

    meses = orden_meses(df[MES_COL])
    columnas = [c for c in df.columns if c.startswith("pct_")]
    if not columnas:
        raise SystemExit("No hay columnas pct_* en rankings.parquet")

    out_root = args.out
    out_root.mkdir(parents=True, exist_ok=True)

    filas: list[dict[str, object]] = []
    for col in columnas:
        print(col, file=sys.stderr)
        filas.append(drift_columna(df, col, meses))

    ranked = (
        pl.DataFrame(filas)
        .sort("ks_mean_consecutivos", descending=True, nulls_last=True)
        .with_row_index("rank", offset=1)
    )
    csv_path = out_root / "drift_por_columna.csv"
    ranked.write_csv(csv_path)

    md_path = out_root / "top20_drift.md"
    escribir_top20_md(ranked, md_path, meses, df.height)
    print(f"CSV: {csv_path}", file=sys.stderr)
    print(f"MD: {md_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

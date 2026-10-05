"""Por columna: distribución facetada por clase_ternaria.

<= umbral valores únicos: barras de % dentro de cada clase.
> umbral y numérica: KDE facetada (ejes compartidos entre facets).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy.stats import gaussian_kde

from dataset import EDA_DIR, input_path
from frecuencias_por_columna import (
    col_safe,
    serie_es_numerica,
    serie_float,
    _serie_como_valor,
)

CLASE_COL = "clase_ternaria"


def orden_clases(series: pl.Series) -> list[str]:
    preferido = ["CONTINUA", "BAJA+1", "BAJA+2"]
    presentes = series.drop_nulls().unique().to_list()
    orden = [c for c in preferido if c in presentes]
    resto = sorted(c for c in presentes if c not in preferido)
    return orden + resto


def tabla_pct_por_clase(df: pl.DataFrame, col: str) -> pl.DataFrame:
    work = pl.DataFrame(
        {
            "clase": df[CLASE_COL],
            "valor": _serie_como_valor(df[col]),
        }
    )
    counts = work.group_by("clase", "valor").len().rename({"len": "n"})
    totals = work.group_by("clase").len().rename({"len": "total_clase"})
    return (
        counts.join(totals, on="clase")
        .with_columns((pl.col("n") / pl.col("total_clase") * 100).alias("pct"))
        .sort("clase", "valor")
    )


def grafico_barras_pct_por_clase(
    tabla: pl.DataFrame,
    clases: list[str],
    titulo: str,
    out_path: Path,
) -> None:
    valores = (
        tabla.group_by("valor")
        .agg(pl.col("n").sum())
        .sort("n", descending=True)["valor"]
        .to_list()
    )
    n_clases = len(clases)
    fig_w = max(6, len(valores) * 0.25) * max(1, n_clases * 0.55)
    fig, axes = plt.subplots(
        1,
        n_clases,
        figsize=(fig_w, 4),
        sharex=True,
        sharey=True,
        squeeze=False,
    )
    for i, clase in enumerate(clases):
        ax = axes[0, i]
        sub = tabla.filter(pl.col("clase") == clase)
        pct_map = dict(zip(sub["valor"].to_list(), sub["pct"].to_list()))
        pct = [float(pct_map.get(v, 0.0)) for v in valores]
        ax.bar(range(len(valores)), pct)
        ax.set_title(clase, fontsize=9)
        ax.set_xticks(range(len(valores)))
        ax.set_xticklabels(valores, rotation=45, ha="right", fontsize=7)
        if i == 0:
            ax.set_ylabel("% dentro de la clase")
    fig.suptitle(titulo, y=1.02)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def _kde_curvas_por_clase(
    df: pl.DataFrame,
    col: str,
    clases: list[str],
    n_grid: int,
) -> tuple[np.ndarray, dict[str, np.ndarray], float]:
    all_vals: list[float] = []
    curvas: dict[str, np.ndarray] = {}
    for clase in clases:
        mask = (df[CLASE_COL] == clase) & df[col].is_not_null()
        vals = serie_float(df.filter(mask)[col]).to_numpy()
        vals = vals[~np.isnan(vals)]
        if vals.size:
            all_vals.extend(vals.tolist())
    if not all_vals:
        raise ValueError("sin valores numéricos")
    x_min = float(np.min(all_vals))
    x_max = float(np.max(all_vals))
    if x_min == x_max:
        pad = abs(x_min) * 0.01 + 1.0
        x_min -= pad
        x_max += pad
    xs = np.linspace(x_min, x_max, n_grid)
    y_max = 0.0
    for clase in clases:
        mask = (df[CLASE_COL] == clase) & df[col].is_not_null()
        vals = serie_float(df.filter(mask)[col]).to_numpy()
        vals = vals[~np.isnan(vals)]
        if vals.size < 2:
            ys = np.zeros_like(xs)
        else:
            kde = gaussian_kde(vals)
            ys = kde(xs)
            y_max = max(y_max, float(np.max(ys)))
        curvas[clase] = ys
    return xs, curvas, y_max


def grafico_kde_por_clase(
    df: pl.DataFrame,
    col: str,
    clases: list[str],
    titulo: str,
    out_path: Path,
    n_grid: int,
) -> None:
    xs, curvas, y_max = _kde_curvas_por_clase(df, col, clases, n_grid)
    n_clases = len(clases)
    fig, axes = plt.subplots(
        1,
        n_clases,
        figsize=(4 * n_clases, 4),
        sharex=True,
        sharey=True,
        squeeze=False,
    )
    for i, clase in enumerate(clases):
        ax = axes[0, i]
        ax.plot(xs, curvas[clase])
        ax.set_title(clase, fontsize=9)
        ax.set_xlim(xs[0], xs[-1])
        ax.set_ylim(0, y_max * 1.05 if y_max > 0 else 1.0)
        if i == 0:
            ax.set_ylabel("densidad")
        ax.set_xlabel(col, fontsize=8)
    fig.suptitle(titulo, y=1.02)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def procesar_columna(
    df: pl.DataFrame,
    col: str,
    out_root: Path,
    clases: list[str],
    max_categorias: int,
    n_grid: int,
) -> dict[str, str | int]:
    series = df[col]
    n_unique = series.n_unique()
    numerica = serie_es_numerica(series)
    slug = col_safe(col)
    ruta_tabla = out_root / f"tbl_{slug}_por_clase.csv"
    ruta_grafico = out_root / f"plot_{slug}_por_clase.png"

    if n_unique <= max_categorias:
        tabla = tabla_pct_por_clase(df, col)
        tabla.write_csv(ruta_tabla)
        grafico_barras_pct_por_clase(tabla, clases, col, ruta_grafico)
        modo = "barras_pct"
    elif numerica:
        grafico_kde_por_clase(df, col, clases, col, ruta_grafico, n_grid)
        modo = "kde"
        ruta_tabla = None
    else:
        modo = "omitido_alta_cardinalidad_no_numerica"
        ruta_grafico = None
        ruta_tabla = None

    row: dict[str, str | int] = {
        "columna": col,
        "modo": modo,
        "n_unique": n_unique,
        "dtype": "numerica" if numerica else str(series.dtype),
    }
    row["ruta_tabla"] = (
        str(ruta_tabla.relative_to(out_root)) if ruta_tabla is not None else ""
    )
    row["ruta_grafico"] = (
        str(ruta_grafico.relative_to(out_root)) if ruta_grafico is not None else ""
    )
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=EDA_DIR / "resultados" / "frecuencias_por_clase",
        help="Directorio de salida",
    )
    parser.add_argument(
        "--max-categorias",
        type=int,
        default=20,
        help="Máximo de valores únicos para gráfico de barras %",
    )
    parser.add_argument(
        "--kde-grid",
        type=int,
        default=200,
        help="Puntos de la grilla para KDE",
    )
    args = parser.parse_args()

    path = input_path()
    df = pl.read_csv(path, infer_schema_length=0)
    if CLASE_COL not in df.columns:
        raise SystemExit(f"Falta columna {CLASE_COL!r} en {path}")

    clases = orden_clases(df[CLASE_COL])
    out_root = args.out
    out_root.mkdir(parents=True, exist_ok=True)

    columnas = [c for c in df.columns if c != CLASE_COL]
    filas: list[dict[str, str | int]] = []
    for col in columnas:
        print(col, file=sys.stderr)
        filas.append(
            procesar_columna(
                df,
                col,
                out_root,
                clases,
                args.max_categorias,
                args.kde_grid,
            )
        )

    pl.DataFrame(filas).write_csv(out_root / "indice.csv")


if __name__ == "__main__":
    main()

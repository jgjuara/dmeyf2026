"""Por columna pct_* en rankings.parquet: KDE facetada por foto_mes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy.stats import gaussian_kde

from dataset import EDA_DIR, JUARA_DIR
from frecuencias_por_columna import col_safe, serie_float

MES_COL = "foto_mes"
RANKINGS_PATH = JUARA_DIR / "data" / "rankings.parquet"


def rankings_path() -> Path:
    if not RANKINGS_PATH.is_file():
        raise SystemExit(f"Archivo inexistente: {RANKINGS_PATH}")
    return RANKINGS_PATH


def orden_meses(series: pl.Series) -> list[int]:
    return sorted(series.unique().to_list())


def _kde_curvas_por_mes(
    df: pl.DataFrame,
    col: str,
    meses: list[int],
    n_grid: int,
) -> tuple[np.ndarray, dict[int, np.ndarray], float]:
    all_vals: list[float] = []
    for mes in meses:
        mask = (df[MES_COL] == mes) & df[col].is_not_null()
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
    curvas: dict[int, np.ndarray] = {}
    for mes in meses:
        mask = (df[MES_COL] == mes) & df[col].is_not_null()
        vals = serie_float(df.filter(mask)[col]).to_numpy()
        vals = vals[~np.isnan(vals)]
        if vals.size < 2 or float(np.min(vals)) == float(np.max(vals)):
            ys = np.zeros_like(xs)
        else:
            try:
                kde = gaussian_kde(vals)
                ys = kde(xs)
                y_max = max(y_max, float(np.max(ys)))
            except (ValueError, np.linalg.LinAlgError):
                ys = np.zeros_like(xs)
        curvas[mes] = ys
    return xs, curvas, y_max


def grafico_kde_por_mes(
    df: pl.DataFrame,
    col: str,
    meses: list[int],
    titulo: str,
    out_path: Path,
    n_grid: int,
) -> None:
    xs, curvas, y_max = _kde_curvas_por_mes(df, col, meses, n_grid)
    n_meses = len(meses)
    fig, axes = plt.subplots(
        1,
        n_meses,
        figsize=(4 * n_meses, 4),
        sharex=True,
        sharey=True,
        squeeze=False,
    )
    for i, mes in enumerate(meses):
        ax = axes[0, i]
        ax.plot(xs, curvas[mes])
        ax.set_title(str(mes), fontsize=9)
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
    meses: list[int],
    n_grid: int,
) -> dict[str, str | int]:
    slug = col_safe(col)
    ruta_grafico = out_root / f"plot_{slug}.png"
    try:
        grafico_kde_por_mes(df, col, meses, col, ruta_grafico, n_grid)
        modo = "kde"
        ruta_rel = str(ruta_grafico.relative_to(out_root))
    except ValueError:
        modo = "omitido_sin_datos"
        ruta_rel = ""
    return {
        "columna": col,
        "n_meses": len(meses),
        "modo": modo,
        "ruta_grafico": ruta_rel,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=EDA_DIR / "resultados" / "densidades_rankings",
        help="Directorio de salida",
    )
    parser.add_argument(
        "--kde-grid",
        type=int,
        default=200,
        help="Puntos de la grilla para KDE",
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

    filas: list[dict[str, str | int]] = []
    for col in columnas:
        print(col, file=sys.stderr)
        filas.append(procesar_columna(df, col, out_root, meses, args.kde_grid))

    pl.DataFrame(filas).write_csv(out_root / "indice.csv")


if __name__ == "__main__":
    main()

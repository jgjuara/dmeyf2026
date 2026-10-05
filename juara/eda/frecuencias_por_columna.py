"""Por columna: tabla de frecuencias CSV y gráfico (barras % o boxplot).

Límites: IDs numéricos de alta cardinalidad se binnean; lectura completa en memoria.
Columnas string con >max categorías: top 20 + OTROS y barras %.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import polars as pl

from dataset import EDA_DIR, input_path


def col_safe(name: str) -> str:
    safe = re.sub(r"[^\w.-]", "_", name).strip("_")
    return safe or "col"


def dtype_es_numerico(dtype: pl.DataType) -> bool:
    return dtype.is_numeric()


def serie_es_numerica(series: pl.Series) -> bool:
    if dtype_es_numerico(series.dtype):
        return True
    if series.dtype not in (pl.Utf8, pl.String):
        return False
    non_null = series.drop_nulls()
    if non_null.len() == 0:
        return False
    return non_null.cast(pl.Float64, strict=False).null_count() == 0


def serie_float(series: pl.Series) -> pl.Series:
    if series.dtype in (pl.Utf8, pl.String):
        return series.cast(pl.Float64, strict=False)
    return series.cast(pl.Float64)


def clasificar_modo(
    n_unique: int,
    numerica: bool,
    max_categorias: int,
) -> str:
    if n_unique <= max_categorias:
        return "categorica"
    if numerica:
        return "continua"
    return "texto_top20"


def _con_pct(tabla: pl.DataFrame, total: int) -> pl.DataFrame:
    return tabla.with_columns((pl.col("n") / total * 100).alias("pct"))


def _serie_como_valor(series: pl.Series) -> pl.Series:
    return (
        pl.DataFrame({"v": series})
        .select(
            pl.when(pl.col("v").is_null())
            .then(pl.lit("__NULL__"))
            .otherwise(pl.col("v").cast(pl.String))
            .alias("valor")
        )["valor"]
    )


def tabla_categorica(series: pl.Series, total: int) -> pl.DataFrame:
    tabla = (
        pl.DataFrame({"valor": _serie_como_valor(series)})
        .group_by("valor")
        .len()
        .rename({"len": "n"})
        .sort("n", descending=True)
    )
    return _con_pct(tabla, total)


def tabla_top20_otros(series: pl.Series, total: int, top_k: int) -> pl.DataFrame:
    counts = (
        pl.DataFrame({"valor": _serie_como_valor(series)})
        .group_by("valor")
        .len()
        .rename({"len": "n"})
        .sort("n", descending=True)
    )
    if counts.height <= top_k:
        return _con_pct(counts, total)
    top = counts.head(top_k)
    otros_n = int(counts.slice(top_k)["n"].sum())
    otros = pl.DataFrame(
        {"valor": ["OTROS"], "n": [otros_n]},
        schema={"valor": pl.String, "n": counts.schema["n"]},
    )
    return _con_pct(pl.concat([top, otros]), total)


def tabla_binned(series: pl.Series, total: int, n_bins: int) -> pl.DataFrame | None:
    s = serie_float(series.drop_nulls())
    if s.len() == 0 or s.null_count() > 0:
        return None
    if s.n_unique() < 2:
        return None
    lo = float(s.min())  # type: ignore[arg-type]
    hi = float(s.max())  # type: ignore[arg-type]
    if lo == hi:
        return None
    hist = s.hist(bin_count=n_bins)
    if hist.height == 0:
        return None
    bps = hist["breakpoint"].to_list()
    mins = [lo] + bps[:-1]
    tabla = pl.DataFrame(
        {
            "bin": list(range(hist.height)),
            "min": mins,
            "max": bps,
            "n": hist["count"],
        }
    )
    return _con_pct(tabla, total)


def grafico_barras_pct(tabla: pl.DataFrame, titulo: str, out_path: Path) -> None:
    etiquetas = tabla["valor"].to_list()
    pct = tabla["pct"].to_list()
    fig, ax = plt.subplots(figsize=(max(6, len(etiquetas) * 0.35), 4))
    ax.bar(range(len(etiquetas)), pct)
    ax.set_xticks(range(len(etiquetas)))
    ax.set_xticklabels(etiquetas, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("%")
    ax.set_title(titulo)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def grafico_boxplot(series: pl.Series, titulo: str, out_path: Path) -> None:
    valores = serie_float(series.drop_nulls()).to_list()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.boxplot(valores, orientation="vertical")
    ax.set_ylabel("valor")
    ax.set_title(titulo)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def procesar_columna(
    df: pl.DataFrame,
    col: str,
    out_root: Path,
    total: int,
    max_categorias: int,
    n_bins: int,
) -> dict[str, str | int]:
    series = df[col]
    n_unique = series.n_unique()
    numerica = serie_es_numerica(series)
    modo = clasificar_modo(n_unique, numerica, max_categorias)
    dtype_label = "numerica" if numerica else str(series.dtype)

    slug = col_safe(col)
    ruta_tabla = out_root / f"tbl_{slug}.csv"
    ruta_grafico = out_root / f"plot_{slug}.png"

    if modo == "continua":
        tabla = tabla_binned(series, total, n_bins)
        if tabla is not None:
            tabla.write_csv(ruta_tabla)
            grafico_boxplot(series, col, ruta_grafico)
            return {
                "columna": col,
                "modo": modo,
                "n_unique": n_unique,
                "dtype": dtype_label,
                "ruta_tabla": str(ruta_tabla.relative_to(out_root)),
                "ruta_grafico": str(ruta_grafico.relative_to(out_root)),
            }
        modo = "categorica"

    if modo == "categorica":
        tabla = tabla_categorica(series, total)
        grafico_barras_pct(tabla, col, ruta_grafico)
    else:
        tabla = tabla_top20_otros(series, total, max_categorias)
        grafico_barras_pct(tabla, col, ruta_grafico)

    tabla.write_csv(ruta_tabla)
    return {
        "columna": col,
        "modo": modo,
        "n_unique": n_unique,
        "dtype": dtype_label,
        "ruta_tabla": str(ruta_tabla.relative_to(out_root)),
        "ruta_grafico": str(ruta_grafico.relative_to(out_root)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=EDA_DIR / "resultados" / "frecuencias",
        help="Directorio de salida",
    )
    parser.add_argument(
        "--max-categorias",
        type=int,
        default=20,
        help="Umbral de valores únicos para tratar como categoría",
    )
    parser.add_argument(
        "--bins",
        type=int,
        default=20,
        help="Cantidad de bins para columnas continuas",
    )
    args = parser.parse_args()

    path = input_path()
    df = pl.read_csv(path, infer_schema_length=0)
    total = df.height
    out_root = args.out
    out_root.mkdir(parents=True, exist_ok=True)

    filas: list[dict[str, str | int]] = []
    for col in df.columns:
        print(col, file=sys.stderr)
        filas.append(
            procesar_columna(
                df,
                col,
                out_root,
                total,
                args.max_categorias,
                args.bins,
            )
        )

    indice = pl.DataFrame(filas)
    indice.write_csv(out_root / "indice.csv")


if __name__ == "__main__":
    main()

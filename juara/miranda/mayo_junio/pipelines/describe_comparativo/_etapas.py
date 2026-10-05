"""Etapas 0–7 del comparativo BAJA vs CONTINUA."""

from __future__ import annotations

from datetime import UTC, datetime

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from _columns import (
    NOCONTINUAS_COLS,
    PCT_QUANTILES,
    bucket_for_column,
    column_groups,
    columns_in_bucket,
    md_table,
)
from _paths import (
    INFORME_MD,
    PARQUET_BAJA,
    PARQUET_CONTINUA,
    POOL_MES,
    POOLED_FOTO_MES_LABEL,
    PLOTS_DIR,
    TABLAS_DIR,
)
from _stats import (
    attach_fdr_batch,
    attach_fdr_by_foto_mes,
    is_binary_01,
    mann_whitney_u_and_r,
    test_binary_two_sample,
    test_mann_whitney,
)


def _comparison_slices(df: pl.DataFrame) -> list[tuple[str, pl.DataFrame]]:
    if POOL_MES:
        return [(POOLED_FOTO_MES_LABEL, df)]
    meses = sorted(int(m) for m in df["foto_mes"].unique().to_list())
    return [(str(fm), df.filter(pl.col("foto_mes") == fm)) for fm in meses]


def _attach_fdr(frame: pl.DataFrame) -> pl.DataFrame:
    if frame.height == 0:
        return frame
    if POOL_MES:
        return attach_fdr_batch(frame)
    return attach_fdr_by_foto_mes(frame)


def _inferencia_criterio() -> str:
    if POOL_MES:
        return (
            "tests por variable apilando mayo+junio; "
            "FDR Benjamini–Hochberg por etapa (un lote por CSV)"
        )
    return "tests por variable y foto_mes; FDR Benjamini–Hochberg por etapa × foto_mes"


def load_and_stack() -> pl.DataFrame:
    baja = pl.read_parquet(PARQUET_BAJA).with_columns(pl.lit("baja").alias("grupo"))
    continua = pl.read_parquet(PARQUET_CONTINUA).with_columns(pl.lit("continua").alias("grupo"))
    if baja.columns != continua.columns:
        raise SystemExit("Columnas distintas entre parquets BAJA y CONTINUA")
    return pl.concat([baja, continua], how="vertical")


def run_etapa0(df: pl.DataFrame) -> dict[str, pl.DataFrame]:
    TABLAS_DIR.mkdir(parents=True, exist_ok=True)
    volumen = (
        df.group_by("grupo", "foto_mes")
        .len()
        .rename({"len": "n_casos"})
        .sort("grupo", "foto_mes")
    )
    criterios = pl.DataFrame(
        {
            "regla": [
                "cohorte_baja",
                "cohorte_continua",
                "mes",
                "grano",
                "inferencia",
            ],
            "descripcion": [
                "dataset_mayo_junio.parquet: mayo BAJA+1; junio BAJA+1 y BAJA+2",
                "dataset_continua_20_mayo_junio.parquet: CONTINUA, ~20% por foto_mes",
                "foto_mes % 100 IN (5, 6)",
                "(numero_de_cliente, foto_mes, grupo) único",
                _inferencia_criterio(),
            ],
        }
    )
    if POOL_MES:
        criterios = criterios.with_columns(
            pl.when(pl.col("regla") == "mes")
            .then(pl.lit("foto_mes % 100 IN (5, 6); contrastes apilados mayo+junio"))
            .otherwise(pl.col("descripcion"))
            .alias("descripcion")
        )
    n = df.height
    n_unique = df.unique(subset=["numero_de_cliente", "foto_mes", "grupo"]).height
    meses = sorted(int(m) for m in df["foto_mes"].unique().to_list())
    meses_ok = all(m % 100 in (5, 6) for m in meses)
    baja_only = df.filter(pl.col("grupo") == "baja")
    cont_only = df.filter(pl.col("grupo") == "continua")
    n_baja_continua = cont_only.filter(pl.col("clase_ternaria") == "CONTINUA").height
    validacion = pl.DataFrame(
        {
            "chequeo": [
                "columnas_esperadas_712",
                "claves_unicas_grupo",
                "solo_mayo_junio",
                "baja_un_foto_por_cliente",
                "continua_solo_clase",
            ],
            "ok": [
                len(df.columns) == 712,
                n == n_unique,
                meses_ok,
                baja_only.unique(subset=["numero_de_cliente", "foto_mes"]).height == baja_only.height,
                n_baja_continua == cont_only.height,
            ],
            "detalle": [
                str(len(df.columns)),
                f"duplicados={n - n_unique}",
                str(meses),
                f"{baja_only.height} filas",
                f"{n_baja_continua}/{cont_only.height}",
            ],
        }
    )
    grupos = column_groups([c for c in df.columns if c != "grupo"])
    out = {
        "volumen_por_grupo_foto_mes.csv": volumen,
        "criterios_comparativo.csv": criterios,
        "validacion_stack.csv": validacion,
        "grupos_columnas.csv": grupos,
    }
    for name, frame in out.items():
        frame.write_csv(TABLAS_DIR / name)
    failed = validacion.filter(~pl.col("ok"))
    if failed.height:
        msgs = ", ".join(failed["chequeo"].to_list())
        raise SystemExit(f"Validación etapa 0 fallida: {msgs}")
    return out


def run_etapa1(df: pl.DataFrame) -> pl.DataFrame:
    balance = (
        df.group_by("grupo", "foto_mes")
        .len()
        .rename({"len": "n"})
        .sort("grupo", "foto_mes")
    )
    baja_clase = (
        df.filter(pl.col("grupo") == "baja")
        .group_by("clase_ternaria", "foto_mes")
        .len()
        .rename({"len": "n"})
        .sort("foto_mes", "clase_ternaria")
    )
    balance.write_csv(TABLAS_DIR / "etapa1_balance_grupo_foto_mes.csv")
    baja_clase.write_csv(TABLAS_DIR / "etapa1_baja_clase_ternaria.csv")

    fig, ax = plt.subplots(figsize=(6, 4))
    meses = sorted(int(m) for m in df["foto_mes"].unique().to_list())
    x = np.arange(len(meses))
    width = 0.35
    for i, g in enumerate(["baja", "continua"]):
        sub = balance.filter(pl.col("grupo") == g)
        vals = [int(sub.filter(pl.col("foto_mes") == fm)["n"].sum()) for fm in meses]
        ax.bar(x + i * width, vals, width, label=g)
    ax.set_xticks(x + width / 2)
    ax.set_xticklabels([str(m) for m in meses])
    ax.set_ylabel("Casos")
    titulo = "Volumen por grupo y foto_mes (referencia descriptiva)"
    if POOL_MES:
        titulo += " — contrastes inferenciales pooled mayo+junio"
    ax.set_title(titulo)
    ax.legend()
    fig.tight_layout()
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOTS_DIR / "etapa1_balance_grupo.png", dpi=120)
    plt.close(fig)
    return balance


def _compare_nocontinuas(
    df: pl.DataFrame,
    variables: list[str],
    grupo_columnas: str,
) -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    for col in variables:
        if col not in df.columns:
            continue
        union_vals = df[col].drop_nulls().to_numpy()
        es_bin = is_binary_01(union_vals)
        for fm, sub in _comparison_slices(df):
            b = sub.filter(pl.col("grupo") == "baja")[col].to_numpy()
            c = sub.filter(pl.col("grupo") == "continua")[col].to_numpy()
            row: dict[str, object] = {
                "grupo_columnas": grupo_columnas,
                "variable": col,
                "foto_mes": fm,
                "es_binaria_01": es_bin,
                "n_baja": int(np.sum(~np.isnan(b))),
                "n_continua": int(np.sum(~np.isnan(c))),
            }
            if es_bin:
                prev_b = float(np.nanmean(b))
                prev_c = float(np.nanmean(c))
                p, test_name = test_binary_two_sample(b, c)
                row.update(
                    {
                        "prev_baja": prev_b,
                        "prev_continua": prev_c,
                        "efecto": prev_b - prev_c,
                        "mediana_baja": None,
                        "mediana_continua": None,
                        "p_value": p,
                        "test": test_name,
                    }
                )
            else:
                med_b = float(np.nanmedian(b))
                med_c = float(np.nanmedian(c))
                mean_b = float(np.nanmean(b))
                mean_c = float(np.nanmean(c))
                p = test_mann_whitney(b, c)
                row.update(
                    {
                        "prev_baja": None,
                        "prev_continua": None,
                        "efecto": med_b - med_c,
                        "mediana_baja": med_b,
                        "mediana_continua": med_c,
                        "media_baja": mean_b,
                        "media_continua": mean_c,
                        "p_value": p,
                        "test": "mann_whitney",
                    }
                )
            rows.append(row)
    frame = pl.DataFrame(rows)
    if frame.height == 0:
        return frame
    return _attach_fdr(frame)


def _plot_top_nocontinuas(frame: pl.DataFrame, prefix: str) -> None:
    if frame.height == 0:
        return
    for fm, sub in _comparison_slices_from_frame(frame):
        for es_bin, title_suffix in [(True, "flags_delta_prev"), (False, "multivalor_delta_mediana")]:
            g = sub.filter(pl.col("es_binaria_01") == es_bin).sort(pl.col("efecto").abs(), descending=True).head(15)
            if g.height == 0:
                continue
            fig, ax = plt.subplots(figsize=(9, 5))
            vars_ = g["variable"].to_list()[::-1]
            eff = [float(v) for v in g["efecto"].to_list()[::-1]]
            colors = ["#c44e52" if e > 0 else "#4c72b0" for e in eff]
            ax.barh(vars_, eff, color=colors)
            ax.axvline(0, color="gray", lw=0.8)
            ax.set_xlabel("efecto (baja − continua)")
            cohort = "mayo+junio pooled" if POOL_MES else str(fm)
            ax.set_title(f"{prefix} {cohort} — top 15 |efecto| ({title_suffix})")
            fig.tight_layout()
            fname = f"{prefix}_{title_suffix}.png" if POOL_MES else f"{prefix}_{fm}_{title_suffix}.png"
            fig.savefig(PLOTS_DIR / fname, dpi=120)
            plt.close(fig)


def _comparison_slices_from_frame(frame: pl.DataFrame) -> list[tuple[str, pl.DataFrame]]:
    if POOL_MES:
        return [(POOLED_FOTO_MES_LABEL, frame)]
    return [(fm, frame.filter(pl.col("foto_mes") == fm)) for fm in frame["foto_mes"].unique().to_list()]


def run_etapa2(df: pl.DataFrame) -> pl.DataFrame:
    cols = columns_in_bucket(df.columns, "nocontinuas_base")
    frame = _compare_nocontinuas(df, cols, "nocontinuas_base")
    frame.write_csv(TABLAS_DIR / "etapa2_nocontinuas_base.csv")
    _plot_top_nocontinuas(frame, "etapa2")
    return frame


def run_etapa3(df: pl.DataFrame) -> pl.DataFrame:
    cols = columns_in_bucket(df.columns, "nocontinuas_lag1")
    frame = _compare_nocontinuas(df, cols, "nocontinuas_lag1")
    frame.write_csv(TABLAS_DIR / "etapa3_nocontinuas_lag1.csv")
    _plot_top_nocontinuas(frame, "etapa3")
    return frame


def run_etapa4(df: pl.DataFrame) -> pl.DataFrame:
    cols = columns_in_bucket(df.columns, "nocontinuas_lag2")
    frame = _compare_nocontinuas(df, cols, "nocontinuas_lag2")
    frame.write_csv(TABLAS_DIR / "etapa4_nocontinuas_lag2.csv")
    _plot_top_nocontinuas(frame, "etapa4")
    return frame


def _compare_rankings(df: pl.DataFrame, bucket: str, grupo_columnas: str) -> pl.DataFrame:
    cols = columns_in_bucket(df.columns, bucket)
    rows: list[dict[str, object]] = []
    for col in cols:
        for fm, sub in _comparison_slices(df):
            b = sub.filter(pl.col("grupo") == "baja")[col].drop_nulls()
            c = sub.filter(pl.col("grupo") == "continua")[col].drop_nulls()
            bn = b.to_numpy()
            cn = c.to_numpy()
            p, rank_bis = mann_whitney_u_and_r(bn, cn)
            med_b = float(np.median(bn)) if bn.size else float("nan")
            med_c = float(np.median(cn)) if cn.size else float("nan")
            row: dict[str, object] = {
                "grupo_columnas": grupo_columnas,
                "variable": col,
                "foto_mes": fm,
                "n_baja": int(bn.size),
                "n_continua": int(cn.size),
                "media_baja": float(np.mean(bn)) if bn.size else None,
                "media_continua": float(np.mean(cn)) if cn.size else None,
                "mediana_baja": med_b,
                "mediana_continua": med_c,
                "efecto": med_b - med_c,
                "rank_biserial": rank_bis,
                "p_value": p,
                "test": "mann_whitney",
            }
            for q in PCT_QUANTILES:
                qn = int(q * 100)
                row[f"p{qn}_baja"] = float(np.quantile(bn, q)) if bn.size else None
                row[f"p{qn}_continua"] = float(np.quantile(cn, q)) if cn.size else None
            rows.append(row)
    frame = pl.DataFrame(rows)
    if frame.height == 0:
        return frame
    return _attach_fdr(frame)


def _plot_data_for_slice(df: pl.DataFrame, fm: str) -> pl.DataFrame:
    if POOL_MES:
        return df
    return df.filter(pl.col("foto_mes") == int(fm))


def _plot_top_rankings(frame: pl.DataFrame, prefix: str, df: pl.DataFrame) -> None:
    if frame.height == 0:
        return
    cohort_label = "mayo+junio pooled" if POOL_MES else None
    for fm, sub_frame in _comparison_slices_from_frame(frame):
        sig = (
            sub_frame.filter(pl.col("q_value").is_not_null())
            .filter(pl.col("q_value") < 0.05)
            .sort(pl.col("efecto").abs(), descending=True)
            .head(10)
        )
        if sig.height == 0:
            sig = sub_frame.sort(pl.col("efecto").abs(), descending=True).head(10)
        if sig.height == 0:
            continue
        vars_ = sig["variable"].to_list()
        n = len(vars_)
        fig, axes = plt.subplots(1, n, figsize=(2.2 * n, 3.5), squeeze=False)
        plot_df = _plot_data_for_slice(df, fm)
        for j, var in enumerate(vars_):
            ax = axes[0, j]
            data = [
                plot_df.filter(pl.col("grupo") == "baja")[var].drop_nulls().to_numpy(),
                plot_df.filter(pl.col("grupo") == "continua")[var].drop_nulls().to_numpy(),
            ]
            ax.violinplot(data, showmeans=True)
            ax.set_xticks([1, 2])
            ax.set_xticklabels(["baja", "continua"], rotation=45, ha="right")
            ax.set_title(var.replace("pct_", "")[:18], fontsize=8)
        label = cohort_label or str(fm)
        fig.suptitle(f"{prefix} — {label} (top por |efecto| o FDR)")
        fig.tight_layout()
        vname = f"{prefix}_violins_pooled.png" if POOL_MES else f"{prefix}_violins_{fm}.png"
        fig.savefig(PLOTS_DIR / vname, dpi=120)
        plt.close(fig)

        top30 = sub_frame.sort(pl.col("efecto").abs(), descending=True).head(30)
        if top30.height >= 5:
            fig2, ax2 = plt.subplots(figsize=(8, 10))
            ylabels = top30["variable"].to_list()
            effects = top30["efecto"].to_list()
            im = ax2.imshow(
                np.array(effects).reshape(-1, 1),
                aspect="auto",
                cmap="RdBu_r",
                vmin=-max(abs(e) for e in effects),
                vmax=max(abs(e) for e in effects),
            )
            ax2.set_yticks(range(len(ylabels)))
            ax2.set_yticklabels(ylabels, fontsize=7)
            ax2.set_xticks([0])
            ax2.set_xticklabels([label])
            ax2.set_title(f"{prefix} heatmap Δ mediana (top 30 |efecto|)")
            fig2.colorbar(im, ax=ax2, fraction=0.02)
            fig2.tight_layout()
            hname = f"{prefix}_heatmap_pooled.png" if POOL_MES else f"{prefix}_heatmap_{fm}.png"
            fig2.savefig(PLOTS_DIR / hname, dpi=120)
            plt.close(fig2)


def run_etapa5(df: pl.DataFrame) -> pl.DataFrame:
    frame = _compare_rankings(df, "rankings_pct", "rankings_pct")
    frame.write_csv(TABLAS_DIR / "etapa5_rankings_pct.csv")
    _plot_top_rankings(frame, "etapa5", df)
    return frame


def run_etapa6(df: pl.DataFrame) -> dict[str, pl.DataFrame]:
    specs = [
        ("rankings_lag1_pct", "etapa6a_rankings_lag1_pct.csv"),
        ("rankings_lag2_pct", "etapa6b_rankings_lag2_pct.csv"),
        ("rankings_delta1_pct", "etapa6c_rankings_delta1_pct.csv"),
        ("rankings_delta2_pct", "etapa6d_rankings_delta2_pct.csv"),
    ]
    out: dict[str, pl.DataFrame] = {}
    combined: list[pl.DataFrame] = []
    for bucket, fname in specs:
        frame = _compare_rankings(df, bucket, bucket)
        frame.write_csv(TABLAS_DIR / fname)
        prefix = fname.replace(".csv", "")
        _plot_top_rankings(frame, prefix, df)
        out[fname] = frame
        combined.append(frame)
    pl.concat(combined).write_csv(TABLAS_DIR / "etapa6_rankings_lag_delta_combined.csv")
    return out


def run_etapa7(all_frames: list[pl.DataFrame]) -> pl.DataFrame:
    unified = pl.concat([f for f in all_frames if f.height > 0], how="diagonal_relaxed")
    resumen = (
        unified.sort(pl.col("efecto").abs(), descending=True)
        .select(
            "grupo_columnas",
            "variable",
            "foto_mes",
            "efecto",
            "p_value",
            "q_value",
            "test",
        )
        .head(200)
    )
    resumen.write_csv(TABLAS_DIR / "resumen_top_efectos.csv")
    return resumen


def write_informe(
    df: pl.DataFrame,
    etapa0: dict[str, pl.DataFrame],
    resumen: pl.DataFrame,
    frames_etapa2_6: list[pl.DataFrame],
) -> None:
    volumen = etapa0["volumen_por_grupo_foto_mes.csv"]
    criterios = etapa0["criterios_comparativo.csv"]
    grupos = etapa0["grupos_columnas.csv"]
    validacion = etapa0["validacion_stack.csv"]

    n_baja = int(df.filter(pl.col("grupo") == "baja").height)
    n_cont = int(df.filter(pl.col("grupo") == "continua").height)

    top20 = resumen.head(20)
    sig_counts: list[tuple[str, int]] = []
    for f in frames_etapa2_6:
        if f.height == 0:
            continue
        gc = str(f["grupo_columnas"][0])
        n_sig = f.filter(pl.col("q_value").is_not_null() & (pl.col("q_value") < 0.05)).height
        sig_counts.append((gc, n_sig))

    sig_tbl = pl.DataFrame({"grupo_columnas": [s[0] for s in sig_counts], "n_q_lt_0_05": [s[1] for s in sig_counts]})

    nocont_base = [c for c in NOCONTINUAS_COLS if c in df.columns]
    dominio_txt = (
        f"Nocontinuas base ({len(nocont_base)} flags/conteos): productos, tarjetas, seguros y digital "
        f"(`thomebanking`, `cmobile_app_trx`, …). Rankings `pct_*` y capas lag/delta: rentabilidad, saldos, "
        f"comisiones y dinámica mes a mes."
    )

    if POOL_MES:
        titulo = "# Informe comparativo: BAJA vs CONTINUA (mayo–junio, pooled)"
        inferencia_nocont = (
            "Por cada variable (mayo+junio apilados): prevalencia o mediana por grupo; "
            "chi-cuadrado/Fisher (0/1) o Mann–Whitney; efecto = baja − continua; "
            "FDR Benjamini–Hochberg por etapa (un lote por CSV)."
        )
        sig_caption = "Significativos FDR (q < 0,05) por capa (una fila por variable):"
        limitaciones = """### Limitaciones

- CONTINUA es ~20% del universo por mes: alto poder estadístico; priorizar **tamaño de efecto** además de `q_value`.
- Los contrastes apilan filas de mayo y junio; la mezcla de cohortes BAJA (`BAJA+1` / `BAJA+2` en junio) no se estratifica en la inferencia.
- Los `pct_*` (y capas lag/delta derivadas) se calcularon como `PERCENT_RANK` **intra-mes**; al contrastar grupos pooled, baja y continua de un mismo mes comparten escala, pero mayo y junio no son comparables en nivel absoluto del percentil.
- BAJA en junio agrega `BAJA+1` y `BAJA+2`."""
        ejecucion = """```bash
cd juara/miranda/mayo_junio
uv run python prep/join_mayo_junio.py
uv run python prep/join_continua_20_mayo_junio.py
cd pipelines/describe_comparativo && uv run python run_comparativo.py --pool-mes
```"""
    else:
        titulo = "# Informe comparativo: BAJA vs CONTINUA (mayo–junio)"
        inferencia_nocont = (
            "Por cada variable y `foto_mes`: prevalencia o mediana por grupo; chi-cuadrado/Fisher (0/1) o "
            "Mann–Whitney; efecto = baja − continua; FDR por mes."
        )
        sig_caption = "Significativos FDR (q < 0,05) por capa (todas las filas variable×mes):"
        limitaciones = """### Limitaciones

- CONTINUA es ~20% del universo por mes: alto poder estadístico; priorizar **tamaño de efecto** además de `q_value`.
- Los `pct_*` son `PERCENT_RANK` intra-mes; no mezclar meses en una sola escala absoluta.
- BAJA en junio agrega `BAJA+1` y `BAJA+2`."""
        ejecucion = """```bash
cd juara/miranda/mayo_junio
uv run python prep/join_mayo_junio.py
uv run python prep/join_continua_20_mayo_junio.py
cd pipelines/describe_comparativo && uv run python run_comparativo.py
```"""

    body = f"""{titulo}

Generado: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")}

Fuentes: `{PARQUET_BAJA.name}` (baja) y `{PARQUET_CONTINUA.name}` (continua 20% por mes).

## 0. Criterios y volumen

{md_table(criterios)}

### Conteos por grupo y foto_mes

{md_table(volumen)}

- Filas baja: {n_baja}; filas continua: {n_cont}; total apilado: {df.height}.

![Balance grupo](plots/etapa1_balance_grupo.png)

### Validación del stack

{md_table(validacion)}

## 1. Balance y subtipos BAJA

Dentro de `grupo=baja`, mayo concentra `BAJA+1`; junio mezcla `BAJA+1` y `BAJA+2`. No se contrastan esas clases como etapa principal.

Ver `tablas/etapa1_baja_clase_ternaria.csv`.

## 2–4. Nocontinuas (base, lag1, lag2)

{inferencia_nocont}

| Artefacto | Variables |
| --- | --- |
| `etapa2_nocontinuas_base.csv` | capa base |
| `etapa3_nocontinuas_lag1.csv` | t−1 |
| `etapa4_nocontinuas_lag2.csv` | t−2 |

Los lags capturan historia reciente frente al mes actual de la foto.

## 5–6. Rankings percentiles (126 columnas por capa)

Mann–Whitney sobre `pct_*`, `lag1_pct_*`, `lag2_pct_*`, `delta1_pct_*`, `delta2_pct_*`. Efecto reportado: Δ mediana (baja − continua).

{md_table(grupos)}

{sig_caption}

{md_table(sig_tbl)}

## 7. Síntesis de señal

Top 20 efectos globales (|efecto|) unificando etapas 2–6:

{md_table(top20, float_fmt=".6f")}

Tabla completa: `tablas/resumen_top_efectos.csv`.

### Lectura por dominio

{dominio_txt}

Comparar `delta*_pct_*` con niveles `pct_*` ayuda a separar posición relativa intra-mes de cambio respecto a lags.

{limitaciones}

## Ejecución

{ejecucion}
"""
    INFORME_MD.parent.mkdir(parents=True, exist_ok=True)
    INFORME_MD.write_text(body, encoding="utf-8")


def run_all() -> tuple[pl.DataFrame, pl.DataFrame]:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    for old in PLOTS_DIR.glob("*.png"):
        old.unlink()
    df = load_and_stack()
    etapa0 = run_etapa0(df)
    run_etapa1(df)
    e2 = run_etapa2(df)
    e3 = run_etapa3(df)
    e4 = run_etapa4(df)
    e5 = run_etapa5(df)
    e6_dict = run_etapa6(df)
    frames = [e2, e3, e4, e5] + list(e6_dict.values())
    resumen = run_etapa7(frames)
    write_informe(df, etapa0, resumen, frames)
    return df, resumen

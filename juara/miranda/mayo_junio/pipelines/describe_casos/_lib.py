"""Lógica compartida del análisis descriptivo (cohorte unificada, sin estratificar por clase)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.pyplot as plt
import polars as pl

from _paths import COHORT_PRESET, DATASET_PARQUET, INFORME_MD, PLOTS_DIR, TABLAS_DIR

_FE_DIR = Path(__file__).resolve().parents[4] / "fe"
if str(_FE_DIR) not in sys.path:
    sys.path.insert(0, str(_FE_DIR))
from column_buckets import bucket_for_column  # noqa: E402

NOCONTINUAS_COLS = [
    "active_quarter",
    "cliente_vip",
    "internet",
    "tcuentas",
    "ccuenta_corriente",
    "cdescubierto_preacordado",
    "ctarjeta_visa",
    "ctarjeta_master",
    "cseguro_vida",
    "cseguro_vivienda",
    "cseguro_accidentes_personales",
    "tcallcenter",
    "thomebanking",
    "ccajas_transacciones",
    "tmobile_app",
    "cmobile_app_trx",
    "Master_delinquency",
    "Master_status",
    "Visa_delinquency",
    "Visa_status",
    "ctarjeta_debito",
    "cseguro_auto",
    "cforex",
    "cforex_buy",
    "cforex_sell",
    "ccheques_depositados_rechazados",
]

PCT_COLS = [
    "pct_cliente_edad",
    "pct_cliente_antiguedad",
    "pct_mrentabilidad",
    "pct_mrentabilidad_annual",
    "pct_mcomisiones",
    "pct_cproductos",
    "pct_mcuentas_saldo",
    "pct_ctrx_quarter",
    "pct_chomebanking_transacciones",
    "pct_mautoservicio",
    "pct_mpayroll",
]

PCT_QUANTILES = (0.1, 0.25, 0.5, 0.75, 0.9)


def load_dataset() -> pl.DataFrame:
    return pl.read_parquet(DATASET_PARQUET)


def column_groups(columns: list[str]) -> pl.DataFrame:
    counts: dict[str, int] = {}
    for c in columns:
        b = bucket_for_column(c)
        counts[b] = counts.get(b, 0) + 1
    return pl.DataFrame({"grupo": list(counts.keys()), "n_columnas": list(counts.values())}).sort(
        "grupo"
    )


def cohort_slices(df: pl.DataFrame, *, include_todos: bool = True) -> list[tuple[str, pl.DataFrame]]:
    """Subconjuntos por foto_mes; opcionalmente la cohorte completa (válido para variables brutas)."""
    out: list[tuple[str, pl.DataFrame]] = []
    if include_todos:
        out.append(("todos", df))
    for part in df.partition_by("foto_mes", maintain_order=True):
        fm = int(part["foto_mes"][0])
        out.append((str(fm), part))
    return out


def foto_mes_slices(df: pl.DataFrame) -> list[tuple[str, pl.DataFrame]]:
    """Solo particiones por foto_mes (percentiles pct_* son relativos a cada mes)."""
    return cohort_slices(df, include_todos=False)


def tabla_resumen_volumen(df: pl.DataFrame) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "metrica": [
                "filas",
                "columnas",
                "clientes_distintos",
                "foto_mes_distintos",
            ],
            "valor": [
                df.height,
                len(df.columns),
                df["numero_de_cliente"].n_unique(),
                df["foto_mes"].n_unique(),
            ],
        }
    )


def tabla_conteos_foto_mes(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.group_by("foto_mes")
        .len()
        .rename({"len": "n_casos"})
        .sort("foto_mes")
    )


def tabla_criterios_seleccion() -> pl.DataFrame:
    if COHORT_PRESET.key == "continua_20":
        rows = [
            ("mes", "foto_mes % 100 IN (5, 6)"),
            ("clase", "solo CONTINUA"),
            ("muestra", "20% de casos por foto_mes (ceil(n×0.2), hash reproducible)"),
            ("clave_grano", "(numero_de_cliente, foto_mes) único por fila"),
            ("analisis", "cohorte unificada CONTINUA muestreada"),
        ]
    else:
        rows = [
            ("mes", "foto_mes % 100 IN (5, 6)"),
            ("mayo_clase", "solo BAJA+1"),
            ("junio_clase", "BAJA+1 y BAJA+2"),
            ("clave_grano", "(numero_de_cliente, foto_mes) único por fila"),
            ("analisis", "cohorte unificada; no se estratifica por clase_ternaria"),
        ]
    return pl.DataFrame({"regla": [r[0] for r in rows], "descripcion": [r[1] for r in rows]})


def tabla_clientes_por_foto_mes(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.group_by("numero_de_cliente")
        .agg(pl.col("foto_mes").n_unique().alias("n_fotos_mes"))
        .group_by("n_fotos_mes")
        .len()
        .rename({"len": "n_clientes"})
        .sort("n_fotos_mes")
    )


def tabla_resumen_nocontinuas(df: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    for col in NOCONTINUAS_COLS:
        if col not in df.columns:
            continue
        vmax = int(df[col].max())  # type: ignore[arg-type]
        es_01 = vmax <= 1
        for foto_mes, sub in cohort_slices(df):
            n = sub.height
            media = sub[col].mean()
            row: dict[str, object] = {
                "variable": col,
                "foto_mes": foto_mes,
                "n": n,
                "media": media,
                "max_val": vmax,
                "es_binaria_01": es_01,
            }
            row["prevalencia"] = float(sub[col].sum()) / n if es_01 and n else None
            rows.append(row)
    return pl.DataFrame(rows).sort("variable", "foto_mes")


def tabla_validacion(df: pl.DataFrame) -> pl.DataFrame:
    n = df.height
    n_unique_keys = df.unique(subset=["numero_de_cliente", "foto_mes"]).height
    meses = sorted(int(m) for m in df["foto_mes"].unique().to_list())
    meses_ok = all(m % 100 in (5, 6) for m in meses)
    conteo_meses = df.group_by("foto_mes").len().sort("foto_mes")
    sum_conteos = int(conteo_meses["len"].sum())
    clientes_un_foto = (
        df.group_by("numero_de_cliente")
        .agg(pl.col("foto_mes").n_unique().alias("n"))
        .filter(pl.col("n") == 1)
        .height
    )
    n_continua = (
        df.filter(pl.col("clase_ternaria") == "CONTINUA").height if "clase_ternaria" in df.columns else 0
    )
    checks: list[tuple[str, bool, str]] = [
        ("filas_igual_suma_por_mes", n == sum_conteos, f"{n} vs {sum_conteos}"),
        ("claves_unicas", n == n_unique_keys, f"duplicados={n - n_unique_keys}"),
        ("solo_mayo_junio", meses_ok, str(meses)),
        ("columnas_esperadas_711", len(df.columns) == 711, str(len(df.columns))),
    ]
    if COHORT_PRESET.key == "continua_20":
        n_clientes = df["numero_de_cliente"].n_unique()
        checks.append(("solo_clase_continua", n_continua == n, f"{n_continua}/{n}"))
        checks.append(
            (
                "clientes_distintos_leq_filas",
                n_clientes <= n,
                f"clientes={n_clientes}, filas={n}",
            )
        )
    else:
        checks.append(
            ("un_foto_mes_por_cliente", clientes_un_foto == n, f"{clientes_un_foto}/{n}")
        )
    return pl.DataFrame(
        {
            "chequeo": [c[0] for c in checks],
            "ok": [c[1] for c in checks],
            "detalle": [c[2] for c in checks],
        }
    )


def tabla_percentiles_pct(df: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    for col in PCT_COLS:
        if col not in df.columns:
            continue
        for foto_mes, sub in foto_mes_slices(df):
            s = sub[col].drop_nulls()
            if s.len() == 0:
                continue
            row: dict[str, object] = {
                "variable": col,
                "foto_mes": foto_mes,
                "media": s.mean(),
                "std": s.std(),
            }
            for q in PCT_QUANTILES:
                row[f"p{int(q * 100)}"] = s.quantile(q)
            rows.append(row)
    return pl.DataFrame(rows).sort("variable", "foto_mes")


def plot_conteos_foto_mes(conteos: pl.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(5, 4))
    labels = [str(v) for v in conteos["foto_mes"].to_list()]
    ax.bar(labels, conteos["n_casos"].to_list(), color=["#4c72b0", "#55a868"])
    ax.set_ylabel("Casos")
    titulo = (
        "Casos por foto_mes (CONTINUA, 20% por mes)"
        if COHORT_PRESET.key == "continua_20"
        else "Casos por foto_mes (cohorte unificada)"
    )
    ax.set_title(titulo)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "conteos_foto_mes.png", dpi=120)
    plt.close(fig)


def plot_prevalencia_flags(resumen: pl.DataFrame) -> None:
    g = (
        resumen.filter(pl.col("foto_mes") == "todos")
        .filter(pl.col("es_binaria_01"))
        .sort("prevalencia", descending=True)
    )
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(g["variable"].to_list()[::-1], g["prevalencia"].to_list()[::-1], color="#4c72b0")
    ax.set_xlabel("Prevalencia (proporción igual a 1)")
    flag_title = (
        "Flags 0/1 — CONTINUA (20% por mes)"
        if COHORT_PRESET.key == "continua_20"
        else "Flags 0/1 — cohorte completa"
    )
    ax.set_title(flag_title)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "prevalencia_flags_01.png", dpi=120)
    plt.close(fig)


def plot_hist_pct(df: pl.DataFrame) -> None:
    cols = ["pct_mrentabilidad", "pct_cproductos", "pct_mcuentas_saldo"]
    meses = sorted(int(m) for m in df["foto_mes"].unique().to_list())
    fig, axes = plt.subplots(len(meses), len(cols), figsize=(11, 3.2 * len(meses)), squeeze=False)
    for i, fm in enumerate(meses):
        sub = df.filter(pl.col("foto_mes") == fm)
        for j, col in enumerate(cols):
            ax = axes[i, j]
            ax.hist(sub[col].drop_nulls().to_numpy(), bins=30, color="#4c72b0", alpha=0.85, density=True)
            ax.set_title(f"{fm} — {col.replace('pct_', '')}")
            ax.set_xlabel("percentil intra-mes")
    fig.suptitle("Distribución de percentiles (referencia = universo del mismo foto_mes)")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "hist_pct_por_foto_mes.png", dpi=120)
    plt.close(fig)


def md_table(df: pl.DataFrame, float_fmt: str = ".4f") -> str:
    cols = df.columns
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for row in df.iter_rows():
        cells: list[str] = []
        for v in row:
            if v is None:
                cells.append("")
            elif isinstance(v, float):
                cells.append(format(v, float_fmt))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_tablas(df: pl.DataFrame) -> dict[str, pl.DataFrame]:
    TABLAS_DIR.mkdir(parents=True, exist_ok=True)
    tables = {
        "resumen_volumen.csv": tabla_resumen_volumen(df),
        "conteos_foto_mes.csv": tabla_conteos_foto_mes(df),
        "criterios_seleccion.csv": tabla_criterios_seleccion(),
        "grupos_columnas.csv": column_groups(df.columns),
        "clientes_por_cantidad_fotos_mes.csv": tabla_clientes_por_foto_mes(df),
        "resumen_nocontinuas.csv": tabla_resumen_nocontinuas(df),
        "percentiles_variables_pct.csv": tabla_percentiles_pct(df),
        "validacion_dataset.csv": tabla_validacion(df),
    }
    for name, frame in tables.items():
        frame.write_csv(TABLAS_DIR / name)
    failed = tables["validacion_dataset.csv"].filter(~pl.col("ok"))
    if failed.height:
        msgs = ", ".join(failed["chequeo"].to_list())
        raise SystemExit(f"Validación del dataset fallida: {msgs}")
    return tables


def write_plots(df: pl.DataFrame, tables: dict[str, pl.DataFrame]) -> None:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    for old in PLOTS_DIR.glob("*.png"):
        old.unlink()
    plot_conteos_foto_mes(tables["conteos_foto_mes.csv"])
    plot_prevalencia_flags(tables["resumen_nocontinuas.csv"])
    plot_hist_pct(df)


def write_informe(tables: dict[str, pl.DataFrame]) -> None:
    resumen = tables["resumen_volumen.csv"]
    conteos = tables["conteos_foto_mes.csv"]
    grupos = tables["grupos_columnas.csv"]
    criterios = tables["criterios_seleccion.csv"]
    clientes_fm = tables["clientes_por_cantidad_fotos_mes.csv"]
    nocont = tables["resumen_nocontinuas.csv"]
    pct_tbl = tables["percentiles_variables_pct.csv"]
    validacion = tables["validacion_dataset.csv"]

    prev_global = (
        nocont.filter(pl.col("foto_mes") == "todos")
        .filter(pl.col("es_binaria_01"))
        .sort("prevalencia", descending=True)
        .select("variable", "prevalencia")
        .head(12)
    )
    medias_conteo = (
        nocont.filter(pl.col("foto_mes") == "todos")
        .filter(~pl.col("es_binaria_01"))
        .sort("media", descending=True)
        .select("variable", "media", "max_val")
        .head(8)
    )
    pct_por_mes = (
        pct_tbl.select("foto_mes", "variable", "media", "p50", "p90")
        .sort("foto_mes", "variable")
    )

    n_total = int(resumen.filter(pl.col("metrica") == "filas")["valor"].item())
    n_clientes = int(resumen.filter(pl.col("metrica") == "clientes_distintos")["valor"].item())
    solo_un_mes = int(clientes_fm.filter(pl.col("n_fotos_mes") == 1)["n_clientes"].item())
    n_mayo = int(conteos.filter(pl.col("foto_mes") == 202105)["n_casos"].sum())
    n_junio = int(conteos.filter(pl.col("foto_mes") == 202106)["n_casos"].sum())
    if COHORT_PRESET.key == "continua_20":
        grano_txt = (
            f"{n_total} observaciones cliente–mes (`CONTINUA`); "
            f"{n_clientes} clientes distintos ({solo_un_mes} con una sola foto en la muestra)."
        )
    else:
        grano_txt = (
            f"{n_total} observaciones cliente–mes; "
            f"cada uno de los {solo_un_mes} clientes aparece en un único `foto_mes`."
        )

    if COHORT_PRESET.key == "continua_20":
        titulo_informe = "Informe descriptivo: CONTINUA (20% por mes, mayo–junio)"
        nota_clase = (
            "Cohorte `CONTINUA` en mayo y junio; el join aplica ~20% de casos **por** `foto_mes` "
            "(misma lógica que `join_continua_20_mayo_junio.py`)."
        )
    else:
        titulo_informe = "Informe descriptivo: casos seleccionados (mayo–junio)"
        nota_clase = (
            "El parquet incluye `clase_ternaria` como variable de etiqueta; el perfil descriptivo "
            "trata la muestra como una sola cohorte."
        )

    body = f"""# {titulo_informe}

Generado: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")}

Fuente: `{DATASET_PARQUET.name}` (construido con `{COHORT_PRESET.join_script}`).

## 1. Criterios de selección

{md_table(criterios)}

{nota_clase}

## 2. Volumen y grano

{md_table(resumen)}

{grano_txt}

### Conteo por foto_mes

{md_table(conteos)}

- `202105`: {n_mayo} casos.
- `202106`: {n_junio} casos.

![Conteos por foto_mes](plots/conteos_foto_mes.png)

## 3. Validación del parquet

{md_table(validacion)}

## 4. Estructura de columnas

{md_table(grupos)}

Las columnas `pct_*` son `PERCENT_RANK` **por** `foto_mes` (ver `build_rankings.py`). No se promedian entre meses en una sola escala: los estadísticos de la sección 6 se calculan por `foto_mes`. Los prefijos `lag1_` / `lag2_` y `delta1_pct_` / `delta2_pct_` provienen de capas de historia y variación.

## 5. Variables nocontinuas (capa base)

Flags estrictamente 0/1 (`max_val <= 1` en la cohorte); las doce mayores prevalencias:

{md_table(prev_global, float_fmt=".3f")}

Variables con valores múltiples (media y máximo en la cohorte):

{md_table(medias_conteo, float_fmt=".3f")}

![Prevalencia flags 0/1](plots/prevalencia_flags_01.png)

Medias y prevalencias por `foto_mes` y cohorte `todos` (variables brutas): `tablas/resumen_nocontinuas.csv`.

## 6. Percentiles de variables continuas

Por `foto_mes` (cada valor `pct_*` es relativo al universo de competencia de ese mes):

{md_table(pct_por_mes, float_fmt=".3f")}

No son montos absolutos. Mezclar filas de distintos `foto_mes` en un solo histograma o media global distorsionaría la interpretación.

![Histogramas por foto_mes](plots/hist_pct_por_foto_mes.png)

Tabla completa: `tablas/percentiles_variables_pct.csv`.

## 7. Ejecución

Desde `juara/miranda/mayo_junio/`:

```bash
uv run python {COHORT_PRESET.join_script}
cd pipelines/describe_casos && uv run python {COHORT_PRESET.run_script}
```

| Artefacto | Descripción |
| --- | --- |
| `tablas/*.csv` | Tablas del análisis |
| `plots/*.png` | Gráficos referenciados |
| `{INFORME_MD.name}` | Este informe |
"""
    INFORME_MD.parent.mkdir(parents=True, exist_ok=True)
    INFORME_MD.write_text(body, encoding="utf-8")


def run() -> None:
    df = load_dataset()
    tables = write_tablas(df)
    write_plots(df, tables)
    write_informe(tables)

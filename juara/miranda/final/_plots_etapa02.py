"""Etapa 02: rasgos al anclaje vs CONTINUA (10 gráficos)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from _metrics import (
    TemporalMetrics,
    anchor_snapshot,
    calcular_metricas_temporales,
    contrastes_ancla,
    contrastes_subgrupos,
    dominio_matrix,
    prevalencia_flags,
)
from _paths import PLOTS_DIR
from _plot_utils import savefig

OUT = PLOTS_DIR / "etapa_02"


def run(panel: pl.DataFrame, metricas: TemporalMetrics | None = None) -> list[str]:
    """Genera diez gráficos de efecto con estratos y persistencia explícitos."""

    metricas = metricas or calcular_metricas_temporales(panel)
    paths: list[str] = []
    aggregated = metricas.contrastes_agregados.with_columns(
        pl.col("cohens_d_ponderado").abs().alias("_abs_d")
    ).sort("_abs_d", descending=True)
    stratified = metricas.contrastes_estratificados
    persistence = metricas.persistencia
    domains = metricas.dominios
    top = aggregated.head(12)

    # 01 efecto total ponderado
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(top["variable"].to_list()[::-1], top["cohens_d_ponderado"].to_numpy()[::-1], color="C0")
    ax.axvline(0, color="gray", lw=0.8)
    ax.set_xlabel("Cohen's d ponderado (BAJA − CONTINUA)")
    p = OUT / "01_ranking_brechas_efecto.png"
    savefig(p, "Brechas agregadas, ponderadas por tamaño BAJA")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 02 intervalos bootstrap de las brechas principales
    interval = top.head(10)
    fig, ax = plt.subplots(figsize=(8, 5))
    y = np.arange(interval.height)
    ax.errorbar(
        interval["bootstrap_mean_diff"],
        y,
        xerr=[
            interval["bootstrap_mean_diff"] - interval["ic95_lo"],
            interval["ic95_hi"] - interval["bootstrap_mean_diff"],
        ],
        fmt="o",
    )
    ax.axvline(0, color="gray", ls="--")
    ax.set_yticks(y, interval["variable"].to_list())
    p = OUT / "02_top_violin_baja_continua.png"
    savefig(p, "IC95 bootstrap de efectos ponderados")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 03 efecto por ancla, promediado sobre horizontes sólo para visualización
    selected = top.head(8)["variable"].to_list()
    by_anchor = (
        stratified.filter(pl.col("variable").is_in(selected))
        .group_by("variable", "foto_mes_ancla")
        .agg(pl.col("cohens_d").mean().alias("cohens_d"))
        .pivot(on="foto_mes_ancla", index="variable", values="cohens_d")
        .fill_null(0)
    )
    fig, ax = plt.subplots(figsize=(9, 5))
    im = ax.imshow(by_anchor.drop("variable").to_numpy(), aspect="auto", cmap="coolwarm")
    ax.set_yticks(range(by_anchor.height), by_anchor["variable"].to_list())
    ax.set_xticks(range(len(by_anchor.columns) - 1), [column for column in by_anchor.columns if column != "variable"])
    plt.colorbar(im, ax=ax, label="Cohen's d")
    p = OUT / "03_prevalencia_flags_ancla.png"
    savefig(p, "Efectos por ancla (promedio visual entre horizontes)")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 04 dominios agregados
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(domains["dominio"].to_list()[::-1], domains["mean_abs_cohens_d"].to_numpy()[::-1])
    p = OUT / "04_matriz_dominios_heatmap.png"
    savefig(p, "Magnitud media de efecto por dominio")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 05 y 06 horizontes comparables, con sus propios controles
    for horizon, filename, title, color in [
        (1, "05_baja1_vs_continua.png", "Efectos estratificados BAJA+1", "C3"),
        (2, "06_baja2_vs_continua.png", "Efectos estratificados BAJA+2", "C4"),
    ]:
        subset = (
            stratified.filter(
                (pl.col("horizonte_evento") == horizon) & pl.col("variable").is_in(selected)
            )
            .group_by("variable")
            .agg(pl.col("cohens_d").mean().alias("cohens_d"))
            .sort("cohens_d", descending=True)
        )
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.barh(subset["variable"].to_list()[::-1], subset["cohens_d"].to_numpy()[::-1], color=color)
        ax.axvline(0, color="gray", lw=0.8)
        p = OUT / filename
        savefig(p, title)
        paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 07 evolución por ancla de las cuatro señales de mayor tamaño
    fig, ax = plt.subplots(figsize=(8, 4))
    for variable in selected[:4]:
        sub = (
            stratified.filter(pl.col("variable") == variable)
            .group_by("foto_mes_ancla")
            .agg(pl.col("diff_baja_menos_continua").mean().alias("efecto"))
            .sort("foto_mes_ancla")
        )
        ax.plot(sub["foto_mes_ancla"].cast(str), sub["efecto"], marker="o", label=variable)
    ax.axhline(0, color="gray", lw=0.8)
    ax.legend(fontsize=7)
    p = OUT / "07_bootstrap_ic_top.png"
    savefig(p, "Evolución por ancla de brechas principales")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 08 clasificación reproducible de persistencia
    classes = (
        persistence.group_by("clasificacion_persistencia")
        .agg(pl.len().alias("n_variables"))
        .sort("clasificacion_persistencia")
    )
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(classes["clasificacion_persistencia"], classes["n_variables"], color="C5")
    ax.tick_params(axis="x", rotation=20)
    ax.set_ylabel("variables")
    p = OUT / "08_mediana_vs_dispersion.png"
    savefig(p, "Clasificación de persistencia entre anclas")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 09 denominadores no nulos de los efectos principales
    fig, ax = plt.subplots(figsize=(8, 4))
    sample_sizes = top.head(8)
    y = np.arange(sample_sizes.height)
    ax.barh(y - 0.2, sample_sizes["n_baja_no_nulo"], 0.4, label="BAJA")
    ax.barh(y + 0.2, sample_sizes["n_continua_no_nulo"], 0.4, label="CONTINUA")
    ax.set_yticks(y, sample_sizes["variable"].to_list())
    ax.legend()
    p = OUT / "09_edad_antiguedad_ancla.png"
    savefig(p, "Denominadores no nulos de efectos ponderados")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 10 estratos incluidos por variable: cobertura analítica del contraste
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(top["variable"].to_list(), top["n_estratos_ponderados"], color="C0")
    ax.tick_params(axis="x", rotation=45)
    ax.set_ylabel("estratos ancla-horizonte incluidos")
    p = OUT / "10_rentabilidad_saldos_scatter.png"
    savefig(p, "Cobertura de estratos por métrica")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))
    return paths

    paths: list[str] = []
    snap = anchor_snapshot(panel)
    if contrastes is None:
        contrastes = contrastes_ancla(panel)
    sub = contrastes_subgrupos(panel)
    prev = prevalencia_flags(snap)
    dom = dominio_matrix(contrastes, panel.columns)

    top = contrastes.head(15)

    # 01 ranking brechas
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(top["variable"].to_list()[::-1], top["cohens_d"].to_numpy()[::-1], color="C0")
    ax.set_xlabel("Cohen's d (BAJA − CONTINUA)")
    p = OUT / "01_ranking_brechas_efecto.png"
    savefig(p, "Ranking de efecto al anclaje")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 02 violins top vars
    vars_top = top.head(6)["variable"].to_list()
    fig, axes = plt.subplots(2, 3, figsize=(10, 6))
    for ax, var in zip(axes.ravel(), vars_top):
        for g, color in [("BAJA", "C1"), ("CONTINUA", "C2")]:
            vals = snap.filter(pl.col("grupo") == g)[var].drop_nulls().to_numpy()
            if len(vals):
                ax.violinplot([vals], positions=[0 if g == "BAJA" else 1], showmeans=True)
        ax.set_title(var[:20], fontsize=8)
        ax.set_xticks([0, 1], ["BAJA", "CONT"])
    p = OUT / "02_top_violin_baja_continua.png"
    savefig(p, "Distribuciones variables top")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 03 prevalencia flags
    fig, ax = plt.subplots(figsize=(9, 4))
    for g, color in [("BAJA", "C1"), ("CONTINUA", "C2")]:
        s = prev.filter(pl.col("grupo") == g)
        ax.plot(range(s.height), s["prevalencia"], marker="o", label=g, color=color)
    ax.set_xticks(range(prev.filter(pl.col("grupo") == "BAJA").height))
    ax.set_xticklabels(prev.filter(pl.col("grupo") == "BAJA")["variable"], rotation=45, ha="right")
    ax.legend()
    p = OUT / "03_prevalencia_flags_ancla.png"
    savefig(p, "Prevalencia flags 0/1")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 04 heatmap dominios
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(dom["dominio"].to_list()[::-1], dom["mean_abs_cohens_d"].to_numpy()[::-1])
    p = OUT / "04_matriz_dominios_heatmap.png"
    savefig(p, "Efecto medio por dominio")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 05 BAJA+1 vs CONTINUA (top diff)
    s1 = sub.filter(pl.col("clase_ancla") == "BAJA+1").sort("cohens_d", descending=True).head(12)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(s1["variable"].to_list()[::-1], s1["cohens_d"].to_numpy()[::-1], color="C3")
    p = OUT / "05_baja1_vs_continua.png"
    savefig(p, "BAJA+1 vs CONTINUA")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 06 BAJA+2 vs CONTINUA
    s2 = sub.filter(pl.col("clase_ancla") == "BAJA+2").sort("cohens_d", descending=True).head(12)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(s2["variable"].to_list()[::-1], s2["cohens_d"].to_numpy()[::-1], color="C4")
    p = OUT / "06_baja2_vs_continua.png"
    savefig(p, "BAJA+2 vs CONTINUA")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 07 bootstrap IC top
    t5 = contrastes.head(8)
    fig, ax = plt.subplots(figsize=(8, 4))
    y = np.arange(t5.height)
    ax.errorbar(
        t5["bootstrap_mean_diff"],
        y,
        xerr=[
            t5["bootstrap_mean_diff"] - t5["ic95_lo"],
            t5["ic95_hi"] - t5["bootstrap_mean_diff"],
        ],
        fmt="o",
    )
    ax.set_yticks(y, t5["variable"].to_list())
    ax.axvline(0, color="gray", ls="--")
    p = OUT / "07_bootstrap_ic_top.png"
    savefig(p, "IC bootstrap diferencia de medias")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 08 media vs mediana (rentabilidad proxy)
    var = "mrentabilidad" if "mrentabilidad" in snap.columns else top["variable"][0]
    fig, ax = plt.subplots(figsize=(6, 4))
    for g in ("BAJA", "CONTINUA"):
        v = snap.filter(pl.col("grupo") == g)[var].drop_nulls()
        ax.scatter([g] * v.len(), v.to_numpy(), alpha=0.15, s=8)
        ax.scatter([g], [float(v.median())], color="black", s=80, marker="D", label=f"{g} mediana")
    ax.set_title(var)
    p = OUT / "08_mediana_vs_dispersion.png"
    savefig(p, "Mediana y dispersión")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 09 edad antigüedad
    fig, ax = plt.subplots(figsize=(6, 4))
    for g, color in [("BAJA", "C1"), ("CONTINUA", "C2")]:
        ax.scatter(
            snap.filter(pl.col("grupo") == g)["cliente_edad"],
            snap.filter(pl.col("grupo") == g)["cliente_antiguedad"],
            alpha=0.2,
            s=6,
            label=g,
            color=color,
        )
    ax.legend()
    ax.set_xlabel("edad")
    ax.set_ylabel("antigüedad")
    p = OUT / "09_edad_antiguedad_ancla.png"
    savefig(p, "Edad vs antigüedad al anclaje")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 10 rentabilidad vs saldos
    fig, ax = plt.subplots(figsize=(6, 4))
    for g, color in [("BAJA", "C1"), ("CONTINUA", "C2")]:
        subg = snap.filter(pl.col("grupo") == g)
        ax.scatter(
            subg["mcuentas_saldo"],
            subg["mrentabilidad"],
            alpha=0.2,
            s=6,
            label=g,
            color=color,
        )
    ax.legend()
    p = OUT / "10_rentabilidad_saldos_scatter.png"
    savefig(p, "Rentabilidad vs saldo cuentas")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    return paths

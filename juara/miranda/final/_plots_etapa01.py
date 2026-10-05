"""Etapa 01: cohorte y calidad (10 gráficos)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from _metrics import TemporalMetrics, calcular_metricas_temporales
from _paths import PLOTS_DIR
from _plot_utils import savefig

OUT = PLOTS_DIR / "etapa_01"


def run(
    panel: pl.DataFrame, raw: pl.DataFrame, metricas: TemporalMetrics | None = None
) -> list[str]:
    """Genera diez lecturas de composición, comparabilidad y cobertura."""

    metricas = metricas or calcular_metricas_temporales(panel)
    paths: list[str] = []
    composition = metricas.composicion_cohorte
    strata = metricas.resumen_cohorte
    coverage = metricas.cobertura
    baja = composition.filter(pl.col("grupo") == "BAJA")
    continua = composition.filter(pl.col("grupo") == "CONTINUA")
    labels = [
        f"{row['foto_mes_ancla']} +{row['horizonte_evento']}"
        for row in strata.iter_rows(named=True)
    ]
    x = np.arange(strata.height)

    # 01 tamaño BAJA/CONTINUA por estrato comparable
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(x - 0.2, strata["n_baja"], 0.4, label="BAJA", color="C1")
    ax.bar(x + 0.2, strata["n_continua"], 0.4, label="CONTINUA", color="C2")
    ax.set_xticks(x, labels, rotation=35, ha="right")
    ax.set_ylabel("episodios de cohorte")
    ax.legend()
    p = OUT / "01_volumen_clase_mes.png"
    savefig(p, "Tamaño por ancla y horizonte")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 02 tasa BAJA explícita, determinada por el diseño de controles
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(x, strata["tasa_baja_cohorte"], marker="o", color="C1")
    ax.set_xticks(x, labels, rotation=35, ha="right")
    ax.set_ylim(0, max(0.06, float(strata["tasa_baja_cohorte"].max()) * 1.15))
    ax.set_ylabel("BAJA / cohorte")
    p = OUT / "02_cobertura_longitudinal.png"
    savefig(p, "Tasa BAJA por estrato (diseño de cohorte)")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 03 composición BAJA+1 y BAJA+2 por ancla
    fig, ax = plt.subplots(figsize=(8, 4))
    anchors = baja["foto_mes_ancla"].unique().sort().to_list()
    anchor_x = np.arange(len(anchors))
    for horizon, color in [(1, "C3"), (2, "C4")]:
        sub = (
            baja.filter(pl.col("horizonte_evento") == horizon)
            .select("foto_mes_ancla", "n_miembros")
            .join(pl.DataFrame({"foto_mes_ancla": anchors}), on="foto_mes_ancla", how="right", coalesce=True)
            .fill_null(0)
            .sort("foto_mes_ancla")
        )
        ax.bar(
            anchor_x + (-0.2 if horizon == 1 else 0.2),
            sub["n_miembros"],
            width=0.4,
            label=f"BAJA+{horizon}",
            alpha=0.75,
            color=color,
        )
    ax.set_xticks(anchor_x, [str(anchor) for anchor in anchors])
    ax.set_ylabel("eventos seleccionados")
    ax.legend()
    p = OUT / "03_distribucion_horizonte.png"
    savefig(p, "Composición BAJA por ancla")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 04 razón efectiva de controles
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.axhline(20, color="gray", ls="--", label="objetivo 20:1")
    ax.plot(x, strata["ratio_controles_por_baja"], marker="o", color="C2")
    ax.set_xticks(x, labels, rotation=35, ha="right")
    ax.set_ylabel("CONTINUA por BAJA")
    ax.legend()
    p = OUT / "04_faltantes_panel.png"
    savefig(p, "Balance de controles por estrato")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    relative = coverage.filter(pl.col("eje_temporal") == "mes_relativo")
    relative = (
        relative.group_by("grupo", "mes_relativo")
        .agg(
            pl.col("n_miembros_observados").sum().alias("n_observados"),
            pl.col("denominador_cohorte").sum().alias("denominador"),
        )
        .with_columns((pl.col("n_observados") / pl.col("denominador")).alias("cobertura"))
    )
    # 05 cobertura relativa agregada preservando denominadores
    fig, ax = plt.subplots(figsize=(8, 4))
    for group, color in [("BAJA", "C1"), ("CONTINUA", "C2")]:
        sub = relative.filter(pl.col("grupo") == group).sort("mes_relativo")
        ax.plot(sub["mes_relativo"], sub["cobertura"], marker="o", label=group, color=color)
    ax.axvline(0, color="gray", ls="--", lw=0.8)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("observados / denominador")
    ax.legend()
    p = OUT / "05_duplicados_resueltos.png"
    savefig(p, "Cobertura por mes relativo")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 06 cobertura BAJA por estrato y mes relativo
    heat = (
        coverage.filter(
            (pl.col("eje_temporal") == "mes_relativo") & (pl.col("grupo") == "BAJA")
        )
        .pivot(
            on="mes_relativo",
            index=["foto_mes_ancla", "horizonte_evento"],
            values="cobertura_cohorte",
        )
        .fill_null(0)
    )
    fig, ax = plt.subplots(figsize=(9, 3))
    im = ax.imshow(
        heat.drop(["foto_mes_ancla", "horizonte_evento"]).to_numpy(),
        aspect="auto",
        vmin=0,
        vmax=1,
        cmap="Blues",
    )
    ax.set_yticks(
        range(heat.height),
        [f"{row['foto_mes_ancla']} +{row['horizonte_evento']}" for row in heat.iter_rows(named=True)],
    )
    ax.set_xticks(
        range(len(heat.columns) - 2),
        [column for column in heat.columns if column not in {"foto_mes_ancla", "horizonte_evento"}],
    )
    plt.colorbar(im, ax=ax, label="cobertura")
    p = OUT / "06_composicion_baja12.png"
    savefig(p, "Cobertura BAJA por estrato")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 07 cobertura por mes calendario: no confundir con la escala relativa
    calendar = coverage.filter(pl.col("eje_temporal") == "foto_mes")
    calendar = (
        calendar.group_by("grupo", "foto_mes")
        .agg(
            pl.col("n_miembros_observados").sum().alias("n_observados"),
            pl.col("denominador_cohorte").sum().alias("denominador"),
        )
        .with_columns((pl.col("n_observados") / pl.col("denominador")).alias("cobertura"))
    )
    fig, ax = plt.subplots(figsize=(8, 4))
    for group, color in [("BAJA", "C1"), ("CONTINUA", "C2")]:
        sub = calendar.filter(pl.col("grupo") == group).sort("foto_mes")
        ax.plot(sub["foto_mes"].cast(str), sub["cobertura"], marker="o", label=group, color=color)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("observados / denominador")
    ax.legend()
    p = OUT / "07_continua_muestra_vs_poblacion.png"
    savefig(p, "Cobertura por mes calendario")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 08 candidatas y episodios BAJA retenidos tras deduplicación
    candidates = (
        raw.filter(pl.col("clase_ternaria").is_in(["BAJA+1", "BAJA+2"]))
        .with_columns(
            pl.when(pl.col("clase_ternaria") == "BAJA+1")
            .then(1)
            .otherwise(2)
            .alias("horizonte_evento")
        )
        .group_by(pl.col("foto_mes").alias("foto_mes_ancla"), "horizonte_evento")
        .agg(pl.len().alias("n_candidatas"))
    )
    selected = baja.select(
        "foto_mes_ancla",
        "horizonte_evento",
        pl.col("n_miembros").alias("n_seleccionadas"),
    )
    events = candidates.join(selected, on=["foto_mes_ancla", "horizonte_evento"], how="inner")
    fig, ax = plt.subplots(figsize=(9, 4))
    event_x = np.arange(events.height)
    ax.bar(event_x - 0.2, events["n_candidatas"], 0.4, label="candidatas")
    ax.bar(event_x + 0.2, events["n_seleccionadas"], 0.4, label="seleccionadas")
    ax.set_xticks(
        event_x,
        [f"{row['foto_mes_ancla']} +{row['horizonte_evento']}" for row in events.iter_rows(named=True)],
        rotation=35,
        ha="right",
    )
    ax.legend()
    p = OUT / "08_comparabilidad_tamanos.png"
    savefig(p, "Eventos BAJA candidatos y seleccionados")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 09 controles replicados para comparabilidad por horizonte
    replication = continua.with_columns(
        (pl.col("n_controles_replicados") / pl.col("n_miembros")).alias("proporcion_replicada")
    )
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(
        [f"{row['foto_mes_ancla']} +{row['horizonte_evento']}" for row in replication.iter_rows(named=True)],
        replication["proporcion_replicada"],
        color="C2",
    )
    ax.set_ylim(0, 1)
    ax.set_ylabel("replicados / CONTINUA")
    plt.xticks(rotation=35, ha="right")
    p = OUT / "09_productos_digital_ancla.png"
    savefig(p, "Replicación de controles por estrato")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 10 denominadores totales de toda lectura comparativa
    totals = composition.group_by("grupo").agg(pl.col("n_miembros").sum().alias("n"))
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(totals["grupo"], totals["n"], color=["C1", "C2"])
    for index, value in enumerate(totals["n"].to_list()):
        ax.text(index, value, f"n={value:,}", ha="center", va="bottom")
    ax.set_ylabel("episodios de cohorte")
    p = OUT / "10_audit_meses_relativos.png"
    savefig(p, "Denominadores totales de comparación")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))
    return paths

    snap = panel.filter(pl.col("foto_mes") == pl.col("foto_mes_ancla"))

    # 01 volumen
    vol = snap.group_by("grupo", "foto_mes_ancla").agg(pl.len().alias("n")).sort("foto_mes_ancla")
    fig, ax = plt.subplots(figsize=(8, 4))
    for g, color in [("BAJA", "C1"), ("CONTINUA", "C2")]:
        sub = vol.filter(pl.col("grupo") == g)
        ax.bar(
            [f"{r['foto_mes_ancla']}" for r in sub.iter_rows(named=True)],
            sub["n"].to_list(),
            alpha=0.7,
            label=g,
            color=color,
        )
    ax.legend()
    ax.set_xlabel("foto_mes ancla")
    p = OUT / "01_volumen_clase_mes.png"
    savefig(p, "Volumen por grupo y mes de anclaje")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 02 cobertura longitudinal
    cov = pl.read_csv(OUT.parent.parent / "tablas" / "auditoria_cobertura_mes_relativo.csv")
    fig, ax = plt.subplots(figsize=(8, 4))
    for g in cov["grupo"].unique().to_list():
        sub = cov.filter(pl.col("grupo") == g)
        ax.plot(sub["mes_relativo"], sub["n_clientes"], marker="o", label=g)
    ax.axvline(0, color="gray", ls="--", lw=0.8)
    ax.legend()
    ax.set_xlabel("mes_relativo (0 = evento esperado)")
    p = OUT / "02_cobertura_longitudinal.png"
    savefig(p, "Cobertura del panel por mes relativo")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 03 horizonte
    baja = snap.filter(pl.col("grupo") == "BAJA")
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(baja["horizonte_meses"].to_numpy(), bins=[0.5, 1.5, 2.5], rwidth=0.8, color="C3")
    ax.set_xticks([1, 2])
    ax.set_xlabel("horizonte (meses)")
    p = OUT / "03_distribucion_horizonte.png"
    savefig(p, "Distribución BAJA+1 / BAJA+2")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 04 faltantes en panel
    miss = (
        panel.select([pl.col(c).null_count().alias(c) for c in panel.columns if c.startswith("m")][:20])
        .transpose(include_header=True, header_name="variable", column_names=["n_null"])
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(miss["variable"].to_list()[::-1], miss["n_null"].to_numpy()[::-1])
    p = OUT / "04_faltantes_panel.png"
    savefig(p, "Nulos en variables monetarias (muestra)")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 05 duplicados
    dup = pl.read_csv(OUT.parent.parent / "tablas" / "auditoria_duplicados_baja.csv")
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.bar(["resueltos", "cohorte única"], [dup.height, snap.filter(pl.col("grupo") == "BAJA").height])
    p = OUT / "05_duplicados_resueltos.png"
    savefig(p, "Duplicados BAJA en ancla")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 06 composición BAJA+1/2
    comp = pl.read_csv(OUT.parent.parent / "tablas" / "auditoria_composicion_baja12.csv")
    fig, ax = plt.subplots(figsize=(7, 4))
    labels = [f"{r['foto_mes_ancla']}-{r['clase_ancla']}" for r in comp.iter_rows(named=True)]
    ax.bar(labels, comp["n"].to_list(), color="C4")
    plt.xticks(rotation=30, ha="right")
    p = OUT / "06_composicion_baja12.png"
    savefig(p, "Composición BAJA por ancla")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 07 continua muestra vs población
    anchor = raw.filter(pl.col("foto_mes").is_in(list(ANCHOR_MONTHS)))
    pop = (
        anchor.filter(pl.col("clase_ternaria") == "CONTINUA")
        .group_by("foto_mes")
        .agg(pl.len().alias("poblacion"))
    )
    samp = snap.filter(pl.col("grupo") == "CONTINUA").group_by("foto_mes_ancla").agg(pl.len().alias("muestra"))
    merged = pop.join(samp, left_on="foto_mes", right_on="foto_mes_ancla", how="left")
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(merged.height)
    ax.bar(x - 0.2, merged["poblacion"], width=0.4, label="población")
    ax.bar(x + 0.2, merged["muestra"], width=0.4, label=f"muestra ~{SAMPLE_FRAC:.0%}")
    ax.set_xticks(x, [str(m) for m in merged["foto_mes"].to_list()])
    ax.legend()
    p = OUT / "07_continua_muestra_vs_poblacion.png"
    savefig(p, "CONTINUA: población vs muestra")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 08 comparabilidad tamaños
    sizes = snap.group_by("grupo").agg(pl.len().alias("n"))
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.pie(sizes["n"].to_list(), labels=sizes["grupo"].to_list(), autopct="%1.1f%%")
    p = OUT / "08_comparabilidad_tamanos.png"
    savefig(p, "Tamaño relativo BAJA vs CONTINUA")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 09 productos/digital ancla
    cols = [c for c in NOCONTINUAS_ANCLA if c in snap.columns][:8]
    prev_b = []
    prev_c = []
    for c in cols:
        prev_b.append(float((snap.filter(pl.col("grupo") == "BAJA")[c] > 0).mean()))
        prev_c.append(float((snap.filter(pl.col("grupo") == "CONTINUA")[c] > 0).mean()))
    fig, ax = plt.subplots(figsize=(9, 4))
    x = np.arange(len(cols))
    ax.bar(x - 0.2, prev_b, 0.4, label="BAJA")
    ax.bar(x + 0.2, prev_c, 0.4, label="CONTINUA")
    ax.set_xticks(x, cols, rotation=45, ha="right")
    ax.legend()
    p = OUT / "09_productos_digital_ancla.png"
    savefig(p, "Prevalencia flags al anclaje")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 10 meses relativos disponibles
    heat = (
        panel.group_by("grupo", "mes_relativo")
        .agg(pl.col("numero_de_cliente").n_unique().alias("n"))
        .pivot(on="mes_relativo", index="grupo", values="n")
        .fill_null(0)
    )
    fig, ax = plt.subplots(figsize=(10, 3))
    mat = heat.drop("grupo").to_numpy()
    im = ax.imshow(mat, aspect="auto", cmap="Blues")
    ax.set_yticks(range(heat.height), heat["grupo"].to_list())
    ax.set_xticks(range(len(heat.columns) - 1), [c for c in heat.columns if c != "grupo"])
    plt.colorbar(im, ax=ax, label="clientes")
    p = OUT / "10_audit_meses_relativos.png"
    savefig(p, "Heatmap cobertura mes relativo")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    return paths

"""Etapa 03: ciclo de vida alineado al evento (10 gráficos)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import polars as pl

from _metrics import TemporalMetrics, calcular_metricas_temporales
from _paths import PLOTS_DIR
from _plot_utils import savefig

OUT = PLOTS_DIR / "etapa_03"

TRAJ_VARS = [
    ("mrentabilidad", "Rentabilidad"),
    ("thomebanking", "Homebanking"),
    ("ctarjeta_visa_transacciones", "Trx Visa"),
    ("mcomisiones", "Comisiones"),
    ("mcuentas_saldo", "Saldo cuentas"),
    ("Visa_msaldototal", "Saldo Visa"),
    ("mprestamos_personales", "Préstamos personales"),
    ("cproductos", "Productos"),
]


def _mean_traj(panel: pl.DataFrame, var: str, grupo: str) -> tuple[list[int], list[float]]:
    sub = (
        panel.filter(pl.col("grupo") == grupo)
        .group_by("mes_relativo")
        .agg(pl.col(var).mean().alias("m"))
        .sort("mes_relativo")
    )
    return sub["mes_relativo"].to_list(), sub["m"].to_list()


def run(panel: pl.DataFrame, metricas: TemporalMetrics | None = None) -> list[str]:
    """Genera lecturas alineadas y calendarias sin confundir sus escalas."""

    metricas = metricas or calcular_metricas_temporales(panel)
    paths: list[str] = []
    vars_ok = [(variable, title) for variable, title in TRAJ_VARS if variable in panel.columns][:4]
    aligned = metricas.trayectorias_alineadas
    calendar = metricas.trayectorias_calendario
    coverage = metricas.cobertura

    def aggregate(
        frame: pl.DataFrame, axis: str, variable: str, extra: list[str] | None = None
    ) -> pl.DataFrame:
        groups = ["grupo", axis] + (extra or [])
        value = f"media_{variable}"
        return (
            frame.with_columns((pl.col(value) * pl.col("n_miembros_observados")).alias("_ponderado"))
            .group_by(*groups)
            .agg(
                pl.col("_ponderado").sum().alias("_suma"),
                pl.col("n_miembros_observados").sum().alias("n_miembros_observados"),
            )
            .with_columns(
                (pl.col("_suma") / pl.col("n_miembros_observados")).alias("media")
            )
            .sort(groups)
        )

    # 01-04 trayectorias alineadas; los denominadores se materializan en tablas.
    for index, (variable, title) in enumerate(vars_ok, start=1):
        summary = aggregate(aligned, "mes_relativo", variable)
        fig, ax = plt.subplots(figsize=(7, 4))
        for group, color in [("BAJA", "C1"), ("CONTINUA", "C2")]:
            sub = summary.filter(pl.col("grupo") == group)
            ax.plot(sub["mes_relativo"], sub["media"], marker="o", label=group, color=color)
        ax.axvline(0, color="gray", ls="--", lw=0.8)
        ax.set_xlabel("mes relativo al evento esperado")
        ax.legend()
        p = OUT / f"{index:02d}_trayectoria_{variable}.png"
        savefig(p, f"{title}: evolución alineada (ver denominadores)")
        paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    primary, primary_title = vars_ok[0]
    # 05 nivel por calendario: deliberadamente separado de la lectura alineada.
    calendar_summary = aggregate(calendar, "foto_mes", primary)
    fig, ax = plt.subplots(figsize=(7, 4))
    for group, color in [("BAJA", "C1"), ("CONTINUA", "C2")]:
        sub = calendar_summary.filter(pl.col("grupo") == group)
        ax.plot(sub["foto_mes"].cast(str), sub["media"], marker="o", label=group, color=color)
    ax.legend()
    ax.set_xlabel("mes calendario")
    p = OUT / "05_nivel_calendario_rentabilidad.png"
    savefig(p, f"{primary_title}: niveles por calendario (no alineados)")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 06 brecha agregada en escala relativa
    relative_summary = aggregate(aligned, "mes_relativo", primary)
    baja = relative_summary.filter(pl.col("grupo") == "BAJA").select(
        "mes_relativo", pl.col("media").alias("media_baja")
    )
    continua = relative_summary.filter(pl.col("grupo") == "CONTINUA").select(
        "mes_relativo", pl.col("media").alias("media_continua")
    )
    gap = baja.join(continua, on="mes_relativo").with_columns(
        (pl.col("media_baja") - pl.col("media_continua")).alias("brecha")
    )
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(gap["mes_relativo"], gap["brecha"], color="C5")
    ax.axhline(0, color="gray", lw=0.8)
    p = OUT / "06_brecha_alineada.png"
    savefig(p, f"{primary_title}: brecha BAJA − CONTINUA alineada")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 07 brecha por ancla: la evolución agregada no oculta heterogeneidad mensual.
    by_anchor = aggregate(aligned, "mes_relativo", primary, ["foto_mes_ancla"])
    fig, ax = plt.subplots(figsize=(8, 4))
    for anchor in by_anchor["foto_mes_ancla"].unique().sort().to_list():
        sub = by_anchor.filter(pl.col("foto_mes_ancla") == anchor)
        b = sub.filter(pl.col("grupo") == "BAJA").select("mes_relativo", pl.col("media").alias("b"))
        c = sub.filter(pl.col("grupo") == "CONTINUA").select("mes_relativo", pl.col("media").alias("c"))
        joined = b.join(c, on="mes_relativo").with_columns((pl.col("b") - pl.col("c")).alias("gap"))
        ax.plot(joined["mes_relativo"], joined["gap"], marker="o", label=str(anchor))
    ax.axhline(0, color="gray", lw=0.8)
    ax.legend(title="ancla", fontsize=7)
    p = OUT / "07_brecha_rentabilidad.png"
    savefig(p, f"{primary_title}: brecha por ancla")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 08 BAJA por horizonte, en su propio calendario relativo.
    baja_horizon = aggregate(
        aligned.filter(pl.col("grupo") == "BAJA"),
        "mes_relativo",
        primary,
        ["horizonte_evento"],
    )
    fig, ax = plt.subplots(figsize=(7, 4))
    for horizon, color in [(1, "C3"), (2, "C4")]:
        sub = baja_horizon.filter(pl.col("horizonte_evento") == horizon)
        ax.plot(sub["mes_relativo"], sub["media"], marker="o", label=f"BAJA+{horizon}", color=color)
    ax.axvline(0, color="gray", ls="--")
    ax.legend()
    p = OUT / "08_trayectoria_por_horizonte.png"
    savefig(p, f"{primary_title}: BAJA por horizonte")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 09 cobertura relativa publicada junto a trayectorias.
    cov_relative = (
        coverage.filter(pl.col("eje_temporal") == "mes_relativo")
        .group_by("grupo", "mes_relativo")
        .agg(
            pl.col("n_miembros_observados").sum().alias("n"),
            pl.col("denominador_cohorte").sum().alias("denominador"),
        )
        .with_columns((pl.col("n") / pl.col("denominador")).alias("cobertura"))
        .sort(["grupo", "mes_relativo"])
    )
    fig, ax = plt.subplots(figsize=(7, 4))
    for group, color in [("BAJA", "C1"), ("CONTINUA", "C2")]:
        sub = cov_relative.filter(pl.col("grupo") == group)
        ax.plot(sub["mes_relativo"], sub["cobertura"], marker="o", label=group, color=color)
    ax.set_ylim(0, 1.05)
    ax.legend()
    p = OUT / "09_trayectoria_digital.png"
    savefig(p, "Cobertura de trayectorias por mes relativo")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 10 denominadores no nulos del indicador principal por calendario.
    den = metricas.denominadores_metricas.filter(
        (pl.col("eje_temporal") == "foto_mes") & (pl.col("variable") == primary)
    )
    den = den.group_by("grupo", "foto_mes").agg(pl.col("n_observaciones_no_nulas").sum().alias("n"))
    fig, ax = plt.subplots(figsize=(7, 4))
    for group, color in [("BAJA", "C1"), ("CONTINUA", "C2")]:
        sub = den.filter(pl.col("grupo") == group).sort("foto_mes")
        ax.plot(sub["foto_mes"].cast(str), sub["n"], marker="o", label=group, color=color)
    ax.legend()
    ax.set_ylabel("observaciones no nulas")
    p = OUT / "10_trayectoria_comisiones_trx.png"
    savefig(p, f"Denominadores de {primary_title} por calendario")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))
    return paths

    paths: list[str] = []
    vars_ok = [(v, t) for v, t in TRAJ_VARS if v in panel.columns]

    # 01-06 trayectorias principales
    for idx, (var, title) in enumerate(vars_ok[:6], start=1):
        fig, ax = plt.subplots(figsize=(7, 4))
        for g, color in [("BAJA", "C1"), ("CONTINUA", "C2")]:
            xs, ys = _mean_traj(panel, var, g)
            ax.plot(xs, ys, marker="o", label=g, color=color)
        ax.axvline(0, color="gray", ls="--", lw=0.8)
        ax.set_xlabel("mes_relativo")
        ax.set_ylabel("media")
        p = OUT / f"{idx:02d}_trayectoria_{var}.png"
        savefig(p, f"{title}: trayectoria alineada")
        paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 07 brecha BAJA-CONTINUA (rentabilidad)
    var = vars_ok[0][0]
    b_x, b_y = _mean_traj(panel, var, "BAJA")
    c_x, c_y = _mean_traj(panel, var, "CONTINUA")
    gap = {x: b - c for x, b, c in zip(b_x, b_y, c_y) if x in c_x}
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(list(gap.keys()), list(gap.values()), color="C5")
    ax.axhline(0, color="gray", lw=0.8)
    p = OUT / "07_brecha_rentabilidad.png"
    savefig(p, "Brecha media BAJA − CONTINUA")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 08 por horizonte BAJA+1 vs BAJA+2
    fig, ax = plt.subplots(figsize=(7, 4))
    for clase, color in [("BAJA+1", "C3"), ("BAJA+2", "C4")]:
        sub = (
            panel.filter((pl.col("grupo") == "BAJA") & (pl.col("clase_ancla") == clase))
            .group_by("mes_relativo")
            .agg(pl.col(var).mean().alias("m"))
            .sort("mes_relativo")
        )
        ax.plot(sub["mes_relativo"], sub["m"], marker="o", label=clase, color=color)
    ax.axvline(0, color="gray", ls="--")
    ax.legend()
    p = OUT / "08_trayectoria_por_horizonte.png"
    savefig(p, "Trayectoria por horizonte")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 09 digital (tmobile_app)
    var_d = "tmobile_app" if "tmobile_app" in panel.columns else vars_ok[1][0]
    fig, ax = plt.subplots(figsize=(7, 4))
    for g in ("BAJA", "CONTINUA"):
        xs, ys = _mean_traj(panel, var_d, g)
        ax.plot(xs, ys, marker="o", label=g)
    ax.axvline(0, color="gray", ls="--")
    ax.legend()
    p = OUT / "09_trayectoria_digital.png"
    savefig(p, "Actividad digital")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 10 comisiones + transacciones normalizadas
    fig, ax = plt.subplots(figsize=(7, 4))
    for var2, lab in [("mcomisiones", "comisiones"), ("ctransferencias_emitidas", "trx transf.")]:
        if var2 not in panel.columns:
            continue
        xs, ys = _mean_traj(panel, var2, "BAJA")
        if ys:
            m = max(abs(v) for v in ys) or 1
            ax.plot(xs, [v / m for v in ys], marker="o", label=f"BAJA {lab}")
    ax.axvline(0, color="gray", ls="--")
    ax.legend()
    p = OUT / "10_trayectoria_comisiones_trx.png"
    savefig(p, "Comisiones y transferencias (norm.)")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    return paths

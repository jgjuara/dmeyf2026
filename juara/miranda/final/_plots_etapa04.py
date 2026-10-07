"""Etapa 04: clustering SHAP (10 gráficos)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from _paths import PERFILES_CLIENTES_PLOTS_DIR, PLOTS_DIR
from _plot_utils import savefig

OUT = PLOTS_DIR / "etapa_04"
PERFILES_OUT = PERFILES_CLIENTES_PLOTS_DIR


def _rejected_plots(cluster_out: dict) -> list[str]:
    """Conserva la interfaz gráfica y declara que no hay perfiles defendibles."""

    names = [
        "01_silueta_vs_k.png",
        "02_tamanos_cluster.png",
        "03_importancia_global_shap.png",
        "04_heatmap_perfiles_shap.png",
        "05_composicion_baja12_cluster.png",
        "06_scatter_shap_top2.png",
        "07_transiciones_pre_evento.png",
        "08_auc_clasificador.png",
        "09_ancla_mes_por_cluster.png",
        "10_metricas_cluster_elegido.png",
    ]
    message = "No se aceptó una segmentación defendible."
    reasons = cluster_out["metrics"].get("motivos_no_aceptacion", [])
    paths: list[str] = []
    for index, name in enumerate(names, start=1):
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.axis("off")
        text = message
        if index in (1, 8, 10) and reasons:
            text += "\n" + "\n".join(f"• {reason}" for reason in reasons)
        ax.text(0.5, 0.5, text, ha="center", va="center", wrap=True)
        path = OUT / name
        savefig(path, f"Etapa 04 — gráfico {index:02d}")
        paths.append(str(path.relative_to(PLOTS_DIR.parent)))
    return paths


def _finite_values(frame: pl.DataFrame, variable: str) -> np.ndarray:
    values = frame[variable].to_numpy().astype(float, copy=False)
    return values[np.isfinite(values)]


def _matched_control_values(
    snap: pl.DataFrame, member_ids: list[str], variable: str
) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve CONTINUA ponderada por los estratos ancla-horizonte del clúster."""

    weights = (
        snap.filter(pl.col("cohort_member_id").is_in(member_ids))
        .group_by("foto_mes_ancla", "horizonte_evento")
        .len()
        .rename({"len": "peso"})
    )
    controls = (
        snap.filter(pl.col("grupo") == "CONTINUA")
        .select("foto_mes_ancla", "horizonte_evento", variable)
        .join(weights, on=["foto_mes_ancla", "horizonte_evento"], how="inner")
    )
    values = controls[variable].to_numpy().astype(float, copy=False)
    control_weights = controls["peso"].to_numpy().astype(float, copy=False)
    valid = np.isfinite(values) & np.isfinite(control_weights) & (control_weights > 0)
    return values[valid], control_weights[valid]


def _matched_control_mean(snap: pl.DataFrame, member_ids: list[str], variable: str) -> float:
    weights = (
        snap.filter(pl.col("cohort_member_id").is_in(member_ids))
        .group_by("foto_mes_ancla", "horizonte_evento")
        .len()
        .rename({"len": "peso"})
    )
    controls = (
        snap.filter(pl.col("grupo") == "CONTINUA")
        .group_by("foto_mes_ancla", "horizonte_evento")
        .agg(pl.col(variable).mean().alias("media_continua"))
    )
    weighted = weights.join(controls, on=["foto_mes_ancla", "horizonte_evento"], how="left")
    observed = weighted.filter(pl.col("media_continua").is_not_null())
    denominator = observed["peso"].sum()
    if not denominator:
        return float("nan")
    return float((observed["peso"] * observed["media_continua"]).sum() / denominator)


def _profile_pair(
    snap: pl.DataFrame, member_ids: list[str], variable: str
) -> tuple[float, float]:
    members = snap.filter(pl.col("cohort_member_id").is_in(member_ids))
    values = _finite_values(members, variable)
    mean_segment = float(np.mean(values)) if values.size else float("nan")
    mean_control = _matched_control_mean(snap, member_ids, variable)
    return mean_segment, mean_control


def _interval(variable: str, value: float) -> str:
    if not np.isfinite(value):
        return "Sin dato"
    if variable == "cliente_edad":
        if value < 18:
            return "Menor de 18"
        if value < 25:
            return "18-24"
        if value < 35:
            return "25-34"
        if value < 45:
            return "35-44"
        if value < 55:
            return "45-54"
        if value < 65:
            return "55-64"
        if value < 75:
            return "65-74"
        return "75 o más"
    if value <= 12:
        return "Hasta 12 meses"
    if value <= 36:
        return "13-36 meses"
    if value <= 60:
        return "37-60 meses"
    if value <= 120:
        return "61-120 meses"
    if value <= 240:
        return "121-240 meses"
    return "Más de 240 meses"


def _intervals(variable: str) -> list[str]:
    if variable == "cliente_edad":
        return ["Menor de 18", "18-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75 o más", "Sin dato"]
    return [
        "Hasta 12 meses",
        "13-36 meses",
        "37-60 meses",
        "61-120 meses",
        "121-240 meses",
        "Más de 240 meses",
        "Sin dato",
    ]


def _distribution_percentages(
    values: np.ndarray, weights: np.ndarray | None, variable: str
) -> tuple[list[str], np.ndarray]:
    categories = _intervals(variable)
    totals = dict.fromkeys(categories, 0.0)
    if weights is None:
        weights = np.ones(values.size, dtype=float)
    for value, weight in zip(values, weights, strict=True):
        totals[_interval(variable, value)] += weight
    denominator = sum(totals.values())
    percentages = np.array([100 * totals[category] / denominator if denominator else 0 for category in categories])
    return categories, percentages


def _rejected_profile_plots(cluster_out: dict) -> list[str]:
    names = [
        "01_top10_vs_continua.png",
        "02_distribucion_edad.png",
        "03_distribucion_antiguedad.png",
        "04_perfil_financiero.png",
    ]
    reasons = cluster_out["metrics"].get("motivos_no_aceptacion", [])
    detail = "\n".join(f"• {reason}" for reason in reasons)
    paths: list[str] = []
    for name in names:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            "Advertencia: la segmentación no fue aceptada.\n"
            "No se publican perfiles de clientes ni datos residuales."
            + (f"\n{detail}" if detail else ""),
            ha="center",
            va="center",
            wrap=True,
        )
        path = PERFILES_OUT / name
        savefig(path)
        paths.append(str(path.relative_to(PLOTS_DIR.parent)))
    return paths


def run_perfiles_clientes(panel: pl.DataFrame, cluster_out: dict) -> list[str]:
    """Publica contrastes descriptivos sólo cuando la segmentación fue aceptada."""

    for path in PERFILES_OUT.glob("*.png"):
        path.unlink()
    if not cluster_out["accepted"]:
        return _rejected_profile_plots(cluster_out)

    snap = panel.filter(pl.col("foto_mes") == pl.col("foto_mes_ancla"))
    assign = cluster_out["assign"]
    clusters = sorted(assign["cluster"].unique().to_list())
    members_by_cluster = {
        cluster: assign.filter(pl.col("cluster") == cluster)["cohort_member_id"].to_list()
        for cluster in clusters
    }
    paths: list[str] = []

    # El panel por variable evita comparar magnitudes heterogéneas sobre una misma escala.
    variables = [
        variable
        for variable in cluster_out["imp_df"].head(10)["feature"].to_list()
        if variable in snap.columns
    ]
    fig, axes = plt.subplots(5, 2, figsize=(13, 15))
    for ax, variable in zip(axes.flat, variables, strict=False):
        positions: list[float] = []
        heights: list[float] = []
        colors: list[str] = []
        labels: list[str] = []
        for index, cluster in enumerate(clusters):
            segment, control = _profile_pair(snap, members_by_cluster[cluster], variable)
            positions.extend([index * 3, index * 3 + 1])
            heights.extend([segment, control])
            colors.extend(["#1f77b4", "#9da3a6"])
            labels.extend([f"C{cluster}\nBAJA", f"C{cluster}\nCONT."])
        ax.bar(positions, heights, color=colors)
        ax.set_xticks(positions, labels, fontsize=8)
        ax.set_title(variable, fontsize=10)
        ax.axhline(0, color="#555555", linewidth=0.7)
    for ax in axes.flat[len(variables) :]:
        ax.axis("off")
    fig.suptitle(
        "Variables relevantes: media nominal al ancla frente a CONTINUA emparejada",
        fontsize=13,
    )
    path = PERFILES_OUT / "01_top10_vs_continua.png"
    savefig(path)
    paths.append(str(path.relative_to(PLOTS_DIR.parent)))

    for plot_index, variable, title in [
        (2, "cliente_edad", "Distribución de edad al ancla"),
        (3, "cliente_antiguedad", "Distribución de antigüedad al ancla"),
    ]:
        fig, axes = plt.subplots(1, len(clusters), figsize=(7 * len(clusters), 5), sharey=True)
        axes_array = np.atleast_1d(axes)
        for ax, cluster in zip(axes_array, clusters, strict=True):
            members = snap.filter(pl.col("cohort_member_id").is_in(members_by_cluster[cluster]))
            segment_values = members[variable].to_numpy().astype(float, copy=False)
            control_values, control_weights = _matched_control_values(
                snap, members_by_cluster[cluster], variable
            )
            categories, segment_pct = _distribution_percentages(segment_values, None, variable)
            _, control_pct = _distribution_percentages(control_values, control_weights, variable)
            x = np.arange(len(categories))
            ax.bar(x - 0.2, segment_pct, width=0.4, label="BAJA", color="#1f77b4")
            ax.bar(x + 0.2, control_pct, width=0.4, label="CONTINUA emparejada", color="#9da3a6")
            ax.set_xticks(x, categories, rotation=35, ha="right", fontsize=8)
            ax.set_title(f"Clúster C{cluster}")
            ax.set_ylabel("% dentro del grupo")
            ax.legend(fontsize=8)
        fig.suptitle(title, fontsize=13)
        path = PERFILES_OUT / (
            "02_distribucion_edad.png"
            if plot_index == 2
            else "03_distribucion_antiguedad.png"
        )
        savefig(path)
        paths.append(str(path.relative_to(PLOTS_DIR.parent)))

    financial_metrics = [
        ("tcuentas", "Cantidad de cuentas"),
        ("mcuentas_saldo", "Saldo de cuentas"),
        ("mprestamos_personales", "Préstamos personales"),
        ("mprestamos_prendarios", "Préstamos prendarios"),
        ("Visa_msaldototal", "Saldo Visa"),
        ("Master_msaldototal", "Saldo Master"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for ax, (variable, title) in zip(axes.flat, financial_metrics, strict=True):
        positions: list[float] = []
        heights: list[float] = []
        labels: list[str] = []
        for index, cluster in enumerate(clusters):
            segment, control = _profile_pair(snap, members_by_cluster[cluster], variable)
            positions.extend([index * 3, index * 3 + 1])
            heights.extend([segment, control])
            labels.extend([f"C{cluster}\nBAJA", f"C{cluster}\nCONT."])
        ax.bar(positions, heights, color=["#1f77b4", "#9da3a6"] * len(clusters))
        ax.set_xticks(positions, labels, fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.axhline(0, color="#555555", linewidth=0.7)
    fig.suptitle(
        "Perfil financiero: cada panel conserva su propia escala; CONTINUA está emparejada",
        fontsize=12,
    )
    path = PERFILES_OUT / "04_perfil_financiero.png"
    savefig(path)
    paths.append(str(path.relative_to(PLOTS_DIR.parent)))
    return paths


def run(panel: pl.DataFrame, cluster_out: dict) -> list[str]:
    if not cluster_out["accepted"]:
        return _rejected_plots(cluster_out)

    paths: list[str] = []
    labels = cluster_out["labels"]
    shap = cluster_out["shap_baja"]
    feats = cluster_out["feats"]
    imp = cluster_out["imp_df"]
    eval_df = cluster_out["eval_df"]
    assign = cluster_out["assign"]
    k = cluster_out["k"]

    # 01 silueta vs k
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(eval_df["k"], eval_df["silhouette"], marker="o", label="silueta")
    ax.plot(eval_df["k"], eval_df["stability_mean"], marker="s", label="estabilidad media")
    ax.axvline(k, color="gray", ls="--", label=f"k={k}")
    ax.legend()
    p = OUT / "01_silueta_vs_k.png"
    savefig(p, "Selección de k")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 02 tamaños cluster
    sizes = np.bincount(labels, minlength=k)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(range(k), sizes)
    ax.set_xlabel("cluster")
    p = OUT / "02_tamanos_cluster.png"
    savefig(p, "Tamaño por clúster")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 03 importancia global SHAP
    top = imp.head(15)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(top["feature"].to_list()[::-1], top["mean_abs_shap"].to_numpy()[::-1])
    p = OUT / "03_importancia_global_shap.png"
    savefig(p, "Importancia global |SHAP|")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 04 heatmap perfiles (top features)
    topf = imp.head(10)["feature"].to_list()
    idxs = [feats.index(f) for f in topf]
    mat = np.zeros((k, len(topf)))
    for c in range(k):
        mat[c] = shap[labels == c][:, idxs].mean(axis=0)
    fig, ax = plt.subplots(figsize=(10, 4))
    im = ax.imshow(mat, aspect="auto", cmap="coolwarm")
    ax.set_yticks(range(k), [f"C{c}" for c in range(k)])
    ax.set_xticks(range(len(topf)), topf, rotation=45, ha="right")
    plt.colorbar(im, ax=ax)
    p = OUT / "04_heatmap_perfiles_shap.png"
    savefig(p, "Perfiles SHAP medios")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 05 composición BAJA+1/2 por cluster
    comp = assign.group_by("cluster", "clase_ancla").agg(pl.len().alias("n"))
    fig, ax = plt.subplots(figsize=(7, 4))
    for clase, color in [("BAJA+1", "C0"), ("BAJA+2", "C1")]:
        s = comp.filter(pl.col("clase_ancla") == clase)
        ax.bar(s["cluster"] + (0 if clase == "BAJA+1" else 0.35), s["n"], width=0.35, label=clase, color=color)
    ax.legend()
    p = OUT / "05_composicion_baja12_cluster.png"
    savefig(p, "BAJA+1 / BAJA+2 por clúster")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 06 PCA-free 2D: mean SHAP dims 1-2 (top features by variance)
    var_idx = np.argsort(np.var(shap, axis=0))[-2:]
    coords = shap[:, var_idx]
    fig, ax = plt.subplots(figsize=(6, 5))
    for c in range(k):
        m = labels == c
        ax.scatter(coords[m, 0], coords[m, 1], s=8, alpha=0.4, label=f"C{c}")
    ax.set_xlabel(f"SHAP {feats[var_idx[0]]}")
    ax.set_ylabel(f"SHAP {feats[var_idx[1]]}")
    ax.legend(markerscale=2)
    p = OUT / "06_scatter_shap_top2.png"
    savefig(p, "Dispersión en plano SHAP (sin PCA)")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 07 transiciones pre-evento con KMeans fijo
    transitions = cluster_out["transitions"]
    matrix = transitions["aggregate_matrix"]
    fig, ax = plt.subplots(figsize=(6, 5))
    if matrix.is_empty():
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            "No hay estratos con soporte suficiente para publicar transiciones.",
            ha="center",
            va="center",
            wrap=True,
        )
    else:
        transition_values = np.zeros((k, k))
        for row in matrix.iter_rows(named=True):
            transition_values[int(row["estado_origen"]), int(row["estado_destino"])] = row[
                "probabilidad"
            ]
        image = ax.imshow(transition_values, vmin=0, vmax=1, cmap="Blues")
        for origin in range(k):
            for destination in range(k):
                ax.text(
                    destination,
                    origin,
                    f"{transition_values[origin, destination]:.2f}",
                    ha="center",
                    va="center",
                    color="white" if transition_values[origin, destination] > 0.5 else "black",
                )
        ax.set_xticks(range(k), [f"C{cluster}" for cluster in range(k)])
        ax.set_yticks(range(k), [f"C{cluster}" for cluster in range(k)])
        ax.set_xlabel("Estado destino")
        ax.set_ylabel("Estado origen")
        fig.colorbar(image, ax=ax, label="Probabilidad por estado origen")
    p = OUT / "07_transiciones_pre_evento.png"
    savefig(p, "Transiciones pre-evento entre estados SHAP")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 08 discriminación temporal por ancla
    auc = cluster_out["metrics"]["auc_temporal_media"]
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.bar(["media temporal"], [auc], color="C2")
    ax.set_ylim(0, 1)
    p = OUT / "08_auc_clasificador.png"
    savefig(p, "AUC clasificador BAJA vs CONTINUA")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 09 foto_mes ancla por cluster
    fm = assign.group_by("cluster", "foto_mes_ancla").agg(pl.len().alias("n"))
    fig, ax = plt.subplots(figsize=(7, 4))
    for c in fm["cluster"].unique().sort().to_list():
        s = fm.filter(pl.col("cluster") == c)
        ax.plot(s["foto_mes_ancla"], s["n"], marker="o", label=f"C{c}")
    ax.legend()
    p = OUT / "09_ancla_mes_por_cluster.png"
    savefig(p, "Mes de anclaje por clúster")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    # 10 métricas del corte elegido
    row = eval_df.filter(pl.col("k") == k)
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.bar(
        ["silueta", "estabilidad\nmedia", "ARI ancla mín."],
        [row["silhouette"][0], row["stability_mean"][0], row["anchor_ari_min"][0]],
    )
    p = OUT / "10_metricas_cluster_elegido.png"
    savefig(p, f"Métricas k={k}")
    paths.append(str(p.relative_to(PLOTS_DIR.parent)))

    return paths

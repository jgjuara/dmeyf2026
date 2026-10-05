"""Segmentación BAJA validada temporalmente sobre contribuciones SHAP."""

from __future__ import annotations

import json

import lightgbm as lgb
import numpy as np
import polars as pl
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, roc_auc_score, silhouette_score

from _columns import ANCHOR_PREDICTORS, PROFILE_DOMAINS, anchor_predictor_features
from _config import (
    CLUSTER_SEED,
    K_MAX,
    K_MIN,
    LGBM_PARAMS,
    MIN_CLUSTER_FRAC,
    STABILITY_BOOTSTRAPS,
)
from _paths import TABLES_DIR

MIN_PREDICTORS = 5
MIN_SILHOUETTE = 0.15
MIN_STABILITY_MEAN = 0.70
MIN_STABILITY_P05 = 0.50
MIN_ANCHOR_ARI = 0.50
MIN_TEMPORAL_AUC = 0.55
# Un estrato necesita al menos 20 pares consecutivos: permite observar cada
# origen varias veces sin ocultar los estratos que no alcanzan ese soporte.
MIN_TRANSITION_PAIRS = 20
OPERATIVE_FINANCIAL_VARIABLES = (
    "deuda_total_operativa",
    "patrimonio_liquido_operativo",
)

CLUSTER_PROFILE_TABLES = (
    "cluster_perfiles_shap.csv",
    "cluster_fichas_resumen.csv",
    "cluster_fichas_anclas.csv",
    "cluster_fichas_dominios.csv",
    "cluster_fichas_finanzas_operativas.csv",
    "cluster_fichas_nominales.csv",
    "cluster_fichas_rasgos.csv",
    "cluster_fichas_trayectoria.csv",
    "cluster_top10_global_shap_media_mediana.csv",
    "cluster_edad_antiguedad_descriptivos.csv",
    "cluster_edad_antiguedad_distribucion.csv",
)
TRANSITION_TABLES = (
    "cluster_estados_pre_evento.csv",
    "cluster_ciclo_vida_c0_terminal.csv",
    "cluster_ciclo_vida_c0_terminal_historico.csv",
    "cluster_ciclo_vida_c1_terminal.csv",
    "cluster_ciclo_vida_c1_terminal_historico.csv",
    "cluster_transiciones_pares.csv",
    "cluster_transiciones_cobertura.csv",
    "cluster_transiciones_matriz_estratificada.csv",
    "cluster_transiciones_matriz_mes_relativo.csv",
    "cluster_transiciones_matriz_agregada.csv",
    "cluster_transiciones_resumen_episodio.csv",
    "cluster_transiciones_resumen_agregado.csv",
)

HISTORICAL_LIFECYCLE_DOMAINS = {
    **PROFILE_DOMAINS,
    "otros_indicadores": (
        "active_quarter",
        "cliente_vip",
        "cdescubierto_preacordado",
        "cseguro_vida",
        "cseguro_auto",
    ),
    "finanzas_operativas": OPERATIVE_FINANCIAL_VARIABLES,
}


def _clear_cluster_profile_tables() -> None:
    """Elimina perfiles de una ejecución aceptada que ya no son publicables."""

    for name in CLUSTER_PROFILE_TABLES:
        path = TABLES_DIR / name
        if path.is_file():
            path.unlink()


def _clear_transition_tables() -> None:
    """Elimina transiciones que no pertenecen a la ejecución vigente."""

    for name in TRANSITION_TABLES:
        path = TABLES_DIR / name
        if path.is_file():
            path.unlink()


def _prep_xy(snap: pl.DataFrame) -> tuple[np.ndarray, np.ndarray, list[str]]:
    feats = anchor_predictor_features(snap)
    if len(feats) < MIN_PREDICTORS:
        raise ValueError(
            f"Predictores permitidos insuficientes: {len(feats)} < {MIN_PREDICTORS}."
        )
    work = snap.select(feats + ["grupo"]).fill_null(0)
    X = work.select(feats).to_numpy()
    y = (work["grupo"] == "BAJA").to_numpy().astype(np.int32)
    return X, y, feats


def _fit_classifier(X: np.ndarray, y: np.ndarray) -> lgb.LGBMClassifier:
    clf = lgb.LGBMClassifier(**LGBM_PARAMS)
    clf.fit(X, y)
    return clf


def temporal_validation(
    snap: pl.DataFrame, X: np.ndarray, y: np.ndarray
) -> tuple[pl.DataFrame, bool]:
    """Evalúa cada ancla contra modelos entrenados sólo en las demás anclas."""

    anchors = snap["foto_mes_ancla"].to_numpy()
    rows: list[dict[str, int | float | bool | str]] = []
    for anchor in sorted(np.unique(anchors)):
        test_mask = anchors == anchor
        train_mask = ~test_mask
        y_train, y_test = y[train_mask], y[test_mask]
        valid = len(np.unique(y_train)) == 2 and len(np.unique(y_test)) == 2
        auc = float("nan")
        reason = ""
        if valid:
            clf = _fit_classifier(X[train_mask], y_train)
            auc = float(roc_auc_score(y_test, clf.predict_proba(X[test_mask])[:, 1]))
        else:
            reason = "La ancla o su entrenamiento no contiene ambas clases."
        rows.append(
            {
                "foto_mes_ancla": int(anchor),
                "n_train": int(train_mask.sum()),
                "n_test": int(test_mask.sum()),
                "n_baja_test": int(y_test.sum()),
                "n_continua_test": int((y_test == 0).sum()),
                "auc": auc,
                "apta": bool(valid and auc >= MIN_TEMPORAL_AUC),
                "motivo": reason,
            }
        )
    evaluation = pl.DataFrame(rows)
    return evaluation, evaluation.height > 0 and bool(evaluation["apta"].all())


def train_classifier(
    X: np.ndarray, y: np.ndarray, temporal_eval: pl.DataFrame
) -> tuple[lgb.LGBMClassifier, dict[str, float | int]]:
    clf = _fit_classifier(X, y)
    aucs = temporal_eval["auc"].drop_nulls().drop_nans()
    return clf, {
        "auc_temporal_media": float(aucs.mean()) if aucs.len() else float("nan"),
        "auc_temporal_min": float(aucs.min()) if aucs.len() else float("nan"),
        "n_entrenamiento": int(len(y)),
    }


def shap_matrix(clf: lgb.LGBMClassifier, X: np.ndarray) -> np.ndarray:
    """Contribuciones sin término base (última columna LightGBM)."""
    contrib = clf.booster_.predict(X, pred_contrib=True)
    return contrib[:, :-1]


def _stability_scores(shap_baja: np.ndarray, labels: np.ndarray, k: int) -> list[float]:
    rng = np.random.default_rng(CLUSTER_SEED)
    size = max(k * 2, int(len(shap_baja) * 0.8))
    scores: list[float] = []
    for _ in range(STABILITY_BOOTSTRAPS):
        idx = rng.choice(len(shap_baja), size=size, replace=False)
        sampled = KMeans(n_clusters=k, random_state=CLUSTER_SEED, n_init=10).fit_predict(
            shap_baja[idx]
        )
        scores.append(float(adjusted_rand_score(labels[idx], sampled)))
    return scores


def _anchor_stability(
    shap_baja: np.ndarray, labels: np.ndarray, anchors: np.ndarray, k: int, min_size: int
) -> float:
    scores: list[float] = []
    for anchor in np.unique(anchors):
        idx = np.flatnonzero(anchors == anchor)
        if len(idx) < max(k * 2, min_size):
            return float("nan")
        sampled = KMeans(n_clusters=k, random_state=CLUSTER_SEED, n_init=10).fit_predict(
            shap_baja[idx]
        )
        scores.append(float(adjusted_rand_score(labels[idx], sampled)))
    return float(np.min(scores)) if scores else float("nan")


def choose_k(shap_baja: np.ndarray, anchors: np.ndarray) -> tuple[int | None, pl.DataFrame]:
    """Acepta un corte sólo si tamaño, silueta y estabilidad son suficientes."""

    min_size = max(20, int(np.ceil(len(shap_baja) * MIN_CLUSTER_FRAC)))
    rows: list[dict[str, object]] = []
    best_k: int | None = None
    best_score = -np.inf
    for k in range(K_MIN, K_MAX + 1):
        if k >= len(shap_baja):
            break
        km = KMeans(n_clusters=k, random_state=CLUSTER_SEED, n_init=10)
        labels = km.fit_predict(shap_baja)
        sizes = np.bincount(labels, minlength=k)
        enough_size = int(sizes.min()) >= min_size
        sil = float(silhouette_score(shap_baja, labels)) if enough_size else float("nan")
        scores = _stability_scores(shap_baja, labels, k) if enough_size else []
        stability_mean = float(np.mean(scores)) if scores else float("nan")
        stability_p05 = float(np.quantile(scores, 0.05)) if scores else float("nan")
        anchor_ari = (
            _anchor_stability(shap_baja, labels, anchors, k, min_size)
            if enough_size
            else float("nan")
        )
        accepted = bool(
            enough_size
            and sil >= MIN_SILHOUETTE
            and stability_mean >= MIN_STABILITY_MEAN
            and stability_p05 >= MIN_STABILITY_P05
            and anchor_ari >= MIN_ANCHOR_ARI
        )
        rows.append(
            {
                "k": k,
                "min_cluster": int(sizes.min()),
                "max_cluster": int(sizes.max()),
                "min_cluster_required": min_size,
                "silhouette": sil,
                "stability_mean": stability_mean,
                "stability_p05": stability_p05,
                "anchor_ari_min": anchor_ari,
                "aceptado": accepted,
                "stability_scores": json.dumps(scores),
            }
        )
        if accepted and sil > best_score:
            best_score = sil
            best_k = k
    return best_k, pl.DataFrame(rows)


def _control_mean_by_cluster(
    snap: pl.DataFrame, member_ids: list[str], variable: str
) -> float:
    members = snap.filter(pl.col("cohort_member_id").is_in(member_ids))
    weights = (
        members.group_by("foto_mes_ancla", "horizonte_evento")
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


def _control_summary_by_cluster(
    snap: pl.DataFrame, member_ids: list[str], variable: str
) -> tuple[int, float, float]:
    """Resume CONTINUA con los pesos de ancla y horizonte del segmento."""

    members = snap.filter(pl.col("cohort_member_id").is_in(member_ids))
    weights = (
        members.group_by("foto_mes_ancla", "horizonte_evento")
        .len()
        .rename({"len": "peso"})
    )
    controls = (
        snap.filter(pl.col("grupo") == "CONTINUA")
        .select("foto_mes_ancla", "horizonte_evento", variable)
        .join(weights, on=["foto_mes_ancla", "horizonte_evento"], how="inner")
    )
    values = controls[variable].to_numpy().astype(float, copy=False)
    weights_array = controls["peso"].to_numpy().astype(np.int64, copy=False)
    valid = np.isfinite(values) & (weights_array > 0)
    values = values[valid]
    weights_array = weights_array[valid]
    if not values.size:
        return 0, float("nan"), float("nan")
    expanded = np.repeat(values, weights_array)
    return controls.height, float(np.mean(expanded)), float(np.median(expanded))


def _numeric_values(frame: pl.DataFrame, variable: str) -> np.ndarray:
    """Devuelve observaciones finitas para descriptivos de una variable numérica."""

    values = frame[variable].to_numpy().astype(float, copy=False)
    return values[np.isfinite(values)]


def _percent_difference(value: float, reference: float) -> float:
    """Calcula la diferencia porcentual con denominador CONTINUA no nulo."""

    if not np.isfinite(value) or not np.isfinite(reference) or reference == 0:
        return float("nan")
    return float(100 * (value - reference) / abs(reference))


def _demographic_interval(variable: str, value: float) -> str:
    """Asigna intervalos exhaustivos y comparables para edad y antigüedad."""

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


def _demographic_intervals(variable: str) -> tuple[str, ...]:
    """Expone el orden estable de los intervalos publicados."""

    if variable == "cliente_edad":
        return (
            "Menor de 18",
            "18-24",
            "25-34",
            "35-44",
            "45-54",
            "55-64",
            "65-74",
            "75 o más",
            "Sin dato",
        )
    return (
        "Hasta 12 meses",
        "13-36 meses",
        "37-60 meses",
        "61-120 meses",
        "121-240 meses",
        "Más de 240 meses",
        "Sin dato",
    )


def _write_executive_tables(
    panel: pl.DataFrame,
    snap: pl.DataFrame,
    assign: pl.DataFrame,
    feats: list[str],
    shap_baja: np.ndarray,
    labels: np.ndarray,
    top_global_features: list[str],
) -> None:
    """Materializa fichas cuantitativas sin etiquetas interpretativas."""

    sizes = assign.group_by("cluster").len().rename({"len": "n"}).sort("cluster")
    summary = sizes.with_columns((pl.col("n") / assign.height).alias("peso"))
    composition = (
        assign.group_by("cluster", "clase_ancla")
        .len()
        .pivot(on="clase_ancla", index="cluster", values="len", aggregate_function="sum")
        .fill_null(0)
    )
    summary.join(composition, on="cluster", how="left").write_csv(
        TABLES_DIR / "cluster_fichas_resumen.csv"
    )
    (
        assign.group_by("cluster", "foto_mes_ancla", "mes_evento_esperado")
        .len()
        .rename({"len": "n"})
        .join(sizes, on="cluster")
        .with_columns((pl.col("n") / pl.col("n_right")).alias("peso_cluster"))
        .drop("n_right")
        .sort("cluster", "foto_mes_ancla")
        .write_csv(TABLES_DIR / "cluster_fichas_anclas.csv")
    )

    domain_rows: list[dict[str, object]] = []
    for cluster in sorted(assign["cluster"].unique().to_list()):
        ids = assign.filter(pl.col("cluster") == cluster)["cohort_member_id"].to_list()
        members = snap.filter(pl.col("cohort_member_id").is_in(ids))
        for domain, candidates in PROFILE_DOMAINS.items():
            for variable in (name for name in candidates if name in snap.columns):
                values = _numeric_values(members, variable)
                mean_control = _control_mean_by_cluster(snap, ids, variable)
                n_control, _, median_control = _control_summary_by_cluster(snap, ids, variable)
                mean_cluster = float(np.mean(values)) if values.size else float("nan")
                domain_rows.append(
                    {
                        "cluster": cluster,
                        "dominio": domain,
                        "variable": variable,
                        "n_segmento": int(values.size),
                        "media_segmento": mean_cluster,
                        "mediana_segmento": float(np.median(values)) if values.size else float("nan"),
                        "n_continua_emparejada": n_control,
                        "media_continua_emparejada": mean_control,
                        "mediana_continua_emparejada": median_control,
                        "brecha_vs_continua": mean_cluster - mean_control,
                    }
                )
    pl.DataFrame(domain_rows).sort("cluster", "dominio", "variable").write_csv(
        TABLES_DIR / "cluster_fichas_dominios.csv"
    )

    nominal_variables = tuple(dict.fromkeys((*ANCHOR_PREDICTORS, *OPERATIVE_FINANCIAL_VARIABLES)))
    domain_by_variable = {
        variable: domain
        for domain, variables in HISTORICAL_LIFECYCLE_DOMAINS.items()
        for variable in variables
    }
    nominal_rows: list[dict[str, object]] = []
    for cluster in sorted(assign["cluster"].unique().to_list()):
        ids = assign.filter(pl.col("cluster") == cluster)["cohort_member_id"].to_list()
        members = snap.filter(pl.col("cohort_member_id").is_in(ids))
        for variable in (name for name in nominal_variables if name in snap.columns):
            values = _numeric_values(members, variable)
            n_control, mean_control, median_control = _control_summary_by_cluster(
                snap, ids, variable
            )
            mean_segment = float(np.mean(values)) if values.size else float("nan")
            median_segment = float(np.median(values)) if values.size else float("nan")
            nominal_rows.append(
                {
                    "cluster": cluster,
                    "dominio": domain_by_variable.get(variable, "otros_indicadores"),
                    "variable": variable,
                    "n_segmento": int(values.size),
                    "media_segmento": mean_segment,
                    "mediana_segmento": median_segment,
                    "n_continua_emparejada": n_control,
                    "media_continua_emparejada": mean_control,
                    "mediana_continua_emparejada": median_control,
                    "brecha_nominal_vs_continua": mean_segment - mean_control,
                    "diferencia_pct_vs_continua": _percent_difference(
                        mean_segment, mean_control
                    ),
                }
            )
    pl.DataFrame(nominal_rows).sort("cluster", "dominio", "variable").write_csv(
        TABLES_DIR / "cluster_fichas_nominales.csv"
    )

    financial_rows: list[dict[str, object]] = []
    for cluster in sorted(assign["cluster"].unique().to_list()):
        ids = assign.filter(pl.col("cluster") == cluster)["cohort_member_id"].to_list()
        members = snap.filter(pl.col("cohort_member_id").is_in(ids))
        for variable in OPERATIVE_FINANCIAL_VARIABLES:
            values = _numeric_values(members, variable)
            n_control, mean_control, median_control = _control_summary_by_cluster(
                snap, ids, variable
            )
            mean_segment = float(np.mean(values)) if values.size else float("nan")
            median_segment = float(np.median(values)) if values.size else float("nan")
            financial_rows.append(
                {
                    "cluster": cluster,
                    "variable": variable,
                    "n_segmento": int(values.size),
                    "media_segmento": mean_segment,
                    "mediana_segmento": median_segment,
                    "n_continua_emparejada": n_control,
                    "media_continua_emparejada": mean_control,
                    "mediana_continua_emparejada": median_control,
                    "brecha_media_vs_continua": mean_segment - mean_control,
                    "brecha_mediana_vs_continua": median_segment - median_control,
                }
            )
    pl.DataFrame(financial_rows).sort("cluster", "variable").write_csv(
        TABLES_DIR / "cluster_fichas_finanzas_operativas.csv"
    )

    trait_rows: list[dict[str, object]] = []
    for cluster in sorted(assign["cluster"].unique().to_list()):
        mean_shap = shap_baja[labels == cluster].mean(axis=0)
        for rank, idx in enumerate(np.argsort(np.abs(mean_shap))[::-1][:3], start=1):
            trait_rows.append(
                {
                    "cluster": cluster,
                    "rango": rank,
                    "variable": feats[idx],
                    "mean_shap": float(mean_shap[idx]),
                    "direccion_vs_continua": "mayor" if mean_shap[idx] > 0 else "menor",
                }
            )
    pl.DataFrame(trait_rows).write_csv(TABLES_DIR / "cluster_fichas_rasgos.csv")

    top_rows: list[dict[str, object]] = []
    demographic_descriptive_rows: list[dict[str, object]] = []
    demographic_distribution_rows: list[dict[str, object]] = []
    demographic_variables = ("cliente_edad", "cliente_antiguedad")
    for cluster in sorted(assign["cluster"].unique().to_list()):
        ids = assign.filter(pl.col("cluster") == cluster)["cohort_member_id"].to_list()
        members = snap.filter(pl.col("cohort_member_id").is_in(ids))
        for rank, variable in enumerate(top_global_features, start=1):
            values = _numeric_values(members, variable)
            n_control, _, median_control = _control_summary_by_cluster(snap, ids, variable)
            mean_control = _control_mean_by_cluster(snap, ids, variable)
            mean_segment = float(np.mean(values)) if values.size else float("nan")
            top_rows.append(
                {
                    "cluster": cluster,
                    "rango_importancia_global": rank,
                    "variable": variable,
                    "n": int(values.size),
                    "media_ancla": mean_segment,
                    "mediana_ancla": float(np.median(values)) if values.size else None,
                    "n_continua_emparejada": n_control,
                    "media_continua_emparejada": mean_control,
                    "mediana_continua_emparejada": median_control,
                    "brecha_vs_continua": mean_segment - mean_control,
                }
            )
        for variable in demographic_variables:
            values = _numeric_values(members, variable)
            demographic_descriptive_rows.append(
                {
                    "cluster": cluster,
                    "variable": variable,
                    "n": int(values.size),
                    "media": float(np.mean(values)) if values.size else None,
                    "mediana": float(np.median(values)) if values.size else None,
                    "p10": float(np.quantile(values, 0.10)) if values.size else None,
                    "p25": float(np.quantile(values, 0.25)) if values.size else None,
                    "p75": float(np.quantile(values, 0.75)) if values.size else None,
                    "p90": float(np.quantile(values, 0.90)) if values.size else None,
                    "minimo": float(np.min(values)) if values.size else None,
                    "maximo": float(np.max(values)) if values.size else None,
                }
            )
            intervals = _demographic_intervals(variable)
            counts = dict.fromkeys(intervals, 0)
            for value in members[variable].to_numpy().astype(float, copy=False):
                interval = (
                    _demographic_interval(variable, value)
                    if np.isfinite(value)
                    else "Sin dato"
                )
                counts[interval] += 1
            for order, interval in enumerate(intervals, start=1):
                count = counts[interval]
                demographic_distribution_rows.append(
                    {
                        "cluster": cluster,
                        "variable": variable,
                        "orden_intervalo": order,
                        "intervalo": interval,
                        "n": count,
                        "porcentaje": count / members.height,
                    }
                )
    pl.DataFrame(top_rows).sort("cluster", "rango_importancia_global").write_csv(
        TABLES_DIR / "cluster_top10_global_shap_media_mediana.csv"
    )
    pl.DataFrame(demographic_descriptive_rows).sort("cluster", "variable").write_csv(
        TABLES_DIR / "cluster_edad_antiguedad_descriptivos.csv"
    )
    pl.DataFrame(
        demographic_distribution_rows
    ).sort("cluster", "variable", "orden_intervalo").write_csv(
        TABLES_DIR / "cluster_edad_antiguedad_distribucion.csv"
    )

    trajectory_vars = [
        name
        for domain in PROFILE_DOMAINS.values()
        for name in domain
        if name in panel.columns
    ]
    assigned_panel = panel.join(
        assign.select("cohort_member_id", "cluster"), on="cohort_member_id", how="inner"
    ).filter(pl.col("mes_relativo") < 0)
    trajectories: list[pl.DataFrame] = []
    for variable in trajectory_vars:
        segments = (
            assigned_panel.group_by("cluster", "mes_relativo")
            .agg(
                pl.col("cohort_member_id").n_unique().alias("n_episodios_observados"),
                pl.col(variable).mean().alias("media_segmento"),
            )
            .with_columns(pl.lit(variable).alias("variable"))
        )
        controls = (
            panel.filter((pl.col("grupo") == "CONTINUA") & (pl.col("mes_relativo") < 0))
            .group_by("mes_relativo")
            .agg(pl.col(variable).mean().alias("media_continua"))
        )
        trajectories.append(
            segments.join(controls, on="mes_relativo", how="left").with_columns(
                (pl.col("media_segmento") - pl.col("media_continua")).alias(
                    "brecha_vs_continua"
                )
            )
        )
    pl.concat(trajectories).sort("cluster", "variable", "mes_relativo").write_csv(
        TABLES_DIR / "cluster_fichas_trayectoria.csv"
    )


def _month_ordinal(month: int) -> int:
    """Convierte YYYYMM a un ordinal mensual para validar adyacencia calendario."""

    return (month // 100) * 12 + month % 100


def _transition_matrix(
    pairs: pl.DataFrame, keys: list[str], coverage: pl.DataFrame
) -> pl.DataFrame:
    """Calcula probabilidades por origen sin promediar probabilidades de estratos."""

    counts = (
        pairs.group_by(keys + ["estado_origen", "estado_destino"])
        .len()
        .rename({"len": "n_pares"})
    )
    denominators = (
        counts.group_by(keys + ["estado_origen"])
        .agg(pl.col("n_pares").sum().alias("n_pares_origen"))
    )
    matrix = (
        counts.join(denominators, on=keys + ["estado_origen"], how="left")
        .with_columns((pl.col("n_pares") / pl.col("n_pares_origen")).alias("probabilidad"))
    )
    if {"foto_mes_ancla", "horizonte_evento"}.issubset(keys):
        matrix = matrix.join(
            coverage.select(
                "foto_mes_ancla",
                "horizonte_evento",
                "n_pares_observados",
                "publicable",
                "motivo_no_publicable",
            ),
            on=["foto_mes_ancla", "horizonte_evento"],
            how="left",
        )
    return matrix.sort(keys + ["estado_origen", "estado_destino"])


def _terminal_cluster_balance_lifecycle(
    panel: pl.DataFrame, states: pl.DataFrame, terminal_cluster: int
) -> pl.DataFrame:
    """Resume el saldo previo de episodios cuyo último estado observable es un clúster."""

    columns = {
        "mes_relativo": pl.Int64,
        "n_episodios_observados": pl.Int64,
        "media_saldo_cluster_terminal": pl.Float64,
        "mediana_saldo_cluster_terminal": pl.Float64,
        "n_controles_observados": pl.Int64,
        "media_saldo_continua_ponderada": pl.Float64,
        "brecha_media_cluster_menos_continua": pl.Float64,
    }
    terminal_members = states.filter(
        (pl.col("mes_relativo") == -1) & (pl.col("estado_temporal") == terminal_cluster)
    ).select("cohort_member_id")
    if terminal_members.is_empty():
        return pl.DataFrame(schema=columns)

    cases = (
        panel.filter((pl.col("grupo") == "BAJA") & (pl.col("mes_relativo") < 0))
        .join(terminal_members, on="cohort_member_id", how="inner")
        .select(
            "cohort_member_id",
            "foto_mes_ancla",
            "horizonte_evento",
            "mes_relativo",
            "mcuentas_saldo",
        )
    )
    case_levels = (
        cases.group_by("mes_relativo")
        .agg(
            pl.col("cohort_member_id").n_unique().alias("n_episodios_observados"),
            pl.col("mcuentas_saldo").mean().alias("media_saldo_cluster_terminal"),
            pl.col("mcuentas_saldo").median().alias("mediana_saldo_cluster_terminal"),
        )
    )
    case_weights = (
        cases.group_by("foto_mes_ancla", "horizonte_evento", "mes_relativo")
        .agg(pl.col("cohort_member_id").n_unique().alias("_peso_episodios"))
    )
    control_levels = (
        panel.filter((pl.col("grupo") == "CONTINUA") & (pl.col("mes_relativo") < 0))
        .group_by("foto_mes_ancla", "horizonte_evento", "mes_relativo")
        .agg(
            pl.col("cohort_member_id").n_unique().alias("n_controles_observados"),
            pl.col("mcuentas_saldo").mean().alias("_media_saldo_continua"),
        )
    )
    controls = (
        case_weights.join(
            control_levels,
            on=["foto_mes_ancla", "horizonte_evento", "mes_relativo"],
            how="inner",
        )
        .with_columns(
            (pl.col("_peso_episodios") * pl.col("_media_saldo_continua")).alias(
                "_saldo_continua_ponderado"
            )
        )
        .group_by("mes_relativo")
        .agg(
            pl.col("n_controles_observados").sum().alias("n_controles_observados"),
            pl.col("_peso_episodios").sum().alias("_peso_total"),
            pl.col("_saldo_continua_ponderado").sum().alias("_saldo_total"),
        )
        .with_columns(
            (pl.col("_saldo_total") / pl.col("_peso_total")).alias(
                "media_saldo_continua_ponderada"
            )
        )
        .drop("_peso_total", "_saldo_total")
    )
    return (
        case_levels.join(controls, on="mes_relativo", how="left")
        .with_columns(
            (
                pl.col("media_saldo_cluster_terminal")
                - pl.col("media_saldo_continua_ponderada")
            ).alias("brecha_media_cluster_menos_continua")
        )
        .sort("mes_relativo")
    )


def _terminal_cluster_historical_profile(
    panel: pl.DataFrame, states: pl.DataFrame, terminal_cluster: int
) -> pl.DataFrame:
    """Materializa niveles previos de variables admitidas para un clúster terminal."""

    columns = {
        "dominio": pl.String,
        "variable": pl.String,
        "mes_relativo": pl.Int64,
        "n_episodios_observados": pl.Int64,
        "media_cluster_terminal": pl.Float64,
        "mediana_cluster_terminal": pl.Float64,
        "n_controles_observados": pl.Int64,
        "media_continua_ponderada": pl.Float64,
        "brecha_media_cluster_menos_continua": pl.Float64,
    }
    terminal_members = states.filter(
        (pl.col("mes_relativo") == -1) & (pl.col("estado_temporal") == terminal_cluster)
    ).select("cohort_member_id")
    variables = [
        variable
        for variable in (*ANCHOR_PREDICTORS, *OPERATIVE_FINANCIAL_VARIABLES)
        if variable in panel.columns
    ]
    if terminal_members.is_empty() or not variables:
        return pl.DataFrame(schema=columns)

    domain_by_variable = {
        variable: domain
        for domain, domain_variables in HISTORICAL_LIFECYCLE_DOMAINS.items()
        for variable in domain_variables
    }
    cases = (
        panel.filter((pl.col("grupo") == "BAJA") & (pl.col("mes_relativo") < 0))
        .join(terminal_members, on="cohort_member_id", how="inner")
        .select(
            "cohort_member_id",
            "foto_mes_ancla",
            "horizonte_evento",
            "mes_relativo",
            *variables,
        )
    )
    controls = panel.filter(
        (pl.col("grupo") == "CONTINUA") & (pl.col("mes_relativo") < 0)
    ).select(
        "cohort_member_id",
        "foto_mes_ancla",
        "horizonte_evento",
        "mes_relativo",
        *variables,
    )
    rows: list[pl.DataFrame] = []
    strata = ["foto_mes_ancla", "horizonte_evento", "mes_relativo"]
    for variable in variables:
        observed_cases = cases.filter(pl.col(variable).is_not_null())
        case_levels = observed_cases.group_by("mes_relativo").agg(
            pl.col("cohort_member_id").n_unique().alias("n_episodios_observados"),
            pl.col(variable).mean().alias("media_cluster_terminal"),
            pl.col(variable).median().alias("mediana_cluster_terminal"),
        )
        case_weights = observed_cases.group_by(strata).agg(
            pl.col("cohort_member_id").n_unique().alias("_peso_episodios")
        )
        control_levels = (
            controls.filter(pl.col(variable).is_not_null())
            .group_by(strata)
            .agg(
                pl.col("cohort_member_id").n_unique().alias("n_controles_observados"),
                pl.col(variable).mean().alias("_media_continua"),
            )
        )
        weighted_controls = (
            case_weights.join(control_levels, on=strata, how="inner")
            .with_columns(
                (pl.col("_peso_episodios") * pl.col("_media_continua")).alias(
                    "_saldo_continua_ponderado"
                )
            )
            .group_by("mes_relativo")
            .agg(
                pl.col("n_controles_observados").sum().alias("n_controles_observados"),
                pl.col("_peso_episodios").sum().alias("_peso_total"),
                pl.col("_saldo_continua_ponderado").sum().alias("_saldo_total"),
            )
            .with_columns(
                (pl.col("_saldo_total") / pl.col("_peso_total")).alias(
                    "media_continua_ponderada"
                )
            )
            .drop("_peso_total", "_saldo_total")
        )
        rows.append(
            case_levels.join(weighted_controls, on="mes_relativo", how="left")
            .with_columns(
                pl.lit(domain_by_variable.get(variable, "otros_indicadores")).alias("dominio"),
                pl.lit(variable).alias("variable"),
                (
                    pl.col("media_cluster_terminal") - pl.col("media_continua_ponderada")
                ).alias("brecha_media_cluster_menos_continua"),
            )
            .select(list(columns))
        )
    return pl.concat(rows).sort("dominio", "variable", "mes_relativo")


def run_temporal_transitions(panel: pl.DataFrame, cluster_out: dict) -> dict:
    """Puntúa estados previos con el modelo y KMeans del ancla, sin reentrenarlos.

    Las matrices agregadas incluyen sólo estratos con al menos
    ``MIN_TRANSITION_PAIRS`` pares consecutivos observados. La tabla de cobertura y
    la matriz estratificada conservan también los estratos no publicables.
    """

    _clear_transition_tables()
    if not cluster_out["accepted"]:
        return {
            "available": False,
            "min_pairs_per_stratum": MIN_TRANSITION_PAIRS,
            "reason": "La segmentación no fue aceptada.",
        }

    clf: lgb.LGBMClassifier = cluster_out["clf"]
    kmeans: KMeans = cluster_out["kmeans"]
    feats: list[str] = cluster_out["feats"]
    required = {
        "cohort_member_id",
        "foto_mes",
        "foto_mes_ancla",
        "horizonte_evento",
        "mes_relativo",
        "grupo",
    }
    missing = sorted(required - set(panel.columns))
    if missing:
        raise ValueError(f"El panel no permite transiciones; faltan columnas: {missing}")
    missing_features = sorted(set(feats) - set(panel.columns))
    if missing_features:
        raise ValueError(
            f"El panel no contiene predictores para estados temporales: {missing_features}"
        )

    pre_event = panel.filter(
        (pl.col("grupo") == "BAJA") & (pl.col("mes_relativo") < 0)
    ).sort("cohort_member_id", "foto_mes")
    if pre_event.is_empty():
        raise ValueError("No hay fotos BAJA previas al evento para construir estados.")

    available_predictors = pl.sum_horizontal(
        [pl.col(feature).is_not_null().cast(pl.Int64) for feature in feats]
    ).alias("n_predictores_observados")
    X = pre_event.select(feats).fill_null(0).to_numpy()
    predictor_support = pre_event.select(available_predictors)["n_predictores_observados"]
    states = pre_event.select(
        "cohort_member_id",
        "numero_de_cliente",
        "foto_mes",
        "foto_mes_ancla",
        "horizonte_evento",
        "mes_evento_esperado",
        "mes_relativo",
        "grupo",
    ).with_columns(
        pl.Series("estado_temporal", kmeans.predict(shap_matrix(clf, X))),
        predictor_support,
        pl.lit(len(feats)).alias("n_predictores_permitidos"),
    ).sort("cohort_member_id", "foto_mes")

    expected = cluster_out["assign"].select("cohort_member_id", "cluster").sort(
        "cohort_member_id"
    )
    anchor_states = (
        states.filter(pl.col("foto_mes") == pl.col("foto_mes_ancla"))
        .select("cohort_member_id", "estado_temporal")
        .sort("cohort_member_id")
    )
    same_members = (
        anchor_states.height == expected.height
        and anchor_states["cohort_member_id"].to_list()
        == expected["cohort_member_id"].to_list()
    )
    same_labels = (
        same_members
        and anchor_states["estado_temporal"].to_list() == expected["cluster"].to_list()
    )
    if not same_labels:
        raise ValueError(
            "La asignación temporal al ancla no reproduce cluster_asignaciones_baja.csv; "
            "se cancela la publicación de transiciones."
        )
    states.write_csv(TABLES_DIR / "cluster_estados_pre_evento.csv")
    for terminal_cluster in (0, 1):
        _terminal_cluster_balance_lifecycle(panel, states, terminal_cluster).write_csv(
            TABLES_DIR / f"cluster_ciclo_vida_c{terminal_cluster}_terminal.csv"
        )
        _terminal_cluster_historical_profile(panel, states, terminal_cluster).write_csv(
            TABLES_DIR / f"cluster_ciclo_vida_c{terminal_cluster}_terminal_historico.csv"
        )

    sequenced = states.with_columns(
        (((pl.col("foto_mes") // 100) * 12) + (pl.col("foto_mes") % 100)).alias("_orden_mes"),
        pl.col("foto_mes").shift(-1).over("cohort_member_id").alias("_foto_mes_destino"),
        pl.col("mes_relativo").shift(-1).over("cohort_member_id").alias("_mes_relativo_destino"),
        pl.col("estado_temporal").shift(-1).over("cohort_member_id").alias("_estado_destino"),
        (((pl.col("foto_mes") // 100) * 12) + (pl.col("foto_mes") % 100))
        .shift(-1)
        .over("cohort_member_id")
        .alias("_orden_mes_destino"),
    )
    pairs = (
        sequenced.filter(pl.col("_orden_mes_destino") == pl.col("_orden_mes") + 1)
        .select(
            "cohort_member_id",
            "foto_mes_ancla",
            "horizonte_evento",
            "mes_evento_esperado",
            pl.col("foto_mes").alias("foto_mes_origen"),
            pl.col("_foto_mes_destino").alias("foto_mes_destino"),
            pl.col("mes_relativo").alias("mes_relativo_origen"),
            pl.col("_mes_relativo_destino").alias("mes_relativo_destino"),
            pl.col("estado_temporal").alias("estado_origen"),
            pl.col("_estado_destino").alias("estado_destino"),
        )
        .sort("cohort_member_id", "foto_mes_origen")
    )
    pairs.write_csv(TABLES_DIR / "cluster_transiciones_pares.csv")

    coverage_states = (
        states.group_by("foto_mes_ancla", "horizonte_evento")
        .agg(
            pl.col("cohort_member_id").n_unique().alias("n_episodios"),
            pl.len().alias("n_fotos_pre_evento"),
        )
    )
    coverage_pairs = (
        pairs.group_by("foto_mes_ancla", "horizonte_evento")
        .agg(
            pl.len().alias("n_pares_observados"),
            pl.col("cohort_member_id").n_unique().alias("n_episodios_con_pares"),
        )
    )
    coverage = (
        coverage_states.join(
            coverage_pairs, on=["foto_mes_ancla", "horizonte_evento"], how="left"
        )
        .with_columns(
            pl.col("n_pares_observados").fill_null(0).cast(pl.Int64),
            pl.col("n_episodios_con_pares").fill_null(0).cast(pl.Int64),
        )
        .with_columns(
            (pl.col("n_pares_observados") >= MIN_TRANSITION_PAIRS).alias("publicable"),
            pl.when(pl.col("n_pares_observados") >= MIN_TRANSITION_PAIRS)
            .then(pl.lit(""))
            .otherwise(
                pl.format(
                    "Soporte insuficiente: {} pares observados < mínimo {}.",
                    pl.col("n_pares_observados"),
                    MIN_TRANSITION_PAIRS,
                )
            )
            .alias("motivo_no_publicable"),
        )
        .sort("foto_mes_ancla", "horizonte_evento")
    )
    coverage.write_csv(TABLES_DIR / "cluster_transiciones_cobertura.csv")

    stratified = _transition_matrix(
        pairs,
        [
            "foto_mes_ancla",
            "horizonte_evento",
            "mes_relativo_origen",
            "mes_relativo_destino",
        ],
        coverage,
    )
    stratified.write_csv(TABLES_DIR / "cluster_transiciones_matriz_estratificada.csv")

    published_pairs = pairs.join(
        coverage.filter(pl.col("publicable")).select(
            "foto_mes_ancla", "horizonte_evento"
        ),
        on=["foto_mes_ancla", "horizonte_evento"],
        how="inner",
    )
    by_relative = _transition_matrix(
        published_pairs,
        ["mes_relativo_origen", "mes_relativo_destino"],
        coverage,
    )
    by_relative.write_csv(TABLES_DIR / "cluster_transiciones_matriz_mes_relativo.csv")
    aggregated = (
        published_pairs.group_by("estado_origen", "estado_destino")
        .agg(
            pl.len().alias("n_pares"),
            pl.struct(["foto_mes_ancla", "horizonte_evento"])
            .n_unique()
            .alias("n_estratos_contributivos"),
        )
    )
    aggregate_denominators = (
        aggregated.group_by("estado_origen")
        .agg(pl.col("n_pares").sum().alias("n_pares_origen"))
    )
    aggregated = (
        aggregated.join(aggregate_denominators, on="estado_origen", how="left")
        .with_columns((pl.col("n_pares") / pl.col("n_pares_origen")).alias("probabilidad"))
        .sort("estado_origen", "estado_destino")
    )
    aggregated.write_csv(TABLES_DIR / "cluster_transiciones_matriz_agregada.csv")

    episode_rows: list[dict[str, object]] = []
    for episode in states.partition_by("cohort_member_id", maintain_order=True):
        ordered = episode.sort("foto_mes")
        relative = ordered["mes_relativo"].to_list()
        months = ordered["foto_mes"].to_list()
        temporal_states = ordered["estado_temporal"].to_list()
        minus_one = ordered.filter(pl.col("mes_relativo") == -1)
        has_minus_one = minus_one.height == 1
        first_ordinal = _month_ordinal(months[0])
        last_ordinal = _month_ordinal(months[-1])
        complete_path = bool(
            has_minus_one
            and relative[-1] == -1
            and len(months) == last_ordinal - first_ordinal + 1
        )
        changed = (
            temporal_states[0] != int(minus_one["estado_temporal"][0])
            if complete_path
            else None
        )
        episode_rows.append(
            {
                "cohort_member_id": ordered["cohort_member_id"][0],
                "foto_mes_ancla": ordered["foto_mes_ancla"][0],
                "horizonte_evento": ordered["horizonte_evento"][0],
                "estado_inicial_observable": temporal_states[0],
                "estado_menos_1": int(minus_one["estado_temporal"][0]) if has_minus_one else None,
                "n_fotos_pre_evento": ordered.height,
                "n_pares_consecutivos": max(ordered.height - 1, 0)
                if complete_path
                else int(
                    pairs.filter(
                        pl.col("cohort_member_id") == ordered["cohort_member_id"][0]
                    ).height
                ),
                "trayecto_completo_hasta_menos_1": complete_path,
                "cambio_entre_extremos": changed,
                "motivo_no_comparable": ""
                if complete_path
                else "Falta foto -1 o hay meses calendario no consecutivos.",
            }
        )
    episode_summary = pl.DataFrame(episode_rows).sort("cohort_member_id")
    episode_summary.write_csv(TABLES_DIR / "cluster_transiciones_resumen_episodio.csv")

    comparable = episode_summary.filter(pl.col("trayecto_completo_hasta_menos_1"))
    n_pairs = published_pairs.height
    n_stay_pairs = published_pairs.filter(pl.col("estado_origen") == pl.col("estado_destino")).height
    n_changed_pairs = n_pairs - n_stay_pairs
    n_comparable = comparable.height
    n_changed_episodes = comparable.filter(pl.col("cambio_entre_extremos")).height
    summary = pl.DataFrame(
        {
            "min_pares_por_estrato": [MIN_TRANSITION_PAIRS],
            "n_estratos_total": [coverage.height],
            "n_estratos_publicables": [coverage.filter(pl.col("publicable")).height],
            "n_pares_publicados": [n_pairs],
            "n_pares_permanencia": [n_stay_pairs],
            "n_pares_migracion": [n_changed_pairs],
            "tasa_permanencia_pares": [n_stay_pairs / n_pairs if n_pairs else None],
            "tasa_migracion_pares": [n_changed_pairs / n_pairs if n_pairs else None],
            "n_episodios_comparables": [n_comparable],
            "n_episodios_cambio_extremos": [n_changed_episodes],
            "tasa_cambio_extremos": [
                n_changed_episodes / n_comparable if n_comparable else None
            ],
        }
    )
    summary.write_csv(TABLES_DIR / "cluster_transiciones_resumen_agregado.csv")
    return {
        "available": True,
        "min_pairs_per_stratum": MIN_TRANSITION_PAIRS,
        "n_published_strata": int(coverage.filter(pl.col("publicable")).height),
        "n_published_pairs": n_pairs,
        "aggregate_matrix": aggregated,
        "coverage": coverage,
        "summary": summary,
    }


def run_clustering(panel: pl.DataFrame) -> dict:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    snap = panel.filter(pl.col("foto_mes") == pl.col("foto_mes_ancla"))
    required_meta = {
        "cohort_member_id",
        "horizonte_evento",
        "foto_mes_ancla",
        "mes_evento_esperado",
        "grupo",
    }
    missing_meta = sorted(required_meta - set(snap.columns))
    if missing_meta:
        raise ValueError(f"El contrato de cohorte no contiene: {missing_meta}")
    X_all, y_all, feats = _prep_xy(snap)
    temporal_eval, temporal_accepted = temporal_validation(snap, X_all, y_all)
    temporal_eval.write_csv(TABLES_DIR / "cluster_validacion_temporal.csv")
    clf, metrics = train_classifier(X_all, y_all, temporal_eval)
    shap_all = shap_matrix(clf, X_all)
    baja_mask = y_all == 1
    shap_baja = shap_all[baja_mask]
    baja_snap = snap.filter(pl.col("grupo") == "BAJA")
    k, eval_df = choose_k(shap_baja, baja_snap["foto_mes_ancla"].to_numpy())
    eval_df.write_csv(TABLES_DIR / "cluster_evaluacion_k.csv")

    global_imp = np.abs(shap_baja).mean(axis=0)
    imp_df = pl.DataFrame({"feature": feats, "mean_abs_shap": global_imp}).sort(
        "mean_abs_shap", descending=True
    )
    imp_df.write_csv(TABLES_DIR / "cluster_importancia_global_shap.csv")
    top_global_features = imp_df.head(10)["feature"].to_list()

    accepted = temporal_accepted and k is not None
    reasons: list[str] = []
    if not temporal_accepted:
        reasons.append("La discriminación temporal por ancla no supera el umbral en todas las anclas.")
    if k is None:
        reasons.append("Ningún número de segmentos cumple tamaño, silueta y estabilidad.")
    selected_silhouette = (
        float(eval_df.filter(pl.col("k") == k)["silhouette"][0]) if k is not None else float("nan")
    )
    meta = {
        **metrics,
        # Compatibilidad con el orquestador e informe aún no migrados.
        "auc_holdout": metrics["auc_temporal_media"],
        "silhouette_elegido": selected_silhouette,
        "n_features": len(feats),
        "predictores_permitidos": feats,
        "umbral_auc_temporal": MIN_TEMPORAL_AUC,
        "umbral_silueta": MIN_SILHOUETTE,
        "umbral_estabilidad_media": MIN_STABILITY_MEAN,
        "umbral_estabilidad_p05": MIN_STABILITY_P05,
        "umbral_estabilidad_ancla_ari": MIN_ANCHOR_ARI,
        "segmentacion_aceptada": accepted,
        "motivos_no_aceptacion": reasons,
        "k_elegido": k,
        "seed": CLUSTER_SEED,
        "lgbm_params": LGBM_PARAMS,
        "nota": "Los segmentos sólo se publican si superan todas las validaciones.",
    }
    if not accepted:
        _clear_cluster_profile_tables()
        _clear_transition_tables()
        empty = pl.DataFrame(
            schema={
                "cohort_member_id": pl.String,
                "numero_de_cliente": pl.Int64,
                "foto_mes_ancla": pl.Int64,
                "horizonte_evento": pl.Int64,
                "mes_evento_esperado": pl.Int64,
                "clase_ancla": pl.String,
                "cluster": pl.Int64,
            }
        )
        empty.write_csv(TABLES_DIR / "cluster_asignaciones_baja.csv")
        (TABLES_DIR / "cluster_metadata.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return {
            "feats": feats,
            "labels": np.array([], dtype=np.int32),
            "shap_baja": shap_baja,
            "assign": empty,
            "eval_df": eval_df,
            "imp_df": imp_df,
            "k": 0,
            "accepted": False,
            "metrics": meta,
        }

    kmeans = KMeans(n_clusters=k, random_state=CLUSTER_SEED, n_init=10)
    labels = kmeans.fit_predict(shap_baja)
    cluster_profiles = []
    for c in range(k):
        mask = labels == c
        prof = np.mean(shap_baja[mask], axis=0)
        cluster_profiles.append(
            pl.DataFrame({"cluster": c, "feature": feats, "mean_shap": prof})
        )
    pl.concat(cluster_profiles).write_csv(TABLES_DIR / "cluster_perfiles_shap.csv")

    assign = baja_snap.select(
        "cohort_member_id",
        "numero_de_cliente",
        "foto_mes_ancla",
        "horizonte_evento",
        "mes_evento_esperado",
        "clase_ancla",
    ).with_columns(pl.Series("cluster", labels))
    assign.write_csv(TABLES_DIR / "cluster_asignaciones_baja.csv")
    _write_executive_tables(
        panel, snap, assign, feats, shap_baja, labels, top_global_features
    )
    (TABLES_DIR / "cluster_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    return {
        "clf": clf,
        "kmeans": kmeans,
        "feats": feats,
        "labels": labels,
        "shap_baja": shap_baja,
        "assign": assign,
        "eval_df": eval_df,
        "imp_df": imp_df,
        "k": k,
        "accepted": True,
        "metrics": meta,
    }

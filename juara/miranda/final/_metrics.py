"""Métricas multimensuales comparables para la cohorte BAJA/CONTINUA."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

from _columns import NOCONTINUAS_ANCLA, columns_by_bucket, numeric_features
from _config import BOOTSTRAP_N, BOOTSTRAP_SEED
from _paths import TABLES_DIR

_COHORT_COLUMNS = frozenset(
    {
        "cohort_member_id",
        "numero_de_cliente",
        "foto_mes",
        "clase_ternaria",
        "grupo",
        "foto_mes_ancla",
        "clase_ancla",
        "horizonte_evento",
        "horizonte_meses",
        "mes_evento_esperado",
        "es_control_replicado",
        "mes_relativo",
    }
)
_MIN_OBSERVACIONES = 10
_MAX_OBSERVACIONES_BOOTSTRAP = 2_000
_MIN_ANCLAS_PERSISTENCIA = 3
_PROPORCION_PERSISTENCIA = 0.75


@dataclass(frozen=True)
class TemporalMetrics:
    """Tablas analíticas que sustentan la lectura temporal del pipeline."""

    composicion_cohorte: pl.DataFrame
    resumen_cohorte: pl.DataFrame
    cobertura: pl.DataFrame
    contrastes_estratificados: pl.DataFrame
    contrastes_agregados: pl.DataFrame
    trayectorias_alineadas: pl.DataFrame
    trayectorias_calendario: pl.DataFrame
    denominadores_metricas: pl.DataFrame
    persistencia: pl.DataFrame
    dominios: pl.DataFrame


def anchor_snapshot(panel: pl.DataFrame) -> pl.DataFrame:
    return panel.filter(pl.col("foto_mes") == pl.col("foto_mes_ancla"))


def metric_features(panel: pl.DataFrame) -> list[str]:
    """Devuelve variables numéricas observables, excluyendo metadatos de cohorte."""

    return [column for column in numeric_features(panel) if column not in _COHORT_COLUMNS]


def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    va, vb = np.var(a, ddof=1), np.var(b, ddof=1)
    pooled = np.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2))
    if pooled == 0:
        return 0.0
    return float((np.mean(a) - np.mean(b)) / pooled)


def _bootstrap_sample(values: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Limita el remuestreo a una submuestra determinista para acotar su coste."""

    if len(values) <= _MAX_OBSERVACIONES_BOOTSTRAP:
        return values
    return values[rng.choice(len(values), size=_MAX_OBSERVACIONES_BOOTSTRAP, replace=False)]


def _bootstrap_draws(a: np.ndarray, b: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Obtiene réplicas bootstrap de la diferencia de medias BAJA−CONTINUA."""

    if len(a) == 0 or len(b) == 0:
        return np.full(BOOTSTRAP_N, np.nan)
    sampled_a = _bootstrap_sample(a, rng)
    sampled_b = _bootstrap_sample(b, rng)
    index_a = rng.integers(0, len(sampled_a), size=(BOOTSTRAP_N, len(sampled_a)))
    index_b = rng.integers(0, len(sampled_b), size=(BOOTSTRAP_N, len(sampled_b)))
    return sampled_a[index_a].mean(axis=1) - sampled_b[index_b].mean(axis=1)


def bootstrap_diff(
    a: np.ndarray, b: np.ndarray, rng: np.random.Generator
) -> tuple[float, float, float]:
    """Compatibilidad: devuelve media e intervalo de las réplicas bootstrap."""

    draws = _bootstrap_draws(a, b, rng)
    return (
        float(np.nanmean(draws)),
        float(np.nanquantile(draws, 0.025)),
        float(np.nanquantile(draws, 0.975)),
    )


def _numeric_values(frame: pl.DataFrame, column: str) -> np.ndarray:
    values = frame[column].drop_nulls().to_numpy().astype(float, copy=False)
    return values[np.isfinite(values)]


def _effect(
    baja_values: np.ndarray, continua_values: np.ndarray, rng: np.random.Generator
) -> tuple[dict[str, float | int | bool], np.ndarray]:
    """Calcula un contraste y conserva réplicas para la agregación ponderada."""

    draws = _bootstrap_draws(baja_values, continua_values, rng)
    lo, hi = float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))
    return (
        {
            "n_baja_no_nulo": len(baja_values),
            "n_continua_no_nulo": len(continua_values),
            "media_baja": float(np.mean(baja_values)),
            "media_continua": float(np.mean(continua_values)),
            "diff_baja_menos_continua": float(np.mean(baja_values) - np.mean(continua_values)),
            "cohens_d": _cohens_d(baja_values, continua_values),
            "bootstrap_mean_diff": float(np.mean(draws)),
            "ic95_lo": lo,
            "ic95_hi": hi,
            "intervalo_excluye_cero": bool(lo > 0 or hi < 0),
        },
        draws,
    )


def _cohort_composition(panel: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    snap = anchor_snapshot(panel)
    composition = (
        snap.group_by(
            "grupo",
            "foto_mes_ancla",
            "horizonte_evento",
            "mes_evento_esperado",
            "clase_ancla",
        )
        .agg(
            pl.len().alias("n_miembros"),
            pl.col("numero_de_cliente").n_unique().alias("n_clientes_unicos"),
            pl.col("es_control_replicado").sum().alias("n_controles_replicados"),
        )
        .sort(["foto_mes_ancla", "horizonte_evento", "grupo"])
    )
    bajas = composition.filter(pl.col("grupo") == "BAJA").select(
        "foto_mes_ancla", "horizonte_evento", pl.col("n_miembros").alias("n_baja")
    )
    controles = composition.filter(pl.col("grupo") == "CONTINUA").select(
        "foto_mes_ancla", "horizonte_evento", pl.col("n_miembros").alias("n_continua")
    )
    by_stratum = (
        bajas.join(controles, on=["foto_mes_ancla", "horizonte_evento"], how="full", coalesce=True)
        .fill_null(0)
        .with_columns(
            (pl.col("n_baja") + pl.col("n_continua")).alias("n_total_cohorte"),
            (pl.col("n_baja") / (pl.col("n_baja") + pl.col("n_continua"))).alias(
                "tasa_baja_cohorte"
            ),
            (pl.col("n_continua") / pl.col("n_baja")).alias("ratio_controles_por_baja"),
        )
        .sort(["foto_mes_ancla", "horizonte_evento"])
    )
    monthly = (
        by_stratum.group_by("foto_mes_ancla")
        .agg(
            pl.col("n_baja").sum().alias("n_baja"),
            pl.col("n_continua").sum().alias("n_continua"),
            pl.col("n_total_cohorte").sum().alias("n_total_cohorte"),
            pl.col("ratio_controles_por_baja").mean().alias("ratio_controles_por_baja_medio"),
            pl.col("horizonte_evento").n_unique().alias("n_horizontes"),
        )
        .with_columns(
            (pl.col("n_baja") / pl.col("n_total_cohorte")).alias("tasa_baja_cohorte")
        )
        .sort("foto_mes_ancla")
    )
    return composition, by_stratum, monthly


def _coverage(panel: pl.DataFrame) -> pl.DataFrame:
    cohort_sizes = (
        anchor_snapshot(panel)
        .group_by("grupo", "foto_mes_ancla", "horizonte_evento")
        .agg(pl.len().alias("denominador_cohorte"))
    )
    tables: list[pl.DataFrame] = []
    for axis in ("mes_relativo", "foto_mes"):
        tables.append(
            panel.group_by("grupo", "foto_mes_ancla", "horizonte_evento", axis)
            .agg(pl.col("cohort_member_id").n_unique().alias("n_miembros_observados"))
            .join(cohort_sizes, on=["grupo", "foto_mes_ancla", "horizonte_evento"], how="left")
            .with_columns(
                pl.lit(axis).alias("eje_temporal"),
                (pl.col("n_miembros_observados") / pl.col("denominador_cohorte")).alias(
                    "cobertura_cohorte"
                ),
            )
        )
    return pl.concat(tables, how="diagonal_relaxed").sort(
        ["eje_temporal", "foto_mes_ancla", "horizonte_evento", "grupo", "mes_relativo", "foto_mes"],
        nulls_last=True,
    )


def _trajectories(
    panel: pl.DataFrame, variables: list[str]
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    pre_event = panel.filter(pl.col("mes_relativo") < 0)
    aggregate = [pl.col(variable).mean().alias(f"media_{variable}") for variable in variables]
    aligned = (
        pre_event.group_by("grupo", "foto_mes_ancla", "horizonte_evento", "mes_relativo")
        .agg(pl.col("cohort_member_id").n_unique().alias("n_miembros_observados"), *aggregate)
        .sort(["foto_mes_ancla", "horizonte_evento", "grupo", "mes_relativo"])
    )
    calendar = (
        pre_event.group_by("grupo", "foto_mes_ancla", "horizonte_evento", "foto_mes")
        .agg(pl.col("cohort_member_id").n_unique().alias("n_miembros_observados"), *aggregate)
        .sort(["foto_mes_ancla", "horizonte_evento", "grupo", "foto_mes"])
    )
    denominator_tables: list[pl.DataFrame] = []
    for axis in ("mes_relativo", "foto_mes"):
        for variable in variables:
            denominator_tables.append(
                pre_event.group_by("grupo", "foto_mes_ancla", "horizonte_evento", axis)
                .agg(pl.col(variable).count().alias("n_observaciones_no_nulas"))
                .with_columns(pl.lit(axis).alias("eje_temporal"), pl.lit(variable).alias("variable"))
            )
    denominators = pl.concat(denominator_tables, how="diagonal_relaxed").sort(
        ["eje_temporal", "variable", "foto_mes_ancla", "horizonte_evento", "grupo"],
        nulls_last=True,
    )
    return aligned, calendar, denominators


def _stratified_contrasts(
    panel: pl.DataFrame, variables: list[str]
) -> tuple[pl.DataFrame, dict[str, list[tuple[dict, np.ndarray]]]]:
    snap = anchor_snapshot(panel)
    rows: list[dict] = []
    details: dict[str, list[tuple[dict, np.ndarray]]] = {variable: [] for variable in variables}
    strata = (
        snap.select("foto_mes_ancla", "horizonte_evento", "mes_evento_esperado")
        .unique()
        .sort(["foto_mes_ancla", "horizonte_evento"])
    )
    for stratum_index, stratum in enumerate(strata.iter_rows(named=True)):
        baja = snap.filter(
            (pl.col("grupo") == "BAJA")
            & (pl.col("foto_mes_ancla") == stratum["foto_mes_ancla"])
            & (pl.col("horizonte_evento") == stratum["horizonte_evento"])
        )
        continua = snap.filter(
            (pl.col("grupo") == "CONTINUA")
            & (pl.col("foto_mes_ancla") == stratum["foto_mes_ancla"])
            & (pl.col("horizonte_evento") == stratum["horizonte_evento"])
        )
        for variable_index, variable in enumerate(variables):
            baja_values = _numeric_values(baja, variable)
            continua_values = _numeric_values(continua, variable)
            if min(len(baja_values), len(continua_values)) < _MIN_OBSERVACIONES:
                continue
            rng = np.random.default_rng(
                np.random.SeedSequence([BOOTSTRAP_SEED, stratum_index, variable_index])
            )
            effect, draws = _effect(baja_values, continua_values, rng)
            row = {
                "variable": variable,
                "foto_mes_ancla": stratum["foto_mes_ancla"],
                "horizonte_evento": stratum["horizonte_evento"],
                "mes_evento_esperado": stratum["mes_evento_esperado"],
                "criterio_inclusion": f">={_MIN_OBSERVACIONES} observaciones no nulas por grupo",
                "n_baja_cohorte": baja.height,
                "n_continua_cohorte": continua.height,
                **effect,
            }
            rows.append(row)
            details[variable].append((row, draws))
    return pl.DataFrame(rows), details


def _aggregate_contrasts(
    contrast_details: dict[str, list[tuple[dict, np.ndarray]]]
) -> pl.DataFrame:
    rows: list[dict] = []
    for variable, details in contrast_details.items():
        if not details:
            continue
        weights = np.asarray([item[0]["n_baja_no_nulo"] for item in details], dtype=float)
        weights /= weights.sum()
        effects = [item[0] for item in details]
        weighted_draws = weights @ np.vstack([item[1] for item in details])
        lo, hi = float(np.quantile(weighted_draws, 0.025)), float(
            np.quantile(weighted_draws, 0.975)
        )
        rows.append(
            {
                "variable": variable,
                "n_estratos_ponderados": len(details),
                "n_baja_no_nulo": int(sum(item["n_baja_no_nulo"] for item in effects)),
                "n_continua_no_nulo": int(sum(item["n_continua_no_nulo"] for item in effects)),
                "media_baja_ponderada": float(
                    np.average([item["media_baja"] for item in effects], weights=weights)
                ),
                "media_continua_ponderada": float(
                    np.average([item["media_continua"] for item in effects], weights=weights)
                ),
                "diff_baja_menos_continua": float(
                    np.average([item["diff_baja_menos_continua"] for item in effects], weights=weights)
                ),
                "cohens_d_ponderado": float(
                    np.average([item["cohens_d"] for item in effects], weights=weights)
                ),
                "cohens_d": float(
                    np.average([item["cohens_d"] for item in effects], weights=weights)
                ),
                "bootstrap_mean_diff": float(np.mean(weighted_draws)),
                "ic95_lo": lo,
                "ic95_hi": hi,
                "intervalo_excluye_cero": bool(lo > 0 or hi < 0),
                "ponderacion": "peso proporcional a n_baja_no_nulo por estrato",
                "bootstrap_replicas": BOOTSTRAP_N,
                "max_observaciones_por_grupo_bootstrap": _MAX_OBSERVACIONES_BOOTSTRAP,
            }
        )
    return pl.DataFrame(rows).sort("cohens_d_ponderado", descending=True, nulls_last=True)


def _persistence(contrasts: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    rows: list[dict] = []
    if not contrasts.is_empty():
        for (variable,), sub in contrasts.group_by("variable", maintain_order=True):
            positive = sub.filter(
                (pl.col("intervalo_excluye_cero"))
                & (pl.col("diff_baja_menos_continua") > 0)
            )["foto_mes_ancla"].n_unique()
            negative = sub.filter(
                (pl.col("intervalo_excluye_cero"))
                & (pl.col("diff_baja_menos_continua") < 0)
            )["foto_mes_ancla"].n_unique()
            n_anchors = sub["foto_mes_ancla"].n_unique()
            required = max(
                _MIN_ANCLAS_PERSISTENCIA,
                int(np.ceil(n_anchors * _PROPORCION_PERSISTENCIA)),
            )
            dominant = max(positive, negative)
            if n_anchors < _MIN_ANCLAS_PERSISTENCIA:
                classification = "sin_estabilidad_suficiente"
            elif dominant >= required:
                classification = "persistente"
            elif positive + negative == 1:
                classification = "exclusiva_de_un_ancla"
            else:
                classification = "sin_estabilidad_suficiente"
            rows.append(
                {
                    "variable": variable,
                    "n_estratos_evaluados": sub.height,
                    "n_anclas_evaluadas": n_anchors,
                    "n_efectos_positivos_ic_excluye_cero": positive,
                    "n_efectos_negativos_ic_excluye_cero": negative,
                    "direccion_dominante": "positiva" if positive >= negative else "negativa",
                    "umbral_anclas_persistencia": required,
                    "clasificacion_persistencia": classification,
                }
            )
    criteria = pl.DataFrame(
        {
            "criterio": [
                "elegibilidad_contraste",
                "persistente",
                "exclusiva_de_un_ancla",
                "sin_estabilidad_suficiente",
                "bootstrap",
            ],
            "regla": [
                f">={_MIN_OBSERVACIONES} observaciones no nulas por grupo y estrato",
                (
                    f">={_MIN_ANCLAS_PERSISTENCIA} anclas y dirección con IC95 fuera de cero "
                    f"en al menos {int(_PROPORCION_PERSISTENCIA * 100)}% de las anclas"
                ),
                "exactamente un efecto por ancla con IC95 fuera de cero",
                "no cumple los criterios anteriores o no cubre tres anclas",
                (
                    f"{BOOTSTRAP_N} réplicas, semilla {BOOTSTRAP_SEED}; "
                    f"máximo {_MAX_OBSERVACIONES_BOOTSTRAP} observaciones por grupo y estrato"
                ),
            ],
        }
    )
    return pl.DataFrame(rows), criteria


def calcular_metricas_temporales(
    panel: pl.DataFrame, variables: list[str] | None = None
) -> TemporalMetrics:
    """Materializa tamaños, coberturas, contrastes y trayectorias multimensuales."""

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    variables = variables or metric_features(panel)
    composition, summary, monthly_summary = _cohort_composition(panel)
    coverage = _coverage(panel)
    trajectories_aligned, trajectories_calendar, metric_denominators = _trajectories(panel, variables)
    stratified, detail = _stratified_contrasts(panel, variables)
    aggregated = _aggregate_contrasts(detail)
    persistence, criteria = _persistence(stratified)
    domains = dominio_matrix(aggregated, variables, write=False)

    composition.write_csv(TABLES_DIR / "cohorte_ancla_horizonte.csv")
    monthly_summary.write_csv(TABLES_DIR / "cohorte_resumen_mensual.csv")
    coverage.write_csv(TABLES_DIR / "cobertura_denominadores.csv")
    trajectories_aligned.write_csv(TABLES_DIR / "trayectorias_alineadas_evento.csv")
    trajectories_calendar.write_csv(TABLES_DIR / "trayectorias_nivel_calendario.csv")
    metric_denominators.write_csv(TABLES_DIR / "denominadores_metricas.csv")
    stratified.write_csv(TABLES_DIR / "contrastes_estratificados_ancla_horizonte.csv")
    aggregated.write_csv(TABLES_DIR / "contrastes_agregados_ponderados.csv")
    persistence.write_csv(TABLES_DIR / "persistencia_senales.csv")
    criteria.write_csv(TABLES_DIR / "criterios_persistencia.csv")
    domains.write_csv(TABLES_DIR / "matriz_dominios_efecto.csv")

    # Nombres previos preservados para consumidores aún no migrados.
    aggregated.write_csv(TABLES_DIR / "contrastes_ancla_baja_vs_continua.csv")
    stratified.write_csv(TABLES_DIR / "contrastes_baja12_vs_continua.csv")
    trajectories_aligned.write_csv(TABLES_DIR / "trayectorias_agregadas.csv")
    return TemporalMetrics(
        composition,
        summary,
        coverage,
        stratified,
        aggregated,
        trajectories_aligned,
        trajectories_calendar,
        metric_denominators,
        persistence,
        domains,
    )


def contrastes_ancla(panel: pl.DataFrame) -> pl.DataFrame:
    """Compatibilidad: devuelve el contraste multimensual ponderado."""

    return calcular_metricas_temporales(panel).contrastes_agregados


def contrastes_subgrupos(panel: pl.DataFrame) -> pl.DataFrame:
    """Compatibilidad: devuelve contrastes explícitamente estratificados."""

    return calcular_metricas_temporales(panel).contrastes_estratificados


def prevalencia_flags(snap: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict] = []
    for col in NOCONTINUAS_ANCLA:
        if col not in snap.columns:
            continue
        for grupo in ("BAJA", "CONTINUA"):
            sub = snap.filter(pl.col("grupo") == grupo)
            vals = sub[col].drop_nulls()
            if vals.len() == 0:
                continue
            prev = float((vals > 0).mean()) if vals.dtype in (pl.Float64, pl.Int64, pl.UInt32) else float(
                vals.cast(pl.Boolean).mean()
            )
            rows.append(
                {
                    "variable": col,
                    "grupo": grupo,
                    "prevalencia": prev,
                    "n_observaciones_no_nulas": vals.len(),
                }
            )
    out = pl.DataFrame(rows)
    out.write_csv(TABLES_DIR / "prevalencia_flags_ancla.csv")
    return out


def trayectorias_agregadas(panel: pl.DataFrame, variables: list[str]) -> pl.DataFrame:
    """Compatibilidad: devuelve trayectorias alineadas separadas por estrato."""

    return calcular_metricas_temporales(panel, variables).trayectorias_alineadas


def dominio_matrix(
    contrastes: pl.DataFrame, columns: list[str], *, write: bool = True
) -> pl.DataFrame:
    buckets = columns_by_bucket(columns)
    rows: list[dict] = []
    for bucket, cols in buckets.items():
        sub = contrastes.filter(pl.col("variable").is_in(cols))
        if sub.is_empty():
            continue
        effect_column = "cohens_d_ponderado" if "cohens_d_ponderado" in sub.columns else "cohens_d"
        rows.append(
            {
                "dominio": bucket,
                "n_vars": len(cols),
                "mean_abs_cohens_d": float(sub[effect_column].abs().mean()),
                "max_abs_cohens_d": float(sub[effect_column].abs().max()),
            }
        )
    out = pl.DataFrame(rows).sort("mean_abs_cohens_d", descending=True)
    if write:
        out.write_csv(TABLES_DIR / "matriz_dominios_efecto.csv")
    return out

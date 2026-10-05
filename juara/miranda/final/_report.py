"""Informe empresarial trazable a las tablas del pipeline."""

from __future__ import annotations

import math

import polars as pl

from _config import ALL_FOTO_MESES, ANCHOR_MONTHS, BOOTSTRAP_N, CONTROL_RATIO, SAMPLE_SEED
from _paths import RESULTS_DIR, TABLES_DIR

DESTACADOS_POR_ETAPA: dict[int, list[str]] = {
    1: [
        "plots/etapa_01/02_cobertura_longitudinal.png",
        "plots/etapa_01/06_composicion_baja12.png",
        "plots/etapa_01/08_comparabilidad_tamanos.png",
    ],
    2: [
        "plots/etapa_02/01_ranking_brechas_efecto.png",
        "plots/etapa_02/04_matriz_dominios_heatmap.png",
        "plots/etapa_02/07_bootstrap_ic_top.png",
    ],
    3: [
        "plots/etapa_03/01_trayectoria_mrentabilidad.png",
        "plots/etapa_03/07_brecha_rentabilidad.png",
        "plots/etapa_03/08_trayectoria_por_horizonte.png",
    ],
    4: [
        "plots/etapa_04/01_silueta_vs_k.png",
        "plots/etapa_04/08_auc_clasificador.png",
        "plots/etapa_04/10_metricas_cluster_elegido.png",
    ],
}

PROFILE_LABELS = {
    "cliente_edad": "Edad (años)",
    "cliente_antiguedad": "Antigüedad (meses)",
    "ctrx_quarter": "Transacciones trimestrales",
    "ctarjeta_visa_transacciones": "Transacciones Visa",
    "ctarjeta_master_transacciones": "Transacciones Master",
    "mpayroll": "Payroll",
    "tcuentas": "Cantidad de cuentas",
    "mcuentas_saldo": "Saldo de cuentas",
    "mprestamos_personales": "Préstamos personales",
    "mprestamos_prendarios": "Préstamos prendarios",
    "Visa_msaldototal": "Saldo Visa",
    "Master_msaldototal": "Saldo Master",
}

PROFILE_VARIABLES = list(PROFILE_LABELS)

OPERATIVE_FINANCE_LABELS = {
    "deuda_total_operativa": "Deuda total operativa",
    "patrimonio_liquido_operativo": "Patrimonio líquido operativo",
}

HISTORICAL_VARIABLE_LABELS = {
    **PROFILE_LABELS,
    **OPERATIVE_FINANCE_LABELS,
    "active_quarter": "Actividad trimestral",
    "cliente_vip": "Cliente VIP",
    "cdescubierto_preacordado": "Descubierto preacordado",
    "cseguro_vida": "Seguro de vida",
    "cseguro_auto": "Seguro automotor",
}

HISTORICAL_DOMAIN_LABELS = {
    "perfil_cliente": "Perfil del cliente",
    "rentabilidad": "Rentabilidad",
    "saldos": "Saldos",
    "financiero": "Financiero",
    "productos": "Productos",
    "canales": "Canales y transacciones",
    "otros_indicadores": "Otros indicadores del clasificador",
    "finanzas_operativas": "Finanzas operativas",
}


def _read_table(name: str) -> pl.DataFrame:
    """Lee una tabla materializada; falla si el contrato del pipeline no se cumplió."""

    path = TABLES_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Falta la tabla requerida para el informe: {path}")
    return pl.read_csv(path)


def _fmt(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "sí" if value else "no"
    if isinstance(value, float):
        if not math.isfinite(value):
            return "—"
        if abs(value) >= 1_000:
            return f"{value:,.0f}".replace(",", ".")
        if abs(value) >= 10:
            return f"{value:.1f}"
        return f"{value:.3f}"
    return str(value)


def _markdown_table(frame: pl.DataFrame, columns: list[str], limit: int = 8) -> str:
    present = [column for column in columns if column in frame.columns]
    if not present or frame.is_empty():
        return "_Sin filas disponibles._"
    table = frame.select(present).head(limit)
    lines = [
        "| " + " | ".join(present) + " |",
        "| " + " | ".join("---" for _ in present) + " |",
    ]
    for row in table.iter_rows():
        lines.append("| " + " | ".join(_fmt(value) for value in row) + " |")
    return "\n".join(lines)


def _number(frame: pl.DataFrame, column: str) -> int:
    return int(frame[column].sum()) if column in frame.columns and frame.height else 0


def _cluster_section(meta: dict) -> str:
    temporal_auc = meta.get("auc_temporal_media")
    temporal_min = meta.get("auc_temporal_min")
    accepted = bool(meta.get("segmentacion_aceptada"))
    status = (
        "aceptada para descripción exploratoria"
        if accepted
        else "no aceptada; no hay perfiles de clientes defendibles"
    )
    lines = [
        "## Perfiles cuantitativos y prioridades sugeridas\n",
        f"- Estado: **{status}**.",
        f"- AUC temporal media/mínima: **{_fmt(temporal_auc)} / {_fmt(temporal_min)}**.",
        f"- Predictores permitidos al ancla: **{_fmt(meta.get('n_features'))}**.",
    ]
    if not accepted:
        reasons = meta.get("motivos_no_aceptacion", [])
        detail = "; ".join(str(reason) for reason in reasons) or (
            "La validación no produjo un corte aceptable."
        )
        lines.extend(
            [
                f"- Motivo: {detail}",
                "- Decisión sugerida: no asignar prioridades ni tratamientos por segmento; "
                "usar la evidencia agregada y revalidar antes de operacionalizar una segmentación.",
                "- Gráficos de validación: "
                "`plots/etapa_04/01_silueta_vs_k.png`, "
                "`plots/etapa_04/08_auc_clasificador.png` y "
                "`plots/etapa_04/10_metricas_cluster_elegido.png`.",
            ]
        )
        return "\n".join(lines) + "\n"

    summary = _read_table("cluster_fichas_resumen.csv")
    anchors = _read_table("cluster_fichas_anclas.csv")
    traits = _read_table("cluster_fichas_rasgos.csv")
    domains = _read_table("cluster_fichas_dominios.csv")
    operative_finances = _read_table("cluster_fichas_finanzas_operativas.csv")
    trajectories = _read_table("cluster_fichas_trayectoria.csv")
    top10_global = _read_table("cluster_top10_global_shap_media_mediana.csv")
    demographics = _read_table("cluster_edad_antiguedad_descriptivos.csv")
    cluster_columns = ["cluster", "n", "peso", "BAJA+1", "BAJA+2"]
    key_levels = domains.filter(
        pl.col("variable").is_in(["mrentabilidad", "mcuentas_saldo", "cproductos", "ctrx_quarter"])
    ).sort("cluster", "variable")
    profitability_path = (
        trajectories.filter(pl.col("variable") == "mrentabilidad")
        .group_by("cluster")
        .agg(
            pl.col("mes_relativo").min().alias("mes_relativo_min"),
            pl.col("mes_relativo").max().alias("mes_relativo_max"),
            pl.col("brecha_vs_continua").mean().alias("brecha_media_vs_continua"),
        )
        .sort("cluster")
    )
    lines.extend(
        [
            "",
            "Tamaño y composición de los segmentos aceptados:",
            _markdown_table(summary, cluster_columns),
            "",
            "Distribución por ancla y evento esperado:",
            _markdown_table(
                anchors,
                ["cluster", "foto_mes_ancla", "mes_evento_esperado", "n", "peso_cluster"],
            ),
            "",
            "Rasgos distintivos del modelo (no son causas):",
            _markdown_table(traits, ["cluster", "rango", "variable", "direccion_vs_continua", "mean_shap"]),
            "",
            "Media y mediana al ancla de las diez variables con mayor importancia global "
            "SHAP (misma selección para todos los segmentos):",
            _markdown_table(
                top10_global,
                [
                    "cluster",
                    "rango_importancia_global",
                    "variable",
                    "n",
                    "media_ancla",
                    "mediana_ancla",
                    "n_continua_emparejada",
                    "media_continua_emparejada",
                    "brecha_vs_continua",
                ],
                limit=20,
            ),
            "",
            "Descriptivos de edad y antigüedad al ancla:",
            _markdown_table(
                demographics,
                [
                    "cluster",
                    "variable",
                    "n",
                    "media",
                    "mediana",
                    "p10",
                    "p25",
                    "p75",
                    "p90",
                    "minimo",
                    "maximo",
                ],
            ),
            "",
            "Las distribuciones completas por intervalos comparables están en "
            "`tablas/cluster_edad_antiguedad_distribucion.csv`.",
            "",
            "Niveles y brechas por dominio frente a CONTINUA emparejada:",
            _markdown_table(
                key_levels,
                [
                    "cluster",
                    "dominio",
                    "variable",
                    "media_segmento",
                    "media_continua_emparejada",
                    "brecha_vs_continua",
                ],
            ),
            "",
            "Proxy financiero operativo al ancla por segmento frente a CONTINUA emparejada:",
            _markdown_table(
                operative_finances,
                [
                    "cluster",
                    "variable",
                    "n_segmento",
                    "media_segmento",
                    "mediana_segmento",
                    "n_continua_emparejada",
                    "media_continua_emparejada",
                    "mediana_continua_emparejada",
                    "brecha_media_vs_continua",
                    "brecha_mediana_vs_continua",
                ],
            ),
            "",
            "`deuda_total_operativa` suma préstamos personales, prendarios e hipotecarios "
            "y los saldos Visa/Master truncados inferiormente en cero; "
            "`patrimonio_liquido_operativo` es `mcuentas_saldo − deuda_total_operativa` "
            "con nulos tratados como cero.",
            "Ambas medidas son proxies operativos, no patrimonio neto contable. Se excluyen "
            "`mactivos_margen` y `mpasivos_margen` porque representan márgenes, no saldos.",
            "",
            "Evolución pre-evento de rentabilidad por segmento (promedio de brecha "
            "BAJA−CONTINUA en las fotos previas disponibles):",
            _markdown_table(
                profitability_path,
                [
                    "cluster",
                    "mes_relativo_min",
                    "mes_relativo_max",
                    "brecha_media_vs_continua",
                ],
            ),
            "",
        ]
    )
    for row in summary.sort("n", descending=True).iter_rows(named=True):
        cluster = row["cluster"]
        weight = _fmt(row.get("peso"))
        top_traits = traits.filter(pl.col("cluster") == cluster).sort("rango")["variable"].to_list()
        lines.append(
            f"- Prioridad exploratoria C{cluster}: {row['n']} episodios ({weight} de BAJA); "
            f"medir en una prueba controlada intervenciones de contacto u oferta alrededor de "
            f"`{', '.join(top_traits)}`. El tamaño prioriza capacidad de prueba, no riesgo causal."
        )
    return "\n".join(lines) + "\n"


def _temporal_transition_section(meta: dict) -> str:
    """Resume cambios pre-evento sin convertirlos en evidencia causal."""

    if not bool(meta.get("segmentacion_aceptada")):
        return (
            "## Estados y transiciones pre-evento\n\n"
            "No se publican transiciones porque la segmentación no fue aceptada.\n"
        )

    coverage = _read_table("cluster_transiciones_cobertura.csv")
    aggregate = _read_table("cluster_transiciones_matriz_agregada.csv")
    summary = _read_table("cluster_transiciones_resumen_agregado.csv")
    if summary.is_empty():
        return "## Estados y transiciones pre-evento\n\n_Sin resumen disponible._\n"
    row = summary.row(0, named=True)
    lines = [
        "## Estados y transiciones pre-evento\n",
        "Los estados se puntuaron en cada foto BAJA previa al evento con el mismo "
        "LightGBM y el mismo KMeans ajustados al ancla. La asignación de cada ancla "
        "reproduce `cluster_asignaciones_baja.csv` antes de publicar transiciones.",
        f"- Umbral publicado: **{_fmt(row['min_pares_por_estrato'])} pares consecutivos** "
        "por `(foto_mes_ancla, horizonte_evento)`.",
        f"- Estratos publicables: **{_fmt(row['n_estratos_publicables'])}** de "
        f"**{_fmt(row['n_estratos_total'])}**; pares incluidos: "
        f"**{_fmt(row['n_pares_publicados'])}**.",
        f"- Permanencia entre pares: **{_fmt(row['tasa_permanencia_pares'])}** "
        f"({_fmt(row['n_pares_permanencia'])} pares); migración: "
        f"**{_fmt(row['tasa_migracion_pares'])}** "
        f"({_fmt(row['n_pares_migracion'])} pares).",
        f"- Episodios con trayecto completo hasta `-1`: "
        f"**{_fmt(row['n_episodios_comparables'])}**; cambio entre el primer estado "
        f"observable y `-1`: **{_fmt(row['tasa_cambio_extremos'])}**.",
        "",
        "Matriz agregada, ponderada por pares observados de los estratos publicables:",
        _markdown_table(
            aggregate,
            [
                "estado_origen",
                "estado_destino",
                "n_pares",
                "n_pares_origen",
                "n_estratos_contributivos",
                "probabilidad",
            ],
            limit=max(aggregate.height, 1),
        ),
        "",
        "Cobertura por estrato, incluidos los no publicables:",
        _markdown_table(
            coverage,
            [
                "foto_mes_ancla",
                "horizonte_evento",
                "n_episodios",
                "n_fotos_pre_evento",
                "n_pares_observados",
                "publicable",
                "motivo_no_publicable",
            ],
            limit=max(coverage.height, 1),
        ),
        "",
        "La migración observada describe cambios de asignación SHAP en pares calendario "
        "consecutivos; no demuestra migración estructural, causalidad ni efecto de una "
        "intervención. Los estratos de soporte insuficiente permanecen desglosados y "
        "no se mezclan en la matriz agregada.",
    ]
    return "\n".join(lines) + "\n"


def _profile_metric_sentence(row: dict[str, object], label: str) -> str:
    return (
        f"{label}: BAJA **{_fmt(row.get('media_segmento'))}**, CONTINUA emparejada "
        f"**{_fmt(row.get('media_continua_emparejada'))}**, brecha BAJA−CONTINUA "
        f"**{_fmt(row.get('brecha_vs_continua'))}**."
    )


def _operational_finance_table(rows: pl.DataFrame) -> str:
    """Presenta los proxies financieros con niveles y brechas trazables."""

    display_rows = [
        {
            "métrica": OPERATIVE_FINANCE_LABELS.get(
                str(row["variable"]), str(row["variable"])
            ),
            "n BAJA": row["n_segmento"],
            "BAJA media": row["media_segmento"],
            "BAJA mediana": row["mediana_segmento"],
            "n CONTINUA emparejada": row["n_continua_emparejada"],
            "CONTINUA media": row["media_continua_emparejada"],
            "CONTINUA mediana": row["mediana_continua_emparejada"],
            "brecha media BAJA−CONTINUA": row["brecha_media_vs_continua"],
            "brecha mediana BAJA−CONTINUA": row["brecha_mediana_vs_continua"],
        }
        for row in rows.iter_rows(named=True)
    ]
    return _markdown_table(
        pl.DataFrame(display_rows),
        [
            "métrica",
            "n BAJA",
            "BAJA media",
            "BAJA mediana",
            "n CONTINUA emparejada",
            "CONTINUA media",
            "CONTINUA mediana",
            "brecha media BAJA−CONTINUA",
            "brecha mediana BAJA−CONTINUA",
        ],
        limit=len(display_rows),
    )


def _transition_profile_section(cluster_meta: dict) -> str:
    """Resume cambios de estado pre-evento sin confundirlos con causalidad."""

    if not bool(cluster_meta.get("segmentacion_aceptada")):
        return ""

    coverage = _read_table("cluster_transiciones_cobertura.csv")
    aggregate = _read_table("cluster_transiciones_matriz_agregada.csv")
    episodes = _read_table("cluster_transiciones_resumen_episodio.csv")
    states = _read_table("cluster_estados_pre_evento.csv")
    if coverage.is_empty() or aggregate.is_empty() or episodes.is_empty() or states.is_empty():
        return ""

    comparable = episodes.filter(
        pl.col("trayecto_completo_hasta_menos_1")
        & (pl.col("n_pares_consecutivos") >= 1)
    )
    endpoint_matrix = (
        comparable.group_by("estado_inicial_observable", "estado_menos_1")
        .len()
        .rename({"len": "n_episodios"})
        .with_columns(
            pl.col("n_episodios")
            .sum()
            .over("estado_inicial_observable")
            .alias("n_episodios_origen")
        )
        .with_columns(
            (pl.col("n_episodios") / pl.col("n_episodios_origen")).alias("probabilidad")
        )
        .sort("estado_inicial_observable", "estado_menos_1")
    )
    first_states = (
        states.sort("cohort_member_id", "foto_mes")
        .group_by("cohort_member_id", maintain_order=True)
        .agg(
            pl.first("mes_relativo").alias("mes_relativo_inicial"),
            pl.first("estado_temporal").alias("estado_inicial"),
        )
    )
    state_menos_2 = states.filter(pl.col("mes_relativo") == -2).select(
        "cohort_member_id", pl.col("estado_temporal").alias("estado_menos_2")
    )
    t2_comparable = (
        comparable.select(
            "cohort_member_id",
            pl.col("estado_menos_1").alias("estado_menos_1"),
        )
        .join(first_states, on="cohort_member_id", how="inner")
        .join(state_menos_2, on="cohort_member_id", how="inner")
        .filter(pl.col("mes_relativo_inicial") < -2)
    )
    if comparable.is_empty() or t2_comparable.is_empty():
        return ""

    n_endpoint = comparable.height
    n_endpoint_changed = int(comparable["cambio_entre_extremos"].sum())
    n_t2 = t2_comparable.height
    initial_to_t2 = float(
        (t2_comparable["estado_inicial"] != t2_comparable["estado_menos_2"]).mean()
    )
    initial_to_t1 = float(
        (t2_comparable["estado_inicial"] != t2_comparable["estado_menos_1"]).mean()
    )
    t2_to_t1 = float(
        (t2_comparable["estado_menos_2"] != t2_comparable["estado_menos_1"]).mean()
    )
    publicable = coverage.filter(pl.col("publicable"))
    lines = [
        "\n## Ciclo de vida de los perfiles antes de BAJA\n",
        "Cada foto previa al evento se puntuó con el mismo LightGBM y KMeans "
        "ajustados al ancla. La asignación al ancla reproduce la segmentación publicada; "
        "por ello los cambios siguientes son cambios de estado del modelo, no nuevos clústeres.",
        f"- Estratos con soporte: **{publicable.height} de {coverage.height}**; "
        f"pares calendario consecutivos incluidos: **{_fmt(int(publicable['n_pares_observados'].sum()))}**.",
        f"- Entre **{_fmt(n_endpoint)}** episodios con al menos dos fotos previas, "
        f"**{n_endpoint_changed / n_endpoint:.1%}** cambia entre el primer estado observable y `t=-1`.",
        f"- Para **{_fmt(n_t2)}** episodios con historia anterior a `t=-2`, el cambio "
        f"primer estado→`t=-2` es **{initial_to_t2:.1%}**; "
        f"primer estado→`t=-1`, **{initial_to_t1:.1%}**; y "
        f"`t=-2`→`t=-1`, **{t2_to_t1:.1%}**.",
        "",
        "Matriz entre el primer estado observable y `t=-1`:",
        _markdown_table(
            endpoint_matrix,
            [
                "estado_inicial_observable",
                "estado_menos_1",
                "n_episodios",
                "n_episodios_origen",
                "probabilidad",
            ],
        ),
        "",
        "Matriz agregada de transiciones entre meses calendario consecutivos:",
        _markdown_table(
            aggregate,
            [
                "estado_origen",
                "estado_destino",
                "n_pares",
                "n_pares_origen",
                "n_estratos_contributivos",
                "probabilidad",
            ],
        ),
        "",
        "Los estratos con soporte insuficiente no se mezclan en las matrices. Por definición "
        "de BAJA, no hay trayectoria publicable desde `t=0`: la ausencia del cliente no se "
        "interpreta como continuidad ni como saldo cero. Tampoco se demuestra causalidad, "
        "migración estructural o efecto de una intervención.",
    ]
    return "\n".join(lines) + "\n"


def _terminal_cluster_balance_lifecycle_section(cluster_meta: dict, cluster: int) -> str:
    """Explica el saldo previo de episodios cuyo último estado es un clúster."""

    if not bool(cluster_meta.get("segmentacion_aceptada")):
        return ""
    lifecycle = _read_table(f"cluster_ciclo_vida_c{cluster}_terminal.csv")
    if lifecycle.is_empty():
        return (
            f"\n## Saldo previo de los episodios que terminan en C{cluster}\n\n"
            f"_No hay episodios con estado C{cluster} en su última foto observable._\n"
        )

    comparable = lifecycle.drop_nulls(
        [
            "media_saldo_cluster_terminal",
            "media_saldo_continua_ponderada",
        ]
    ).sort("mes_relativo")
    if comparable.is_empty():
        return (
            f"\n## Saldo previo de los episodios que terminan en C{cluster}\n\n"
            "_No hay controles emparejados observables para la comparación._\n"
        )

    first = comparable.row(0, named=True)
    last = comparable.row(-1, named=True)
    always_below_reference = bool(
        (
            comparable["media_saldo_cluster_terminal"]
            < comparable["media_saldo_continua_ponderada"]
        ).all()
    )
    display = comparable.rename(
        {
            "mes_relativo": "meses antes de la desaparición",
            "n_episodios_observados": f"episodios C{cluster} observados",
            "media_saldo_cluster_terminal": f"saldo medio C{cluster} terminal",
            "mediana_saldo_cluster_terminal": f"saldo mediano C{cluster} terminal",
            "n_controles_observados": "controles observados",
            "media_saldo_continua_ponderada": "saldo medio CONTINUA ponderada",
            "brecha_media_cluster_menos_continua": f"brecha media C{cluster}−CONTINUA",
        }
    )
    relation = (
        f"En todos los meses observables, el saldo medio de C{cluster} terminal quedó por debajo "
        "de la referencia CONTINUA ponderada por los mismos estratos."
        if always_below_reference
        else "La relación con CONTINUA varía entre los meses observables."
    )
    return "\n".join(
        [
            f"\n## Saldo previo de los episodios que terminan en C{cluster}\n",
            f"Aquí «terminan en C{cluster}» significa que el mismo modelo asigna C{cluster} en `t=-1`, "
            "la última foto observable antes de que el cliente desaparezca. No equivale "
            f"necesariamente a C{cluster} al ancla: para BAJA+2 el ancla ocurre en `t=-2`.",
            "La tabla reconstruye sólo fotos previas (`t<0`) y pondera CONTINUA por "
            "`(foto_mes_ancla, horizonte_evento)` de esos episodios.",
            _markdown_table(
                display,
                [
                    "meses antes de la desaparición",
                    f"episodios C{cluster} observados",
                    f"saldo medio C{cluster} terminal",
                    f"saldo mediano C{cluster} terminal",
                    "saldo medio CONTINUA ponderada",
                    f"brecha media C{cluster}−CONTINUA",
                ],
                limit=display.height,
            ),
            (
                "En la media de las fotos disponibles, el saldo de estos episodios pasa de "
                f"**{_fmt(first['media_saldo_cluster_terminal'])}** en `t={first['mes_relativo']}` "
                f"a **{_fmt(last['media_saldo_cluster_terminal'])}** en `t={last['mes_relativo']}`. "
                f"{relation}"
            ),
            "La variación entre filas no identifica el cambio de cada cliente: el número de "
            "episodios observados cambia con el mes relativo. Por ello permite descartar o "
            "sustentar un patrón de niveles previos, no atribuir causalidad ni medir el saldo "
            "después de la baja.",
        ]
    ) + "\n"


def _terminal_cluster_historical_profile_detail_section(
    cluster_meta: dict, cluster: int
) -> str:
    """Publica el histórico pre-evento completo de los predictores de un clúster terminal."""

    if not bool(cluster_meta.get("segmentacion_aceptada")):
        return ""
    history = _read_table(f"cluster_ciclo_vida_c{cluster}_terminal_historico.csv")
    if history.is_empty():
        return ""

    relative_months = sorted(history["mes_relativo"].unique().to_list())
    level_columns = [f"t={month}" for month in relative_months]
    lines = [
        f"\n## Histórico completo de variables relevantes: C{cluster} terminal\n",
        f"Se publican las **{history['variable'].n_unique()} variables**: las 28 admitidas "
        "por el clasificador y los dos proxies financieros operativos. Cada fila se refiere "
        f"a los episodios cuyo último estado observable es C{cluster} y sólo contiene fotos "
        "anteriores a la desaparición.",
        "Los niveles son medias; las brechas restan la media CONTINUA ponderada por los mismos "
        "estratos. Los denominadores por variable y mes están en "
        f"`tablas/cluster_ciclo_vida_c{cluster}_terminal_historico.csv`.",
    ]
    for domain in history["dominio"].unique().sort().to_list():
        domain_history = history.filter(pl.col("dominio") == domain)

        def _pivot(value: str) -> pl.DataFrame:
            result = domain_history.pivot(
                on="mes_relativo",
                index="variable",
                values=value,
                aggregate_function="first",
            )
            renames = {
                str(month): f"t={month}"
                for month in relative_months
                if str(month) in result.columns
            }
            result = result.rename(renames)
            return result.with_columns(
                pl.col("variable")
                .map_elements(
                    lambda variable: HISTORICAL_VARIABLE_LABELS.get(variable, variable),
                    return_dtype=pl.String,
                )
                .alias("métrica")
            ).select(["métrica", *[column for column in level_columns if column in result.columns]])

        lines.extend(
            [
                f"\n### {HISTORICAL_DOMAIN_LABELS.get(domain, domain)}\n",
                f"Niveles medios de C{cluster} terminal:",
                _markdown_table(
                    _pivot("media_cluster_terminal"), ["métrica", *level_columns], limit=100
                ),
                f"Brecha media C{cluster} terminal − CONTINUA ponderada:",
                _markdown_table(
                    _pivot("brecha_media_cluster_menos_continua"),
                    ["métrica", *level_columns],
                    limit=100,
                ),
            ]
        )
    lines.append(
        "Estas medias históricas no son trayectorias individuales: cambian los episodios "
        "observables y no se estima un efecto causal de ninguna variable."
    )
    return "\n".join(lines) + "\n"


def _profile_executive_context() -> str:
    """Resume en el informe de perfiles el alcance y señales globales del ejecutivo."""

    monthly = _read_table("cohorte_resumen_mensual.csv")
    persistence = _read_table("persistencia_senales.csv")
    domains = _read_table("matriz_dominios_efecto.csv")
    n_baja = _number(monthly, "n_baja")
    n_continua = _number(monthly, "n_continua")
    n_strata = (
        _read_table("cohorte_ancla_horizonte.csv")
        .select(["foto_mes_ancla", "horizonte_evento"])
        .unique()
        .height
    )
    persistent = persistence.filter(pl.col("clasificacion_persistencia") == "persistente")
    return "\n".join(
        [
            "## Marco del informe ejecutivo\n",
            f"El informe ejecutivo analiza **{n_baja} episodios BAJA** y "
            f"**{n_continua} episodios CONTINUA** en **{n_strata} estratos "
            "ancla–horizonte**. CONTINUA es una referencia seleccionada "
            "determinísticamente por estrato, no un contrafactual causal.",
            f"En el conjunto total, **{persistent.height} variables** cumplen el criterio de "
            "persistencia: misma dirección con IC95% fuera de cero en al menos 75 % de las "
            "anclas y tres o más anclas.",
            "Efecto medio absoluto por dominio en la cohorte completa (lectura agregada, no causal):",
            _markdown_table(
                domains,
                ["dominio", "n_vars", "mean_abs_cohens_d", "max_abs_cohens_d"],
                limit=domains.height,
            ),
            "Los perfiles y el histórico C1 que siguen son un desglose de ese marco global; "
            "no sustituyen sus controles estratificados ni convierten las asociaciones en causas.",
        ]
    ) + "\n"


def write_informe_perfiles_clientes(cluster_meta: dict, plot_paths: list[str]) -> None:
    """Escribe perfiles descriptivos trazables o una advertencia de no aceptación."""

    lines = [
        "# Perfiles de clientes por clúster\n",
        "Este informe es descriptivo. Las diferencias al ancla se contrastan contra "
        "CONTINUA emparejada por `(foto_mes_ancla, horizonte_evento)` con los mismos "
        "pesos estratificados usados por el pipeline; no prueban causalidad.\n",
        "Semántica de BAJA: un cliente rotulado BAJA+1 en la foto `t` deja de estar en la "
        "base en `t+1`; para BAJA+2 deja de estar en `t+2`. En este informe "
        "`mes_relativo=0` es esa primera foto sin registro, no una observación. BAJA+1 se "
        "ancla en `t=-1` y BAJA+2 en `t=-2`; las trayectorias BAJA usan exclusivamente "
        "`t<0`.\n",
        _profile_executive_context(),
    ]
    if not bool(cluster_meta.get("segmentacion_aceptada")):
        reasons = cluster_meta.get("motivos_no_aceptacion", [])
        lines.extend(
            [
                "## Advertencia de validación\n",
                "La segmentación fue **rechazada**. No se describen perfiles ni se reutilizan "
                "asignaciones de ejecuciones previas.",
                "- Motivo: "
                + ("; ".join(str(reason) for reason in reasons) if reasons else "no especificado.")
                + "\n",
                "Los gráficos siguientes contienen la misma advertencia:\n",
            ]
        )
        lines.extend(f"![Advertencia de segmentación]({path})\n" for path in plot_paths)
        (RESULTS_DIR / "informe_perfiles_clientes.md").write_text(
            "\n".join(lines), encoding="utf-8"
        )
        return

    summary = _read_table("cluster_fichas_resumen.csv")
    profiles = _read_table("cluster_fichas_dominios.csv").filter(
        pl.col("variable").is_in(PROFILE_VARIABLES)
    )
    operative_finances = _read_table("cluster_fichas_finanzas_operativas.csv")
    nominal_profiles = _read_table("cluster_fichas_nominales.csv")
    total_baja = int(summary["n"].sum())
    key_metrics = profiles.filter(
        pl.col("variable").is_in(["ctrx_quarter", "mcuentas_saldo"])
    )
    lines.extend(
        [
            "## Alcance\n",
            f"Se describen {total_baja} episodios BAJA en **{summary.height} clústeres aceptados**. "
            f"AUC temporal media/mínima: **{_fmt(cluster_meta.get('auc_temporal_media'))} / "
            f"{_fmt(cluster_meta.get('auc_temporal_min'))}**; silueta elegida: "
            f"**{_fmt(cluster_meta.get('silhouette_elegido'))}**.",
            "No hay patrimonio neto ni deuda total consolidada en la fuente. Los saldos, "
            "préstamos y tarjetas son proxies operativos y no permiten afirmaciones absolutas "
            "sobre riqueza, endeudamiento total o capacidad de pago.\n",
            "## Tamaño de los clústeres\n",
            _markdown_table(summary.sort("cluster"), ["cluster", "n", "peso", "BAJA+1", "BAJA+2"]),
            "\n## Síntesis comparativa\n",
        ]
    )
    for summary_row in summary.sort("cluster").iter_rows(named=True):
        cluster = int(summary_row["cluster"])
        metrics = {
            row["variable"]: row
            for row in key_metrics.filter(pl.col("cluster") == cluster).iter_rows(named=True)
        }
        transactions = metrics.get("ctrx_quarter", {})
        balance = metrics.get("mcuentas_saldo", {})
        weight = float(summary_row["peso"]) * 100
        lines.append(
            f"- C{cluster}: **{_fmt(summary_row['n'])} episodios ({weight:.0f} %)**; "
            f"{_fmt(transactions.get('media_segmento'))} transacciones trimestrales frente a "
            f"{_fmt(transactions.get('media_continua_emparejada'))} en CONTINUA; saldo de "
            f"cuentas {_fmt(balance.get('media_segmento'))} frente a "
            f"{_fmt(balance.get('media_continua_emparejada'))}."
        )
    lines.extend(
        [
            "El detalle siguiente cubre payroll, cuentas, préstamos, tarjetas, edad y "
            "antigüedad, con sus brechas frente a CONTINUA emparejada.",
        ]
    )
    for summary_row in summary.sort("cluster").iter_rows(named=True):
        cluster = int(summary_row["cluster"])
        rows = profiles.filter(pl.col("cluster") == cluster)
        by_variable = {row["variable"]: row for row in rows.iter_rows(named=True)}
        lines.extend(
            [
                f"\n## Clúster C{cluster}\n",
                f"C{cluster} reúne **{summary_row['n']} episodios BAJA** "
                f"({_fmt(summary_row.get('peso'))} del total BAJA). Se observan sus niveles "
                "al ancla y sus brechas descriptivas frente a CONTINUA emparejada.",
            ]
        )
        categories = [
            ("Demografía", ["cliente_edad", "cliente_antiguedad"]),
            (
                "Uso transaccional",
                ["ctrx_quarter", "ctarjeta_visa_transacciones", "ctarjeta_master_transacciones"],
            ),
            ("Payroll y cuentas", ["mpayroll", "tcuentas", "mcuentas_saldo"]),
            (
                "Préstamos y tarjetas",
                [
                    "mprestamos_personales",
                    "mprestamos_prendarios",
                    "Visa_msaldototal",
                    "Master_msaldototal",
                ],
            ),
        ]
        for heading, variables in categories:
            available = [
                _profile_metric_sentence(by_variable[variable], PROFILE_LABELS[variable])
                for variable in variables
                if variable in by_variable
            ]
            if available:
                lines.append(f"\n**{heading}.** " + " ".join(available))

        finance_rows = operative_finances.filter(pl.col("cluster") == cluster).sort("variable")
        lines.extend(
            [
                "\n### Finanzas operativas\n",
                "`deuda_total_operativa = mprestamos_personales + "
                "mprestamos_prendarios + mprestamos_hipotecarios + "
                "max(Visa_msaldototal, 0) + max(Master_msaldototal, 0)`; "
                "`patrimonio_liquido_operativo = mcuentas_saldo − "
                "deuda_total_operativa`. Los nulos de las variables fuente se tratan como cero.",
                _operational_finance_table(finance_rows),
                "Limitación: `patrimonio_liquido_operativo` no es patrimonio neto. "
                "Excluye `mactivos_margen` y `mpasivos_margen`, además de activos, pasivos "
                "y obligaciones que no estén representados en esta fórmula.",
            ]
        )

        nominal_display = (
            nominal_profiles.filter(pl.col("cluster") == cluster)
            .with_columns(
                pl.col("variable")
                .map_elements(
                    lambda variable: HISTORICAL_VARIABLE_LABELS.get(variable, variable),
                    return_dtype=pl.String,
                )
                .alias("métrica")
            )
            .select(
                [
                    "dominio",
                    "métrica",
                    "n_segmento",
                    "media_segmento",
                    "mediana_segmento",
                    "media_continua_emparejada",
                    "mediana_continua_emparejada",
                    "brecha_nominal_vs_continua",
                    "diferencia_pct_vs_continua",
                ]
            )
            .sort("dominio", "métrica")
            .rename(
                {
                    "n_segmento": "n BAJA",
                    "media_segmento": "BAJA media nominal",
                    "mediana_segmento": "BAJA mediana nominal",
                    "media_continua_emparejada": "CONTINUA media nominal",
                    "mediana_continua_emparejada": "CONTINUA mediana nominal",
                    "brecha_nominal_vs_continua": "brecha nominal BAJA−CONTINUA",
                    "diferencia_pct_vs_continua": "diferencia porcentual vs CONTINUA",
                }
            )
        )
        lines.extend(
            [
                "\n### Perfil nominal completo al ancla\n",
                "Las filas siguientes usan los valores nominales de las columnas fuente; "
                "no muestran percentiles, `percent_rnk` ni puntuaciones SHAP. La diferencia "
                "porcentual se calcula como `(media BAJA − media CONTINUA) / "
                "abs(media CONTINUA) × 100`; queda sin definir si la media CONTINUA es cero.",
                _markdown_table(
                    nominal_display,
                    [
                        "dominio",
                        "métrica",
                        "n BAJA",
                        "BAJA media nominal",
                        "BAJA mediana nominal",
                        "CONTINUA media nominal",
                        "CONTINUA mediana nominal",
                        "brecha nominal BAJA−CONTINUA",
                        "diferencia porcentual vs CONTINUA",
                    ],
                    limit=nominal_display.height,
                ),
            ]
        )
    transition_section = _transition_profile_section(cluster_meta)
    if transition_section:
        lines.append(transition_section)
    for cluster in (0, 1):
        terminal_lifecycle = _terminal_cluster_balance_lifecycle_section(cluster_meta, cluster)
        if terminal_lifecycle:
            lines.append(terminal_lifecycle)
        historical_profile_detail = _terminal_cluster_historical_profile_detail_section(
            cluster_meta, cluster
        )
        if historical_profile_detail:
            lines.append(historical_profile_detail)
    lines.extend(
        [
            "\n## Gráficos trazables\n",
            "Cada métrica se muestra en paneles independientes cuando sus unidades difieren; "
            "las distribuciones se expresan como porcentaje dentro de cada grupo.",
        ]
    )
    plot_titles = [
        "Top 10 frente a CONTINUA",
        "Distribución de edad",
        "Distribución de antigüedad",
        "Perfil financiero",
    ]
    for index, path in enumerate(plot_paths):
        title = plot_titles[index] if index < len(plot_titles) else "Gráfico de perfil"
        lines.append(f"\n### {title}\n\n![{title}]({path})\n")
    lines.extend(
        [
            "## Conclusiones\n",
            "C0 conserva mayor actividad transaccional y liquidez observable que C1; "
            "C1 concentra menor actividad, menor antigüedad y peor saldo de cuentas. "
            "Estas asociaciones descriptivas no permiten concluir solvencia, endeudamiento "
            "total ni causalidad.",
            "## Limitaciones\n",
            "- CONTINUA es una referencia emparejada, no una contrafactual causal.",
            "- La ausencia de patrimonio neto y deuda total consolidada impide clasificaciones "
            "absolutas de solvencia o endeudamiento.",
            "- Los clústeres describen patrones en contribuciones SHAP validadas; no determinan "
            "causas de BAJA ni la conveniencia de una intervención.",
        ]
    )
    (RESULTS_DIR / "informe_perfiles_clientes.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def write_destacados() -> None:
    lines = [
        "# Gráficos destacados\n",
        "Cada ruta se usa para sustentar una decisión del informe: cobertura y comparabilidad "
        "(etapa 01), tamaño/incertidumbre de brechas (02), evolución alineada al evento (03) "
        "y validación de segmentación (04).\n",
    ]
    for etapa, paths in DESTACADOS_POR_ETAPA.items():
        lines.append(f"\n## Etapa {etapa:02d}\n")
        lines.extend(f"- `{path}`\n" for path in paths)
    (RESULTS_DIR / "destacados.md").write_text("".join(lines), encoding="utf-8")


def write_informe(
    audit: pl.DataFrame,
    contrastes: pl.DataFrame,
    cluster_meta: dict,
    plot_paths: dict[int, list[str]],
) -> None:
    """Escribe un informe ejecutivo sin inferencias fuera de las tablas fuente."""

    monthly = _read_table("cohorte_resumen_mensual.csv")
    strata = _read_table("cohorte_ancla_horizonte.csv")
    persistence = _read_table("persistencia_senales.csv")
    coverage = _read_table("cobertura_denominadores.csv")
    domains = _read_table("matriz_dominios_efecto.csv")
    persistent = persistence.filter(pl.col("clasificacion_persistencia") == "persistente")
    persistent_effects = (
        persistent.join(
            contrastes.select(
                [
                    "variable",
                    "diff_baja_menos_continua",
                    "cohens_d_ponderado",
                    "ic95_lo",
                    "ic95_hi",
                    "n_estratos_ponderados",
                ]
            ),
            on="variable",
            how="left",
        )
        .with_columns(pl.col("cohens_d_ponderado").abs().alias("_abs_d"))
        .sort("_abs_d", descending=True)
    )
    coverage_summary = (
        coverage.group_by("grupo")
        .agg(
            pl.col("cobertura_cohorte").min().alias("cobertura_min"),
            pl.col("cobertura_cohorte").max().alias("cobertura_max"),
        )
        .sort("grupo")
    )
    n_baja = _number(monthly, "n_baja")
    n_continua = _number(monthly, "n_continua")
    n_strata = strata.select(["foto_mes_ancla", "horizonte_evento"]).unique().height
    summary = (
        f"Se analizaron {n_baja} episodios BAJA y {n_continua} episodios CONTINUA "
        f"en {n_strata} estratos ancla–horizonte. "
        f"{persistent.height} variables cumplen el criterio de persistencia."
    )
    stage_counts = "\n".join(
        f"| {stage:02d} | {len(paths)} | `plots/etapa_{stage:02d}/` |"
        for stage, paths in sorted(plot_paths.items())
    )
    selected_graphs = "\n".join(
        f"![Gráfico de soporte]({path})"
        for paths in DESTACADOS_POR_ETAPA.values()
        for path in paths
    )
    body = f"""# Informe ejecutivo multimensual de bajas

## Resumen ejecutivo

{summary}

- El análisis es descriptivo: compara BAJA con CONTINUA comparable al ancla y no atribuye causas.
- Las prioridades por segmento son exploratorias: se sustentan en una segmentación aceptada
  para descripción, no en riesgo causal ni eficacia de tratamiento.

## Alcance y calidad de datos

- Fuente: `data/competencia_01.parquet`; fotos observadas: {", ".join(map(str, ALL_FOTO_MESES))}.
- Anclas configuradas y válidas: {", ".join(map(str, ANCHOR_MONTHS))}; horizontes BAJA+1 y BAJA+2.
- CONTINUA se seleccionó de forma determinista por `(foto_mes_ancla, horizonte_evento)`, con razón {CONTROL_RATIO}:1 y semilla {SAMPLE_SEED}; se excluyeron clientes BAJA.
- Semántica de BAJA: un cliente rotulado BAJA+1 en la foto `t` deja de estar en la base en `t+1`; para BAJA+2 deja de estar en `t+2`. En este informe `mes_relativo=0` es esa primera foto sin registro, no una observación. BAJA+1 se ancla en `t=-1` y BAJA+2 en `t=-2`.
- Las trayectorias BAJA y sus comparaciones se restringen a `mes_relativo<0`. No se publican niveles posteriores a la baja ni se interpreta la ausencia como saldo cero.
- Los tamaños de cohorte proceden de `tablas/cohorte_resumen_mensual.csv`; la auditoría por estrato de `tablas/auditoria_cohorte.parquet`.

| grupo | cobertura mínima | cobertura máxima |
| --- | --- | --- |
{chr(10).join(f"| {row['grupo']} | {_fmt(row['cobertura_min'])} | {_fmt(row['cobertura_max'])} |" for row in coverage_summary.iter_rows(named=True))}

## Evolución multimensual

Tamaños observados por mes de ancla:

{_markdown_table(monthly, ["foto_mes_ancla", "n_baja", "n_continua", "n_total_cohorte", "tasa_baja_cohorte", "ratio_controles_por_baja_medio"])}

La evolución se lee sólo antes de la desaparición (`mes_relativo<0`) y se separa por mes
calendario en `tablas/trayectorias_nivel_calendario.csv`; los denominadores están en
`tablas/denominadores_metricas.csv`. Las trayectorias no prueban cambio individual ni causalidad.

## Hallazgos persistentes

El criterio exige una dirección con IC95% fuera de cero en al menos 75% de las anclas y al
menos tres anclas. Las filas siguientes son diferencias BAJA−CONTINUA ponderadas por estrato:

{_markdown_table(persistent_effects, ["variable", "n_anclas_evaluadas", "diff_baja_menos_continua", "cohens_d_ponderado", "ic95_lo", "ic95_hi", "n_estratos_ponderados"])}

Dominios con efecto medio absoluto (lectura agregada, no causal):

{_markdown_table(domains, ["dominio", "n_vars", "mean_abs_cohens_d", "max_abs_cohens_d"])}

{_cluster_section(cluster_meta)}
{_temporal_transition_section(cluster_meta)}
{_terminal_cluster_balance_lifecycle_section(cluster_meta, 0)}
{_terminal_cluster_historical_profile_detail_section(cluster_meta, 0)}
{_terminal_cluster_balance_lifecycle_section(cluster_meta, 1)}
{_terminal_cluster_historical_profile_detail_section(cluster_meta, 1)}
## Metodología y limitaciones

- Cada episodio usa un identificador único; BAJA se deduplica por cliente y mes de evento esperado.
- Los contrastes se calculan al ancla, estratificados por ancla y horizonte; se ponderan por casos BAJA no nulos y usan {BOOTSTRAP_N} réplicas bootstrap.
- La validación de perfiles exige discriminación temporal, tamaño mínimo, silueta y estabilidad; una AUC alta sólo describe separación predictiva dentro de estos datos, no utilidad causal.
- La ventana termina en 202108. Por definición operativa de BAJA, no se usan fotos en `t=0` o posteriores para BAJA, no se imputan clientes ausentes y no se extrapola fuera de los seis meses.
- BAJA+1/BAJA+2 es una etiqueta observada de la fuente; el informe no verifica una cancelación efectiva ni el efecto de una intervención.

## Gráficos de soporte

| Etapa | gráficos generados | carpeta |
| --- | ---: | --- |
{stage_counts}

{selected_graphs}

Rutas y criterio de selección: `destacados.md`. Tablas fuente: `tablas/`.
"""
    (RESULTS_DIR / "informe_final.md").write_text(body, encoding="utf-8")

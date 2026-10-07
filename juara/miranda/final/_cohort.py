"""Construcción reproducible del panel longitudinal BAJA versus CONTINUA."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb
import polars as pl

from _config import (
    ALL_FOTO_MESES,
    ANCHOR_MONTHS,
    BAJA_CLASSES,
    CONTINUA_CLASS,
    CONTROL_RATIO,
    EVENT_HORIZONS,
    MIN_BAJAS_PER_STRATUM,
    SAMPLE_FRAC,
    SAMPLE_SEED,
)
from _paths import PANEL_DIR, SOURCE_PARQUET, TABLAS_DIR, ensure_output_directories

DEBT_SOURCE_COLUMNS = (
    "mprestamos_personales",
    "mprestamos_prendarios",
    "mprestamos_hipotecarios",
    "Visa_msaldototal",
    "Master_msaldototal",
)
OPERATIVE_BALANCE_COLUMN = "mcuentas_saldo"


def yyyymm_to_ord(ym: int) -> int:
    return (ym // 100) * 12 + (ym % 100)


def add_yyyymm(ym: int, delta: int) -> int:
    y, m = ym // 100, ym % 100
    m += delta
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    return y * 100 + m


def horizonte_meses(clase: str) -> int:
    if clase == "BAJA+1":
        return 1
    if clase == "BAJA+2":
        return 2
    raise ValueError(f"clase no BAJA: {clase}")


def _sample_continua(continua_anchor: pl.DataFrame, exclude_clients: pl.Series) -> pl.DataFrame:
    base = continua_anchor.filter(~pl.col("numero_de_cliente").is_in(exclude_clients.to_list()))
    ranked = base.with_columns(
        pl.struct("numero_de_cliente", "foto_mes")
        .hash(seed=SAMPLE_SEED)
        .rank(method="ordinal")
        .over("foto_mes")
        .alias("_rank_hash"),
        pl.len().over("foto_mes").alias("_n"),
    ).with_columns((pl.col("_n") * SAMPLE_FRAC).ceil().cast(pl.Int64).alias("_cap"))
    return (
        ranked.filter(pl.col("_rank_hash") <= pl.col("_cap"))
        .select("numero_de_cliente", pl.col("foto_mes").alias("foto_mes_ancla"))
        .unique()
    )


def _add_operational_financial_variables(raw: pl.DataFrame) -> pl.DataFrame:
    """Añade proxies operativos de deuda y patrimonio líquido, no contable."""

    debt = (
        pl.col("mprestamos_personales").fill_null(0)
        + pl.col("mprestamos_prendarios").fill_null(0)
        + pl.col("mprestamos_hipotecarios").fill_null(0)
        + pl.max_horizontal(pl.col("Visa_msaldototal").fill_null(0), pl.lit(0))
        + pl.max_horizontal(pl.col("Master_msaldototal").fill_null(0), pl.lit(0))
    )
    return raw.with_columns(debt.alias("deuda_total_operativa")).with_columns(
        (pl.col(OPERATIVE_BALANCE_COLUMN).fill_null(0) - pl.col("deuda_total_operativa")).alias(
            "patrimonio_liquido_operativo"
        )
    )


def build_cohort(raw: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Construye la cohorte en memoria con el mismo diseño que el materializador.

    Conserva esta API para el orquestador legado. Cada cliente BAJA conserva un
    único registro por evento esperado; los CONTINUA se replican por estrato
    sólo mediante identificadores de miembro distintos.
    """

    validate_source(raw)
    raw = _add_operational_financial_variables(raw)
    negative_operational_debt = raw.filter(
        pl.col("deuda_total_operativa").is_null() | (pl.col("deuda_total_operativa") < 0)
    ).height
    if negative_operational_debt:
        raise CohortValidationError(
            "deuda_total_operativa debe ser no negativa; "
            f"se detectaron {negative_operational_debt} filas inválidas."
        )
    available_months = set(raw["foto_mes"].unique().to_list())
    valid_anchors = [
        anchor
        for anchor in ANCHOR_MONTHS
        if all(
            add_yyyymm(anchor, horizon) in available_months
            and raw.filter(
                (pl.col("foto_mes") == anchor)
                & (pl.col("clase_ternaria") == f"BAJA+{horizon}")
            ).height
            >= MIN_BAJAS_PER_STRATUM
            for horizon in EVENT_HORIZONS
        )
    ]
    if not valid_anchors:
        raise CohortValidationError("No hay anclas aptas para construir la cohorte.")

    anchor = raw.filter(pl.col("foto_mes").is_in(valid_anchors))
    baja_raw = anchor.filter(pl.col("clase_ternaria").is_in(list(BAJA_CLASSES)))
    n_baja_raw = baja_raw.height
    dup_clients = (
        baja_raw.group_by("numero_de_cliente")
        .agg(pl.len().alias("n_events"))
        .filter(pl.col("n_events") > 1)
    )

    def _ord_expr(col: str) -> pl.Expr:
        return ((pl.col(col) // 100) * 12 + (pl.col(col) % 100)).cast(pl.Int64)

    baja_ranked = baja_raw.with_columns(
        _ord_expr("foto_mes").alias("_ord_ancla"),
        pl.col("clase_ternaria")
        .map_elements(horizonte_meses, return_dtype=pl.Int64)
        .alias("_horiz"),
    ).with_columns(
        pl.struct(["foto_mes", "_horiz"])
        .map_elements(
            lambda s: add_yyyymm(s["foto_mes"], s["_horiz"]),
            return_dtype=pl.Int64,
        )
        .alias("mes_evento_esperado")
    ).sort(["numero_de_cliente", "mes_evento_esperado", "_ord_ancla", "_horiz"])

    baja_one = (
        baja_ranked.group_by(["numero_de_cliente", "mes_evento_esperado"], maintain_order=True)
        .first()
        .with_columns(
            pl.lit("BAJA").alias("grupo"),
            pl.col("foto_mes").alias("foto_mes_ancla"),
            pl.col("clase_ternaria").alias("clase_ancla"),
            pl.col("_horiz").alias("horizonte_evento"),
        )
        .with_columns(
            pl.struct(["foto_mes_ancla", "horizonte_evento"])
            .map_elements(
                lambda s: add_yyyymm(s["foto_mes_ancla"], s["horizonte_evento"]),
                return_dtype=pl.Int64,
            )
            .alias("mes_evento_esperado"),
            pl.col("horizonte_evento").alias("horizonte_meses"),
        )
    )

    strata = (
        baja_one.group_by("foto_mes_ancla", "horizonte_evento")
        .agg(pl.len().alias("n_bajas"))
        .with_columns((pl.col("n_bajas") * CONTROL_RATIO).alias("n_controles_requeridos"))
    )

    baja_client_ids = baja_raw["numero_de_cliente"]
    continua_anchor = anchor.filter(pl.col("clase_ternaria") == CONTINUA_CLASS).select(
        "numero_de_cliente", "foto_mes"
    )
    continua_sample = (
        continua_anchor.filter(~pl.col("numero_de_cliente").is_in(baja_client_ids.to_list()))
        .rename({"foto_mes": "foto_mes_ancla"})
        .join(strata, on="foto_mes_ancla", how="inner")
        .with_columns(
            pl.struct(
                ["numero_de_cliente", "foto_mes_ancla", "horizonte_evento"]
            ).hash(seed=SAMPLE_SEED).alias("_hash")
        )
        .with_columns(
            pl.col("_hash")
            .rank(method="ordinal")
            .over("foto_mes_ancla", "horizonte_evento")
            .alias("_orden_control")
        )
    )
    supply = (
        continua_sample.group_by("foto_mes_ancla", "horizonte_evento")
        .agg(pl.len().alias("n_controles_disponibles"))
        .join(strata, on=["foto_mes_ancla", "horizonte_evento"], how="right")
        .fill_null(0)
    )
    insufficient_controls = supply.filter(
        pl.col("n_controles_disponibles") < pl.col("n_controles_requeridos")
    )
    if insufficient_controls.height:
        raise CohortValidationError(
            f"Suministro CONTINUA insuficiente: {insufficient_controls.to_dicts()}"
        )
    continua_sample = continua_sample.filter(
        pl.col("_orden_control") <= pl.col("n_controles_requeridos")
    )
    cohort_cols = [
        "cohort_member_id",
        "numero_de_cliente",
        "grupo",
        "foto_mes_ancla",
        "clase_ancla",
        "horizonte_evento",
        "horizonte_meses",
        "mes_evento_esperado",
        "es_control_replicado",
    ]
    baja_one = baja_one.with_columns(
        pl.format(
            "BAJA|{}|{}|{}",
            "numero_de_cliente",
            "foto_mes_ancla",
            "horizonte_evento",
        ).alias("cohort_member_id"),
        pl.lit(False).alias("es_control_replicado"),
    ).select(cohort_cols)
    continua_cohort = continua_sample.with_columns(
        pl.lit("CONTINUA").alias("grupo"),
        pl.lit(CONTINUA_CLASS).alias("clase_ancla"),
        pl.col("horizonte_evento").alias("horizonte_meses"),
        pl.struct(["foto_mes_ancla", "horizonte_evento"])
        .map_elements(
            lambda s: add_yyyymm(s["foto_mes_ancla"], s["horizonte_evento"]),
            return_dtype=pl.Int64,
        )
        .alias("mes_evento_esperado"),
        pl.format(
            "CONTINUA|{}|{}|{}",
            "numero_de_cliente",
            "foto_mes_ancla",
            "horizonte_evento",
        ).alias("cohort_member_id"),
    ).with_columns(
        (pl.len().over("numero_de_cliente") > 1).alias("es_control_replicado")
    ).select(cohort_cols)

    cohort = pl.concat([baja_one, continua_cohort], how="vertical")
    if cohort["cohort_member_id"].n_unique() != cohort.height:
        raise CohortValidationError("Miembros de cohorte duplicados.")

    panel = (
        raw.filter(pl.col("foto_mes").is_in(list(ALL_FOTO_MESES)))
        .join(cohort, on="numero_de_cliente", how="inner")
        .with_columns(
            _ord_expr("foto_mes").alias("_ord_foto"),
            _ord_expr("mes_evento_esperado").alias("_ord_evento"),
        )
        .with_columns((pl.col("_ord_foto") - pl.col("_ord_evento")).alias("mes_relativo"))
        .drop("_ord_foto", "_ord_evento")
        .filter((pl.col("grupo") != "BAJA") | (pl.col("mes_relativo") < 0))
    )
    if panel.select(pl.struct(["cohort_member_id", "foto_mes"]).n_unique()).item() != panel.height:
        raise CohortValidationError("Fotos duplicadas dentro de un episodio de cohorte.")

    audit = _build_audit(
        baja_raw, dup_clients, baja_one, continua_cohort, panel, n_baja_raw, raw.height
    )
    return cohort, panel, audit


def _build_audit(
    baja_raw: pl.DataFrame,
    dup_clients: pl.DataFrame,
    baja_one: pl.DataFrame,
    continua_cohort: pl.DataFrame,
    panel: pl.DataFrame,
    n_baja_raw: int,
    n_fuente: int,
) -> pl.DataFrame:
    rows = [
        ("filas_fuente", n_fuente),
        ("filas_baja_ancla_bruto", n_baja_raw),
        ("clientes_baja_unicos", baja_one.height),
        ("clientes_baja_duplicados_resueltos", dup_clients.height),
        ("clientes_continua_muestra", continua_cohort.height),
        ("filas_panel", panel.height),
    ]
    audit_counts = pl.DataFrame({"metrica": [r[0] for r in rows], "valor": [r[1] for r in rows]})

    by_grupo = (
        panel.filter(pl.col("foto_mes") == pl.col("foto_mes_ancla"))
        .group_by("grupo")
        .agg(pl.col("numero_de_cliente").n_unique().alias("n_clientes_ancla"))
    )

    cobertura = (
        panel.group_by("grupo", "mes_relativo")
        .agg(pl.col("numero_de_cliente").n_unique().alias("n_clientes"))
        .sort("grupo", "mes_relativo")
    )

    comp_baja = (
        baja_one.group_by("foto_mes_ancla", "clase_ancla")
        .agg(pl.len().alias("n"))
        .sort("foto_mes_ancla", "clase_ancla")
    )

    TABLAS_DIR.mkdir(parents=True, exist_ok=True)
    audit_counts.write_csv(TABLAS_DIR / "auditoria_cardinalidades.csv")
    by_grupo.write_csv(TABLAS_DIR / "auditoria_clientes_ancla.csv")
    cobertura.write_csv(TABLAS_DIR / "auditoria_cobertura_mes_relativo.csv")
    comp_baja.write_csv(TABLAS_DIR / "auditoria_composicion_baja12.csv")
    dup_clients.write_csv(TABLAS_DIR / "auditoria_duplicados_baja.csv")
    baja_one.write_parquet(TABLAS_DIR / "cohorte_baja.parquet")
    continua_cohort.write_parquet(TABLAS_DIR / "cohorte_continua.parquet")
    panel.write_parquet(TABLAS_DIR / "panel_longitudinal.parquet")

    return audit_counts


def validate_source(raw: pl.DataFrame) -> None:
    for col in ("numero_de_cliente", "foto_mes", "clase_ternaria"):
        if col not in raw.columns:
            raise CohortValidationError(f"Columna crítica ausente: {col}")
    missing_debt_columns = sorted(set(DEBT_SOURCE_COLUMNS) - set(raw.columns))
    if missing_debt_columns:
        raise CohortValidationError(
            "Columnas fuente requeridas para deuda_total_operativa ausentes: "
            f"{missing_debt_columns}"
        )
    if OPERATIVE_BALANCE_COLUMN not in raw.columns:
        raise CohortValidationError(
            f"Columna fuente requerida para patrimonio_liquido_operativo ausente: "
            f"{OPERATIVE_BALANCE_COLUMN}"
        )
    meses = sorted(raw["foto_mes"].unique().to_list())
    missing = sorted(set(ALL_FOTO_MESES) - set(meses))
    if missing:
        raise CohortValidationError(f"foto_mes incompletos; faltan: {missing}")
    invalid = [month for month in meses if not _is_valid_yyyymm(month)]
    if invalid:
        raise CohortValidationError(f"foto_mes contiene YYYYMM inválidos: {invalid}")
    if raw.select(pl.struct(["numero_de_cliente", "foto_mes"]).n_unique()).item() != raw.height:
        raise CohortValidationError("La fuente contiene claves duplicadas de cliente y foto_mes.")
    if raw["numero_de_cliente"].null_count():
        raise CohortValidationError("numero_de_cliente contiene nulos.")
    invalid_clients = raw.filter(
        pl.col("numero_de_cliente") != pl.col("numero_de_cliente").floor()
    ).height
    if invalid_clients:
        raise CohortValidationError(
            "numero_de_cliente contiene valores no enteros; no puede usarse como clave."
        )


class CohortValidationError(ValueError):
    """Indica que la fuente no permite construir una cohorte comparable."""


def _is_valid_yyyymm(month: int) -> bool:
    return isinstance(month, int) and 1 <= month % 100 <= 12


def _validate_config(config: "PipelineConfig") -> None:
    """Verifica que la ventana y sus anclas permitan ambos horizontes."""

    study_months = tuple(config.study_months)
    anchor_months = tuple(config.anchor_months)
    if not study_months or tuple(sorted(set(study_months))) != study_months:
        raise CohortValidationError("study_months debe ser una secuencia ascendente y sin duplicados.")
    if not all(_is_valid_yyyymm(month) for month in study_months):
        raise CohortValidationError("study_months contiene meses YYYYMM inválidos.")
    if not anchor_months or tuple(sorted(set(anchor_months))) != anchor_months:
        raise CohortValidationError("anchor_months debe ser una secuencia ascendente y sin duplicados.")
    if not all(_is_valid_yyyymm(month) for month in anchor_months):
        raise CohortValidationError("anchor_months contiene meses YYYYMM inválidos.")
    if not set(anchor_months).issubset(study_months):
        raise CohortValidationError("Toda ancla debe pertenecer a study_months.")
    if config.control_ratio <= 0 or config.minimum_bajas_per_stratum <= 0:
        raise CohortValidationError("control_ratio y minimum_bajas_per_stratum deben ser positivos.")

    unavailable_events = [
        (anchor, horizon)
        for anchor in anchor_months
        for horizon in EVENT_HORIZONS
        if add_yyyymm(anchor, horizon) not in study_months
    ]
    if unavailable_events:
        detail = ", ".join(f"{anchor}/+{horizon}" for anchor, horizon in unavailable_events)
        raise CohortValidationError(f"Anclas sin foto post-evento en la ventana: {detail}")


@dataclass(frozen=True)
class PipelineConfig:
    """Parámetros explícitos de la cohorte y de sus controles reproducibles."""

    anchor_months: tuple[int, ...] = ANCHOR_MONTHS
    study_months: tuple[int, ...] = ALL_FOTO_MESES
    event_labels: tuple[str, ...] = tuple(sorted(BAJA_CLASSES))
    control_label: str = CONTINUA_CLASS
    control_ratio: int = CONTROL_RATIO
    random_seed: int = SAMPLE_SEED
    minimum_bajas_per_stratum: int = MIN_BAJAS_PER_STRATUM

    @property
    def required_columns(self) -> tuple[str, ...]:
        return (
            "numero_de_cliente",
            "foto_mes",
            "clase_ternaria",
            *DEBT_SOURCE_COLUMNS,
            OPERATIVE_BALANCE_COLUMN,
        )


@dataclass(frozen=True)
class CohortArtifacts:
    """Rutas y cardinalidades producidas por la construcción de la cohorte."""

    cohort_members: Path
    longitudinal_panel: Path
    event_candidates: Path
    cohort_size: int
    panel_size: int


def _sql_path(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def _source_relation(source: Path) -> str:
    return f"read_parquet('{_sql_path(source)}')"


def _month_shift_sql(month: str, horizon: str) -> str:
    month_index = f"(CAST(FLOOR(({month}) / 100) AS INTEGER) * 12 + MOD(({month}), 100) - 1)"
    shifted_index = f"({month_index} + ({horizon}))"
    return (
        f"(CAST(FLOOR(({shifted_index}) / 12) AS INTEGER) * 100"
        f" + MOD(({shifted_index}), 12) + 1)"
    )


def _relative_month_sql(month: str, event_month: str) -> str:
    month_index = f"(CAST(FLOOR(({month}) / 100) AS INTEGER) * 12 + MOD(({month}), 100))"
    event_index = (
        f"(CAST(FLOOR(({event_month}) / 100) AS INTEGER) * 12"
        f" + MOD(({event_month}), 100))"
    )
    return f"CAST(({month_index} - {event_index}) AS INTEGER)"


def _copy_parquet(connection: duckdb.DuckDBPyConnection, query: str, destination: Path) -> None:
    connection.execute(
        f"COPY ({query}) TO '{_sql_path(destination)}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )


def _validate_panel_source(
    connection: duckdb.DuckDBPyConnection, source: Path, config: PipelineConfig
) -> dict[str, object]:
    _validate_config(config)
    if not source.is_file():
        raise CohortValidationError(f"Fuente inexistente: {source}")

    relation = _source_relation(source)
    columns = tuple(row[0] for row in connection.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall())
    missing_critical_columns = sorted(
        {"numero_de_cliente", "foto_mes", "clase_ternaria"} - set(columns)
    )
    if missing_critical_columns:
        raise CohortValidationError(f"Columnas críticas ausentes: {missing_critical_columns}")
    missing_debt_columns = sorted(set(DEBT_SOURCE_COLUMNS) - set(columns))
    if missing_debt_columns:
        raise CohortValidationError(
            "Columnas fuente requeridas para deuda_total_operativa ausentes: "
            f"{missing_debt_columns}"
        )
    if OPERATIVE_BALANCE_COLUMN not in columns:
        raise CohortValidationError(
            f"Columna fuente requerida para patrimonio_liquido_operativo ausente: "
            f"{OPERATIVE_BALANCE_COLUMN}"
        )

    months = tuple(
        row[0]
        for row in connection.execute(f"SELECT DISTINCT foto_mes FROM {relation} ORDER BY foto_mes").fetchall()
    )
    missing_months = sorted(set(config.study_months) - set(months))
    if missing_months:
        raise CohortValidationError(f"Meses requeridos ausentes: {missing_months}")
    invalid_months = [
        month for month in months if not isinstance(month, int) or not _is_valid_yyyymm(month)
    ]
    if invalid_months:
        raise CohortValidationError(f"foto_mes contiene valores YYYYMM inválidos: {invalid_months}")

    duplicate_keys = connection.execute(
        f"SELECT COUNT(*) - COUNT(DISTINCT (numero_de_cliente, foto_mes)) FROM {relation}"
    ).fetchone()[0]
    if duplicate_keys:
        raise CohortValidationError(
            f"La fuente contiene {duplicate_keys} claves duplicadas de cliente y foto_mes."
        )

    invalid_clients = connection.execute(
        f"""
        SELECT COUNT(*) FROM {relation}
        WHERE numero_de_cliente IS NULL
           OR numero_de_cliente != FLOOR(numero_de_cliente)
        """
    ).fetchone()[0]
    if invalid_clients:
        raise CohortValidationError(
            "numero_de_cliente contiene nulos o valores no enteros; no puede usarse como clave."
        )

    anchor_status: list[dict[str, int | str | bool]] = []
    valid_anchors: list[int] = []
    for anchor in config.anchor_months:
        strata_ok = True
        for label, horizon in (("BAJA+1", 1), ("BAJA+2", 2)):
            expected_event_month = add_yyyymm(anchor, horizon)
            n_candidates = connection.execute(
                f"""
                SELECT COUNT(*)
                FROM {relation}
                WHERE foto_mes = ? AND clase_ternaria = ?
                """,
                [anchor, label],
            ).fetchone()[0]
            post_photo_available = expected_event_month in months
            stratum_ok = (
                post_photo_available and n_candidates >= config.minimum_bajas_per_stratum
            )
            strata_ok = strata_ok and stratum_ok
            anchor_status.append(
                {
                    "foto_mes_ancla": anchor,
                    "clase_ancla": label,
                    "horizonte_evento": horizon,
                    "mes_evento_esperado": expected_event_month,
                    "foto_evento_disponible": post_photo_available,
                    "n_bajas_candidatas": n_candidates,
                    "estrato_apto": stratum_ok,
                }
            )
        if strata_ok:
            valid_anchors.append(anchor)

    if not valid_anchors:
        detail = ", ".join(
            f"{row['foto_mes_ancla']}/{row['clase_ancla']}={row['n_bajas_candidatas']}"
            for row in anchor_status
        )
        raise CohortValidationError(f"No hay anclas aptas para BAJA+1 y BAJA+2: {detail}")

    return {
        "filas": connection.execute(f"SELECT COUNT(*) FROM {relation}").fetchone()[0],
        "meses": months,
        "columnas": columns,
        "anclas_configuradas": config.anchor_months,
        "anclas_validas": tuple(valid_anchors),
        "auditoria_anclas": anchor_status,
    }


def build_longitudinal_panel(
    config: PipelineConfig = PipelineConfig(),
    source: Path = SOURCE_PARQUET,
) -> CohortArtifacts:
    """Materializa BAJA/CONTINUA con sus fotos y una referencia temporal común.

    Los episodios BAJA se deduplican por cliente y mes de evento esperado,
    conservando el ancla más temprana si el mismo evento aparece con ambos
    horizontes. Los CONTINUA se seleccionan con un orden hash estable por mes
    de anclaje y horizonte. La réplica por horizonte sólo crea una referencia
    temporal comparable; no atribuye a esos clientes un evento de baja.
    """

    ensure_output_directories()
    connection = duckdb.connect()
    try:
        source_audit = _validate_panel_source(connection, source, config)
        source_relation = _source_relation(source)
        valid_anchor_months = tuple(source_audit["anclas_validas"])
        anchor_months = ", ".join(map(str, valid_anchor_months))
        study_months = ", ".join(map(str, config.study_months))
        labels = ", ".join(f"'{label}'" for label in config.event_labels)
        connection.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE event_candidates_ranked AS
            WITH candidates AS (
                SELECT
                    CAST(numero_de_cliente AS BIGINT) AS numero_de_cliente,
                    foto_mes AS foto_mes_ancla,
                    clase_ternaria AS clase_ancla,
                    CASE clase_ternaria WHEN 'BAJA+1' THEN 1 WHEN 'BAJA+2' THEN 2 END
                        AS horizonte_evento
                FROM {source_relation}
                WHERE foto_mes IN ({anchor_months}) AND clase_ternaria IN ({labels})
            ),
            enriched AS (
                SELECT *,
                    {_month_shift_sql("foto_mes_ancla", "horizonte_evento")}
                        AS mes_evento_esperado
                FROM candidates
            )
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY numero_de_cliente, mes_evento_esperado
                    ORDER BY mes_evento_esperado, foto_mes_ancla, horizonte_evento
                ) AS orden_evento
            FROM enriched
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE TEMP TABLE selected_bajas AS
            SELECT * FROM event_candidates_ranked WHERE orden_evento = 1
            """
        )
        connection.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE case_strata AS
            SELECT foto_mes_ancla, horizonte_evento, COUNT(*) AS n_bajas,
                   COUNT(*) * {config.control_ratio}
                       AS n_controles_requeridos
            FROM selected_bajas
            GROUP BY ALL
            """
        )
        connection.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE eligible_controls AS
            SELECT CAST(source.numero_de_cliente AS BIGINT) AS numero_de_cliente,
                   source.foto_mes AS foto_mes_ancla
            FROM {source_relation} AS source
            WHERE source.foto_mes IN ({anchor_months})
              AND source.clase_ternaria = '{config.control_label}'
              AND NOT EXISTS (
                  SELECT 1 FROM event_candidates_ranked AS event
                  WHERE event.numero_de_cliente = CAST(source.numero_de_cliente AS BIGINT)
              )
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE TEMP TABLE control_supply AS
            SELECT strata.foto_mes_ancla, strata.horizonte_evento, strata.n_bajas,
                   COUNT(controls.numero_de_cliente) AS n_controles_disponibles,
                   strata.n_controles_requeridos
            FROM case_strata AS strata
            LEFT JOIN eligible_controls AS controls
              ON controls.foto_mes_ancla = strata.foto_mes_ancla
            GROUP BY ALL
            """
        )
        invalid_strata = connection.execute(
            f"""
            SELECT foto_mes_ancla, horizonte_evento, n_bajas,
                   n_controles_disponibles, n_controles_requeridos
            FROM control_supply
            WHERE n_controles_disponibles < n_controles_requeridos
            ORDER BY foto_mes_ancla, horizonte_evento
            """
        ).fetchall()
        if invalid_strata:
            detail = ", ".join(
                f"{month}/+{horizon}: bajas={bajas}, controles={available}/{required}"
                for month, horizon, bajas, available, required in invalid_strata
            )
            raise CohortValidationError(f"Estratos insuficientes: {detail}")

        duplicated_events = connection.execute(
            """
            SELECT COUNT(*) - COUNT(DISTINCT (numero_de_cliente, mes_evento_esperado))
            FROM selected_bajas
            """
        ).fetchone()[0]
        if duplicated_events:
            raise CohortValidationError(
                f"Episodios BAJA no deduplicados por cliente y evento: {duplicated_events}"
            )

        connection.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE selected_controls AS
            WITH ranked AS (
                SELECT controls.numero_de_cliente, strata.foto_mes_ancla,
                       strata.horizonte_evento, strata.n_controles_requeridos,
                       ROW_NUMBER() OVER (
                           PARTITION BY strata.foto_mes_ancla, strata.horizonte_evento
                           ORDER BY hash(
                               controls.numero_de_cliente, strata.foto_mes_ancla,
                               strata.horizonte_evento, {config.random_seed}
                           ), controls.numero_de_cliente
                       ) AS orden_control
                FROM eligible_controls AS controls
                INNER JOIN case_strata AS strata
                  ON strata.foto_mes_ancla = controls.foto_mes_ancla
            )
            SELECT * FROM ranked WHERE orden_control <= n_controles_requeridos
            """
        )
        connection.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE cohort_members AS
            WITH controls_with_replication AS (
                SELECT *,
                       COUNT(*) OVER (PARTITION BY numero_de_cliente) > 1
                           AS es_control_replicado
                FROM selected_controls
            )
            SELECT
                CONCAT('BAJA|', numero_de_cliente::VARCHAR, '|',
                       foto_mes_ancla::VARCHAR, '|', horizonte_evento::VARCHAR)
                    AS cohort_member_id,
                numero_de_cliente, 'BAJA' AS grupo, foto_mes_ancla,
                horizonte_evento, mes_evento_esperado, clase_ancla,
                FALSE AS es_control_replicado
            FROM selected_bajas
            UNION ALL
            SELECT
                CONCAT('CONTINUA|', numero_de_cliente::VARCHAR, '|',
                       foto_mes_ancla::VARCHAR, '|', horizonte_evento::VARCHAR),
                numero_de_cliente, 'CONTINUA', foto_mes_ancla, horizonte_evento,
                {_month_shift_sql("foto_mes_ancla", "horizonte_evento")},
                '{config.control_label}', es_control_replicado
            FROM controls_with_replication
            """
        )
        duplicated_members = connection.execute(
            "SELECT COUNT(*) - COUNT(DISTINCT cohort_member_id) FROM cohort_members"
        ).fetchone()[0]
        if duplicated_members:
            raise CohortValidationError(f"Miembros de cohorte duplicados: {duplicated_members}")

        bajas_in_controls = connection.execute(
            """
            SELECT COUNT(*)
            FROM cohort_members AS control
            INNER JOIN event_candidates_ranked AS baja USING (numero_de_cliente)
            WHERE control.grupo = 'CONTINUA'
            """
        ).fetchone()[0]
        if bajas_in_controls:
            raise CohortValidationError(
                f"Controles que figuran como BAJA en algún ancla: {bajas_in_controls}"
            )

        connection.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE longitudinal_panel AS
            SELECT source.*, cohort.cohort_member_id, cohort.grupo,
                   cohort.foto_mes_ancla, cohort.horizonte_evento,
                   cohort.horizonte_evento AS horizonte_meses,
                   cohort.mes_evento_esperado, cohort.clase_ancla,
                   cohort.es_control_replicado,
                   COALESCE(source.mprestamos_personales, 0)
                       + COALESCE(source.mprestamos_prendarios, 0)
                       + COALESCE(source.mprestamos_hipotecarios, 0)
                       + GREATEST(COALESCE(source.Visa_msaldototal, 0), 0)
                       + GREATEST(COALESCE(source.Master_msaldototal, 0), 0)
                       AS deuda_total_operativa,
                   COALESCE(source.mcuentas_saldo, 0)
                       - (
                           COALESCE(source.mprestamos_personales, 0)
                           + COALESCE(source.mprestamos_prendarios, 0)
                           + COALESCE(source.mprestamos_hipotecarios, 0)
                           + GREATEST(COALESCE(source.Visa_msaldototal, 0), 0)
                           + GREATEST(COALESCE(source.Master_msaldototal, 0), 0)
                       ) AS patrimonio_liquido_operativo,
                   {_relative_month_sql("source.foto_mes", "cohort.mes_evento_esperado")}
                       AS mes_relativo
            FROM {source_relation} AS source
            INNER JOIN cohort_members AS cohort
              ON CAST(source.numero_de_cliente AS BIGINT) = cohort.numero_de_cliente
            WHERE source.foto_mes IN ({study_months})
              AND (
                  cohort.grupo <> 'BAJA'
                  OR {_relative_month_sql("source.foto_mes", "cohort.mes_evento_esperado")} < 0
              )
            """
        )
        duplicated_panel_keys = connection.execute(
            "SELECT COUNT(*) - COUNT(DISTINCT (cohort_member_id, foto_mes)) FROM longitudinal_panel"
        ).fetchone()[0]
        if duplicated_panel_keys:
            raise CohortValidationError(f"Claves duplicadas en panel: {duplicated_panel_keys}")
        negative_operational_debt = connection.execute(
            """
            SELECT COUNT(*)
            FROM longitudinal_panel
            WHERE deuda_total_operativa IS NULL OR deuda_total_operativa < 0
            """
        ).fetchone()[0]
        if negative_operational_debt:
            raise CohortValidationError(
                "deuda_total_operativa debe ser no negativa; "
                f"se detectaron {negative_operational_debt} filas inválidas."
            )

        event_candidates = TABLAS_DIR / "candidatos_evento.parquet"
        cohort_members = TABLAS_DIR / "miembros_cohorte.parquet"
        longitudinal_panel = PANEL_DIR / "panel_longitudinal.parquet"
        _copy_parquet(
            connection,
            """
            SELECT *, orden_evento = 1 AS es_evento_seleccionado
            FROM event_candidates_ranked
            ORDER BY numero_de_cliente, foto_mes_ancla, horizonte_evento
            """,
            event_candidates,
        )
        _copy_parquet(
            connection,
            "SELECT * FROM cohort_members ORDER BY grupo, foto_mes_ancla, horizonte_evento, numero_de_cliente",
            cohort_members,
        )
        _copy_parquet(
            connection,
            "SELECT * FROM longitudinal_panel ORDER BY cohort_member_id, foto_mes",
            longitudinal_panel,
        )
        _copy_parquet(
            connection,
            """
            SELECT grupo, foto_mes_ancla, horizonte_evento, mes_evento_esperado,
                   clase_ancla, COUNT(*) AS n_miembros
            FROM cohort_members
            GROUP BY ALL
            ORDER BY grupo, foto_mes_ancla, horizonte_evento
            """,
            TABLAS_DIR / "auditoria_cohorte.parquet",
        )
        _copy_parquet(
            connection,
            """
            SELECT foto_mes_ancla, clase_ancla, horizonte_evento,
                   mes_evento_esperado,
                   COUNT(*) AS n_candidatos,
                   SUM(CASE WHEN orden_evento = 1 THEN 1 ELSE 0 END)
                       AS n_eventos_seleccionados
            FROM event_candidates_ranked
            GROUP BY ALL
            ORDER BY foto_mes_ancla, horizonte_evento
            """,
            TABLAS_DIR / "auditoria_composicion_baja12.parquet",
        )
        _copy_parquet(
            connection,
            """
            SELECT grupo, foto_mes_ancla, horizonte_evento, mes_relativo,
                   COUNT(DISTINCT cohort_member_id) AS n_miembros_observados
            FROM longitudinal_panel
            GROUP BY ALL
            ORDER BY grupo, foto_mes_ancla, horizonte_evento, mes_relativo
            """,
            TABLAS_DIR / "auditoria_cobertura_panel.parquet",
        )
        _copy_parquet(
            connection,
            """
            SELECT COUNT(*) AS n_candidatos,
                   COUNT(DISTINCT numero_de_cliente) AS n_clientes_candidatos,
                   SUM(CASE WHEN orden_evento = 1 THEN 1 ELSE 0 END) AS n_eventos_seleccionados,
                   SUM(CASE WHEN orden_evento > 1 THEN 1 ELSE 0 END) AS n_eventos_descartados
            FROM event_candidates_ranked
            """,
            TABLAS_DIR / "auditoria_duplicados_evento.parquet",
        )
        _copy_parquet(
            connection,
            "SELECT * FROM control_supply ORDER BY foto_mes_ancla, horizonte_evento",
            TABLAS_DIR / "auditoria_controles.parquet",
        )
        (TABLAS_DIR / "auditoria_fuente.json").write_text(
            json.dumps(
                {
                    "fuente": str(source),
                    "configuracion": asdict(config),
                    "perfil_fuente": source_audit,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        cohort_size = connection.execute("SELECT COUNT(*) FROM cohort_members").fetchone()[0]
        panel_size = connection.execute("SELECT COUNT(*) FROM longitudinal_panel").fetchone()[0]
        return CohortArtifacts(
            cohort_members=cohort_members,
            longitudinal_panel=longitudinal_panel,
            event_candidates=event_candidates,
            cohort_size=cohort_size,
            panel_size=panel_size,
        )
    finally:
        connection.close()

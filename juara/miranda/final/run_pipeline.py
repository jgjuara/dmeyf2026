"""Orquesta cohorte, contrastes, gráficos, clustering SHAP e informe."""

from __future__ import annotations

import sys

import polars as pl

from _cluster_shap import run_clustering, run_temporal_transitions
from _cohort import CohortValidationError, build_longitudinal_panel
from _config import MIN_BAJA_N, MIN_CONTINUA_N
from _metrics import calcular_metricas_temporales
from _paths import PLOTS_DIR, SOURCE_PARQUET, TABLAS_DIR, ensure_output_directories
from _plots_etapa01 import run as run_etapa01
from _plots_etapa02 import run as run_etapa02
from _plots_etapa03 import run as run_etapa03
from _plots_etapa04 import run as run_etapa04
from _plots_etapa04 import run_perfiles_clientes
from _report import write_destacados, write_informe, write_informe_perfiles_clientes


def _validate_sizes(panel: pl.DataFrame) -> None:
    snap = panel.filter(pl.col("foto_mes") == pl.col("foto_mes_ancla"))
    n_baja = snap.filter(pl.col("grupo") == "BAJA").height
    n_cont = snap.filter(pl.col("grupo") == "CONTINUA").height
    if n_baja < MIN_BAJA_N:
        raise CohortValidationError(f"Muy pocos casos BAJA en ancla: {n_baja} < {MIN_BAJA_N}")
    if n_cont < MIN_CONTINUA_N:
        raise CohortValidationError(f"Muy pocos CONTINUA en ancla: {n_cont} < {MIN_CONTINUA_N}")


def _clear_stage_plots() -> None:
    """Elimina PNG previos para que cada etapa publique exactamente sus diez gráficos."""

    for etapa in range(1, 5):
        stage_dir = PLOTS_DIR / f"etapa_{etapa:02d}"
        if stage_dir.is_dir():
            for plot in stage_dir.glob("*.png"):
                plot.unlink()


def main() -> None:
    ensure_output_directories()
    raw = pl.read_parquet(SOURCE_PARQUET)
    cohort_artifacts = build_longitudinal_panel()
    panel = pl.read_parquet(cohort_artifacts.longitudinal_panel)
    audit = pl.read_parquet(TABLAS_DIR / "auditoria_cohorte.parquet")
    _validate_sizes(panel)

    metricas = calcular_metricas_temporales(panel)
    contrastes = metricas.contrastes_agregados

    _clear_stage_plots()
    plot_paths: dict[int, list[str]] = {}
    plot_paths[1] = run_etapa01(panel, raw, metricas)
    plot_paths[2] = run_etapa02(panel, metricas)
    plot_paths[3] = run_etapa03(panel, metricas)
    cluster_out = run_clustering(panel)
    cluster_out["transitions"] = run_temporal_transitions(panel, cluster_out)
    plot_paths[4] = run_etapa04(panel, cluster_out)
    profile_plot_paths = run_perfiles_clientes(panel, cluster_out)

    for etapa, paths in plot_paths.items():
        if len(paths) != 10:
            raise SystemExit(f"Etapa {etapa:02d}: se esperaban 10 gráficos, hay {len(paths)}")

    write_destacados()
    write_informe(audit, contrastes, cluster_out["metrics"], plot_paths)
    write_informe_perfiles_clientes(cluster_out["metrics"], profile_plot_paths)

    print(f"panel: {panel.height} filas")
    print(f"gráficos: {sum(len(p) for p in plot_paths.values()) + len(profile_plot_paths)}")
    print(f"informe: resultados/informe_final.md")
    print(f"informe de perfiles: resultados/informe_perfiles_clientes.md")


if __name__ == "__main__":
    try:
        main()
    except CohortValidationError as error:
        print(f"Validación fallida: {error}", file=sys.stderr)
        raise SystemExit(2) from error

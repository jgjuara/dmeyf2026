"""Informe de perfiles agrupados a partir del corte jerárquico k=7."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy.cluster.hierarchy import fcluster

from _hierarchical import PROFILE_FEATURES, load_index_frame

K7 = 7
MERGED_K7_CLUSTERS = frozenset({2, 4, 5})
PROFILE_ORDER = ("C1", "C3", "C6", "C7", "C2_4_5")


def k7_to_perfil(cluster_k7: int) -> str:
    """Mapea etiqueta k=7 a perfil analítico (fusiona 2, 4 y 5)."""
    if cluster_k7 in MERGED_K7_CLUSTERS:
        return "C2_4_5"
    if cluster_k7 in (1, 3, 6, 7):
        return f"C{cluster_k7}"
    raise ValueError(f"cluster_k7 inesperado: {cluster_k7}")


def load_linkage(linkage_path: Path) -> np.ndarray:
    """Carga la matriz de enlace persistida."""
    if not linkage_path.is_file():
        raise FileNotFoundError(f"No existe enlace: {linkage_path}")
    with np.load(linkage_path) as archive:
        if "linkage" not in archive:
            raise ValueError(f"{linkage_path} no contiene 'linkage'")
        return np.asarray(archive["linkage"])


def build_assignments(
    *,
    linkage_path: Path,
    proximity_dir: Path,
    parquet_path: Path,
) -> pl.DataFrame:
    """Deriva k=7 y aplica el mapeo de cinco perfiles."""
    linkage_matrix = load_linkage(linkage_path)
    n_rows = linkage_matrix.shape[0] + 1
    index = load_index_frame(
        proximity_dir=proximity_dir,
        parquet_path=parquet_path,
        n_rows=n_rows,
    )
    labels_k7 = fcluster(linkage_matrix, t=K7, criterion="maxclust").astype(np.int32)
    perfiles = [k7_to_perfil(int(c)) for c in labels_k7]
    return index.with_columns(
        pl.Series("cluster_k7", labels_k7),
        pl.Series("perfil_agrupado", perfiles),
    )


def profile_by_group(assignments: pl.DataFrame, parquet_path: Path) -> pl.DataFrame:
    """Tabla de perfil por perfil_agrupado."""
    frame = pl.read_parquet(parquet_path).with_row_index("row_idx")
    feature_cols = [c for c in PROFILE_FEATURES if c in frame.columns]
    merged = assignments.join(frame.select(["row_idx", *feature_cols]), on="row_idx", how="left")

    summary_rows: list[dict[str, object]] = []
    for perfil in PROFILE_ORDER:
        subset = merged.filter(pl.col("perfil_agrupado") == perfil)
        if subset.is_empty():
            continue
        k7_parts = sorted(subset["cluster_k7"].unique().to_list())
        row: dict[str, object] = {
            "perfil_agrupado": perfil,
            "cluster_k7_componentes": ",".join(str(int(x)) for x in k7_parts),
            "n": subset.height,
            "pct_202105": float(subset.filter(pl.col("foto_mes") == 202105).height / subset.height),
            "pct_202106": float(subset.filter(pl.col("foto_mes") == 202106).height / subset.height),
        }
        for clase, count in (
            subset.group_by("clase_ternaria").len().sort("clase_ternaria").iter_rows()
        ):
            row[f"n_clase_{clase}"] = int(count)
        for feature in feature_cols:
            row[f"mean_{feature}"] = float(subset[feature].cast(pl.Float64).mean())
        summary_rows.append(row)
    return pl.DataFrame(summary_rows)


def write_plots(assignments: pl.DataFrame, profiles: pl.DataFrame, plots_dir: Path) -> None:
    """Gráficos de tamaño y composición mensual por perfil."""
    plots_dir.mkdir(parents=True, exist_ok=True)
    order = [p for p in PROFILE_ORDER if p in profiles["perfil_agrupado"].to_list()]

    fig, ax = plt.subplots(figsize=(9, 4))
    ns = [
        int(profiles.filter(pl.col("perfil_agrupado") == p).select("n").to_series()[0])
        for p in order
    ]
    ax.bar(order, ns, color="steelblue")
    ax.set_ylabel("n casos")
    ax.set_title("Tamaño por perfil agrupado (corte k=7 reclasificado)")
    fig.tight_layout()
    fig.savefig(plots_dir / "tamanos_perfil.png", dpi=120)
    plt.close(fig)

    mayo = [
        float(profiles.filter(pl.col("perfil_agrupado") == p).select("pct_202105").to_series()[0])
        for p in order
    ]
    junio = [
        float(profiles.filter(pl.col("perfil_agrupado") == p).select("pct_202106").to_series()[0])
        for p in order
    ]
    x = np.arange(len(order))
    width = 0.35
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(x - width / 2, mayo, width, label="202105")
    ax.bar(x + width / 2, junio, width, label="202106")
    ax.set_xticks(x)
    ax.set_xticklabels(order)
    ax.set_ylabel("fracción dentro del perfil")
    ax.set_title("Composición por foto_mes")
    ax.legend()
    fig.tight_layout()
    fig.savefig(plots_dir / "composicion_foto_mes.png", dpi=120)
    plt.close(fig)


def write_informe(
    *,
    out_dir: Path,
    profiles: pl.DataFrame,
    linkage_path: Path,
    parquet_path: Path,
) -> Path:
    """Informe Markdown con metodología y perfiles comparativos."""
    informe_path = out_dir / "informe_clusters_agrupados.md"
    preview = io.StringIO()
    profiles.write_csv(preview)

    interpretaciones: list[str] = []
    for row in profiles.iter_rows(named=True):
        perfil = row["perfil_agrupado"]
        n = row["n"]
        comp = row.get("cluster_k7_componentes", "")
        rent = row.get("mean_pct_mrentabilidad")
        rent_txt = f"{rent:.3f}" if rent is not None else "n/d"
        interpretaciones.append(
            f"- **{perfil}** (n={n}, k7={comp}): "
            f"mayo {row['pct_202105']:.1%}, junio {row['pct_202106']:.1%}; "
            f"mean pct_mrentabilidad={rent_txt}."
        )

    body = f"""# Informe de clústeres agrupados — cohorte BAJA (Miranda)

Generado: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")}

## Metodología

1. Se carga el enlace jerárquico ya calculado (`average linkage` sobre distancia RF).
2. Se aplica un corte fijo **k=7** (`fcluster`, `maxclust`).
3. Reclasificación analítica (no reoptimiza k):
   - se conservan por separado los clústeres k7 **1, 3, 6 y 7** → perfiles **C1, C3, C6, C7**;
   - se fusionan los clústeres k7 **2, 4 y 5** → perfil **C2_4_5**.

Fuente enlace: `{linkage_path}`
Cohorte: `{parquet_path}`

## Limitaciones

- El corte k=7 incluye subgrupos pequeños (p. ej. n=14–22); la fusión 2+4+5 los agrupa a propósito.
- No sustituye la partición automática k=2 del pipeline principal; es una lectura alternativa del dendrograma.

## Perfiles (tabla)

```
{preview.getvalue().strip()}
```

## Lectura comparativa

{chr(10).join(interpretaciones)}

## Artefactos

| Ruta | Descripción |
| --- | --- |
| `tablas/asignaciones_agrupadas.csv` | `cluster_k7` y `perfil_agrupado` por fila |
| `tablas/perfiles_agrupados.csv` | Resumen por perfil |
| `plots/tamanos_perfil.png` | Tamaños |
| `plots/composicion_foto_mes.png` | Mayo vs junio por perfil |
"""
    informe_path.write_text(body, encoding="utf-8")
    return informe_path


def run_grouped_report(
    *,
    hierarchical_dir: Path,
    proximity_dir: Path,
    parquet_path: Path,
    out_dir: Path,
) -> dict[str, Path]:
    """Genera asignaciones, perfiles, gráficos e informe agrupado."""
    linkage_path = hierarchical_dir / "linkage.npz"
    assignments = build_assignments(
        linkage_path=linkage_path,
        proximity_dir=proximity_dir,
        parquet_path=parquet_path,
    )
    profiles = profile_by_group(assignments, parquet_path)

    expected = set(PROFILE_ORDER)
    found = set(profiles["perfil_agrupado"].to_list())
    if found != expected:
        raise RuntimeError(f"Perfiles esperados {expected}, obtenidos {found}")
    if assignments.height != profiles["n"].sum():
        raise RuntimeError("Los conteos por perfil no suman el total de filas")

    tablas_dir = out_dir / "tablas"
    plots_dir = out_dir / "plots"
    tablas_dir.mkdir(parents=True, exist_ok=True)

    assign_path = tablas_dir / "asignaciones_agrupadas.csv"
    profile_path = tablas_dir / "perfiles_agrupados.csv"
    assignments.write_csv(assign_path)
    profiles.write_csv(profile_path)
    write_plots(assignments, profiles, plots_dir)
    informe_path = write_informe(
        out_dir=out_dir,
        profiles=profiles,
        linkage_path=linkage_path,
        parquet_path=parquet_path,
    )

    metadata = {
        "k7": K7,
        "merge_k7": sorted(MERGED_K7_CLUSTERS),
        "profiles": list(PROFILE_ORDER),
        "n": int(assignments.height),
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }
    metadata_path = out_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "assignments": assign_path,
        "profiles": profile_path,
        "informe": informe_path,
        "metadata": metadata_path,
        "plots_dir": plots_dir,
    }

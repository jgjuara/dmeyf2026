"""Clustering jerárquico (average linkage) sobre distancia RF precomputada."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
from scipy.spatial.distance import squareform
from sklearn.metrics import silhouette_score

INDEX_COLUMNS = ("numero_de_cliente", "foto_mes", "clase_ternaria")
PROFILE_FEATURES = (
    "cliente_vip",
    "internet",
    "pct_mrentabilidad",
    "pct_mcuentas_saldo",
    "pct_ctrx_quarter",
    "lag1_pct_mrentabilidad",
    "delta1_pct_mrentabilidad",
)


def load_distance_matrix(distance_path: Path) -> np.ndarray:
    """Carga y valida la matriz de distancia cuadrada."""
    if not distance_path.is_file():
        raise FileNotFoundError(f"No existe distancia: {distance_path}")
    with np.load(distance_path) as archive:
        if "distance" not in archive:
            raise ValueError(f"{distance_path} no contiene la clave 'distance'")
        distance = np.asarray(archive["distance"], dtype=np.float64)
    if distance.ndim != 2 or distance.shape[0] != distance.shape[1]:
        raise ValueError("La distancia debe ser una matriz cuadrada")
    if not np.all(np.isfinite(distance)):
        raise ValueError("La matriz de distancia contiene valores no finitos")
    if np.max(np.abs(distance - distance.T)) > 1e-5:
        raise ValueError("La matriz de distancia no es simétrica")
    if np.max(np.abs(np.diag(distance))) > 1e-5:
        raise ValueError("La diagonal de distancia debe ser cero")
    if np.any(distance < -1e-6) or np.any(distance > 1.0 + 1e-5):
        raise ValueError("La distancia debe estar en [0, 1]")
    return distance


def load_index_frame(
    *,
    proximity_dir: Path,
    parquet_path: Path,
    n_rows: int,
) -> pl.DataFrame:
    """Carga y valida el índice de filas contra la cohorte y la distancia."""
    index_path = proximity_dir / "indice_clientes.csv"
    if not parquet_path.is_file():
        raise FileNotFoundError(f"No existe parquet de cohorte: {parquet_path}")
    frame = pl.read_parquet(parquet_path)
    missing = [name for name in INDEX_COLUMNS if name not in frame.columns]
    if missing:
        raise ValueError(f"Faltan columnas en parquet: {', '.join(missing)}")
    if frame.height != n_rows:
        raise ValueError(
            f"El parquet tiene {frame.height} filas pero la distancia tiene {n_rows}"
        )
    if index_path.is_file():
        index = pl.read_csv(index_path)
        missing = [name for name in ("row_idx", *INDEX_COLUMNS) if name not in index.columns]
        if missing:
            raise ValueError(f"Faltan columnas en {index_path}: {', '.join(missing)}")
        index = index.sort("row_idx")
        if index.height != n_rows:
            raise ValueError(
                f"El índice tiene {index.height} filas pero la distancia tiene {n_rows}"
            )
        if not np.array_equal(index["row_idx"].to_numpy(), np.arange(n_rows)):
            raise ValueError("row_idx debe ser consecutivo y estar alineado con la distancia")
        for name in INDEX_COLUMNS:
            if not index[name].equals(frame[name]):
                raise ValueError(f"El índice no está alineado con el parquet en {name}")
        return index

    return frame.select(INDEX_COLUMNS).with_row_index("row_idx")


def evaluate_cuts(
    linkage_matrix: np.ndarray,
    distance: np.ndarray,
    *,
    k_min: int,
    k_max: int,
    min_cluster_size: int,
) -> pl.DataFrame:
    """Evalúa cortes por número de clústeres y silueta con distancia precomputada."""
    if k_min < 2:
        raise ValueError("k_min debe ser >= 2")
    if k_max < k_min:
        raise ValueError("k_max debe ser >= k_min")

    rows: list[dict[str, float | int | bool | None]] = []
    for k in range(k_min, k_max + 1):
        labels = fcluster(linkage_matrix, t=k, criterion="maxclust")
        _, counts = np.unique(labels, return_counts=True)
        min_size = int(counts.min())
        degenerate = min_size < min_cluster_size or len(counts) < 2
        silhouette: float | None
        if degenerate:
            silhouette = None
        else:
            silhouette = float(silhouette_score(distance, labels, metric="precomputed"))
        rows.append(
            {
                "k": k,
                "silhouette": silhouette,
                "min_cluster_size": min_size,
                "max_cluster_size": int(counts.max()),
                "degenerate": degenerate,
            }
        )
    return pl.DataFrame(rows)


def select_best_k(evaluation: pl.DataFrame) -> int:
    """Elige k con mayor silueta entre cortes no degenerados."""
    valid = evaluation.filter(~pl.col("degenerate") & pl.col("silhouette").is_not_null())
    if valid.is_empty():
        raise RuntimeError("Ningún corte cumple el tamaño mínimo de clúster")
    best = valid.sort("silhouette", descending=True).row(0, named=True)
    return int(best["k"])


def profile_clusters(assignments: pl.DataFrame, parquet_path: Path) -> pl.DataFrame:
    """Resume volumen, foto_mes, clase y medias de variables seleccionadas."""
    frame = pl.read_parquet(parquet_path).with_row_index("row_idx")
    feature_cols = [c for c in PROFILE_FEATURES if c in frame.columns]
    merged = assignments.join(frame.select(["row_idx", *feature_cols]), on="row_idx", how="left")

    summary_rows: list[dict[str, object]] = []
    for cluster_id in sorted(merged["cluster"].unique().to_list()):
        subset = merged.filter(pl.col("cluster") == cluster_id)
        row: dict[str, object] = {
            "cluster": int(cluster_id),
            "n": subset.height,
            "pct_202105": float(subset.filter(pl.col("foto_mes") == 202105).height / subset.height),
            "pct_202106": float(subset.filter(pl.col("foto_mes") == 202106).height / subset.height),
        }
        if "clase_ternaria" in subset.columns:
            for clase, count in (
                subset.group_by("clase_ternaria").len().sort("clase_ternaria").iter_rows()
            ):
                row[f"n_clase_{clase}"] = int(count)
        for feature in feature_cols:
            row[f"mean_{feature}"] = float(subset[feature].cast(pl.Float64).mean())
        summary_rows.append(row)
    return pl.DataFrame(summary_rows).sort("cluster")


def write_plots(
    *,
    linkage_matrix: np.ndarray,
    evaluation: pl.DataFrame,
    assignments: pl.DataFrame,
    plots_dir: Path,
    chosen_k: int,
) -> None:
    """Genera dendrograma truncado, tamaños y silueta vs k."""
    plots_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 5))
    dendrogram(
        linkage_matrix,
        truncate_mode="lastp",
        p=30,
        leaf_rotation=90,
        leaf_font_size=8,
        ax=ax,
        color_threshold=None,
    )
    ax.set_title("Dendrograma (average linkage, truncado)")
    ax.set_ylabel("distancia de enlace")
    fig.tight_layout()
    fig.savefig(plots_dir / "dendrograma_truncado.png", dpi=120)
    plt.close(fig)

    sizes = assignments.group_by("cluster").len().sort("cluster").rename({"len": "n"})
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(sizes["cluster"].to_list(), sizes["n"].to_list(), color="steelblue")
    ax.set_xlabel("clúster")
    ax.set_ylabel("n casos")
    ax.set_title(f"Tamaños de clúster (k={chosen_k})")
    fig.tight_layout()
    fig.savefig(plots_dir / "tamanos_cluster.png", dpi=120)
    plt.close(fig)

    valid = evaluation.filter(pl.col("silhouette").is_not_null())
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(valid["k"].to_list(), valid["silhouette"].to_list(), marker="o")
    ax.axvline(chosen_k, color="crimson", linestyle="--", label=f"k elegido={chosen_k}")
    ax.set_xlabel("k")
    ax.set_ylabel("silueta (precomputed)")
    ax.set_title("Silueta por número de clústeres")
    ax.legend()
    fig.tight_layout()
    fig.savefig(plots_dir / "silueta_vs_k.png", dpi=120)
    plt.close(fig)


def write_informe(
    *,
    out_dir: Path,
    metadata: dict[str, object],
    evaluation: pl.DataFrame,
    profiles: pl.DataFrame,
    chosen_k: int,
) -> Path:
    """Escribe informe Markdown con fuente, parámetros y lectura inicial."""
    informe_path = out_dir / "informe_cluster_jerarquico.md"
    best_row = evaluation.filter(pl.col("k") == chosen_k).row(0, named=True)
    sil = best_row["silhouette"]
    sil_txt = f"{sil:.4f}" if sil is not None else "n/d"
    preview = io.StringIO()
    profiles.head(10).write_csv(preview)

    body = f"""# Clustering jerárquico — cohorte BAJA (Miranda)

Generado: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")}

## Fuente

- Distancia RF: `{metadata["proximity_dir"]}/distancia.npz`
- Parquet: `{metadata["parquet_path"]}`
- Enlace: **average** (no Ward; disimilitud 1 − proximidad RF).

## Parámetros

- k evaluado: {metadata["k_min"]}–{metadata["k_max"]}
- tamaño mínimo de clúster: {metadata["min_cluster_size"]}
- **k elegido**: {chosen_k} (silueta = {sil_txt})

## Limitaciones

- Segmentación exploratoria basada en proximidad de hojas RF; no implica causalidad ni regla operativa.
- La silueta con matriz grande es costosa; el corte es un compromiso global, no validado externamente.

## Perfiles (resumen)

Ver `tablas/perfiles_cluster.csv`. Primeras filas:

```
{preview.getvalue().strip()}
```

## Artefactos

| Ruta | Descripción |
| --- | --- |
| `tablas/evaluacion_cortes.csv` | Silueta y tamaños por k |
| `tablas/asignaciones_cluster.csv` | Etiqueta por fila |
| `tablas/perfiles_cluster.csv` | Medias y conteos por clúster |
| `plots/*.png` | Dendrograma, tamaños, silueta |
"""
    informe_path.write_text(body, encoding="utf-8")
    return informe_path


def run_hierarchical(
    *,
    proximity_dir: Path,
    parquet_path: Path,
    out_dir: Path,
    k_min: int,
    k_max: int,
    min_cluster_size: int,
) -> dict[str, Path]:
    """Pipeline completo: enlace, selección de k, tablas, gráficos e informe."""
    distance_path = proximity_dir / "distancia.npz"
    distance = load_distance_matrix(distance_path)
    index = load_index_frame(
        proximity_dir=proximity_dir,
        parquet_path=parquet_path,
        n_rows=distance.shape[0],
    )

    linkage_matrix = linkage(squareform(distance, checks=False), method="average")
    evaluation = evaluate_cuts(
        linkage_matrix,
        distance,
        k_min=k_min,
        k_max=k_max,
        min_cluster_size=min_cluster_size,
    )
    chosen_k = select_best_k(evaluation)
    labels = fcluster(linkage_matrix, t=chosen_k, criterion="maxclust")
    assignments = index.with_columns(pl.Series("cluster", labels.astype(np.int32)))
    profiles = profile_clusters(assignments, parquet_path)

    tablas_dir = out_dir / "tablas"
    plots_dir = out_dir / "plots"
    tablas_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    eval_path = tablas_dir / "evaluacion_cortes.csv"
    assign_path = tablas_dir / "asignaciones_cluster.csv"
    profile_path = tablas_dir / "perfiles_cluster.csv"
    evaluation.write_csv(eval_path)
    assignments.write_csv(assign_path)
    profiles.write_csv(profile_path)

    linkage_path = out_dir / "linkage.npz"
    np.savez_compressed(linkage_path, linkage=linkage_matrix)

    write_plots(
        linkage_matrix=linkage_matrix,
        evaluation=evaluation,
        assignments=assignments,
        plots_dir=plots_dir,
        chosen_k=chosen_k,
    )

    metadata: dict[str, object] = {
        "n": int(distance.shape[0]),
        "chosen_k": chosen_k,
        "k_min": k_min,
        "k_max": k_max,
        "min_cluster_size": min_cluster_size,
        "linkage_method": "average",
        "proximity_dir": str(proximity_dir.resolve()),
        "parquet_path": str(parquet_path.resolve()),
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }
    metadata_path = out_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    informe_path = write_informe(
        out_dir=out_dir,
        metadata=metadata,
        evaluation=evaluation,
        profiles=profiles,
        chosen_k=chosen_k,
    )

    return {
        "evaluation": eval_path,
        "assignments": assign_path,
        "profiles": profile_path,
        "linkage": linkage_path,
        "metadata": metadata_path,
        "informe": informe_path,
        "plots_dir": plots_dir,
    }

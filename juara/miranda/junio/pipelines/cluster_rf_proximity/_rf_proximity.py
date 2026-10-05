"""Construye matrices de proximidad y distancia con un RF no supervisado."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import numpy as np
import polars as pl
import polars.selectors as cs
from sklearn import __version__ as sklearn_version
from sklearn.ensemble import RandomForestClassifier

EXCLUDED_COLUMNS = ("numero_de_cliente", "foto_mes", "clase_ternaria")
LABEL_COLUMN = "clase_ternaria"
BAJA12_CLASSES = frozenset({"BAJA+1", "BAJA+2"})
POSITIVE_CLASS_BAJA12 = "BAJA+2"
MIN_SKLEARN_VERSION = (1, 9, 1)
ForestMode = Literal["unsupervised", "supervised_baja12"]


def _version_tuple(version: str) -> tuple[int, ...]:
    """Obtiene los componentes numéricos principales de una versión."""
    parts: list[int] = []
    for part in version.split("."):
        digits = "".join(char for char in part if char.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def require_native_nan_support() -> None:
    """Aborta si la versión instalada no admite NaN en RandomForestClassifier."""
    if _version_tuple(sklearn_version) < MIN_SKLEARN_VERSION:
        required = ".".join(map(str, MIN_SKLEARN_VERSION))
        raise RuntimeError(
            f"scikit-learn>={required} es requerido para conservar NaN nativos; "
            f"instalado: {sklearn_version}"
        )


def load_cohort(parquet_path: Path) -> tuple[pl.DataFrame, np.ndarray, list[str]]:
    """Carga la cohorte, mantiene todas sus filas y transforma nulos a NaN de NumPy."""
    if not parquet_path.is_file():
        raise FileNotFoundError(f"No existe el parquet de cohorte: {parquet_path}")

    frame = pl.read_parquet(parquet_path)
    missing_columns = [name for name in EXCLUDED_COLUMNS if name not in frame.columns]
    if missing_columns:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing_columns)}")

    feature_names = [name for name in frame.select(cs.numeric()).columns if name not in EXCLUDED_COLUMNS]
    if not feature_names:
        raise ValueError("El parquet no contiene features numéricas")

    # NumPy representa los nulos numéricos como NaN; no se imputa ni se descarta ninguna fila.
    X = (
        frame.select(
            pl.col(name).cast(pl.Float32, strict=True).fill_null(float("nan"))
            for name in feature_names
        )
        .to_numpy()
        .astype(np.float32, copy=False)
    )
    return frame, X, feature_names


def synthetic_rows(X: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Permuta cada feature de forma independiente, incluidos sus NaN."""
    synthetic = np.empty_like(X)
    for column in range(X.shape[1]):
        synthetic[:, column] = rng.permutation(X[:, column])
    return synthetic


def fit_unsupervised_forest(
    X: np.ndarray,
    *,
    n_trees: int,
    min_samples_leaf: int,
    seed: int,
) -> RandomForestClassifier:
    """Ajusta un clasificador real-versus-sintético para inducir estructura no supervisada."""
    if n_trees < 1:
        raise ValueError("--n-trees debe ser mayor o igual a 1")
    if min_samples_leaf < 1:
        raise ValueError("--min-samples-leaf debe ser mayor o igual a 1")

    synthetic = synthetic_rows(X, np.random.default_rng(seed))
    X_train = np.concatenate((X, synthetic), axis=0)
    y_train = np.concatenate(
        (np.ones(X.shape[0], dtype=np.uint8), np.zeros(X.shape[0], dtype=np.uint8))
    )
    forest = RandomForestClassifier(
        n_estimators=n_trees,
        min_samples_leaf=min_samples_leaf,
        max_features="sqrt",
        n_jobs=-1,
        random_state=seed,
    )
    forest.fit(X_train, y_train)
    return forest


def baja12_labels_from_frame(frame: pl.DataFrame) -> tuple[np.ndarray, dict[str, int]]:
    """Codifica clase_ternaria en y binario (BAJA+1→0, BAJA+2→1) y devuelve conteos por clase."""
    if LABEL_COLUMN not in frame.columns:
        raise ValueError(f"Falta la columna de etiqueta: {LABEL_COLUMN}")

    labels = frame[LABEL_COLUMN].to_list()
    invalid = sorted({value for value in labels if value not in BAJA12_CLASSES})
    if invalid:
        raise ValueError(
            f"{LABEL_COLUMN} debe estar en {sorted(BAJA12_CLASSES)}; valores no permitidos: {invalid}"
        )

    class_counts = {"BAJA+1": 0, "BAJA+2": 0}
    y = np.empty(len(labels), dtype=np.uint8)
    for index, value in enumerate(labels):
        class_counts[value] += 1
        y[index] = 0 if value == "BAJA+1" else 1
    return y, class_counts


def fit_supervised_baja12_forest(
    X: np.ndarray,
    y: np.ndarray,
    *,
    n_trees: int,
    min_samples_leaf: int,
    seed: int,
) -> RandomForestClassifier:
    """Ajusta RandomForestClassifier solo sobre filas reales con etiqueta BAJA+1/BAJA+2."""
    if n_trees < 1:
        raise ValueError("--n-trees debe ser mayor o igual a 1")
    if min_samples_leaf < 1:
        raise ValueError("--min-samples-leaf debe ser mayor o igual a 1")
    if X.shape[0] != y.shape[0]:
        raise ValueError("X e y deben tener la misma cantidad de filas")

    forest = RandomForestClassifier(
        n_estimators=n_trees,
        min_samples_leaf=min_samples_leaf,
        max_features="sqrt",
        n_jobs=-1,
        random_state=seed,
    )
    forest.fit(X, y)
    return forest


def proximity_from_leaves(leaves: np.ndarray) -> np.ndarray:
    """Calcula fracción de hojas compartidas sin materializar un cubo fila×fila×árbol."""
    n_rows, n_trees = leaves.shape
    proximity = np.zeros((n_rows, n_rows), dtype=np.float32)
    increment = np.float32(1.0 / n_trees)
    block_size = 256

    for tree_leaves in leaves.T:
        order = np.argsort(tree_leaves, kind="stable")
        split_points = np.flatnonzero(np.diff(tree_leaves[order])) + 1
        for group in np.split(order, split_points):
            for start in range(0, len(group), block_size):
                block = group[start : start + block_size]
                proximity[np.ix_(block, group)] += increment

    np.fill_diagonal(proximity, np.float32(1.0))
    return proximity


def save_artifacts(
    *,
    frame: pl.DataFrame,
    proximity: np.ndarray,
    feature_names: list[str],
    parquet_path: Path,
    out_dir: Path,
    n_trees: int,
    min_samples_leaf: int,
    seed: int,
    forest_mode: ForestMode = "unsupervised",
    class_counts: dict[str, int] | None = None,
) -> dict[str, Path]:
    """Persiste el índice y las matrices de proximidad/distancia junto con sus metadatos."""
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "indice_clientes.csv"
    proximity_path = out_dir / "proximidad.npz"
    distance_path = out_dir / "distancia.npz"
    metadata_path = out_dir / "metadata.json"
    distance = np.float32(1.0) - proximity

    (
        frame.select(EXCLUDED_COLUMNS)
        .with_row_index("row_idx")
        .write_csv(index_path)
    )
    np.savez_compressed(proximity_path, proximity=proximity)
    np.savez_compressed(distance_path, distance=distance)
    metadata: dict[str, object] = {
        "n": int(proximity.shape[0]),
        "n_features": len(feature_names),
        "feature_names": feature_names,
        "n_trees": n_trees,
        "min_samples_leaf": min_samples_leaf,
        "seed": seed,
        "forest_mode": forest_mode,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "parquet_path": str(parquet_path.resolve()),
        "scikit_learn_version": sklearn_version,
    }
    if forest_mode == "supervised_baja12":
        metadata["label_column"] = LABEL_COLUMN
        metadata["positive_class"] = POSITIVE_CLASS_BAJA12
        if class_counts is not None:
            metadata["class_counts"] = class_counts
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "index": index_path,
        "proximity": proximity_path,
        "distance": distance_path,
        "metadata": metadata_path,
    }


def run_proximity(
    *,
    parquet_path: Path,
    out_dir: Path,
    n_trees: int,
    min_samples_leaf: int,
    seed: int,
    forest_mode: ForestMode = "unsupervised",
) -> dict[str, Path]:
    """Ejecuta carga, RF (no supervisado o BAJA+1/2) y persistencia de sus matrices."""
    require_native_nan_support()
    frame, X, feature_names = load_cohort(parquet_path)
    class_counts: dict[str, int] | None = None

    if forest_mode == "unsupervised":
        forest = fit_unsupervised_forest(
            X,
            n_trees=n_trees,
            min_samples_leaf=min_samples_leaf,
            seed=seed,
        )
    elif forest_mode == "supervised_baja12":
        y, class_counts = baja12_labels_from_frame(frame)
        forest = fit_supervised_baja12_forest(
            X,
            y,
            n_trees=n_trees,
            min_samples_leaf=min_samples_leaf,
            seed=seed,
        )
    else:
        raise ValueError(f"forest_mode no soportado: {forest_mode!r}")

    leaves = forest.apply(X)
    proximity = proximity_from_leaves(leaves)
    return save_artifacts(
        frame=frame,
        proximity=proximity,
        feature_names=feature_names,
        parquet_path=parquet_path,
        out_dir=out_dir,
        n_trees=n_trees,
        min_samples_leaf=min_samples_leaf,
        seed=seed,
        forest_mode=forest_mode,
        class_counts=class_counts,
    )

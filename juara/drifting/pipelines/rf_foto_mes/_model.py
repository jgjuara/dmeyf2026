"""RF multiclass foto_mes: entrenamiento, métricas, importancia por permutación."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from sklearn import __version__ as sklearn_version
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split

from _load import LABEL_COLUMN, load_dataset

MIN_SKLEARN_VERSION = (1, 9, 1)


def _version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in version.split("."):
        digits = "".join(char for char in part if char.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def require_native_nan_support() -> None:
    if _version_tuple(sklearn_version) < MIN_SKLEARN_VERSION:
        required = ".".join(map(str, MIN_SKLEARN_VERSION))
        raise RuntimeError(
            f"scikit-learn>={required} requerido para NaN nativos; instalado: {sklearn_version}"
        )


def _baseline_metrics(y: np.ndarray) -> dict[str, float]:
    classes, counts = np.unique(y, return_counts=True)
    n = len(y)
    n_classes = len(classes)
    majority_acc = float(counts.max() / n)
    uniform_acc = 1.0 / n_classes if n_classes else float("nan")
    return {
        "n_samples": int(n),
        "n_classes": int(n_classes),
        "majority_class_accuracy": majority_acc,
        "uniform_random_accuracy": uniform_acc,
    }


def _class_counts(frame: pl.DataFrame) -> dict[str, int]:
    if LABEL_COLUMN not in frame.columns:
        return {}
    rows = frame.group_by(LABEL_COLUMN).len().sort(LABEL_COLUMN).iter_rows()
    return {str(k): int(v) for k, v in rows}


def fit_rf(
    X_train: np.ndarray,
    y_train: np.ndarray,
    *,
    n_trees: int,
    min_samples_leaf: int,
    seed: int,
    oob_score: bool = False,
) -> RandomForestClassifier:
    forest = RandomForestClassifier(
        n_estimators=n_trees,
        min_samples_leaf=min_samples_leaf,
        max_features="sqrt",
        n_jobs=-1,
        random_state=seed,
        oob_score=oob_score,
    )
    forest.fit(X_train, y_train)
    return forest


def _stratified_subsample(
    X: np.ndarray,
    y: np.ndarray,
    max_samples: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    if X.shape[0] <= max_samples:
        return X, y
    idx = np.arange(X.shape[0])
    train_idx, _ = train_test_split(
        idx,
        train_size=max_samples,
        stratify=y,
        random_state=seed,
    )
    return X[train_idx], y[train_idx]


def run_pipeline(
    *,
    parquet_path: Path,
    out_dir: Path,
    test_size: float,
    seed: int,
    n_trees: int,
    min_samples_leaf: int,
    importance_max_samples: int | None,
    oob_score: bool,
) -> dict[str, Path]:
    require_native_nan_support()
    out_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    frame, X, y, feature_names = load_dataset(parquet_path)
    if len(feature_names) != 152:
        print(f"aviso: n_features={len(feature_names)} (esperado ~152)")

    baseline_full = _baseline_metrics(y)
    counts_full = _class_counts(frame)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        stratify=y,
        random_state=seed,
    )

    forest = fit_rf(
        X_train,
        y_train,
        n_trees=n_trees,
        min_samples_leaf=min_samples_leaf,
        seed=seed,
        oob_score=oob_score,
    )

    y_pred = forest.predict(X_test)
    classes = sorted(np.unique(y).tolist(), key=lambda v: (isinstance(v, str), v))

    acc = float(accuracy_score(y_test, y_pred))
    bal_acc = float(balanced_accuracy_score(y_test, y_pred))
    macro_f1 = float(f1_score(y_test, y_pred, average="macro"))

    cm = confusion_matrix(y_test, y_pred, labels=classes)
    cm_df = pl.DataFrame(
        cm,
        schema=[f"pred_{c}" for c in classes],
    ).with_columns(pl.Series("true_foto_mes", [str(c) for c in classes]))

    metricas: dict[str, Any] = {
        "holdout": {
            "accuracy": acc,
            "balanced_accuracy": bal_acc,
            "macro_f1": macro_f1,
            "test_size": test_size,
            "n_train": int(X_train.shape[0]),
            "n_test": int(X_test.shape[0]),
        },
        "baseline_full_dataset": baseline_full,
        "chance_uniform_1_over_k": baseline_full["uniform_random_accuracy"],
    }
    if oob_score:
        metricas["train_oob_score"] = float(forest.oob_score_)

    metricas_path = out_dir / "metricas.json"
    metricas_path.write_text(json.dumps(metricas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    cm_path = out_dir / "confusion_matrix.csv"
    cm_df.write_csv(cm_path)

    imp_n = importance_max_samples
    X_imp, y_imp = X_test, y_test
    if imp_n is not None and X_test.shape[0] > imp_n:
        X_imp, y_imp = _stratified_subsample(X_test, y_test, imp_n, seed)

    perm = permutation_importance(
        forest,
        X_imp,
        y_imp,
        n_repeats=5,
        random_state=seed,
        n_jobs=-1,
        scoring="balanced_accuracy",
    )
    imp_rows = sorted(
        zip(feature_names, perm.importances_mean, perm.importances_std, strict=True),
        key=lambda t: t[1],
        reverse=True,
    )
    imp_df = pl.DataFrame(
        {
            "feature": [r[0] for r in imp_rows],
            "importance_mean": [float(r[1]) for r in imp_rows],
            "importance_std": [float(r[2]) for r in imp_rows],
        }
    )
    imp_path = out_dir / "importancia_permutacion.csv"
    imp_df.write_csv(imp_path)

    metadata: dict[str, Any] = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "parquet_path": str(parquet_path.resolve()),
        "out_dir": str(out_dir.resolve()),
        "label_column": LABEL_COLUMN,
        "n_features": len(feature_names),
        "feature_names_count": len(feature_names),
        "n_rows": int(frame.height),
        "foto_mes_counts": counts_full,
        "hyperparameters": {
            "n_estimators": n_trees,
            "min_samples_leaf": min_samples_leaf,
            "max_features": "sqrt",
            "random_state": seed,
        },
        "split": {"test_size": test_size, "stratify": LABEL_COLUMN, "random_state": seed},
        "permutation_importance": {
            "scoring": "balanced_accuracy",
            "n_repeats": 5,
            "importance_max_samples": importance_max_samples,
            "n_samples_used": int(X_imp.shape[0]),
        },
        "scikit_learn_version": sklearn_version,
    }
    meta_path = out_dir / "metadata.json"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _plot_confusion_matrix(cm, classes, plots_dir / "confusion_matrix.png")
    _write_informe(
        out_dir / "informe_rf_foto_mes.md",
        counts_full=counts_full,
        metricas=metricas,
        cm_df=cm_df,
        top_importance=imp_df.head(30),
        n_features=len(feature_names),
        hyper=metadata["hyperparameters"],
        split=metadata["split"],
        perm_meta=metadata["permutation_importance"],
    )

    return {
        "metricas": metricas_path,
        "confusion_matrix": cm_path,
        "importancia": imp_path,
        "metadata": meta_path,
        "informe": out_dir / "informe_rf_foto_mes.md",
        "plot": plots_dir / "confusion_matrix.png",
    }


def _df_md_table(df: pl.DataFrame) -> str:
    cols = df.columns
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    rows = []
    for row in df.iter_rows():
        cells = ["" if v is None else str(v) for v in row]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, sep, *rows])


def _plot_confusion_matrix(cm: np.ndarray, classes: list, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(classes)), [str(c) for c in classes], rotation=45, ha="right")
    ax.set_yticks(range(len(classes)), [str(c) for c in classes])
    ax.set_xlabel("Predicho")
    ax.set_ylabel("Verdadero foto_mes")
    ax.set_title("Matriz de confusión (holdout)")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", color="black", fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _write_informe(
    path: Path,
    *,
    counts_full: dict[str, int],
    metricas: dict[str, Any],
    cm_df: pl.DataFrame,
    top_importance: pl.DataFrame,
    n_features: int,
    hyper: dict[str, Any],
    split: dict[str, Any],
    perm_meta: dict[str, Any],
) -> None:
    hold = metricas["holdout"]
    base = metricas["baseline_full_dataset"]
    lines = [
        "# Informe: RF multiclass `foto_mes` (drifting)",
        "",
        "## Diseño",
        "",
        "- **Datos:** `dataset_nocont_rank.parquet` (nocontinuas + rankings, todas las filas y clases).",
        f"- **Predictores:** {n_features} columnas (`nocontinuas_base` + `pct_*`, sin lag/delta).",
        f"- **Etiqueta:** `foto_mes` (multiclass).",
        f"- **Modelo:** RandomForestClassifier, `n_estimators={hyper['n_estimators']}`, "
        f"`min_samples_leaf={hyper['min_samples_leaf']}`, `max_features=sqrt`, `random_state={hyper['random_state']}`.",
        f"- **Partición:** holdout estratificado {int((1 - split['test_size']) * 100)}/{int(split['test_size'] * 100)} "
        f"(seed={split['random_state']}).",
        "",
        "## Conteos por `foto_mes` (dataset completo)",
        "",
    ]
    for mes, n in sorted(counts_full.items(), key=lambda x: x[0]):
        lines.append(f"- {mes}: {n}")
    lines.extend(
        [
            "",
            "## Métricas holdout vs baseline",
            "",
            f"| Métrica | Valor |",
            f"| --- | --- |",
            f"| Accuracy | {hold['accuracy']:.4f} |",
            f"| Balanced accuracy | {hold['balanced_accuracy']:.4f} |",
            f"| Macro-F1 | {hold['macro_f1']:.4f} |",
            f"| Baseline clase mayoritaria (dataset completo) | {base['majority_class_accuracy']:.4f} |",
            f"| Azar uniforme (1/k, k={base['n_classes']}) | {base['uniform_random_accuracy']:.4f} |",
            "",
            "Un accuracy holdout claramente por encima de 1/k sugiere que las features portan estructura "
            "asociada al mes calendario; no implica causalidad ni estabilidad fuera del panel.",
            "",
            "## Matriz de confusión",
            "",
            "Ver `confusion_matrix.csv` y `plots/confusion_matrix.png`.",
            "",
            _df_md_table(cm_df),
            "",
            "",
            "## Top permutation importance (holdout)",
            "",
            f"Muestra usada: {perm_meta['n_samples_used']} filas "
            f"(máx. configurado: {perm_meta['importance_max_samples']}).",
            "",
            _df_md_table(top_importance),
            "",
            "",
            "Muchas variables `pct_*` reflejan posición relativa intra-mes; un cambio de mezcla de clientes "
            "entre meses puede elevar su importancia sin indicar un nivel absoluto estable.",
            "",
            "## Conclusión exploratoria",
            "",
        ]
    )
    chance = base["uniform_random_accuracy"]
    if hold["accuracy"] > chance + 0.05:
        lines.append(
            "La separación holdout supera el azar uniforme de forma marcada: hay señal temporal "
            "en nocontinuas + rankings del mes."
        )
    elif hold["accuracy"] > chance + 0.01:
        lines.append(
            "La separación holdout es moderadamente superior al azar; conviene revisar la matriz "
            "de confusión por meses adyacentes."
        )
    else:
        lines.append(
            "La separación holdout es débil respecto al azar uniforme; el drift estructural en estas "
            "features no se manifiesta como clasificación fácil de mes."
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")

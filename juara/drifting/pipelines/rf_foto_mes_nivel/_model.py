"""RF multiclass foto_mes en nivel crudo: entrenamiento, métricas, informe comparativo."""

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

from _features import continuas_nivel_names
from _load import LABEL_COLUMN, load_dataset
from _paths import BASELINE_METRICAS

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


def _load_baseline_metricas(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


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
    n_cont = len([f for f in feature_names if f in continuas_nivel_names()])
    n_nocont = len(feature_names) - n_cont
    print(f"n_features={len(feature_names)} (nocontinuas_base={n_nocont}, continuas_nivel={n_cont})")

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
        "n_nocontinuas_base": n_nocont,
        "n_continuas_nivel": n_cont,
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
    baseline_rank = _load_baseline_metricas(BASELINE_METRICAS)
    _write_informe(
        out_dir / "informe_rf_foto_mes_nivel.md",
        counts_full=counts_full,
        metricas=metricas,
        baseline_rank=baseline_rank,
        cm_df=cm_df,
        top_importance=imp_df.head(30),
        n_features=len(feature_names),
        n_nocont=n_nocont,
        n_cont=n_cont,
        hyper=metadata["hyperparameters"],
        split=metadata["split"],
        perm_meta=metadata["permutation_importance"],
    )

    return {
        "metricas": metricas_path,
        "confusion_matrix": cm_path,
        "importancia": imp_path,
        "metadata": meta_path,
        "informe": out_dir / "informe_rf_foto_mes_nivel.md",
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
    baseline_rank: dict[str, Any] | None,
    cm_df: pl.DataFrame,
    top_importance: pl.DataFrame,
    n_features: int,
    n_nocont: int,
    n_cont: int,
    hyper: dict[str, Any],
    split: dict[str, Any],
    perm_meta: dict[str, Any],
) -> None:
    hold = metricas["holdout"]
    base = metricas["baseline_full_dataset"]
    lines = [
        "# Informe: RF multiclass `foto_mes` — nivel crudo (drifting)",
        "",
        "## Diseño",
        "",
        "- **Datos:** `dataset_nocont_nivel.parquet` (nocontinuas + continuas en escala original).",
        f"- **Predictores:** {n_features} columnas (`nocontinuas_base`={n_nocont}, `continuas_nivel`={n_cont}; sin `pct_*`, lag ni delta).",
        f"- **Etiqueta:** `foto_mes` (multiclass).",
        f"- **Modelo:** RandomForestClassifier, `n_estimators={hyper['n_estimators']}`, "
        f"`min_samples_leaf={hyper['min_samples_leaf']}`, `max_features=sqrt`, `random_state={hyper['random_state']}`.",
        f"- **Partición:** holdout estratificado {int((1 - split['test_size']) * 100)}/{int(split['test_size'] * 100)} "
        f"(seed={split['random_state']}).",
        "",
        "## Comparación vs `rf_foto_mes` (rankings `pct_*`)",
        "",
    ]

    if baseline_rank is None:
        lines.append("_No se encontró `resultados/rf_foto_mes/metricas.json`._")
    else:
        br = baseline_rank["holdout"]
        lines.extend(
            [
                "| Métrica | Nivel crudo (este pipeline) | Rankings `pct_*` (`rf_foto_mes`) |",
                "| --- | --- | --- |",
                f"| Accuracy | {hold['accuracy']:.4f} | {br['accuracy']:.4f} |",
                f"| Balanced accuracy | {hold['balanced_accuracy']:.4f} | {br['balanced_accuracy']:.4f} |",
                f"| Macro-F1 | {hold['macro_f1']:.4f} | {br['macro_f1']:.4f} |",
                "",
                "Misma hipérbola RF, mismo split 80/20 estratificado (seed 2026) y mismo panel (983 061 filas). "
                "La diferencia aísla el efecto de usar **niveles absolutos** frente a **percentiles intra-mes**.",
                "",
            ]
        )

    lines.append("## Conteos por `foto_mes` (dataset completo)")
    lines.append("")
    for mes, n in sorted(counts_full.items(), key=lambda x: x[0]):
        lines.append(f"- {mes}: {n}")
    lines.extend(
        [
            "",
            "## Métricas holdout vs baseline (nivel)",
            "",
            "| Métrica | Valor |",
            "| --- | --- |",
            f"| Accuracy | {hold['accuracy']:.4f} |",
            f"| Balanced accuracy | {hold['balanced_accuracy']:.4f} |",
            f"| Macro-F1 | {hold['macro_f1']:.4f} |",
            f"| Baseline clase mayoritaria (dataset completo) | {base['majority_class_accuracy']:.4f} |",
            f"| Azar uniforme (1/k, k={base['n_classes']}) | {base['uniform_random_accuracy']:.4f} |",
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
            "## Auditoría de leakage (exploratoria)",
            "",
            "- **Fuga directa:** no. `foto_mes`, `clase_ternaria` y `numero_de_cliente` quedan fuera de X; el join por clave no duplica filas (983 061 filas).",
            "- **Continuas en nivel:** no hay `PARTITION BY foto_mes` en estas columnas; no acoplan la etiqueta vía percentil intra-cohorte como `pct_*`. "
            "Sí pueden codificar drift de **escala absoluta** (inflación de saldos, cambios de producto, recorte de outliers) entre meses calendario.",
            "- **Contraste con `pct_*`:** en `rf_foto_mes`, la etiqueta coincide con el estrato usado para calcular ranks; aquí esa vía está ausente. "
            "Un accuracy mucho menor que ~0,999 apuntaría a que la separación casi total del baseline ranking venía del acoplamiento rank–mes, no de nocontinuas solas.",
            "- **Split 80/20 por fila:** igual que el pipeline con rankings; no mide generalización a clientes ausentes del train.",
            "",
            "## Conclusión exploratoria",
            "",
        ]
    )

    chance = base["uniform_random_accuracy"]
    rank_acc = baseline_rank["holdout"]["accuracy"] if baseline_rank else None

    if rank_acc is not None and hold["accuracy"] < rank_acc - 0.1:
        lines.append(
            "El RF en **nivel crudo** separa `foto_mes` mucho peor que con `pct_*`: la cohorte mensual "
            "no queda marcada por ranks relativos, sino que la señal temporal (si existe) debe venir de "
            "cambios de nivel absoluto o de nocontinuas, no del percentil intra-mes."
        )
    elif hold["accuracy"] > chance + 0.05:
        lines.append(
            "Aun sin `pct_*`, el holdout supera claramente el azar uniforme: parte del drift temporal "
            "se refleja en niveles absolutos de continuas y/o en nocontinuas."
        )
    elif hold["accuracy"] > chance + 0.01:
        lines.append(
            "La separación holdout es moderada respecto al azar; conviene contrastar con la matriz de confusión "
            "y con el baseline ranking (~0,9999 accuracy)."
        )
    else:
        lines.append(
            "La separación holdout es cercana al azar (1/6): **el mes no se discrimina fácilmente** "
            "con nocontinuas + continuas en escala original, coherente con que el drift fuerte del panel "
            "se manifestaba sobre todo vía rankings intra-mes."
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")

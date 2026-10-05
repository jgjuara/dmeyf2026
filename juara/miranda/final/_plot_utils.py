"""Utilidades matplotlib."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def savefig(path: Path, title: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if title:
        plt.title(title, fontsize=11)
    plt.tight_layout()
    plt.savefig(path, dpi=120, bbox_inches="tight")
    plt.close()

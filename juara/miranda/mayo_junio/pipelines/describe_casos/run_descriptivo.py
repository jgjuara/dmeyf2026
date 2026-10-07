"""Genera tablas, gráficos e informe markdown del dataset mayo–junio."""

from __future__ import annotations

from _lib import run
from _paths import INFORME_MD, PLOTS_DIR, TABLAS_DIR


def main() -> None:
    run()
    print(f"tablas: {TABLAS_DIR}")
    print(f"plots: {PLOTS_DIR}")
    print(f"informe: {INFORME_MD}")


if __name__ == "__main__":
    main()

"""Ejecuta en secuencia la cadena FE v1 (última versión de cada paso).

Rama activa v1; delta2 materializa solo el paso v2 (lag1 − lag2). No ejecuta
builders legacy (rankings/continuas v2, delta2 sin sufijo, delta2_v1).

Desde juara/:

    uv run fe/run_fe_v1_latest.py
    uv run fe/run_fe_v1_latest.py --download
    uv run fe/run_fe_v1_latest.py --from 3
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

FE_DIR = Path(__file__).resolve().parent
JUARA_DIR = FE_DIR.parent

BUILDERS: tuple[str, ...] = (
    "build_competencia_01_parquet_v1.py",
    "build_competencia_01_clean_v1.py",
    "build_competencia_nocontinuas_v1.py",
    "build_competencia_continuas_v1.py",
    "build_rankings_v1.py",
    "build_competencia_nocontinuas_v1_lag1.py",
    "build_competencia_nocontinuas_v1_lag2.py",
    "build_competencia_continuas_v1_lag1.py",
    "build_competencia_continuas_v1_lag2.py",
    "build_competencia_continuas_v1_delta1.py",
    "build_rankings_v1_lag1.py",
    "build_rankings_v1_lag2.py",
    "build_rankings_v1_delta1.py",
    "build_competencia_continuas_v1_delta2_v2.py",
    "build_rankings_v1_delta2_v2.py",
)

DOWNLOAD_SCRIPT = "download_competencia_crudo.py"


def _run_script(script: str) -> int:
    path = FE_DIR / script
    if not path.is_file():
        print(f"script inexistente: {path}", file=sys.stderr)
        return 1
    return subprocess.run(
        ["uv", "run", f"fe/{script}"],
        cwd=JUARA_DIR,
        check=False,
    ).returncode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--download",
        action="store_true",
        help="Ejecutar download_competencia_crudo.py antes de los builders.",
    )
    parser.add_argument(
        "--from",
        dest="from_step",
        type=int,
        metavar="N",
        default=1,
        help="Primer índice de BUILDERS a ejecutar (1-based).",
    )
    args = parser.parse_args()

    if args.from_step < 1 or args.from_step > len(BUILDERS):
        raise SystemExit(f"--from debe estar entre 1 y {len(BUILDERS)}")

    queue: list[str] = []
    if args.download:
        queue.append(DOWNLOAD_SCRIPT)
    queue.extend(BUILDERS[args.from_step - 1 :])

    total = len(queue)
    for i, script in enumerate(queue, start=1):
        print(f"--- [{i}/{total}] fe/{script} ---", flush=True)
        code = _run_script(script)
        if code != 0:
            raise SystemExit(code)

    print(f"cadena FE v1 completada ({total} pasos).")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

#!/usr/bin/env python3
"""Orquesta el informe comparativo BO 02 (CV5) vs 03 (CV3)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args(argv: list[str]) -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    z494 = here.parent
    parser = argparse.ArgumentParser(description="Pipeline informe BO 02 vs 03.")
    parser.add_argument("--bo-02", type=Path, default=z494 / "02/resultados/HT4940/BO_log.txt")
    parser.add_argument("--bo-03", type=Path, default=z494 / "03/resultados/HT4940/BO_log.txt")
    parser.add_argument(
        "--perfil-02",
        type=Path,
        default=z494 / "02/resultados/estudio/perfil_surrogate",
    )
    parser.add_argument(
        "--perfil-03",
        type=Path,
        default=z494 / "03/resultados/estudio/perfil_surrogate",
    )
    parser.add_argument("--out-dir", type=Path, default=here / "estudio")
    return parser.parse_args(argv)


def require(path: Path, label: str) -> None:
    if not path.is_file() and not path.is_dir():
        print(f"Falta {label}: {path}", file=sys.stderr)
        raise SystemExit(1)


def run_step(cmd: list[str]) -> None:
    print(f">>> {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    here = Path(__file__).resolve().parent
    py = sys.executable

    require(args.bo_02.resolve(), "BO_log 02")
    require(args.bo_03.resolve(), "BO_log 03")
    require(args.perfil_02.resolve(), "perfil_surrogate 02")
    require(args.perfil_03.resolve(), "perfil_surrogate 03")

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    common = [
        "--bo-02",
        str(args.bo_02.resolve()),
        "--bo-03",
        str(args.bo_03.resolve()),
        "--out-dir",
        str(out_dir),
    ]

    run_step([py, str(here / "bo_comparar_objetivo.py"), *common])
    run_step([py, str(here / "bo_comparar_trayectoria.py"), *common])
    run_step(
        [
            py,
            str(here / "bo_comparar_regiones.py"),
            *common,
            "--perfil-02",
            str(args.perfil_02.resolve()),
            "--perfil-03",
            str(args.perfil_03.resolve()),
        ]
    )
    run_step([py, str(here / "generar_informe_md.py"), "--common-dir", str(here), "--estudio-dir", str(out_dir)])

    informe = here / "INFORME_BO_CV3_VS_CV5.md"
    if not informe.is_file():
        print("No se genero el informe.", file=sys.stderr)
        return 1
    print(f"Listo: {informe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

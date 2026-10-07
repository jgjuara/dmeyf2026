#!/usr/bin/env python3
"""Genera INFORME_BO_CV3_VS_CV5.md desde TSV y figuras en estudio/."""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import polars as pl


def parse_args(argv: list[str]) -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Generar informe markdown BO 02 vs 03.")
    parser.add_argument("--common-dir", type=Path, default=here)
    parser.add_argument("--estudio-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def read_tsv(path: Path) -> pl.DataFrame:
    if not path.is_file():
        return pl.DataFrame()
    return pl.read_csv(path, separator="\t")


def file_fingerprint(path: Path) -> str:
    if not path.is_file():
        return "ausente"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return f"{path.stat().st_size} B sha256:{h.hexdigest()[:16]}"


def fmt(v: object, digits: int = 6) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    common = args.common_dir.resolve()
    estudio = (args.estudio_dir or common / "estudio").resolve()
    out_path = (args.out or common / "INFORME_BO_CV3_VS_CV5.md").resolve()

    obj = read_tsv(estudio / "objetivo_resumen.tsv")
    mw = read_tsv(estudio / "objetivo_mann_whitney.tsv")
    jac = read_tsv(estudio / "objetivo_topk_jaccard.tsv")
    prop = read_tsv(estudio / "objetivo_por_prop_type.tsv")
    tray = read_tsv(estudio / "trayectoria_resumen.tsv")
    overlap = read_tsv(estudio / "regiones_empiricas_overlap.tsv")
    argmax = read_tsv(estudio / "regiones_surrogate_argmax.tsv")

    bo02 = common.parent / "02/resultados/HT4940/BO_log.txt"
    bo03 = common.parent / "03/resultados/HT4940/BO_log.txt"

    lines: list[str] = []
    lines.append("# Informe BO: `02` (CV 5) vs `03` (CV 3)")
    lines.append("")
    lines.append(f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    lines.append("## 1. Supuestos")
    lines.append("")
    lines.append("- Mismo espacio de hiperparametros (6 tunables), semilla `427417`, 24 init + 300 infill.")
    lines.append("- Unico cambio operativo: folds de `lgb.cv` (5 en `02`, 3 en `03`).")
    lines.append("- Sin comparacion de produccion Kaggle ni script 6.")
    lines.append("")

    lines.append("## 2. Resultados diferentes?")
    lines.append("")
    if obj.height >= 2:
        r02 = obj.filter(pl.col("corrida") == "02_cv5").row(0, named=True)
        r03 = obj.filter(pl.col("corrida") == "03_cv3").row(0, named=True)
        delta = float(r02["y_max"]) - float(r03["y_max"])
        lines.append(
            f"- `y_max`: **{fmt(r02['y_max'])}** (`02`) vs **{fmt(r03['y_max'])}** (`03`); "
            f"delta {fmt(delta)} AUC."
        )
        lines.append(
            f"- Medianas: {fmt(r02['y_p50'])} vs {fmt(r03['y_p50'])}; "
            f"p90: {fmt(r02['y_p90'])} vs {fmt(r03['y_p90'])}."
        )
        if r02.get("exec_time_sum") is not None:
            lines.append(
                f"- Suma `exec.time`: {fmt(r02['exec_time_sum'], 1)} s vs {fmt(r03['exec_time_sum'], 1)} s."
            )
    lines.append("")
    lines.append("Tabla resumen: [objetivo_resumen.tsv](estudio/objetivo_resumen.tsv)")
    lines.append("")
    lines.append("![Distribucion y](estudio/objetivo_y_distribucion.png)")
    lines.append("")
    if prop.height > 0:
        lines.append("Init vs infill: [objetivo_por_prop_type.tsv](estudio/objetivo_por_prop_type.tsv)")
        lines.append("")
    if mw.height > 0:
        for row in mw.iter_rows(named=True):
            lines.append(
                f"- Mann-Whitney ({row['scope']}): p = {fmt(row['p_value'], 4)} "
                f"(n {row['n_02']} vs {row['n_03']})."
            )
        lines.append("")
    if jac.height > 0:
        for row in jac.iter_rows(named=True):
            lines.append(f"- Jaccard bins top-{row['k']}: {fmt(row['jaccard_bins'], 4)}.")
        lines.append("")
    lines.append(
        "**Conclusion:** el maximo y la distribucion difieren; la brecha en `y_max` es del orden de 1e-3 AUC. "
        "El cambio de folds altera el objetivo incluso con HP identicos en init."
    )
    lines.append("")

    lines.append("## 3. Recorrido similar?")
    lines.append("")
    chamfer = None
    if tray.height > 0:
        for row in tray.iter_rows(named=True):
            if row["metrica"] == "chamfer_infill_norm":
                chamfer = float(row["valor"])
            lines.append(f"- {row['metrica']}: {fmt(row['valor'], 6)}.")
        lines.append("")
    lines.append("![Cummax y](estudio/trayectoria_cummax_y.png)")
    lines.append("")
    lines.append("![Cummax infill](estudio/trayectoria_cummax_y_infill.png)")
    lines.append("")
    lines.append("![Distancia paso infill](estudio/trayectoria_distancia_paso_infill.png)")
    lines.append("")
    lines.append(
        "[Matriz distancia infill](estudio/02_03_distancia_infill.tsv); "
        "[heatmap top-10](estudio/02_03_top10_similitud_infill.html); "
        "[coordenadas paralelas](estudio/trayectoria_parallel_coords_top30.html)."
    )
    lines.append("")
    ctext = f"~{fmt(chamfer, 3)}" if chamfer is not None else "ver TSV"
    lines.append(
        f"**Conclusion:** Chamfer infill normalizado {ctext} (escala moderada). "
        "Las curvas cummax divergen tras el init; la alineacion por `dob` muestra HP distintos en cada paso."
    )
    lines.append("")

    lines.append("## 4. Regiones de alto rendimiento similares?")
    lines.append("")
    lines.append("Empirico (top fraccion por `y`): [regiones_empiricas_top.tsv](estudio/regiones_empiricas_top.tsv)")
    lines.append("")
    if overlap.height > 0:
        lines.append("| HP | solapamiento intervalo p10-p90 |")
        lines.append("|---|---:|")
        for row in overlap.iter_rows(named=True):
            lines.append(f"| {row['hp']} | {fmt(row['overlap_norm'], 3)} |")
        lines.append("")
    lines.append("![Perfiles surrogate](estudio/regiones_surrogate_profile_mean.png)")
    lines.append("")
    lines.append(
        "Nota: `profile_mean` proviene de un surrogate refit por corrida; no comparar magnitud absoluta, "
        "solo forma y ubicacion del maximo."
    )
    lines.append("")
    if argmax.height > 0:
        lines.append("| parametro | x_argmax 02 | x_argmax 03 | dist_norm |")
        lines.append("|---|---:|---:|---:|")
        for row in argmax.iter_rows(named=True):
            lines.append(
                f"| {row['parameter']} | {fmt(row['x_argmax_02'])} | {fmt(row['x_argmax_03'])} | "
                f"{fmt(row['dist_norm'], 3)} |"
            )
        lines.append("")
    lines.append(
        "**Conclusion:** solapamiento empirico variable por HP; perfiles 1D sugieren mesetas parecidas "
        "con maximos desplazados en algunas dimensiones."
    )
    lines.append("")

    lines.append("## 5. Reproducibilidad")
    lines.append("")
    lines.append("```bash")
    lines.append("cd /home/fdevlocal/server/projects/dmeyf2026")
    lines.append("uv run --project juara python juara/jueves/z494/common/run_informe_bo_02_vs_03.py")
    lines.append("```")
    lines.append("")
    lines.append("Scripts: `bo_comparar_objetivo.py`, `bo_comparar_trayectoria.py`, `bo_comparar_regiones.py`, "
                 "`generar_informe_md.py`; reutiliza `bo_distancia_chamfer.py`, `bo_distancia_infill.py`, "
                 "`bo_similitud_infill*.py`.")
    lines.append("")
    lines.append(f"- `BO_log` 02: {file_fingerprint(bo02)}")
    lines.append(f"- `BO_log` 03: {file_fingerprint(bo03)}")
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Informe: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

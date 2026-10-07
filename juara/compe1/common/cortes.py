"""Escritura y parseo de archivos cortes_ganancia*.txt."""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl

from common.data import ganancia_envio

ENVIOS_RE = re.compile(r"Envios=([0-9]+)")
TOTAL_RE = re.compile(r"TOTAL=(-?[0-9]+)")


def write_cortes_ganancia(
    df_sorted: pl.DataFrame,
    path: Path,
    cortes: list[int],
    header: str | None = None,
) -> None:
    lines: list[str] = []
    if header:
        lines.append(header)
    for envios in cortes:
        total = ganancia_envio(df_sorted, envios)
        lines.append(f"Envios={envios}\t TOTAL={total}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_cortes_primo(path: Path) -> pl.DataFrame:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        raise ValueError(f"Archivo vacío o sin cortes: {path}")
    if lines[0].startswith("semilla_train="):
        primo = int(lines[0].split("=", 1)[1])
    else:
        m = re.match(r"cortes_ganancia_(\d+)\.txt$", path.name)
        if not m:
            raise ValueError(f"No se pudo inferir primo: {path}")
        primo = int(m.group(1))

    body = [ln for ln in lines if ln.startswith("Envios=")]
    if not body:
        raise ValueError(f"Sin líneas Envios= en {path}")

    rows = []
    for ln in body:
        env_m = ENVIOS_RE.search(ln)
        tot_m = TOTAL_RE.search(ln)
        if not env_m or not tot_m:
            continue
        rows.append(
            {
                "primo": primo,
                "envios": int(env_m.group(1)),
                "tipo": "holdout",
                "ganancia": float(tot_m.group(1)),
            }
        )
    return pl.DataFrame(rows)


def parse_cortes_media(path: Path) -> pl.DataFrame:
    lines = path.read_text(encoding="utf-8").splitlines()
    body = [ln for ln in lines if ln.startswith("Envios=")]
    rows = []
    for ln in body:
        env_m = ENVIOS_RE.search(ln)
        tot_m = TOTAL_RE.search(ln)
        if env_m and tot_m:
            rows.append(
                {
                    "envios": int(env_m.group(1)),
                    "ganancia": float(tot_m.group(1)),
                    "fuente": "prob_media",
                }
            )
    return pl.DataFrame(rows)

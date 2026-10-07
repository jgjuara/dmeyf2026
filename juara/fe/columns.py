"""Selección de columnas continuas a transformar."""

from pathlib import Path

KEY_COLUMNS = frozenset({"numero_de_cliente", "foto_mes"})
LAG_SKIP_COLUMNS = KEY_COLUMNS | frozenset({"clase_ternaria"})


def load_nocontinuas(path: Path) -> frozenset[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip() for line in lines if line.strip())


def columns_competencia_nocontinuas(path: Path) -> list[str]:
    """Claves, clase_ternaria y variables del listado (orden del md, sin duplicados)."""
    keys = ["numero_de_cliente", "foto_mes", "clase_ternaria"]
    seen = set(keys)
    ordered = list(keys)
    for line in path.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if name and name not in seen:
            ordered.append(name)
            seen.add(name)
    return ordered


def columns_to_rank(all_columns: list[str], nocontinuas: frozenset[str]) -> list[str]:
    skip = nocontinuas | KEY_COLUMNS
    return [c for c in all_columns if c not in skip]


def columns_competencia_continuas(all_columns: list[str], nocontinuas: frozenset[str]) -> list[str]:
    return ["numero_de_cliente", "foto_mes"] + columns_to_rank(all_columns, nocontinuas)


def columns_competencia_continuas(all_columns: list[str], nocontinuas: frozenset[str]) -> list[str]:
    return ["numero_de_cliente", "foto_mes"] + columns_to_rank(all_columns, nocontinuas)


def columns_for_lag1(all_columns: list[str]) -> list[str]:
    return [c for c in all_columns if c not in LAG_SKIP_COLUMNS]

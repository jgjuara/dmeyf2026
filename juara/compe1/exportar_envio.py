#!/usr/bin/env python3
"""Arma un CSV de envío con los N primeros `numero_de_cliente` de un TSV ordenado.

El archivo no lleva encabezado ni comillas. Cada id se escribe como entero
decimal (`48000000`, `31100000`), nunca en notación científica.

Supuestos:
- La columna `numero_de_cliente` existe. Si existe `orden`, el corte son los N
  de menor orden; si no, las primeras N filas de datos.
- El sufijo de experimento sale de `--exp` o de `meta.yml` (`experiment_id`).
- Los ranks del modelo salen de `--ranks` o de `meta.yml` (`ranks_bo`).
- El nombre es `{YYYYMMDDHHMMSS}_{n}env_{rank02}_{exp00}.csv` (hora local, `_`).
  Varios ranks: `rank02-03`. `experiment_id` `00` → `exp00`; `01py` → `exp01py`.
  No se incluye el número de experimento (p. ej. `1990` en `experimento`).

Garantiza un CSV de una columna, codificación ASCII, fin de línea LF.
Falla si N no entra en el archivo, un id no es entero, hay ids repetidos en el
corte, faltan las etiquetas del nombre o el destino ya existe.
"""

from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

COLUMNA_ID = "numero_de_cliente"
COLUMNA_ORDEN = "orden"
_TOKEN = re.compile(r"[A-Za-z0-9_-]+")
_DIGITOS = re.compile(r"[0-9]+")


def a_entero(texto: str) -> int:
    """Convierte un id de cliente a `int` sin usar `float`.

    Acepta dígitos (`48000000`) o una notación que sea un entero exacto
    (`4.8e+07`, `3.11e+07`). El resultado se puede formatear con `format(n, "d")`
    y no sale en notación científica.

    Raises:
        ValueError: el texto está vacío, no es un entero o es negativo.
    """
    limpio = texto.strip()
    if limpio == "":
        raise ValueError("numero_de_cliente vacío")
    if _DIGITOS.fullmatch(limpio):
        valor = int(limpio)
    else:
        try:
            decimal = Decimal(limpio)
        except InvalidOperation as exc:
            raise ValueError(f"numero_de_cliente no es entero: {texto!r}") from exc
        if not decimal.is_finite() or decimal != decimal.to_integral_value():
            raise ValueError(f"numero_de_cliente no es entero: {texto!r}")
        valor = int(decimal)
    if valor < 0:
        raise ValueError(f"numero_de_cliente negativo: {texto!r}")
    return valor


def _separador(encabezado: str) -> str:
    if "\t" in encabezado:
        return "\t"
    if "," in encabezado:
        return ","
    raise ValueError("el encabezado no usa tabulador ni coma")


def leer_top(path: Path, n: int) -> list[int]:
    """Devuelve los N ids del corte.

    Raises:
        ValueError: archivo vacío, sin la columna de id, N fuera de rango,
            id no entero, `orden` no entero o ids repetidos en el corte.
    """
    if n < 1:
        raise ValueError(f"N debe ser >= 1, llegó {n}")
    if not path.is_file():
        raise ValueError(f"no existe el TSV: {path}")

    with path.open(newline="", encoding="utf-8") as fh:
        primera = fh.readline()
        if primera == "":
            raise ValueError(f"archivo vacío: {path}")
        separador = _separador(primera)
        fh.seek(0)
        lector = csv.reader(fh, delimiter=separador)
        encabezado = next(lector)
        if encabezado:
            encabezado[0] = encabezado[0].lstrip("\ufeff")
        nombres = [celda.strip() for celda in encabezado]
        if nombres.count(COLUMNA_ID) != 1:
            raise ValueError(f"falta una única columna {COLUMNA_ID} en {path}")
        idx_id = nombres.index(COLUMNA_ID)
        idx_orden = nombres.index(COLUMNA_ORDEN) if COLUMNA_ORDEN in nombres else None

        crudos: list[tuple[int, int]] = []
        for n_fila, fila in enumerate(lector, start=2):
            if not fila or all(not celda.strip() for celda in fila):
                continue
            if len(fila) <= idx_id or (idx_orden is not None and len(fila) <= idx_orden):
                raise ValueError(f"fila {n_fila} incompleta")
            try:
                cliente = a_entero(fila[idx_id])
            except ValueError as exc:
                raise ValueError(f"fila {n_fila}: {exc}") from exc
            if idx_orden is None:
                orden = len(crudos) + 1
            else:
                texto_orden = fila[idx_orden].strip()
                if not _DIGITOS.fullmatch(texto_orden):
                    raise ValueError(f"fila {n_fila}: orden no entero: {fila[idx_orden]!r}")
                orden = int(texto_orden)
            crudos.append((orden, cliente))

    if n > len(crudos):
        raise ValueError(f"N={n} supera las {len(crudos)} filas de {path}")

    crudos.sort(key=lambda par: par[0])
    ids = [cliente for _, cliente in crudos[:n]]
    if len(set(ids)) != len(ids):
        raise ValueError("el corte tiene numero_de_cliente repetidos")
    return ids


def _token(valor: object, campo: str) -> str:
    if isinstance(valor, bool) or valor is None:
        raise ValueError(f"{campo} ausente o inválido: {valor!r}")
    if campo == "exp" and isinstance(valor, int):
        texto = f"{valor:02d}"
    else:
        texto = str(valor).strip()
    if not _TOKEN.fullmatch(texto):
        raise ValueError(f"{campo} no sirve como nombre de archivo: {texto!r}")
    return texto


def _meta(tsv: Path) -> dict:
    camino = tsv.parent / "meta.yml"
    if not camino.is_file():
        return {}
    with camino.open(encoding="utf-8") as fh:
        datos = yaml.safe_load(fh)
    if not isinstance(datos, dict):
        raise ValueError(f"meta.yml no es un mapa: {camino}")
    return datos


def _ranks_desde_meta(valor: object) -> list[int]:
    if valor is None:
        raise ValueError("ranks_bo ausente")
    if isinstance(valor, list):
        if not valor:
            raise ValueError("ranks_bo vacío")
        return sorted(int(x) for x in valor)
    return [int(valor)]


def token_ranks(ranks: list[int]) -> str:
    """Etiqueta `rank02` o `rank02-03` para el nombre del archivo."""
    partes = [f"{r:02d}" for r in ranks]
    cuerpo = "-".join(partes)
    token = f"rank{cuerpo}"
    if not _TOKEN.fullmatch(token):
        raise ValueError(f"ranks no sirven como nombre de archivo: {ranks!r}")
    return token


def resolver_ranks(tsv: Path, ranks_cli: str | None) -> list[int]:
    if ranks_cli is not None:
        texto = ranks_cli.strip()
        if texto == "":
            raise ValueError("--ranks vacío")
        return sorted(int(p.strip()) for p in texto.split(",") if p.strip())
    meta = _meta(tsv)
    return _ranks_desde_meta(meta.get("ranks_bo"))


def sufijo_exp(tsv: Path, exp: str | None) -> str:
    """Resuelve `exp00` / `exp01` / `exp01py`.

    Raises:
        ValueError: falta `--exp` y `meta.yml` no trae `experiment_id`.
    """
    if exp is None:
        meta = _meta(tsv)
        if "experiment_id" not in meta:
            raise ValueError("falta --exp y meta.yml no trae experiment_id")
        exp_texto = _token(meta["experiment_id"], "exp")
    else:
        exp_texto = _token(exp, "exp")
    sufijo = exp_texto if exp_texto.startswith("exp") else f"exp{exp_texto}"
    _token(sufijo, "exp")
    return sufijo


def nombre_csv(n: int, ranks: list[int], sufijo_exp: str, momento: datetime) -> str:
    """Nombre `{timestamp}_{n}env_{rankXX}_{expYY}.csv`."""
    marca = momento.strftime("%Y%m%d%H%M%S")
    return f"{marca}_{n}env_{token_ranks(ranks)}_{sufijo_exp}.csv"


def escribir_csv(path: Path, ids: list[int]) -> None:
    """Escribe un id por línea, sin encabezado, sin comillas y con LF.

    Raises:
        FileExistsError: `path` ya existe.
        RuntimeError: alguna línea no quedó como dígitos ASCII.
    """
    if path.exists():
        raise FileExistsError(f"ya existe el destino, no se pisa: {path}")
    lineas: list[str] = []
    for cliente in ids:
        linea = format(int(cliente), "d")
        if not linea.isascii() or not linea.isdigit():
            raise RuntimeError(f"id exportado inválido: {linea!r}")
        lineas.append(linea)
    texto = "\n".join(lineas) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texto, encoding="ascii", newline="\n")
    leido = path.read_text(encoding="ascii")
    if leido != texto:
        raise RuntimeError(f"el CSV escrito no coincide con los ids: {path}")


def exportar(
    tsv: Path,
    n: int,
    exp: str | None = None,
    ranks: str | None = None,
    salida: Path | None = None,
    momento: datetime | None = None,
) -> Path:
    """Corta N clientes y escribe el CSV. Devuelve la ruta creada."""
    ids = leer_top(tsv, n)
    ranks_resueltos = resolver_ranks(tsv, ranks)
    sufijo = sufijo_exp(tsv, exp)
    carpeta = tsv.parent if salida is None else salida
    destino = carpeta / nombre_csv(n, ranks_resueltos, sufijo, momento or datetime.now())
    escribir_csv(destino, ids)
    return destino


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Exporta los N primeros numero_de_cliente de un TSV a un CSV "
            "sin encabezado y sin comillas."
        )
    )
    parser.add_argument("--tsv", type=Path, required=True)
    parser.add_argument("--n", type=int, required=True, help="Cantidad de clientes.")
    parser.add_argument(
        "--exp",
        default=None,
        help="Carpeta de experimento (00, 01, 01py). Se escribe como exp00, exp01, exp01py.",
    )
    parser.add_argument(
        "--ranks",
        default=None,
        help="Ranks BO usados, separados por coma (p. ej. 2 o 2,3). Default: meta.yml ranks_bo.",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=None,
        help="Directorio de salida. Default: la carpeta del TSV.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    destino = exportar(args.tsv, args.n, args.exp, args.ranks, args.salida)
    print(destino)


if __name__ == "__main__":
    main()

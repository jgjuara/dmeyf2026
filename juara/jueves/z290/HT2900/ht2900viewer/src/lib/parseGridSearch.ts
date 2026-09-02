import * as d3 from 'd3';
import type { GridSearchRow } from './types';

const REQUIRED_COLUMNS = [
  'cp',
  'maxdepth',
  'minsplit',
  'minbucket',
  'ganancia_test',
] as const;

/** Parse tab-separated gridsearch_detalle.txt into typed rows. */
export function parseGridSearch(text: string): GridSearchRow[] {
  const trimmed = text.trim();
  if (!trimmed) {
    throw new Error('El archivo está vacío.');
  }

  const raw = d3.tsvParse(trimmed);
  if (raw.length === 0) {
    throw new Error('No se encontraron filas de datos.');
  }

  const columns = Object.keys(raw[0]);
  for (const col of REQUIRED_COLUMNS) {
    if (!columns.includes(col)) {
      throw new Error(`Columna requerida faltante: ${col}`);
    }
  }

  const rows: GridSearchRow[] = [];
  for (const row of raw) {
    const cp = Number(row.cp);
    const maxdepth = Number(row.maxdepth);
    const minsplit = Number(row.minsplit);
    const minbucket = Number(row.minbucket);
    const ganancia_test = Number(row.ganancia_test);

    if (
      Number.isNaN(cp) ||
      Number.isNaN(maxdepth) ||
      Number.isNaN(minsplit) ||
      Number.isNaN(minbucket) ||
      Number.isNaN(ganancia_test)
    ) {
      throw new Error('Valores numéricos inválidos en una o más filas.');
    }

    const parsed: GridSearchRow = {
      cp,
      maxdepth,
      minsplit,
      minbucket,
      ganancia_test,
    };

    if (row.semilla !== undefined && row.semilla !== '') {
      parsed.semilla = Number(row.semilla);
    }

    rows.push(parsed);
  }

  return rows;
}

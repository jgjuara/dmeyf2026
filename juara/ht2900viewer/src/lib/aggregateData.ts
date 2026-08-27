import * as d3 from 'd3';
import type { AggregatedPoint, FilterRanges, GridSearchRow } from './types';

/** Exclude cp=0, group by (maxdepth, minsplit, minbucket), mean ganancia_test. */
export function aggregateData(rows: GridSearchRow[]): AggregatedPoint[] {
  const filtered = rows.filter((r) => r.cp !== 0);

  const grouped = d3.rollup(
    filtered,
    (values) => ({
      ganancia_test_mean: d3.mean(values, (d) => d.ganancia_test) ?? 0,
      ganancia_test_std: d3.deviation(values, (d) => d.ganancia_test) ?? 0,
      n: values.length,
    }),
    (d) => d.maxdepth,
    (d) => d.minsplit,
    (d) => d.minbucket,
  );

  const result: AggregatedPoint[] = [];
  for (const [maxdepth, bySplit] of grouped) {
    for (const [minsplit, byBucket] of bySplit) {
      for (const [minbucket, agg] of byBucket) {
        result.push({
          maxdepth,
          minsplit,
          minbucket,
          ganancia_test_mean: agg.ganancia_test_mean,
          ganancia_test_std: agg.ganancia_test_std,
          n: agg.n,
        });
      }
    }
  }

  return result;
}

export function computeFilterRanges(points: AggregatedPoint[]): FilterRanges {
  const maxdepth = d3.extent(points, (d) => d.maxdepth) as [number, number];
  const minsplit = d3.extent(points, (d) => d.minsplit) as [number, number];
  const minbucket = d3.extent(points, (d) => d.minbucket) as [number, number];
  const ganancia_test_mean = d3.extent(
    points,
    (d) => d.ganancia_test_mean,
  ) as [number, number];

  return { maxdepth, minsplit, minbucket, ganancia_test_mean };
}

export function applyFilters(
  points: AggregatedPoint[],
  ranges: FilterRanges,
): AggregatedPoint[] {
  return points.filter(
    (p) =>
      p.maxdepth >= ranges.maxdepth[0] &&
      p.maxdepth <= ranges.maxdepth[1] &&
      p.minsplit >= ranges.minsplit[0] &&
      p.minsplit <= ranges.minsplit[1] &&
      p.minbucket >= ranges.minbucket[0] &&
      p.minbucket <= ranges.minbucket[1] &&
      p.ganancia_test_mean >= ranges.ganancia_test_mean[0] &&
      p.ganancia_test_mean <= ranges.ganancia_test_mean[1],
  );
}

import type { AggregatedPoint, RankedGainPoint } from './types';

export function pointKey(
  p: Pick<AggregatedPoint, 'maxdepth' | 'minsplit' | 'minbucket'>,
): string {
  return `${p.maxdepth}|${p.minsplit}|${p.minbucket}`;
}

/** Sort by ganancia_test_mean ascending and assign rank 1..N. */
export function buildGainCurve(points: AggregatedPoint[]): RankedGainPoint[] {
  return [...points]
    .sort((a, b) => a.ganancia_test_mean - b.ganancia_test_mean)
    .map((point, index) => ({
      ...point,
      rank: index + 1,
    }));
}

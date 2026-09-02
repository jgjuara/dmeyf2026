export interface GridSearchRow {
  semilla?: number;
  cp: number;
  maxdepth: number;
  minsplit: number;
  minbucket: number;
  ganancia_test: number;
}

export interface AggregatedPoint {
  maxdepth: number;
  minsplit: number;
  minbucket: number;
  ganancia_test_mean: number;
  ganancia_test_std: number;
  n: number;
}

export interface RankedGainPoint extends AggregatedPoint {
  rank: number;
}

export interface FilterRanges {
  maxdepth: [number, number];
  minsplit: [number, number];
  minbucket: [number, number];
  ganancia_test_mean: [number, number];
}

export interface Rotation {
  yaw: number;
  pitch: number;
}

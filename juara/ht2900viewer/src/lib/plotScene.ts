import type { Vec3 } from './project3d';

export interface AxisConfig {
  key: 'maxdepth' | 'minsplit' | 'minbucket';
  label: string;
  color: string;
  extent: [number, number];
}

/** Unit-cube wireframe edges in normalized [-1, 1] space. */
export const WIRE_EDGES: [Vec3, Vec3][] = [
  [{ x: -1, y: -1, z: -1 }, { x: 1, y: -1, z: -1 }],
  [{ x: 1, y: -1, z: -1 }, { x: 1, y: -1, z: 1 }],
  [{ x: 1, y: -1, z: 1 }, { x: -1, y: -1, z: 1 }],
  [{ x: -1, y: -1, z: 1 }, { x: -1, y: -1, z: -1 }],
  [{ x: -1, y: 1, z: -1 }, { x: 1, y: 1, z: -1 }],
  [{ x: 1, y: 1, z: -1 }, { x: 1, y: 1, z: 1 }],
  [{ x: 1, y: 1, z: 1 }, { x: -1, y: 1, z: 1 }],
  [{ x: -1, y: 1, z: 1 }, { x: -1, y: 1, z: -1 }],
  [{ x: -1, y: -1, z: -1 }, { x: -1, y: 1, z: -1 }],
  [{ x: 1, y: -1, z: -1 }, { x: 1, y: 1, z: -1 }],
  [{ x: 1, y: -1, z: 1 }, { x: 1, y: 1, z: 1 }],
  [{ x: -1, y: -1, z: 1 }, { x: -1, y: 1, z: 1 }],
];

/** Floor grid on the min face (y = -1) of the unit cube. */
export function floorGrid(divisions = 5): [Vec3, Vec3][] {
  const lines: [Vec3, Vec3][] = [];
  const y = -1;

  for (let i = 0; i <= divisions; i++) {
    const t = -1 + (2 * i) / divisions;
    lines.push(
      [{ x: t, y, z: -1 }, { x: t, y, z: 1 }],
      [{ x: -1, y, z: t }, { x: 1, y, z: t }],
    );
  }

  return lines;
}

export const AXES: Array<{
  key: AxisConfig['key'];
  label: string;
  color: string;
  from: Vec3;
  to: Vec3;
  tickAt: Vec3;
}> = [
  {
    key: 'minsplit',
    label: 'minsplit',
    color: '#51cf66',
    from: { x: -1, y: -1, z: -1 },
    to: { x: 1, y: -1, z: -1 },
    tickAt: { x: 1, y: -1, z: -1 },
  },
  {
    key: 'maxdepth',
    label: 'maxdepth',
    color: '#ff6b6b',
    from: { x: -1, y: -1, z: -1 },
    to: { x: -1, y: 1, z: -1 },
    tickAt: { x: -1, y: 1, z: -1 },
  },
  {
    key: 'minbucket',
    label: 'minbucket',
    color: '#74c0fc',
    from: { x: -1, y: -1, z: -1 },
    to: { x: -1, y: -1, z: 1 },
    tickAt: { x: -1, y: -1, z: 1 },
  },
];

export function formatAxisValue(value: number): string {
  if (Math.abs(value) >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `${(value / 1_000).toFixed(1)}k`;
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function formatGanancia(value: number): string {
  if (Math.abs(value) >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(2)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `${(value / 1_000).toFixed(0)}k`;
  }
  return String(Math.round(value));
}

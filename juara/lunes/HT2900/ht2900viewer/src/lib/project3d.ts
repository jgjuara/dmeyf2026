import type { Rotation } from './types';

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export interface ProjectedPoint {
  x: number;
  y: number;
  z: number;
}

function rotateY(p: Vec3, angle: number): Vec3 {
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  return {
    x: p.x * cos + p.z * sin,
    y: p.y,
    z: -p.x * sin + p.z * cos,
  };
}

function rotateX(p: Vec3, angle: number): Vec3 {
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  return {
    x: p.x,
    y: p.y * cos - p.z * sin,
    z: p.y * sin + p.z * cos,
  };
}

/** Orthographic projection with yaw/pitch rotation into screen coordinates. */
export function project3d(
  point: Vec3,
  rotation: Rotation,
  width: number,
  height: number,
  scale: number,
): ProjectedPoint {
  let p = rotateY(point, rotation.yaw);
  p = rotateX(p, rotation.pitch);

  const cx = width / 2;
  const cy = height / 2;

  return {
    x: cx + p.x * scale,
    y: cy - p.y * scale,
    z: p.z,
  };
}

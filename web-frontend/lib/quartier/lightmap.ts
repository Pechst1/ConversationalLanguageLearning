/**
 * Le Quartier · the lamps' pools, baked once.
 *
 * A phone cannot light every fragment from forty lamps, and a print does not need it to: the
 * pools of light on the cobbles are a second ink, laid where the lamps are. So the lamps are
 * summed once into a map of the ground (rgb for the street lamps, alpha for the rooms' own
 * light) and every surface reads its pool from there, quantised into hard rings by the shader.
 */
import { DataTexture, LinearFilter, RGBAFormat, UnsignedByteType, Vector4 } from 'three';

import type { Lamp } from './kit';

export interface LightMap {
  texture: DataTexture;
  rect: Vector4;
  /** the light at a point of the ground: street rgb, room alpha (for the paper figures) */
  sample: (x: number, z: number) => [number, number, number, number];
}

export interface Bounds {
  x0: number;
  z0: number;
  x1: number;
  z1: number;
}

/**
 * Sum the lamps into a map covering `bounds` at `perMetre` texels a metre. `inRoom` keeps a
 * room's lamps inside it and the street's outside, since walls cast no shadows here.
 */
export function bakeLightMap(lamps: Lamp[], bounds: Bounds, perMetre: number, inRoom: (x: number, z: number) => boolean): LightMap {
  const w = Math.min(2048, Math.ceil((bounds.x1 - bounds.x0) * perMetre));
  const h = Math.min(2048, Math.ceil((bounds.z1 - bounds.z0) * perMetre));
  const sx = (bounds.x1 - bounds.x0) / w;
  const sz = (bounds.z1 - bounds.z0) / h;
  const acc = new Float32Array(w * h * 4);
  for (const lamp of lamps) {
    const r = lamp.range;
    const ix0 = Math.max(0, Math.floor((lamp.pos.x - r - bounds.x0) / sx));
    const ix1 = Math.min(w - 1, Math.ceil((lamp.pos.x + r - bounds.x0) / sx));
    const iz0 = Math.max(0, Math.floor((lamp.pos.z - r - bounds.z0) / sz));
    const iz1 = Math.min(h - 1, Math.ceil((lamp.pos.z + r - bounds.z0) / sz));
    // a lamp high on its post lights a wider, softer pool than one at eye level
    const lift = Math.max(0, lamp.pos.y - 1);
    for (let iz = iz0; iz <= iz1; iz++) {
      const z = bounds.z0 + (iz + 0.5) * sz;
      for (let ix = ix0; ix <= ix1; ix++) {
        const x = bounds.x0 + (ix + 0.5) * sx;
        const room = inRoom(x, z);
        if (!!lamp.indoor !== room) continue;
        const d = Math.hypot(x - lamp.pos.x, z - lamp.pos.z, lift * 0.35);
        if (d >= r) continue;
        const t = 1 - d / r;
        const f = t * t * (3 - 2 * t) * lamp.power;
        const k = (iz * w + ix) * 4;
        if (lamp.indoor) {
          acc[k + 3] += f;
        } else {
          acc[k] += lamp.color[0] * f;
          acc[k + 1] += lamp.color[1] * f;
          acc[k + 2] += lamp.color[2] * f;
        }
      }
    }
  }
  const data = new Uint8Array(w * h * 4);
  for (let i = 0; i < acc.length; i++) data[i] = Math.min(255, Math.round((acc[i] / 4) * 255));
  const texture = new DataTexture(data, w, h, RGBAFormat, UnsignedByteType);
  texture.magFilter = LinearFilter;
  texture.minFilter = LinearFilter;
  texture.needsUpdate = true;
  const rect = new Vector4(bounds.x0, bounds.z0, 1 / (bounds.x1 - bounds.x0), 1 / (bounds.z1 - bounds.z0));
  const sample = (x: number, z: number): [number, number, number, number] => {
    const ix = Math.floor((x - bounds.x0) / sx);
    const iz = Math.floor((z - bounds.z0) / sz);
    if (ix < 0 || iz < 0 || ix >= w || iz >= h) return [0, 0, 0, 0];
    const k = (iz * w + ix) * 4;
    return [acc[k], acc[k + 1], acc[k + 2], acc[k + 3]];
  };
  return { texture, rect, sample };
}

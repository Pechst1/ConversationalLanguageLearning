/**
 * WP-120 §5.1 · placing a lat/lon on La Carte's drawings, client-side, no geo library.
 *
 * `public/assets/carte/carte-projection.json` (written by `scripts/geo/build_carte.py`)
 * carries the Lambert-93 constants and, per drawing, the 6-number affine from projected
 * metres to SVG user units, the drawing's lat/lon bounds and the overseas insets (each
 * with its own equirectangular constants and affine). `projectPoint` is the build
 * script's `project_point`, line for line; the tests hold it to the script's own check
 * points (± 2 units).
 */

import projectionData from '@/public/assets/carte/carte-projection.json';

import type { CarteLevel } from '@/lib/carte-types';

export type Affine = [number, number, number, number, number, number];

export type CarteBounds = { lat_min: number; lat_max: number; lon_min: number; lon_max: number };

export type CarteInset = {
  code: string;
  name_fr: string;
  box: [number, number, number, number];
  bbox: CarteBounds;
  equirect: { lon0: number; lat0: number; cos_lat0: number };
  affine: Affine;
};

export type CarteDrawing = {
  viewBox: [number, number, number, number];
  projection: 'lambert93';
  affine: Affine;
  bounds: CarteBounds;
  insets: CarteInset[];
};

export type CarteProjection = {
  fallback: boolean;
  lambert93: { e: number; n: number; c: number; rho0: number; lon0: number; x0: number; y0: number };
  drawings: Record<CarteLevel, CarteDrawing>;
  checks: Array<{ drawing: CarteLevel; label: string; lat: number; lon: number; x: number; y: number }>;
};

export const CARTE_PROJECTION = projectionData as unknown as CarteProjection;

/** The static drawing of a level (`public/assets/carte/<level>.svg`). */
export function drawingUrl(level: CarteLevel): string {
  return `/assets/carte/${level}.svg`;
}

const RAD = Math.PI / 180;

export function lambert93(lat: number, lon: number, projection: CarteProjection = CARTE_PROJECTION): [number, number] {
  const { e, n, c, rho0, lon0, x0, y0 } = projection.lambert93;
  const phi = lat * RAD;
  const es = e * Math.sin(phi);
  const t = Math.tan(Math.PI / 4 - phi / 2) / Math.pow((1 - es) / (1 + es), e / 2);
  const rho = c * Math.pow(t, n);
  const theta = n * (lon - lon0) * RAD;
  return [x0 + rho * Math.sin(theta), y0 + rho0 - rho * Math.cos(theta)];
}

export function applyAffine([a, b, c, d, e, f]: Affine, x: number, y: number): [number, number] {
  return [a * x + c * y + e, b * x + d * y + f];
}

const inside = (b: CarteBounds, lat: number, lon: number) =>
  lat >= b.lat_min && lat <= b.lat_max && lon >= b.lon_min && lon <= b.lon_max;

/** SVG user units on `level`'s drawing, or `null` when the point is not on it. */
export function projectPoint(
  level: CarteLevel,
  lat: number,
  lon: number,
  projection: CarteProjection = CARTE_PROJECTION,
): [number, number] | null {
  const drawing = projection.drawings[level];
  if (!drawing || !Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  for (const inset of drawing.insets || []) {
    if (inside(inset.bbox, lat, lon)) {
      const { lon0, lat0, cos_lat0: cosLat0 } = inset.equirect;
      return applyAffine(inset.affine, (lon - lon0) * cosLat0, lat - lat0);
    }
  }
  if (!inside(drawing.bounds, lat, lon)) return null;
  const [x, y] = lambert93(lat, lon, projection);
  return applyAffine(drawing.affine, x, y);
}

export function viewBoxOf(level: CarteLevel, projection: CarteProjection = CARTE_PROJECTION): { width: number; height: number } {
  const [, , width, height] = projection.drawings[level].viewBox;
  return { width, height };
}

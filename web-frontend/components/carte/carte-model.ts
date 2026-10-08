/**
 * WP-120 §5.2 · La Carte as pure functions: which pins a level shows, where, how
 * they cluster, and what a tap on a cluster does.
 *
 * Three levels, France → Île-de-France → Paris. A pin is on a level when its point
 * lies on that level's drawing (`projectPoint`). Pins are 28 px stamps; two marks
 * closer than `CLUSTER_PX` on screen merge into a cluster (an ink disc with the
 * count). A cluster zooms one level when all of it lies on the next drawing;
 * otherwise (two Papiers in Lyon, or the same café twice in Paris) it opens a list.
 */

import type { CarteLevel, CartePin, CarteQuartierPlace } from '@/lib/carte-types';

import { CARTE_PROJECTION, projectPoint, viewBoxOf, type CarteProjection } from './carte-projection';

export const CARTE_LEVELS: readonly CarteLevel[] = ['france', 'idf', 'paris'];
/** The pin's diameter on screen (the vignette's `pin` size). */
export const PIN_PX = 28;
/** Marks closer than this (CSS px, centre to centre) cluster. */
export const CLUSTER_PX = 28;
/** «Mon quartier» squares are smaller; they cluster among themselves only. */
export const QUARTIER_CLUSTER_PX = 18;
/** The map's width on a 390 px phone with the 16 px gutters, before it is measured. */
export const DEFAULT_MAP_PX = 358;

export type Placed<T> = { item: T; x: number; y: number };

export type Cluster<T> = {
  /** Stable: the first member's key. */
  id: string;
  x: number;
  y: number;
  members: Placed<T>[];
};

export function nextLevel(level: CarteLevel): CarteLevel | null {
  const index = CARTE_LEVELS.indexOf(level);
  return index >= 0 && index < CARTE_LEVELS.length - 1 ? CARTE_LEVELS[index + 1] : null;
}

export function previousLevel(level: CarteLevel): CarteLevel | null {
  const index = CARTE_LEVELS.indexOf(level);
  return index > 0 ? CARTE_LEVELS[index - 1] : null;
}

/** The items whose point lies on `level`'s drawing, with their SVG coordinates. */
export function placeOnLevel<T extends { lat: number; lon: number }>(
  level: CarteLevel,
  items: readonly T[],
  projection: CarteProjection = CARTE_PROJECTION,
): Placed<T>[] {
  const placed: Placed<T>[] = [];
  for (const item of items) {
    const point = projectPoint(level, item.lat, item.lon, projection);
    if (point) placed.push({ item, x: point[0], y: point[1] });
  }
  return placed;
}

/** CSS px per SVG unit when the drawing is `mapPx` wide. */
export function pxPerUnit(level: CarteLevel, mapPx: number, projection: CarteProjection = CARTE_PROJECTION): number {
  return (mapPx > 0 ? mapPx : DEFAULT_MAP_PX) / viewBoxOf(level, projection).width;
}

/**
 * Greedy clustering in screen space, in the items' order: a mark joins the first
 * cluster whose centre is within `radiusPx`, and the centre moves to the members' mean.
 */
export function clusterPlaced<T>(
  placed: readonly Placed<T>[],
  unitPx: number,
  keyOf: (item: T) => string,
  radiusPx: number = CLUSTER_PX,
): Cluster<T>[] {
  const clusters: Cluster<T>[] = [];
  const limit = radiusPx / Math.max(unitPx, 1e-9);
  for (const mark of placed) {
    const home = clusters.find((cluster) => Math.hypot(cluster.x - mark.x, cluster.y - mark.y) < limit);
    if (home) {
      home.members.push(mark);
      home.x = home.members.reduce((sum, m) => sum + m.x, 0) / home.members.length;
      home.y = home.members.reduce((sum, m) => sum + m.y, 0) / home.members.length;
    } else {
      clusters.push({ id: keyOf(mark.item), x: mark.x, y: mark.y, members: [mark] });
    }
  }
  return clusters;
}

/** Oldest Papier first, so a cluster's id and the pins' tab order stay stable. */
export function orderPins(pins: readonly CartePin[]): CartePin[] {
  return [...pins].sort((a, b) => (a.week === b.week ? a.sessionId.localeCompare(b.sessionId) : a.week.localeCompare(b.week)));
}

export type LevelLayout = {
  level: CarteLevel;
  width: number;
  height: number;
  clusters: Cluster<CartePin>[];
  /** Pins of the map that this level does not show (e.g. Bourgogne, seen from Paris). */
  elsewhere: number;
  quartier: Cluster<CarteQuartierPlace>[];
};

export function layoutLevel(
  level: CarteLevel,
  pins: readonly CartePin[],
  options: { mapPx?: number; quartier?: readonly CarteQuartierPlace[]; projection?: CarteProjection } = {},
): LevelLayout {
  const projection = options.projection ?? CARTE_PROJECTION;
  const unit = pxPerUnit(level, options.mapPx ?? DEFAULT_MAP_PX, projection);
  const placed = placeOnLevel(level, orderPins(pins), projection);
  const { width, height } = viewBoxOf(level, projection);
  const quartier =
    level === 'paris' && options.quartier?.length
      ? clusterPlaced(placeOnLevel(level, options.quartier, projection), unit, (q) => q.id, QUARTIER_CLUSTER_PX)
      : [];
  return {
    level,
    width,
    height,
    clusters: clusterPlaced(placed, unit, (pin) => pin.sessionId),
    elsewhere: pins.length - placed.length,
    quartier,
  };
}

/** Where a tap on a cluster goes: the next level when all of it is on that drawing, else a list. */
export function clusterTarget(
  level: CarteLevel,
  cluster: Cluster<CartePin>,
  projection: CarteProjection = CARTE_PROJECTION,
): { kind: 'zoom'; level: CarteLevel } | { kind: 'list' } {
  const next = nextLevel(level);
  // A cluster outside the Île-de-France (two Papiers in Lyon) has no closer drawing.
  if (next && cluster.members.every((m) => projectPoint(next, m.item.lat, m.item.lon, projection))) {
    return { kind: 'zoom', level: next };
  }
  return { kind: 'list' };
}

export function weekNo(week: string): number | null {
  const match = /W(\d{1,2})$/.exec(week || '');
  return match ? Number(match[1]) : null;
}

/** The learner's part of `text` as segments, `[start, end)` spans marked. */
export function markSpans(text: string, spans: ReadonlyArray<readonly [number, number]>): Array<{ text: string; yours: boolean }> {
  const clean = [...spans]
    .map(([a, b]) => [Math.max(0, a), Math.min(text.length, b)] as const)
    .filter(([a, b]) => b > a)
    .sort((x, y) => x[0] - y[0]);
  const out: Array<{ text: string; yours: boolean }> = [];
  let at = 0;
  for (const [a, b] of clean) {
    if (a < at) continue;
    if (a > at) out.push({ text: text.slice(at, a), yours: false });
    out.push({ text: text.slice(a, b), yours: true });
    at = b;
  }
  if (at < text.length) out.push({ text: text.slice(at), yours: false });
  return out;
}

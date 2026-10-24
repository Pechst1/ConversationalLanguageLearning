/**
 * Le Quartier · a racecourse on race day: the set of a place where the news happens.
 *
 * The forge places it from the survey (`scripts/forge/venue.py`): the grandstand's footprint
 * says where the stand is and which way it looks, the course's land which side the track lies,
 * and the way the course turns which way the horses run. The kit draws it in the quai's inks:
 * the stand's tiers full of people under a roof on thin posts, the esplanade and the lawn before
 * it, the white rails of the home straight, the winning post with its red disc and the line
 * across the turf, the betting windows, the board across the track, the trees of the Bois
 * beyond and the windmill far off on its rise. The horses are the director's (`course.ts`).
 */
import { Vector3 } from 'three';

import { KERB, boxShape, fitText, planeTree } from './kit';
import type { Build } from './kit';
import { PATTERN, area2, nextId, seeded } from './geo';
import type { Paint, Press } from './geo';
import { COATS } from './horse-art';
import type { SilkPattern, Silks } from './horse-art';
import type { Words } from './memory';
import { INKS, TONES, css, mix } from './palette';
import type { Hex } from './palette';

type XZ = [number, number];

export interface RaceSpec {
  name: Words;
  /** the distance and the hour on the card (the article's) */
  metres: number;
  hour: string;
  runners: number;
  /** the draw of the field: silks, coats and the morning's odds */
  seed: number;
}

export interface VenueSpec {
  kind: 'hippodrome';
  /** the winning post's foot on the rail; `u` the way the horses run, `n` from the stand across the track */
  post: XZ;
  u: XZ;
  n: XZ;
  /** metres across: the track between its rails, the lawn before the rail, the esplanade before the stand */
  track: number;
  lawn: number;
  esplanade: number;
  /** the grandstand behind the esplanade, from u0 to u1 along the straight (from the survey) */
  stand: { u0: number; u1: number; depth: number; height: number };
  /** along the straight: the betting windows on the esplanade, the board across the track */
  guichet: number;
  board: number;
  /** the windmill, far across the course (u, n) */
  moulin: [number, number] | null;
  race: RaceSpec;
}

export interface Runner {
  /** the number on the saddle cloth */
  n: number;
  silks: Silks;
  coat: Hex;
  /** the morning's odds, «7 contre 1» */
  odds: number;
}

export interface VenueBuilt {
  spec: VenueSpec;
  /** a point of the set: `u` metres along the straight from the post, `n` across from the rail, `y` up */
  at: (u: number, n: number, y?: number) => Vector3;
  runners: Runner[];
  /** last year's winner, back for another go */
  holder: number;
  /** where the clerk stands behind the window, and where you stand to bet */
  clerk: Vector3;
  window: Vector3;
  /** the board's face, toward the stand: its middle, its normal, its size (the director prints on it) */
  board: { center: Vector3; normal: Vector3; width: number; height: number };
  /** at the rail by the post: where to watch the finish from */
  rail: Vector3;
}

const SILK_INKS: Hex[] = [
  INKS.cobalt,
  INKS.vermilion,
  INKS.sunflower,
  INKS.green,
  INKS.ink,
  INKS.card,
  mix(INKS.vermilion, INKS.card, 0.45),
  mix(INKS.cobalt, INKS.card, 0.5),
  INKS.ochre,
  mix(INKS.green, INKS.sunflower, 0.45),
];
const PATTERNS: SilkPattern[] = ['plain', 'hoops', 'sash', 'halves', 'stars', 'chevrons'];
/** the odds a field of sixteen is quoted at, from the favourite out */
const BOOK = [3, 5, 6, 8, 9, 11, 13, 15, 18, 20, 25, 30, 35, 40, 50, 60];

/** The field: each runner's silks, coat and odds, the same for a race's seed. */
export function fieldOf(race: RaceSpec): { runners: Runner[]; holder: number } {
  const R = seeded(race.seed);
  const n = Math.max(2, Math.min(16, race.runners));
  const odds = BOOK.slice(0, n);
  // shuffle all but the shortest price, which last year's winner carries
  for (let i = odds.length - 1; i > 1; i--) {
    const j = 1 + R.int(0, i - 1);
    const t = odds[i];
    odds[i] = odds[j];
    odds[j] = t;
  }
  const holder = 1 + R.int(0, n - 1);
  const rest = odds.slice(1);
  const runners: Runner[] = [];
  for (let i = 1; i <= n; i++) {
    const body = SILK_INKS[(i * 3 + R.int(0, 2)) % SILK_INKS.length];
    let second = SILK_INKS[(i * 7 + 3 + R.int(0, 3)) % SILK_INKS.length];
    if (second === body) second = SILK_INKS[(SILK_INKS.indexOf(body) + 4) % SILK_INKS.length];
    runners.push({
      n: i,
      silks: { body, second, pattern: PATTERNS[(i + R.int(0, PATTERNS.length - 1)) % PATTERNS.length], cap: R.chance(0.5) ? second : body },
      coat: COATS[R.int(0, COATS.length - 1)],
      odds: i === holder ? odds[0] : (rest.shift() as number),
    });
  }
  return { runners, holder };
}

/** Lay the racecourse into the build. */
export function hippodrome(B: Build, v: VenueSpec): VenueBuilt {
  const D = B.dry;
  const [ux, uz] = v.u;
  const [nx, nz] = v.n;
  const xz = (u: number, n: number): XZ => [v.post[0] + ux * u + nx * n, v.post[1] + uz * u + nz * n];
  const at = (u: number, n: number, y = 0) => {
    const [x, z] = xz(u, n);
    return new Vector3(x, y, z);
  };
  // `Press.at`'s frame: its x along u, its z along s · n
  const ang = Math.atan2(-uz, ux);
  const s = Math.sign(nx * -uz + nz * ux) || 1;
  const block = (u: number, n: number, y0: number, lu: number, ln: number, h: number, paint: Paint) => {
    const p = at(u, n);
    D.at(p.x, y0, p.z, ang, () => D.block(0, 0, 0, lu, h, ln, paint));
  };
  const flat = (P: Press, u0: number, u1: number, n0: number, n1: number, y: number, paint: Paint) => {
    const pts = [xz(u0, n0), xz(u1, n0), xz(u1, n1), xz(u0, n1)];
    // a negative area in (x, z) faces up
    const ring = area2(pts) > 0 ? pts.slice().reverse() : pts;
    const q = ring.map(([x, z]) => new Vector3(x, y, z));
    P.quad(q[0], q[1], q[2], q[3], paint, paint.id);
  };
  const T = v.track;
  const front = -(v.lawn + v.esplanade);
  const far = { u0: -420, u1: 220 };

  /* ---- the ground: the turf, the lawn, the esplanade, the infield ------------------------- */
  const turfA: Paint = { color: mix(INKS.green, INKS.sunflower, 0.38), id: 10, pattern: PATTERN.grit };
  const turfB: Paint = { color: mix(INKS.green, INKS.sunflower, 0.26), id: 10, pattern: PATTERN.grit };
  for (let u = far.u0, k = 0; u < far.u1; u += 12, k++) flat(D, u, Math.min(far.u1, u + 12), 0, T, KERB + 0.02, k % 2 ? turfA : turfB);
  // the line across the turf at the post
  flat(D, -0.14, 0.14, 0, T, KERB + 0.03, { color: INKS.card, id: 6 });
  const lawn: Paint = { color: mix(INKS.green, INKS.sunflower, 0.32), id: 10, pattern: PATTERN.grit };
  flat(D, far.u0, far.u1, -v.lawn, 0, KERB + 0.02, lawn);
  flat(D, far.u0, far.u1, T, T + 260, KERB + 0.02, { color: mix(INKS.green, INKS.sunflower, 0.22), id: 10, pattern: PATTERN.grit });
  flat(B.wet, v.stand.u0 - 30, v.stand.u1 + 30, front, -v.lawn, KERB, { color: mix(TONES.stoneGround, INKS.paper, 0.35), id: 3, pattern: PATTERN.flags });
  flat(D, far.u0, far.u1, front - v.stand.depth - 40, front, KERB - 0.01, { color: mix(INKS.green, INKS.ink, 0.12), id: 10, pattern: PATTERN.grit });

  /* ---- the rails of the straight ---------------------------------------------------------- */
  const white: Paint = { color: INKS.card, id: nextId() };
  for (const rn of [-0.1, T + 0.1]) {
    for (let u = far.u0; u < far.u1; u += 24) {
      const lu = Math.min(24, far.u1 - u);
      block(u + lu / 2, rn, KERB + 0.95, lu, 0.1, 0.13, white);
    }
    for (let u = far.u0; u <= far.u1; u += Math.abs(u) < 160 ? 3 : 8) block(u, rn, KERB, 0.09, 0.09, 0.95, white);
    // nobody walks onto the track
    const [cx, cz] = xz((far.u0 + far.u1) / 2, rn);
    B.blocks.push(boxShape(cx, cz, far.u1 - far.u0, 0.5, ang));
  }

  /* ---- the winning post ------------------------------------------------------------------- */
  {
    const p = at(0, -0.55);
    D.cylinder(p.x, KERB, p.z, 0.08, 0.07, 4.1, 8, { color: INKS.card, id: nextId() }, { flat: true });
    const disc = at(0, -0.55, KERB + 4.1);
    D.at(disc.x, disc.y, disc.z, ang, () => {
      D.box(0, 0, 0, 1.08, 1.08, 0.05, { color: INKS.card, id: nextId() });
      D.box(0, 0, s * 0.04, 0.86, 0.86, 0.05, { color: INKS.vermilion, id: nextId() });
      D.box(0, 0, -s * 0.04, 0.86, 0.86, 0.05, { color: INKS.vermilion, id: nextId() });
    });
  }

  /* ---- the grandstand --------------------------------------------------------------------- */
  const st = v.stand;
  const len = st.u1 - st.u0;
  const mid = (st.u0 + st.u1) / 2;
  const tiers = 12;
  const tread = 0.8;
  const rise = 0.42;
  const base = 1.4;
  const concrete: Paint = { color: mix(TONES.stoneLight, INKS.paper, 0.3), id: nextId(), pattern: PATTERN.courses };
  const step: Paint = { color: mix(TONES.stoneLight, INKS.ink, 0.08), id: nextId() };
  for (let i = 0; i < tiers; i++) block(mid, front - (i + 0.5) * tread, KERB, len, tread, base + (i + 1) * rise, i % 2 ? step : concrete);
  const top = base + tiers * rise;
  const back = Math.max(4, st.depth - tiers * tread);
  const glassBand: Paint = { color: TONES.pane, wet: 0.6, id: nextId() };
  block(mid, front - tiers * tread - back / 2, KERB, len, back, st.height - 1.2, concrete);
  // the glazed boxes above the top tier, facing the course
  for (let y = top + 1.2; y < st.height - 3; y += 3.6) block(mid, front - tiers * tread + 0.12, KERB + y, len - 2, 0.3, 2.2, glassBand);
  // the ends, closed
  for (const e of [st.u0, st.u1]) block(e, front - st.depth / 2, KERB, 0.7, st.depth, st.height - 1.2, concrete);
  // the roof, reaching out over the tiers on thin posts
  const roof: Paint = { color: mix(INKS.card, INKS.cobalt, 0.06), id: nextId() };
  block(mid, front - st.depth / 2 + 4.5, KERB + st.height - 1.2, len + 2, st.depth + 9, 0.5, roof);
  for (let u = st.u0 + 6; u < st.u1 - 3; u += 14) {
    const p = at(u, front - 0.3);
    D.cylinder(p.x, KERB + base, p.z, 0.16, 0.12, st.height - 1.2 - base, 8, { color: mix(INKS.card, INKS.ink, 0.12), id: roof.id }, { flat: true });
  }
  // the people in the stand: a coat and a head on each seat that is taken
  {
    const R = seeded(v.race.seed + 17);
    const coats = [INKS.cobalt, mix(INKS.ink, INKS.cobalt, 0.3), INKS.vermilion, mix(INKS.ochre, INKS.ink, 0.3), INKS.green, mix(INKS.paper, INKS.ink, 0.3), INKS.sunflower, mix(INKS.card, INKS.ochre, 0.2)];
    const heads = [mix(INKS.ochre, INKS.card, 0.55), mix(INKS.ochre, INKS.ink, 0.35), mix(INKS.ochre, INKS.vermilion, 0.3)];
    const ids = [nextId(), nextId(), nextId()];
    for (let i = 0; i < tiers; i++) {
      const y = KERB + base + (i + 1) * rise;
      for (let u = st.u0 + 1.2; u < st.u1 - 1.2; u += 0.64) {
        if (!R.chance(0.74)) continue;
        const p = at(u + R.range(-0.08, 0.08), front - (i + 0.5) * tread + 0.08);
        const h = R.range(0.5, 0.66);
        const id = ids[R.int(0, ids.length - 1)];
        D.at(p.x, y, p.z, ang, () => {
          D.block(0, 0, 0, 0.44, h, 0.3, { color: coats[R.int(0, coats.length - 1)], id });
          D.block(0, h, 0, 0.2, 0.22, 0.2, { color: heads[R.int(0, heads.length - 1)], id });
        });
      }
    }
  }
  // the name along the roof's edge
  {
    const n = at(mid, front + 4.62, KERB + st.height - 0.95);
    B.signs.push({ key: 'tribune', center: n, normal: new Vector3(nx, 0, nz), width: Math.min(34, len * 0.4), height: 0.95, density: 60, draw: letters('HIPPODROME DE LONGCHAMP', css(INKS.card), css(INKS.cobalt)) });
  }
  B.blocks.push(boxShape(...xz(mid, front - st.depth / 2), len + 1, st.depth, ang));

  /* ---- the betting windows ---------------------------------------------------------------- */
  const { runners, holder } = fieldOf(v.race);
  const g = v.guichet;
  const gn = front + 3.4;
  const kiosk: Paint = { color: mix(INKS.green, INKS.ink, 0.25), id: nextId(), pattern: PATTERN.ribs };
  const trim: Paint = { color: mix(INKS.card, INKS.ochre, 0.1), id: nextId() };
  block(g, gn - 1.1, KERB, 4.2, 0.35, 2.8, kiosk);
  for (const e of [-1, 1]) block(g + e * 1.95, gn, KERB, 0.3, 2.55, 2.8, kiosk);
  block(g, gn + 1.1, KERB, 3.6, 0.35, 1.05, trim);
  block(g, gn + 1.1, KERB + 2.2, 3.6, 0.35, 0.6, kiosk);
  block(g, gn, KERB + 2.8, 4.7, 3.1, 0.18, trim);
  block(g, gn - 0.85, KERB, 3.5, 0.06, 2.6, { color: mix(INKS.ink, INKS.cobalt, 0.2), id: nextId() });
  B.signs.push({ key: 'guichet', center: at(g, gn + 1.29, KERB + 2.5), normal: new Vector3(nx, 0, nz), width: 2.6, height: 0.42, density: 160, draw: letters('PARIS · GUICHET', css(mix(INKS.green, INKS.ink, 0.25)), css(INKS.card)) });
  B.blocks.push(boxShape(...xz(g, gn), 4.4, 2.8, ang));
  // over the window, the runners and their odds: what you read on your way to bet
  block(g, gn + 0.4, KERB + 2.98, 3.5, 0.14, 2.3, kiosk);
  B.signs.push({ key: 'cote', center: at(g, gn + 0.485, KERB + 4.13), normal: new Vector3(nx, 0, nz), width: 3.3, height: 2.1, density: 190, draw: oddsArt(runners) });

  /* ---- the board across the track --------------------------------------------------------- */
  const bn = T + 16;
  const frame: Paint = { color: mix(INKS.ink, INKS.cobalt, 0.25), id: nextId() };
  for (const e of [-4, 4]) block(v.board + e, bn, KERB, 0.4, 0.4, 3.4, frame);
  block(v.board, bn + 0.15, KERB + 3.2, 10.2, 0.4, 5.8, frame);

  /* ---- the Bois beyond the course, and the windmill on its rise ---------------------------- */
  {
    const R = seeded(v.race.seed + 5);
    for (let u = -300; u < 200; u += R.range(9, 16)) planeTree(B, ...xz(u, T + R.range(70, 110)), KERB, R.range(1.3, 1.8), true);
    for (let u = -300; u < 200; u += R.range(14, 22)) planeTree(B, ...xz(u, front - st.depth - R.range(14, 30)), KERB, R.range(1.2, 1.6), true);
    // at the ends of the lawn, close by
    for (const e of [-1, 1]) planeTree(B, ...xz(e * 52, -v.lawn * 0.5), KERB, 1.15, false);
  }
  if (v.moulin) {
    const [mu, mn] = v.moulin;
    const p = at(mu, mn);
    const stone: Paint = { color: mix(TONES.stoneLight, INKS.ochre, 0.12), id: nextId(), pattern: PATTERN.courses };
    D.cylinder(p.x, KERB, p.z, 3.4, 2.7, 10, 12, stone, { flat: true });
    D.cylinder(p.x, KERB + 10, p.z, 3.0, 0.15, 3.4, 12, { color: mix(INKS.vermilion, INKS.ink, 0.35), id: nextId() }, { flat: true });
    const hub = at(mu, mn - 3.2, KERB + 9.2);
    const sail: Paint = { color: mix(INKS.ochre, INKS.ink, 0.45), id: nextId() };
    const tilt = 0.4;
    for (let k = 0; k < 4; k++) {
      const a = tilt + (k * Math.PI) / 2;
      const tip = hub.clone().add(new Vector3(ux * Math.cos(a) * 8.5, Math.sin(a) * 8.5, uz * Math.cos(a) * 8.5));
      D.bar(hub, tip, 0.9, sail);
    }
  }

  return {
    spec: v,
    at,
    runners,
    holder,
    clerk: at(g, gn + 0.35, 0),
    window: at(g, gn + 2.6, 0),
    board: { center: at(v.board, bn - 0.08, KERB + 6.1), normal: new Vector3(-nx, 0, -nz), width: 9.6, height: 5.2 },
    rail: at(2, -1.3, 0),
  };
}

/** The board by the window: each runner's number, its silks and its odds, «40/1». */
function oddsArt(runners: Runner[]) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = css(mix(INKS.ink, INKS.green, 0.2));
    ctx.fillRect(0, 0, w, h);
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'center';
    ctx.fillStyle = css(INKS.sunflower);
    const head = fitText(ctx, 'LES PARTANTS · LA COTE', w * 0.9, Math.round(h * 0.07), '700 {s}px "Helvetica Neue", Arial, sans-serif');
    ctx.font = `700 ${head}px "Helvetica Neue", Arial, sans-serif`;
    ctx.fillText('LES PARTANTS · LA COTE', w / 2, h * 0.075);
    const rows = Math.ceil(runners.length / 2);
    const top = h * 0.16;
    const row = (h * 0.81) / rows;
    runners.forEach((r, i) => {
      const col = i < rows ? 0 : 1;
      const x = (col * w) / 2 + w * 0.05;
      const y = top + row * ((i % rows) + 0.5);
      // the silks: the jacket, and the cap on it
      ctx.fillStyle = css(r.silks.body);
      ctx.fillRect(x, y - row * 0.22, row * 0.5, row * 0.5);
      ctx.fillStyle = css(r.silks.cap);
      ctx.beginPath();
      ctx.arc(x + row * 0.25, y - row * 0.25, row * 0.17, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = css(INKS.card);
      ctx.textAlign = 'left';
      ctx.font = `700 ${Math.round(row * 0.58)}px Georgia, 'Times New Roman', serif`;
      ctx.fillText(String(r.n), x + row * 0.7, y + row * 0.03);
      ctx.fillStyle = css(INKS.sunflower);
      ctx.textAlign = 'right';
      ctx.font = `700 ${Math.round(row * 0.5)}px "Helvetica Neue", Arial, sans-serif`;
      ctx.fillText(`${r.odds}/1`, ((col + 1) * w) / 2 - w * 0.05, y + row * 0.03);
    });
  };
}

/** A line of capitals on a band of colour. */
function letters(text: string, ink: string, ground: string) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = ground;
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = ink;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const size = fitText(ctx, text, w * 0.94, Math.round(h * 0.62), '700 {s}px "Helvetica Neue", Arial, sans-serif');
    ctx.font = `700 ${size}px "Helvetica Neue", Arial, sans-serif`;
    ctx.fillText(text, w / 2, h * 0.54);
  };
}

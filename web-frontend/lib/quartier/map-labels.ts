/**
 * Le Quartier · where La Carte writes each pin's name (P12 stage 6).
 *
 * Observed 17 Nov (`quartier-q-roam-map-all.png`): every name was written to the right of its pin
 * at full length, so «L'hippodrome de ParisLongchamp» ran over «L'hémicycle de l'Assemblée
 * nationale», the mairie's over the gare's, and in «Ton quartier» names ran off the right edge.
 *
 * Each name now takes the first place that is free, in the map's own units: to the right of its
 * pin, to the left, above, below; at full length, then without its complement («L'hippodrome»),
 * then cut with «…». Free means inside the frame and over no other name or pin. A name that finds
 * no place is left off: the pin is still there, and its card says the name. The pin you are at is
 * placed first, then the open places, then the rest.
 *
 * Widths are measured where the map can measure them (round 3: `a1-d3-q-map.png`, the estimate ran
 * short and «Le q…» touched the frame and the red ring): La Carte hands `placeLabels` a canvas
 * `measureText` with its own label font once it is in a browser; the server render and the tests
 * use the estimate (about half an em a letter). The halo the label is drawn with (its stroke) is
 * part of its box, a name keeps clear of its own pin's ring, and the district numbers are avoided
 * where a free place exists without them.
 */

export type XY = [number, number];

export interface LabelPin {
  id: string;
  name: string;
  xy: XY;
  /** placed before the others: where you are, then the open places */
  rank: number;
  /** the pin you are at: drawn with its ring */
  here?: boolean;
}

export interface PlacedLabel {
  id: string;
  text: string;
  x: number;
  y: number;
  anchor: 'start' | 'middle' | 'end';
  /** the box the name covers: x0, y0, x1, y1 */
  rect: [number, number, number, number];
}

/** An em of the map's label font, in letters: a serif italic runs narrower than its size. */
export const LETTER_EM = 0.52;

/** The name's size and the gap to its pin, in units of the map (`u`, a hundredth of the frame). */
export const LABEL = { size: 3.4, gap: 2.6, dot: 1.7, margin: 1 };

/**
 * A pin as drawn, in units of the map: the dot (`r` 1.7) with its stroke (0.45 wide, half outside),
 * the ring round the pin you are at (`r` 3.2, stroke 0.5), and the paper kept between two pins.
 */
export const PIN = { dot: 1.7 + 0.45 / 2, ring: 3.2 + 0.5 / 2, apart: 0.6 };

/** How far a pin reaches from its centre, in units of the map. */
export function pinReach(here: boolean): number {
  return here ? PIN.ring : PIN.dot;
}

/**
 * Where each pin is drawn so that none touches another (round 2, walk 17 Nov, `a1-d3-q-map.png`:
 * the gare de l’Est, the mairie du 10e and the quai sit a few hundred metres apart, and at the
 * map's scale their grey dots and the red ring ran into each other). Pins that would touch are
 * pushed apart along the line between them, the pin you are at never moves; a pin moves no
 * further than it must. Deterministic: the same map on the server, in a test and on a phone.
 */
export function spreadPins(pins: Array<{ id: string; xy: XY; here?: boolean }>, u: number): Map<string, XY> {
  const at = pins.map((p) => [p.xy[0], p.xy[1]] as XY);
  for (let round = 0; round < 60; round++) {
    let moved = false;
    for (let i = 0; i < pins.length; i++) {
      for (let j = i + 1; j < pins.length; j++) {
        const need = (pinReach(Boolean(pins[i].here)) + pinReach(Boolean(pins[j].here)) + PIN.apart) * u;
        let dx = at[j][0] - at[i][0];
        let dy = at[j][1] - at[i][1];
        let d = Math.hypot(dx, dy);
        if (d >= need - 1e-9) continue;
        if (d < 1e-9) {
          // one on the other: part them along a fixed bearing, by their order
          const a = ((i * 7 + j * 3) % 8) * (Math.PI / 4);
          dx = Math.cos(a);
          dy = Math.sin(a);
          d = 1;
        }
        const ux = dx / d;
        const uy = dy / d;
        const push = need - Math.hypot(at[j][0] - at[i][0], at[j][1] - at[i][1]);
        const [si, sj] = pins[i].here ? [0, 1] : pins[j].here ? [1, 0] : [0.5, 0.5];
        at[i] = [at[i][0] - ux * push * si, at[i][1] - uy * push * si];
        at[j] = [at[j][0] + ux * push * sj, at[j][1] + uy * push * sj];
        moved = true;
      }
    }
    if (!moved) break;
  }
  return new Map(pins.map((p, i) => [p.id, at[i]]));
}

export function textWidth(text: string, size: number): number {
  return Array.from(text).length * LETTER_EM * size;
}

/** A label's width in the map's units at font size `size` (La Carte's `measureText`, or `textWidth`). */
export type Measure = (text: string, size: number) => number;

/** The label's halo (the stroke it is drawn with, `strokeWidth` 0.9u, half outside) and the paper kept round a pin, in units of the map. */
export const HALO = 0.45;
export const CLEAR = 0.8;

/** The fewest letters a cut name keeps before its «…» («Le q…» says nothing). */
export const CUT_MIN = 6;

/** «L'hippodrome de ParisLongchamp» -> «L'hippodrome»; a name with no complement has no short form. */
export function shortName(name: string): string | null {
  const m = /^(.+?)\s+(?:de|du|des|d['’])\s*\S/.exec(name);
  return m && m[1].length >= 4 ? m[1] : null;
}

type Rect = [number, number, number, number];
const overlaps = (a: Rect, b: Rect) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];

export interface LabelOptions {
  /** the label font's real widths, where the map can measure them */
  measure?: Measure | null;
  /** boxes a name should not cover if it can help it (the district numbers) */
  avoid?: Rect[];
}

/** Where each pin's name goes inside `box` (x, y, width, height), or no entry when none fits. */
export function placeLabels(pins: LabelPin[], box: [number, number, number, number], u: number, opts: LabelOptions = {}): PlacedLabel[] {
  const size = LABEL.size * u;
  const halo = HALO * u;
  const widthOf = (t: string) => (opts.measure ? opts.measure(t, size) : textWidth(t, size)) + 2 * halo;
  const half = size * 0.6 + halo;
  const m = LABEL.margin * u;
  const frame: Rect = [box[0] + m, box[1] + m, box[0] + box[2] - m, box[1] + box[3] - m];
  const inside = (r: Rect) => r[0] >= frame[0] && r[1] >= frame[1] && r[2] <= frame[2] && r[3] <= frame[3];
  // every pin as drawn: the dot and its stroke, the ring round the pin you are at
  const marks = pins.map((p): Rect => {
    const r = pinReach(Boolean(p.here)) * u;
    return [p.xy[0] - r, p.xy[1] - r, p.xy[0] + r, p.xy[1] + r];
  });
  const placed: PlacedLabel[] = [];
  const order = [...pins].sort((a, b) => a.rank - b.rank);
  for (const pin of order) {
    const [x, y] = pin.xy;
    // the name starts clear of its own pin as drawn (round 3: the ring of the pin you are at ran into it)
    const gap = Math.max(LABEL.gap, pinReach(Boolean(pin.here)) + CLEAR) * u;
    const texts = [pin.name, shortName(pin.name)].filter((t): t is string => Boolean(t));
    // last, the name cut to what fits beside the pin, never to fewer than CUT_MIN letters
    const cut = (room: number) => {
      const letters = Array.from(pin.name);
      for (let n = letters.length - 1; n >= CUT_MIN; n--) {
        const t = `${letters.slice(0, n).join('').trimEnd()}…`;
        if (widthOf(t) <= room) return t;
      }
      return null;
    };
    // the text is drawn at (x, y); its box takes the halo on every side
    const sides = (t: string): PlacedLabel[] => {
      const w = widthOf(t);
      return [
        { id: pin.id, text: t, x: x + gap + halo, y, anchor: 'start', rect: [x + gap, y - half, x + gap + w, y + half] },
        { id: pin.id, text: t, x: x - gap - halo, y, anchor: 'end', rect: [x - gap - w, y - half, x - gap, y + half] },
        { id: pin.id, text: t, x, y: y - gap - half, anchor: 'middle', rect: [x - w / 2, y - gap - 2 * half, x + w / 2, y - gap] },
        { id: pin.id, text: t, x, y: y + gap + half, anchor: 'middle', rect: [x - w / 2, y + gap, x + w / 2, y + gap + 2 * half] },
      ];
    };
    const free = (c: PlacedLabel, avoid: Rect[]) =>
      inside(c.rect) &&
      !placed.some((p) => overlaps(p.rect, c.rect)) &&
      !marks.some((d, i) => pins[i].id !== pin.id && overlaps(d, c.rect)) &&
      !avoid.some((a) => overlaps(a, c.rect));
    const first = (candidates: string[]) => {
      for (const avoid of [opts.avoid ?? [], []]) {
        for (const t of candidates) {
          const best = sides(t).find((c) => free(c, avoid));
          if (best) return best;
        }
      }
      return null;
    };
    const best = first(texts) ?? first([cut(frame[2] - (x + gap)), cut(x - gap - frame[0])].filter((t): t is string => Boolean(t)));
    if (best) placed.push(best);
  }
  return placed;
}

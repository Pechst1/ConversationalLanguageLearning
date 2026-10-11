/**
 * WP-144 «La page verticale» · where each balloon goes, and what goes to the sheet.
 *
 * The one rule that is never broken: **a balloon, a caption or a tail never
 * covers a face.** Everything else bends to it.
 *
 * WP-144b, after the owner's blind A/B lost the three-speaker panels:
 *
 *   · a spoken line sits near its speaker: just above the head (the tail points
 *     down at it), else beside it. A tail is never longer than `tailMax` (15 %
 *     of the panel's height) and never crosses another balloon;
 *   · reading order: captions first, top left; then each line is clearly lower
 *     than the one said before it, or to its right on the same row;
 *   · when the lines cannot all sit near their speakers, the oldest go to the
 *     sheet (and are revealed first), rather than any line hanging on a long
 *     tail. When dropping from the end keeps more lines on the picture, the
 *     newest go instead; the sheet never holds a hole in the dialogue.
 *
 * The learner's own line (a reply, or the story's «Vous») is docked at the
 * bottom edge, full width, without a tail: the point-of-view position (WP-146).
 * It is placed first, stands outside the reading order of the cast, and never
 * covers a face; when it would, it goes to the sheet and the caller raises the
 * figures (`HEAD_LINE_DROPS`).
 *
 * Pure: sizes in, positions out. The component measures the balloons (so text
 * scaling and «Traduire» are honoured), calls `layoutPanel`, and draws.
 */

import type { Box, HeadBox, Size } from './page-geometry';

export type LayoutKind = 'caption' | 'speech' | 'you';

export type LayoutItem = {
  key: string;
  kind: LayoutKind;
  size: Size;
  /** The speaker's head (index into `heads`), or -1 for none on stage. */
  anchor: number;
};

export type Tail = { side: 'down' | 'left' | 'right'; baseX: number; baseY: number; tipX: number; tipY: number };

export type Placed = Box & { key: string; kind: LayoutKind; anchor: number; tail: Tail | null };

export type SheetMode = 'none' | 'dock' | 'below';

export type PanelLayout = {
  placed: Placed[];
  /** Keys that did not fit, in reading order: the sheet's lines. */
  overflow: string[];
  sheet: { mode: SheetMode; maxHeight: number };
};

export type LayoutOptions = {
  /** Clear space from the panel's edges. */
  margin?: number;
  /** Space between two balloons, and between a balloon and a face. */
  gap?: number;
  /** Space kept at the top (a state chip drawn over the panel). */
  topInset?: number;
  /** Space kept at the foot. */
  bottomInset?: number;
  /**
   * The faces are not known (a painted panel draws its people into the picture):
   * lines without a head stay in the top `unknownZone` of the panel, and the
   * sheet goes below the panel rather than over it.
   */
  unknownFaces?: boolean;
  unknownZone?: number;
  /** The smallest docked sheet worth drawing; below it the sheet goes under the panel. */
  minSheet?: number;
};

const TAIL_IDEAL = 22;
/** A tail is never longer than this share of the panel's height. */
export const TAIL_MAX_SHARE = 0.15;
/** A line said later starts at least this much lower than the one before (unless it is to its right). */
const READ_STEP = 24;
/** Half a tail's width at its base, and the clearance a tail keeps from a balloon. */
const TAIL_HALF = 7;
/** How many places are tried per line, and how much searching a panel may cost. */
const CANDIDATES_PER_LINE = 14;
const SEARCH_BUDGET = 2500;

export function intersects(a: Box, b: Box, pad = 0): boolean {
  return a.x < b.x + b.w + pad && b.x < a.x + a.w + pad && a.y < b.y + b.h + pad && b.y < a.y + a.h + pad;
}

function clamp(value: number, min: number, max: number): number {
  if (max < min) return min;
  return Math.min(Math.max(value, min), max);
}

type Ctx = {
  panel: Size;
  heads: HeadBox[];
  margin: number;
  gap: number;
  top: number;
  bottom: number;
  unknownFaces: boolean;
  unknownZone: number;
  tailMax: number;
};

export function tailLength(tail: Tail): number {
  return Math.hypot(tail.tipX - tail.baseX, tail.tipY - tail.baseY);
}

/** Points along a tail, from just off its balloon to just short of its tip. */
function tailPoints(tail: Tail, steps = 24): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  for (let step = 1; step < steps; step += 1) {
    const t = step / steps;
    out.push([tail.baseX + (tail.tipX - tail.baseX) * t, tail.baseY + (tail.tipY - tail.baseY) * t]);
  }
  return out;
}

function inside(point: [number, number], box: Box, pad = 0): boolean {
  return point[0] > box.x - pad && point[0] < box.x + box.w + pad && point[1] > box.y - pad && point[1] < box.y + box.h + pad;
}

/** Does this tail run over (or within a tail's half width of) the box? */
export function tailCrosses(tail: Tail, box: Box, pad = TAIL_HALF): boolean {
  return tailPoints(tail).some((point) => inside(point, box, pad));
}

function clear(box: Box, ctx: Ctx, placed: Box[]): boolean {
  if (box.x < ctx.margin - 0.5 || box.x + box.w > ctx.panel.w - ctx.margin + 0.5) return false;
  if (box.y < ctx.top - 0.5 || box.y + box.h > ctx.bottom + 0.5) return false;
  if (ctx.heads.some((head) => intersects(box, head))) return false;
  return !placed.some((other) => intersects(box, other, ctx.gap - 0.5));
}

function tailFor(box: Box, head: HeadBox, side: Tail['side']): Tail {
  const cx = head.x + head.w / 2;
  if (side === 'down') {
    const baseX = clamp(cx, box.x + 18, box.x + box.w - 18);
    return { side, baseX, baseY: box.y + box.h, tipX: clamp(cx, head.x + head.w * 0.25, head.x + head.w * 0.75), tipY: head.y };
  }
  const tipY = head.y + head.h * 0.4;
  const baseY = clamp(tipY, box.y + 14, box.y + box.h - 14);
  return side === 'left'
    ? { side, baseX: box.x + box.w, baseY, tipX: head.x, tipY }
    : { side, baseX: box.x, baseY, tipX: head.x + head.w, tipY };
}

/** Is `next` read after `prev`? Clearly lower (wholly lower when it sits to the left), or to its right on the same row. */
export function readsAfter(next: Box, prev: Box): boolean {
  const right = next.x >= prev.x + prev.w - 2 && next.y >= prev.y - 4;
  if (right) return true;
  if (next.y < prev.y + READ_STEP) return false;
  const leftOf = next.x + next.w / 2 < prev.x + prev.w / 2 - 1;
  return !leftOf || next.y >= prev.y + prev.h;
}

type State = { placed: Placed[]; overflow: string[]; cursor: number; spoken: number };

function fits(candidate: Placed, ctx: Ctx, state: State): boolean {
  const boxes = state.placed as Box[];
  if (!clear(candidate, ctx, boxes)) return false;
  // No placed tail may run over the new balloon.
  if (state.placed.some((entry) => entry.tail && tailCrosses(entry.tail, candidate))) return false;
  const tail = candidate.tail;
  if (tail) {
    if (tailLength(tail) > ctx.tailMax + 0.5) return false;
    if (state.placed.some((entry) => tailCrosses(tail, entry))) return false;
    // A tail runs to its own speaker, over nobody else's face.
    if (ctx.heads.some((head, index) => index !== candidate.anchor && tailCrosses(tail, head, 0))) return false;
  }
  if (candidate.kind === 'speech') {
    for (const prev of state.placed) {
      if (prev.kind === 'speech' && !readsAfter(candidate, prev)) return false;
    }
  }
  return true;
}

/** The places a line could go, best first, that fit what is already placed. */
function candidatesFor(item: LayoutItem, ctx: Ctx, state: State): Placed[] {
  const w = Math.min(item.size.w, ctx.panel.w - ctx.margin * 2);
  const h = item.size.h;
  const make = (box: Box, anchor: number, tail: Tail | null): Placed => ({ ...box, key: item.key, kind: item.kind, anchor, tail });
  const out: Placed[] = [];
  const offer = (candidate: Placed) => {
    if (out.length >= CANDIDATES_PER_LINE) return;
    if (out.some((other) => Math.abs(other.x - candidate.x) < 2 && Math.abs(other.y - candidate.y) < 2)) return;
    if (fits(candidate, ctx, state)) out.push(candidate);
  };

  if (item.kind === 'caption') {
    offer(make({ x: ctx.margin, y: state.cursor, w, h }, -1, null));
    return out;
  }
  if (item.kind === 'you') {
    // The point of view: docked at the bottom edge, full width, no tail; a second
    // line of the learner's stacks above the first.
    const full = ctx.panel.w - ctx.margin * 2;
    const floor = state.placed.filter((entry) => entry.kind === 'you').reduce((low, entry) => Math.min(low, entry.y - ctx.gap), ctx.bottom);
    const box = { x: ctx.margin, y: floor - h, w: full, h };
    if (box.y >= ctx.top) offer(make(box, -1, null));
    return out;
  }

  const head = item.anchor >= 0 ? ctx.heads[item.anchor] : undefined;
  if (head) {
    const cx = head.x + head.w / 2;
    const ideal = clamp(cx - w / 2, ctx.margin, ctx.panel.w - ctx.margin - w);
    const prevLines = state.placed.filter((entry) => entry.kind === 'speech');
    // Where to try: centred on the head, offset either way, against the edges,
    // and just right of each line already placed (the next one on the same row).
    const xs = [cx - w / 2, cx - w * 0.3, cx - w * 0.7, ctx.margin, ctx.panel.w - ctx.margin - w, ...prevLines.map((prev) => prev.x + prev.w + ctx.gap)]
      .map((x) => clamp(x, ctx.margin, ctx.panel.w - ctx.margin - w))
      .sort((a, b) => Math.abs(a - ideal) - Math.abs(b - ideal));
    // How high: from the ideal tail to the longest, and just under each line placed.
    const dys = new Set<number>();
    for (let dy = TAIL_IDEAL; dy <= ctx.tailMax; dy += 12) dys.add(dy);
    dys.add(ctx.tailMax);
    for (const prev of prevLines) {
      for (const y of [prev.y + prev.h + ctx.gap, prev.y + READ_STEP]) {
        const dy = head.y - h - y;
        if (dy >= TAIL_IDEAL - 10 && dy <= ctx.tailMax) dys.add(dy);
      }
    }
    // Above the head, nearest first, never further than a tail may reach.
    // At most two places per height, so the search also sees the higher ones.
    for (const dy of Array.from(dys).sort((a, b) => a - b)) {
      const before = out.length;
      for (const x of xs) {
        if (out.length - before >= 2) break;
        const box = { x, y: head.y - dy - h, w, h };
        offer(make(box, item.anchor, tailFor(box, head, 'down')));
      }
    }
    // Beside it.
    for (const side of ['left', 'right'] as const) {
      const x = side === 'left' ? head.x - ctx.gap - w : head.x + head.w + ctx.gap;
      for (const y of [head.y + head.h * 0.4 - h / 2, head.y - h / 2, head.y + head.h * 0.7 - h / 2]) {
        const box = { x, y, w, h };
        offer(make(box, item.anchor, tailFor(box, head, side)));
      }
    }
    return out;
  }

  // A voice with no face on stage (or a painted panel): the first place, from the
  // top, that reads after the lines before it; left, right, left…
  const sides = state.spoken % 2 === 0 ? [ctx.margin, ctx.panel.w - ctx.margin - w] : [ctx.panel.w - ctx.margin - w, ctx.margin];
  const limit = ctx.unknownFaces ? Math.min(ctx.bottom, ctx.panel.h * ctx.unknownZone) : ctx.bottom;
  for (let y = state.cursor; y + h <= limit + 0.5; y += 6) {
    for (const x of sides) offer(make({ x, y, w, h }, -1, null));
    if (out.length >= 2) break;
  }
  return out;
}

function advance(state: State, entry: Placed): State {
  return {
    placed: [...state.placed, entry],
    overflow: state.overflow,
    cursor: entry.kind === 'caption' ? entry.y + entry.h + 8 : state.cursor,
    spoken: state.spoken + (entry.kind === 'speech' ? 1 : 0),
  };
}

function skip(state: State, key: string): State {
  return { ...state, overflow: [...state.overflow, key] };
}

/**
 * Place every item not in `forced`, searching (with backtracking) for a place
 * for each spoken line. Captions and the learner's line may go to the sheet on
 * their own; a spoken line may not (the caller decides which lines leave).
 */
function search(items: LayoutItem[], ctx: Ctx, forced: Set<string>): State | null {
  let budget = SEARCH_BUDGET;
  const walk = (index: number, state: State): State | null => {
    if (index >= items.length) return state;
    if (budget <= 0) return null;
    budget -= 1;
    const item = items[index];
    if (forced.has(item.key)) return walk(index + 1, skip(state, item.key));
    const options = candidatesFor(item, ctx, state);
    for (const option of options) {
      const done = walk(index + 1, advance(state, option));
      if (done) return done;
    }
    // A caption or the learner's line leaves the picture only when it has no
    // place at all, never to make room for the lines after it.
    if (item.kind !== 'speech' && !options.length) return walk(index + 1, skip(state, item.key));
    return null;
  };
  return walk(0, { placed: [], overflow: [], cursor: ctx.top, spoken: 0 });
}

/** The old way, kept as the fallback: place in order, and send the rest to the sheet from the first line that does not fit. */
function greedy(items: LayoutItem[], ctx: Ctx, forced: Set<string>): State {
  let state: State = { placed: [], overflow: [], cursor: ctx.top, spoken: 0 };
  let stopped = false;
  for (const item of items) {
    if (stopped || forced.has(item.key)) {
      state = skip(state, item.key);
      continue;
    }
    const [best] = candidatesFor(item, ctx, state);
    if (best) state = advance(state, best);
    else {
      if (item.kind === 'speech') stopped = true;
      state = skip(state, item.key);
    }
  }
  return state;
}

function placeAll(allItems: LayoutItem[], ctx: Ctx, forced: Set<string>): { placed: Placed[]; overflow: string[] } {
  // The learner's lines are not anchored to a head: they take the bottom band
  // first, and the cast's balloons are placed around them.
  const items = [...allItems.filter((item) => item.kind === 'you'), ...allItems.filter((item) => item.kind !== 'you')];
  const spoken = items.filter((item) => item.kind === 'speech').map((item) => item.key);
  let oldest: State | null = null;
  for (let k = 0; k <= spoken.length && !oldest; k += 1) {
    oldest = search(items, ctx, new Set(Array.from(forced).concat(spoken.slice(0, k))));
  }
  const newest = greedy(items, ctx, forced);
  const best = oldest && oldest.placed.length >= newest.placed.length ? oldest : newest;
  // The sheet reads in the dialogue's order.
  const order = new Map(allItems.map((item, index) => [item.key, index] as const));
  return { placed: best.placed, overflow: [...best.overflow].sort((a, b) => (order.get(a) ?? 0) - (order.get(b) ?? 0)) };
}

/** The lowest face's foot: the sheet may dock only beneath it. */
function lowestFace(heads: HeadBox[]): number {
  return heads.reduce((low, head) => Math.max(low, head.y + head.h), 0);
}

/**
 * Lay out one panel. Items are in reading order: captions, then the lines as
 * they are said (the learner's among them).
 */
export function layoutPanel(panel: Size, heads: HeadBox[], items: LayoutItem[], options: LayoutOptions = {}): PanelLayout {
  const margin = options.margin ?? 12;
  const gap = options.gap ?? 8;
  const unknownFaces = Boolean(options.unknownFaces);
  const minSheet = options.minSheet ?? 96;
  const base: Ctx = {
    panel,
    heads,
    margin,
    gap,
    top: (options.topInset ?? 0) + margin,
    bottom: panel.h - (options.bottomInset ?? 0) - margin,
    unknownFaces,
    unknownZone: options.unknownZone ?? 0.4,
    tailMax: panel.h * TAIL_MAX_SHARE,
  };

  let ctx = base;
  let forced = new Set<string>();
  let result = placeAll(items, ctx, forced);
  let sheet: PanelLayout['sheet'] = { mode: 'none', maxHeight: 0 };

  // Something did not fit: the sheet takes the rest. Docked over the panel's foot
  // when there is room under the lowest face; under the panel otherwise. A docked
  // sheet takes room from the panel, so lay out again with it (a few times at most).
  for (let round = 0; round < 4 && result.overflow.length; round += 1) {
    const room = heads.length ? panel.h - (options.bottomInset ?? 0) - lowestFace(heads) - gap : panel.h * 0.5;
    if (unknownFaces || room < minSheet) {
      sheet = { mode: 'below', maxHeight: 0 };
      break;
    }
    const sizes = new Map(items.map((item) => [item.key, item.size.h] as const));
    const wanted = result.overflow.reduce((sum, key) => sum + (sizes.get(key) ?? 0) + gap, 24);
    const height = Math.min(room, Math.max(minSheet, wanted));
    sheet = { mode: 'dock', maxHeight: Math.floor(room) };
    // The learner's balloon joins the sheet: one place at the foot, not two.
    forced = new Set(items.filter((item) => item.kind === 'you').map((item) => item.key));
    ctx = { ...base, bottom: Math.min(base.bottom, panel.h - height - gap) };
    const next = placeAll(items, ctx, forced);
    const same = next.overflow.length === result.overflow.length;
    result = next;
    if (same) break;
  }

  return { placed: result.placed, overflow: result.overflow, sheet: result.overflow.length ? sheet : { mode: 'none', maxHeight: 0 } };
}

/** For tests and QA: does any placed box, or any tail short of its tip, touch a face? */
export function coversAFace(layout: PanelLayout, heads: HeadBox[]): boolean {
  const inside = (x: number, y: number) => heads.some((head) => x > head.x && x < head.x + head.w && y > head.y && y < head.y + head.h);
  return layout.placed.some((entry) => {
    if (heads.some((head) => intersects(entry, head))) return true;
    const tail = entry.tail;
    if (!tail) return false;
    for (let step = 0; step <= 19; step += 1) {
      const t = step / 20;
      if (inside(tail.baseX + (tail.tipX - tail.baseX) * t, tail.baseY + (tail.tipY - tail.baseY) * t)) return true;
    }
    return false;
  });
}

/**
 * WP-144 «La page verticale» · where each balloon goes, and what goes to the sheet.
 *
 * The one rule that is never broken: **a balloon, a caption or a tail never
 * covers a face.** Everything else bends to it: a line that cannot be placed
 * clear of every head goes to the bottom sheet, and so does every line after
 * it, so the dialogue is still read in order.
 *
 * Reading order is top to bottom: narration captions first, at the top left,
 * then the spoken lines in the order they are said, each one no higher than the
 * one before. A spoken line sits above its speaker's head (the tail points down
 * at them), else beside it, else under it on the torso. The learner's own line
 * is the balloon at the bottom right, the point-of-view position (WP-146).
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

const TAIL_MIN = 12;
const TAIL_IDEAL = 26;

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
};

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

/** One pass: place what fits, in order, and stop at the first line that does not. */
function placeAll(items: LayoutItem[], ctx: Ctx, forceSheet: Set<string>): { placed: Placed[]; overflow: string[] } {
  const placed: Placed[] = [];
  const overflow: string[] = [];
  let cursor = ctx.top;
  let spoken = 0;
  let stopped = false;
  const boxes = () => placed.map((entry) => entry as Box);

  for (const item of items) {
    if (stopped || forceSheet.has(item.key)) {
      // The learner's line can go to the sheet without stopping the flow above it.
      if (!stopped && item.kind !== 'you') stopped = true;
      overflow.push(item.key);
      continue;
    }
    const w = Math.min(item.size.w, ctx.panel.w - ctx.margin * 2);
    const h = item.size.h;
    let chosen: Placed | null = null;

    if (item.kind === 'caption') {
      const box = { x: ctx.margin, y: cursor, w, h };
      if (clear(box, ctx, boxes())) chosen = { ...box, key: item.key, kind: item.kind, anchor: -1, tail: null };
    } else if (item.kind === 'you') {
      const box = { x: ctx.panel.w - ctx.margin - w, y: ctx.bottom - h, w, h };
      if (box.y >= ctx.top && clear(box, ctx, boxes())) chosen = { ...box, key: item.key, kind: item.kind, anchor: -1, tail: null };
    } else {
      const head = item.anchor >= 0 ? ctx.heads[item.anchor] : undefined;
      if (head) {
        const cx = head.x + head.w / 2;
        const candidates: Array<{ box: Box; side: Tail['side'] }> = [
          // above the head, flowing down from the line before
          { box: { x: clamp(cx - w / 2, ctx.margin, ctx.panel.w - ctx.margin - w), y: cursor, w, h }, side: 'down' },
          // beside it
          { box: { x: head.x - ctx.gap - w, y: Math.max(cursor, head.y), w, h }, side: 'left' },
          { box: { x: head.x + head.w + ctx.gap, y: Math.max(cursor, head.y), w, h }, side: 'right' },
        ];
        for (const candidate of candidates) {
          const { box, side } = candidate;
          if (side === 'down' && box.y + box.h > head.y - TAIL_MIN) continue;
          if (clear(box, ctx, boxes())) {
            chosen = { ...box, key: item.key, kind: item.kind, anchor: item.anchor, tail: tailFor(box, head, side) };
            break;
          }
        }
      } else {
        // A voice with no face on stage (or a painted panel): left, right, left…
        const x = spoken % 2 === 0 ? ctx.margin : ctx.panel.w - ctx.margin - w;
        const box = { x, y: cursor, w, h };
        const zoneOk = !ctx.unknownFaces || box.y + box.h <= ctx.panel.h * ctx.unknownZone;
        if (zoneOk && clear(box, ctx, boxes())) chosen = { ...box, key: item.key, kind: item.kind, anchor: -1, tail: null };
      }
    }

    if (!chosen) {
      if (item.kind !== 'you') stopped = true;
      overflow.push(item.key);
      continue;
    }
    placed.push(chosen);
    if (item.kind !== 'you') cursor = chosen.y + chosen.h + ctx.gap;
    if (item.kind === 'speech') spoken += 1;
  }
  return { placed, overflow };
}

/**
 * Bring each balloon placed above its speaker down toward them (a short tail
 * reads better than a long one), never past the balloon under it, never onto a
 * face, and never above where it already was.
 */
function settle(placed: Placed[], ctx: Ctx): Placed[] {
  const out = placed.map((entry) => ({ ...entry }));
  for (let i = out.length - 1; i >= 0; i -= 1) {
    const entry = out[i];
    if (entry.kind !== 'speech' || entry.tail?.side !== 'down' || entry.anchor < 0) continue;
    const head = ctx.heads[entry.anchor];
    let limit = head.y - TAIL_IDEAL - entry.h;
    for (let j = i + 1; j < out.length; j += 1) {
      const below = out[j];
      const overlapsX = below.x < entry.x + entry.w + ctx.gap && entry.x < below.x + below.w + ctx.gap;
      if (overlapsX) limit = Math.min(limit, below.y - ctx.gap - entry.h);
      // Reading order: never lower than a line said after it.
      if (below.kind === 'speech') limit = Math.min(limit, below.y);
    }
    const others = out.filter((_, index) => index !== i);
    let y = Math.max(entry.y, limit);
    while (y > entry.y && !clear({ x: entry.x, y, w: entry.w, h: entry.h }, ctx, others)) y -= 4;
    if (y > entry.y) {
      out[i] = { ...entry, y, tail: tailFor({ x: entry.x, y, w: entry.w, h: entry.h }, head, 'down') };
    }
  }
  return out;
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

  return { placed: settle(result.placed, ctx), overflow: result.overflow, sheet: result.overflow.length ? sheet : { mode: 'none', maxHeight: 0 } };
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

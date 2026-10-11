/**
 * WP-143 «One stage, one light» · where the drawn cast stands, and the rule that a
 * face is never cropped (finding C-8).
 *
 * Every figure is laid out in the stage's own percentages (left/height/bottom, as the
 * stage's CSS draws it), then each rig's head box (its authored `crops.head`, read in
 * the crop the stage draws) is checked against the frame and the figure is moved, or
 * if it must be, shrunk, until the whole head sits inside. Bodies may be cut by the
 * frame; heads may not.
 *
 *   band  the reader's and the Revue's plate: busts sized by the stage's height,
 *         standing on the bottom edge (the layout of WP-116 phase 3).
 *   fill  a full-bleed crop (WP-144's 9:16 page): whole figures standing on a ground
 *         line, sized so that every head fits side by side, grouped on `focus.x`.
 *
 * Pure: no React, no DOM. `plateObjectPosition` gives the CSS object-position that
 * keeps a focus point of a plate in view when the plate is cropped to the stage.
 */
import type { RigCrop, RigDef } from '@/components/cast/rig-kit';

export type StageFraming = 'band' | 'fill';

/** A point as fractions (0–1) of the plate (fill) or of the stage (band), from the top left. */
export type FocusPoint = { x: number; y: number };

/** A box in percent of the stage: x and w of its width, y and h of its height (from the top). */
export type HeadBox = { x: number; y: number; w: number; h: number };

export type FigurePlacement = {
  rigId: string;
  front: boolean;
  /** The crop the figure is drawn in (`bust` in band, `full` in fill). */
  crop: Extract<RigCrop, 'bust' | 'full'>;
  /** centre, % of the stage's width */
  centre: number;
  /** height, % of the stage's height */
  height: number;
  /** bottom edge, % of the stage's height above the stage's bottom (negative: below it) */
  bottom: number;
  zIndex: number;
  /** the head, % of the stage */
  head: HeadBox;
};

export type LayoutMember = { rigId: string; speaking?: boolean };

/** The margin a head keeps from every edge, % of the stage. */
export const HEAD_MARGIN = 2;

const BAND_SLOTS: Record<number, Array<{ centre: number; height: number; lift: number }>> = {
  1: [{ centre: 50, height: 92, lift: 0 }],
  2: [
    { centre: 31, height: 88, lift: 0 },
    { centre: 69, height: 88, lift: 0 },
  ],
  3: [
    { centre: 20, height: 82, lift: 0 },
    { centre: 50, height: 82, lift: 8 },
    { centre: 80, height: 82, lift: 0 },
  ],
};

/** fill: the tallest a standing figure may be, by how many stand (% of the stage's height). */
const FILL_HEIGHT: Record<number, number> = { 1: 64, 2: 60, 3: 54 };
/** fill: the ground line, % above the stage's bottom (the feet and their contact shadow show). */
const FILL_GROUND = 3;

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

/** The crop box's width ÷ height (bust 180:220, full 200:420). */
export function cropRatio(rig: Pick<RigDef, 'crops'>, crop: 'bust' | 'full'): number {
  const box = rig.crops[crop];
  return box[2] / box[3];
}

/**
 * The rig's head (its authored `crops.head`) as fractions of the given crop, clipped
 * to the crop: x, y from the crop's top left, w, h of its width and height.
 */
export function headFraction(rig: Pick<RigDef, 'crops'>, crop: 'bust' | 'full'): { x: number; y: number; w: number; h: number } {
  const [cx, cy, cw, ch] = rig.crops[crop];
  const [hx, hy, hw, hh] = rig.crops.head;
  const left = clamp((hx - cx) / cw, 0, 1);
  const top = clamp((hy - cy) / ch, 0, 1);
  const right = clamp((hx + hw - cx) / cw, 0, 1);
  const bottom = clamp((hy + hh - cy) / ch, 0, 1);
  return { x: left, y: top, w: right - left, h: bottom - top };
}

/** Where the head of a figure falls on the stage, in % of the stage. */
export function headBox(
  rig: Pick<RigDef, 'crops'>,
  crop: 'bust' | 'full',
  placement: { centre: number; height: number; bottom: number },
  aspect: number,
): HeadBox {
  const f = headFraction(rig, crop);
  const width = (placement.height * cropRatio(rig, crop)) / aspect;
  const left = placement.centre - width / 2;
  const top = 100 - placement.bottom - placement.height;
  return { x: left + f.x * width, y: top + f.y * placement.height, w: f.w * width, h: f.h * placement.height };
}

/** True when the whole box lies inside the stage, `margin` % from every edge. */
export function boxInFrame(box: HeadBox, margin = 0): boolean {
  const eps = 1e-6;
  return (
    box.x >= margin - eps &&
    box.y >= margin - eps &&
    box.x + box.w <= 100 - margin + eps &&
    box.y + box.h <= 100 - margin + eps
  );
}

/**
 * Moves (and, only if a head is larger than the frame, shrinks) one figure until its
 * head is inside the frame. The body may leave the frame; the head may not.
 */
export function keepHeadInFrame(
  rig: Pick<RigDef, 'crops'>,
  crop: 'bust' | 'full',
  start: { centre: number; height: number; bottom: number },
  aspect: number,
  margin = HEAD_MARGIN,
): { centre: number; height: number; bottom: number } {
  let { centre, height, bottom } = start;
  const room = 100 - 2 * margin;
  const f = headFraction(rig, crop);
  const ratio = cropRatio(rig, crop);
  // Too big for the frame at all: shrink about the feet until the head fits.
  const headW = (f.w * height * ratio) / aspect;
  const headH = f.h * height;
  const shrink = Math.min(1, headW > 0 ? room / headW : 1, headH > 0 ? room / headH : 1);
  if (shrink < 1) height *= shrink;
  let head = headBox(rig, crop, { centre, height, bottom }, aspect);
  // Vertically: a head above the top comes down (the body leaves at the bottom);
  // a head below the bottom goes up.
  if (head.y < margin) bottom -= margin - head.y;
  else if (head.y + head.h > 100 - margin) bottom += head.y + head.h - (100 - margin);
  head = headBox(rig, crop, { centre, height, bottom }, aspect);
  // Sideways: a head past an edge comes back in.
  if (head.x < margin) centre += margin - head.x;
  else if (head.x + head.w > 100 - margin) centre -= head.x + head.w - (100 - margin);
  return { centre, height, bottom };
}

/**
 * The stage's layout for up to three figures. `aspect` is the stage's width ÷ height.
 * `rigOf` finds a rig's definition (the registry's `rigFor`); a member without one is
 * left out. Every returned head is inside the frame (`HEAD_MARGIN` from each edge).
 */
export function stageLayout({
  members,
  aspect,
  rigOf,
  framing = 'band',
  focus = null,
  margin = HEAD_MARGIN,
}: {
  members: LayoutMember[];
  aspect: number;
  rigOf: (id: string) => Pick<RigDef, 'crops'> | null;
  framing?: StageFraming;
  focus?: FocusPoint | null;
  margin?: number;
}): FigurePlacement[] {
  const ratio = aspect > 0 && Number.isFinite(aspect) ? aspect : 1;
  const cast = members
    .map((member) => ({ member, rig: rigOf(member.rigId) }))
    .filter((entry): entry is { member: LayoutMember; rig: Pick<RigDef, 'crops'> } => entry.rig !== null)
    .slice(0, 3);
  const n = cast.length;
  if (!n) return [];
  const shift = focus ? clamp(focus.x, 0, 1) * 100 - 50 : 0;

  if (framing === 'fill') {
    // Whole figures on a ground line, as tall as their heads allow side by side.
    const crop = 'full' as const;
    const widest = Math.max(...cast.map(({ rig }) => headFraction(rig, crop).w * cropRatio(rig, crop)));
    const fitWidth = ((100 - 2 * margin) / n) * 0.96;
    const height = Math.min(FILL_HEIGHT[n] ?? FILL_HEIGHT[3], (fitWidth * ratio) / Math.max(widest, 0.01));
    const figureWidth = (height * Math.max(...cast.map(({ rig }) => cropRatio(rig, crop)))) / ratio;
    // Spread the figures by their own width, but no further apart than the frame allows.
    const step = Math.min(figureWidth * 0.82, (100 - 2 * margin) / n);
    return cast.map(({ member, rig }, index) => {
      const front = Boolean(member.speaking);
      const start = {
        centre: 50 + shift + (index - (n - 1) / 2) * step,
        height: height * (front || n === 1 ? 1 : 0.95),
        bottom: FILL_GROUND,
      };
      const placed = keepHeadInFrame(rig, crop, start, ratio, margin);
      return {
        rigId: member.rigId,
        front,
        crop,
        ...placed,
        zIndex: front ? 3 : 1,
        head: headBox(rig, crop, placed, ratio),
      };
    });
  }

  const slots = BAND_SLOTS[n];
  return cast.map(({ member, rig }, index) => {
    const slot = slots[index];
    const front = Boolean(member.speaking);
    const start = {
      centre: slot.centre + shift,
      height: slot.height * (front || n === 1 ? 1 : 0.92),
      bottom: front ? 0 : slot.lift,
    };
    const placed = keepHeadInFrame(rig, 'bust', start, ratio, margin);
    return {
      rigId: member.rigId,
      front,
      crop: 'bust' as const,
      ...placed,
      zIndex: front ? 3 : 1,
      head: headBox(rig, 'bust', placed, ratio),
    };
  });
}

/**
 * The CSS `object-position` that keeps `focus` (fractions of the plate) as near the
 * stage's centre as the plate allows, for a plate drawn `object-fit: cover`.
 */
export function plateObjectPosition({
  plateAspect,
  stageAspect,
  focus,
}: {
  plateAspect: number;
  stageAspect: number;
  focus: FocusPoint;
}): string {
  // The visible share of the plate on each axis under `cover`.
  const visibleW = plateAspect > stageAspect ? stageAspect / plateAspect : 1;
  const visibleH = plateAspect > stageAspect ? 1 : plateAspect / stageAspect;
  const axis = (point: number, visible: number) =>
    visible >= 1 ? 50 : clamp(((clamp(point, 0, 1) - visible / 2) / (1 - visible)) * 100, 0, 100);
  const x = axis(focus.x, visibleW);
  const y = axis(focus.y, visibleH);
  return `${Math.round(x * 10) / 10}% ${Math.round(y * 10) / 10}%`;
}

/**
 * WP-144 «La page verticale» · where things are in a full-bleed panel.
 *
 * The panel is the phone's screen between the reader's bar and its nav (about
 * 9:16). Inside it, from the back:
 *
 *   · the plate, `object-fit: cover`, cropped per beat (`plateFocus`);
 *   · the cast box: the drawn stage (`PanelStage`, unchanged props) in a box at
 *     the panel's foot, full width, whose height depends on how many stand in it
 *     (`castBox`) — one speaker is a close shot, three are a wider one;
 *   · the balloon layer, which must never cover a face (`balloon-layout.ts`).
 *
 * The faces are known geometrically: `PanelStage` places each figure by a slot
 * (centre, height and lift, in % of its box) and draws the rig's bust crop, and
 * each rig names its head crop. `stageHeadBoxes` repeats that arithmetic. It
 * mirrors `SLOTS` in `components/cast/PanelStage.tsx` (owned by WP-143); the
 * test suite renders `PanelStage` and fails if the two ever disagree.
 * TODO(WP-143 merge): once PanelStage exports its layout (or reports head boxes
 * for `framing='fill'`), read them from there instead of `STAGE_SLOTS`.
 *
 * Pure: no React, no DOM. Every unit is px in the panel's own box.
 */

import { drawnFaceId } from '../../../cast/CastFace';
import { rigFor } from '../../../cast/cast-registry';
import { stageMembers, type StageMember } from '../../../cast/PanelStage';

export type Box = { x: number; y: number; w: number; h: number };
export type Size = { w: number; h: number };

/** One face on the panel: the rig it belongs to and its box. */
export type HeadBox = Box & { rigId: string };

/** Mirror of `SLOTS` in PanelStage.tsx: centre and height in % of the box, lift in %. */
export const STAGE_SLOTS: Record<number, Array<{ centre: number; height: number; lift: number }>> = {
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

/** Every bust crop is 180 × 220 (cast-rig.css fixes the figure's ratio to it). */
const BUST_RATIO = 180 / 220;

/**
 * The cast box's width ÷ height, by how many stand. One figure: nearly square,
 * a close shot. Three: the old band's proportion, so they do not overlap more
 * than they already did.
 */
const CAST_RATIO: Record<number, number> = { 1: 1.1, 2: 1.35, 3: 1.6 };

/** The share of the panel's height the cast box may take at most. */
const CAST_MAX_SHARE = 0.62;

/** The cast box inside a panel of `panel` size for `count` figures; null when nobody stands. */
export function castBox(panel: Size, count: number): Box | null {
  if (count <= 0 || panel.w <= 0 || panel.h <= 0) return null;
  const ratio = CAST_RATIO[Math.min(count, 3)] ?? CAST_RATIO[3];
  const h = Math.min(panel.w / ratio, panel.h * CAST_MAX_SHARE);
  return { x: 0, y: panel.h - h, w: panel.w, h };
}

/**
 * Where each figure's head is, in panel px, for the members PanelStage will draw
 * (the same dedupe, the same order, at most three, Toi never). `inflate` pads
 * every box (the idle bob and sway move a figure by a few px).
 */
export function stageHeadBoxes(members: StageMember[], box: Box | null, inflate = 6): HeadBox[] {
  if (!box) return [];
  const cast = stageMembers(members);
  const slots = STAGE_SLOTS[cast.length] ?? [];
  const heads: HeadBox[] = [];
  cast.forEach((member, index) => {
    const slot = slots[index];
    const rig = rigFor(member.rigId);
    if (!slot || !rig) return;
    const front = Boolean(member.speaking);
    const heightPct = slot.height * (front || cast.length === 1 ? 1 : 0.92);
    const bottomPct = front ? 0 : slot.lift;
    const figH = (heightPct / 100) * box.h;
    const figW = figH * BUST_RATIO;
    const figX = box.x + (slot.centre / 100) * box.w - figW / 2;
    const figBottom = box.y + box.h - (bottomPct / 100) * box.h;
    const figY = figBottom - figH;
    const [bx, by, bw, bh] = rig.crops.bust;
    const [hx, hy, hw, hh] = rig.crops.head;
    const x = figX + ((hx - bx) / bw) * figW;
    const y = figY + ((hy - by) / bh) * figH;
    const w = (hw / bw) * figW;
    const h = (hh / bh) * figH;
    heads.push({
      rigId: member.rigId,
      x: x - inflate,
      y: Math.max(figY, y) - inflate,
      w: w + inflate * 2,
      h: Math.min(h, figBottom - Math.max(figY, y)) + inflate * 2,
    });
  });
  return heads;
}

/** The head a line points at: its speaker's rig among the heads, or null (narrator, Toi, off stage). */
export function headIndexFor(heads: HeadBox[], speaker: { speakerId?: string | null; who?: string | null }): number {
  const rigId = drawnFaceId(speaker.speakerId || '', speaker.who || '');
  if (!rigId || rigId === 'user') return -1;
  return heads.findIndex((head) => head.rigId === rigId);
}

/** The slow push-in: how far the camera moves in over a beat (1 = none). */
export const PUSH_IN_SCALE = 1.06;

/**
 * A box as it will be at the end of the push-in (scaled by `scale` about
 * `origin`), unioned with where it starts, so a balloon placed clear of it stays
 * clear for the whole beat.
 */
export function pushInBounds(box: Box, origin: { x: number; y: number }, scale = PUSH_IN_SCALE): Box {
  const x2 = origin.x + (box.x - origin.x) * scale;
  const y2 = origin.y + (box.y - origin.y) * scale;
  const w2 = box.w * scale;
  const h2 = box.h * scale;
  const left = Math.min(box.x, x2);
  const top = Math.min(box.y, y2);
  const right = Math.max(box.x + box.w, x2 + w2);
  const bottom = Math.max(box.y + box.h, y2 + h2);
  return { x: left, y: top, w: right - left, h: bottom - top };
}

/** The camera's push-in origin: the lead speaker's face, else the panel's centre. */
export function pushInOrigin(panel: Size, heads: HeadBox[]): { x: number; y: number } {
  const lead = heads[0];
  if (!lead) return { x: panel.w / 2, y: panel.h / 2 };
  return { x: lead.x + lead.w / 2, y: lead.y + lead.h / 2 };
}

/**
 * The crop of the plate for this beat, as CSS `object-position` percentages.
 *
 * The plates are 3:2 and the panel about 9:16, so a cover crop shows some 40 %
 * of a plate's width; which 40 % is the beat's choice. The camera looks to the
 * side its lead speaker stands on; a silent beat or a beat with no one on stage
 * alternates sides from panel to panel, so two silent beats in a row are two
 * different crops of the same room. The first panel is the establishing shot:
 * the plate's middle.
 */
export function plateFocus(stage: {
  ordinal: number;
  cast?: Array<{ id: string; speaking?: boolean }> | null;
  silent?: boolean;
}): { x: number; y: number } {
  const cast = stageMembers((stage.cast ?? []) as StageMember[]);
  if (stage.ordinal <= 1) return { x: 50, y: 50 };
  if (cast.length && !stage.silent) {
    const slot = (STAGE_SLOTS[cast.length] ?? [])[0];
    if (slot) return { x: 25 + (slot.centre / 100) * 50, y: 50 };
  }
  return { x: stage.ordinal % 2 === 0 ? 32 : 68, y: 50 };
}

/**
 * WP-144 «La page verticale» · where things are in a full-bleed panel.
 *
 * The panel is the phone's screen between the reader's bar and its nav (about
 * 9:16). Inside it, from the back:
 *
 *   · the plate, `object-fit: cover`, cropped per beat (`plateFocus`);
 *   · the stage: `PanelStage` with WP-143's `framing='fill'` (whole figures on a
 *     ground line, as large as their heads allow side by side) in a stage box
 *     the size of the panel or taller (`stageFrame`). The box is placed so the
 *     heads sit at a medium-shot height — a little above the middle — never on
 *     the bottom edge; what falls below the panel is cut by it;
 *   · the balloon layer, which must never cover a face (`balloon-layout.ts`).
 *
 * WP-144b: the faces are WP-143's own head boxes (`stageLayout`, the function
 * PanelStage draws with, called with the same aspect the stage is given), not a
 * mirror of its slots.
 *
 * Pure: no React, no DOM. Every unit is px in the panel's own box.
 */

import { drawnFaceId } from '../../../cast/CastFace';
import { rigFor } from '../../../cast/cast-registry';
import { stageMembers, type StageMember } from '../../../cast/PanelStage';
import { stageLayout } from '../../../../lib/stage-frame';

export type Box = { x: number; y: number; w: number; h: number };
export type Size = { w: number; h: number };

/** One face on the panel: the rig it belongs to and its box. */
export type HeadBox = Box & { rigId: string };

/**
 * The stage box's height as a share of the panel's, by how many stand. One and
 * two figures stand taller than the panel (a medium shot: the heads large, the
 * legs below the frame; two are as large as their heads allow side by side).
 * Three are already width-bound at the panel's height: side by side their heads
 * cannot grow, so they stand whole, on the room's floor.
 */
const STAGE_HEIGHT: Record<number, number> = { 1: 1.3, 2: 1.5, 3: 1 };

/** Where the top of the highest head sits, as a share of the panel's height. */
const HEAD_LINE: Record<number, number> = { 1: 0.34, 2: 0.4, 3: 0.44 };

/** How far a beat may lower the head line to fit its lines (see `stageFrame`). */
export const HEAD_LINE_DROPS = [0, 0.08, 0.16];

/** The heads keep this much of the panel's height clear of its bottom edge. */
const FOOT_ROOM = 0.18;

export type StageFrame = {
  /** The stage's box in panel px (may run past the panel's foot). */
  box: Box;
  /** The stage's width ÷ height, handed to PanelStage as `aspect`. */
  aspect: number;
  /** Every figure's head in panel px, in PanelStage's member order. */
  heads: HeadBox[];
};

/**
 * The stage for the members PanelStage will draw (the same dedupe, the same
 * order, at most three, Toi never), and every head on it. Null when nobody
 * stands. `inflate` pads every head (the idle bob and sway move a figure by a
 * few px). `lower` moves the head line down by that share of the panel (a beat
 * with more to say gives its balloons more sky), never past `FOOT_ROOM`.
 */
export function stageFrame(panel: Size, members: StageMember[], inflate = 6, lower = 0): StageFrame | null {
  const cast = stageMembers(members).slice(0, 3);
  if (!cast.length || panel.w <= 0 || panel.h <= 0) return null;
  const n = cast.length;
  const h = panel.h * (STAGE_HEIGHT[n] ?? 1);
  const aspect = panel.w / h;
  const layout = stageLayout({
    members: cast.map((member) => ({ rigId: member.rigId, speaking: member.speaking })),
    aspect,
    rigOf: rigFor,
    framing: 'fill',
  });
  if (!layout.length) return null;
  const top = Math.min(...layout.map((place) => (place.head.y / 100) * h));
  const bottom = Math.max(...layout.map((place) => ((place.head.y + place.head.h) / 100) * h));
  // The medium shot: the highest head on the head line, unless that would sink
  // the lowest face into the panel's foot.
  let y = panel.h * ((HEAD_LINE[n] ?? 0.44) + lower) - top;
  y = Math.min(y, panel.h * (1 - FOOT_ROOM) - bottom);
  y = Math.max(y, panel.h * 0.04 - top);
  const box = { x: 0, y, w: panel.w, h };
  const heads = layout.map((place) => {
    const x = (place.head.x / 100) * box.w;
    const hy = box.y + (place.head.y / 100) * box.h;
    const w = (place.head.w / 100) * box.w;
    const hh = (place.head.h / 100) * box.h;
    return { rigId: place.rigId, x: x - inflate, y: hy - inflate, w: w + inflate * 2, h: hh + inflate * 2 };
  });
  return { box, aspect, heads };
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
  // The fill stage stands the lead speaker leftmost: with company, the camera looks left.
  if (cast.length && !stage.silent) return { x: cast.length > 1 ? 38 : 50, y: 50 };
  return { x: stage.ordinal % 2 === 0 ? 32 : 68, y: 50 };
}

/**
 * WP-116 phase 3 · the drawn cast standing on a panel's plate.
 *
 * Who: the panel's speakers (one figure each, at most three), plus Toi seen from
 * behind in the corner when the learner speaks in the panel. Where: the speaker in
 * front and a little bigger, the others behind and raised. The stage is drawn
 * inside the reader's plate frame (`.fr-plate`, square, `position: relative`).
 *
 * WP-119 §8.2 · Toi's `outfit` (on a member whose id is Toi's) is drawn only when
 * `surface === 'revue'`. In the story the heavy coat stays canon (WP-118), so on
 * the default `story` surface the outfit is dropped. The applied outfit is on the
 * Toi figure as `data-outfit`.
 */
import React from 'react';

import type { StageMood } from '@/lib/cast-faces';
import { castVariant } from '@/lib/cast-variants';
import { CastRig } from './CastRig';
import { rigFaceFor, rigFor } from './cast-registry';
import { drawnFaceId } from './CastFace';
import type { Outfit, Viseme } from './rig-kit';

export type StageMember = {
  /** Any id the payloads use for the character («marin», «marin_leveque», a name). */
  id: string;
  /** WP-137 C-4: the four portrait moods, or `cold` (no smile). */
  mood?: StageMood | null;
  speaking?: boolean;
  /** WP-116 phase 4: the mouth while this member's line is heard. */
  mouth?: Viseme | 'auto';
  /** WP-119 · Toi's outfit; only the Revue stage draws it (see `toiOutfit`). */
  outfit?: Outfit;
  /** WP-119 §8.3 · an authored prop in the figure's hands («notebook»); a rig that has none ignores it. */
  hold?: string | null;
};

/**
 * WP-119 · how Toi is cropped. `bust` is the season panels' corner figure (46 %
 * high); `half` is the Revue's waist crop (58 % high, 180:260) so the dress reads.
 */
export type YouCrop = 'bust' | 'half';

export type StageSurface = 'story' | 'revue';

/** The outfit Toi wears on this surface: the coat everywhere but the Revue. */
export function toiOutfit(members: StageMember[], surface: StageSurface = 'story'): Outfit {
  if (surface !== 'revue') return 'coat';
  const toi = members.find((member) => member.outfit && rigFor(member.id)?.id === 'user');
  return toi?.outfit ?? 'coat';
}

/**
 * Where each figure stands, by how many stand: its centre (% of the panel's width)
 * and its height (% of the panel's height). Sizing by height keeps every head in
 * the frame whatever the panel's shape (square in the reader, wide in the story).
 */
const SLOTS: Record<number, Array<{ centre: number; height: number; lift: number }>> = {
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

export function stageMembers(members: StageMember[]): Array<StageMember & { rigId: string }> {
  const seen = new Set<string>();
  const out: Array<StageMember & { rigId: string }> = [];
  for (const member of members) {
    const rigId = drawnFaceId(member.id);
    if (!rigId || rigId === 'user' || seen.has(rigId)) continue;
    seen.add(rigId);
    out.push({ ...member, rigId });
    if (out.length === 3) break;
  }
  return out;
}

export function PanelStage({
  members,
  you = false,
  still = false,
  talking = null,
  surface = 'story',
  entering = null,
}: {
  members: StageMember[];
  /**
   * The learner speaks in this panel: Toi stands in the corner, from behind.
   * WP-119: `{ crop: 'half' }` is the Revue's waist crop.
   */
  you?: boolean | { crop?: YouCrop };
  still?: boolean;
  /** WP-116 phase 4: who is heard right now and their mouth; the others hold still. */
  talking?: { id: string; mouth: Viseme | 'auto' } | null;
  /** WP-119 · where the stage stands; only `revue` lets Toi change out of the coat. */
  surface?: StageSurface;
  /** WP-119 · the rig id that slides in (260 ms; none under Reduce Motion, see cast-rig.css). */
  entering?: string | null;
}) {
  const talkingRig = talking ? drawnFaceId(talking.id) : null;
  const cast = stageMembers(members);
  const outfit = toiOutfit(members, surface);
  const youCrop: YouCrop | null = you ? (typeof you === 'object' && you.crop === 'half' ? 'half' : 'bust') : null;
  const enteringRig = entering ? drawnFaceId(entering) : null;
  if (!cast.length && !youCrop) return null;
  const slots = SLOTS[cast.length] ?? [];
  return (
    <div className="cast-stage" aria-hidden="true" data-cast-stage={cast.map((member) => member.rigId).join(' ')}>
      {cast.map((member, index) => {
        const slot = slots[index];
        const front = Boolean(member.speaking);
        const face = rigFaceFor(member.mood ?? 'neutral');
        const heard = talkingRig === member.rigId ? talking?.mouth ?? 'auto' : 'auto';
        return (
          <div
            key={member.rigId}
            className="cast-stage__figure"
            data-speaking={front ? '' : undefined}
            data-entering={enteringRig === member.rigId ? '' : undefined}
            style={{
              left: `${slot.centre}%`,
              height: `${slot.height * (front || cast.length === 1 ? 1 : 0.92)}%`,
              bottom: `${front ? 0 : slot.lift}%`,
              zIndex: front ? 3 : 1,
            }}
          >
            <CastRig
              id={member.rigId}
              mood={face.mood}
              crop="bust"
              size={180}
              variant={castVariant(member.rigId) ?? undefined}
              // The voice moves the mouth; between words a cold face holds its level line.
              mouth={heard !== 'auto' ? heard : face.mouth}
              // One mover at a time: while someone is heard, the others hold still.
              still={still || Boolean(talkingRig && talkingRig !== member.rigId)}
              hold={member.hold ?? undefined}
              label=""
            />
          </div>
        );
      })}
      {youCrop === 'bust' && (
        <div
          className="cast-stage__figure cast-stage__figure--you"
          data-outfit={outfit}
          style={{ left: '88%', height: '46%', bottom: '-8%', zIndex: 4 }}
        >
          <CastRig id="user" crop="bust" size={120} still={still} outfit={outfit} label="" />
        </div>
      )}
      {youCrop === 'half' && (
        // The waist crop: Toi's full drawing (viewBox 0 0 200 420) framed on x 10–190,
        // y 76–336, so the window is 180:260 and the bust's head stays where it was.
        <div
          className="cast-stage__figure cast-stage__figure--you"
          data-outfit={outfit}
          data-crop="half"
          style={{ left: '86%', height: '58%', bottom: '-6%', zIndex: 4, aspectRatio: '180 / 260', overflow: 'hidden' }}
        >
          <div style={{ position: 'absolute', left: '-5.556%', top: '-29.231%', width: '111.111%', height: '161.538%' }}>
            <CastRig id="user" crop="full" size={120} still={still} outfit={outfit} label="" />
          </div>
        </div>
      )}
    </div>
  );
}

export default PanelStage;

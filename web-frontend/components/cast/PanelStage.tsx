/**
 * WP-116 phase 3 · the drawn cast standing on a panel's plate.
 *
 * Who: the panel's speakers (one figure each, at most three), plus Toi seen from
 * behind in the corner when the learner speaks in the panel. Where: the speaker in
 * front and a little bigger, the others behind and raised. The stage is drawn
 * inside the reader's plate frame (`.fr-plate`, square, `position: relative`).
 */
import React from 'react';

import type { PortraitMood } from '@/lib/onboarding-portraits';
import { castVariant } from '@/lib/cast-variants';
import { CastRig } from './CastRig';
import { rigMoodFor } from './cast-registry';
import { drawnFaceId } from './CastFace';
import type { Viseme } from './rig-kit';

export type StageMember = {
  /** Any id the payloads use for the character («marin», «marin_leveque», a name). */
  id: string;
  mood?: PortraitMood | null;
  speaking?: boolean;
  /** WP-116 phase 4: the mouth while this member's line is heard. */
  mouth?: Viseme | 'auto';
};

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
}: {
  members: StageMember[];
  /** The learner speaks in this panel: Toi stands in the corner, from behind. */
  you?: boolean;
  still?: boolean;
  /** WP-116 phase 4: who is heard right now and their mouth; the others hold still. */
  talking?: { id: string; mouth: Viseme | 'auto' } | null;
}) {
  const talkingRig = talking ? drawnFaceId(talking.id) : null;
  const cast = stageMembers(members);
  if (!cast.length && !you) return null;
  const slots = SLOTS[cast.length] ?? [];
  return (
    <div className="cast-stage" aria-hidden="true" data-cast-stage={cast.map((member) => member.rigId).join(' ')}>
      {cast.map((member, index) => {
        const slot = slots[index];
        const front = Boolean(member.speaking);
        return (
          <div
            key={member.rigId}
            className="cast-stage__figure"
            data-speaking={front ? '' : undefined}
            style={{
              left: `${slot.centre}%`,
              height: `${slot.height * (front || cast.length === 1 ? 1 : 0.92)}%`,
              bottom: `${front ? 0 : slot.lift}%`,
              zIndex: front ? 3 : 1,
            }}
          >
            <CastRig
              id={member.rigId}
              mood={rigMoodFor(member.mood ?? 'neutral')}
              crop="bust"
              size={180}
              variant={castVariant(member.rigId) ?? undefined}
              mouth={talkingRig === member.rigId ? talking?.mouth ?? 'auto' : 'auto'}
              // One mover at a time: while someone is heard, the others hold still.
              still={still || Boolean(talkingRig && talkingRig !== member.rigId)}
              label=""
            />
          </div>
        );
      })}
      {you && (
        <div className="cast-stage__figure cast-stage__figure--you" style={{ left: '88%', height: '46%', bottom: '-8%', zIndex: 4 }}>
          <CastRig id="user" crop="bust" size={120} still={still} label="" />
        </div>
      )}
    </div>
  );
}

export default PanelStage;

/**
 * WP-119 · RvStage — the plate with the drawn cast (WP-119 §8.3, design §3.2).
 *
 * Romy in front with her notebook, Toi from behind in the plan's dress (the
 * waist crop, so the dress reads). Wraps `PanelStage surface="revue"`, the only
 * surface that lets Toi out of the coat. Sizes: `full` (4:3, arrive), `band`
 * (390:168, pinned over the thread), `une` (16:9, La Une and the chooser).
 * `pending` is the reader's «sous presse» duotone with a folio pill. The plate
 * is decorative (`alt=""`, `aria-hidden`): the narration carries the place.
 */

import React from 'react';

import { PanelStage, type StageMember } from '@/components/cast/PanelStage';
import type { Outfit } from '@/components/cast/rig-kit';
import { resolveMediaUrl } from '@/lib/media-url';

export type RvStageProps = {
  plateUrl: string | null;
  size: 'full' | 'band' | 'une';
  cast: StageMember[];
  /** Toi from behind, in this outfit. Omitted: no Toi (La Une's card shows Romy alone). */
  you?: { outfit?: Outfit } | null;
  /** A guest's rig id sliding in (phase 2). */
  entering?: string | null;
  /** «Un vignoble en Bourgogne · sous presse» — the plate is still being painted. */
  pending?: { folio: string } | null;
  still?: boolean;
  children?: React.ReactNode;
};

export function RvStage({ plateUrl, size, cast, you = null, entering = null, pending = null, still = false, children }: RvStageProps) {
  const src = plateUrl ? resolveMediaUrl(plateUrl) ?? plateUrl : null;
  const members: StageMember[] = cast.map((member) => ({ ...member, speaking: member.speaking ?? true }));
  if (you) members.push({ id: 'user', outfit: you.outfit });
  return (
    <div className="rv-stage" data-size={size} data-pending={pending ? '' : undefined}>
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img className="rv-stage__plate" src={src} alt="" aria-hidden="true" decoding="async" />
      ) : (
        <span className="rv-stage__fallback" aria-hidden="true" />
      )}
      <span className="rv-stage__ink" aria-hidden="true" />
      <PanelStage members={members} you={you ? { crop: 'half' } : false} surface="revue" entering={entering} still={still} />
      {pending && <span className="rv-stage__folio">{pending.folio}</span>}
      {children}
    </div>
  );
}

/**
 * The Revue cast from the wire's stage: Romy (with her prop) and, phase 2, the
 * guest beside her (two slots, 31 % / 69 %). `speaker` is whoever spoke last:
 * they stand in front; without one, Romy does.
 */
export function stageCast(cast: Array<{ id: string; hold: string | null }>, speaker?: string | null): StageMember[] {
  const members = cast.filter((member) => member.id !== 'user');
  const front = speaker && members.some((member) => member.id === speaker) ? speaker : members[0]?.id;
  return members.map((member) => ({ id: member.id, hold: member.hold, speaking: member.id === front }));
}

export default RvStage;

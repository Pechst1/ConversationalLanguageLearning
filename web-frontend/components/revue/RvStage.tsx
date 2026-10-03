/**
 * WP-119 · RvStage — the plate with the drawn cast (WP-119 §8.3, design §3.2).
 *
 * Romy in front with her notebook, Toi from behind in the plan's dress (the
 * waist crop, so the dress reads). Wraps `PanelStage surface="revue"`, the only
 * surface that lets Toi out of the coat. Sizes: `full` (4:3, arrive), `band`
 * (390:168, pinned over the thread), `une` (16:9, La Une and the chooser).
 * `pending` is the reader's «sous presse» duotone with a folio pill. The plate
 * is decorative (`alt=""`, `aria-hidden`): the narration carries the place.
 *
 * Phase 4 «Les planches» (§12.7): a dossier may carry a second view. When the
 * plate changes (the guest's entrance, or `make`) the new plate fades in over
 * the old one in 320 ms, like the reader's art (at once under Reduce Motion);
 * the cast and the frame never move.
 */

import React, { useEffect, useState } from 'react';

import { PanelStage, type StageMember } from '@/components/cast/PanelStage';
import type { Outfit } from '@/components/cast/rig-kit';
import { prefersReducedMotion } from '@/lib/journey-reply-reveal';
import { resolveMediaUrl } from '@/lib/media-url';
import type { RvStage as RvStageWire, RvThreadItem } from '@/lib/revue-types';

const PLATE_FADE_MS = 320;

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
  const plate = usePlateCrossfade(src);
  const members: StageMember[] = cast.map((member) => ({ ...member, speaking: member.speaking ?? true }));
  if (you) members.push({ id: 'user', outfit: you.outfit });
  return (
    <div className="rv-stage" data-size={size} data-pending={pending ? '' : undefined}>
      {plate.previous && (
        // eslint-disable-next-line @next/next/no-img-element
        <img className="rv-stage__plate is-previous" src={plate.previous} alt="" aria-hidden="true" decoding="async" />
      )}
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={src}
          className="rv-stage__plate"
          src={src}
          alt=""
          aria-hidden="true"
          decoding="async"
          onLoad={plate.onLoad}
          style={plate.style}
        />
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
 * The plate crossfade: the previous plate stays underneath until the new one has
 * loaded, then the new one fades in (no fade under Reduce Motion) and the old one
 * goes. The first plate simply appears.
 */
function usePlateCrossfade(src: string | null): {
  previous: string | null;
  style: React.CSSProperties | undefined;
  onLoad: () => void;
} {
  const [current, setCurrent] = useState(src);
  const [previous, setPrevious] = useState<string | null>(null);
  const [arrived, setArrived] = useState(true);

  useEffect(() => {
    if (src === current) return;
    setPrevious(current);
    setArrived(!current); // nothing to fade from: show at once
    setCurrent(src);
  }, [src, current]);

  useEffect(() => {
    if (!arrived || !previous) return undefined;
    const timer = window.setTimeout(() => setPrevious(null), prefersReducedMotion() ? 0 : PLATE_FADE_MS);
    return () => window.clearTimeout(timer);
  }, [arrived, previous]);

  const fading = previous !== null;
  const style: React.CSSProperties | undefined = fading
    ? {
        opacity: arrived ? 1 : 0,
        transition: prefersReducedMotion() ? 'none' : `opacity ${PLATE_FADE_MS}ms ease-out`,
      }
    : undefined;
  return { previous, style, onLoad: () => setArrived(true) };
}

/**
 * Which plate the stage shows (§12.7): the site until the stage switches, then the
 * second view. It switches when the server says so (`plateSwitched`), when a guest
 * has entered in the thread (the turn result carries no stage), or when the make
 * step is open; it never switches back.
 */
export function stagePlateUrl(
  stage: Pick<RvStageWire, 'plateUrl' | 'plateUrlSecond' | 'plateSwitched'>,
  thread: RvThreadItem[] = [],
  making = false,
): string | null {
  if (!stage.plateUrlSecond) return stage.plateUrl;
  const guestEntered = thread.some((item) => item.kind === 'guest' && item.move === 'enter');
  return stage.plateSwitched || guestEntered || making ? stage.plateUrlSecond : stage.plateUrl;
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

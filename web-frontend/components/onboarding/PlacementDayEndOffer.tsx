/**
 * WP-126 — the placement, offered at the end of the day.
 *
 * Owner decision 2 (2026-10-04): the placement is offered right after the first
 * completed ending to a learner who declared more than «Nouveau», instead of on
 * Home after three days. It sits on the day's reward screen (`JourneyRecap`),
 * under the day's own primary («Ranger le sceau»), as one calm card:
 *
 *  - «Faire le bilan» (or «Reprendre le bilan» when one is open) opens
 *    `/placement?from=day-end`;
 *  - «Pas maintenant» declines (`POST /placement/skip`): the server records it,
 *    `GET /placement/offer` stops offering, so it does not come back every day.
 *    Réglages keeps the voluntary re-run.
 *
 * It renders nothing while it asks, on any error, after an early stop (a
 * partial day is not an ending), and whenever the server says no. Never a chain
 * of assessments: the vocabulary check is offered only from the placement's
 * result, not here.
 */

import React from 'react';
import Link from 'next/link';

import { Action, Surface } from '@/components/atelier-v2/ui';
import { placementCopy } from '@/lib/placement-copy';
import api, { type PlacementOffer } from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

export const PLACEMENT_DAY_END_HREF = '/placement?from=day-end';

export type DayEndOfferState = 'hidden' | 'offer' | 'resume' | 'declined';

/** What the card shows, from the server's offer and the day's state. */
export function dayEndOfferState(
  offer: Pick<PlacementOffer, 'offer'> & { resume?: boolean | null } | null | undefined,
  { partial = false, declined = false }: { partial?: boolean; declined?: boolean } = {},
): DayEndOfferState {
  if (declined) return 'declined';
  if (partial || !offer || offer.offer !== true) return 'hidden';
  return offer.resume ? 'resume' : 'offer';
}

export function PlacementDayEndOfferView({
  state,
  language,
  pending = false,
  onSkip,
}: {
  state: DayEndOfferState;
  language: ControlLanguage;
  pending?: boolean;
  onSkip: () => void;
}) {
  if (state === 'hidden') return null;
  const copy = placementCopy(language);
  if (state === 'declined') {
    return (
      <p className="pl-dayend__note" role="status" data-placement-offer="declined">
        {copy.day_end_skipped}
        <PlacementDayEndStyles />
      </p>
    );
  }
  const resume = state === 'resume';
  return (
    <Surface tone="outline" className="pl-dayend" data-placement-offer={state}>
      <span className="av2-label">{copy.day_end_kicker}</span>
      <p className="pl-dayend__title">{resume ? copy.day_end_title_resume : copy.day_end_title}</p>
      <p className="pl-dayend__lead">{copy.day_end_lead}</p>
      <p className="pl-dayend__fine">{copy.day_end_fine}</p>
      <div className="pl-dayend__actions">
        <Link className="av2-btn av2-btn--secondary" href={PLACEMENT_DAY_END_HREF}>
          {resume ? copy.day_end_resume : copy.day_end_begin}
        </Link>
        <Action tone="quiet" pending={pending} pendingLabel={copy.day_end_skip} onClick={onSkip}>
          {copy.day_end_skip}
        </Action>
      </div>
      <PlacementDayEndStyles />
    </Surface>
  );
}

/** The card with its two calls. `partial`: the day ended early — no offer then. */
export function PlacementDayEndOffer({ language, partial = false }: { language: ControlLanguage; partial?: boolean }) {
  const [offer, setOffer] = React.useState<PlacementOffer | null>(null);
  const [declined, setDeclined] = React.useState(false);
  const [pending, setPending] = React.useState(false);

  React.useEffect(() => {
    if (partial) return undefined;
    let alive = true;
    api
      .getPlacementOffer()
      .then((body) => {
        if (alive) setOffer(body ?? null);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [partial]);

  const skip = React.useCallback(async () => {
    setPending(true);
    try {
      await api.skipPlacement();
      setDeclined(true);
    } catch {
      // Declining must never trap the learner: the card simply goes away and the
      // server, which did not record it, may offer it once more another day.
      setOffer(null);
    } finally {
      setPending(false);
    }
  }, []);

  return (
    <PlacementDayEndOfferView
      state={dayEndOfferState(offer, { partial, declined })}
      language={language}
      pending={pending}
      onSkip={() => void skip()}
    />
  );
}

function PlacementDayEndStyles() {
  return (
    <style jsx global>{`
      .av2 .pl-dayend {
        display: flex;
        flex-direction: column;
        gap: 8px;
        min-width: 0;
      }
      .av2 .pl-dayend__title {
        margin: 0;
        font-family: var(--av2-serif);
        font-size: var(--av2-t-title);
        line-height: 1.2;
        color: var(--av2-ink);
        overflow-wrap: anywhere;
      }
      .av2 .pl-dayend__lead {
        margin: 0;
        font-size: var(--av2-t-body);
        line-height: 1.45;
        color: var(--av2-ink-2);
      }
      .av2 .pl-dayend__fine,
      .av2 .pl-dayend__note {
        margin: 0;
        font-size: var(--av2-t-label);
        line-height: 1.45;
        color: var(--av2-muted);
      }
      .av2 .pl-dayend__actions {
        display: flex;
        flex-direction: column;
        align-items: stretch;
        gap: 4px;
        margin-top: 4px;
      }
    `}</style>
  );
}

export default PlacementDayEndOffer;

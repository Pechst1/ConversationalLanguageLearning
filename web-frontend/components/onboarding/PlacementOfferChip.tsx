/**
 * WP-75 — the placement, offered quietly and only when it can help.
 *
 * `GET /placement/offer` says `{ offer: true }` from the first completed ending
 * on (WP-126) for a learner who did not start as «Nouveau». Until then — and on any error —
 * this renders nothing: the placement is never a first task, and never a nag.
 */

import React from 'react';
import Link from 'next/link';

import { useLearnerLanguage } from '@/lib/learner-language';
import { placementCopy } from '@/lib/placement-copy';
import apiService from '@/services/api';

export const PLACEMENT_OFFER_HREF = '/placement?from=offer';

/** `className` goes on a wrapper that exists only when the chip does. */
export function PlacementOfferChip({ className }: { className?: string }) {
  const [offer, setOffer] = React.useState(false);
  // WP-126: chrome in the learner's own language (it was French for everyone).
  const copy = placementCopy(useLearnerLanguage());

  React.useEffect(() => {
    let alive = true;
    apiService
      .get<{ offer?: boolean }>('/placement/offer', { suppressGlobalError: true } as Record<string, unknown>)
      .then((body) => {
        if (alive) setOffer(body?.offer === true);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  if (!offer) return null;
  return (
    <div className={className}>
      <Link className="av2-chip av2-chip--quiet" href={PLACEMENT_OFFER_HREF}>
        <span>{copy.chip}</span>
      </Link>
    </div>
  );
}

export default PlacementOfferChip;

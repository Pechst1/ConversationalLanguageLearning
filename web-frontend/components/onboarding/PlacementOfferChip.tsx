/**
 * WP-75 — the placement, offered quietly and only when it can help.
 *
 * `GET /placement/offer` says `{ offer: true }` only after three completed days
 * for a learner who did not start as «Nouveau». Until then — and on any error —
 * this renders nothing: the placement is never a first task, and never a nag.
 */

import React from 'react';
import Link from 'next/link';

import apiService from '@/services/api';

export const PLACEMENT_OFFER_HREF = '/placement?from=offer';

/** `className` goes on a wrapper that exists only when the chip does. */
export function PlacementOfferChip({ className }: { className?: string }) {
  const [offer, setOffer] = React.useState(false);

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
        <span>Faire le point sur votre niveau</span>
      </Link>
    </div>
  );
}

export default PlacementOfferChip;

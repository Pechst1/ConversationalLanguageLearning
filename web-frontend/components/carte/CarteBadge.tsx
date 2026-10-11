/**
 * WP-120 phase D · the Relevé's way onto La Carte: a small France silhouette with
 * the learner's pin count (`GET /revue/carte` → `counts.france`), linking to
 * `/carte`. It sits in «Le Papier» (RvReleveSection), under the section head.
 *
 * Given a `count`, it draws that; otherwise it reads the map itself. It renders
 * NOTHING while loading, when the Revue is off, when the read fails, or when no
 * Papier has a place yet: the Relevé never shows a broken or empty door.
 */

import React, { useEffect, useState } from 'react';
import Link from 'next/link';

import { carteClient, type CarteClient } from '@/lib/carte-api';

import { carteCopy } from './carte-copy';

export const CARTE_HREF = '/carte';

/** A France silhouette, drawn small (24 × 24), ink on paper; decorative. */
export function FranceSilhouette({ size = 22 }: { size?: number }) {
  return (
    <svg className="carte-badge__france" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path
        d="M11.6 1.6l2.3 1.5 2.6.3.6 1.9 2.4 1.1 1.5-.4.3 2-1.2 1.6.3 2.2-1.6.9.9 1.5-.3 2.3 1.4 1.4-1.6 1.6-3.1.2-2.3 1.5-2.4-.9-2.2.9-3.1-1.3.5-2.2-.9-1.9 1.2-2.6-1.3-1.9-2.6-.9-.6-1.9 2.5-.3 1.4-1.6 1.9.4 1.8-1.7.4-2.1 1.7.8z"
        fill="currentColor"
      />
      <path d="M21.2 18.6l.8 1.3-.4 2.1-.9-.5z" fill="currentColor" />
    </svg>
  );
}

export type CarteBadgeProps = {
  /** Given: drawn as is (tests, previews). Absent: read from the API. */
  count?: number;
  client?: CarteClient;
  /** The chrome language of the label (the French stays French). */
  language?: string | null;
};

export function CarteBadge({ count: given, client, language = 'fr' }: CarteBadgeProps) {
  const [count, setCount] = useState<number | null>(given ?? null);

  useEffect(() => {
    if (given !== undefined) {
      setCount(given);
      return undefined;
    }
    let alive = true;
    (client ?? carteClient())
      .carte()
      .then((result) => {
        if (alive) setCount(result.enabled ? result.view.counts.france : 0);
      })
      .catch(() => {
        // A failing read is a missing badge, never an error on the Relevé.
      });
    return () => {
      alive = false;
    };
  }, [given, client]);

  if (!count) return null;
  const copy = carteCopy(language);
  return (
    <Link href={CARTE_HREF} className="carte-badge" aria-label={copy.badge_label(count)} data-carte-badge={count}>
      <FranceSilhouette />
      <span className="carte-badge__name" lang="fr" aria-hidden="true">
        {copy.page_title}
      </span>
      <span className="carte-badge__count" aria-hidden="true">
        {count}
      </span>
    </Link>
  );
}

export default CarteBadge;

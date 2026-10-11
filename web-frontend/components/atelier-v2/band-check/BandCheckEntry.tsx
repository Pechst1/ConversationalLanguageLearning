/**
 * SPEED-1 — the way into «Vérification du lexique».
 *
 * WP-127: shown only while the top-down ladder (`GET /vocabulary/band-check/ladder`)
 * has a band to check now — not when it is done, and not when this visit's two
 * checks are spent (no nag); otherwise it renders nothing (and it
 * renders nothing while it asks, so a screen never jumps for a learner who has
 * nothing to check). One calm, secondary action — the host screen keeps its own
 * single primary.
 *
 *  - `origin="placement"`: on the placement result, the lead explains why.
 *  - `origin="lexique"`: in Le lexique, a quiet line naming the levels left.
 */

import React from 'react';
import Link from 'next/link';

import { Surface } from '@/components/atelier-v2/ui';
import api, { type BandCheckLadder, type BandCheckSubBand } from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { bandCheckCopy, bandCheckFill } from './band-check-copy';
import { nextBand } from './band-check-state';
import type { BandCheckOrigin } from './BandCheck';

export const BAND_CHECK_ROUTE = '/vocabulary/verification';

export function bandCheckHref(origin: BandCheckOrigin, band?: string | null): string {
  const params = new URLSearchParams({ from: origin });
  if (band) params.set('band', band);
  return `${BAND_CHECK_ROUTE}?${params.toString()}`;
}

/** The entry as drawn, for the gallery and for the fetching wrapper. */
export function BandCheckEntryView({
  origin,
  language,
  bands,
  ladder,
}: {
  origin: BandCheckOrigin;
  language: ControlLanguage;
  /** Without a ladder (an older server, the gallery), the same rule is computed here. */
  bands: BandCheckSubBand[];
  ladder?: Pick<BandCheckLadder, 'status' | 'next'> | null;
}) {
  const next = ladder ? (ladder.status === 'open' ? ladder.next ?? null : null) : nextBand(bands);
  if (!next) return null;
  const copy = bandCheckCopy(language);
  const resumed = bands.some((row) => row.missed);
  const lead =
    origin === 'placement'
      ? copy.entry_lead_placement
      : bandCheckFill(resumed ? copy.entry_lead_resume : copy.entry_lead_lexique, { band: next });
  return (
    <Surface tone="outline" className="bc-entry">
      <p className="bc-entry__lead">{lead}</p>
      <Link className="av2-btn av2-btn--secondary" href={bandCheckHref(origin)}>
        {copy.entry_cta}
      </Link>
      <style jsx global>{`
        .av2 .bc-entry {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .av2 .bc-entry__lead {
          margin: 0;
          font-size: var(--av2-t-label);
          line-height: 1.45;
          color: var(--av2-ink-2);
        }
      `}</style>
    </Surface>
  );
}

export function BandCheckEntry({ origin, language }: { origin: BandCheckOrigin; language: ControlLanguage }) {
  const [ladder, setLadder] = React.useState<BandCheckLadder | null>(null);
  React.useEffect(() => {
    let alive = true;
    api
      .getBandCheckLadder()
      .then((body) => {
        if (alive) setLadder(body ?? null);
      })
      .catch(() => {
        // An entry point is an offer: when the ladder cannot be read, it is
        // simply not shown.
        if (alive) setLadder(null);
      });
    return () => {
      alive = false;
    };
  }, []);
  if (!ladder) return null;
  return <BandCheckEntryView origin={origin} language={language} bands={ladder.bands} ladder={ladder} />;
}

export default BandCheckEntry;

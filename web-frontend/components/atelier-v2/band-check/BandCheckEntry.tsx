/**
 * SPEED-1 — the way into «Vérification du lexique».
 *
 * Shown only while `GET /vocabulary/band-check` lists at least one uncredited
 * sub-band below the learner's level; otherwise it renders nothing (and it
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
import api, { type BandCheckSubBand } from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { bandCheckCopy, bandCheckFill } from './band-check-copy';
import { uncreditedBands } from './band-check-state';
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
}: {
  origin: BandCheckOrigin;
  language: ControlLanguage;
  bands: BandCheckSubBand[];
}) {
  const open = uncreditedBands(bands);
  if (open.length === 0) return null;
  const copy = bandCheckCopy(language);
  const lead =
    origin === 'placement'
      ? copy.entry_lead_placement
      : bandCheckFill(copy.entry_lead_lexique, { bands: open.map((row) => row.sub_band).join(' · ') });
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
  const [bands, setBands] = React.useState<BandCheckSubBand[] | null>(null);
  React.useEffect(() => {
    let alive = true;
    api
      .getBandChecks()
      .then((list) => {
        if (alive) setBands(Array.isArray(list) ? list : []);
      })
      .catch(() => {
        // An entry point is an offer: when the list cannot be read, it is
        // simply not shown.
        if (alive) setBands([]);
      });
    return () => {
      alive = false;
    };
  }, []);
  if (!bands) return null;
  return <BandCheckEntryView origin={origin} language={language} bands={bands} />;
}

export default BandCheckEntry;

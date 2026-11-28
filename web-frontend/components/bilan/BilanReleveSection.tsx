/**
 * «Le bilan» in the Cahier → Relevé: this week so far and the past weeks that were
 * played, each a quiet row to its page. Draws nothing while the switch is off (a 404),
 * on an error, or before the first answer — the Relevé stays as it was.
 */

import React from 'react';
import Link from 'next/link';

import { ArrowRightIcon, Surface } from '@/components/atelier-v2/ui';
import { NbSectionHead } from '@/components/cahiers/CahierV2';
import { bilanClient, bilanHref } from '@/lib/bilan-api';
import type { Bilan } from '@/lib/bilan-types';

import { bilanCopy, normalizeBilanLanguage } from './bilan-copy';
import { weekRow } from './bilan-model';

/** At most this many past weeks are listed here; the page itself walks further back. */
const PAST_WEEKS_SHOWN = 4;

export function BilanReleveSection({ language }: { language: unknown }) {
  const code = normalizeBilanLanguage(language);
  const copy = bilanCopy(code);
  const [bilan, setBilan] = React.useState<Bilan | null>(null);

  React.useEffect(() => {
    let alive = true;
    bilanClient()
      .week()
      .then((result) => {
        if (alive && result.enabled) setBilan(result.bilan);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  if (!bilan) return null;
  const [current, ...past] = bilan.weeks;
  const rows = [
    ...(current ? [{ ...current, isCurrent: true }] : []),
    ...past.filter((row) => row.daysPlayed > 0).slice(0, PAST_WEEKS_SHOWN).map((row) => ({ ...row, isCurrent: false })),
  ];
  return (
    <section id="bilan" className="nb-rv__sec" aria-label={copy.page_title}>
      <NbSectionHead t={copy.page_title} n={null} />
      <Surface className="bl-releve">
        {rows.map((row) => {
          const line = weekRow(row.weekStart, row.daysPlayed, row.isCurrent, code, copy);
          return (
            <Link key={row.weekStart} className="av2-row bl-releve__row" href={bilanHref(row.isCurrent ? null : row.weekStart)}>
              <span className="av2-row__main">
                <span className="av2-label">{line.label}</span>
                <span className="av2-body bl-releve__meta">{line.meta}</span>
              </span>
              <ArrowRightIcon size={18} />
            </Link>
          );
        })}
      </Surface>
    </section>
  );
}

export default BilanReleveSection;

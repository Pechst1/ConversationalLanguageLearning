/**
 * WP-122 B · Le Correcteur on La Une and in the Relevé, decided as data (the Radio's
 * pattern: `lib/radio-une.ts`).
 *
 * `pages/atelier.tsx` reads `GET /revue/correcteur/week` beside the day
 * (`useCorrecteurWeek`) and hands it here; this file says what Home draws.
 *
 * - The Correcteur is off (a 404), the read failed, or it has not answered: nothing.
 * - **The Papier day** (the Revue's hero is on La Une): no chip — the Papier is the
 *   day's route, as for the Radio.
 * - Any other day: one quiet chip «Le Correcteur» while a draft is waiting — the week
 *   has a dossier the learner has not corrected, and nothing was corrected this week
 *   yet (one draft a week is the habit; the desk's page still offers the others).
 *
 * **Precedence** (WP-119 §2 extended by WP-122): letter, Le Papier, La Radio,
 * Le Correcteur, words due. The chip goes right after the Radio chip, else after the
 * Revue chip, else after the letter, else first. HomeScreen shows at most two chips
 * (one once the day is done), so the Correcteur shows only when fewer than two of
 * letter · Papier · Radio are on La Une. Tested in `components/correcteur/correcteur.test.js`.
 */

import { useEffect, useState } from 'react';

import { correcteurCopy } from '@/components/correcteur/correcteur-copy';
import { correcteurClient } from '@/lib/correcteur-api';
import type { CrWeekResult } from '@/lib/correcteur-types';
import { oncePerLoad } from '@/lib/once-per-load';

/** The shape of HomeScreen's `HomeChip` (structural, so this file stays pure). */
export type CorrecteurHomeChip = { id: string; label: string; ariaLabel: string; href: string; shape: 'story' };

export const CORRECTEUR_HREF = '/correcteur';

/** The first dossier still waiting for the learner's marks, or null. */
export function correcteurWaiting(result: CrWeekResult | null | undefined): { id: string; titleFr: string } | null {
  if (!result || !result.enabled) return null;
  const first = result.week.dossiers[0];
  return first && first.id ? { id: first.id, titleFr: first.titleFr } : null;
}

/** `/correcteur?dossier=<id>` — the waiting draft's desk. */
export function correcteurHref(dossierId: string): string {
  return `${CORRECTEUR_HREF}?dossier=${encodeURIComponent(dossierId)}`;
}

export function correcteurHomeChip(result: CrWeekResult | null | undefined, language: unknown): CorrecteurHomeChip | null {
  const waiting = correcteurWaiting(result);
  if (!waiting || !result || !result.enabled || result.week.corrected.length > 0) return null;
  const copy = correcteurCopy(language);
  return { id: 'correcteur', label: copy.chip_label, ariaLabel: copy.chip_aria, href: correcteurHref(waiting.id), shape: 'story' };
}

/**
 * Home's chips with the Correcteur in them: after the Radio chip, else after the
 * Revue chip, else after the letter, else first. `papierDay` keeps the row as it is.
 */
export function withCorrecteurChip<T extends { id: string }>(chips: T[], chip: T | null, papierDay = false): T[] {
  if (!chip || papierDay) return chips;
  const after = ['radio', 'revue', 'courrier']
    .map((id) => chips.findIndex((entry) => entry.id === id))
    .find((index) => index >= 0);
  const at = (after ?? -1) + 1;
  return [...chips.slice(0, at), chip, ...chips.slice(at)];
}

/** `GET /revue/correcteur/week`, once per page load; null until it answers or when it fails. */
export function useCorrecteurWeek(): CrWeekResult | null {
  const [week, setWeek] = useState<CrWeekResult | null>(null);
  useEffect(() => {
    let alive = true;
    oncePerLoad('revue/correcteur/week', () => correcteurClient().week())
      .then((result) => {
        if (alive) setWeek(result);
      })
      .catch(() => {
        /* the Correcteur is an enrichment — La Une renders without it */
      });
    return () => {
      alive = false;
    };
  }, []);
  return week;
}

/**
 * «Papier · les rendez-vous» (2026-11-21) · «La une de la semaine» on La Une, decided as data
 * (the Correcteur's pattern: `lib/correcteur-une.ts`).
 *
 * `pages/atelier.tsx` reads `GET /revue/une` beside the day (`useUneSemaine`) — only on the
 * last day of the week (Sunday): any other day it asks nothing, so the switch off changes no
 * request on six days of seven and no payload on any. This file says what Home draws:
 *
 * - The switch off (a 404), the read failed, not answered, not Sunday: nothing.
 * - **The Papier day** (the Revue's hero is on La Une): no chip — the Papier is the day's route.
 * - Sunday of a week with two printed pieces or more (`due_today`): one quiet chip «La une de
 *   la semaine» → `/revue/une`. It goes after the Correcteur, else the Radio, else the Revue,
 *   else the letter, else first; HomeScreen shows at most two chips.
 */

import { useEffect, useState } from 'react';

import { RDV_FR } from '@/components/revue/rdv/rdv-copy';
import { oncePerLoad } from '@/lib/once-per-load';
import { rdvClient, type RvUneSemaine } from '@/lib/revue-rdv';

export const UNE_SEMAINE_HREF = '/revue/une';

export type UneHomeChip = { id: string; label: string; ariaLabel: string; href: string; shape: 'story' };

export function uneHomeChip(une: RvUneSemaine | null | undefined): UneHomeChip | null {
  if (!une || !une.dueToday) return null;
  // French: the paper's own name, as «Le Papier» and «Le Correcteur» are on their chips.
  return { id: 'une', label: RDV_FR.une_title, ariaLabel: `${RDV_FR.une_title} · ${une.datelineFr}`, href: UNE_SEMAINE_HREF, shape: 'story' };
}

export function withUneChip<T extends { id: string }>(chips: T[], chip: T | null, papierDay = false): T[] {
  if (!chip || papierDay) return chips;
  const after = ['correcteur', 'radio', 'revue', 'courrier']
    .map((id) => chips.findIndex((entry) => entry.id === id))
    .find((index) => index >= 0);
  const at = (after ?? -1) + 1;
  return [...chips.slice(0, at), chip, ...chips.slice(at)];
}

/** Sunday only: `GET /revue/une`, once per page load; null until it answers, when it fails or is off. */
export function useUneSemaine(now: () => Date = () => new Date()): RvUneSemaine | null {
  const [une, setUne] = useState<RvUneSemaine | null>(null);
  useEffect(() => {
    if (now().getDay() !== 0) return undefined;
    let alive = true;
    oncePerLoad('revue/une', () => rdvClient().une())
      .then((result) => {
        if (alive) setUne(result);
      })
      .catch(() => {
        /* an enrichment — La Une renders without it */
      });
    return () => {
      alive = false;
    };
    // Once per page load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return une;
}

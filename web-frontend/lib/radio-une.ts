/**
 * WP-122 A · La Radio on La Une, decided as data (the Revue's pattern: `lib/revue-une.ts`).
 *
 * `pages/atelier.tsx` reads `GET /revue/radio/week` beside the day (`useRadioWeek`) and
 * hands it here; this file says what Home draws. No HomeScreen change.
 *
 * - The Radio is off (a 404), the read failed, or it has not answered: nothing.
 * - **The Papier day** (the Revue's hero is on La Une): no Radio chip — the Papier is
 *   the day's route (spec §3.2: «a chip on La Une on non-Papier days»).
 * - Any other day: one quiet chip «La Radio» (its length, «50 s», in the accessible name: the 25-word Home) while there is an unheard
 *   bulletin and none was heard today (`week.chip`, decided by the server).
 *
 * **Precedence** (WP-119 §2 extended): letter, Le Papier, La Radio, words due. The
 * Radio chip goes right after the Revue chip (or after the letter when there is no
 * Revue chip, or first). HomeScreen shows at most two chips (one once the day is
 * done), so: letter + Papier → no Radio today; letter + Radio; Papier + Radio; Radio +
 * words due. The rule is tested in `components/radio/radio.test.js`.
 */

import { useEffect, useState } from 'react';

import { fill, radioCopy } from '@/components/radio/radio-copy';
import { oncePerLoad } from '@/lib/once-per-load';
import { radioClient } from '@/lib/radio-api';
import type { RadioWeekResult } from '@/lib/radio-types';

/** The shape of HomeScreen's `HomeChip` (structural, so this file stays pure). */
export type RadioHomeChip = { id: string; label: string; ariaLabel: string; href: string; shape: 'story' };

/** The chip's seconds: the server's estimate, rounded to 5 s, 50 when it gave none. */
export function radioChipSeconds(seconds: number | null | undefined): number {
  const value = typeof seconds === 'number' && Number.isFinite(seconds) && seconds > 0 ? seconds : 50;
  return Math.round(value / 5) * 5;
}

export function radioHomeChip(result: RadioWeekResult | null | undefined, language: unknown): RadioHomeChip | null {
  if (!result || !result.enabled) return null;
  const { week } = result;
  if (!week.chip || !week.current) return null;
  const copy = radioCopy(language);
  const s = radioChipSeconds(week.seconds);
  return {
    id: 'radio',
    label: fill(copy.chip_label, { s }),
    ariaLabel: fill(copy.chip_aria, { s }),
    href: `/radio?dossier=${encodeURIComponent(week.current.dossierId)}`,
    shape: 'story',
  };
}

/**
 * Home's chips with the Radio in them: after the Revue chip, else after the letter,
 * else first. `papierDay` (the Revue's hero is on La Une) keeps the row as it is.
 */
export function withRadioChip<T extends { id: string }>(chips: T[], chip: T | null, papierDay = false): T[] {
  if (!chip || papierDay) return chips;
  const revue = chips.findIndex((entry) => entry.id === 'revue');
  const letter = chips.findIndex((entry) => entry.id === 'courrier');
  const at = (revue >= 0 ? revue : letter) + 1; // 0 when there is neither
  return [...chips.slice(0, at), chip, ...chips.slice(at)];
}

/** `GET /revue/radio/week`, once per page load; null until it answers or when it fails. */
export function useRadioWeek(): RadioWeekResult | null {
  const [week, setWeek] = useState<RadioWeekResult | null>(null);
  useEffect(() => {
    let alive = true;
    oncePerLoad('revue/radio/week', () => radioClient().week())
      .then((result) => {
        if (alive) setWeek(result);
      })
      .catch(() => {
        /* the Radio is an enrichment — La Une renders without it */
      });
    return () => {
      alive = false;
    };
  }, []);
  return week;
}

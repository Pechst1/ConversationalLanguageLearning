/**
 * WP-119 · La Revue on La Une, as data for HomeScreen's existing slots
 * (design §4.1: «HomeScreen's `chips` and `hero` slots, as data: no change to
 * HomeScreen.tsx»).
 *
 * - Phase 1, and any day that is not the Revue day: one quiet chip
 *   «La Revue · sem. 40» to `/revue` (the chooser), until this week's Revue is
 *   filed. Absent when the Revue is off (`GET /revue/week` 404s).
 * - The Revue day (phase 3, `DayShape.REVUE`): `revueUneState` picks the hero
 *   card's state; the page renders `RvUneCard` in `hero` with `planHidden`.
 */

import type { RvOffer, RvWeekResult } from '@/lib/revue-types';

import { fill, revueCopy } from './revue-copy';
import { weekNumber } from './revue-model';
import type { RvUneCardState } from './RvUneCard';

/** The shape of HomeScreen's `HomeChip` (kept structural so this file stays pure). */
export type RevueHomeChip = { id: string; label: string; ariaLabel: string; href: string; shape: 'story' };

export function revueHomeChip(week: RvWeekResult | null | undefined, language: unknown): RevueHomeChip | null {
  if (!week || !week.enabled) return null;
  const offer = week.offer;
  if (offer.filed || !offer.recommended) return null;
  const copy = revueCopy(language);
  const n = weekNumber(offer.week.iso);
  return {
    id: 'revue',
    label: fill(copy.chip_label, { n }),
    ariaLabel: fill(copy.chip_aria, { n }),
    href: offer.resume ? `/revue?session=${encodeURIComponent(offer.resume.sessionId)}` : '/revue',
    shape: 'story',
  };
}

/** Which La Une card the offer calls for; null when there is nothing to show. */
export function revueUneState(offer: RvOffer): RvUneCardState | null {
  if (offer.filed) return 'filed';
  if (offer.resume) return 'resume';
  if (!offer.recommended) return null;
  return offer.recommended.evergreen || offer.evergreenOnly ? 'evergreen' : 'offer';
}

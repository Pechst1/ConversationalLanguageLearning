/**
 * WP-119 phase 1 · La Revue's entry on La Une, decided as data.
 *
 * `pages/atelier.tsx` fetches `revueClient().week()` beside the day and hands the
 * answer here; this file says what Home draws. It is pure (no React, no network)
 * so the rules are tested without mounting the page
 * (`components/atelier-v2/home/atelier-revue-entry.test.js`).
 *
 * The rules are the design spec's §2 (information architecture,
 * `docs/implementation/atelier-v2/WP-119-DESIGN.md`):
 *
 * - The Revue is off, the read failed, or it has not answered yet: nothing.
 *   Home is exactly what it was.
 * - **The Revue day** (`DayShape.REVUE`, dealt by the planner from phase 3,
 *   «never on a tentpole day, at most once a week»): `RvUneCard` in the `hero`
 *   slot with `planHidden`, because the card is the route. Its state comes from
 *   `revueUneState(offer)`. No Revue chip that day: the hero is the door.
 *   A special edition (WP-94 «Numéro spécial», `special`) never gives up its
 *   hero, whatever the planner dealt — it is the only special-day predicate the
 *   page has; there is no tentpole/finale flag on the day in the client.
 * - **Any other day of the week**: one quiet chip «La Revue · sem. 40» until
 *   this week's Revue is filed (`revueHomeChip`).
 *
 * **A letter and a Revue on the same day** (§2: «letter first, then Revue, then
 * words due»): on an ordinary day the letter keeps the first chip and the
 * Revue chip goes second, before words due / the after-day chip (HomeScreen
 * shows two, one once the day is done). On the Revue day the Revue is the day's route and takes La Une
 * whole: the card's word budget leaves no room for a chip while it carries the
 * press or the filed line, so the letter waits in the Courrier tab that day
 * and is back in the chip row the next (`revueHomeChips`).
 *
 * Until the planner deals `revue` (phase 3) no day is the Revue day, so phase 1
 * shows the chip only — which is what §2 schedules for phase 1.
 */

import { fill, type RevueCopy } from '@/components/revue/revue-copy';
import { revueHomeChip, revueUneState, type RevueHomeChip } from '@/components/revue/revue-home';
import { startedWhen } from '@/components/revue/revue-model';
import type { RvUneCardState } from '@/components/revue/RvUneCard';
import type { RvOffer, RvStoryCard, RvWeekResult } from '@/lib/revue-types';

/** The journey day shape the planner deals for a Revue day (phase 3). */
export const REVUE_DAY_SHAPE = 'revue';

export type RevueUneHero = {
  offer: RvOffer;
  story: RvStoryCard;
  state: RvUneCardState;
};

export type RevueUneEntry = {
  /** The chip, to be placed right after the letter's (see `withRevueChip`). */
  chip: RevueHomeChip | null;
  /** The hero card's data; the page renders `RvUneCard` and sets `planHidden`. */
  hero: RevueUneHero | null;
};

const NOTHING: RevueUneEntry = { chip: null, hero: null };

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null;

/** Today's day shape, from the journey snapshot or, before it starts, the envelope. */
export function dayShapeFrom(dayJourney: unknown, dayEnvelope: unknown): string | null {
  const envelope = asRecord(dayEnvelope);
  for (const holder of [asRecord(dayJourney), asRecord(envelope?.journey), envelope]) {
    const shape = holder?.day_shape;
    if (typeof shape === 'string' && shape.trim()) return shape;
  }
  return null;
}

/** The Revue day: the planner dealt `revue`, and it is not a special edition. */
export function isRevueDay(dayShape: string | null | undefined, special: boolean): boolean {
  return !special && dayShape === REVUE_DAY_SHAPE;
}

/** The story the card shows: the one being resumed or filed if it is in the offer, else the recommendation. */
function heroStory(offer: RvOffer, state: RvUneCardState): RvStoryCard | null {
  const stories = [offer.recommended, ...offer.alternatives].filter(Boolean) as RvStoryCard[];
  const wanted = state === 'resume' ? offer.resume?.dossierId : state === 'filed' ? offer.filed?.dossierId : null;
  return (wanted && stories.find((story) => story.dossierId === wanted)) || offer.recommended || stories[0] || null;
}

export function revueUneEntry({
  week,
  language,
  dayShape,
  special,
}: {
  week: RvWeekResult | null | undefined;
  language: unknown;
  dayShape: string | null | undefined;
  special: boolean;
}): RevueUneEntry {
  if (!week || !week.enabled) return NOTHING;
  const offer = week.offer;
  if (isRevueDay(dayShape, special)) {
    const state = revueUneState(offer);
    const story = state ? heroStory(offer, state) : null;
    if (state && story) return { chip: null, hero: { offer, story, state } };
  }
  return { chip: revueHomeChip(week, language), hero: null };
}

/** Puts the Revue chip right after the letter (or first when there is no letter). */
export function withRevueChip<T extends { id: string }>(chips: T[], chip: T | null): T[] {
  if (!chip) return chips;
  const letter = chips.findIndex((entry) => entry.id === 'courrier');
  const at = letter + 1; // 0 when there is no letter
  return [...chips.slice(0, at), chip, ...chips.slice(at)];
}

/**
 * Home's chip row with the Revue in it. Ordinary day: the Revue chip after the
 * letter. Revue day: no chips. The card spends the 18 words beside the masthead
 * (`uneCardParts`; `home.test.js` draws it with `chips: []`), and even one
 * two-word chip breaks WP-81's 25 — the French resume card and the French filed
 * card both reach 26. (The design's #filed wants «the one post-day chip»; that
 * needs the filed card to budget for it first — RvUneCard's business, not La
 * Une's.)
 */
export function revueHomeChips<T extends { id: string }>(entry: RevueUneEntry, chips: T[]): T[] {
  if (entry.hero) return [];
  return withRevueChip(chips, entry.chip as T | null);
}

/** The resume card's one clause: «Commencée hier · ta question attend.» */
export function revueResumeLine(offer: RvOffer, copy: RevueCopy, now: Date = new Date()): string | null {
  const resume = offer.resume;
  if (!resume) return null;
  const when = startedWhen(resume.startedAt, copy, now);
  if (resume.openQuestionFr) return fill(copy.resume_line_question, { when });
  const what = (copy.beat_names as Record<string, string>)[resume.beat];
  return what ? fill(copy.resume_line, { when, what }) : when;
}

/** The hero press: the session being resumed, else `/revue`. */
export function revueOpenHref(offer: RvOffer): string {
  return '/revue' + (offer.resume ? `?session=${encodeURIComponent(offer.resume.sessionId)}` : '');
}

/** A row picked in «Autre sujet ?», or a free request that matched. */
export function revueDossierHref(dossierId: string): string {
  return `/revue?dossier=${encodeURIComponent(dossierId)}`;
}

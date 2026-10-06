/**
 * WP-31 «Répétition» — presentation-independent state.
 *
 * Every function here is pure over the wire envelope, so the node suite can
 * exercise all eight states with no DOM and the renderer holds no policy.
 *
 * Two rules the page must not be able to break, and which therefore live here:
 *
 *  1. **A rehearsal the provider could not prepare is a state, not an error.**
 *     `not_prepared` renders «Répétition non préparée» with a retry. There is no
 *     branch that shows a scene when the server sent none.
 *  2. **The private rubric arrives only when the rehearsal is over.** The server
 *     sends `rubric_native: null` while it is live; nothing in the renderer may
 *     invent a substitute, so `phaseFor` never exposes a rubric before
 *     `finished`.
 *
 * WP-82: every sentence is chrome, read from `rehearsal-copy.ts` in the chrome
 * language. Each function takes that language last and defaults to French.
 */

import type { RehearsalEnvelope, RehearsalView } from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { fill, rehearsalCopy } from './rehearsal-copy';

export type RehearsalPhase =
  | { kind: 'loading' }
  /** `/state` itself failed. Not a rehearsal state: the page is simply unread. */
  | { kind: 'load_failed'; message: string }
  /** The weekly cap is 0 — the feature is off, and the page says so. */
  | { kind: 'disabled' }
  /** Nothing open, and there is room this week. */
  | { kind: 'declare'; previous: RehearsalView | null }
  /** Nothing open, and no room until `nextSlotAt`. */
  | { kind: 'capped'; nextSlotAt: string | null; previous: RehearsalView | null }
  /** The provider did not answer. The declaration survived. */
  | { kind: 'not_prepared'; rehearsal: RehearsalView }
  /** A scene is ready, or is being played. */
  | { kind: 'rehearsing'; rehearsal: RehearsalView; turnIndex: number }
  /** Rehearsed; the real event has not arrived yet. */
  | { kind: 'waiting'; rehearsal: RehearsalView }
  /** «Comment ça s'est passé ?» */
  | { kind: 'debrief'; rehearsal: RehearsalView }
  /** The debrief is recorded. Terminal. */
  | { kind: 'debriefed'; rehearsal: RehearsalView };

const LIVE_STATUSES = new Set(['ready', 'rehearsing']);

/** The next turn the learner owes, which is also the idempotency key. */
export function nextTurnIndex(rehearsal: RehearsalView): number {
  return rehearsal.turns.length;
}

/** Turns left in the bound this rehearsal declared. Never negative. */
export function turnsRemaining(rehearsal: RehearsalView): number {
  return Math.max(0, (rehearsal.turns_total || 0) - rehearsal.turns.length);
}

/**
 * Which state the page is in.
 *
 * `debrief_due` is the server's own answer to "is a finished rehearsal owed a
 * debrief today"; the client never recomputes it from the date, because the
 * learner's day and the server's day are not always the same one.
 */
export function phaseFor(
  envelope: RehearsalEnvelope | null,
  options: { loading?: boolean; error?: string | null } = {},
): RehearsalPhase {
  if (options.error) return { kind: 'load_failed', message: options.error };
  if (options.loading || !envelope) return { kind: 'loading' };

  const due = envelope.debrief_due ?? null;
  if (due) return { kind: 'debrief', rehearsal: due };

  const current = envelope.rehearsal ?? null;
  if (current) {
    if (current.status === 'not_prepared') return { kind: 'not_prepared', rehearsal: current };
    if (LIVE_STATUSES.has(current.status)) {
      return { kind: 'rehearsing', rehearsal: current, turnIndex: nextTurnIndex(current) };
    }
    if (current.status === 'rehearsed') {
      return current.debrief_available
        ? { kind: 'debrief', rehearsal: current }
        : { kind: 'waiting', rehearsal: current };
    }
    if (current.status === 'debriefed') return { kind: 'debriefed', rehearsal: current };
  }

  if (envelope.cap.limit <= 0) return { kind: 'disabled' };
  if (envelope.cap.remaining <= 0) {
    return { kind: 'capped', nextSlotAt: envelope.cap.next_slot_at ?? null, previous: current };
  }
  return { kind: 'declare', previous: current };
}

/** «il vous reste 1 répétition cette semaine» — a sentence, never a fraction. */
export function capSentence(cap: RehearsalEnvelope['cap'], language: ControlLanguage = 'fr'): string {
  const copy = rehearsalCopy(language);
  if (cap.limit <= 0) return copy.cap_off;
  if (cap.remaining <= 0) return copy.cap_spent;
  if (cap.remaining === 1) return copy.cap_one;
  return fill(copy.cap_many, { n: cap.remaining });
}

/** When the next slot frees, or null when there is nothing to say. */
export function nextSlotSentence(iso: string | null, language: ControlLanguage = 'fr'): string | null {
  if (!iso) return null;
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return null;
  const copy = rehearsalCopy(language);
  const label = when.toLocaleDateString(copy.locale, { weekday: 'long', day: 'numeric', month: 'long' });
  return fill(copy.next_slot, { date: label });
}

/** The date of the real event, or null when nobody named one. */
export function eventDateSentence(rehearsal: RehearsalView, language: ControlLanguage = 'fr'): string | null {
  if (!rehearsal.event_date) return null;
  const when = new Date(`${rehearsal.event_date}T12:00:00`);
  if (Number.isNaN(when.getTime())) return null;
  const copy = rehearsalCopy(language);
  const label = when.toLocaleDateString(copy.locale, { weekday: 'long', day: 'numeric', month: 'long' });
  return fill(copy.event_date, { date: label });
}

export type DebriefOutcome = 'done' | 'partly' | 'not_yet';

/** The three outcomes, in the order the learner reads them. */
export function debriefChoices(
  language: ControlLanguage = 'fr',
): ReadonlyArray<{ id: DebriefOutcome; label: string; hint: string }> {
  const copy = rehearsalCopy(language);
  return [
    { id: 'done', label: copy.debrief_done, hint: copy.debrief_done_hint },
    { id: 'partly', label: copy.debrief_partly, hint: copy.debrief_partly_hint },
    { id: 'not_yet', label: copy.debrief_not_yet, hint: copy.debrief_not_yet_hint },
  ];
}
export const DEBRIEF_CHOICES = debriefChoices('fr');

/**
 * What the result panel says about the rehearsal itself.
 *
 * Deliberately modest: the rehearsal score is *not* the package's metric, so it
 * is reported as what was covered, never as a grade or a percentage.
 */
export function resultSentence(rehearsal: RehearsalView, language: ControlLanguage = 'fr'): string {
  const copy = rehearsalCopy(language);
  const result = rehearsal.result;
  if (!result) return copy.result_none;
  if (result.outcome === 'met') return copy.result_met;
  if (result.outcome === 'partially_met') {
    const template = result.points_covered > 1 ? copy.result_partial_many : copy.result_partial_one;
    return fill(template, { n: result.points_covered, total: result.points_total });
  }
  return copy.result_not_yet;
}

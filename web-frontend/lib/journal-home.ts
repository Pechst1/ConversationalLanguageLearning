/**
 * P9 · «Le journal de bord» gets a door on Home.
 *
 * The journal (Cahier → Journal, `components/cahiers/JournalTab.tsx`) asks the
 * learner, the day after a scene, to retell it from memory in two to four
 * sentences. Home never pointed to it, so it was found only by learners who
 * opened the Cahier. Now, while a retell is waiting, Home's chip row carries one
 * chip for it, second after the letter, and the chip leaves once the retell is
 * sent or skipped.
 *
 * «Waiting» is the journal's own answer, read from `GET /journal/state` (its
 * existing «today» envelope; no new server field): `status === 'offered'` and no
 * text on the entry. 'written', 'skipped', 'unavailable' and 'none' draw nothing.
 * The route creates the day's offer on first read; that is idempotent and writes
 * no learner content (see `journal.py: read_state`), the same read the tab makes.
 *
 * Pure apart from `useJournalWaiting`, so `p9-rooms.test.js` reads it directly.
 */

import { useEffect, useState } from 'react';

import { atelierCopy } from '@/lib/atelier-v2-copy';
import { oncePerLoad } from '@/lib/once-per-load';
import type { JournalEnvelope } from '@/services/api';
import apiService from '@/services/api';

export const JOURNAL_HOME_HREF = '/notebook?mode=journal';

/** The shape of HomeScreen's `HomeChip` (structural, so this file stays pure). */
export type JournalHomeChip = {
  id: 'journal';
  label: string;
  meta: string;
  ariaLabel: string;
  href: string;
  shape: 'story';
};

/** What Home needs to know: is a retell waiting, and how old is its scene. */
export type JournalWaiting = { daysAgo: number | null };

/** A retell is waiting: offered, and nothing written on it yet. */
export function journalWaiting(envelope: JournalEnvelope | null | undefined): JournalWaiting | null {
  if (!envelope || envelope.status !== 'offered') return null;
  const entry = envelope.entry;
  if (!entry || entry.status !== 'offered' || (entry.entry_text || '').trim()) return null;
  const days = entry.cue?.days_ago;
  return { daysAgo: typeof days === 'number' && Number.isFinite(days) ? days : null };
}

/**
 * The chip, in Home's chrome language. «Raconter hier» when the scene was
 * yesterday; a scene from further back is «la scène», never «hier».
 * Two to four sentences: «≈ 2 min».
 */
export function journalHomeChip(waiting: JournalWaiting | null, language: unknown): JournalHomeChip | null {
  if (!waiting) return null;
  const copy = atelierCopy(language);
  return {
    id: 'journal',
    label: waiting.daysAgo === 1 ? copy.home_journal : copy.home_journal_older,
    meta: '≈ 2 min',
    ariaLabel: `${copy.home_journal_aria} · 2 min`,
    href: JOURNAL_HOME_HREF,
    shape: 'story',
  };
}

/**
 * Home's chips with the journal in them: right after the letter, else first.
 * Applied last, so the Revue and the Radio (which also follow the letter) come
 * after it. An empty row stays empty: on the Revue day the Papier takes La Une
 * whole (`revueHomeChips`), and the journal waits in the Cahier that day.
 */
export function withJournalChip<T extends { id: string }>(chips: T[], chip: T | null, papierDay = false): T[] {
  if (!chip || papierDay) return chips;
  const letter = chips.findIndex((entry) => entry.id === 'courrier');
  const at = letter + 1; // 0 when there is no letter
  return [...chips.slice(0, at), chip, ...chips.slice(at)];
}

/** `GET /journal/state`, once per page load; null until it answers, when nothing waits, or on failure. */
export function useJournalWaiting(enabled: boolean): JournalWaiting | null {
  const [waiting, setWaiting] = useState<JournalWaiting | null>(null);
  useEffect(() => {
    if (!enabled) return undefined;
    let alive = true;
    oncePerLoad('journal/state', () => apiService.getJournalState())
      .then((envelope) => {
        if (alive) setWaiting(journalWaiting(envelope));
      })
      .catch(() => {
        /* the journal is an enrichment — Home renders without it */
      });
    return () => {
      alive = false;
    };
  }, [enabled]);
  return waiting;
}

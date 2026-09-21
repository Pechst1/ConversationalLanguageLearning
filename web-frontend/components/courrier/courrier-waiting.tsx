/* WP-65 — the letter that is waiting, read from one endpoint.
 *
 * Why `/missions/today` and not a cheaper read: WP-64 materialises the day's
 * second letter *inside* that call (`MissionScheduler.today` sweeps overdue
 * letters, then opens at most one chain instalment or story-born letter). A
 * Home row that asked anything else would show yesterday's Courrier and the
 * chain would never advance until the learner opened the Courrier by hand —
 * which is the loop WP-64's "Still open" note warned about.
 *
 * Coalesced through `oncePerLoad`, under the same key on every surface, so La
 * Une and the Feuilleton reader ask once between them. A failed read leaves the
 * row off: an entry nobody can open is worse than no entry (WP-38's rule, kept).
 */

import React, { useEffect, useState } from 'react';

import { oncePerLoad } from '@/lib/once-per-load';
import apiService, { RealWorldMission } from '@/services/api';

import { CrLetterRow, crLetterHint } from './Correspondance';

/** The one key both surfaces share, so two rows are one request. */
export const COURRIER_TODAY_KEY = 'missions/today';

/** A letter still owed: available (unread) or half answered. `lapsed` and
 *  `completed` are not waiting on anybody and never raise a row. */
export function courrierAwaitingLetter(today: {
  active_mission?: RealWorldMission | null;
  weekly_mission?: RealWorldMission | null;
  post_session_recommendation?: RealWorldMission | null;
} | null): RealWorldMission | null {
  if (!today) return null;
  const open = (mission: RealWorldMission | null | undefined) =>
    mission && (mission.status === 'available' || mission.status === 'in_progress') ? mission : null;
  return open(today.active_mission) || open(today.weekly_mission) || open(today.post_session_recommendation) || null;
}

export function useCourrierLetter(): RealWorldMission | null {
  const [letter, setLetter] = useState<RealWorldMission | null>(null);
  useEffect(() => {
    let alive = true;
    oncePerLoad(COURRIER_TODAY_KEY, () => apiService.getMissionsToday())
      .then((today) => { if (alive) setLetter(courrierAwaitingLetter(today)); })
      .catch(() => { /* the Courrier is an enrichment here — the screen stands without it */ });
    return () => { alive = false; };
  }, []);
  return letter;
}

/* ---------- La Une ----------
   The shape `HomeScreen` already renders for the dossier and the rehearsal: a
   label, one clause, a link. Deliberately NOT a second press bar — an unread
   letter is the day's second action, and the design contract allows one
   primary per screen. */

export type CourrierHomeEntry = {
  id: string;
  label: string;
  hint: string;
  href: string;
  ariaLabel: string;
};

export function courrierHomeEntry(letter: RealWorldMission | null, now?: Date): CourrierHomeEntry | null {
  if (!letter) return null;
  const courrier = letter.courrier || null;
  const correspondent = letter.correspondent || courrier?.correspondent || null;
  const name = String(correspondent?.name || '').trim();
  const hint = crLetterHint({
    name,
    chain: letter.chain || courrier?.chain || null,
    origin: courrier?.origin || null,
    expiresAt: letter.expires_at || courrier?.expires_at || null,
    now,
  });
  const label = letter.status === 'in_progress' ? 'Votre réponse est commencée' : 'Une lettre vous attend';
  return {
    id: 'courrier',
    label,
    hint,
    href: `/missions?mission=${letter.id}`,
    ariaLabel: `${label} — ${hint}`,
  };
}

/** La Une's Courrier row, as a `HomeEntry`-shaped value or `null`. */
export function useCourrierHomeEntry(): CourrierHomeEntry | null {
  const letter = useCourrierLetter();
  return courrierHomeEntry(letter);
}

/* ---------- the Feuilleton ----------
   WP-65 §4: when a character picked up a pen about a scene the learner just
   played (`courrier.origin === 'story_born'`), the Feuilleton says so — in its
   own margin, as a row, without leaving the episode.

   Only a story-born letter earns this row. The weekly Courrier has nothing to
   do with the episode, and advertising it here would turn the reader into a
   second Home screen. */

export function courrierStoryBornLetter(letter: RealWorldMission | null): RealWorldMission | null {
  if (!letter) return null;
  return String(letter.courrier?.origin || '') === 'story_born' ? letter : null;
}

export function CrStoryLetterRow() {
  const letter = courrierStoryBornLetter(useCourrierLetter());
  if (!letter) return null;
  const correspondent = letter.correspondent || letter.courrier?.correspondent || null;
  const name = String(correspondent?.name || '').trim();
  return (
    <CrLetterRow
      name={name}
      href={`/missions?mission=${letter.id}`}
      hint={name ? `${name} vous écrit après l’épisode.` : 'Quelqu’un vous écrit après l’épisode.'}
    />
  );
}

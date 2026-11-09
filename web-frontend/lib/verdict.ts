/**
 * #333: one screen state for every surface that judges what a learner wrote.
 *
 * The server sends the one verdict shape as `check` (`app/core/verdict.py`); a screen reads
 * its state here and its words from `CHECK_COPY`, so «you were right» and «nothing read this»
 * can't look alike on any surface. Every line that says a check did not run carries
 * `data-check` with the state, so a walk can name it.
 */

export type CheckEdit = {
  span: string;
  replacement: string;
  note?: string;
};

export type CheckLike = {
  outcome?: string | null;
  call?: string | null;
  retryable?: boolean | null;
  edits?: CheckEdit[] | null;
};

export type CheckState =
  /** The second read is still running: the surface's own «Je relis…». */
  | 'checking'
  /** Nothing read it and the rules found nothing. */
  | 'not_checked'
  /** The full check did not run; the rules found real fixes. */
  | 'basic'
  /** A key or a model decided: show the verdict. */
  | 'settled';

export function checkState(check: CheckLike | null | undefined): CheckState {
  if (!check) return 'settled';
  if (check.call === 'pending') return 'checking';
  if (check.outcome !== 'not_checked') return 'settled';
  return check.edits?.length ? 'basic' : 'not_checked';
}

/** Whether this state says nobody read the answer. */
export function isUnread(state: CheckState): state is 'not_checked' | 'basic' {
  return state === 'not_checked' || state === 'basic';
}

/** The words of the two unread states. Each surface's copy table points here. */
export const CHECK_COPY = {
  en: {
    not_checked: "Answer saved, not checked yet. It doesn't count yet.",
    basic: 'Basic check only. The full check did not run.',
  },
  de: {
    not_checked: 'Antwort gespeichert, noch nicht geprüft. Sie zählt noch nicht.',
    basic: 'Nur Grundprüfung. Die volle Prüfung lief nicht.',
  },
  fr: {
    not_checked: 'Réponse enregistrée, pas encore vérifiée. Elle ne compte pas encore.',
    basic: 'Vérification de base seulement. La vérification complète n’a pas eu lieu.',
  },
} as const;

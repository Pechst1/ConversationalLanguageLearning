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
  corrected?: string | null;
  /** Package V stage 3: when an answer saved unread was checked since (the job or «Ask again»). */
  checked_since?: string | null;
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

/** Whether asking again can reach a reader: `retryable: false` means there is none to ask (#724). */
export function canAskAgain(check: CheckLike | null | undefined): boolean {
  return isUnread(checkState(check)) && check?.retryable !== false;
}

/**
 * #724: the line of an unread answer. The rules' fixes make it a basic check; with none, an
 * answer that can be checked again says «not checked yet» next to its retry, and one that
 * cannot says plainly that checking is unavailable, never «not checked yet» over a dead retry.
 */
export function unreadLine(check: CheckLike | null | undefined): 'basic' | 'not_checked' | 'unavailable' {
  if (checkState(check) === 'basic') return 'basic';
  return canAskAgain(check) ? 'not_checked' : 'unavailable';
}

/** Whether this answer was saved unread and has been checked since: the screen says so once. */
export function checkedSince(check: CheckLike | null | undefined): boolean {
  return Boolean(check?.checked_since) && checkState(check) === 'settled';
}

/** The words of the two unread states, and of one read since. Each surface's copy table points here. */
export const CHECK_COPY = {
  en: {
    not_checked: "Answer saved, not checked yet. It doesn't count yet.",
    basic: 'Basic check only. The full check did not run.',
    unavailable: 'Checking is not available right now, so this answer does not count. Go on with the next one.',
    checked_since: 'Checked since. It counts now.',
  },
  de: {
    not_checked: 'Antwort gespeichert, noch nicht geprüft. Sie zählt noch nicht.',
    basic: 'Nur Grundprüfung. Die volle Prüfung lief nicht.',
    unavailable: 'Die Prüfung ist gerade nicht verfügbar, darum zählt diese Antwort nicht. Mach mit der nächsten weiter.',
    checked_since: 'Inzwischen geprüft. Sie zählt jetzt.',
  },
  fr: {
    not_checked: 'Réponse enregistrée, pas encore vérifiée. Elle ne compte pas encore.',
    basic: 'Vérification de base seulement. La vérification complète n’a pas eu lieu.',
    unavailable: 'La vérification n’est pas disponible pour le moment : cette réponse ne compte pas. Passe à la suivante.',
    checked_since: 'Vérifiée depuis. Elle compte maintenant.',
  },
} as const;

/** One line of the fixes list: a fix with its reason, or several mechanical fixes of one kind. */
export type FixLine = { wrong?: string; fixed?: string; why?: string };
export type FixRow =
  | { kind: 'one'; fixed?: string; why?: string }
  | { kind: 'apostrophes' | 'accents'; fixes: string[] };

const LETTERS_ONLY = /[\s'’‘`]/g;

function unmarked(text: string): string {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

function mechanicalKind(line: FixLine): 'apostrophes' | 'accents' | null {
  const wrong = String(line.wrong || '').trim();
  const fixed = String(line.fixed || '').trim();
  if (!wrong || !fixed || wrong === fixed) return null;
  if (unmarked(wrong) === unmarked(fixed)) return 'accents';
  if (unmarked(wrong).replace(LETTERS_ONLY, '') === unmarked(fixed).replace(LETTERS_ONLY, '')) return 'apostrophes';
  return null;
}

/**
 * The fixes as the card lists them (#133): every fix once, with two or more of one mechanical
 * kind on one line («3 apostrophes»), where the first of them stood.
 */
export function fixRows(lines: FixLine[]): FixRow[] {
  const groups: Record<'apostrophes' | 'accents', FixLine[]> = {
    apostrophes: lines.filter((line) => mechanicalKind(line) === 'apostrophes'),
    accents: lines.filter((line) => mechanicalKind(line) === 'accents'),
  };
  const placed = new Set<string>();
  const rows: FixRow[] = [];
  for (const line of lines) {
    const kind = mechanicalKind(line);
    if (!kind || groups[kind].length < 2) {
      rows.push({ kind: 'one', fixed: line.fixed, why: line.why });
    } else if (!placed.has(kind)) {
      placed.add(kind);
      rows.push({ kind, fixes: groups[kind].map((item) => String(item.fixed)) });
    }
  }
  return rows;
}

/** How many rows the card opens with; «N more» opens the rest. */
export const FIX_ROWS_SHOWN = 3;

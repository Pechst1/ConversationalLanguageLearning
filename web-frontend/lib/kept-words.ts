/**
 * WP-78 «Garder» — the pure half of tap-to-keep, for the word-help sheet.
 *
 * A word can be kept only when the sheet found it in the lexicon (a real
 * meaning, not the line's translation) and knows the sentence it came from:
 * the server stores the sentence as the word's example in the learner's own
 * Lexique and refuses anything else. WP-82: the sheet's chrome follows the one
 * language rule — `KEEP_COPY` is the French table, `keepCopy(language)` picks
 * the learner's (up to A2) for the reader that knows it.
 */

import type { ControlLanguage } from '@/types/daily-journey';

export type KeepState =
  | { kind: 'idle' }
  | { kind: 'saving' }
  | { kind: 'kept'; already: boolean }
  | { kind: 'refused'; message: string };

export const KEEP_COPY = {
  action: 'Garder',
  saving: 'Enregistrement…',
  kept: 'Gardé dans votre lexique — il reviendra demain.',
  already: 'Déjà dans votre lexique.',
  failed: 'Ce mot n’a pas pu être gardé. Réessayez plus tard.',
} as const;

type KeepCopy = { [K in keyof typeof KEEP_COPY]: string };

const KEEP_COPY_BY_LANGUAGE: Record<ControlLanguage, KeepCopy> = {
  fr: KEEP_COPY,
  en: {
    action: 'Keep',
    saving: 'Saving…',
    kept: 'Kept in your Lexique — it will come back tomorrow.',
    already: 'Already in your Lexique.',
    failed: 'This word could not be kept. Try again later.',
  },
  de: {
    action: 'Behalten',
    saving: 'Wird gespeichert…',
    kept: 'In deinem Lexique gespeichert — es kommt morgen wieder.',
    already: 'Schon in deinem Lexique.',
    failed: 'Dieses Wort konnte nicht gespeichert werden. Versuch es später noch einmal.',
  },
};

/** The keep copy in `language`; French when none is given. */
export function keepCopy(language?: ControlLanguage | null): KeepCopy {
  return (language && KEEP_COPY_BY_LANGUAGE[language]) || KEEP_COPY;
}

/** Offer «Garder» only for a dictionary entry with its sentence. */
export function canKeep(glossKind: string, sentence: string | null | undefined): boolean {
  return glossKind === 'gloss' && Boolean((sentence || '').trim());
}

/** The server's French refusal when there is one, a calm generic line otherwise. */
export function keepRefusalMessage(error: unknown, language?: ControlLanguage | null): string {
  // The server's refusal is written in French; another chrome language
  // keeps its own sentence rather than mixing two languages in one sheet.
  if (language && language !== 'fr') return keepCopy(language).failed;
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (detail && typeof detail === 'object') {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === 'string' && message.trim()) return message;
  }
  return KEEP_COPY.failed;
}

/** What the sheet says once the keep has an answer. */
export function keepStatusLine(state: KeepState, language?: ControlLanguage | null): string | null {
  const copy = keepCopy(language);
  switch (state.kind) {
    case 'saving':
      return copy.saving;
    case 'kept':
      return state.already ? copy.already : copy.kept;
    case 'refused':
      return state.message;
    default:
      return null;
  }
}

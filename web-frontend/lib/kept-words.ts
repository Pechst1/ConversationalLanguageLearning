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
  /** WP-138: `retryable` — a network or server failure (try again); otherwise the
   *  word itself cannot be kept (no entry, no meaning in your language), for good. */
  | { kind: 'refused'; message: string; retryable: boolean };

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
export function canKeep(
  glossKind: string,
  sentence: string | null | undefined,
  glossLanguage?: string | null,
  learnerLanguage?: string | null,
): boolean {
  // The server keeps a word only with a meaning in the learner's own language
  // (`no_gloss_in_learner_language`); a fallback gloss in another language is shown
  // but not offered to keep — the walk saw 38 «Garder» taps refused in one run.
  if (glossLanguage && learnerLanguage && glossLanguage !== learnerLanguage) return false;
  return glossKind === 'gloss' && Boolean((sentence || '').trim());
}

/**
 * WP-138: why a word cannot be kept, per server code, in the sheet's language.
 * Each of these is permanent — a property of the word, not of the moment — so
 * none of them says «try again later».
 */
const KEEP_REFUSALS: Record<ControlLanguage, Record<string, string>> = {
  fr: {
    empty_term: 'Ce mot ne peut pas être gardé.',
    no_sentence: 'Ce mot ne peut être gardé qu’avec sa phrase.',
    not_in_lexicon: 'Ce mot n’est pas encore dans le lexique.',
    no_gloss_in_learner_language: 'Pas encore de traduction dans votre langue pour ce mot.',
    refused: 'Ce mot ne peut pas être gardé.',
  },
  en: {
    empty_term: 'This word can’t be kept.',
    no_sentence: 'A word can only be kept with the sentence it came from.',
    not_in_lexicon: 'This word isn’t in the dictionary yet, so it can’t be kept.',
    no_gloss_in_learner_language: 'There is no English translation for this word yet, so it can’t be kept.',
    refused: 'This word can’t be kept.',
  },
  de: {
    empty_term: 'Dieses Wort kann nicht gespeichert werden.',
    no_sentence: 'Ein Wort kann nur mit seinem Satz gespeichert werden.',
    not_in_lexicon: 'Dieses Wort steht noch nicht im Wörterbuch und kann nicht gespeichert werden.',
    no_gloss_in_learner_language: 'Für dieses Wort gibt es noch keine deutsche Übersetzung, deshalb kann es nicht gespeichert werden.',
    refused: 'Dieses Wort kann nicht gespeichert werden.',
  },
};

type KeepError = { response?: { status?: number; data?: { detail?: unknown } } };

/**
 * What a failed keep means: the server's structured refusal (a permanent reason,
 * said in the sheet's language) or a failure worth retrying (no answer, a server
 * error, an expired session).
 */
export function keepRefusal(
  error: unknown,
  language?: ControlLanguage | null,
): { message: string; retryable: boolean; code: string | null } {
  const lang: ControlLanguage = (language && KEEP_REFUSALS[language] ? language : 'fr') as ControlLanguage;
  const table = KEEP_REFUSALS[lang];
  const response = (error as KeepError)?.response;
  const status = response?.status;
  const detail = response?.data?.detail;
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const { code, retryable, message } = detail as { code?: unknown; retryable?: unknown; message?: unknown };
    if (typeof code === 'string' && code) {
      if (retryable === true) return { message: keepCopy(lang).failed, retryable: true, code };
      const known = table[code];
      // An unknown code: the server's French line for the French reader, else the
      // plain permanent refusal — never another language's sentence in this sheet.
      const fallback = lang === 'fr' && typeof message === 'string' && message.trim() ? message : table.refused;
      return { message: known || fallback, retryable: false, code };
    }
  }
  // A 4xx other than an expired session is the request itself: retrying sends it again.
  if (typeof status === 'number' && status >= 400 && status < 500 && status !== 401 && status !== 408 && status !== 429) {
    return { message: table.refused, retryable: false, code: null };
  }
  return { message: keepCopy(lang).failed, retryable: true, code: null };
}

/** The refusal's line alone (see `keepRefusal`). */
export function keepRefusalMessage(error: unknown, language?: ControlLanguage | null): string {
  return keepRefusal(error, language).message;
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

/**
 * WP-78 «Garder» — the pure half of tap-to-keep, for the word-help sheet.
 *
 * A word can be kept only when the sheet found it in the lexicon (a real
 * meaning, not the line's translation) and knows the sentence it came from:
 * the server stores the sentence as the word's example in the learner's own
 * Lexique and refuses anything else. Chrome is French on every screen.
 */

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

/** Offer «Garder» only for a dictionary entry with its sentence. */
export function canKeep(glossKind: string, sentence: string | null | undefined): boolean {
  return glossKind === 'gloss' && Boolean((sentence || '').trim());
}

/** The server's French refusal when there is one, a calm generic line otherwise. */
export function keepRefusalMessage(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (detail && typeof detail === 'object') {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === 'string' && message.trim()) return message;
  }
  return KEEP_COPY.failed;
}

/** What the sheet says once the keep has an answer. */
export function keepStatusLine(state: KeepState): string | null {
  switch (state.kind) {
    case 'saving':
      return KEEP_COPY.saving;
    case 'kept':
      return state.already ? KEEP_COPY.already : KEEP_COPY.kept;
    case 'refused':
      return state.message;
    default:
      return null;
  }
}

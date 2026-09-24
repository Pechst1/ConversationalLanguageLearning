/**
 * WP-75 — «A win before an account»: the sixty-second taste.
 *
 * One authored scene at Le Mistral, played before sign-up with no network and
 * no model: Romy says hello, the learner answers with a tap, then orders a
 * coffee from tiles, and Romy reacts. Everything a learner reads that
 * *explains* is in their own language; everything said in the story is French.
 *
 * Grading is local and exact — there is nothing to be generous about in a
 * three-option choice or a four-tile bank — and pure, so it is unit-tested.
 */

import type { OnboardingLanguage } from './onboarding-locale';

export type TasteMood = 'neutral' | 'happy' | 'cross';

export type TasteLine = {
  /** Who speaks. A key of the cast portraits. */
  characterId: string;
  speaker: string;
  fr: string;
  native: Record<OnboardingLanguage, string>;
};

export type TasteOption = { id: string; fr: string };

export type TasteChoiceItem = {
  kind: 'choice';
  id: string;
  line: TasteLine;
  /** The instruction, in the learner's language. */
  task: Record<OnboardingLanguage, string>;
  options: TasteOption[];
  answerId: string;
  /** What Romy says back to a right answer. */
  reply: TasteLine;
};

export type TasteTilesItem = {
  kind: 'tiles';
  id: string;
  line: TasteLine;
  task: Record<OnboardingLanguage, string>;
  tiles: TasteOption[];
  /** Tile ids, in order. */
  answer: string[];
  reply: TasteLine;
};

export type TasteItem = TasteChoiceItem | TasteTilesItem;

const ROMY = { characterId: 'romy_tremblay', speaker: 'Romy' } as const;

export const TASTE_ITEMS: TasteItem[] = [
  {
    kind: 'choice',
    id: 'greet',
    line: {
      ...ROMY,
      fr: 'Bonjour ! Moi, c’est Romy.',
      native: {
        en: 'Hello! I’m Romy.',
        de: 'Hallo! Ich bin Romy.',
        fr: 'Bonjour ! Moi, c’est Romy.',
      },
    },
    task: {
      en: 'Say hello back.',
      de: 'Grüßen Sie zurück.',
      fr: 'Répondez-lui.',
    },
    options: [
      { id: 'merci', fr: 'Merci !' },
      { id: 'bonjour', fr: 'Bonjour !' },
      { id: 'au-revoir', fr: 'Au revoir !' },
    ],
    answerId: 'bonjour',
    reply: {
      ...ROMY,
      fr: 'Bienvenue au Mistral !',
      native: {
        en: 'Welcome to Le Mistral!',
        de: 'Willkommen im Mistral!',
        fr: 'Bienvenue au Mistral !',
      },
    },
  },
  {
    kind: 'tiles',
    id: 'order',
    line: {
      ...ROMY,
      fr: 'Vous prenez quoi ?',
      native: {
        en: 'What will you have?',
        de: 'Was nehmen Sie?',
        fr: 'Vous prenez quoi ?',
      },
    },
    task: {
      en: 'Order a coffee.',
      de: 'Bestellen Sie einen Kaffee.',
      fr: 'Commandez un café.',
    },
    tiles: [
      { id: 'svp', fr: 's’il vous plaît' },
      { id: 'merci', fr: 'merci' },
      { id: 'cafe', fr: 'Un café,' },
      { id: 'bonsoir', fr: 'Bonsoir' },
    ],
    answer: ['cafe', 'svp'],
    reply: {
      ...ROMY,
      fr: 'Parfait ! Margaux, deux cafés !',
      native: {
        en: 'Perfect! Margaux, two coffees!',
        de: 'Perfekt! Margaux, zwei Kaffee!',
        fr: 'Parfait ! Margaux, deux cafés !',
      },
    },
  },
];

export type TasteVerdict = 'pending' | 'correct' | 'wrong';

/** A choice is right exactly when the tapped option is the answer. */
export function gradeChoice(item: TasteChoiceItem, optionId: string | null): TasteVerdict {
  if (!optionId) return 'pending';
  return optionId === item.answerId ? 'correct' : 'wrong';
}

/**
 * Tiles are graded the moment the learner has placed as many tiles as the
 * answer holds — no «check» tap. Fewer is still pending; the right tiles in
 * the wrong order are wrong.
 */
export function gradeTiles(item: TasteTilesItem, placed: readonly string[]): TasteVerdict {
  if (placed.length < item.answer.length) return 'pending';
  if (placed.length !== item.answer.length) return 'wrong';
  return item.answer.every((id, index) => placed[index] === id) ? 'correct' : 'wrong';
}

/** The portrait follows the verdict (WP-D2: the map lives in `lib/cast-faces`). */
export { moodForVerdict } from './cast-faces';

/** The assembled French sentence for a set of placed tiles. */
export function tilesSentence(item: TasteTilesItem, placed: readonly string[]): string {
  const byId = new Map(item.tiles.map((tile) => [tile.id, tile.fr]));
  return placed.map((id) => byId.get(id) ?? '').filter(Boolean).join(' ');
}

/** The explaining chrome of the taste and the landing, per language. */
export type TasteCopy = {
  /** The app's promise, ≤ 12 words. */
  promise: string;
  translate: string;
  hide_translation: string;
  correct: string;
  wrong: string;
  remove_tile: string;
  tiles_hint: string;
  closing: string;
  language: string;
  status: { selected: string; correct: string; wrong: string };
  options_label: string;
};

export const TASTE_COPY: Record<OnboardingLanguage, TasteCopy> = {
  en: {
    promise: 'Learn French inside a story. Your first scene takes a minute.',
    translate: 'Tap to translate',
    hide_translation: 'Hide translation',
    correct: 'Right!',
    wrong: 'Not quite. Try again.',
    remove_tile: 'Remove the last word',
    tiles_hint: 'Tap the words in order',
    closing: 'Romy, Marin and Lila are waiting. Keep your story.',
    language: 'Language',
    status: { selected: 'selected', correct: 'right', wrong: 'wrong' },
    options_label: 'Your answer',
  },
  de: {
    promise: 'Französisch lernen in einer Geschichte. Die erste Szene dauert eine Minute.',
    translate: 'Tippen zum Übersetzen',
    hide_translation: 'Übersetzung ausblenden',
    correct: 'Richtig!',
    wrong: 'Nicht ganz. Noch einmal.',
    remove_tile: 'Letztes Wort entfernen',
    tiles_hint: 'Tippen Sie die Wörter der Reihe nach an',
    closing: 'Romy, Marin und Lila warten. Behalten Sie Ihre Geschichte.',
    language: 'Sprache',
    status: { selected: 'ausgewählt', correct: 'richtig', wrong: 'falsch' },
    options_label: 'Ihre Antwort',
  },
  fr: {
    promise: 'Apprenez le français dans une histoire. La première scène prend une minute.',
    translate: 'Toucher pour traduire',
    hide_translation: 'Masquer la traduction',
    correct: 'Exact !',
    wrong: 'Pas tout à fait. Réessayez.',
    remove_tile: 'Retirer le dernier mot',
    tiles_hint: 'Touchez les mots dans l’ordre',
    closing: 'Romy, Marin et Lila vous attendent. Gardez votre histoire.',
    language: 'Langue',
    status: { selected: 'choisi', correct: 'juste', wrong: 'faux' },
    options_label: 'Votre réponse',
  },
};

/**
 * The taste's buttons. 2026-09-24: a button is the app's own words, so before an
 * account exists it follows the detected onboarding language like the rest of
 * the screen (the one-language rule; a newcomer reads as a beginner). Only the
 * names of places — La Une, Le Courrier… — stay French.
 */
export type TasteNav = { start: string; have_account: string; next: string; keep: string; retry: string };

export const TASTE_NAV: Record<OnboardingLanguage, TasteNav> = {
  en: {
    start: 'Start',
    have_account: 'I already have an account',
    next: 'Continue',
    keep: 'Keep your story',
    retry: 'Try again',
  },
  de: {
    start: 'Loslegen',
    have_account: 'Ich habe schon ein Konto',
    next: 'Weiter',
    keep: 'Behalten Sie Ihre Geschichte',
    retry: 'Nochmal versuchen',
  },
  fr: {
    start: 'Commencer',
    have_account: 'J’ai déjà un compte',
    next: 'Continuer',
    keep: 'Gardez votre histoire',
    retry: 'Réessayer',
  },
};

// ---------------------------------------------------------------------------
// Completion flag — so sign-up does not need to say anything more about it.
// ---------------------------------------------------------------------------

export const TASTE_DONE_STORAGE_KEY = 'atelier.tasteDone';

export function rememberTasteDone(): void {
  try {
    window.localStorage.setItem(TASTE_DONE_STORAGE_KEY, '1');
  } catch {
    try {
      window.sessionStorage.setItem(TASTE_DONE_STORAGE_KEY, '1');
    } catch {
      // Neither store is available; nothing downstream depends on it.
    }
  }
}

export function tasteWasDone(): boolean {
  try {
    if (window.localStorage.getItem(TASTE_DONE_STORAGE_KEY) === '1') return true;
  } catch {
    // fall through
  }
  try {
    return window.sessionStorage.getItem(TASTE_DONE_STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

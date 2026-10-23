/**
 * Le Lexique · what one sitting of the deck has filed (pages/vocabulary/review.tsx).
 *
 * The deck opens on the copy cached on the device and asks the server for the
 * fresh one at the same time. The learner can file cards before that answer
 * lands, so the fresh deck must not undo them: a card filed in this sitting
 * stays filed, and the progress count keeps it.
 */
import { nextAgainQueue } from './recall-ladder';

export type DeckProgress = {
  /** Cards filed in this sitting, right or wrong. */
  filed: ReadonlySet<number>;
  /** WP-115b successive relearning: filed wrong, asked again at the end. */
  again: readonly number[];
};

export const EMPTY_PROGRESS: DeckProgress = { filed: new Set(), again: [] };

/** `revalidate`: the server's copy of the deck already on screen. `new-deck`: another deck. */
export type DeckLoad = 'revalidate' | 'new-deck';

export function fileCard(progress: DeckProgress, wordId: number, wrong: boolean): DeckProgress {
  return {
    filed: new Set(progress.filed).add(wordId),
    again: nextAgainQueue([...progress.again], wordId, wrong),
  };
}

/**
 * The fresh copy of the deck on screen keeps what was filed: the server may
 * have dealt it before those reviews were saved, and resetting here brought
 * the card just answered with «je sais» straight back. Another deck («Encore N
 * mots», the next deck of the day, «Actualiser») starts from nothing.
 */
export function progressAfterLoad(progress: DeckProgress, load: DeckLoad): DeckProgress {
  return load === 'revalidate' ? progress : EMPTY_PROGRESS;
}

/** The cards still to ask, in deck order, then the ones to ask again. */
export function remainingCards<T extends { word_id: number }>(ordered: readonly T[], progress: DeckProgress): T[] {
  const main = ordered.filter((item) => !progress.filed.has(item.word_id));
  const byId = new Map(ordered.map((item) => [item.word_id, item]));
  const again = progress.again.map((id) => byId.get(id)).filter(Boolean) as T[];
  return [...main, ...again];
}

const DECK_LISTS = ['due_words', 'fragile_words', 'linked_words', 'topic_compatible_words', 'new_words'] as const;

type DeckLists = { [K in (typeof DECK_LISTS)[number]]: ReadonlyArray<{ word_id: number }> };

/** The deck as the device should cache it once cards are filed: without them. */
export function withoutFiled<C extends DeckLists>(context: C, filed: ReadonlySet<number>): C {
  const next = { ...context };
  for (const key of DECK_LISTS) {
    next[key] = (context[key] || []).filter((item) => !filed.has(item.word_id)) as C[typeof key];
  }
  return next;
}

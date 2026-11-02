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

/**
 * Owner, 1 Nov: «wenn ich auf „Weiß ich“ gehe, bleibt die Karte trotzdem da und ich komme
 * nicht weiter». The page filed a card only once the server had answered the review: a
 * slow, refused or failed request left the card on screen with every grade button
 * disabled, and each grade button reached the filing its own way. Every grade now goes
 * through {@link gradeAction} and is filed at once; the server's answer can only move a
 * card into or out of «ask again» ({@link settleVerdict}, {@link reviewNotSaved}), never
 * hold the deck.
 */
export type GradeAction = { kind: 'reveal' } | { kind: 'file'; rating: number; wrong: boolean };

/**
 * What a grade does, for every grade the page offers (Encore, Dur, «Weiß ich» / Bien,
 * Facile, the graded card's one «Weiter», the keys 1–4): an unturned card is turned
 * first (a grade never files blind); a turned card is filed. An answered card is right
 * or wrong by its answer (the device's own fold until the server's verdict lands); a
 * self-rated card is wrong only on «Encore».
 */
export function gradeAction({
  revealed,
  rating,
  graded,
  typedMatches,
}: {
  revealed: boolean;
  rating: number;
  graded: boolean;
  typedMatches: boolean;
}): GradeAction {
  if (!revealed) return { kind: 'reveal' };
  return { kind: 'file', rating, wrong: graded ? !typedMatches : rating === 0 };
}

/** The server's verdict on a card already filed: it moves the card into or out of «ask again». */
export function settleVerdict(progress: DeckProgress, wordId: number, wrong: boolean): DeckProgress {
  if (!progress.filed.has(wordId)) return progress;
  const queued = progress.again.includes(wordId);
  if (queued === wrong) return progress;
  return { filed: progress.filed, again: nextAgainQueue([...progress.again], wordId, wrong) };
}

/** A review the server did not save: the card is asked again at the end, never lost or stuck. */
export function reviewNotSaved(progress: DeckProgress, wordId: number): DeckProgress {
  return settleVerdict(progress, wordId, true);
}

/**
 * What the card's foot offers (owner, 1 Nov). «Weiß ich» on an unturned card only turned
 * it, so the card stayed: a button said one thing and did another. Before the card is
 * turned the foot holds one button, which turns it; the grades (Encore, «Weiß ich», Dur,
 * Facile) appear only on a turned card, and a typed answer is filed by its one «Weiter».
 */
export type DeckFoot = 'turn' | 'graded-next' | 'grades';

export function deckFoot({ revealed, graded }: { revealed: boolean; graded: boolean }): DeckFoot {
  if (!revealed) return 'turn';
  return graded ? 'graded-next' : 'grades';
}

/**
 * The deck's order is the server's (`deck_order`, `app/services/deck_order.py`): the
 * device never re-sorts the deck by tiers of its own (owner requests, 1 and 2 Nov). A card the
 * order does not name keeps its place after it; with no order the payload's stands.
 */
export function deckOrdered<T extends { word_id: number }>(items: T[], order?: readonly number[] | null): T[] {
  if (!order?.length) return items;
  const position = new Map(order.map((id, index) => [id, index]));
  return items
    .map((item, index) => ({ item, at: position.get(item.word_id) ?? order.length + index }))
    .sort((a, b) => a.at - b.at)
    .map(({ item }) => item);
}

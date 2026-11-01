/**
 * The word a card asks and answers with (/vocabulary/review) — the one place a card's
 * French word is turned into what the learner reads.
 *
 * Owner request, 1 Nov: a French noun on a card always carries its article — on the
 * front of a recognition card, on the back of a production card, on the back of a
 * card asked from the learner's side, and on the deck's last line. Every one of those
 * reads `shownFrench`, which is `frenchHeadword` (`lib/french-noun.ts`). The bare
 * French stays for what is not shown as the card's word: grading the typed answer
 * (an article is never required, `normalizeAnswer`), finding the word in its example
 * to mark it, telling an example from a «word - gloss» line.
 */

import { learnerGloss } from './glosses';
import { frenchHeadword } from './french-noun';
import { lineAnswer, linePrompt, type CardMode, type LadderCue } from '../components/lexique/recall-ladder';

export type CardWordItem = {
  word?: string | null;
  direction?: string | null;
  gender?: string | null;
  part_of_speech?: string | null;
  /** 'pl' for a noun used in the plural only («les gens»). */
  number?: string | null;
  translation?: string | null;
  translations?: Record<string, string | null | undefined> | null;
};

/**
 * A card direction reads "<asked side>_to_<answer side>". Only the first half matters:
 * `de_to_fr`/`en_to_fr` ask from the learner's side, everything else asks from the
 * target language.
 */
export function asksFromLearnerSide(item: CardWordItem): boolean {
  const [from, to] = String(item.direction || '').split('_to_');
  return Boolean(from && to && from !== 'fr');
}

/** The card's French, bare (graded, searched in its example). */
export function bareFrench(item: CardWordItem): string {
  return String(item.translations?.fr || item.word || '').trim();
}

/** The card's French as the learner reads it: a noun with its article. */
export function shownFrench(item: CardWordItem): string {
  return frenchHeadword({
    word: bareFrench(item),
    gender: item.gender,
    partOfSpeech: item.part_of_speech,
    number: item.number,
  });
}

/** The meaning in the learner's language. */
export function cardMeaning(item: CardWordItem): string {
  return learnerGloss(item);
}

/** The side of the card that is asked (recognition): the French, or the meaning. */
export function askedSide(item: CardWordItem): string {
  if (asksFromLearnerSide(item)) return learnerGloss(item, String(item.word || ''));
  return shownFrench(item);
}

/** The side of the card that answers it (recognition): the meaning, or the French. */
export function answerSide(item: CardWordItem): string {
  if (asksFromLearnerSide(item)) return shownFrench(item) || String(item.word || '');
  return learnerGloss(item);
}

export type CardTexts = {
  /** The card's front. */
  prompt: string;
  /** The card's back, as shown. */
  answer: string;
  /** What a typed answer is graded against (no article required). */
  expected: string;
};

/** What the card shows on each side, and what a typed answer is graded against. */
export function cardTexts({
  item,
  mode,
  cue,
  listenPrompt,
}: {
  item: CardWordItem | null;
  mode: CardMode;
  cue: LadderCue | null;
  listenPrompt: string;
}): CardTexts {
  if (!item) return { prompt: '', answer: '', expected: '' };
  const meaning = cardMeaning(item);
  const french = bareFrench(item);
  const shown = shownFrench(item);
  const prompt =
    mode === 'audio'
      ? listenPrompt
      : mode === 'production'
        ? meaning || shown
        : mode === 'scene' || mode === 'rescue'
          ? linePrompt(cue) || meaning || shown
          : askedSide(item);
  if (mode === 'recognition') {
    const answer = answerSide(item);
    return { prompt, answer, expected: asksFromLearnerSide(item) ? french : answer };
  }
  // Owner decision 2026-10-08: a line card is answered with the form in its line.
  const expected = lineAnswer(mode, cue, french);
  return { prompt, answer: expected === french ? shown : expected, expected };
}

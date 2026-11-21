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
  /**
   * Whether the front is the French itself. Decided here, with the front, so the page
   * never guesses it from the mode alone (a production card whose word has no gloss
   * falls back to its French; a recognition card stored `en_to_fr` asks by the gloss).
   */
  promptIsFrench: boolean;
  /**
   * The line under a front in the learner's language that says the French is asked
   * («How do you say it in French?»); empty on a French front and on an audio card.
   * Walk finding #725: «school» and «forty» stood alone on the front, among cards that
   * all showed their French, and nothing said the card went the other way.
   */
  ask: string;
  /** The card's back, as shown. */
  answer: string;
  /** Whether the back is the French (every card but a recognition card asked in French). */
  answerIsFrench: boolean;
  /** What a typed answer is graded against (no article required). */
  expected: string;
};

/** What the card shows on each side, and what a typed answer is graded against. */
export function cardTexts({
  item,
  mode,
  cue,
  listenPrompt,
  askPrompt = '',
}: {
  item: CardWordItem | null;
  mode: CardMode;
  cue: LadderCue | null;
  listenPrompt: string;
  /** The chrome line that asks for the French (`ask_in_french`). */
  askPrompt?: string;
}): CardTexts {
  if (!item) return { prompt: '', promptIsFrench: false, ask: '', answer: '', answerIsFrench: false, expected: '' };
  const meaning = cardMeaning(item);
  const french = bareFrench(item);
  const shown = shownFrench(item);
  const line = mode === 'scene' || mode === 'rescue' ? linePrompt(cue) : '';
  // Which side the front shows: the ear; the French (a recognition card, a blanked French
  // line, a word with no gloss to ask by); or the meaning, in the learner's language.
  const side: 'audio' | 'fr' | 'learner' =
    mode === 'audio'
      ? 'audio'
      : mode === 'recognition'
        ? asksFromLearnerSide(item) && learnerGloss(item) ? 'learner' : 'fr'
        : line || !meaning ? 'fr' : 'learner';
  const prompt =
    side === 'audio'
      ? listenPrompt
      : mode === 'recognition'
        ? askedSide(item)
        : side === 'learner' ? meaning : line || shown;
  const front = { prompt, promptIsFrench: side === 'fr', ask: side === 'learner' ? askPrompt : '' };
  if (mode === 'recognition') {
    const answer = answerSide(item);
    const fromLearner = asksFromLearnerSide(item);
    return { ...front, answer, answerIsFrench: fromLearner, expected: fromLearner ? french : answer };
  }
  // Owner decision 2026-10-08: a line card is answered with the form in its line.
  const expected = lineAnswer(mode, cue, french);
  return { ...front, answer: expected === french ? shown : expected, answerIsFrench: true, expected };
}

/**
 * The example a word card quotes on its back (/vocabulary/review).
 *
 * #398 (live walk 31 Oct): every word card's back read « lampe - lamp », « quinze -
 * fifteen », « coopérative - co-operative »: a card with no example sentence printed its
 * headword and its gloss in the example's quotation marks. That is neither a sentence nor
 * an example, and the headword and its meaning are on the card already. With no example,
 * the card quotes nothing.
 */

type CardText = { french?: string | null; meaning?: string | null; example?: string | null };

const fold = (value: string) =>
  value
    .normalize('NFC')
    .toLowerCase()
    .replace(/[«»“”"]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

/** The card's example sentence, or '' when there is none (a «word - gloss» line is none). */
export function cardExample({ french, meaning, example }: CardText): string {
  const text = String(example || '').trim();
  if (!text) return '';
  const word = String(french || '').trim();
  const gloss = String(meaning || '').trim();
  if (word && gloss && [' - ', ' – ', ' — '].some((dash) => fold(`${word}${dash}${gloss}`) === fold(text))) return '';
  return text;
}

/** The line quoted under the card once it is turned: the example (and, by ear, the meaning too). */
export function cardContextText({ mode, meaning, example }: CardText & { mode: string }): string {
  const sentence = String(example || '').trim();
  if (mode === 'audio') return [String(meaning || '').trim(), sentence].filter(Boolean).join(' · ');
  return sentence;
}

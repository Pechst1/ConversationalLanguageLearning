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

/** An example cut around the card's word, so the card can mark it. */
export type MarkedExample = { before: string; word: string; after: string };

const ARTICLES = new Set(['le', 'la', 'les', "l'", 'un', 'une']);
const LETTER = 'A-Za-z0-9À-ÖØ-öø-ÿŒœ';

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** The word without its article («la serrure» → «serrure»), as the server's `_head`. */
function head(word: string): string {
  const text = String(word || '').trim();
  const [first, ...rest] = text.split(' ');
  return rest.length && ARTICLES.has(first.toLowerCase()) ? rest.join(' ') : text;
}

/** The example with its first occurrence of the word marked (none found: nothing marked). */
export function markExample(example: string, french: string): MarkedExample | null {
  const sentence = String(example || '').trim();
  if (!sentence) return null;
  for (const form of [head(french), String(french || '').trim()]) {
    if (!form) continue;
    const pattern = new RegExp(`(^|[^${LETTER}])(${escapeRegExp(form)})(?=$|[^${LETTER}])`, 'i');
    const match = pattern.exec(sentence);
    if (match) {
      const start = match.index + match[1].length;
      const end = start + match[2].length;
      return { before: sentence.slice(0, start), word: sentence.slice(start, end), after: sentence.slice(end) };
    }
  }
  return { before: sentence, word: '', after: '' };
}

/**
 * Owner decision 2026-11-01 — «you translate the word, and you get the example sentence
 * along with it». What each face of a word card quotes:
 *
 * - recognition (the French word asked): the example on the front, the word marked;
 *   asked from the learner's side the French sentence would give the answer away, so it
 *   waits for the back;
 * - production (the meaning asked, type the French): the French example waits for the
 *   back — any version of it on the front shows the word or a form of it (an inflected
 *   «allons» for «aller» survives a substitution); the front quotes the sentence's
 *   translation in the learner's language, when there is one, which holds no French;
 * - once turned, every card quotes the example and, when there is one, its translation;
 * - audio is unchanged: nothing on the front, its own context line on the back.
 */
export type CardFaces = {
  frontExample: MarkedExample | null;
  frontTranslation: string;
  backExample: MarkedExample | null;
  backTranslation: string;
};

export function cardFaces({
  mode,
  french,
  meaning,
  example,
  exampleTranslation,
  promptIsFrench,
}: CardText & { mode: string; exampleTranslation?: string | null; promptIsFrench: boolean }): CardFaces {
  const sentence = cardExample({ french, meaning, example });
  const translation = sentence ? String(exampleTranslation || '').trim() : '';
  if (mode === 'audio') return { frontExample: null, frontTranslation: '', backExample: null, backTranslation: '' };
  const marked = markExample(sentence, String(french || ''));
  return {
    frontExample: mode === 'recognition' && promptIsFrench ? marked : null,
    frontTranslation: mode === 'production' ? translation : '',
    backExample: marked,
    backTranslation: marked ? translation : '',
  };
}

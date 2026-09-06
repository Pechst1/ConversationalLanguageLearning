/* Splitting a French line into tappable words.
 *
 * Élision ("l'arrivée", "qu'il") keeps the article with the punctuation run and
 * makes the *content* word the tappable one, because "l" is not a lookup.
 * Hyphenated compounds ("rendez-vous", "est-ce") stay one word, because they
 * are one entry.
 *
 * Pure module: unit-tested with `node --test`.
 */

export type FrenchToken = {
  key: string;
  text: string;
  /** true when this run is a word the learner can tap for help */
  word: boolean;
  /** the normalized surface form to look up (empty for non-words) */
  term: string;
};

const WORD_RE = /[A-Za-zÀ-ÖØ-öø-ÿŒœ]+(?:-[A-Za-zÀ-ÖØ-öø-ÿŒœ]+)*/g;

/* One-or-two letter élision prefixes: when a word run is immediately followed
   by an apostrophe, it is a clitic, not a lookup. */
const ELISION = new Set(['l', 'd', 'j', 'n', 'm', 't', 's', 'c', 'qu', 'lorsqu', 'puisqu', 'jusqu']);

const APOSTROPHES = new Set(["'", '’', 'ʼ']);

export function lookupTerm(raw: string): string {
  return String(raw || '')
    .replace(/[’ʼ]/g, "'")
    .replace(/^[^A-Za-zÀ-ÖØ-öø-ÿŒœ]+|[^A-Za-zÀ-ÖØ-öø-ÿŒœ]+$/g, '')
    .toLowerCase()
    .trim();
}

export function tokenizeFrench(text: string, keyPrefix = 't'): FrenchToken[] {
  const source = String(text || '');
  if (!source) return [];
  const tokens: FrenchToken[] = [];
  let cursor = 0;
  let index = 0;
  WORD_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  // eslint-disable-next-line no-cond-assign
  while ((match = WORD_RE.exec(source)) !== null) {
    const start = match.index;
    const end = start + match[0].length;
    if (start > cursor) {
      tokens.push({ key: `${keyPrefix}-s${index}`, text: source.slice(cursor, start), word: false, term: '' });
      index += 1;
    }
    const nextChar = source.charAt(end);
    const isClitic = APOSTROPHES.has(nextChar) && ELISION.has(match[0].toLowerCase());
    const term = isClitic ? '' : lookupTerm(match[0]);
    tokens.push({
      key: `${keyPrefix}-w${index}`,
      text: match[0],
      word: Boolean(term),
      term,
    });
    index += 1;
    cursor = end;
  }
  if (cursor < source.length) {
    tokens.push({ key: `${keyPrefix}-s${index}`, text: source.slice(cursor), word: false, term: '' });
  }
  return tokens;
}

/* The sentence a tapped word came from, trimmed to the clause so the help sheet
   can quote real context instead of a whole paragraph. */
export function sentenceAround(text: string, term: string): string {
  const source = String(text || '').trim();
  if (!source) return '';
  const parts = source.split(/(?<=[.!?…»])\s+/).filter(Boolean);
  if (parts.length <= 1) return source;
  const needle = lookupTerm(term);
  const hit = parts.find((part) => tokenizeFrench(part).some((token) => token.term === needle));
  return (hit || parts[0]).trim();
}

/**
 * Le Déclic (grammar pilot, owner's choice of 9 November 2026): which letters of an answer carry
 * the rule. The options of a drill already differ exactly where the rule lives, so the marks are
 * read from them on the device and no item needs new content:
 *
 *   «Margaux est rentrée» against «Margaux est rentré» and «Margaux a rentré» marks «est» and «e».
 *
 * When the comparison is not telling (the options share nothing), the sentence stays plain rather
 * than marking a guess. Display only: nothing here decides whether an answer is right.
 */

import { splitSentences } from './sentence-split';

export type DiffSegment = { text: string; mark: boolean };
/** One word and the white space that follows it; joined back they are the text, unchanged. */
export type DiffWord = { segments: DiffSegment[]; space: string };

type Token = { start: number; end: number; key: string };

/** A word keeps its apostrophe, so «j'ai» is the two words «j'» and «ai». */
const WORD = /[^\s'’ʼ]+['’ʼ]?/g;
const TRAILING_PUNCTUATION = /[.,;:!?…»"”]+$/;
/** A shared start this long is a stem («rentr|ée»); a shorter one is a coincidence («es|t»). */
const MIN_STEM = 3;

function clean(text: unknown): string {
  return String(text ?? '').normalize('NFC').trim();
}

function fold(text: string): string {
  return text.toLowerCase().replace(/['’ʼ‘`´]/g, "'");
}

function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  const pattern = new RegExp(WORD.source, 'g');
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text))) {
    tokens.push({ start: match.index, end: match.index + match[0].length, key: fold(match[0]).replace(TRAILING_PUNCTUATION, '') });
  }
  return tokens;
}

/** The longest run of words two answers share, in order, as index pairs. */
function commonPairs(a: Token[], b: Token[]): Array<[number, number]> {
  const table = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      table[i][j] = a[i].key === b[j].key ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  const pairs: Array<[number, number]> = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i].key === b[j].key) {
      pairs.push([i, j]);
      i += 1;
      j += 1;
    } else if (table[i + 1][j] >= table[i][j + 1]) i += 1;
    else j += 1;
  }
  return pairs;
}

function sharedStart(a: string, b: string): number {
  let index = 0;
  while (index < a.length && index < b.length && a[index] === b[index]) index += 1;
  return index;
}

/**
 * Which characters of `text` differ from the `others`. A word that is merely shorter than its rival
 * («parti» against «partie») has no letter of its own to mark, so it counts only when nothing else
 * in the answer differs.
 */
function marksOf(text: string, tokens: Token[], others: string[]): boolean[] {
  const hard = new Array<boolean>(text.length).fill(false);
  const soft = new Array<boolean>(text.length).fill(false);
  const paint = (marks: boolean[], from: number, to: number) => {
    for (let index = from; index < to; index += 1) marks[index] = true;
  };
  others.forEach((other) => {
    const rival = tokenize(clean(other));
    const pairs: Array<[number, number]> = [...commonPairs(tokens, rival), [tokens.length, rival.length]];
    let i = 0;
    let j = 0;
    pairs.forEach(([nextI, nextJ]) => {
      for (let k = i; k < nextI; k += 1) {
        const token = tokens[k];
        const opposite = j + (k - i) < nextJ ? rival[j + (k - i)].key : '';
        const shared = sharedStart(token.key, opposite);
        const wordEnd = token.start + token.key.length;
        if (shared === token.key.length && opposite) paint(soft, token.start, wordEnd);
        else if (shared >= MIN_STEM) paint(hard, token.start + shared, wordEnd);
        else paint(hard, token.start, wordEnd);
      }
      i = nextI + 1;
      j = nextJ + 1;
    });
  });
  return hard.some(Boolean) ? hard : soft;
}

function telling(tokens: Token[], marks: boolean[]): boolean {
  if (!marks.some(Boolean)) return false;
  if (tokens.length < 3) return true;
  // Three or more words and every one of them differs: nothing here points at a rule.
  return !tokens.every((token) => {
    for (let index = token.start; index < token.start + token.key.length; index += 1) {
      if (!marks[index]) return false;
    }
    return true;
  });
}

/**
 * An option sharing no word or stem with the answer («autrement» against «mains» and «main») says
 * nothing about where the rule is, so it counts only when no option is closer.
 */
function closest(tokens: Token[], rivals: string[]): string[] {
  const related = rivals.filter((rival) =>
    tokenize(rival).some((other) => tokens.some((token) => token.key === other.key || sharedStart(token.key, other.key) >= MIN_STEM)),
  );
  return related.length ? related : rivals;
}

/** `text` as words, with the letters that differ from `others` marked. No `others`: all plain. */
export function ruleDiff(text: unknown, others: unknown[] = []): DiffWord[] {
  const value = clean(text);
  const tokens = tokenize(value);
  const rivals = others.map(clean).filter((other) => other && fold(other) !== fold(value));
  const found = rivals.length ? marksOf(value, tokens, closest(tokens, rivals)) : [];
  const marks = telling(tokens, found) ? found : new Array<boolean>(value.length).fill(false);
  return tokens.map((token, index) => {
    const segments: DiffSegment[] = [];
    for (let at = token.start; at < token.end; at += 1) {
      const mark = Boolean(marks[at]);
      const last = segments[segments.length - 1];
      if (last && last.mark === mark) last.text += value[at];
      else segments.push({ text: value[at], mark });
    }
    return { segments, space: value.slice(token.end, tokens[index + 1]?.start ?? token.end) };
  });
}

/** The parts of a diff that are marked, in order. */
export function markedParts(words: DiffWord[]): string[] {
  return words.flatMap((word) => word.segments.filter((segment) => segment.mark).map((segment) => segment.text));
}

/**
 * The explanation without the sentence that only repeats «you chose X, this needs Y», which the
 * corrected sentence on screen already shows. Any language: it is the sentence naming both forms.
 * An explanation written another way comes back whole.
 */
export function whyWithoutEcho(why: unknown, learner: unknown, target: unknown): string {
  const text = String(why ?? '').trim();
  const chosen = wordsOf(clean(learner));
  const needed = wordsOf(clean(target));
  if (!text || !chosen.length || !needed.length) return text;
  // #896: sentences are cut by the one shared splitter, the server's mirror.
  const sentences = splitSentences(text);
  if (!sentences.length) return text;
  return sentences
    .filter((sentence) => {
      const words = wordsOf(sentence);
      return !(containsRun(words, chosen) && containsRun(words, needed));
    })
    .join(' ')
    .trim();
}

function wordsOf(text: string): string[] {
  return fold(text).split(/[^a-zà-öø-ÿœ0-9']+/).filter(Boolean);
}

/** Whole words only: «a» is not found in «Aller». */
function containsRun(words: string[], run: string[]): boolean {
  for (let start = 0; start + run.length <= words.length; start += 1) {
    if (run.every((word, offset) => words[start + offset] === word)) return true;
  }
  return false;
}

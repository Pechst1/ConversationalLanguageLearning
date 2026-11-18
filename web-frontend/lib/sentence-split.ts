/**
 * #896 — the one sentence splitter on the device.
 *
 * Every surface that cuts a text into sentences reads it the same way as the server's
 * `sentences` (`app/services/sentence_line.py`); this is its mirror, step for step, and
 * `tests/fixtures/sentence_split_cases.json` pins both (`lib/sentence-split.test.js`,
 * `tests/test_sentence_split_896.py`). A scan, not one regex: older iOS web views refuse
 * lookbehind.
 *
 * A sentence ends on . ! ? … that is no title's or initial's (one closing mark may
 * follow, or a French-spaced « »»), before a word that opens a new one: a capital, a
 * digit, an opening quote or bracket, a dash. Three things a «?» or a «.» there does not
 * end:
 *   - a quotation the sentence carries on after («„Tu est française, Margaux ?“ stimmt
 *     nicht; …», #893);
 *   - a hesitation that runs on in small letters («déjà… le groupe qui …», #849);
 *   - a chain of alternatives («Tu prends l'appartement pour toi ? Pour toi et les
 *     autres ? Ou tu dis au revoir à tout ça ?», #827).
 */

const STOPS = '.!?…';
/** The one closing mark a stop may carry before the space. */
const CLOSERS = '"»”“’)]›';
/** Where a quotation opens, and what closes it («“» closes «„» and opens English quotes). */
const QUOTE_PAIRS: Record<string, string> = { '«': '»', '„': '“”', '“': '”', '‹': '›', '"': '"' };
/** What a new sentence opens on. */
const OPENS = /^[A-ZÀ-ÖØ-Þ0-9«"“„([—–]/;
/** The words a question opens on when it goes on asking the question before it. */
export const CHAIN_WORDS = new Set(['ou', 'et', 'pour', 'ni', 'sinon', 'or', 'and', 'for', 'nor', 'oder', 'und', 'für']);
const TITLE_ABBREVIATIONS = ['M', 'MM', 'Mme', 'Mmes', 'Mlle', 'Mlles', 'Dr', 'Pr', 'Me', 'Mgr', 'St', 'Ste', 'Mr', 'Mrs', 'Ms'];
const TITLE_WORD = new RegExp(`^(?:${TITLE_ABBREVIATIONS.join('|')}|[A-ZÀ-ÖØ-Þ])\\.$`);
const LEADING_MARKS = '«“„"\'‘’([—–- ';
const FIRST_WORD = /^[A-Za-zÀ-ÖØ-öø-ÿŒœ]+/;

function flat(text: unknown): string {
  return String(text ?? '').split(/\s+/).filter(Boolean).join(' ');
}

function stripLeading(value: string, marks: string): string {
  let at = 0;
  while (at < value.length && marks.includes(value[at])) at += 1;
  return value.slice(at);
}

function stripTrailing(value: string, marks: string): string {
  let end = value.length;
  while (end > 0 && marks.includes(value[end - 1])) end -= 1;
  return value.slice(0, end);
}

function quotationSpans(text: string): Array<[number, number]> {
  const spans: Array<[number, number]> = [];
  const stack: Array<[string, number]> = [];
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const top = stack[stack.length - 1];
    if (top && top[0].includes(char)) {
      spans.push([(stack.pop() as [string, number])[1], index]);
    } else if (char in QUOTE_PAIRS) {
      stack.push([QUOTE_PAIRS[char], index]);
    }
  }
  return spans;
}

/** The quotations their sentence carries on after («“ stimmt nicht», «”.», «» demande»). */
function carriedOn(text: string, spans: Array<[number, number]>): Array<[number, number]> {
  return spans.filter(([, end]) => {
    const rest = text.slice(end + 1).trimStart();
    return rest !== '' && !OPENS.test(rest);
  });
}

function endsHere(left: string): boolean {
  let stem = left;
  if (stem.endsWith(' »')) stem = stem.slice(0, -2);
  else if (stem && CLOSERS.includes(stem[stem.length - 1])) stem = stem.slice(0, -1);
  if (!stem || !STOPS.includes(stem[stem.length - 1])) return false;
  const word = stripLeading(stem.slice(stem.lastIndexOf(' ') + 1), LEADING_MARKS);
  return !TITLE_WORD.test(word);
}

/** Whether a sentence asks: it ends on «?», a closing mark may follow. */
export function asks(sentence: unknown): boolean {
  return stripTrailing(String(sentence ?? ''), `${CLOSERS}   `).endsWith('?');
}

function firstWord(sentence: string): string {
  const found = FIRST_WORD.exec(stripLeading(sentence, LEADING_MARKS));
  return found ? found[0].toLowerCase() : '';
}

function chained(pieces: string[]): string[] {
  const joined: string[] = [];
  pieces.forEach((piece) => {
    const last = joined[joined.length - 1];
    if (last !== undefined && asks(last) && asks(piece) && CHAIN_WORDS.has(firstWord(piece))) {
      joined[joined.length - 1] = `${last} ${piece}`;
    } else {
      joined.push(piece);
    }
  });
  return joined;
}

/** `text` as its sentences, the one way every surface reads them (#896). */
export function splitSentences(text: unknown): string[] {
  const line = flat(text);
  if (!line) return [];
  const inside = carriedOn(line, quotationSpans(line));
  const pieces: string[] = [];
  let start = 0;
  for (let index = 1; index < line.length - 1; index += 1) {
    if (line[index] !== ' ') continue;
    if (!OPENS.test(line[index + 1]) || !endsHere(line.slice(0, index))) continue;
    if (inside.some(([opened, closed]) => opened < index && index < closed)) continue;
    pieces.push(line.slice(start, index));
    start = index + 1;
  }
  pieces.push(line.slice(start));
  return chained(pieces.map((piece) => piece.trim()).filter(Boolean));
}

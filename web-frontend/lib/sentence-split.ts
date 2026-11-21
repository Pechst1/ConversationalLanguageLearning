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
 *     autres ? Ou tu dis au revoir à tout ça ?», #827): a run of questions is one only
 *     when it ends on a question that opens on «Ou» («Or», «Oder»); «Alors, quel jour ?
 *     Et on se retrouve où ?» stays two.
 */

const STOPS = '.!?…';
/** The one closing mark a stop may carry before the space. */
const CLOSERS = '"»”“’)]›';
/** Where a quotation opens, and what closes it («“» closes «„» and opens English quotes). */
const QUOTE_PAIRS: Record<string, string> = { '«': '»', '„': '“”', '“': '”', '‹': '›', '"': '"' };
/** What a new sentence opens on. */
const OPENS = /^[A-ZÀ-ÖØ-Þ0-9«"“„([—–]/;
/** The word only a later alternative opens on: it alone closes a chain. */
const ALTERNATIVES = ['ou', 'or', 'oder'];
export const ALTERNATIVE_WORDS = new Set(ALTERNATIVES);
/**
 * The words a question inside a chain may open on («Pour toi et les autres ?»): they link
 * it to the question before only on the way to an «Ou …?». On their own, «Et on se
 * retrouve où ?» is a question of its own.
 */
const LINKS = ['et', 'pour', 'ni', 'and', 'for', 'nor', 'und', 'für'];
export const LINK_WORDS = new Set(LINKS);
const CHAIN_WORDS = new Set(ALTERNATIVES.concat(LINKS));
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

/**
 * Each chain of alternatives as one sentence: a question that opens on «Ou» takes back the
 * questions before it while each one it reaches opens on a chain word, and the question
 * the chain starts from. Nothing joins without an «Ou …?» to close it.
 */
function chained(pieces: string[]): string[] {
  const joined: string[] = [];
  pieces.forEach((piece) => {
    let start = joined.length;
    if (asks(piece) && ALTERNATIVE_WORDS.has(firstWord(piece))) {
      let head = piece;
      while (start > 0 && asks(joined[start - 1]) && CHAIN_WORDS.has(firstWord(head))) {
        start -= 1;
        head = joined[start];
      }
    }
    joined.splice(start, joined.length - start, [...joined.slice(start), piece].join(' '));
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

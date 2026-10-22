/**
 * #236 / #146 — did the learner write this word?
 *
 * The Courrier's word ribbon marked «vendre» as used for «Je préfère vendredi»:
 * it asked `said.includes('vendre')`, a substring test, and «vendre» is the first
 * six letters of «vendredi». The backend had the same test in three places and
 * now has one (`app/services/word_match.py`); this is the browser's copy of that
 * rule, so the ribbon and the server agree.
 *
 * A target is used when the learner wrote that **word**: a whole token, in any
 * case or accent, or a regular inflection of it (the verb conjugated, the noun or
 * adjective in the plural or feminine). Never a longer word that merely starts
 * or ends the same way. Irregular verbs count by their own spelling here; the
 * server, which holds the conjugation table, is the judge of «je vais» for
 * «aller».
 */

const LEADING = new Set(['le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'l', 'se', 's', 'd', 'ne', 'n']);

/** A derived form is never shorter than this: «être» + «re» minus nothing is «et». */
const MIN_DERIVED = 3;

const VERB_ENDINGS: Record<string, string[]> = {
  er: [
    'er', 'e', 'es', 'ons', 'ez', 'ent', 'ais', 'ait', 'ions', 'iez', 'aient', 'ant',
    'erai', 'eras', 'era', 'erons', 'erez', 'eront', 'erais', 'erait', 'erions', 'eriez', 'eraient',
    'ee', 'ees', 'ai', 'as', 'a', 'asse', 'assent',
  ],
  ir: [
    'ir', 'is', 'it', 'issons', 'issez', 'issent', 'issais', 'issait', 'issions', 'issiez',
    'issaient', 'issant', 'i', 'ie', 'ies', 'irai', 'iras', 'ira', 'irons', 'irez', 'iront',
    'irais', 'irait', 'irions', 'iriez', 'iraient', 'isse', 'isses',
  ],
  re: [
    're', '', 's', 't', 'ons', 'ez', 'ent', 'ais', 'ait', 'ions', 'iez', 'aient', 'ant',
    'rai', 'ras', 'ra', 'rons', 'rez', 'ront', 'rais', 'rait', 'rions', 'riez', 'raient',
    'u', 'ue', 'us', 'ues', 'e', 'es',
  ],
};

/** Lower case, no accents, one kind of apostrophe. */
export function fold(text: unknown): string {
  return String(text ?? '')
    .replace(/[‘’‛′´`]/g, "'")
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '');
}

/** The words of `text`, folded: `l'eau` is `l` and `eau`. */
export function tokens(text: unknown): string[] {
  return fold(text).match(/[a-z0-9]+/g) ?? [];
}

function forms(word: string): Set<string> {
  const found = new Set([word, `${word}s`, `${word}x`, `${word}e`, `${word}es`]);
  if (word.endsWith('al') && word.length > 3) found.add(`${word.slice(0, -2)}aux`);
  const endings = word.length > 3 ? VERB_ENDINGS[word.slice(-2)] : undefined;
  if (endings) {
    const stem = word.slice(0, -2);
    endings.forEach((ending) => {
      const form = `${stem}${ending}`;
      if (form.length >= MIN_DERIVED) found.add(form);
    });
  }
  return found;
}

function wanted(label: unknown): string[] {
  const words = tokens(label);
  while (words.length > 1 && LEADING.has(words[0])) words.shift();
  return words;
}

/** Whether `text` contains the target `label` as a word (first word may be inflected). */
export function targetOccursIn(label: unknown, text: unknown): boolean {
  const target = wanted(label);
  const seen = tokens(text);
  if (!target.length || !seen.length) return false;
  const head = target.length > 1 || !LEADING.has(target[0]) ? forms(target[0]) : new Set(target);
  const rest = target.slice(1);
  return seen.some(
    (word, start) => head.has(word) && rest.every((expected, offset) => seen[start + 1 + offset] === expected),
  );
}

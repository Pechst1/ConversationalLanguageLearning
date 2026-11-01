/**
 * A French noun is shown with its article — the one rule every surface uses.
 *
 * Owner request, 1 Nov: wherever a French noun is a card's word (front or back,
 * recognition or production) it carries its article: «la serrure», «le grenier»,
 * «l’horloge (f.)». Before an elided «l’» the gender is said, because the article
 * no longer does. The gender comes from the server (`gender`: the stored value,
 * else the core lexicon, `app/services/lexicon_grammar.py`); nothing is guessed. A
 * noun the catalogue has no gender for — and an epicene one («l’artiste»,
 * «dentiste»), which has no one article — is shown as it is.
 *
 * A noun used in the plural only («les gens», «les vacances») takes «les»: the server
 * says so (`number: "pl"`, from `app/data/lexical/fr_pluralia_tantum.json`, read by
 * `app/services/lexicon_grammar.py`). A final -s or -x says nothing (le bras, le prix,
 * le temps), so nothing here reads one.
 *
 * `articleFor` (the token's la / le / l’ / les, `lib/word-token.ts`) is this module's rule.
 */

export type NounGender = 'f' | 'm';

const FEMININE = new Set(['f', 'fem', 'fém', 'feminine', 'féminin', 'féminine', 'feminin', 'nf', 'n.f.']);
const MASCULINE = new Set(['m', 'masc', 'masculine', 'masculin', 'nm', 'n.m.']);

/** The stored gender as 'f' / 'm', or null. «m/f» and anything unknown stay null. */
export function normalizeGender(value?: string | null): NounGender | null {
  const key = String(value || '').trim().toLowerCase();
  if (FEMININE.has(key)) return 'f';
  if (MASCULINE.has(key)) return 'm';
  return null;
}

/* Words whose h blocks elision (h aspiré). The default for h is elision
   (l’homme, l’heure, l’hôtel), so only the common aspirated ones are listed. */
const H_ASPIRE = new Set([
  'hache', 'haie', 'haine', 'hall', 'halte', 'hamac', 'hameau', 'hamster', 'hanche', 'handicap',
  'hangar', 'hareng', 'haricot', 'harpe', 'hasard', 'hâte', 'hausse', 'haut', 'hauteur', 'héros',
  'hibou', 'hockey', 'homard', 'honte', 'hors-d’œuvre', 'hotte', 'housse', 'huit', 'hurlement', 'hutte',
]);

function foldAccents(value: string): string {
  return value.normalize('NFD').replace(/[̀-ͯ]/g, '');
}

/** The article a noun is written with, when the entry already carries one. */
const WRITTEN_ARTICLE = /^(l[’']|la\s|le\s|les\s|un\s|une\s)/i;

/** Does the noun's first sound take an elided «l’» (a vowel, œ, or a mute h)? */
function elides(text: string): boolean {
  const first = foldAccents(text).charAt(0);
  if (!first) return false;
  // «y» is a consonant before a vowel: le yaourt, le yoga.
  if ('aeiouœæ'.includes(first)) return true;
  return first === 'h' && !H_ASPIRE.has(text.split(/\s/)[0]);
}

/** The server's number for a noun: 'pl' for one used in the plural only. */
export function isPluralOnly(number?: string | null): boolean {
  return String(number || '').trim().toLowerCase() === 'pl';
}

/** la / le / l’ for a gendered noun, les for one used in the plural only. A written article wins. */
export function articleFor(word: string, gender: NounGender | null, number?: string | null): string {
  const text = String(word || '').trim().toLowerCase().replace(/'/g, '’');
  if (/^les\s/.test(text) || isPluralOnly(number)) return 'les';
  if (/^l’/.test(text)) return 'l’';
  if (/^la\s/.test(text)) return 'la';
  if (/^le\s/.test(text)) return 'le';
  if (elides(text)) return 'l’';
  return gender === 'f' ? 'la' : 'le';
}

const NOUN_TAGS = new Set(['noun', 'nom', 'n']);

/** «(f.)» / «(m.)»: what an elided «l’» no longer says. */
export function genderNote(gender: NounGender): string {
  return gender === 'f' ? '(f.)' : '(m.)';
}

/**
 * The French word as a card shows it: a noun with a known gender carries its
 * article (and, after «l’», its gender), a noun used in the plural only «les»;
 * anything else is shown as it is.
 */
export function frenchHeadword({
  word,
  gender,
  partOfSpeech,
  number,
}: {
  word?: string | null;
  gender?: string | null;
  partOfSpeech?: string | null;
  number?: string | null;
}): string {
  const text = String(word || '').trim();
  const known = normalizeGender(gender);
  const pos = String(partOfSpeech || '').trim().toLowerCase();
  // The server only gives a gender or a number to a noun; a stored part of speech
  // that says otherwise («verb» on an imported row) wins.
  if (!text || (pos && !NOUN_TAGS.has(pos))) return text;
  if (isPluralOnly(number)) return WRITTEN_ARTICLE.test(text) ? text : `les ${text}`;
  if (!known) return text;
  const written = WRITTEN_ARTICLE.exec(text);
  if (written) {
    return /^l[’']/i.test(written[1]) ? `${text.replace(/^l'/i, 'l’')} ${genderNote(known)}` : text;
  }
  const article = articleFor(text, known);
  return article === 'l’' ? `l’${text} ${genderNote(known)}` : `${article} ${text}`;
}

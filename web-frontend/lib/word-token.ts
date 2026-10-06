/**
 * WP-D6 — the gender is the shape. The pure half of `WordToken`.
 *
 * A French noun's gender is drawn as a shape: a feminine noun is a circle, a
 * masculine noun a square (8 px radius), and any other part of speech a
 * triangle. The article (la / le / l’) sits inside in Garamond italic, and the
 * token's accessible name says «féminin», «masculin», «verbe»…
 *
 * Colour keeps its role and never carries gender: yellow = new, blue =
 * learning, ink = known. So gender is readable by shape alone (colour-blind
 * safe), and a triangle here is never the red action triangle.
 *
 * Nothing is guessed. Gender comes only from the stored catalogue value (the
 * WP-84 backfill); a word without one is a plain ink token with no article and
 * no gender in its name. The part-of-speech column is only trusted through the
 * same whitelist the Lexique prints.
 */

export type WordGender = 'f' | 'm';
export type WordTokenShape = 'feminine' | 'masculine' | 'other' | 'plain';
export type WordTokenTone = 'new' | 'learning' | 'known';

export type WordTokenModel = {
  shape: WordTokenShape;
  tone: WordTokenTone;
  /** «la», «le», «l’» for a gendered noun; '' otherwise. */
  article: string;
  /** Accessible name: «féminin», «masculin», «verbe»… ; '' when nothing is known. */
  label: string;
  /** What a plain token shows: the word's initial, in ink. */
  initial: string;
};

const FEMININE = new Set(['f', 'fem', 'fém', 'feminine', 'féminin', 'féminine', 'feminin', 'nf', 'n.f.']);
const MASCULINE = new Set(['m', 'masc', 'masculine', 'masculin', 'nm', 'n.m.']);

/** The stored gender as 'f' / 'm', or null. «m/f» and anything unknown stay null. */
export function normalizeGender(value?: string | null): WordGender | null {
  const key = String(value || '').trim().toLowerCase();
  if (FEMININE.has(key)) return 'f';
  if (MASCULINE.has(key)) return 'm';
  return null;
}

/* Same whitelist as the Lexique's meta line: the imported deck's column is an
   English machine key, and junk values print nothing. */
export const PART_OF_SPEECH_LABELS: Record<string, string> = {
  noun: 'nom',
  verb: 'verbe',
  adjective: 'adjectif',
  adverb: 'adverbe',
  pronoun: 'pronom',
  preposition: 'préposition',
  determiner: 'déterminant',
  conjunction: 'conjonction',
  interjection: 'interjection',
  number: 'numéral',
};

export function normalizePartOfSpeech(value?: string | null): string {
  const key = String(value || '').trim().toLowerCase();
  return key in PART_OF_SPEECH_LABELS ? key : '';
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

/** la / le / l’ for a gendered noun. A written article on the entry wins. */
export function articleFor(word: string, gender: WordGender): string {
  const text = String(word || '').trim().toLowerCase().replace(/'/g, '’');
  if (/^l’/.test(text)) return 'l’';
  if (/^la\s/.test(text)) return 'la';
  if (/^le\s/.test(text)) return 'le';
  const first = foldAccents(text).charAt(0);
  if ('aeiouy'.includes(first) && first) return 'l’';
  if (first === 'h' && !H_ASPIRE.has(text.split(/\s/)[0])) return 'l’';
  return gender === 'f' ? 'la' : 'le';
}

/** Map any learner-state vocabulary onto the three colour roles. */
export function wordTokenTone(state?: string | null): WordTokenTone {
  const key = String(state || '').trim().toLowerCase();
  if (!key || key === 'new') return 'new';
  if (key === 'mastered' || key === 'holding' || key === 'known') return 'known';
  return 'learning';
}

export function wordTokenModel({
  word,
  gender,
  partOfSpeech,
  state,
}: {
  word: string;
  gender?: string | null;
  partOfSpeech?: string | null;
  state?: string | null;
}): WordTokenModel {
  const tone = wordTokenTone(state);
  const initial = String(word || '').trim().replace(/^(l['’]|la\s+|le\s+)/i, '').charAt(0).toUpperCase() || '·';
  const known = normalizeGender(gender);
  if (known) {
    return {
      shape: known === 'f' ? 'feminine' : 'masculine',
      tone,
      article: articleFor(word, known),
      label: known === 'f' ? 'féminin' : 'masculin',
      initial,
    };
  }
  const pos = normalizePartOfSpeech(partOfSpeech);
  if (pos && pos !== 'noun') {
    return { shape: 'other', tone, article: '', label: PART_OF_SPEECH_LABELS[pos], initial };
  }
  // A noun without a stored gender, or nothing known at all: no shape, no
  // article, nothing guessed.
  return { shape: 'plain', tone, article: '', label: pos === 'noun' ? 'nom, genre non renseigné' : '', initial };
}

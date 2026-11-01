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

import { articleFor, normalizeGender, type NounGender } from './french-noun';

export type WordGender = NounGender;
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

// The gender and the article are `lib/french-noun.ts`'s, the one rule every surface uses.
export { normalizeGender, articleFor };

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
  number,
  state,
}: {
  word: string;
  gender?: string | null;
  partOfSpeech?: string | null;
  /** The server's number: 'pl' for a noun used in the plural only («les gens»). */
  number?: string | null;
  state?: string | null;
}): WordTokenModel {
  const tone = wordTokenTone(state);
  const initial = String(word || '').trim().replace(/^(l['’]|la\s+|les\s+|le\s+)/i, '').charAt(0).toUpperCase() || '·';
  const known = normalizeGender(gender);
  if (known) {
    return {
      shape: known === 'f' ? 'feminine' : 'masculine',
      tone,
      article: articleFor(word, known, number),
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

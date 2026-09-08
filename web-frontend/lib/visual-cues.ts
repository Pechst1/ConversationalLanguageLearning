/**
 * The review card's visual-cue badge — one scene name per word, in three languages.
 *
 * The badge is a memory hook, not a dictionary entry: it names the scene a word
 * belongs to ("Table · repas") next to one of the design's four Bauhaus shapes.
 * It replaced the old English "WORD / MEMORY CUE" pair, but only by moving to
 * French, which left a German or English beginner reading two French words on
 * the one card that exists to teach them French vocabulary.
 *
 * A scene name explains the word, so under the design contract it follows the
 * learner's `native_language` (WP-21). The shape and the matching signals are
 * language-independent and stay here with the labels, so a cue is one row.
 *
 * The signals are folded, accent-free tokens; they deliberately include German
 * and English surface forms, because the card's own gloss may be in either.
 */

import type { ControlLanguage } from '@/types/daily-journey';

import { normalizeControlLanguage } from './atelier-v2-copy';

export type VisualCueShape = 'story' | 'action' | 'reward' | 'done';

export type VisualCue = {
  /** Stable id — what a test pins, and what analytics would group on. */
  id: string;
  label: string;
  caption: string;
  shape: VisualCueShape;
};

type CueDefinition = {
  id: string;
  shape: VisualCueShape;
  signals: string[];
  text: Record<ControlLanguage, { label: string; caption: string }>;
};

/** Order matters: the first definition whose signal is present wins. */
export const VISUAL_CUE_DEFINITIONS: CueDefinition[] = [
  {
    id: 'decrease',
    shape: 'story',
    signals: ['abaisser', 'baisse', 'reduire', 'reduction', 'senken', 'lower', 'down'],
    text: {
      fr: { label: 'Baisse', caption: 'mouvement' },
      en: { label: 'Decrease', caption: 'movement' },
      de: { label: 'Senken', caption: 'Bewegung' },
    },
  },
  {
    id: 'people',
    shape: 'action',
    signals: ['famille', 'ami', 'soeur', 'frere', 'mere', 'pere', 'person', 'schwester', 'freund'],
    text: {
      fr: { label: 'Gens', caption: 'relation' },
      en: { label: 'People', caption: 'relationship' },
      de: { label: 'Menschen', caption: 'Beziehung' },
    },
  },
  {
    id: 'table',
    shape: 'reward',
    signals: ['cafe', 'vin', 'restaurant', 'manger', 'boire', 'pain', 'food', 'essen', 'trinken'],
    text: {
      fr: { label: 'Table', caption: 'repas' },
      en: { label: 'Table', caption: 'meals' },
      de: { label: 'Tisch', caption: 'Essen' },
    },
  },
  {
    id: 'time',
    shape: 'story',
    signals: ['heure', 'jour', 'semaine', 'temps', 'week', 'time', 'morgen', 'gestern'],
    text: {
      fr: { label: 'Temps', caption: 'quand' },
      en: { label: 'Time', caption: 'when' },
      de: { label: 'Zeit', caption: 'wann' },
    },
  },
  {
    id: 'journey',
    shape: 'done',
    signals: ['train', 'gare', 'metro', 'bus', 'voiture', 'voyage', 'reise', 'transport'],
    text: {
      fr: { label: 'Trajet', caption: 'mouvement' },
      en: { label: 'Journey', caption: 'movement' },
      de: { label: 'Fahrt', caption: 'Bewegung' },
    },
  },
  {
    id: 'home',
    shape: 'reward',
    signals: ['maison', 'appartement', 'porte', 'fenetre', 'home', 'haus', 'wohnung'],
    text: {
      fr: { label: 'Maison', caption: 'lieu' },
      en: { label: 'Home', caption: 'place' },
      de: { label: 'Zuhause', caption: 'Ort' },
    },
  },
  {
    id: 'city',
    shape: 'story',
    signals: ['ville', 'rue', 'hotel', 'bureau', 'place', 'street', 'stadt', 'office'],
    text: {
      fr: { label: 'Ville', caption: 'où' },
      en: { label: 'City', caption: 'where' },
      de: { label: 'Stadt', caption: 'wo' },
    },
  },
  {
    id: 'work',
    shape: 'done',
    signals: ['travail', 'argent', 'prix', 'client', 'job', 'work', 'geld'],
    text: {
      fr: { label: 'Travail', caption: 'pratique' },
      en: { label: 'Work', caption: 'practical' },
      de: { label: 'Arbeit', caption: 'praktisch' },
    },
  },
  {
    id: 'body',
    shape: 'action',
    signals: ['sante', 'douleur', 'malade', 'corps', 'health', 'arzt', 'krank'],
    text: {
      fr: { label: 'Corps', caption: 'santé' },
      en: { label: 'Body', caption: 'health' },
      de: { label: 'Körper', caption: 'Gesundheit' },
    },
  },
  {
    id: 'study',
    shape: 'story',
    signals: ['ecole', 'cours', 'livre', 'apprendre', 'question', 'learn', 'schule'],
    text: {
      fr: { label: 'Étude', caption: 'savoir' },
      en: { label: 'Study', caption: 'knowledge' },
      de: { label: 'Lernen', caption: 'Wissen' },
    },
  },
  {
    id: 'speech',
    shape: 'done',
    signals: ['dire', 'parler', 'demander', 'message', 'lettre', 'sagen', 'sprechen'],
    text: {
      fr: { label: 'Parole', caption: 'message' },
      en: { label: 'Speech', caption: 'message' },
      de: { label: 'Sprechen', caption: 'Nachricht' },
    },
  },
  {
    id: 'civics',
    shape: 'action',
    signals: ['loi', 'etat', 'gouvernement', 'politique', 'law', 'recht'],
    text: {
      fr: { label: 'Cité', caption: 'institutions' },
      en: { label: 'Civics', caption: 'institutions' },
      de: { label: 'Staat', caption: 'Institutionen' },
    },
  },
  {
    id: 'culture',
    shape: 'reward',
    signals: ['film', 'musique', 'jeu', 'art', 'danser', 'music'],
    text: {
      fr: { label: 'Culture', caption: 'loisir' },
      en: { label: 'Culture', caption: 'leisure' },
      de: { label: 'Kultur', caption: 'Freizeit' },
    },
  },
  {
    id: 'clothes',
    shape: 'done',
    signals: ['robe', 'chemise', 'pantalon', 'chaussure', 'kleid', 'schuh'],
    text: {
      fr: { label: 'Habits', caption: 'objet' },
      en: { label: 'Clothes', caption: 'object' },
      de: { label: 'Kleidung', caption: 'Gegenstand' },
    },
  },
];

/** The badge shown when no signal matched: still a hook, never a blank chip. */
export const DEFAULT_VISUAL_CUE: CueDefinition = {
  id: 'word',
  shape: 'done',
  signals: [],
  text: {
    fr: { label: 'Mot', caption: 'à retenir' },
    en: { label: 'Word', caption: 'to remember' },
    de: { label: 'Wort', caption: 'zu merken' },
  },
};

function render(definition: CueDefinition, language: unknown): VisualCue {
  const text = definition.text[normalizeControlLanguage(language)];
  return { id: definition.id, label: text.label, caption: text.caption, shape: definition.shape };
}

/**
 * Pick the cue for a folded signal string.
 *
 * `signal` is the caller's already-folded haystack (word, gloss, topic tags);
 * `hasSignal` is the caller's token matcher, so the matching rule stays exactly
 * the one the review deck used before this table existed.
 */
export function visualCueFor(
  signal: string,
  hasSignal: (haystack: string, words: string[]) => boolean,
  language: unknown,
): VisualCue {
  for (const definition of VISUAL_CUE_DEFINITIONS) {
    if (hasSignal(signal, definition.signals)) return render(definition, language);
  }
  return render(DEFAULT_VISUAL_CUE, language);
}

export default visualCueFor;

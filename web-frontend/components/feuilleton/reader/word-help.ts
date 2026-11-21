/* Word help — where a tapped word's meaning comes from (WordHelpSheet).

   Pure, so the order is pinned by node tests (word-help.test.js):

     1. the meaning the surface already knows (`knownGloss`: Le Papier's target
        words carry their gloss) — shown at once, no request;
     2. the catalogue entry (`/vocabulary/lookup`);
     3. the word read in its sentence (`/atelier/gloss`, 2026-10-19): its meaning
        here and its dictionary form, the sentence's translation underneath — a
        news word or an inflected form («grévistes», «reviennent») misses the
        catalogue, and translating the whole line answered the wrong question.
        R2 (6): when that dictionary form IS a catalogue entry, the answer is the
        entry's (kind 'gloss', with the lemma as the term to keep), so «Garder»
        is offered for every word whose dictionary form has a meaning;
     4. the line's translation (the payload's own, else `/atelier/translate`);
     5. nothing: the sheet says so instead of inventing a gloss. */

import { learnerGloss, type GlossCarrier } from '@/lib/glosses';

export type WordHelpGloss =
  | { kind: 'loading' }
  /** A dictionary meaning: the catalogue's, or one the surface already knew. «Garder» may keep it.
   *  `term`/`lemma`: set when the entry was found through the word's dictionary form
   *  (the printed form missed the catalogue) — `term` is what «Garder» sends. */
  | { kind: 'gloss'; text: string; language: string | null; term?: string; lemma?: string | null }
  /** The word's meaning in this sentence, with its dictionary form when that differs. Not a catalogue row: nothing to keep. */
  | { kind: 'context'; text: string; lemma: string | null; language: string | null }
  | { kind: 'sentence'; text: string }
  | { kind: 'none' };

export type WordHelpSource = {
  term: string;
  surface?: string;
  sentence?: string;
  /** The line's translation, when the payload already carried one. */
  sentenceEn?: string;
  knownGloss?: string | null;
  knownGlossLanguage?: string | null;
};

export type ContextGloss = { lemma: string; gloss: string; language: string; translation: string };

export type WordHelpApi = {
  lookupVocabulary: (term: string) => Promise<unknown>;
  glossInContext?: (word: string, sentence: string) => Promise<ContextGloss>;
  translateForLearner: (text: string) => Promise<string>;
};

export type WordHelpAnswer = { gloss: Exclude<WordHelpGloss, { kind: 'loading' }>; sentenceEn: string };

function fold(text: string): string {
  return text.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim();
}

/** The dictionary form, when it says something the printed word does not. */
export function shownLemma(lemma: string | null | undefined, surface: string): string | null {
  const clean = (lemma || '').trim();
  return clean && fold(clean) !== fold(surface) ? clean : null;
}

/** The catalogue's meaning for `term`, or null (a 404 is the ordinary miss). */
async function catalogueGloss(api: WordHelpApi, term: string): Promise<{ text: string; language: string | null } | null> {
  try {
    const entry = (await api.lookupVocabulary(term)) as Record<string, unknown> | null;
    const text = learnerGloss(entry as GlossCarrier | null, '');
    if (!text) return null;
    return { text, language: typeof entry?.translation_language === 'string' ? entry.translation_language : null };
  } catch {
    return null;
  }
}

export async function resolveWordHelp(source: WordHelpSource, api: WordHelpApi): Promise<WordHelpAnswer> {
  const sentence = (source.sentence || '').trim();
  const supplied = (source.sentenceEn || '').trim();
  const known = (source.knownGloss || '').trim();
  if (known) return { gloss: { kind: 'gloss', text: known, language: source.knownGlossLanguage ?? null }, sentenceEn: supplied };

  const entry = await catalogueGloss(api, source.term);
  if (entry) return { gloss: { kind: 'gloss', ...entry }, sentenceEn: supplied };

  let translated = '';
  if (sentence && api.glossInContext) {
    try {
      const word = (source.surface || source.term).trim();
      const context = await api.glossInContext(word, sentence);
      translated = (context?.translation || '').trim();
      const text = (context?.gloss || '').trim();
      const lemma = shownLemma(context.lemma, word);
      // The printed form missed the catalogue; its dictionary form may not (R2 (6)).
      const byLemma = text && lemma ? await catalogueGloss(api, lemma) : null;
      if (byLemma) {
        return { gloss: { kind: 'gloss', ...byLemma, term: lemma as string, lemma }, sentenceEn: supplied || translated };
      }
      if (text) {
        return {
          gloss: { kind: 'context', text, lemma, language: context.language || null },
          sentenceEn: supplied || translated,
        };
      }
    } catch {
      /* The word could not be read in its sentence: the line instead, as before. */
    }
  }

  // No meaning for the word alone: translate the line instead of guessing the word.
  if (supplied) return { gloss: { kind: 'sentence', text: supplied }, sentenceEn: supplied };
  if (translated) return { gloss: { kind: 'sentence', text: translated }, sentenceEn: translated };
  if (!sentence) return { gloss: { kind: 'none' }, sentenceEn: '' };
  try {
    const text = ((await api.translateForLearner(sentence)) || '').trim();
    return text ? { gloss: { kind: 'sentence', text }, sentenceEn: text } : { gloss: { kind: 'none' }, sentenceEn: '' };
  } catch {
    return { gloss: { kind: 'none' }, sentenceEn: '' };
  }
}

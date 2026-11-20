/**
 * «Papier · les rendez-vous» · the pure part of the client: the pairing of «Trois mots», what a
 * miss says, the line a regular says in the learner's language, the une's count.
 */

import type { RvLanguage } from '@/lib/revue-types';
import { TM_WORD_KEYS, type RvSouvenir, type RvTmCueKey, type RvTmWordKey, type RvTroisMots } from '@/lib/revue-rdv';

import { fillRdv, type RdvCopy } from './rdv-copy';

export type Pairs = Partial<Record<RvTmWordKey, RvTmCueKey>>;

/** The word a tapped cue goes to: the first word without a cue. */
export function activeWord(pairs: Pairs): RvTmWordKey | null {
  return TM_WORD_KEYS.find((key) => !pairs[key]) ?? null;
}

/** Tap a cue: it goes to `word` (default: the first unmatched one), leaving any word that had it. */
export function pairCue(pairs: Pairs, cue: RvTmCueKey, word: RvTmWordKey | null = activeWord(pairs)): Pairs {
  if (!word) return pairs;
  const next: Pairs = {};
  for (const key of TM_WORD_KEYS) if (pairs[key] && pairs[key] !== cue) next[key] = pairs[key];
  next[word] = cue;
  return next;
}

/** Tap a matched word: it lets its cue go. */
export function unpair(pairs: Pairs, word: RvTmWordKey): Pairs {
  const next: Pairs = { ...pairs };
  delete next[word];
  return next;
}

export function complete(pairs: Pairs): pairs is Record<RvTmWordKey, RvTmCueKey> {
  return TM_WORD_KEYS.every((key) => Boolean(pairs[key])) && new Set(TM_WORD_KEYS.map((k) => pairs[k])).size === 3;
}

/** The pairs the learner sees: before the first check, theirs; after a miss, the last tried; once
 * resolved, the solution. */
export function shownPairs(round: RvTroisMots, local: Pairs): Pairs {
  if (round.match.resolved && round.match.solution) return round.match.solution;
  return local;
}

/** What each wrong pair of the last try says, in the mother tongue (never the right cue). */
export function missLines(round: RvTroisMots, xcopy: RdvCopy): string[] {
  if (round.match.resolved && round.match.correct) return [];
  return round.match.misses.map((miss) => {
    const word = round.words.find((w) => w.key === miss.wordKey);
    const cue = round.cues.find((c) => c.key === miss.cueKey);
    if (!word || !cue) return '';
    return cue.kind === 'picture'
      ? fillRdv(xcopy.tm_miss_picture, { word: word.bareFr })
      : fillRdv(xcopy.tm_miss_gloss, { word: word.bareFr, cue: cue.text ?? '' });
  }).filter(Boolean);
}

export function gapMissLine(round: RvTroisMots, xcopy: RdvCopy): string | null {
  const miss = round.gap?.miss;
  if (!miss || round.gap?.correct) return null;
  const word = round.words.find((w) => w.key === miss.wordKey);
  return word ? fillRdv(xcopy.tm_gap_miss, { word: word.bareFr, gloss: miss.gloss }) : null;
}

/** A regular's line in the learner's language: null for French (the line is French). */
export function souvenirTranslation(line: RvSouvenir, language: RvLanguage): string | null {
  if (language === 'en') return line.en || null;
  if (language === 'de') return line.de || null;
  return null;
}

export function uneCount(copy: RdvCopy, filed: number, total: number): string {
  return fillRdv(copy.une_count, { n: filed, total });
}

/**
 * WP-77 — who is speaking, and which of their three faces they are making.
 *
 * Two pure maps, shared by every surface that shows a character line:
 *
 *   * `castIdFor` — anything the payloads call a character («Marin»,
 *     «marin_leveque», «Augustin « Gus » de Roncourt», «Monsieur Marchand»,
 *     `landlord_marchand`) → the portrait directory id, or `null` for anyone
 *     who is not in the drawn cast. It is deliberately strict: the reader's
 *     accent colour hashes unknown speakers onto the cast palette, but a face
 *     is a claim about *who* is talking, so an unknown speaker gets an initial,
 *     never someone else's face.
 *   * `expressionForMood` / `expressionForVerdict` — the living story's mood
 *     (−2 … +2, or the engine's words) and a graded answer → neutral, happy or
 *     cross.
 */

import { CAST_WITH_PORTRAITS, portraitSrc, type PortraitMood } from './onboarding-portraits';

export type CastId = (typeof CAST_WITH_PORTRAITS)[number];

/** Tokens that name one cast member, after accent folding and lowercasing. */
const NAME_TOKENS: Array<[CastId, string[]]> = [
  ['romy_tremblay', ['romy', 'romane', 'tremblay']],
  ['marin_leveque', ['marin', 'leveque']],
  ['lila_bonnet', ['lila', 'bonnet']],
  ['augustin_de_roncourt', ['gus', 'augustin', 'roncourt']],
  ['margaux_barman', ['margaux']],
  ['landlord_marchand', ['marchand', 'landlord', 'proprietaire']],
];

const IDS = new Set<string>(CAST_WITH_PORTRAITS);

function fold(value: unknown): string {
  return String(value ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();
}

/**
 * The portrait id for the first seed that names a cast member, else `null`.
 * Pass the id first and the display name second: an id is the stronger claim.
 */
export function castIdFor(...seeds: unknown[]): CastId | null {
  for (const seed of seeds) {
    const raw = fold(seed).trim();
    if (!raw) continue;
    const asId = raw.replace(/[\s-]+/g, '_');
    if (IDS.has(asId)) return asId as CastId;
    const tokens = new Set(raw.split(/[^a-z0-9]+/).filter(Boolean));
    for (const [id, names] of NAME_TOKENS) {
      if (names.some((name) => tokens.has(name))) return id;
    }
  }
  return null;
}

const HAPPY_WORDS = new Set(['happy', 'warmer', 'warm', 'glowing', 'delighted', 'pleased', 'positive']);
const CROSS_WORDS = new Set(['cross', 'colder', 'cold', 'hurt', 'annoyed', 'angry', 'upset', 'negative']);

/**
 * A mood → one of the three drawn expressions. Numbers are the living story's
 * scale (−2 hurt … +2 glowing); the middle of it is a neutral face, because a
 * one-step drift is not something a face should shout.
 */
export function expressionForMood(mood: unknown): PortraitMood {
  if (typeof mood === 'number' && Number.isFinite(mood)) {
    if (mood >= 1) return 'happy';
    if (mood <= -1) return 'cross';
    return 'neutral';
  }
  const word = fold(mood).trim();
  if (!word) return 'neutral';
  const numeric = Number(word);
  if (word && Number.isFinite(numeric)) return expressionForMood(numeric);
  if (HAPPY_WORDS.has(word)) return 'happy';
  if (CROSS_WORDS.has(word)) return 'cross';
  return 'neutral';
}

/** The character reacts to *your* answer: pleased when it lands, cross when it misses. */
export function expressionForVerdict(verdict: string | null | undefined): PortraitMood {
  if (verdict === 'correct' || verdict === 'supported') return 'happy';
  if (verdict === 'wrong') return 'cross';
  return 'neutral';
}

/** The face for a speaker, or `null` when they have none drawn. */
export function faceSrcFor(seeds: unknown[], mood: PortraitMood = 'neutral'): string | null {
  const id = castIdFor(...seeds);
  return id ? portraitSrc(id, mood) : null;
}

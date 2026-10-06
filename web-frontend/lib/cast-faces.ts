/**
 * WP-77 — who is speaking, and which of their faces they are making.
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

import { CAST_WITH_PORTRAITS, portraitSrc, type FaceMood, type PortraitMood } from './onboarding-portraits';

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

/**
 * WP-111: season-1 people who have no portrait yet. «Camille Marchand» shares a
 * surname with the landlord and must never borrow his face; they get an initial.
 */
const NO_PORTRAIT_TOKENS = new Set(['camille', 'odile', 'bastien', 'diallo', 'vasseur']);

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
    if (Array.from(tokens).some((token) => NO_PORTRAIT_TOKENS.has(token))) return null;
    for (const [id, names] of NAME_TOKENS) {
      if (names.some((name) => tokens.has(name))) return id;
    }
  }
  return null;
}

const HAPPY_WORDS = new Set(['happy', 'warmer', 'warm', 'glowing', 'delighted', 'pleased', 'positive']);
const CROSS_WORDS = new Set(['cross', 'colder', 'cold', 'hurt', 'annoyed', 'angry', 'upset', 'negative']);
/** WP-D8/D2: the fourth face — touched, not merely pleased. Only when the story says so. */
const MOVED_WORDS = new Set(['moved', 'touched', 'tender', 'emu', 'emue', 'touche', 'touchee']);

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
  if (MOVED_WORDS.has(word)) return 'moved';
  return 'neutral';
}

/**
 * WP-137 C-4 · the drawn stage's faces: the four portrait moods, and `cold`.
 * The painted set has no cold portrait (it keeps `expressionForMood`); a drawn
 * figure holds its neutral face on a level mouth, so a dry «Non.» or a frosty
 * welcome is never played with a smile.
 */
export type StageMood = PortraitMood | 'cold';

const COLD_WORDS = new Set([
  'cold', 'cool', 'frosty', 'icy', 'dry', 'deadpan', 'curt', 'flat', 'wary',
  'froid', 'froide', 'sec', 'seche', 'distant', 'distante', 'mefiant', 'mefiante',
]);

/** A line's mood word → the stage face (`cold` for the cold words, else the portrait's). */
export function stageMoodFor(mood: unknown): StageMood {
  if (typeof mood !== 'number' && COLD_WORDS.has(fold(mood).trim())) return 'cold';
  return expressionForMood(mood);
}

/** Does a beat with these moods hold no smile at all (a cold or a cross line in it)? */
export function isColdBeat(moods: Array<StageMood | null | undefined>): boolean {
  return moods.some((mood) => mood === 'cold' || mood === 'cross');
}

/**
 * The character reacts to *your* answer: pleased when it lands, surprised when it
 * misses (WP-116 phase 4: never cross at the learner; the painted set, which has
 * no surprised portrait, still shows its cross one).
 */
export function expressionForVerdict(verdict: string | null | undefined): FaceMood {
  if (verdict === 'correct' || verdict === 'supported') return 'happy';
  if (verdict === 'wrong') return 'surprised';
  return 'neutral';
}

/**
 * WP-D2: the onboarding taste's name for the same reaction, kept so the
 * onboarding and the journey read one map. A pending answer is a neutral face.
 */
export function moodForVerdict(verdict: string | null | undefined): FaceMood {
  return expressionForVerdict(verdict);
}

/** The face for a speaker, or `null` when they have none drawn. */
export function faceSrcFor(seeds: unknown[], mood: FaceMood = 'neutral'): string | null {
  const id = castIdFor(...seeds);
  return id ? portraitSrc(id, mood) : null;
}

/**
 * WP-116: the drawn cast reaches further than the painted portraits did. Camille
 * and Odile have rigs; the learner never has a face. Returns the rig id, or `null`
 * for anyone outside the drawn cast (minor characters keep their initial).
 */
const DRAWN_ONLY: Array<[string, string[]]> = [
  ['camille_marchand', ['camille']],
  ['odile_ferrand', ['odile']],
];

export function drawnCastIdFor(...seeds: unknown[]): string | null {
  for (const seed of seeds) {
    const raw = fold(seed).trim();
    if (!raw) continue;
    const asId = raw.replace(/[\s-]+/g, '_');
    if (asId === 'camille_marchand' || asId === 'odile_ferrand') return asId;
    const tokens = new Set(raw.split(/[^a-z0-9]+/).filter(Boolean));
    for (const [id, names] of DRAWN_ONLY) {
      if (names.some((name) => tokens.has(name))) return id;
    }
    const painted = castIdFor(seed);
    if (painted) return painted;
  }
  return null;
}

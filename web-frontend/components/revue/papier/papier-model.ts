/**
 * «Papier · la belle édition» (2026-11-21) · the paper objects' pure parts, node-tested
 * (papier.test.js): the edition's dateline and number, the folio, the seeded tilt of a
 * stamp or a cutting, the hand-drawn wavy rule under a slip, the grease-pencil loop around
 * a chosen headline, the byline a learner's piece is signed with, and the drop cap.
 *
 * Nothing here reads the network or the clock by itself: dates come in as ISO strings (the
 * session's own `startedAt` / `closedAt`), the edition number from the week («2026-W47» →
 * 47). What the payload does not carry is left out, never invented.
 */

import type { RvComptoirProof } from '@/lib/revue-types';

const DAYS_FR = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi'];
const MONTHS_FR = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];

/** The paper's city: Romy's paper is a Paris paper. */
export const PAPIER_CITY_FR = 'Paris';

/** The edition number of an ISO week («2026-W47» → «47»), '' when the week cannot be read. */
export function editionNumber(weekIso: string | null | undefined): string {
  const match = /W(\d{1,2})$/.exec(weekIso || '');
  return match ? String(Number(match[1])) : '';
}

/** «vendredi 21 novembre» for an ISO date or timestamp, read in the learner's own day; '' when unreadable. */
export function dayFr(iso: string | null | undefined): string {
  if (!iso) return '';
  // A bare day («2026-11-21») is that day wherever the learner is; a timestamp is their local day.
  const bare = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  const date = bare ? new Date(Number(bare[1]), Number(bare[2]) - 1, Number(bare[3])) : new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return `${DAYS_FR[date.getDay()]} ${date.getDate()} ${MONTHS_FR[date.getMonth()]}`;
}

/** The dateline's parts, in reading order: «Paris», «vendredi 21 novembre», «Nº 47» (each only when known). */
export function datelineParts(input: { dateIso?: string | null; weekIso?: string | null }): string[] {
  const parts = [PAPIER_CITY_FR];
  const day = dayFr(input.dateIso);
  if (day) parts.push(day);
  const n = editionNumber(input.weekIso);
  if (n) parts.push(`Nº ${n}`);
  return parts;
}

/** The folio: «2 / 5» — the screen shown among the assignment's screens (1-based, clamped). */
export function folio(steps: readonly string[], shown: string, closed: boolean): { n: number; total: number; fill: number } {
  const total = Math.max(1, steps.length);
  const at = closed && shown === 'page' ? total - 1 : Math.max(0, steps.indexOf(shown));
  const n = Math.min(total, at + 1);
  return { n, total, fill: n / total };
}

/** A small stable hash of a string (FNV-1a, 32 bits). */
export function seedOf(text: string): number {
  let hash = 0x811c9dc5;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

/**
 * The tilt of a stamp or a pasted cutting, in degrees: seeded by what it is stamped on, so the
 * same slip always lands the same way, between −max and +max and never flat (|tilt| ≥ 1).
 */
export function tilt(seed: string, max = 4): number {
  const unit = (seedOf(seed) % 1000) / 999; // 0..1
  const raw = -max + unit * 2 * max;
  const away = Math.abs(raw) < 1 ? (raw < 0 ? -1 : 1) : raw;
  return Math.round(away * 10) / 10;
}

/**
 * A hand-drawn-looking wavy rule for a slip of `chars` characters: an SVG path in a
 * `width × 6` box (stretched to the word's width), its waves about one per 1.2 characters,
 * each crest a little higher or lower (seeded), so no two slips are drawn alike.
 */
export function wavePath(seed: string, chars: number): { d: string; width: number } {
  const waves = Math.max(3, Math.round(Math.max(1, chars) / 1.2));
  const width = waves * 8;
  let hash = seedOf(seed) || 1;
  const next = () => {
    hash = Math.imul(hash ^ (hash >>> 15), 0x2c1b3c6d) >>> 0;
    return (hash % 1000) / 1000;
  };
  let d = `M0 3`;
  for (let index = 0; index < waves; index += 1) {
    const x = index * 8;
    const up = 0.6 + next() * 0.9;
    const down = 5.4 - next() * 0.9;
    d += ` Q${x + 2} ${up.toFixed(2)} ${x + 4} 3 Q${x + 6} ${down.toFixed(2)} ${x + 8} 3`;
  }
  return { d, width };
}

/**
 * The grease-pencil loop around a chosen headline: an ellipse drawn by hand — it starts a
 * little past the left, goes round once and overshoots its start — in a 100 × 40 box,
 * stretched to the proof (`preserveAspectRatio="none"`, `vector-effect: non-scaling-stroke`).
 */
export function pencilLoop(seed: string): string {
  const jitter = (n: number) => ((seedOf(`${seed}:${n}`) % 100) / 100 - 0.5) * 2; // −1..1
  const a = 3 + jitter(1);
  const b = 2 + jitter(2);
  return [
    `M${(12 + jitter(3)).toFixed(1)} ${(6 + b).toFixed(1)}`,
    `C${(40).toFixed(1)} ${(1 + jitter(4)).toFixed(1)} ${(92 + a).toFixed(1)} ${(1 + jitter(5)).toFixed(1)} ${(97 + jitter(6)).toFixed(1)} ${(18 + jitter(7)).toFixed(1)}`,
    `C${(99).toFixed(1)} ${(33 + jitter(8)).toFixed(1)} ${(56).toFixed(1)} ${(39 + jitter(9)).toFixed(1)} ${(22).toFixed(1)} ${(37 + jitter(10)).toFixed(1)}`,
    `C${(1 + jitter(11)).toFixed(1)} ${(35).toFixed(1)} ${(0.5).toFixed(1)} ${(14 + jitter(12)).toFixed(1)} ${(20 + a).toFixed(1)} ${(4 + jitter(13)).toFixed(1)}`,
  ].join(' ');
}

/** The byline a learner's piece is signed with on «La page», by how it reached print (French, as printed). */
export function bylineFr(proof: RvComptoirProof | null | undefined, tiles = false): string {
  if (tiles) return 'Par toi';
  switch (proof) {
    case 'clean':
      return 'Par toi · relu par Romy';
    case 'fixed':
      return 'Par toi · corrigé par toi';
    case 'corrected':
      return 'Par toi · corrigé par Romy';
    default:
      return 'Par toi';
  }
}

/**
 * The drop cap of a lead: its first letter (after an opening guillemet or quote, which stays
 * with the rest), and the rest. No cap for a lead that does not open on a letter.
 */
export function dropCap(text: string): { cap: string; rest: string } | null {
  const trimmed = (text || '').trim();
  const first = trimmed.charAt(0);
  // A letter has a case (Latin, accented): the cap is that letter, the rest follows it.
  if (!first || first.toLowerCase() === first.toUpperCase()) return null;
  return { cap: first, rest: trimmed.slice(1) };
}

/**
 * Which word of a slip a margin note hangs from: the note's hairline runs from the word's
 * horizontal middle (`x`, relative to the proof), clamped inside the proof's gutters.
 */
export function hairlineX(wordLeft: number, wordWidth: number, proofWidth: number, gutter = 14): number {
  const middle = wordLeft + wordWidth / 2;
  return Math.round(Math.min(Math.max(middle, gutter), Math.max(gutter, proofWidth - gutter)));
}

/**
 * FLIP for the wire's strips: from the boxes before and after a reorder, how far each strip
 * must start from (its old place) to slide to its new one. Only strips that moved.
 */
export function flipDeltas(before: Record<string, number>, after: Record<string, number>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const key of Object.keys(after)) {
    if (!(key in before)) continue;
    const delta = before[key] - after[key];
    if (Math.abs(delta) >= 1) out[key] = delta;
  }
  return out;
}

/** The edition a session is printed in: its day (filed, else started) and its week. */
export function editionOf(session: { startedAt?: string | null; closedAt?: string | null; week?: { iso: string } | null }): { dateIso: string | null; weekIso: string | null } {
  return { dateIso: session.closedAt || session.startedAt || null, weekIso: session.week?.iso ?? null };
}

/**
 * The picture a page prints: the story's own (its credit from the pictures list when it is
 * there, else the paper's «Illustration · Le Papier»), captioned by the scene line. None for a
 * season plate (it is not the story's picture).
 */
export function pagePicture(
  stage: { plateUrl: string | null; plateKind?: string; pictures?: Array<{ url: string; captionFr: string | null; creditFr: string }> } | null | undefined,
  sceneFr: string | null | undefined,
  defaultCredit: string,
): { url: string; captionFr: string | null; creditFr: string } | null {
  if (!stage || !stage.plateUrl || stage.plateKind !== 'story') return null;
  const own = (stage.pictures ?? []).find((picture) => picture.url === stage.plateUrl) ?? null;
  const caption = (own?.captionFr ?? '').trim() || (sceneFr ?? '').trim() || null;
  return { url: stage.plateUrl, captionFr: caption, creditFr: own?.creditFr || defaultCredit };
}

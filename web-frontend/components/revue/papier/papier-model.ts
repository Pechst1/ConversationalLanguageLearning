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
export function tilt(seed: string, max = 4, min = 1): number {
  const unit = (seedOf(seed) % 1000) / 999; // 0..1
  const raw = -max + unit * 2 * max;
  const floor = Math.min(min, max);
  const away = Math.abs(raw) < floor ? (raw < 0 ? -floor : floor) : raw;
  return Math.round(away * 10) / 10;
}

/** A stamp's tilt: clearly rotated (2.5° to 4°, either way), the same for the same slip. */
export function stampTilt(seed: string): number {
  return tilt(seed, 4, 2.5);
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
 * The grease-pencil loop round a chosen headline: a rounded rectangle drawn by hand round the
 * text block, in a 100 × 40 box stretched over the block and its padding. Its corners are
 * round enough that the text's own corners stay inside, so it never crosses a letter; it starts
 * on the top edge and overshoots its start a little, as a pencil does.
 */
export function pencilLoop(seed: string): string {
  const j = (n: number) => ((seedOf(`${seed}:${n}`) % 100) / 100 - 0.5) * 1.2; // −0.6..0.6
  const f = (n: number) => n.toFixed(1);
  const top = 1.2 + j(1);
  const bottom = 38.8 + j(2);
  const left = 0.8 + Math.abs(j(3));
  const right = 99.2 - Math.abs(j(4));
  return [
    `M${f(44 + j(5) * 3)} ${f(top)}`,
    `L${f(right - 7)} ${f(top)}`,
    `Q${f(right)} ${f(top)} ${f(right)} ${f(top + 12)}`,
    `L${f(right + j(6) * 0.5)} ${f(bottom - 12)}`,
    `Q${f(right)} ${f(bottom)} ${f(right - 7)} ${f(bottom)}`,
    `L${f(left + 7)} ${f(bottom + j(7) * 0.5)}`,
    `Q${f(left)} ${f(bottom)} ${f(left)} ${f(bottom - 12)}`,
    `L${f(left + j(8) * 0.5)} ${f(top + 12)}`,
    `Q${f(left)} ${f(top)} ${f(left + 7)} ${f(top)}`,
    `L${f(51 + j(5) * 3)} ${f(top - 0.3)}`,
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
 * How a piece reached print, as the byline's tail, agreed with what it qualifies («relue par
 * Romy» for a caption, «relus par Romy» for an interview's words); '' when it went as written.
 * «Corrigé(e)» alone when the learner fixed it: the byline already says «par toi».
 */
export function proofNoteFr(proof: RvComptoirProof | null | undefined, agree: '' | 'e' | 's' = ''): string {
  switch (proof) {
    case 'clean':
      return `relu${agree} par Romy`;
    case 'fixed':
      return `corrigé${agree}`;
    case 'corrected':
      return `corrigé${agree} par Romy`;
    default:
      return '';
  }
}

/** «La photo»: the learner's caption under the picture is signed «Légende · par toi» (and how it reached print). */
export function legendeBylineFr(proof: RvComptoirProof | null | undefined, tiles = false): string {
  const note = tiles ? '' : proofNoteFr(proof, 'e');
  return ['Légende · par toi', note].filter(Boolean).join(', ');
}

/**
 * The drop cap of a lead: its first letter (after an opening guillemet or quote, which stays
 * with the rest), and the rest. No cap for a lead that does not open on a letter.
 */
export function dropCap(text: string): { cap: string; rest: string } | null {
  const trimmed = (text || '').trim();
  const isLetter = (c: string) => Boolean(c) && c.toLowerCase() !== c.toUpperCase();
  const first = trimmed.charAt(0);
  // A cap only when the next character is a letter too: «D'abord», «L'été» or «À 8 h» would
  // strand an apostrophe or a space beside the cap, so those leads are set without one.
  if (!isLetter(first) || !isLetter(trimmed.charAt(1))) return null;
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
  if (!stage) return null;
  const pictures = stage.pictures ?? [];
  // The story's lead picture: its own painted plate, else the first of its pictures (a photo);
  // a season plate is the place's, not the story's.
  const own = stage.plateUrl && stage.plateKind === 'story' ? (pictures.find((picture) => picture.url === stage.plateUrl) ?? null) : null;
  const lead = own ?? pictures[0] ?? null;
  const url = own ? (stage.plateUrl as string) : lead?.url ?? (stage.plateKind === 'story' ? stage.plateUrl : null);
  if (!url) return null;
  const caption = (lead?.captionFr ?? '').trim() || (sceneFr ?? '').trim() || null;
  return { url, captionFr: caption, creditFr: lead?.creditFr || defaultCredit };
}

/** A line folded for comparison: lower case, no accents, letters and digits only. */
export function foldLine(text: string | null | undefined): string {
  return (text ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

/**
 * A standfirst worth printing under a headline: none when it says nothing the headline does
 * not (contained in it, case and accents folded) — a front page never repeats its headline.
 */
export function standfirstFor(headline: string | null | undefined, line: string | null | undefined): string | null {
  const text = (line ?? '').trim();
  if (!text) return null;
  const folded = foldLine(text);
  if (!folded || foldLine(headline).includes(folded)) return null;
  return text;
}

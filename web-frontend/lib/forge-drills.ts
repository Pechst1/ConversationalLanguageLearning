/**
 * La Forge's formats on screen (owner, 2026-10-18: more varied, more fun,
 * more personal, faster learning).
 *
 * The server says how each item is posed (`forge.next.drill`, and
 * `correction.forge.drill` once it is answered; `app/services/forge_drills.py`).
 * Beyond the classic choice, judgement, tiles and rewrite, the page draws:
 *
 *   - typed («Tape la forme»): a fill whose form is typed, accents on a bar;
 *   - dictation («Dictée»): a word bank heard, not read; its meaning shows after;
 *   - spot («Trouve l'erreur»): a repair whose wrong word is tapped and fixed;
 *   - mine («Ta phrase»): the learner's own saved mistake, fixed the same way;
 *   - rafale: four judgements, one tap each, sent as one answer.
 *
 * Grading never changes with the format: a typed fill is a fill, a dictation a
 * word bank, a spot a repair. Pure: no React, so node tests read it directly.
 */

import { fillForge, type ForgeCopy } from './forge-copy';
import { clampRung } from './forge-progress';

export { levelText } from './forge-progress';

export type ForgeDrill =
  | 'choice'
  | 'judge'
  | 'rafale'
  | 'tiles'
  | 'dictation'
  | 'typed'
  | 'spot'
  | 'mine'
  | 'rewrite'
  | 'write'
  | 'scene';

const DRILLS: ReadonlySet<string> = new Set([
  'choice', 'judge', 'rafale', 'tiles', 'dictation', 'typed', 'spot', 'mine', 'rewrite', 'write', 'scene',
]);

/** The formats that name themselves on screen: each asks for a new gesture. */
export const NAMED_DRILLS = ['typed', 'dictation', 'spot', 'mine', 'rafale'] as const;
export type NamedDrill = (typeof NAMED_DRILLS)[number];

export function asDrill(value: unknown): ForgeDrill | null {
  const drill = String(value ?? '').trim();
  return DRILLS.has(drill) ? (drill as ForgeDrill) : null;
}

export function isNamedDrill(drill: ForgeDrill | null | undefined): drill is NamedDrill {
  return (NAMED_DRILLS as readonly string[]).includes(String(drill));
}

type NextLike = {
  concept_id?: number | string | null;
  round?: string | null;
  mode?: string | null;
  item_id?: string | number | null;
  drill?: unknown;
  items?: unknown;
} | null | undefined;

type CorrectionLike = { forge?: { drill?: unknown } | null } | Record<string, any> | null | undefined;

export type ScreenItem = {
  conceptId: number | null | undefined;
  round: string;
  mode: string;
  itemId: string | null | undefined;
};

/** Is this the item the forge is serving right now? */
export function isServed(next: NextLike, here: ScreenItem): boolean {
  if (!next || here.itemId == null || here.itemId === '') return false;
  return Number(next.concept_id) === Number(here.conceptId)
    && String(next.round) === here.round
    && (here.round !== 'recognize' || String(next.mode) === here.mode)
    && String(next.item_id) === String(here.itemId);
}

/**
 * How the item on screen is posed: the forge's word while it serves it, then
 * the answer's own record (the forge has moved on by the time the feedback
 * shows). `null` for an older server, which draws every item the classic way.
 */
export function drillOnScreen(next: NextLike, correction: CorrectionLike, here: ScreenItem): ForgeDrill | null {
  if (isServed(next, here)) return asDrill(next?.drill);
  return asDrill((correction as { forge?: { drill?: unknown } } | null | undefined)?.forge?.drill);
}

// ---------------------------------------------------------------------------
// «Rafale»: four judgements as one answer
// ---------------------------------------------------------------------------

/** A burst's judgements, the lead first; empty unless the forge sent two or more. */
export function burstItems(next: NextLike): Array<Record<string, any>> {
  const items = Array.isArray(next?.items)
    ? (next!.items as unknown[]).filter((item): item is Record<string, any> => Boolean(item) && typeof item === 'object' && (item as any).id != null)
    : [];
  return items.length >= 2 ? items : [];
}

/** The ids a burst is graded by, joined with «+» on its exercise id. */
export function burstItemKey(items: Array<Record<string, any>>): string {
  return items.map((item) => String(item.id)).join('+');
}

export type BurstRow = {
  itemId: string;
  sentence: string;
  answer: string;
  expected: string;
  correct: boolean;
  correctedFr: string | null;
};

/** The burst's marks from the server (`correction.burst`), in the order posed. */
export function burstRows(
  correction: Record<string, any> | null | undefined,
  items: Array<Record<string, any>> = [],
): BurstRow[] {
  const rows = Array.isArray(correction?.burst) ? correction!.burst : [];
  return rows
    .filter((row: any) => row && row.item_id != null)
    .map((row: any) => {
      const item = items.find((candidate) => String(candidate.id) === String(row.item_id));
      return {
        itemId: String(row.item_id),
        sentence: String(row.sentence || item?.prompt || '').trim(),
        answer: String(row.answer || ''),
        expected: String(row.expected || ''),
        correct: Boolean(row.correct),
        correctedFr: String(row.corrected_fr || '').trim() || null,
      };
    });
}

/** «7,4 s» in French and German, «7.4 s» in English; null without a time. */
export function burstSeconds(ms: number | null | undefined, language: string): string | null {
  const value = Number(ms);
  if (!Number.isFinite(value) || value <= 0) return null;
  const seconds = Math.max(0.1, Math.round(value / 100) / 10);
  const text = seconds.toFixed(1);
  return language === 'en' ? text : text.replace('.', ',');
}

// ---------------------------------------------------------------------------
// «Trouve l'erreur» and «Ta phrase»: tap a word, fix it
// ---------------------------------------------------------------------------

export type SpotToken = {
  /** Punctuation before the word («, (). */
  lead: string;
  /** The word itself; empty for a token that is only punctuation. */
  word: string;
  /** Punctuation after it (., !, »). */
  trail: string;
  /** The spacing that followed it in the sentence. */
  space: string;
};

const LEAD = /^[«"“„(\[¿¡'’]+/;
const TRAIL = /[.,;:!?…»"”)\]]+$/;

/** A sentence as tappable words; punctuation rides along and is never a word. */
export function spotTokens(sentence: unknown): SpotToken[] {
  const text = String(sentence ?? '').trim();
  const tokens: SpotToken[] = [];
  const words = /(\S+)(\s*)/g;
  let match: RegExpExecArray | null;
  while ((match = words.exec(text)) !== null) {
    const raw = match[1];
    const lead = (raw.match(LEAD) || [''])[0];
    const rest = raw.slice(lead.length);
    const trail = (rest.match(TRAIL) || [''])[0];
    const word = rest.slice(0, rest.length - trail.length);
    tokens.push(word ? { lead, word, trail, space: match[2] } : { lead: '', word: '', trail: raw, space: match[2] });
  }
  return tokens;
}

/**
 * The sentence with the learner's fixes in it (an empty fix drops the word).
 * A fix that elides («une» → «d'») joins the next word: «pas d'idée».
 */
export function spotAnswer(tokens: SpotToken[], edits: Record<number, string>): string {
  return tokens
    .map((token, index) => {
      const word = Object.prototype.hasOwnProperty.call(edits, index) ? String(edits[index]).trim() : token.word;
      return `${token.lead}${word}${token.trail}${token.space || ' '}`;
    })
    .join('')
    .replace(/\s+/g, ' ')
    .replace(/\s+([.,])/g, '$1')
    .replace(/([A-Za-zÀ-ÿœŒ]['’]) (?=\S)/g, '$1')
    .trim();
}

/**
 * The fixes with `draft` typed into the word at `index`. The fix is part of the
 * answer from the first letter typed (#357): Check never waits for Enter, a
 * blur or a tap elsewhere to «commit» what is already on screen. A draft that
 * is the word as it was is no fix and takes the word out of the edits.
 */
export function spotDraftEdits(
  tokens: SpotToken[],
  edits: Record<number, string>,
  index: number,
  draft: string,
): Record<number, string> {
  const token = tokens[index];
  if (!token) return edits;
  const value = String(draft ?? '').replace(/\s+/g, ' ').trim();
  const next = { ...edits };
  if (value === token.word) delete next[index];
  else next[index] = value;
  return next;
}

/** Did the fixes change anything? (Retyping a word as it was is no fix.) */
export function spotChanged(tokens: SpotToken[], edits: Record<number, string>): boolean {
  return Object.entries(edits).some(([index, value]) => {
    const token = tokens[Number(index)];
    return Boolean(token) && String(value).trim() !== token.word;
  });
}

// ---------------------------------------------------------------------------
// «Tape la forme»: the accent bar
// ---------------------------------------------------------------------------

/** The letters a phone keyboard hides behind a long press, most used first. */
export const ACCENTS = ['é', 'è', 'ê', 'à', 'â', 'ç', 'ù', 'ô', 'î', 'œ'] as const;

/** `insert` typed at the caret (over the selection); the new caret after it. */
export function insertAt(
  value: string,
  start: number | null | undefined,
  end: number | null | undefined,
  insert: string,
): { value: string; caret: number } {
  const text = String(value ?? '');
  // No caret known (the field never focused): the letter goes at the end.
  const known = (at: number | null | undefined): at is number => at != null && Number.isFinite(Number(at));
  const from = known(start) ? Math.max(0, Math.min(text.length, Number(start))) : text.length;
  const to = known(end) ? Math.max(from, Math.min(text.length, Number(end))) : from;
  return { value: `${text.slice(0, from)}${insert}${text.slice(to)}`, caret: from + insert.length };
}

// ---------------------------------------------------------------------------
// «Dictée»: what is heard
// ---------------------------------------------------------------------------

/** The sentence a dictation speaks: the word bank's own answer. */
export function dictationText(item: Record<string, any> | null | undefined): string {
  const answer = String(item?.correct_answer || '').trim();
  if (answer) return answer;
  const tokens = Array.isArray(item?.answer_tokens) ? item!.answer_tokens : [];
  return tokens.map((token: unknown) => String(token)).join(' ').replace(/\s+([.,!?;:])/g, '$1').trim();
}

// ---------------------------------------------------------------------------
// The level, the run and the cheer
// ---------------------------------------------------------------------------

/** A run is cheered from its second right answer. */
export const RUN_CHEER_FROM = 2;

/**
 * The line under a right answer: the rule held, or the level it climbed to,
 * and the run of right answers — «Niveau 4 ↑ · 3 d'affilée». `null` when
 * there is nothing to cheer (a miss never gets a line here).
 */
export function forgeCheer(correction: Record<string, any> | null | undefined, copy: ForgeCopy): string | null {
  const forge = correction?.forge;
  if (!forge || typeof forge !== 'object') return null;
  const parts: string[] = [];
  // #402: a climb is measured from the level before the answer; an item posed below
  // it (a warm-up) is not one. An older server sends only the item's rung.
  const levelBefore = Number(forge.level_before);
  const rung = Number.isFinite(levelBefore) ? levelBefore : Number(forge.rung);
  const after = Number(forge.new_rung);
  if (forge.held) parts.push(copy.cheer_held);
  else if (Number.isFinite(rung) && Number.isFinite(after) && after > rung) parts.push(fillForge(copy.level_up, { n: clampRung(after) + 1 }));
  const run = Math.floor(Number(forge.run) || 0);
  if (run >= RUN_CHEER_FROM) parts.push(fillForge(copy.run_cheer, { n: run }));
  return parts.length ? parts.join(' · ') : null;
}

// ---------------------------------------------------------------------------
// The recap's épreuve offer
// ---------------------------------------------------------------------------

export type TestOutOffer = { conceptId: number; items: number };

/** The rule the recap offers to test out (`recap.forge.test_out_offer`), or null. */
export function testOutOffer(recap: { forge?: { test_out_offer?: unknown } | null } | null | undefined): TestOutOffer | null {
  const offer = recap?.forge?.test_out_offer as { concept_id?: unknown; items?: unknown } | null | undefined;
  const conceptId = Number(offer?.concept_id);
  if (!offer || !Number.isFinite(conceptId) || conceptId <= 0) return null;
  const items = Math.floor(Number(offer.items));
  return { conceptId, items: Number.isFinite(items) && items > 0 ? items : 3 };
}

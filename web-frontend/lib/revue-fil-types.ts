/**
 * «Le fil» (WIRE §10, owner 2026-11-20): the wire's view, its page, its acts.
 *
 * Kept beside `revue-types.ts` (which parses the session and hands `fil` here) so the
 * assignment's wire stays in one place. Snake_case in, camelCase out, every field
 * defaulted: a view the client cannot read is drawn as nothing, never as a wrong answer.
 */

import { parseComptoirNotes, type RvComptoirMark, type RvComptoirMarkKind, type RvComptoirNote, type RvComptoirProof, type RvComptoirText, type RvSource } from './revue-types';

type Json = Record<string, any>;

export type RvFilStep = 'read' | 'order' | 'words' | 'tell' | 'page';
export const RV_FIL_STEPS = ['read', 'order', 'words', 'tell', 'page'] as const;
export type RvFilRole = 'first' | 'middle' | 'last';
const ROLES = ['first', 'middle', 'last'] as const;
const PROOFS = ['clean', 'marked', 'fixed', 'corrected', 'as_written'] as const;
const MARK_KINDS = ['accord', 'conjugaison', 'genre', 'orthographe', 'mot', 'ordre', 'manque'] as const;

/** A dispatch of the wire. `key` is the session's letter for it: it says nothing of the true order. */
export type RvFilStrip = { key: string; text: RvComptoirText; label: RvComptoirText | null };
export type RvFilOrder = {
  /** In the order they were shown. */
  strips: RvFilStrip[];
  tries: number;
  maxTries: number;
  placed: string[];
  /** After a wrong try: the first strip out of place happens after `afterKey`. */
  hint: { key: string; afterKey: string } | null;
  resolved: boolean;
  correct: boolean | null;
  /** The keys in true order, only once resolved. */
  solution: string[];
};
/** A sequence word; `tr` and `role` only once the words step is resolved (or on a miss). */
export type RvFilConnector = { id: string; fr: string; tr: string | null; role: RvFilRole | null };
export type RvFilMiss = { position: number; id: string; fr: string; tr: string | null; role: RvFilRole; needs: RvFilRole };
export type RvFilWords = {
  input: 'place' | 'choose';
  /** The strips in true order. */
  strips: RvComptoirText[];
  connectors: RvFilConnector[];
  /** `choose`: three word ids per strip. */
  options: string[][];
  tries: number;
  maxTries: number;
  picked: string[];
  misses: RvFilMiss[];
  resolved: boolean;
  correct: boolean | null;
  solution: string[];
};
export type RvFilTell = {
  input: 'tiles' | 'frames' | 'free';
  phrase: RvComptoirText;
  tiles: Array<{ key: string; text: RvComptoirText }>;
  connectors: RvFilConnector[];
  frames: RvComptoirText[];
  minWords: number;
  minConnectors: number;
  learnerFr: string | null;
  draftFr: string | null;
  proof: RvComptoirProof | null;
  marks: RvComptoirMark[];
  tries: number;
  maxTries: number;
  printedFr: string | null;
  /** «Le pourquoi» (`REVUE_POURQUOI_ENABLED`), once settled: the marks explained, as the counter's. */
  notes?: RvComptoirNote[];
};
export type RvFilView = {
  step: RvFilStep;
  steps: RvFilStep[];
  band: 'a1' | 'a2' | 'b1';
  titleFr: string;
  read: { datelineFr: string; lead: RvComptoirText; sources: RvSource[] };
  order: RvFilOrder | null;
  words: RvFilWords | null;
  tell: RvFilTell | null;
};
export type RvFilPage = {
  titleFr: string;
  datelineFr: string;
  strips: Array<{ connectorFr: string; textFr: string }>;
  mineFr: string;
  proof: RvComptoirProof | null;
  phraseFr: string;
  words: string[];
};
/** Why an act was not recorded: the client says it in the learner's language. */
export type RvFilError = { code: string; key: string | null; afterKey: string | null; count: number | null };
export type RvFilBody =
  | { act: 'open' }
  | { act: 'order'; order: string[] }
  | { act: 'words'; picks: string[] }
  | { act: 'tell'; parts: string[] }
  | { act: 'tell'; texts: string[]; mode?: 'text' | 'voice' }
  | { act: 'tell'; text: string; mode?: 'text' | 'voice' }
  | { act: 'tell_fix'; text: string; mode?: 'text' | 'voice' }
  | { act: 'tell_fix'; value: 'romy' };

function isObject(value: unknown): value is Json {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}
function str(value: unknown): string {
  return typeof value === 'string' ? value : value == null ? '' : String(value);
}
function strOrNull(value: unknown): string | null {
  return typeof value === 'string' && value ? value : null;
}
function num(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}
function list<T>(value: unknown, parse: (row: Json) => T): T[] {
  return Array.isArray(value) ? value.filter(isObject).map(parse) : [];
}
function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.map(str).filter(Boolean) : [];
}
function oneOf<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return (allowed as readonly string[]).includes(value as string) ? (value as T) : fallback;
}
function text(value: unknown): RvComptoirText {
  const row = isObject(value) ? value : {};
  return { fr: str(row.fr), tr: strOrNull(row.tr) };
}
function connector(row: Json): RvFilConnector {
  return { id: str(row.id), fr: str(row.fr), tr: strOrNull(row.tr), role: row.role == null ? null : oneOf(row.role, ROLES, 'middle') };
}

export function parseFilView(raw: Json, parseSource: (row: Json) => RvSource): RvFilView {
  const read = isObject(raw.read) ? raw.read : {};
  const order = isObject(raw.order) ? raw.order : null;
  const words = isObject(raw.words) ? raw.words : null;
  const tell = isObject(raw.tell) ? raw.tell : null;
  const steps = Array.isArray(raw.steps) ? raw.steps.filter((step: unknown): step is RvFilStep => (RV_FIL_STEPS as readonly unknown[]).includes(step)) : [];
  const hint = order && isObject(order.hint) ? order.hint : null;
  return {
    step: oneOf(raw.step, RV_FIL_STEPS, 'read'),
    steps: steps.length ? steps : [...RV_FIL_STEPS],
    band: oneOf(raw.band, ['a1', 'a2', 'b1'] as const, 'a2'),
    titleFr: str(raw.title_fr),
    read: { datelineFr: str(read.dateline_fr), lead: text(read.lead), sources: list(read.sources, parseSource) },
    order: order
      ? {
          strips: list(order.strips, (row) => ({ key: str(row.key), text: text(row.text), label: isObject(row.label) ? text(row.label) : null })),
          tries: num(order.tries),
          maxTries: num(order.max_tries) || 2,
          placed: strings(order.placed),
          hint: hint ? { key: str(hint.key), afterKey: str(hint.after_key) } : null,
          resolved: Boolean(order.resolved),
          correct: typeof order.correct === 'boolean' ? order.correct : null,
          solution: strings(order.solution),
        }
      : null,
    words: words
      ? {
          input: words.input === 'place' ? 'place' : 'choose',
          strips: Array.isArray(words.strips) ? words.strips.filter(isObject).map(text) : [],
          connectors: list(words.connectors, connector),
          options: Array.isArray(words.options) ? words.options.map(strings) : [],
          tries: num(words.tries),
          maxTries: num(words.max_tries) || 2,
          picked: strings(words.picked),
          misses: list(words.misses, (row) => ({
            position: num(row.position),
            id: str(row.id),
            fr: str(row.fr),
            tr: strOrNull(row.tr),
            role: oneOf(row.role, ROLES, 'middle'),
            needs: oneOf(row.needs, ROLES, 'middle'),
          })),
          resolved: Boolean(words.resolved),
          correct: typeof words.correct === 'boolean' ? words.correct : null,
          solution: strings(words.solution),
        }
      : null,
    tell: tell
      ? {
          input: oneOf(tell.input, ['tiles', 'frames', 'free'] as const, 'free'),
          phrase: text(tell.phrase),
          tiles: list(tell.tiles, (row) => ({ key: str(row.key), text: text(row.text) })),
          connectors: list(tell.connectors, connector),
          frames: Array.isArray(tell.frames) ? tell.frames.filter(isObject).map(text) : [],
          minWords: num(tell.min_words),
          minConnectors: num(tell.min_connectors),
          learnerFr: strOrNull(tell.learner_fr),
          draftFr: strOrNull(tell.draft_fr),
          proof: tell.proof == null ? null : oneOf(tell.proof, PROOFS, 'as_written'),
          marks: list(tell.marks, (row) => ({
            spanFr: str(row.span_fr),
            start: num(row.start),
            kind: oneOf(row.kind, MARK_KINDS, 'mot') as RvComptoirMarkKind,
            ...(str(row.why).trim() ? { why: str(row.why).trim() } : {}),
          })).filter((mark) => mark.spanFr),
          tries: num(tell.tries),
          maxTries: num(tell.max_tries) || 2,
          printedFr: strOrNull(tell.printed_fr),
          ...(Array.isArray(tell.notes) && tell.notes.length ? { notes: parseComptoirNotes(tell.notes) } : {}),
        }
      : null,
  };
}

export function parseFilPage(raw: Json): RvFilPage {
  return {
    titleFr: str(raw.title_fr),
    datelineFr: str(raw.dateline_fr),
    strips: list(raw.strips, (row) => ({ connectorFr: str(row.connector_fr), textFr: str(row.text_fr) })),
    mineFr: str(raw.mine_fr),
    proof: raw.proof == null ? null : oneOf(raw.proof, PROOFS, 'as_written'),
    phraseFr: str(raw.phrase_fr),
    words: strings(raw.words),
  };
}

export function parseFilError(raw: unknown): RvFilError | null {
  if (!isObject(raw) || !raw.code) return null;
  return { code: str(raw.code), key: strOrNull(raw.key), afterKey: strOrNull(raw.after_key), count: typeof raw.count === 'number' ? raw.count : null };
}

export function filBodyWire(body: RvFilBody): Json {
  const wire: Json = { act: body.act };
  if ('order' in body) wire.order = body.order;
  if ('picks' in body) wire.picks = body.picks;
  if ('parts' in body) wire.parts = body.parts;
  if ('texts' in body) wire.texts = body.texts;
  if ('text' in body) wire.text = body.text;
  if ('value' in body) wire.value = body.value;
  if ('mode' in body && body.mode) wire.mode = body.mode;
  return wire;
}

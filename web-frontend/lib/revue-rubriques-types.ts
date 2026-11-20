/**
 * «Le titre» and «L'intox express» (WIRE §11, 2026-11-20): their views, pages and acts.
 *
 * Kept beside `revue-types.ts` (which parses the session and hands `titre` / `intox`
 * here), as `revue-fil-types.ts` is for «Le fil». Snake_case in, camelCase out, every
 * field defaulted: a view the client cannot read is drawn as nothing, never as a wrong
 * answer. Both play through ONE act route (`POST …/rubrique`).
 */

import type { RvClaim, RvComptoirMark, RvComptoirMarkKind, RvComptoirProof, RvComptoirText, RvSource } from './revue-types';

type Json = Record<string, any>;

export type RvTitreStep = 'read' | 'three' | 'trap' | 'build' | 'page';
export const RV_TITRE_STEPS = ['read', 'three', 'trap', 'build', 'page'] as const;
export type RvIntoxStep = 'read' | 'round' | 'fix' | 'page';
export const RV_INTOX_STEPS = ['read', 'round', 'fix', 'page'] as const;
export type RvTitreRole = 'honest' | 'exaggerated' | 'off';
const ROLES = ['honest', 'exaggerated', 'off'] as const;
const PROOFS = ['clean', 'marked', 'fixed', 'corrected', 'as_written'] as const;
const MARK_KINDS = ['accord', 'conjugaison', 'genre', 'orthographe', 'mot', 'ordre', 'manque'] as const;

export type RvRubriqueRead = { datelineFr: string; lead: RvComptoirText; sources: RvSource[] };
/** The outlet's verbatim words, its name, and the words in them that settle the point ('' lights nothing). */
export type RvRubriqueQuote = { quoteFr: string; settlesFr: string; sourceName: string };

/** A headline; `role`, `why` and `claim` only on a wrong one the learner picked, and on all once resolved. */
export type RvTitreOption = { key: string; text: RvComptoirText; role: RvTitreRole | null; why: RvComptoirText | null; claim: RvClaim | null };
export type RvTitreThree = {
  by: { id: string; nameFr: string; roleFr: string };
  headlines: RvTitreOption[];
  tries: number;
  maxTries: number;
  picked: string[];
  resolved: boolean;
  correct: boolean | null;
  /** The honest headline's key, only once resolved. */
  solution: string | null;
};
export type RvTitreTrap = {
  headline: RvComptoirText;
  words: Array<{ index: number; fr: string }>;
  tries: number;
  maxTries: number;
  picked: number[];
  /** After a miss: the tapped words the claims do say (never the answer). */
  fine: number[];
  resolved: boolean;
  correct: boolean | null;
  solution: number[];
  why: RvComptoirText | null;
  claim: RvClaim | null;
};
export type RvTitreBuild = {
  input: 'tiles' | 'frame' | 'free';
  phrase: RvComptoirText;
  subjects: RvComptoirText[];
  facts: RvComptoirText[];
  frame: RvComptoirText | null;
  maxWords: number;
  avoidFr: string;
  learnerFr: string | null;
  draftFr: string | null;
  proof: RvComptoirProof | null;
  marks: RvComptoirMark[];
  tries: number;
  maxTries: number;
  printedFr: string | null;
};
export type RvTitreView = {
  step: RvTitreStep;
  steps: RvTitreStep[];
  band: 'a1' | 'a2' | 'b1';
  titleFr: string;
  read: RvRubriqueRead;
  three: RvTitreThree | null;
  trap: RvTitreTrap | null;
  build: RvTitreBuild | null;
};
export type RvTitrePage = {
  headlineFr: string;
  proof: RvComptoirProof | null;
  datelineFr: string;
  leadFr: string;
  honestFr: string;
  phraseFr: string;
  words: string[];
};

/** A statement; past `text` only once it is answered. */
export type RvIntoxCard = {
  key: string;
  text: RvComptoirText;
  answer: 'vrai' | 'faux' | null;
  true: boolean | null;
  correct: boolean | null;
  why: RvComptoirText | null;
  quote: RvRubriqueQuote | null;
  wrongFr: string | null;
};
export type RvIntoxRound = { cards: RvIntoxCard[]; current: string | null; score: number; answered: number; total: number };
export type RvIntoxFixItem = {
  key: string;
  text: RvComptoirText;
  wrongFr: string;
  options: string[];
  quote: RvRubriqueQuote;
  tries: number;
  maxTries: number;
  attempts: string[];
  resolved: boolean;
  correct: boolean | null;
  rightFr: string | null;
  fixed: RvComptoirText | null;
};
export type RvIntoxView = {
  step: RvIntoxStep;
  steps: RvIntoxStep[];
  band: 'a1' | 'a2' | 'b1';
  titleFr: string;
  read: RvRubriqueRead;
  round: RvIntoxRound | null;
  fix: { input: 'pick' | 'write'; phrase: RvComptoirText; items: RvIntoxFixItem[] } | null;
};
export type RvIntoxPageLine = {
  textFr: string;
  wasFalse: boolean;
  wrongFr: string | null;
  answeredRight: boolean;
  learnerFr: string | null;
  fixedRight: boolean | null;
};
export type RvIntoxPage = {
  titleFr: string;
  datelineFr: string;
  lines: RvIntoxPageLine[];
  score: number;
  total: number;
  fixed: number;
  phraseFr: string;
  words: string[];
};

/** Why an act was not recorded: the client says it in the learner's language. */
export type RvRubriqueError = { code: string; key: string | null; count: number | null };
type Mode = { mode?: 'text' | 'voice' };
export type RvRubriqueBody =
  | { act: 'open' }
  | { act: 'pick'; key: string }
  | { act: 'trap'; words: number[] }
  | { act: 'build'; parts: number[] }
  | ({ act: 'build'; text: string } & Mode)
  | ({ act: 'build_fix'; text: string } & Mode)
  | { act: 'build_fix'; value: 'romy' }
  | { act: 'answer'; key: string; value: 'vrai' | 'faux' }
  | { act: 'fix'; key: string; value: string }
  | ({ act: 'fix'; key: string; text: string } & Mode);

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
function bool(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null;
}
function list<T>(value: unknown, parse: (row: Json) => T): T[] {
  return Array.isArray(value) ? value.filter(isObject).map(parse) : [];
}
function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.map(str).filter(Boolean) : [];
}
function numbers(value: unknown): number[] {
  return Array.isArray(value) ? value.filter((n): n is number => typeof n === 'number' && Number.isInteger(n)) : [];
}
function oneOf<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return (allowed as readonly string[]).includes(value as string) ? (value as T) : fallback;
}
function text(value: unknown): RvComptoirText {
  const row = isObject(value) ? value : {};
  return { fr: str(row.fr), tr: strOrNull(row.tr) };
}
function textOrNull(value: unknown): RvComptoirText | null {
  return isObject(value) && value.fr ? text(value) : null;
}
function steps<T extends string>(value: unknown, allowed: readonly T[]): T[] {
  const rows = Array.isArray(value) ? value.filter((step: unknown): step is T => (allowed as readonly unknown[]).includes(step)) : [];
  return rows.length ? rows : [...allowed];
}
function read(value: unknown, parseSource: (row: Json) => RvSource): RvRubriqueRead {
  const row = isObject(value) ? value : {};
  return { datelineFr: str(row.dateline_fr), lead: text(row.lead), sources: list(row.sources, parseSource) };
}
function quote(value: unknown): RvRubriqueQuote {
  const row = isObject(value) ? value : {};
  return { quoteFr: str(row.quote_fr), settlesFr: str(row.settles_fr), sourceName: str(row.source_name) };
}
function proof(value: unknown): RvComptoirProof | null {
  return value == null ? null : oneOf(value, PROOFS, 'as_written');
}
function marks(value: unknown): RvComptoirMark[] {
  return list(value, (row) => ({ spanFr: str(row.span_fr), start: num(row.start), kind: oneOf(row.kind, MARK_KINDS, 'mot') as RvComptoirMarkKind })).filter(
    (mark) => mark.spanFr,
  );
}
const BANDS = ['a1', 'a2', 'b1'] as const;

export function parseTitreView(raw: Json, parseSource: (row: Json) => RvSource, parseClaim: (row: Json) => RvClaim): RvTitreView {
  const three = isObject(raw.three) ? raw.three : null;
  const trap = isObject(raw.trap) ? raw.trap : null;
  const build = isObject(raw.build) ? raw.build : null;
  const claim = (value: unknown) => (isObject(value) ? parseClaim(value) : null);
  const by = three && isObject(three.by) ? three.by : {};
  return {
    step: oneOf(raw.step, RV_TITRE_STEPS, 'read'),
    steps: steps(raw.steps, RV_TITRE_STEPS),
    band: oneOf(raw.band, BANDS, 'a2'),
    titleFr: str(raw.title_fr),
    read: read(raw.read, parseSource),
    three: three
      ? {
          by: { id: str(by.id), nameFr: str(by.name_fr), roleFr: str(by.role_fr) },
          headlines: list(three.headlines, (row) => ({
            key: str(row.key),
            text: text(row.text),
            role: row.role == null ? null : oneOf(row.role, ROLES, 'off'),
            why: textOrNull(row.why),
            claim: claim(row.claim),
          })),
          tries: num(three.tries),
          maxTries: num(three.max_tries) || 2,
          picked: strings(three.picked),
          resolved: Boolean(three.resolved),
          correct: bool(three.correct),
          solution: strOrNull(three.solution),
        }
      : null,
    trap: trap
      ? {
          headline: text(trap.headline),
          words: list(trap.words, (row) => ({ index: num(row.index), fr: str(row.fr) })),
          tries: num(trap.tries),
          maxTries: num(trap.max_tries) || 2,
          picked: numbers(trap.picked),
          fine: numbers(trap.fine),
          resolved: Boolean(trap.resolved),
          correct: bool(trap.correct),
          solution: numbers(trap.solution),
          why: textOrNull(trap.why),
          claim: claim(trap.claim),
        }
      : null,
    build: build
      ? {
          input: oneOf(build.input, ['tiles', 'frame', 'free'] as const, 'free'),
          phrase: text(build.phrase),
          subjects: Array.isArray(build.subjects) ? build.subjects.filter(isObject).map(text) : [],
          facts: Array.isArray(build.facts) ? build.facts.filter(isObject).map(text) : [],
          frame: textOrNull(build.frame),
          maxWords: num(build.max_words) || 12,
          avoidFr: str(build.avoid_fr),
          learnerFr: strOrNull(build.learner_fr),
          draftFr: strOrNull(build.draft_fr),
          proof: proof(build.proof),
          marks: marks(build.marks),
          tries: num(build.tries),
          maxTries: num(build.max_tries) || 2,
          printedFr: strOrNull(build.printed_fr),
        }
      : null,
  };
}

export function parseIntoxView(raw: Json, parseSource: (row: Json) => RvSource): RvIntoxView {
  const round = isObject(raw.round) ? raw.round : null;
  const fix = isObject(raw.fix) ? raw.fix : null;
  return {
    step: oneOf(raw.step, RV_INTOX_STEPS, 'read'),
    steps: steps(raw.steps, RV_INTOX_STEPS),
    band: oneOf(raw.band, BANDS, 'a2'),
    titleFr: str(raw.title_fr),
    read: read(raw.read, parseSource),
    round: round
      ? {
          cards: list(round.cards, (row) => ({
            key: str(row.key),
            text: text(row.text),
            answer: row.answer == null ? null : oneOf(row.answer, ['vrai', 'faux'] as const, 'vrai'),
            true: bool(row.true),
            correct: bool(row.correct),
            why: textOrNull(row.why),
            quote: isObject(row.quote) ? quote(row.quote) : null,
            wrongFr: strOrNull(row.wrong_fr),
          })),
          current: strOrNull(round.current),
          score: num(round.score),
          answered: num(round.answered),
          total: num(round.total) || 5,
        }
      : null,
    fix: fix
      ? {
          input: fix.input === 'pick' ? 'pick' : 'write',
          phrase: text(fix.phrase),
          items: list(fix.items, (row) => ({
            key: str(row.key),
            text: text(row.text),
            wrongFr: str(row.wrong_fr),
            options: strings(row.options),
            quote: quote(row.quote),
            tries: num(row.tries),
            maxTries: num(row.max_tries) || 2,
            attempts: strings(row.attempts),
            resolved: Boolean(row.resolved),
            correct: bool(row.correct),
            rightFr: strOrNull(row.right_fr),
            fixed: textOrNull(row.fixed),
          })),
        }
      : null,
  };
}

export function parseTitrePage(raw: Json): RvTitrePage {
  return {
    headlineFr: str(raw.headline_fr),
    proof: proof(raw.proof),
    datelineFr: str(raw.dateline_fr),
    leadFr: str(raw.lead_fr),
    honestFr: str(raw.honest_fr),
    phraseFr: str(raw.phrase_fr),
    words: strings(raw.words),
  };
}

export function parseIntoxPage(raw: Json): RvIntoxPage {
  return {
    titleFr: str(raw.title_fr),
    datelineFr: str(raw.dateline_fr),
    lines: list(raw.lines, (row) => ({
      textFr: str(row.text_fr),
      wasFalse: Boolean(row.was_false),
      wrongFr: strOrNull(row.wrong_fr),
      answeredRight: Boolean(row.answered_right),
      learnerFr: strOrNull(row.learner_fr),
      fixedRight: bool(row.fixed_right),
    })),
    score: num(raw.score),
    total: num(raw.total) || 5,
    fixed: num(raw.fixed),
    phraseFr: str(raw.phrase_fr),
    words: strings(raw.words),
  };
}

export function parseRubriqueError(raw: unknown): RvRubriqueError | null {
  if (!isObject(raw) || !raw.code) return null;
  return { code: str(raw.code), key: strOrNull(raw.key), count: typeof raw.count === 'number' ? raw.count : null };
}

export function rubriqueBodyWire(body: RvRubriqueBody): Json {
  const wire: Json = { act: body.act };
  for (const field of ['key', 'value', 'words', 'parts', 'text', 'mode'] as const) {
    const value = (body as Json)[field];
    if (value !== undefined && value !== null) wire[field] = value;
  }
  return wire;
}

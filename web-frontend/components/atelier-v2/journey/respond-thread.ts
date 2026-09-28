/**
 * WP-89 «Le fil» — the respond step is one conversation.
 *
 * Pure: no React, no network, no storage. `RespondStepView` renders what these
 * functions return; `respond-thread.test.js` pins them.
 *
 *   the thread      `prompt.thread` when the server sends it (WP-89 contract),
 *                   else the client's own copy of this step's exchanges, kept
 *                   with the per-turn drafts so a reload keeps the column;
 *   the bubbles     character lines on the left, the learner's own lines on
 *                   the right, the current line last, the field under it;
 *   the tokens      one per planned exchange (`max_turns`), filled as each
 *                   passes — a sequence, never a ring;
 *   the verdict     only when the conversation closes (`next_turn === null`).
 *                   A continuing turn gets no band, no frown and no sound; a
 *                   slip on it is a proofreader's mark on the learner's line.
 */

import type {
  AttemptResult,
  JourneyCorrection,
  RespondPrompt,
  ThreadExchange,
} from '@/types/daily-journey';

import type { JourneyFeedback } from './journey-state';

// ---------------------------------------------------------------------------
// Local copy of the thread (servers that predate WP-89 send no `thread`)
// ---------------------------------------------------------------------------

/** One exchange as the client keeps it: which turn, and the line it answered. */
export type LocalExchange = ThreadExchange & {
  turn: number;
  /** The character's line this answer replied to, when the client saw it. */
  prompt_fr: string | null;
};

export type LocalThread = { exchanges: LocalExchange[] };

export const EMPTY_THREAD: LocalThread = { exchanges: [] };

/**
 * The draft key the thread is kept under. The recovery layer files drafts by
 * the segment before the first colon, so the thread is pruned together with
 * the step's drafts once the server completes the step.
 */
export function threadDraftKey(stepId: string): string {
  return `${stepId}:thread`;
}

/** A line longer than this is clipped in the local copy (never on screen live). */
const MAX_LINE_CHARS = 280;
/** Below the recovery layer's 2000-character draft cap, with room to spare. */
export const MAX_THREAD_CHARS = 1900;

function line(value: unknown): string {
  return typeof value === 'string' ? value.trim().slice(0, MAX_LINE_CHARS) : '';
}

/** Displayed words: trimmed, never clipped (clipping is for the stored copy). */
function words(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function correctionOf(value: unknown): JourneyCorrection | null {
  if (!value || typeof value !== 'object') return null;
  const raw = value as Record<string, unknown>;
  const span = line(raw.span_fr);
  const fixed = line(raw.corrected_fr);
  if (!span || !fixed) return null;
  return { span_fr: span, corrected_fr: fixed, note_native: line(raw.note_native) };
}

function exchangeOf(value: unknown): LocalExchange | null {
  if (!value || typeof value !== 'object') return null;
  const raw = value as Record<string, unknown>;
  const turn = raw.turn;
  if (typeof turn !== 'number' || !Number.isInteger(turn) || turn < 0 || turn > 32) return null;
  const learner = line(raw.learner_fr);
  if (!learner) return null;
  return {
    turn,
    prompt_fr: line(raw.prompt_fr) || null,
    learner_fr: learner,
    character_fr: line(raw.character_fr),
    correction: correctionOf(raw.correction),
  };
}

function sorted(exchanges: LocalExchange[]): LocalExchange[] {
  const byTurn = new Map<number, LocalExchange>();
  exchanges.forEach((exchange) => byTurn.set(exchange.turn, exchange));
  return Array.from(byTurn.values()).sort((a, b) => a.turn - b.turn);
}

/** Tolerant read of a stored thread: anything unreadable is an empty thread. */
export function parseLocalThread(raw: string | null | undefined): LocalThread {
  if (!raw) return EMPTY_THREAD;
  try {
    const parsed = JSON.parse(raw) as { v?: unknown; exchanges?: unknown };
    if (!parsed || parsed.v !== 1 || !Array.isArray(parsed.exchanges)) return EMPTY_THREAD;
    const exchanges = parsed.exchanges
      .map(exchangeOf)
      .filter((exchange): exchange is LocalExchange => exchange !== null);
    return exchanges.length ? { exchanges: sorted(exchanges) } : EMPTY_THREAD;
  } catch {
    return EMPTY_THREAD;
  }
}

/**
 * The stored form. When it would not fit the draft cap, the oldest exchanges
 * go first — the latest lines are the ones a reload needs.
 */
export function serializeLocalThread(thread: LocalThread): string {
  let exchanges = sorted(
    thread.exchanges.map(exchangeOf).filter((exchange): exchange is LocalExchange => exchange !== null),
  );
  let out = JSON.stringify({ v: 1, exchanges });
  while (out.length > MAX_THREAD_CHARS && exchanges.length > 1) {
    exchanges = exchanges.slice(1);
    out = JSON.stringify({ v: 1, exchanges });
  }
  return out.length > MAX_THREAD_CHARS ? JSON.stringify({ v: 1, exchanges: [] }) : out;
}

/** Add (or replace — a replayed result is the same turn) one exchange. */
export function recordExchange(thread: LocalThread, exchange: LocalExchange): LocalThread {
  const clean = exchangeOf(exchange);
  if (!clean) return thread;
  const current = thread.exchanges.find((item) => item.turn === clean.turn);
  if (
    current &&
    current.learner_fr === clean.learner_fr &&
    current.character_fr === clean.character_fr &&
    current.prompt_fr === (clean.prompt_fr ?? current.prompt_fr) &&
    JSON.stringify(current.correction) === JSON.stringify(clean.correction)
  ) {
    return thread;
  }
  const merged = { ...clean, prompt_fr: clean.prompt_fr ?? current?.prompt_fr ?? null };
  return { exchanges: sorted([...thread.exchanges.filter((item) => item.turn !== clean.turn), merged]) };
}

/** What the learner sent, captured at the tap (the snapshot moves on after). */
export type SentTurn = { turn: number; text: string; prompt_fr: string | null };

/**
 * The exchange a scored result settles, ready to keep. `null` when there is
 * nothing to keep (no words, or a result still being graded).
 */
export function exchangeFromResult(input: {
  result: AttemptResult;
  prompt: RespondPrompt;
  sent: SentTurn | null;
  /** The field's text, for a result the learner did not send in this mount (a replay). */
  fallbackText?: string;
}): LocalExchange | null {
  const { result, prompt, sent } = input;
  if (!result || result.pending || result.task_outcome === 'unscored') return null;
  const nextIndex = result.next_turn?.prompt?.turn_index;
  const turn =
    sent?.turn ?? (typeof nextIndex === 'number' ? Math.max(0, nextIndex - 1) : prompt.turn_index);
  return exchangeOf({
    turn,
    prompt_fr: sent?.prompt_fr ?? null,
    learner_fr: sent?.text ?? input.fallbackText ?? '',
    character_fr: result.character_reply_fr ?? '',
    correction: result.correction ?? null,
  });
}

// ---------------------------------------------------------------------------
// The column
// ---------------------------------------------------------------------------

export type CharacterBubble = {
  kind: 'character';
  key: string;
  turn: number;
  text: string;
  /** The character's reply to turn `turn` (rather than the line that opened it). */
  reply: boolean;
  /** The last character line: the one said beside the md face, as the headline. */
  latest: boolean;
};

export type LearnerBubble = {
  kind: 'learner';
  key: string;
  turn: number;
  text: string;
  correction: JourneyCorrection | null;
  /** Sent, and the reply is not back yet. */
  pending: boolean;
};

export type ThreadBubble = CharacterBubble | LearnerBubble;

/** The exchange on the wire or just answered, before it is kept. */
export type InFlightExchange = {
  turn: number;
  prompt_fr: string | null;
  learner_fr: string;
  character_fr: string | null;
  correction: JourneyCorrection | null;
};

/** Same line, whatever the spacing or the apostrophe the keyboard picked. */
export function sameLine(a: string | null | undefined, b: string | null | undefined): boolean {
  const fold = (value: string | null | undefined) =>
    String(value ?? '')
      .replace(/[‘’ʼ]/g, "'")
      .replace(/[  ]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .toLowerCase();
  return fold(a) === fold(b);
}

type Slot = {
  prompt_fr: string | null;
  learner_fr: string;
  character_fr: string;
  correction: JourneyCorrection | null;
  pending: boolean;
};

/**
 * The conversation, oldest first. The server's thread wins for the words; the
 * local copy supplies the lines the server does not repeat (the opening line)
 * and every exchange an older server never sends. The current line is last,
 * unless it is the reply already on screen.
 */
export function threadBubbles(input: {
  prompt: RespondPrompt;
  local?: LocalThread | null;
  inFlight?: InFlightExchange | null;
}): ThreadBubble[] {
  const { prompt } = input;
  const slots = new Map<number, Slot>();

  (Array.isArray(prompt.thread) ? prompt.thread : []).forEach((exchange, index) => {
    const learner = words(exchange?.learner_fr);
    if (!learner) return;
    slots.set(index, {
      prompt_fr: null,
      learner_fr: learner,
      character_fr: words(exchange.character_fr),
      correction: correctionOf(exchange.correction),
      pending: false,
    });
  });

  (input.local?.exchanges ?? []).forEach((exchange) => {
    const held = slots.get(exchange.turn);
    if (!held) {
      slots.set(exchange.turn, {
        prompt_fr: exchange.prompt_fr,
        learner_fr: exchange.learner_fr,
        character_fr: exchange.character_fr,
        correction: exchange.correction,
        pending: false,
      });
    } else if (!held.prompt_fr && exchange.prompt_fr) {
      held.prompt_fr = exchange.prompt_fr;
    }
  });

  const flight = input.inFlight;
  const flightLearner = words(flight?.learner_fr);
  if (flight && flightLearner) {
    const held = slots.get(flight.turn);
    if (!held) {
      const reply = words(flight.character_fr);
      slots.set(flight.turn, {
        prompt_fr: flight.prompt_fr,
        learner_fr: flightLearner,
        character_fr: reply,
        correction: correctionOf(flight.correction),
        pending: !reply,
      });
    } else if (!held.prompt_fr && flight.prompt_fr) {
      held.prompt_fr = flight.prompt_fr;
    }
  }

  const bubbles: ThreadBubble[] = [];
  let lastCharacter: string | null = null;
  const say = (text: string | null | undefined, turn: number, reply: boolean) => {
    const clean = words(text);
    if (!clean) return;
    // A reply that IS the next line is said once.
    if (lastCharacter !== null && sameLine(lastCharacter, clean)) return;
    bubbles.push({ kind: 'character', key: `c${turn}${reply ? 'r' : 'o'}`, turn, text: clean, reply, latest: false });
    lastCharacter = clean;
  };

  const turns = Array.from(slots.keys()).sort((a, b) => a - b);
  turns.forEach((turn) => {
    const slot = slots.get(turn) as Slot;
    say(slot.prompt_fr ?? (turn === prompt.turn_index ? prompt.character_line_fr : null), turn, false);
    bubbles.push({
      kind: 'learner',
      key: `l${turn}`,
      turn,
      text: slot.learner_fr,
      correction: slot.correction,
      pending: slot.pending,
    });
    lastCharacter = null;
    say(slot.character_fr, turn, true);
  });

  if (!slots.has(prompt.turn_index)) say(prompt.character_line_fr, prompt.turn_index, false);

  for (let index = bubbles.length - 1; index >= 0; index -= 1) {
    const bubble = bubbles[index];
    if (bubble.kind === 'character') {
      bubbles[index] = { ...bubble, latest: true };
      break;
    }
  }
  return bubbles;
}

// ---------------------------------------------------------------------------
// The exchange tokens
// ---------------------------------------------------------------------------

export type ExchangeProgress = {
  /** Planned exchanges: one token each. */
  total: number;
  /** Exchanges already played: the filled tokens. */
  played: number;
  /** The exchange the learner is in (1-based), for «Échange 2 sur 3». */
  position: number;
};

/**
 * `closed` is true once the closing turn is answered. A server that plays more
 * turns than it planned (a «relance») grows the sequence rather than overflowing it.
 */
export function exchangeProgress(prompt: RespondPrompt, closed: boolean): ExchangeProgress {
  const index = Math.max(0, Math.floor(Number(prompt.turn_index) || 0));
  const planned = Math.max(1, Math.floor(Number(prompt.max_turns) || 1));
  const total = Math.max(planned, index + 1);
  const played = Math.min(total, index + (closed ? 1 : 0));
  const position = Math.min(total, closed ? played : played + 1);
  return { total, played, position };
}

/** «Échange 2 sur 3» with the template from the copy table. */
export function exchangeLabel(template: string, progress: ExchangeProgress): string {
  return template.replace('{n}', String(progress.position)).replace('{total}', String(progress.total));
}

// ---------------------------------------------------------------------------
// Verdict only at the close
// ---------------------------------------------------------------------------

function answeredResult(feedback: JourneyFeedback): AttemptResult | null {
  return feedback.kind === 'graded' || feedback.kind === 'replying' ? feedback.result : null;
}

/** A turn the server answered with another turn: the conversation goes on. */
export function continuesConversation(feedback: JourneyFeedback): boolean {
  return Boolean(answeredResult(feedback)?.next_turn);
}

/** The closing turn is answered: the one place the verdict is shown. */
export function closesConversation(feedback: JourneyFeedback): boolean {
  const result = answeredResult(feedback);
  return Boolean(result && !result.next_turn);
}

// ---------------------------------------------------------------------------
// The proofreader's mark
// ---------------------------------------------------------------------------

export type MarkedLine = { before: string; mark: string; after: string };

/**
 * Where `span_fr` sits in the learner's line. Exact first, then ignoring case
 * and the apostrophe the keyboard chose. `null` when the span is not there.
 */
export function markSpan(text: string, span: string | null | undefined): MarkedLine | null {
  const needle = String(span ?? '').trim();
  if (!needle || !text) return null;
  let at = text.indexOf(needle);
  if (at === -1) {
    const fold = (value: string) => value.replace(/[‘’ʼ]/g, "'").toLowerCase();
    const haystack = fold(text);
    if (haystack.length === text.length) at = haystack.indexOf(fold(needle));
  }
  if (at === -1) return null;
  return {
    before: text.slice(0, at),
    mark: text.slice(at, at + needle.length),
    after: text.slice(at + needle.length),
  };
}

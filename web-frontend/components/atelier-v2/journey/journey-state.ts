/**
 * Atelier V2 daily journey — presentation-independent state (WP-07 functional).
 *
 * Everything in this file is a pure function over the frozen wire contract
 * (`@/types/daily-journey`). It holds no React, no transport and no styling, so
 * the later Claude-Design renderer can reuse it byte-for-byte and the node test
 * harness can exercise every state without a DOM.
 *
 * The two unions below are what a renderer switches on:
 *
 *   `JourneyPhase`    — where the day is (loading / offer / preparing / …).
 *   `JourneyFeedback` — what just happened to the learner's answer.
 *
 * A transport or provider failure is deliberately NOT expressible as a wrong
 * answer: `feedback.kind === 'graded'` is only ever produced from a real
 * `AttemptResult` the server scored.
 */

import type {
  AssistanceLevel,
  AttemptInput,
  AttemptResult,
  ControlLanguage,
  DayShape,
  JourneyErrorCode,
  JourneyErrorDetail,
  JourneyRecap,
  JourneySnapshot,
  PublicStep,
  RecallFormat,
  RecallPrompt,
  ResolutionPrompt,
  RespondLetter,
  RespondPrompt,
  ScenarioDescriptor,
  ScenePrompt,
  StepKind,
  TaskOutcome,
  TodayEnvelope,
} from '@/types/daily-journey';

// ---------------------------------------------------------------------------
// Phase
// ---------------------------------------------------------------------------

export type JourneyPhase =
  | { kind: 'loading' }
  /** `/today` itself failed. Not a journey state: the day is simply unread. */
  | { kind: 'load_failed'; message: string }
  /** Capability off (`enabled === false`, or a 403 `journey_disabled`). */
  | { kind: 'disabled'; envelope: TodayEnvelope | null }
  /** Enabled, nothing open: today's scenario can be started (or nothing is offered). */
  | { kind: 'offer'; envelope: TodayEnvelope; scenario: ScenarioDescriptor | null }
  | { kind: 'preparing'; journey: JourneySnapshot; retryAfterSeconds: number; retryAllowed: boolean }
  | {
      kind: 'unavailable';
      journey: JourneySnapshot;
      retryAllowed: boolean;
      retryAfterSeconds: number;
    }
  | { kind: 'session'; journey: JourneySnapshot; step: PublicStep | null }
  /**
   * Every planned step is resolved, the server has not been told to finish, and
   * there is therefore no step to render and no recap to read. It is a real
   * server state — an `advance` that returned `current_step_id: null` and a
   * `finish` that has not succeeded yet (or was refused with a stale revision) —
   * so it gets its own kind rather than a `session` with a null step, which
   * renders as an empty screen with no action.
   */
  | { kind: 'awaiting_finish'; journey: JourneySnapshot }
  | { kind: 'paused'; journey: JourneySnapshot; step: PublicStep | null }
  | { kind: 'finished'; journey: JourneySnapshot; recap: JourneyRecap | null };

export type PhaseKind = JourneyPhase['kind'];

// ---------------------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------------------

/**
 * How the server's `task_outcome` + `assistance_level` read to a learner.
 * `unscored` is grading that did not happen, never "you were wrong".
 */
export type AttemptVerdict = 'correct' | 'supported' | 'wrong' | 'unscored';

/**
 * Provenance of a character line, so an authored reply is not sold as a live one.
 *
 * Deliberately NOT the wire's `ReplySource`: this adds `unknown` for a server
 * built before contract revision 2, which sends no `reply_source` at all. The
 * name differs so the two can never be imported interchangeably.
 */
export type ReplyProvenance = 'authored' | 'model' | 'none' | 'unknown';

export type JourneyFeedback =
  | { kind: 'idle' }
  /** A request is in flight. The primary action must be disabled while this holds. */
  | { kind: 'submitting' }
  /** 202 `processing`: the identical request is being replayed with the same key. */
  | { kind: 'retrying'; attempt: number; afterSeconds: number }
  /** 422 `empty_answer` (or the client-side guard). Never a wrong-answer card. */
  | { kind: 'empty'; message: string }
  | {
      kind: 'graded';
      verdict: Exclude<AttemptVerdict, 'unscored'>;
      result: AttemptResult;
      replySource: ReplyProvenance;
    }
  /**
   * WP-76: the same graded result, staged. The character's reply is typing in
   * on the respond step and the verdict card is held back until it has — words
   * first, judgement second. Always followed by `graded` for the same result
   * (`lib/journey-reply-reveal.ts`); inputs stay locked exactly as in `graded`.
   */
  | {
      kind: 'replying';
      verdict: Exclude<AttemptVerdict, 'unscored'>;
      result: AttemptResult;
      replySource: ReplyProvenance;
    }
  /** `pending: true` — retryable grading, `task_outcome: 'unscored'`. */
  | { kind: 'unscored'; message: string; result: AttemptResult }
  /** A 409 that was refetched and reconciled. The learner lost nothing. */
  | { kind: 'reconciled'; code: JourneyErrorCode; message: string }
  /** Transport/provider failure. Retryable, and explicitly not a verdict. */
  | { kind: 'error'; message: string; retryable: boolean };

export type FeedbackKind = JourneyFeedback['kind'];

// ---------------------------------------------------------------------------
// Envelope / snapshot readers
// ---------------------------------------------------------------------------

export function phaseFromEnvelope(envelope: TodayEnvelope | null): JourneyPhase {
  if (!envelope) return { kind: 'loading' };
  if (!envelope.enabled) return { kind: 'disabled', envelope };
  if (!envelope.journey) {
    return { kind: 'offer', envelope, scenario: envelope.available ?? null };
  }
  return phaseFromJourney(envelope.journey, envelope);
}

export function phaseFromJourney(
  journey: JourneySnapshot,
  envelope: TodayEnvelope | null = null,
): JourneyPhase {
  const step = currentStepOf(journey);
  switch (journey.status) {
    case 'preparing':
      return {
        kind: 'preparing',
        journey,
        retryAfterSeconds: journey.retry?.after_seconds ?? 3,
        // WP-69: the server says whether POST /retry may run. A live claim
        // answers 202 without generating, so the button can always ask.
        retryAllowed: journey.retry?.allowed ?? false,
      };
    case 'unavailable':
      return {
        kind: 'unavailable',
        journey,
        retryAllowed: journey.retry?.allowed ?? false,
        retryAfterSeconds: journey.retry?.after_seconds ?? 30,
      };
    case 'paused':
      return { kind: 'paused', journey, step };
    case 'completed':
    case 'ended_early':
      return { kind: 'finished', journey, recap: journey.recap ?? null };
    case 'active':
    default:
      if (envelope && !envelope.enabled) return { kind: 'disabled', envelope };
      if (journeyAwaitsFinish(journey)) return { kind: 'awaiting_finish', journey };
      return { kind: 'session', journey, step };
  }
}

/**
 * "Every step is done, the day is not finished yet."
 *
 * The server answers an `advance` off the last step with an `active` journey
 * whose `current_step_id` is `null`; it stays in that state until a `finish`
 * succeeds. There is nothing to answer and no recap to show, so the only
 * honest offer is to finish — which is exactly what a `finish` refused with a
 * stale `expected_revision` leaves behind, and what used to render as an empty
 * "Step 3 of 3" with no button.
 *
 * A malformed `current_step_id` that simply points at no known step is NOT this
 * state: the plan still says a step is open, and that is a different problem.
 */
export function journeyAwaitsFinish(journey: JourneySnapshot | null): boolean {
  if (!journey || journey.status !== 'active') return false;
  return journey.current_step_id === null && journey.steps.length > 0;
}

export function currentStepOf(journey: JourneySnapshot | null): PublicStep | null {
  if (!journey?.current_step_id) return null;
  return journey.steps.find((step) => step.id === journey.current_step_id) ?? null;
}

/** The journey the shell should render, whatever produced it. */
export function journeyOfPhase(phase: JourneyPhase): JourneySnapshot | null {
  switch (phase.kind) {
    case 'preparing':
    case 'unavailable':
    case 'session':
    case 'awaiting_finish':
    case 'paused':
    case 'finished':
      return phase.journey;
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Progress — real plan data only, never a demo value
// ---------------------------------------------------------------------------

export type JourneyProgress = {
  /** Steps the server marked `completed` or `skipped`. */
  done: number;
  total: number;
  /** 0–100, computed from the plan; 0 when there is no plan yet. */
  percent: number;
  /** Sum of `estimated_seconds` for steps not yet resolved. `null` when unknown. */
  remainingSeconds: number | null;
  /** The plan's own estimate for the whole journey. `null` when unknown. */
  plannedSeconds: number | null;
};

/**
 * Join the parts of a meta line with the design's separator, skipping the ones
 * that are not there.
 *
 * The story-engine `available` descriptor ships `location_name` (and the other
 * placement fields) as empty strings, so an unconditional template produced
 * "Today · " with nothing after it (WP-20 D-7). A separator only ever appears
 * between two real parts.
 */
export function joinMeta(...parts: Array<string | null | undefined>): string {
  return parts
    .map((part) => (typeof part === 'string' ? part.trim() : ''))
    .filter((part) => part.length > 0)
    .join(' · ');
}

export function journeyProgress(journey: JourneySnapshot | null): JourneyProgress {
  if (!journey || journey.steps.length === 0) {
    return {
      done: 0,
      total: 0,
      percent: 0,
      remainingSeconds: null,
      plannedSeconds:
        journey && journey.estimated_active_seconds > 0
          ? journey.estimated_active_seconds
          : null,
    };
  }
  const total = journey.steps.length;
  const done = journey.steps.filter(
    (step) => step.status === 'completed' || step.status === 'skipped',
  ).length;
  const remainingSeconds = journey.steps
    .filter((step) => step.status === 'pending' || step.status === 'active')
    .reduce((sum, step) => sum + Math.max(0, Number(step.estimated_seconds) || 0), 0);
  return {
    done,
    total,
    percent: Math.round((done / total) * 100),
    remainingSeconds,
    plannedSeconds:
      journey.estimated_active_seconds > 0 ? journey.estimated_active_seconds : null,
  };
}

/**
 * "about 4 min" / "about 40 s" from a real number of seconds.
 * `null` in, `null` out — the caller must then say so rather than print a guess.
 */
export function formatDuration(
  seconds: number | null | undefined,
  language: ControlLanguage = 'en',
): string | null {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds <= 0) {
    return null;
  }
  if (seconds < 90) {
    const value = Math.round(seconds);
    return language === 'fr' ? `${value} s` : `${value} s`;
  }
  const minutes = Math.round(seconds / 60);
  if (language === 'de') return `${minutes} Min.`;
  if (language === 'fr') return `${minutes} min`;
  return `${minutes} min`;
}

// ---------------------------------------------------------------------------
// Verdicts
// ---------------------------------------------------------------------------

export function attemptVerdict(
  outcome: TaskOutcome,
  assistance: AssistanceLevel,
): AttemptVerdict {
  if (outcome === 'unscored') return 'unscored';
  if (outcome === 'not_yet') return 'wrong';
  if (outcome === 'partially_met') return 'supported';
  return assistance === 'none' ? 'correct' : 'supported';
}

/**
 * `AttemptResult.reply_source` was ratified additively as contract revision 2 on
 * 2026-09-05. It is read structurally rather than off the type, because a server
 * built before that revision omits the field entirely — that case must resolve to
 * `unknown`, which the renderer must not dress up as either a live or an authored
 * reply. Only an explicit `authored` is labelled.
 */
export function replySourceOf(result: AttemptResult | null | undefined): ReplyProvenance {
  const raw = (result as { reply_source?: unknown } | null | undefined)?.reply_source;
  if (raw === 'authored' || raw === 'model' || raw === 'none') return raw;
  return 'unknown';
}

export function feedbackFromAttempt(result: AttemptResult): JourneyFeedback {
  if (result.pending || result.task_outcome === 'unscored') {
    return {
      kind: 'unscored',
      message: 'still_grading',
      result,
    };
  }
  const verdict = attemptVerdict(result.task_outcome, result.assistance_level);
  if (verdict === 'unscored') {
    return { kind: 'unscored', message: 'still_grading', result };
  }
  return { kind: 'graded', verdict, result, replySource: replySourceOf(result) };
}

/** WP-76: the staged twin of a `graded` feedback (reply on screen, verdict held). */
export function replyingOf(feedback: JourneyFeedback): JourneyFeedback {
  return feedback.kind === 'graded' ? { ...feedback, kind: 'replying' } : feedback;
}

/** A turn that is answered — graded, or staged on its way to graded. */
export function feedbackIsAnswered(feedback: JourneyFeedback): boolean {
  return feedback.kind === 'graded' || feedback.kind === 'replying';
}

// ---------------------------------------------------------------------------
// WP-76 — the header counts steps, never a clock
// ---------------------------------------------------------------------------

/**
 * The 1-based position of the step actually on screen, or null when there is
 * none. Counting finished steps instead advances the header the instant an
 * answer is graded, while the graded step is still the one being read.
 */
export function stepPositionOnScreen(journey: JourneySnapshot | null): number | null {
  if (!journey?.current_step_id) return null;
  const index = journey.steps.findIndex((step) => step.id === journey.current_step_id);
  return index < 0 ? null : index + 1;
}

/**
 * «Étape 2 sur 3» and nothing else.
 *
 * The header used to append the plan's remaining estimate («3 min restant»).
 * That number drops by a whole step's estimate the moment a turn is graded, so
 * after a 12 s wait for the reply it read «45 s restant»: the server's wait,
 * billed to the learner. A countdown also adds pressure while someone is
 * composing French and helps no decision mid-scene. The estimate stays where it
 * helps choose — on the Today card, before starting — and the header shows
 * where the learner is, which nothing but the learner's own «Continuer» moves.
 */
export function journeyHeaderCaption(
  journey: JourneySnapshot | null,
  stepOf: (position: number, total: number) => string,
): string | undefined {
  if (!journey || journey.steps.length === 0) return undefined;
  const total = journey.steps.length;
  const done = journey.steps.filter(
    (step) => step.status === 'completed' || step.status === 'skipped',
  ).length;
  const position = stepPositionOnScreen(journey) ?? Math.min(done + 1, total);
  return stepOf(position, total);
}

// ---------------------------------------------------------------------------
// Contract-state detection
// ---------------------------------------------------------------------------

/**
 * A structured `{"detail": {...}}` body that arrived on a **successful** HTTP
 * status. FastAPI raises `HTTPException(202, detail={...})` for `processing`,
 * and axios resolves any 2xx, so a mutation can legitimately resolve with an
 * error-shaped payload instead of its declared response model.
 */
export function detailOfPayload(payload: unknown): JourneyErrorDetail | null {
  const detail = (payload as { detail?: unknown } | null | undefined)?.detail;
  if (detail && typeof detail === 'object' && typeof (detail as any).code === 'string') {
    return detail as JourneyErrorDetail;
  }
  return null;
}

/** `true` when a resolved payload is really a contract signal, not a result. */
export function payloadIsDetail(payload: unknown): boolean {
  return detailOfPayload(payload) !== null;
}

/** Codes that mean "your view of the journey is stale; refetch and reconcile". */
export const RECONCILE_CODES: JourneyErrorCode[] = [
  'journey_version_conflict',
  'idempotency_conflict',
  'step_not_active',
  'journey_not_active',
];

export function isReconcileCode(code: JourneyErrorCode | null): boolean {
  return code !== null && RECONCILE_CODES.includes(code);
}

// ---------------------------------------------------------------------------
// Step helpers
// ---------------------------------------------------------------------------

export function stepKindOf(step: PublicStep | null): StepKind | null {
  return step ? step.kind : null;
}

/** Voice is offered only when the server says the step accepts it. Text always is. */
export function voiceOffered(prompt: RespondPrompt | null | undefined): boolean {
  return Boolean(prompt?.input_modes?.includes('voice'));
}

export function textOffered(prompt: RespondPrompt | null | undefined): boolean {
  // The contract guarantees text; treat a malformed payload as text-only rather
  // than locking the learner out of their own turn.
  return !prompt || prompt.input_modes.length === 0 || prompt.input_modes.includes('text');
}

/** A blank answer is refused before it can reach the server and cost a turn. */
export function answerIsBlank(text: string): boolean {
  return text.replace(/\s+/g, '').length === 0;
}

// ---------------------------------------------------------------------------
// WP-66 — day shapes and the three formats brought in from the Séance
// ---------------------------------------------------------------------------

/**
 * Which kind of day this is.
 *
 * A server built before WP-66 sends no `day_shape` at all, and that is a
 * standard day — which is exactly what it was. An unknown shape is returned
 * verbatim rather than flattened, so a client can *report* a day it does not
 * have chrome for while still rendering the steps it was sent.
 */
export function dayShapeOf(journey: JourneySnapshot | null): DayShape {
  const raw = journey?.day_shape;
  return typeof raw === 'string' && raw.trim() ? raw : 'standard';
}

/**
 * How one recall format is answered.
 *
 * The three formats WP-66 brought in reuse the renderers that already exist,
 * so they reuse their input modes too: this is the one table that says so, and
 * both the renderer and the request builder read it. A format this client has
 * never heard of is treated as written text, which is the mode every server
 * accepts for any step.
 */
export function recallAnswerMode(
  format: RecallFormat | string,
): 'choice' | 'tiles' | 'text' {
  if (format === 'choice' || format === 'classify' || format === 'listen_tap') return 'choice';
  // WP-86: «Qui a dit ça ?» is a pick among faces.
  if (format === 'who_said') return 'choice';
  // WP-78: an unscramble is tiles; a matching item sends the pairs it made,
  // in order, as consecutive `[fr, native]` tile ids.
  if (format === 'tiles' || format === 'word_bank' || format === 'unscramble') return 'tiles';
  if (format === 'match_pairs') return 'tiles';
  return 'text';
}

/** Is this format answered by picking a chip/option rather than by writing? */
export function recallIsPicked(format: RecallFormat | string): boolean {
  return recallAnswerMode(format) !== 'text';
}

/**
 * The attempt body for a recall step, or `null` when nothing was answered.
 *
 * Keeping this beside `recallAnswerMode` is the point: a renderer that adds a
 * format without teaching this function how it is sent would post a blank
 * answer, and a blank answer costs the learner a turn.
 */
export function recallAttempt(
  prompt: RecallPrompt,
  answer: { choice: string | null; tiles: string[]; text: string },
): AttemptInput | null {
  switch (recallAnswerMode(prompt.task_type)) {
    case 'choice':
      return answer.choice ? { mode: 'choice', option_id: answer.choice } : null;
    case 'tiles':
      return answer.tiles.length ? { mode: 'tiles', tile_ids: answer.tiles } : null;
    default:
      return answerIsBlank(answer.text) ? null : { mode: 'text', text: answer.text };
  }
}

/**
 * A word bank shows chips the answer does not use; tiles show only the answer's
 * own words. The learner has to be able to tell, so the renderer says so —
 * and only when it is true of *this* step.
 */
export function wordBankHasSpareChips(prompt: RecallPrompt): boolean {
  return prompt.task_type === 'word_bank' && prompt.options.length > 0;
}

/** «Écouter d'abord», dealt by the planner rather than chosen by the learner. */
export function sceneOpensOnAudio(prompt: ScenePrompt | null | undefined): boolean {
  return Boolean(prompt?.listen_first && prompt?.audio_available);
}

/**
 * The Courrier letter this respond step answers, or `null`.
 *
 * Half a letter is never shown. A letter block with no sender, no body or no
 * objective would replace the character's line and the day's objective with
 * blanks — the learner would be told to answer nothing, in a scene that had
 * stopped talking. When any of the three is missing the step falls back to the
 * ordinary respond chrome it was built from, which is always complete.
 *
 * This is also the one place that reads `prompt.letter`, so a server that sends
 * a letter this client cannot render is a standard turn rather than an empty
 * page.
 */
export function letterOf(prompt: RespondPrompt | null | undefined): RespondLetter | null {
  const letter = prompt?.letter ?? null;
  if (!letter) return null;
  const name = (letter.correspondent_name ?? '').trim();
  const body = (letter.body_fr ?? '').trim();
  const objective = (letter.objective_native ?? '').trim();
  if (!name || !body || !objective) return null;
  return letter;
}

/**
 * The register verdict to print under the ending, or `null`.
 *
 * `null` covers two different silences and deliberately flattens them, because
 * they render the same way: a server that predates WP-66, and a conversation
 * where register was *not evaluated*. Neither is a pass and neither is a
 * failure, so neither is a line.
 *
 * Half a verdict is never shown: without the French line there is nothing to
 * explain, so the reason is dropped with it.
 */
export function registerNoteOf(
  prompt: ResolutionPrompt | null | undefined,
): { lineFr: string; reasonNative: string | null } | null {
  const lineFr = (prompt?.register_note_fr ?? '').trim();
  if (!lineFr) return null;
  const reason = (prompt?.register_reason_native ?? '').trim();
  return { lineFr, reasonNative: reason || null };
}

/** The chapter recap a «jour de reprise» ends on, or `null`. */
export function chapterRecapOf(
  prompt: ResolutionPrompt | null | undefined,
): string | null {
  return (prompt?.chapter_recap_fr ?? '').trim() || null;
}

// ---------------------------------------------------------------------------
// Recap
// ---------------------------------------------------------------------------

export type RecapView = {
  partial: boolean;
  outcome: TaskOutcome;
  /** At most ONE headline: the correction focus, or nothing. */
  headline: { labelFr: string; reasonNative: string } | null;
  practiced: JourneyRecap['practiced_targets'];
  capabilities: JourneyRecap['capability_evidence'];
  collectibleIds: string[];
  storyCallbackFr: string | null;
  /** `null` means the server did not measure it. Render the absence, not a number. */
  activeSeconds: number | null;
};

export function recapView(recap: JourneyRecap | null): RecapView | null {
  if (!recap) return null;
  return {
    partial: recap.completion_kind === 'early',
    outcome: recap.objective_outcome,
    headline: recap.next_focus
      ? {
          labelFr: recap.next_focus.target.label_fr,
          reasonNative: recap.next_focus.reason_native,
        }
      : null,
    practiced: recap.practiced_targets,
    capabilities: recap.capability_evidence,
    collectibleIds: recap.collectible_ids,
    storyCallbackFr: recap.story_outcome?.callback_fr ?? null,
    activeSeconds:
      typeof recap.active_seconds === 'number' && recap.active_seconds > 0
        ? recap.active_seconds
        : null,
  };
}

// ---------------------------------------------------------------------------
// WP-87 — the resolution waits honestly for the story lane
// ---------------------------------------------------------------------------

/** How often the resolution step re-reads the journey while its ending is written. */
export const STORY_POLL_MS = 1_000;
/**
 * Bounded: the server heals a dead lane with the authored ending after ~15 s
 * unclaimed or ~90 s running, so two minutes of polls always see an ending.
 */
export const STORY_POLL_LIMIT = 120;

/** Is this step a resolution whose ending the story lane is still writing? */
export function resolutionAwaitsStory(step: PublicStep | null | undefined): boolean {
  return Boolean(step && step.kind === 'resolution' && step.prompt.story_pending === true);
}

/** The id of the journey to poll, or `null` when nothing is being written. */
export function storyPollTarget(journey: JourneySnapshot | null | undefined): string | null {
  if (!journey || (journey.status !== 'active' && journey.status !== 'paused')) return null;
  return resolutionAwaitsStory(currentStepOf(journey)) ? journey.id : null;
}

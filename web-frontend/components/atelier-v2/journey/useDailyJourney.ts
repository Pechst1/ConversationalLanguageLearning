/**
 * `useDailyJourney` — the whole daily-journey controller (WP-07 functional).
 *
 * All logic, zero presentation. Components receive `state` and `actions` as
 * props and contain no transport, so the Claude-Design renderer that replaces
 * them later reuses this hook unchanged.
 *
 * Contract states handled explicitly, each with a distinct renderable state:
 *
 *   202 `processing`          reuse the SAME mutation id, wait `retry_after_seconds`
 *   409 `journey_version_conflict`  refetch via `refresh_href` and reconcile
 *   409 `idempotency_conflict` / `step_not_active` / `journey_not_active`  refetch
 *   422 `empty_answer`        inline "write something first", not a wrong answer
 *   403 `journey_disabled`    fall through to legacy behaviour
 *   `pending: true`           retryable "still grading", `task_outcome: unscored`
 *
 * A transport or provider failure can never surface as a red wrong-answer card:
 * `feedback.kind === 'graded'` is only ever built from a real `AttemptResult`.
 *
 * Interruption recovery (WP-10) is wired in here rather than in the page, so
 * the dependency graph stays acyclic and `pages/atelier.tsx` is unchanged:
 * every mutation is recorded before it is sent, marked once it leaves the
 * device, and settled when the server answers. A mutation that was in flight
 * when the app went away is re-sent under its ORIGINAL key, so the server
 * replies with the receipt it already stored instead of recording a second
 * attempt. Nothing here ever invents a grade or a completion.
 *
 * One subtlety this file exists to absorb: FastAPI raises
 * `HTTPException(202, detail={...})` for `processing`, and axios resolves every
 * 2xx, so a mutation can *resolve* with an error-shaped body instead of its
 * declared model. Every call goes through `unwrap`, which checks for that.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import apiService from '@/services/api';
import dailyJourneyService, {
  isJourneyDisabled,
  journeyErrorDetail,
  resolveTimezone,
} from '@/services/daily-journey';
import type {
  AttemptInput,
  AttemptResult,
  ControlLanguage,
  HelpKind,
  HelpResult,
  InputMode,
  JourneyErrorDetail,
  JourneySnapshot,
  PublicStep,
  RespondPrompt,
  TodayEnvelope,
} from '@/types/daily-journey';
import { createAudioMediaRecorder, recordedAudioBlob } from '@/lib/audio-recording';
import useJourneyRecovery, {
  type JourneyRecoveryController,
} from '@/lib/useJourneyRecovery';
import type { PendingPlan, ReplayableKind } from '@/lib/journey-recovery';

import {
  answerIsBlank,
  currentStepOf,
  feedbackFromAttempt,
  journeyAwaitsFinish,
  journeyProgress,
  phaseFromEnvelope,
  phaseFromJourney,
  type JourneyFeedback,
  type JourneyPhase,
  type JourneyProgress,
} from './journey-state';
import {
  createMutationKeyring,
  createRequestGate,
  planFailure,
  runMutation,
  type MutationOutcome,
} from './journey-requests';

/** Bounded auto-poll of a `preparing` journey before a manual "check again". */
const PREPARING_POLL_LIMIT = 8;
/** Under this many bytes nothing was actually captured by the microphone. */
const EMPTY_RECORDING_BYTES = 1200;

export type VoiceState =
  | { kind: 'idle' }
  | { kind: 'unsupported' }
  | { kind: 'recording' }
  | { kind: 'transcribing' }
  | { kind: 'failed'; message: string };

export type DailyJourneyActions = {
  /** Re-read `/today`. Safe, never creates or pays for generation. */
  refresh: () => Promise<void>;
  /** `POST /daily-journeys`. Idempotent per day. */
  start: () => Promise<void>;
  /** `POST …/retry` for a preparing/unavailable journey; the id is reused. */
  retryGeneration: () => Promise<void>;
  /** Reveal help. Assistance is recorded server-side before the content returns. */
  requestHelp: (helpKind: HelpKind) => Promise<void>;
  /** Submit an answer. A blank text/voice answer is refused before it is sent. */
  submitAnswer: (input: AttemptInput) => Promise<void>;
  /** Resubmit the identical body with the identical mutation id. */
  retryLastAnswer: () => Promise<void>;
  /** The single forward action: next turn, next step, or finish. */
  continueJourney: () => Promise<void>;
  pause: () => Promise<void>;
  resume: () => Promise<void>;
  finish: (kind: 'complete' | 'early') => Promise<void>;
  /** Dismiss a feedback card without moving on. */
  clearFeedback: () => void;
  /** Start/stop microphone capture for the current respond step. */
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  resetVoice: () => void;
};

export type DailyJourneyController = {
  phase: JourneyPhase;
  feedback: JourneyFeedback;
  envelope: TodayEnvelope | null;
  journey: JourneySnapshot | null;
  step: PublicStep | null;
  respondPrompt: RespondPrompt | null;
  controlLanguage: ControlLanguage;
  legacyResume: { href: string; session_id: string } | null;
  progress: JourneyProgress;
  /** A mutation is in flight; the primary action must be disabled. */
  busy: boolean;
  /** The most recent revealed help for the current step, or `null`. */
  help: HelpResult | null;
  voice: VoiceState;
  /**
   * Interruption recovery (WP-10): the honest connection state, the learner's
   * persisted drafts, and the reading position. Presentation reads it; it never
   * produces a grade.
   */
  recovery: JourneyRecoveryController;
  actions: DailyJourneyActions;
};

/**
 * What a mutation is, for the recovery record. The kind is what decides whether
 * an interrupted request may ever be replayed, so it is stated at the call site
 * rather than guessed from the intent string.
 */
type MutationMeta = {
  kind: ReplayableKind;
  stepId?: string | null;
  body?: unknown;
};

/**
 * Recover the exact request behind one of this controller's `attempt` keys.
 *
 * The key is `attempt:{journeyId}:{stepId}:{revision}:{JSON}` and the JSON tail
 * can itself contain colons, so only the first four segments are split off.
 * Journey and step ids are server-issued UUIDs and carry none.
 */
export function parseAttemptIntent(intent: string): {
  journeyId: string;
  stepId: string;
  expectedRevision: number;
  input: AttemptInput;
} | null {
  if (!intent || !intent.startsWith('attempt:')) return null;
  const parts = intent.split(':');
  if (parts.length < 5) return null;
  const [, journeyId, stepId, revision] = parts;
  const expectedRevision = Number(revision);
  if (!journeyId || !stepId || !Number.isInteger(expectedRevision)) return null;
  const encoded = intent.slice(`attempt:${journeyId}:${stepId}:${revision}:`.length);
  try {
    const input = JSON.parse(encoded) as AttemptInput;
    if (!input || typeof input !== 'object' || typeof input.mode !== 'string') return null;
    return { journeyId, stepId, expectedRevision, input };
  } catch {
    // A key we cannot read is never re-sent on the learner's behalf.
    return null;
  }
}

function errorMessage(error: unknown): string {
  const detail = journeyErrorDetail(error);
  if (detail?.message) return detail.message;
  return '';
}

export type UseDailyJourneyOptions = {
  /** Skip every request (unauthenticated pages, disabled routes). */
  enabled?: boolean;
  /** Preferred modality for a *new* journey. The server still decides. */
  preferredInputMode?: InputMode;
  /** Called once a journey reaches `completed` / `ended_early`. */
  onFinished?: (journey: JourneySnapshot) => void;
  /** Called when the server answers 403 `journey_disabled`. */
  onDisabled?: () => void;
};

export function useDailyJourney(
  options: UseDailyJourneyOptions = {},
): DailyJourneyController {
  const { enabled = true, preferredInputMode = 'text', onFinished, onDisabled } = options;

  const [envelope, setEnvelope] = useState<TodayEnvelope | null>(null);
  const [journey, setJourney] = useState<JourneySnapshot | null>(null);
  const [phase, setPhase] = useState<JourneyPhase>({ kind: 'loading' });
  const [feedback, setFeedback] = useState<JourneyFeedback>({ kind: 'idle' });
  const [help, setHelp] = useState<HelpResult | null>(null);
  const [voice, setVoice] = useState<VoiceState>({ kind: 'idle' });
  const [busy, setBusy] = useState(false);

  // WP-10, called here rather than from `pages/atelier.tsx`: the page keeps no
  // journey knowledge and the dependency graph stays acyclic.
  const recovery = useJourneyRecovery({ envelope, journey, busy });
  const { clearReplayPlan, replayPlan } = recovery;

  const mountedRef = useRef(true);
  /** Has the capability read ever produced an answer? Silence is not a refusal. */
  const capabilityReadRef = useRef(false);
  /** Stable idempotency keys: one per logical intent, reused on every replay. */
  const keyringRef = useRef(createMutationKeyring());
  /** In-flight promises by intent: a double tap awaits the first request. */
  const gateRef = useRef(createRequestGate());
  const lastAttemptRef = useRef<{
    journeyId: string;
    stepId: string;
    expectedRevision: number;
    input: AttemptInput;
  } | null>(null);
  /**
   * The freshest snapshot this controller has applied.
   *
   * Every mutation carries an `expected_revision`, and a callback that closed
   * over `journey` still sees the revision from the render it was built in.
   * That is fine while one tap makes one request, but `continueJourney` makes
   * two: the `finish` it issues immediately after an `advance` would otherwise
   * send the PRE-advance revision, be refused with 409
   * `journey_version_conflict`, and leave the day active with no step and no
   * recap. Actions therefore read the current snapshot here, not through the
   * closure, and `continueJourney` passes the snapshot `advance` returned.
   */
  const journeyRef = useRef<JourneySnapshot | null>(null);
  const preparingPollsRef = useRef(0);
  const finishedNotifiedRef = useRef<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const submitRef = useRef<(input: AttemptInput) => Promise<void>>(async () => {});
  /**
   * The recovery controller is a fresh object every render. Holding the latest
   * one in a ref keeps `unwrap` — and therefore every action built on it —
   * stable, so recording a mutation costs no re-render churn.
   */
  const recoveryRef = useRef(recovery);
  useEffect(() => {
    recoveryRef.current = recovery;
  });

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      try {
        recorderRef.current?.stop();
      } catch {
        // A recorder that was already stopped is not an error worth surfacing.
      }
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  // -----------------------------------------------------------------------
  // Idempotency
  // -----------------------------------------------------------------------

  const unwrap = useCallback(
    async <T,>(
      intent: string,
      meta: MutationMeta,
      invoke: (id: string) => Promise<T>,
    ): Promise<MutationOutcome<T>> => {
      // The key is minted once per intent and reused for every replay, which
      // is what turns a duplicate submit into a replay instead of a second
      // learning record.
      const id = keyringRef.current.idFor(intent);
      // Recorded BEFORE anything can leave the device, so a kill between the
      // tap and the answer is recoverable. Text only — never audio, never a
      // token, never a transcript log (contract revision 1).
      recoveryRef.current.beginMutation({
        intent,
        mutationId: id,
        kind: meta.kind,
        stepId: meta.stepId ?? null,
        body: meta.body ?? null,
      });
      try {
        return await runMutation<T>({
          mutationId: id,
          invoke: (sent) => {
            // Only a request that actually went out is ever replayed.
            recoveryRef.current.markDispatched();
            return invoke(sent);
          },
          onRetry: (attempt, afterSeconds) => {
            if (mountedRef.current) setFeedback({ kind: 'retrying', attempt, afterSeconds });
          },
        });
      } finally {
        // The server answered, one way or the other: nothing left to replay.
        recoveryRef.current.settleMutation();
      }
    },
    [],
  );

  /** Serialize one intent: a double tap awaits the first request, never a second. */
  const once = useCallback(
    (intent: string, run: () => Promise<void>): Promise<void> =>
      gateRef.current.run(intent, run),
    [],
  );

  // -----------------------------------------------------------------------
  // Snapshot application
  // -----------------------------------------------------------------------

  const applySnapshot = useCallback((next: JourneySnapshot) => {
    if (!mountedRef.current) return;
    journeyRef.current = next;
    setJourney(next);
    setPhase(phaseFromJourney(next));
    setEnvelope((current) => (current ? { ...current, journey: next } : current));
    if (next.status !== 'preparing') preparingPollsRef.current = 0;
  }, []);

  const loadToday = useCallback(async (): Promise<void> => {
    try {
      const next = await dailyJourneyService.today(resolveTimezone());
      capabilityReadRef.current = true;
      if (!mountedRef.current) return;
      setEnvelope(next);
      journeyRef.current = next.journey;
      setJourney(next.journey);
      setPhase(phaseFromEnvelope(next));
      if (!next.enabled) onDisabled?.();
    } catch (error) {
      capabilityReadRef.current = true;
      if (!mountedRef.current) return;
      if (isJourneyDisabled(error)) {
        setPhase({ kind: 'disabled', envelope: null });
        onDisabled?.();
        return;
      }
      setPhase({
        kind: 'load_failed',
        message: errorMessage(error) || 'today_unreachable',
      });
    }
  }, [onDisabled]);

  /** Re-read the journey after a conflict and reconcile the local view. */
  const reconcile = useCallback(
    async (journeyId: string, detail: JourneyErrorDetail | null): Promise<void> => {
      try {
        const next = await dailyJourneyService.get(journeyId);
        applySnapshot(next);
        if (mountedRef.current && detail?.code) {
          setFeedback({
            kind: 'reconciled',
            code: detail.code,
            message: detail.message || 'reconciled',
          });
        }
      } catch {
        await loadToday();
      }
    },
    [applySnapshot, loadToday],
  );

  useEffect(() => {
    // An idle or in-flight capability read is `loading`, never `disabled`.
    // Reporting silence as a refusal let a consumer treat an unread capability
    // as a finished answer, and render something in front of an entry that was
    // about to appear. Only a read that actually returned may say `disabled`.
    if (!enabled) {
      setPhase(capabilityReadRef.current ? { kind: 'disabled', envelope: null } : { kind: 'loading' });
      return;
    }
    setPhase((current) => (
      current.kind === 'disabled' && current.envelope === null && !capabilityReadRef.current
        ? { kind: 'loading' }
        : current
    ));
    void loadToday();
  }, [enabled, loadToday]);

  // Bounded auto-poll while the server is still preparing the day.
  useEffect(() => {
    if (phase.kind !== 'preparing') return undefined;
    if (preparingPollsRef.current >= PREPARING_POLL_LIMIT) return undefined;
    const journeyId = phase.journey.id;
    const wait = Math.max(1, phase.retryAfterSeconds) * 1000;
    const timer = setTimeout(() => {
      preparingPollsRef.current += 1;
      void dailyJourneyService
        .get(journeyId)
        .then((next) => applySnapshot(next))
        .catch(() => undefined);
    }, wait);
    return () => clearTimeout(timer);
  }, [phase, applySnapshot]);

  useEffect(() => {
    if (phase.kind !== 'finished') return;
    if (finishedNotifiedRef.current === phase.journey.id) return;
    finishedNotifiedRef.current = phase.journey.id;
    onFinished?.(phase.journey);
  }, [phase, onFinished]);

  // -----------------------------------------------------------------------
  // Actions
  // -----------------------------------------------------------------------

  const handleFailure = useCallback(
    async (detail: JourneyErrorDetail | null, error: unknown, journeyId?: string) => {
      const plan = planFailure(detail, error, errorMessage(error) || 'transport_error');
      switch (plan.kind) {
        case 'disabled':
          if (mountedRef.current) {
            setPhase({ kind: 'disabled', envelope });
            setFeedback({ kind: 'idle' });
          }
          onDisabled?.();
          return;
        case 'empty':
          if (mountedRef.current) setFeedback({ kind: 'empty', message: plan.message });
          return;
        case 'reconcile':
          if (journeyId) {
            await reconcile(journeyId, { code: plan.code, message: plan.message });
            return;
          }
          break;
        case 'refetch':
          if (journeyId) {
            await reconcile(journeyId, null);
            return;
          }
          break;
        default:
          break;
      }
      if (mountedRef.current) {
        setFeedback({
          kind: 'error',
          message: plan.kind === 'error' ? plan.message : 'transport_error',
          retryable: true,
        });
      }
    },
    [envelope, onDisabled, reconcile],
  );

  const refresh = useCallback(async () => {
    await once('refresh', async () => {
      await loadToday();
    });
  }, [loadToday, once]);

  const start = useCallback(async () => {
    await once('create', async () => {
      setBusy(true);
      try {
        const result = await unwrap('create', { kind: 'create' }, (id) =>
          dailyJourneyService.create({
            mutationId: id,
            timezone: resolveTimezone(),
            preferredInputMode,
          }),
        );
        if (result.ok) {
          applySnapshot(result.value.data);
          if (mountedRef.current) setFeedback({ kind: 'idle' });
          return;
        }
        // A brand-new journey has no id to reconcile against.
        await handleFailure(result.detail, result.error);
        if (result.detail?.code !== 'journey_disabled') await loadToday();
      } finally {
        if (mountedRef.current) setBusy(false);
      }
    });
  }, [applySnapshot, handleFailure, loadToday, once, preferredInputMode, unwrap]);

  const retryGeneration = useCallback(async () => {
    const target = journey;
    if (!target) return;
    const intent = `retry:${target.id}:${target.revision}`;
    await once(intent, async () => {
      setBusy(true);
      try {
        const result = await unwrap(intent, { kind: 'retry' }, (id) =>
          dailyJourneyService.retry(target.id, { mutationId: id }),
        );
        if (result.ok) {
          applySnapshot(result.value.data);
          if (mountedRef.current) setFeedback({ kind: 'idle' });
          return;
        }
        await handleFailure(result.detail, result.error, target.id);
      } finally {
        if (mountedRef.current) setBusy(false);
      }
    });
  }, [applySnapshot, handleFailure, journey, once, unwrap]);

  const requestHelp = useCallback(
    async (helpKind: HelpKind) => {
      const target = journey;
      const step = currentStepOf(target);
      if (!target || !step) return;
      const intent = `help:${target.id}:${step.id}:${helpKind}`;
      await once(intent, async () => {
        setBusy(true);
        try {
          const result = await unwrap(intent, { kind: 'help', stepId: step.id, body: { help_kind: helpKind } }, (id) =>
            dailyJourneyService.help(target.id, step.id, {
              expectedRevision: target.revision,
              helpKind,
              mutationId: id,
            }),
          );
          if (result.ok) {
            if (mountedRef.current) setHelp(result.value);
            applySnapshot(result.value.journey);
            return;
          }
          await handleFailure(result.detail, result.error, target.id);
        } finally {
          if (mountedRef.current) setBusy(false);
        }
      });
    },
    [applySnapshot, handleFailure, journey, once, unwrap],
  );

  const performAttempt = useCallback(
    async (
      journeyId: string,
      stepId: string,
      expectedRevision: number,
      input: AttemptInput,
    ) => {
      // The intent key includes the exact body: resubmitting the same answer
      // replays one request, while a *different* answer is a new intent and so
      // needs a new key (the same key with a different body is a 409).
      const intent = `attempt:${journeyId}:${stepId}:${expectedRevision}:${JSON.stringify(input)}`;
      await once(intent, async () => {
        setBusy(true);
        setFeedback({ kind: 'submitting' });
        try {
          const result = await unwrap(intent, { kind: 'attempt', stepId, body: input }, (id) =>
            dailyJourneyService.attempt(journeyId, stepId, {
              expectedRevision,
              input,
              mutationId: id,
            }),
          );
          if (result.ok) {
            const attempt = result.value;
            applySnapshot(attempt.journey);
            if (mountedRef.current) setFeedback(feedbackFromAttempt(attempt));
            return;
          }
          await handleFailure(result.detail, result.error, journeyId);
        } finally {
          if (mountedRef.current) setBusy(false);
        }
      });
    },
    [applySnapshot, handleFailure, once, unwrap],
  );

  const submitAnswer = useCallback(
    async (input: AttemptInput) => {
      const target = journey;
      const step = currentStepOf(target);
      if (!target || !step) return;
      if ((input.mode === 'text' || input.mode === 'voice') && answerIsBlank(input.text)) {
        // Refused before it can reach the server and burn a turn.
        setFeedback({ kind: 'empty', message: 'empty_answer' });
        return;
      }
      lastAttemptRef.current = {
        journeyId: target.id,
        stepId: step.id,
        expectedRevision: target.revision,
        input,
      };
      await performAttempt(target.id, step.id, target.revision, input);
    },
    [journey, performAttempt],
  );

  useEffect(() => {
    submitRef.current = submitAnswer;
  }, [submitAnswer]);

  const retryLastAnswer = useCallback(async () => {
    const last = lastAttemptRef.current;
    if (!last) return;
    await performAttempt(last.journeyId, last.stepId, last.expectedRevision, last.input);
  }, [performAttempt]);

  /**
   * Finish what the previous run of the app started (WP-10).
   *
   * The recovered plan carries the ORIGINAL mutation id, so it is handed back
   * to the keyring rather than a fresh one being minted: the server then
   * answers with the receipt it already stored, and the learner sees the
   * feedback they never got instead of a second attempt being recorded.
   *
   * Only an `attempt` is re-sent. Every other journey mutation is a state
   * transition the server has already decided, and the snapshot this plan was
   * computed against already carries its result — replaying those would add
   * traffic and no information. Nothing is graded, completed or invented here:
   * a replayed attempt renders only from the server's own `AttemptResult`.
   */
  const replayPending = useCallback(
    async (plan: Extract<PendingPlan, { action: 'replay' }>) => {
      keyringRef.current.adopt(plan.intent, plan.mutationId);
      const recovered = parseAttemptIntent(plan.intent);
      if (!recovered) return;
      await performAttempt(
        recovered.journeyId,
        recovered.stepId,
        recovered.expectedRevision,
        recovered.input,
      );
    },
    [performAttempt],
  );

  useEffect(() => {
    if (!replayPlan || replayPlan.action !== 'replay') return;
    // Offered once. Clearing first means a re-render cannot re-send it.
    clearReplayPlan();
    void replayPending(replayPlan);
  }, [clearReplayPlan, replayPending, replayPlan]);

  /**
   * Finish a KNOWN snapshot.
   *
   * The snapshot is an argument rather than a closure read, because the caller
   * that matters — `continueJourney`, one statement after `advance` — holds a
   * newer snapshot than any closure this render could have captured. The
   * idempotency key still contains that snapshot's revision, so a replay of the
   * same logical finish reuses one key and a finish of a genuinely different
   * revision is a different intent.
   */
  const finishSnapshot = useCallback(
    async (target: JourneySnapshot, kind: 'complete' | 'early') => {
      const intent = `finish:${target.id}:${kind}:${target.revision}`;
      await once(intent, async () => {
        setBusy(true);
        try {
          const result = await unwrap(intent, { kind: 'finish', body: { finish_kind: kind } }, (id) =>
            dailyJourneyService.finish(target.id, {
              expectedRevision: target.revision,
              finishKind: kind,
              mutationId: id,
            }),
          );
          if (result.ok) {
            applySnapshot(result.value);
            if (mountedRef.current) setFeedback({ kind: 'idle' });
            return;
          }
          await handleFailure(result.detail, result.error, target.id);
        } finally {
          if (mountedRef.current) setBusy(false);
        }
      });
    },
    [applySnapshot, handleFailure, once, unwrap],
  );

  /**
   * The public finish action, for the learner's own "stop here" and for the
   * retry offered by the `awaiting_finish` state. It reads the ref rather than
   * the closure so that a finish issued right after another mutation carries
   * the revision the server just handed back.
   */
  const finish = useCallback(
    async (kind: 'complete' | 'early') => {
      const target = journeyRef.current;
      if (!target) return;
      await finishSnapshot(target, kind);
    },
    [finishSnapshot],
  );

  const advance = useCallback(async (): Promise<JourneySnapshot | null> => {
    const target = journeyRef.current;
    const step = currentStepOf(target);
    if (!target || !step) return null;
    const intent = `advance:${target.id}:${step.id}:${target.revision}`;
    let advanced: JourneySnapshot | null = null;
    await once(intent, async () => {
      setBusy(true);
      try {
        const result = await unwrap(intent, { kind: 'advance', stepId: step.id }, (id) =>
          dailyJourneyService.advance(target.id, {
            expectedRevision: target.revision,
            currentStepId: step.id,
            mutationId: id,
          }),
        );
        if (result.ok) {
          advanced = result.value;
          applySnapshot(result.value);
          if (mountedRef.current) {
            setFeedback({ kind: 'idle' });
            setHelp(null);
          }
          return;
        }
        await handleFailure(result.detail, result.error, target.id);
      } finally {
        if (mountedRef.current) setBusy(false);
      }
    });
    return advanced;
  }, [applySnapshot, handleFailure, once, unwrap]);

  /**
   * The single forward action. In order: stay on the same respond step when the
   * server handed back another turn, otherwise acknowledge the step, and finish
   * the day once the plan has no step left.
   *
   * The finish is issued against the snapshot `advance` just returned. Reading
   * the closure's `journey` here sent the pre-advance `expected_revision`, the
   * server refused it with 409 `journey_version_conflict`, and the day was left
   * active with no step and no recap.
   */
  const continueJourney = useCallback(async () => {
    if (feedback.kind === 'graded' && feedback.result.next_turn) {
      setFeedback({ kind: 'idle' });
      setHelp(null);
      return;
    }
    const advanced = await advance();
    if (advanced && journeyAwaitsFinish(advanced)) {
      await finishSnapshot(advanced, 'complete');
    }
  }, [advance, feedback, finishSnapshot]);

  const pause = useCallback(async () => {
    const target = journey;
    if (!target) return;
    const intent = `pause:${target.id}:${target.revision}`;
    await once(intent, async () => {
      setBusy(true);
      try {
        const result = await unwrap(intent, { kind: 'pause' }, (id) =>
          dailyJourneyService.pause(target.id, {
            expectedRevision: target.revision,
            mutationId: id,
          }),
        );
        if (result.ok) applySnapshot(result.value);
        else await handleFailure(result.detail, result.error, target.id);
      } finally {
        if (mountedRef.current) setBusy(false);
      }
    });
  }, [applySnapshot, handleFailure, journey, once, unwrap]);

  const resume = useCallback(async () => {
    const target = journey;
    if (!target) return;
    const intent = `resume:${target.id}:${target.revision}`;
    await once(intent, async () => {
      setBusy(true);
      try {
        const result = await unwrap(intent, { kind: 'resume' }, (id) =>
          dailyJourneyService.resume(target.id, {
            expectedRevision: target.revision,
            mutationId: id,
          }),
        );
        if (result.ok) applySnapshot(result.value);
        else await handleFailure(result.detail, result.error, target.id);
      } finally {
        if (mountedRef.current) setBusy(false);
      }
    });
  }, [applySnapshot, handleFailure, journey, once, unwrap]);

  const clearFeedback = useCallback(() => setFeedback({ kind: 'idle' }), []);

  // -----------------------------------------------------------------------
  // Voice — device capture plus the existing stateless transcription endpoint
  // -----------------------------------------------------------------------

  const resetVoice = useCallback(() => setVoice({ kind: 'idle' }), []);

  const startRecording = useCallback(async () => {
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setVoice({ kind: 'unsupported' });
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = createAudioMediaRecorder(stream);
      streamRef.current = stream;
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = recordedAudioBlob(chunksRef.current, recorder);
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        recorderRef.current = null;
        if (blob.size < EMPTY_RECORDING_BYTES) {
          // Nothing was captured. The learner still holds the turn.
          setVoice({ kind: 'failed', message: 'voice_empty' });
          return;
        }
        setVoice({ kind: 'transcribing' });
        void apiService
          .transcribeAudio(blob)
          .then(async (text) => {
            const spoken = (text || '').trim();
            if (!spoken) {
              setVoice({ kind: 'failed', message: 'voice_empty' });
              return;
            }
            setVoice({ kind: 'idle' });
            // Contract revision 1: no transcript id exists, so `transcript_ref`
            // is omitted. `mode: 'voice'` is what records the modality.
            await submitRef.current({ mode: 'voice', text: spoken });
          })
          .catch(() => {
            // A transcription failure keeps the turn; it is never a wrong answer.
            setVoice({ kind: 'failed', message: 'voice_failed' });
          });
      };
      recorder.start();
      setVoice({ kind: 'recording' });
    } catch {
      setVoice({ kind: 'failed', message: 'voice_permission' });
    }
  }, []);

  const stopRecording = useCallback(() => {
    try {
      recorderRef.current?.stop();
    } catch {
      setVoice({ kind: 'failed', message: 'voice_failed' });
    }
  }, []);

  // -----------------------------------------------------------------------
  // Derived
  // -----------------------------------------------------------------------

  const step = useMemo(() => currentStepOf(journey), [journey]);
  const respondPrompt = useMemo<RespondPrompt | null>(
    () => (step && step.kind === 'respond' ? step.prompt : null),
    [step],
  );
  const progress = useMemo(() => journeyProgress(journey), [journey]);

  const actions = useMemo<DailyJourneyActions>(
    () => ({
      refresh,
      start,
      retryGeneration,
      requestHelp,
      submitAnswer,
      retryLastAnswer,
      continueJourney,
      pause,
      resume,
      finish,
      clearFeedback,
      startRecording,
      stopRecording,
      resetVoice,
    }),
    [
      refresh,
      start,
      retryGeneration,
      requestHelp,
      submitAnswer,
      retryLastAnswer,
      continueJourney,
      pause,
      resume,
      finish,
      clearFeedback,
      startRecording,
      stopRecording,
      resetVoice,
    ],
  );

  return {
    phase,
    feedback,
    envelope,
    journey,
    step,
    respondPrompt,
    controlLanguage: envelope?.control_language ?? 'en',
    legacyResume: envelope?.legacy_resume ?? null,
    progress,
    busy,
    help,
    voice,
    recovery,
    actions,
  };
}

export default useDailyJourney;

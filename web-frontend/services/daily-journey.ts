/**
 * Typed facade over the existing `ApiService` transport for the Atelier V2
 * daily journey (WP-02).
 *
 * Downstream packages (WP-07/09/10) use this module, not parallel `api.ts`
 * edits, so there is exactly one place where the wire contract, the idempotency
 * keys and the conflict codes are interpreted. Auth and the native token
 * refresh come from `ApiService` — this file adds no second auth path.
 */

import apiService from '@/services/api';
import type {
  AdvanceBody,
  AttemptBody,
  AttemptInput,
  AttemptResult,
  CapabilityProgress,
  CreateJourneyBody,
  FinishBody,
  HelpBody,
  HelpKind,
  HelpResult,
  InputMode,
  JourneyErrorCode,
  JourneyErrorDetail,
  JourneyHttpResult,
  JourneySnapshot,
  PublicStep,
  RespondStep,
  TodayEnvelope,
} from '@/types/daily-journey';

export const DAILY_JOURNEY_BUDGET_SECONDS = 300 as const;

/**
 * A fresh idempotency key. Every mutation needs one, and a **retry of the same
 * intent must reuse it** — that is what makes a duplicate submit replay instead
 * of double-crediting.
 */
export function mutationId(): string {
  const globalCrypto = typeof globalThis !== 'undefined' ? globalThis.crypto : undefined;
  if (globalCrypto?.randomUUID) {
    return globalCrypto.randomUUID();
  }
  if (globalCrypto?.getRandomValues) {
    const bytes = new Uint8Array(16);
    globalCrypto.getRandomValues(bytes);
    // RFC 4122 version 4 layout.
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }
  return `mid-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

/** The learner's own IANA zone, or UTC when the browser will not say. */
export function resolveTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

/** Pull the structured `{detail: {...}}` body out of a rejected request. */
export function journeyErrorDetail(error: unknown): JourneyErrorDetail | null {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data
    ?.detail;
  if (detail && typeof detail === 'object' && typeof (detail as any).code === 'string') {
    return detail as JourneyErrorDetail;
  }
  return null;
}

export function journeyErrorCode(error: unknown): JourneyErrorCode | null {
  return journeyErrorDetail(error)?.code ?? null;
}

export function journeyErrorStatus(error: unknown): number | null {
  return (error as { response?: { status?: number } })?.response?.status ?? null;
}

/**
 * The journey moved on. Re-read it (the body carries `refresh_href` and
 * `current_revision`) and replay the intent with a **new** mutation id.
 */
export function isVersionConflict(error: unknown): boolean {
  return journeyErrorCode(error) === 'journey_version_conflict';
}

/** The same key is still being processed. Wait, then retry the identical request. */
export function isProcessing(error: unknown): boolean {
  return journeyErrorCode(error) === 'processing';
}

/** The key was reused for a different body. Never retry — build a new intent. */
export function isIdempotencyConflict(error: unknown): boolean {
  return journeyErrorCode(error) === 'idempotency_conflict';
}

export function isStepNotActive(error: unknown): boolean {
  return journeyErrorCode(error) === 'step_not_active';
}

export function isEmptyAnswer(error: unknown): boolean {
  return journeyErrorCode(error) === 'empty_answer';
}

export function isJourneyDisabled(error: unknown): boolean {
  return journeyErrorCode(error) === 'journey_disabled';
}

/** Seconds to wait before reusing the same request, when the server said so. */
export function retryAfterSeconds(error: unknown, fallback = 2): number {
  const detail = journeyErrorDetail(error);
  return typeof detail?.retry_after_seconds === 'number'
    ? detail.retry_after_seconds
    : fallback;
}

export function currentStep(journey: JourneySnapshot | null): PublicStep | null {
  if (!journey?.current_step_id) return null;
  return journey.steps.find((step) => step.id === journey.current_step_id) ?? null;
}

export function respondStep(journey: JourneySnapshot | null): RespondStep | null {
  const step = journey?.steps.find((item) => item.kind === 'respond');
  return (step as RespondStep | undefined) ?? null;
}

/** Steps the learner still has to work through, in plan order. */
/**
 * True when the character line was written by a person, not generated live.
 * Renderers must not dress an authored line up as a live reply.
 */
export function replyIsAuthored(result: AttemptResult): boolean {
  return result.reply_source === 'authored';
}

export function remainingSteps(journey: JourneySnapshot | null): PublicStep[] {
  if (!journey) return [];
  return journey.steps.filter(
    (step) => step.status === 'pending' || step.status === 'active',
  );
}

export const dailyJourneyService = {
  today(timezone: string = resolveTimezone()): Promise<TodayEnvelope> {
    return apiService.getDailyJourneyToday(timezone);
  },

  get(journeyId: string): Promise<JourneySnapshot> {
    return apiService.getDailyJourney(journeyId);
  },

  capabilityProgress(): Promise<CapabilityProgress> {
    return apiService.getDailyJourneyCapabilityProgress();
  },

  /**
   * 201 a new ready journey, 200 an existing one, 202 while it is preparing.
   * Reuse `body.mutation_id` when retrying the same intent.
   */
  create(options: {
    mutationId?: string;
    timezone?: string;
    preferredInputMode?: InputMode;
  } = {}): Promise<JourneyHttpResult<JourneySnapshot>> {
    const body: CreateJourneyBody = {
      mutation_id: options.mutationId ?? mutationId(),
      timezone: options.timezone ?? resolveTimezone(),
      budget_seconds: DAILY_JOURNEY_BUDGET_SECONDS,
      preferred_input_mode: options.preferredInputMode ?? 'text',
    };
    return apiService.createDailyJourney(body);
  },

  /** Assistance is recorded server-side before the content comes back. */
  help(
    journeyId: string,
    stepId: string,
    options: { expectedRevision: number; helpKind: HelpKind; mutationId?: string },
  ): Promise<HelpResult> {
    const body: HelpBody = {
      mutation_id: options.mutationId ?? mutationId(),
      expected_revision: options.expectedRevision,
      help_kind: options.helpKind,
    };
    return apiService.useDailyJourneyHelp(journeyId, stepId, body);
  },

  /**
   * The client never sends a score. A `pending: true` result means grading is
   * retryable — resubmit the identical body with the same `mutationId`.
   */
  attempt(
    journeyId: string,
    stepId: string,
    options: { expectedRevision: number; input: AttemptInput; mutationId?: string },
  ): Promise<AttemptResult> {
    const body: AttemptBody = {
      mutation_id: options.mutationId ?? mutationId(),
      expected_revision: options.expectedRevision,
      input: options.input,
    };
    return apiService.submitDailyJourneyAttempt(journeyId, stepId, body);
  },

  advance(
    journeyId: string,
    options: { expectedRevision: number; currentStepId: string; mutationId?: string },
  ): Promise<JourneySnapshot> {
    const body: AdvanceBody = {
      mutation_id: options.mutationId ?? mutationId(),
      expected_revision: options.expectedRevision,
      current_step_id: options.currentStepId,
    };
    return apiService.advanceDailyJourney(journeyId, body);
  },

  pause(
    journeyId: string,
    options: { expectedRevision: number; mutationId?: string },
  ): Promise<JourneySnapshot> {
    return apiService.pauseDailyJourney(journeyId, {
      mutation_id: options.mutationId ?? mutationId(),
      expected_revision: options.expectedRevision,
    });
  },

  resume(
    journeyId: string,
    options: { expectedRevision: number; mutationId?: string },
  ): Promise<JourneySnapshot> {
    return apiService.resumeDailyJourney(journeyId, {
      mutation_id: options.mutationId ?? mutationId(),
      expected_revision: options.expectedRevision,
    });
  },

  finish(
    journeyId: string,
    options: {
      expectedRevision: number;
      finishKind: 'complete' | 'early';
      mutationId?: string;
    },
  ): Promise<JourneySnapshot> {
    const body: FinishBody = {
      mutation_id: options.mutationId ?? mutationId(),
      expected_revision: options.expectedRevision,
      finish_kind: options.finishKind,
    };
    return apiService.finishDailyJourney(journeyId, body);
  },

  /** Bounded recovery for a preparing/unavailable journey; the id is reused. */
  retry(
    journeyId: string,
    options: { mutationId?: string } = {},
  ): Promise<JourneyHttpResult<JourneySnapshot>> {
    return apiService.retryDailyJourney(journeyId, {
      mutation_id: options.mutationId ?? mutationId(),
    });
  },
};

export default dailyJourneyService;

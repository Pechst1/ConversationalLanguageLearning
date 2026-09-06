/**
 * Atelier V2 daily journey wire types (contract_version 1).
 *
 * Transcribed from `docs/implementation/atelier-v2/CONTRACT-FREEZE.md`, including
 * contract revision 1 (`transcript_ref` is optional and nullable). These are the
 * only shapes downstream packages should use — no `Record<string, any>` for a
 * core payload, and the discriminated unions are real so `switch (step.kind)`
 * narrows the prompt.
 */

export const DAILY_JOURNEY_CONTRACT_VERSION = 1;
export const DAILY_JOURNEY_BUDGET_SECONDS = 300;

export type ControlLanguage = 'en' | 'de' | 'fr';
export type JourneyStatus =
  | 'preparing' | 'active' | 'paused' | 'completed' | 'ended_early' | 'unavailable';
export type StepKind = 'scene' | 'recall' | 'respond' | 'resolution';
export type StepStatus = 'pending' | 'active' | 'completed' | 'skipped';
export type InputMode = 'text' | 'voice';
export type HelpKind = 'hint' | 'translation' | 'solution' | 'suggested_response';
export type AssistanceLevel =
  | 'none' | 'hint' | 'translation' | 'solution' | 'suggested_response';
export type TaskOutcome = 'met' | 'partially_met' | 'not_yet' | 'unscored';
export type CapabilityKey = 'order_at_cafe' | 'arrange_meeting' | 'explain_delay';
export type CapabilityState =
  | 'not_tried' | 'with_support' | 'independent_once' | 'used_again_later';
export type ScenarioKey = CapabilityKey;
export type EvidenceKind =
  | 'recognized' | 'produced_supported' | 'produced_independent' | 'not_yet' | 'unscored';

export type TargetRef = {
  kind: 'vocabulary' | 'grammar' | 'error';
  /** Canonical existing record id (uuid or external id). */
  id: string;
  label_fr: string;
  label_native: string | null;
};

export type ScenarioDescriptor = {
  scenario_key: ScenarioKey;
  content_version: string;
  title_fr: string;
  objective_key: string;
  objective_native: string;
  level_band: 'A1' | 'A2' | 'B1' | 'B2';
  character_id: string;
  character_name: string;
  location_id: string;
  location_name: string;
  /** Resolved existing media URL; `null` is a valid, renderable state. */
  image_url: string | null;
  serial_thread_id: string | null;
  serial_episode_id: string | null;
  estimated_seconds: number;
};

export type ScenePrompt = {
  setup_fr: string;
  setup_native: string;
  objective_native: string;
  character_line_fr: string | null;
  character_line_audio_url: string | null;
  image_url: string | null;
};

/** Never carries correctness. */
export type RecallOption = { id: string; text_fr: string };

export type RecallPrompt = {
  task_type: 'choice' | 'tiles' | 'short_answer';
  instruction_native: string;
  prompt_fr: string | null;
  /** `[]` for short_answer. */
  options: RecallOption[];
  target: TargetRef;
  /** Only optional recall may be dropped for budget. */
  optional: boolean;
  help_available: HelpKind[];
};

export type RespondPrompt = {
  /** 0-based. */
  turn_index: number;
  /** At most two normal turns. */
  max_turns: number;
  repair_allowed: boolean;
  character_id: string;
  character_name: string;
  character_line_fr: string;
  character_line_audio_url: string | null;
  objective_native: string;
  /** `['text']` when voice is unavailable. */
  input_modes: InputMode[];
  targets: TargetRef[];
  help_available: HelpKind[];
};

export type ResolutionPrompt = {
  outcome_key: string;
  character_line_fr: string;
  summary_native: string;
  image_url: string | null;
};

type PublicStepBase = {
  id: string;
  ordinal: number;
  status: StepStatus;
  estimated_seconds: number;
  /** Server-recorded, never client-asserted. */
  assistance_used: AssistanceLevel[];
};

export type SceneStep = PublicStepBase & { kind: 'scene'; prompt: ScenePrompt };
export type RecallStep = PublicStepBase & { kind: 'recall'; prompt: RecallPrompt };
export type RespondStep = PublicStepBase & { kind: 'respond'; prompt: RespondPrompt };
export type ResolutionStep = PublicStepBase & {
  kind: 'resolution';
  prompt: ResolutionPrompt;
};

export type PublicStep = SceneStep | RecallStep | RespondStep | ResolutionStep;

export type PracticedTarget = {
  target: TargetRef;
  evidence_kind: EvidenceKind;
  assistance_level: AssistanceLevel;
};

export type CapabilityEvidence = {
  capability_key: CapabilityKey;
  state: CapabilityState;
  modality: InputMode;
  /** YYYY-MM-DD, learner-local. */
  observed_on: string;
  context_native: string;
};

export type JourneyRecap = {
  completion_kind: 'complete' | 'early';
  objective_outcome: TaskOutcome;
  practiced_targets: PracticedTarget[];
  capability_evidence: CapabilityEvidence[];
  next_focus: { target: TargetRef; reason_native: string } | null;
  collectible_ids: string[];
  story_outcome: {
    serial_thread_id: string | null;
    serial_episode_id: string | null;
    outcome_key: string;
    callback_fr: string | null;
  } | null;
  /** Measured; `null` when the runtime was not measurable. */
  active_seconds: number | null;
};

export type JourneySnapshot = {
  id: string;
  contract_version: 1;
  revision: number;
  status: JourneyStatus;
  /** YYYY-MM-DD. */
  local_date: string;
  /** IANA. */
  timezone: string;
  budget_seconds: 300;
  estimated_active_seconds: number;
  current_step_id: string | null;
  scenario: ScenarioDescriptor;
  steps: PublicStep[];
  recap: JourneyRecap | null;
  retry: { allowed: boolean; after_seconds: number } | null;
};

export type TodayEnvelope = {
  contract_version: 1;
  enabled: boolean;
  control_language: ControlLanguage;
  local_date: string;
  timezone: string;
  journey: JourneySnapshot | null;
  available: ScenarioDescriptor | null;
  legacy_resume: { href: string; session_id: string } | null;
};

export type JourneyCorrection = {
  /** Must be a real substring of the learner answer. */
  span_fr: string;
  /** Must differ from span_fr. */
  corrected_fr: string;
  note_native: string;
};

export type NextTurn = { step_id: string; prompt: RespondPrompt };

/**
 * Where `character_reply_fr` came from. An authored line must never be
 * presented to the learner as a live model response (WP-06; ratified as an
 * additive field 2026-09-05). `"none"` when there is no reply at all.
 */
export type ReplySource = 'authored' | 'model' | 'none';

export type AttemptResult = {
  contract_version: 1;
  /** Canonical learning record reference; empty while `pending`. */
  evidence_ref: string;
  task_outcome: TaskOutcome;
  assistance_level: AssistanceLevel;
  /** At most ONE foreground correction. */
  correction: JourneyCorrection | null;
  character_reply_fr: string | null;
  reply_source: ReplySource;
  next_turn: NextTurn | null;
  /** `true` => retryable grading, outcome `unscored`. Reuse the same mutation_id. */
  pending: boolean;
  journey: JourneySnapshot;
};

export type HelpResult = {
  contract_version: 1;
  step_id: string;
  help_kind: HelpKind;
  content_fr: string | null;
  content_native: string | null;
  /** Recorded BEFORE the content is returned. */
  assistance_level: AssistanceLevel;
  journey: JourneySnapshot;
};

export type CapabilityProgress = {
  contract_version: 1;
  rubric_version: string;
  capabilities: Array<{
    capability_key: CapabilityKey;
    title_native: string;
    state: CapabilityState | 'unknown';
    modalities: InputMode[];
    latest_qualifying_on: string | null;
    evidence: CapabilityEvidence[];
  }>;
};

export type JourneyErrorCode =
  | 'journey_version_conflict' | 'idempotency_conflict' | 'step_not_active'
  | 'journey_not_active' | 'empty_answer' | 'journey_disabled'
  | 'generation_unavailable' | 'processing';

export type JourneyErrorDetail = {
  code: JourneyErrorCode;
  message: string;
  current_revision?: number;
  refresh_href?: string;
  retry_after_seconds?: number;
};

export type JourneyErrorBody = { detail: JourneyErrorDetail };

/**
 * Contract revision 1 (2026-09-05): `transcript_ref` is optional and nullable —
 * `POST /audio/transcribe` is stateless and persists no transcript row, so
 * there is no id to reference. Voice attempts submit the returned text with
 * `mode: 'voice'` recording the modality.
 */
export type AttemptInput =
  | { mode: 'choice'; option_id: string }
  | { mode: 'tiles'; tile_ids: string[] }
  | { mode: 'text'; text: string }
  | { mode: 'voice'; text: string; transcript_ref?: string | null };

export type CreateJourneyBody = {
  mutation_id: string;
  timezone: string;
  budget_seconds: 300;
  preferred_input_mode: InputMode;
};

export type HelpBody = {
  mutation_id: string;
  expected_revision: number;
  help_kind: HelpKind;
};

export type AttemptBody = {
  mutation_id: string;
  expected_revision: number;
  input: AttemptInput;
};

export type AdvanceBody = {
  mutation_id: string;
  expected_revision: number;
  current_step_id: string;
};

export type RevisionBody = {
  mutation_id: string;
  expected_revision: number;
};

export type FinishBody = {
  mutation_id: string;
  expected_revision: number;
  finish_kind: 'complete' | 'early';
};

export type RetryBody = { mutation_id: string };

/** A journey POST whose HTTP status is part of the contract (201/200/202). */
export type JourneyHttpResult<T> = { data: T; status: number };

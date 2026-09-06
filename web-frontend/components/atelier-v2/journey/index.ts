/**
 * Atelier V2 daily journey — WP-07 functional milestone.
 *
 * `useDailyJourney` owns every request, idempotency key and contract state.
 * The components below are presentation over that controller and hold no
 * transport, so the Claude-Design renderer can replace them without touching
 * the hook. The visual milestone is explicitly still pending.
 */

export { useDailyJourney, default as useDailyJourneyDefault } from './useDailyJourney';
export type {
  DailyJourneyActions,
  DailyJourneyController,
  UseDailyJourneyOptions,
  VoiceState,
} from './useDailyJourney';

export {
  answerIsBlank,
  attemptVerdict,
  currentStepOf,
  detailOfPayload,
  feedbackFromAttempt,
  formatDuration,
  isReconcileCode,
  journeyOfPhase,
  journeyProgress,
  payloadIsDetail,
  phaseFromEnvelope,
  phaseFromJourney,
  recapView,
  replySourceOf,
  stepKindOf,
  textOffered,
  voiceOffered,
  RECONCILE_CODES,
} from './journey-state';
export type {
  AttemptVerdict,
  FeedbackKind,
  JourneyFeedback,
  JourneyPhase,
  JourneyProgress,
  PhaseKind,
  RecapView,
  ReplyProvenance,
} from './journey-state';

export { journeyCopy } from './journey-copy';
export type { JourneyCopy, JourneyCopyKey } from './journey-copy';

export { JourneySession, JourneyRecapView } from './JourneySession';
export type { JourneySessionProps } from './JourneySession';
export { JourneyTodayCard } from './JourneyTodayCard';
export type { JourneyTodayCardProps } from './JourneyTodayCard';
export {
  JourneyFeedbackView,
  RecallStepView,
  RespondStepView,
  ResolutionStepView,
  SceneStepView,
} from './JourneySteps';

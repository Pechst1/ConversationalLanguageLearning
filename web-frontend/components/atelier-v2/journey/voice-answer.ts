/**
 * WP-27 — speaking as the default output, without a word about pronunciation.
 *
 * The journey's respond beat is voice-first: the learner speaks, the recording
 * is transcribed by the existing stateless `POST /audio/transcribe` endpoint,
 * the transcript comes back **into the answer field** so it can be corrected,
 * and the same `submitAnswer` call sends it with `mode: 'voice'`.
 *
 * Two things this file deliberately does NOT do:
 *
 * * **No pronunciation scoring, ever** (owner decision). Speech is turned into
 *   text and graded exactly like typed text. Nothing here measures, scores or
 *   even describes how a sentence sounded.
 * * **No auto-submit.** The earlier controller-side voice path sent the
 *   transcript the instant it arrived, so a mis-heard word became a wrong
 *   answer the learner never saw coming. The transcript is a draft; the learner
 *   presses Send.
 *
 * The state machine is a pure function so every path — including the four
 * failure paths, which are the ones a device actually produces — is testable
 * without a microphone.
 */

/** Why the microphone path stopped. Each maps to one honest sentence. */
export type VoiceFailure =
  /** `getUserMedia` rejected: the OS or the learner said no. */
  | 'permission'
  /** No MediaRecorder / no mediaDevices — a WebView without capture. */
  | 'unsupported'
  /** The device is offline; transcription is a network call. */
  | 'offline'
  /** Something was recorded but it held no audio worth sending. */
  | 'empty'
  /** The transcription call failed, or came back with no words. */
  | 'failed';

export type VoiceAnswerState =
  | { kind: 'idle' }
  | { kind: 'recording' }
  | { kind: 'transcribing' }
  /** A transcript is in the field, waiting to be read, corrected and sent. */
  | { kind: 'transcript'; text: string }
  | { kind: 'failed'; reason: VoiceFailure };

export type VoiceAnswerEvent =
  | { type: 'start' }
  | { type: 'recording' }
  | { type: 'stop' }
  | { type: 'transcribed'; text: string }
  | { type: 'fail'; reason: VoiceFailure }
  | { type: 'reset' };

export const IDLE: VoiceAnswerState = { kind: 'idle' };

/**
 * The whole microphone path as one pure transition.
 *
 * A failure never destroys anything: the learner keeps the turn, keeps whatever
 * is in the field, and the text path stays open underneath. There is no state
 * from which the only way out is success.
 */
export function voiceAnswerReduce(
  state: VoiceAnswerState,
  event: VoiceAnswerEvent,
): VoiceAnswerState {
  switch (event.type) {
    case 'start':
      // Starting from a failure or an old transcript is a fresh attempt.
      return state.kind === 'recording' || state.kind === 'transcribing' ? state : IDLE;
    case 'recording':
      return { kind: 'recording' };
    case 'stop':
      // Only a live recording can be stopped into transcription; a stop that
      // arrives late (double tap, unmount) must not invent work.
      return state.kind === 'recording' ? { kind: 'transcribing' } : state;
    case 'transcribed': {
      const text = event.text.trim();
      // An empty transcript is a failure with its own sentence, never a blank
      // answer submitted on the learner's behalf.
      return text ? { kind: 'transcript', text } : { kind: 'failed', reason: 'failed' };
    }
    case 'fail':
      return { kind: 'failed', reason: event.reason };
    case 'reset':
      return IDLE;
    default:
      return state;
  }
}

/** True while the microphone owns the turn and the send button must wait. */
export function voiceIsBusy(state: VoiceAnswerState): boolean {
  return state.kind === 'recording' || state.kind === 'transcribing';
}

// ---------------------------------------------------------------------------
// The remembered preference
// ---------------------------------------------------------------------------

export type AnswerMode = 'text' | 'voice';

/** One key, one learner, one device. Nothing here is sent to the server. */
export const INPUT_MODE_KEY = 'atelier.journey.answer-mode';
/** Whether the microphone refusal has already been explained once. */
export const MIC_DENIED_KEY = 'atelier.journey.mic-denied-explained';

function storage(): Storage | null {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return null;
    return window.localStorage;
  } catch {
    // Private mode, or a WebView with site data blocked. Not an error: the
    // learner simply gets the default every time.
    return null;
  }
}

/**
 * The learner's remembered answer mode.
 *
 * The default is **voice**: WP-27's whole point is that speaking is the output
 * the product asks for. `'text'` is stored only when the learner chose it, or
 * when the device refused the microphone — a refusal is a fact about the
 * device, and re-asking on every turn would be pestering.
 */
export function readAnswerMode(fallback: AnswerMode = 'voice'): AnswerMode {
  const stored = storage()?.getItem(INPUT_MODE_KEY);
  return stored === 'text' || stored === 'voice' ? stored : fallback;
}

export function writeAnswerMode(mode: AnswerMode): void {
  try {
    storage()?.setItem(INPUT_MODE_KEY, mode);
  } catch {
    /* nothing the learner needs to know about */
  }
}

export function micRefusalExplained(): boolean {
  return storage()?.getItem(MIC_DENIED_KEY) === '1';
}

export function rememberMicRefusalExplained(): void {
  try {
    storage()?.setItem(MIC_DENIED_KEY, '1');
  } catch {
    /* nothing the learner needs to know about */
  }
}

/**
 * Which modality the submitted sentence should be recorded as.
 *
 * The learner spoke it, then may have corrected a word the transcription got
 * wrong — that is still an orally produced sentence, and the evidence records
 * it as one. It stops being voice only when nothing of the spoken turn is left:
 * no transcript, or a field emptied and rewritten from nothing.
 */
export function submittedMode(state: VoiceAnswerState, text: string): AnswerMode {
  if (state.kind !== 'transcript') return 'text';
  return text.trim() ? 'voice' : 'text';
}

export const FAILURE_COPY_KEY: Record<VoiceFailure, string> = {
  permission: 'voice_permission',
  unsupported: 'voice_unsupported',
  offline: 'voice_offline',
  empty: 'voice_empty',
  failed: 'voice_failed',
};

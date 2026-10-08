/**
 * WP-158 slice 1 — speaking inside the story: the «Parler» control's states.
 *
 * Beside the text field of a story reply, the learner can answer aloud. The
 * recording (at most 30 s) is transcribed by `POST /audio/transcribe` with the
 * `story_reply` surface; the transcript lands **in the same text field**, is
 * shown for three seconds under «C'est bien ça ?», and is then sent through the
 * same `submitAnswer` as a typed reply, with `mode: 'voice'`. Touching the field
 * during those three seconds holds the send: the learner corrects, then sends.
 *
 * Nothing here grades, and nothing here measures how the sentence sounded
 * (WP-27 owner decision: no pronunciation scoring, ever).
 *
 * Pure: no React, no network. `useSpokenReply.ts` owns the microphone.
 */

import type { RespondPrompt } from '@/types/daily-journey';

import type { VoiceFailure } from './voice-answer';

/** The longest spoken reply; the recorder stops itself here. */
export const SPOKEN_REPLY_MAX_MS = 30_000;
/** How long the transcript is shown before it is sent by itself. */
export const SPOKEN_CONFIRM_MS = 3_000;
/** Under this many bytes the microphone captured nothing worth transcribing. */
export const SPOKEN_EMPTY_BYTES = 1_200;
/** The transcription surface the server books and caps per turn. */
export const STORY_REPLY_SURFACE = 'story_reply';

/** WP-27's failures, plus the two the server can refuse a story upload with. */
export type SpokenFailure = VoiceFailure | 'ceiling' | 'too_long';

export type SpokenReplyState =
  | { kind: 'idle' }
  | { kind: 'recording'; startedAt: number }
  | { kind: 'transcribing' }
  /** The transcript is in the field; it sends itself unless `held`. */
  | { kind: 'confirm'; text: string; shownAt: number; held: boolean }
  | { kind: 'submitted'; text: string }
  | { kind: 'error'; reason: SpokenFailure };

export type SpokenReplyEvent =
  | { type: 'start' }
  | { type: 'recording'; at: number }
  | { type: 'stop' }
  | { type: 'transcribed'; text: string; at: number }
  | { type: 'fail'; reason: SpokenFailure }
  /** The learner touched the field: no sending behind their back. */
  | { type: 'hold' }
  | { type: 'submitted' }
  | { type: 'reset' };

export const SPOKEN_IDLE: SpokenReplyState = { kind: 'idle' };

export function spokenReplyReduce(
  state: SpokenReplyState,
  event: SpokenReplyEvent,
): SpokenReplyState {
  switch (event.type) {
    case 'start':
      return state.kind === 'recording' || state.kind === 'transcribing' ? state : SPOKEN_IDLE;
    case 'recording':
      return { kind: 'recording', startedAt: event.at };
    case 'stop':
      // A late stop (double tap, the 30 s timer racing a tap) invents nothing.
      return state.kind === 'recording' ? { kind: 'transcribing' } : state;
    case 'transcribed': {
      if (state.kind !== 'transcribing') return state;
      const text = event.text.trim();
      return text
        ? { kind: 'confirm', text, shownAt: event.at, held: false }
        : { kind: 'error', reason: 'failed' };
    }
    case 'fail':
      return { kind: 'error', reason: event.reason };
    case 'hold':
      return state.kind === 'confirm' && !state.held ? { ...state, held: true } : state;
    case 'submitted':
      return state.kind === 'confirm' ? { kind: 'submitted', text: state.text } : state;
    case 'reset':
      return SPOKEN_IDLE;
    default:
      return state;
  }
}

/** While the microphone or the transcription owns the turn, sending waits. */
export function spokenIsBusy(state: SpokenReplyState): boolean {
  return state.kind === 'recording' || state.kind === 'transcribing';
}

/** Whole seconds of recording left (30 → 0), or null when not recording. */
export function recordingSecondsLeft(state: SpokenReplyState, now: number): number | null {
  if (state.kind !== 'recording') return null;
  const left = SPOKEN_REPLY_MAX_MS - Math.max(0, now - state.startedAt);
  return Math.max(0, Math.ceil(left / 1000));
}

/** Whole seconds before the transcript sends itself, or null when it will not. */
export function confirmSecondsLeft(state: SpokenReplyState, now: number): number | null {
  if (state.kind !== 'confirm' || state.held) return null;
  const left = SPOKEN_CONFIRM_MS - Math.max(0, now - state.shownAt);
  return Math.max(0, Math.ceil(left / 1000));
}

/** True once the recording reached its 30 s and must be stopped. */
export function recordingIsOver(state: SpokenReplyState, now: number): boolean {
  return state.kind === 'recording' && now - state.startedAt >= SPOKEN_REPLY_MAX_MS;
}

/** True when the three seconds are up and nobody touched the field. */
export function autoSubmitDue(state: SpokenReplyState, now: number): boolean {
  return state.kind === 'confirm' && !state.held && now - state.shownAt >= SPOKEN_CONFIRM_MS;
}

/**
 * Which modality a reply is sent as: voice while the spoken sentence is still
 * what is in the field (a corrected word keeps it spoken, WP-27), text once the
 * field has been emptied.
 */
export function spokenMode(state: SpokenReplyState, text: string): 'voice' | null {
  if (state.kind !== 'confirm' && state.kind !== 'submitted') return null;
  return text.trim() ? 'voice' : null;
}

/**
 * Whether «Parler» is offered on this prompt: the build ships it, the server
 * pays for it, and the question is a free reply (cards are a tap, a letter is
 * written).
 */
export function spokenReplyOffered(
  prompt: Pick<RespondPrompt, 'choices' | 'letter'> & { spoken_reply?: boolean | null },
  launched: boolean,
): boolean {
  if (!launched || !prompt.spoken_reply) return false;
  if (prompt.letter) return false;
  return !(prompt.choices && prompt.choices.length > 0);
}

/** A refused upload, by the server's code, as one honest failure. */
export function failureFromResponse(status: number | undefined, code: string | undefined): SpokenFailure {
  if (code === 'spoken_reply_turn_ceiling' || status === 429) return 'ceiling';
  if (code === 'spoken_reply_too_long' || status === 413) return 'too_long';
  return 'failed';
}

/** The copy key that says each failure (WP-27's, plus the two story ones). */
export const SPOKEN_FAILURE_COPY_KEY: Record<SpokenFailure, string> = {
  permission: 'voice_permission',
  unsupported: 'voice_unsupported',
  offline: 'voice_offline',
  empty: 'voice_empty',
  failed: 'voice_failed',
  ceiling: 'spoken_ceiling',
  too_long: 'spoken_too_long',
};

/** «{n}» filled into a copy line. */
export function withSeconds(line: string, seconds: number | null): string {
  return line.replace('{seconds}', String(seconds ?? 0));
}

/**
 * WP-91 «Les voix» — the pure half of the heard formats: listen_tap with a
 * real clip, and dictation (a line of today's scene is heard, never printed;
 * the learner types what they hear, graded server-side like a short answer).
 *
 * No DOM here, so node tests pin: where the sound comes from, what the play
 * button says in each state, when a listen_tap falls back to read-and-tap, and
 * when a dictation can be checked. Nothing here listens to the learner.
 */

import type { RecallPrompt } from '@/types/daily-journey';

import type { JourneyCopy } from './journey-copy';
import { recallClipId } from './line-audio';

export type HeardSource =
  /** The journey's authenticated line clip: fetched with the session. */
  | { kind: 'clip'; clipId: string }
  /** Any other URL (a public file): played as it is. */
  | { kind: 'url'; url: string }
  | { kind: 'none' };

export function heardSource(audioUrl: string | null | undefined): HeardSource {
  const raw = String(audioUrl || '').trim();
  if (!raw) return { kind: 'none' };
  const clipId = recallClipId(raw);
  if (clipId) return { kind: 'clip', clipId };
  // Another authenticated API path would fail in an <audio>; say so honestly.
  if (/\/api\/v\d+\//.test(raw)) return { kind: 'none' };
  if (/^(https?:|blob:|data:|\/)/.test(raw)) return { kind: 'url', url: raw };
  return { kind: 'none' };
}

export type HeardState = 'idle' | 'loading' | 'playing' | 'played' | 'unavailable';
export type HeardEvent = 'play' | 'loaded' | 'ended' | 'stop' | 'failed';

/** The play button's machine. A failure can be retried; nothing is a dead end. */
export function heardNext(state: HeardState, event: HeardEvent): HeardState {
  switch (event) {
    case 'play':
      return state === 'loading' || state === 'playing' ? state : 'loading';
    case 'loaded':
      return state === 'loading' ? 'playing' : state;
    case 'ended':
      return state === 'playing' ? 'played' : state;
    case 'stop':
      return state === 'playing' || state === 'loading' ? 'played' : state;
    case 'failed':
      return 'unavailable';
    default:
      return state;
  }
}

/** The button's accessible name, in the learner's language. */
export function heardActionLabel(
  state: HeardState,
  copy: Pick<JourneyCopy, 'dictation_play' | 'dictation_replay' | 'dictation_stop' | 'dictation_loading'>,
): string {
  if (state === 'playing') return copy.dictation_stop;
  if (state === 'loading') return copy.dictation_loading;
  if (state === 'played' || state === 'unavailable') return copy.dictation_replay;
  return copy.dictation_play;
}

export function isDictation(prompt: Pick<RecallPrompt, 'task_type'>): boolean {
  return prompt.task_type === 'dictation';
}

/** A heard format whose clip exists (listen_tap or dictation). */
export function promptIsHeard(prompt: Pick<RecallPrompt, 'task_type' | 'audio_url'>): boolean {
  return (
    (prompt.task_type === 'listen_tap' || prompt.task_type === 'dictation') &&
    heardSource(prompt.audio_url).kind !== 'none'
  );
}

/**
 * listen_tap: is the phrase printed? Yes when there is no clip, when the clip
 * failed (read-and-tap, as before WP-91), and once the answer is graded.
 */
export function listenTapShowsPhrase(
  prompt: Pick<RecallPrompt, 'task_type' | 'audio_url'>,
  options: { clipFailed: boolean; graded: boolean },
): boolean {
  if (prompt.task_type !== 'listen_tap') return true;
  return !promptIsHeard(prompt) || options.clipFailed || options.graded;
}

/** A dictation can be checked once something is typed. */
export function dictationReady(text: string): boolean {
  return text.replace(/\s+/g, ' ').trim().length > 0;
}

/**
 * The field's attributes: the learner's own spelling is the answer, so the
 * device must not fix it, capitalise it or underline it.
 */
export const DICTATION_FIELD_ATTRS = {
  autoCorrect: 'off',
  autoCapitalize: 'off',
  autoComplete: 'off',
  spellCheck: false,
} as const;

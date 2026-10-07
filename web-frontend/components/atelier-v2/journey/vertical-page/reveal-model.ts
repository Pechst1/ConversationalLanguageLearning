/**
 * WP-144 «La page verticale» · the lines arrive with the voice.
 *
 * A panel's narration is there at once. Its lines then come one at a time, in
 * the order they are said:
 *
 *   · `voice`  — the characters speak aloud (WP-91's setting, and a device that
 *                can): each balloon opens as its line starts, and its words
 *                appear with the line's playback position (the same 0…1 clock
 *                the drawn mouth follows, `LineVoice.progress`); the next line
 *                starts when this one ends.
 *   · `timed`  — silent: each balloon opens after the one before has had time
 *                to be read.
 *   · `all`    — Reduce Motion, or nothing to wait for: everything is there at
 *                once. (Sound is not motion: under Reduce Motion the lines are
 *                still spoken in order when the learner has voices on.)
 *
 * A tap on the panel shows everything; «Weiter» never waits for any of it.
 *
 * Pure: the component owns the clocks and feeds this the events.
 */

import { frenchSpacing } from '../../../../lib/french-typography';

export type RevealText = 'all' | 'sequence';

export type RevealPlan = {
  /** How the balloons arrive. */
  text: RevealText;
  /** Speak each line, in order, without being asked. */
  speak: boolean;
  /** Words appear with the voice (only while lines arrive one by one, with sound). */
  words: boolean;
};

export function revealPlan(input: {
  reducedMotion: boolean;
  voicesAloud: boolean;
  voiceSupported: boolean;
  lineCount: number;
}): RevealPlan {
  const speak = input.voicesAloud && input.voiceSupported && input.lineCount > 0;
  if (input.reducedMotion || (input.lineCount <= 1 && !speak)) return { text: 'all', speak, words: false };
  return { text: 'sequence', speak, words: speak };
}

export function revealModeName(plan: RevealPlan): 'all' | 'voice' | 'timed' {
  if (plan.text === 'all') return 'all';
  return plan.speak ? 'voice' : 'timed';
}

export type RevealState = {
  /** How many lines are visible (their balloons open). */
  shown: number;
  /** The line being said, or -1. */
  speaking: number;
};

export type RevealEvent =
  | { type: 'start' }
  /** The line at `index` began to sound. */
  | { type: 'line-started'; index: number }
  /** The line at `index` has ended (or failed, or its time is up). */
  | { type: 'line-ended'; index: number }
  /** The learner tapped the panel: show everything. */
  | { type: 'all' };

export function revealInitial(plan: RevealPlan, total: number): RevealState {
  return plan.text === 'all' ? { shown: total, speaking: -1 } : { shown: 0, speaking: -1 };
}

export function revealReduce(state: RevealState, event: RevealEvent, total: number): RevealState {
  switch (event.type) {
    case 'start':
      return state.shown > 0 ? state : { ...state, shown: Math.min(1, total) };
    case 'line-started':
      return { shown: Math.max(state.shown, Math.min(event.index + 1, total)), speaking: event.index };
    case 'line-ended': {
      const speaking = state.speaking === event.index ? -1 : state.speaking;
      // A line that ends opens the next one; a late "ended" for an older line changes nothing.
      const shown = event.index + 1 >= state.shown ? Math.min(total, event.index + 2) : state.shown;
      return { shown, speaking };
    }
    case 'all':
      return { shown: total, speaking: state.speaking };
    default:
      return state;
  }
}

/** Every line is visible. */
export function revealDone(state: RevealState, total: number): boolean {
  return state.shown >= total;
}

/**
 * How long a silent balloon stays the newest before the next one opens: about
 * the time an A1 reader takes over it, never so short it flickers, never so
 * long the page seems stuck.
 */
export function timedDelayMs(text: string): number {
  const chars = frenchSpacing(String(text || '')).length;
  return Math.round(Math.min(2600, Math.max(900, 500 + chars * 32)));
}

/**
 * How many characters of the line are showing at `progress` (0…1) of its
 * audio. The reader shows a word once its first character is reached, so the
 * first word is there the moment the voice starts. Null progress (nothing is
 * known about the clock) shows the whole line.
 */
export function revealedChars(text: string, progress: number | null | undefined): number {
  const length = frenchSpacing(String(text || '')).length;
  if (progress === null || progress === undefined || !Number.isFinite(progress)) return length;
  if (progress >= 1) return length;
  return Math.max(0, Math.floor(Math.max(0, progress) * length));
}

/**
 * For the words in a line: which token is showing when `revealChars` characters
 * are. A token shows once its first character is reached; a run of punctuation
 * shows with the word before it.
 */
export function tokenShown(tokenStart: number, revealChars: number | null | undefined): boolean {
  if (revealChars === null || revealChars === undefined) return true;
  return tokenStart <= revealChars;
}

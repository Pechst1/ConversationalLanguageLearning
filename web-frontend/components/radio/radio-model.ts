/**
 * WP-122 A · La Radio — the pure half of the surface (no DOM, so node tests pin it).
 *
 * - The player's machine: `idle → loading → playing ⇄ paused → ended`, `failed` from
 *   anywhere (the page then shows the text: silence is a state).
 * - **Listen first** (decision 1): the text is hidden until the bulletin ends, the
 *   learner taps «Lire», or the sound cannot play.
 * - The progress hairline: lines weighted by their length (a long lede is a long
 *   stretch of the line), plus the fraction of the line playing.
 * - The dictée line is masked in the transcript until the dictée is graded — the
 *   learner writes what they heard, not what they just read.
 * - Who stands on the stage: Romy, and the guest from their first line on.
 */

import type { RadioBulletin, RadioLine } from '@/lib/radio-types';

import { fill, type RadioCopy } from './radio-copy';

export type PlayerPhase = 'idle' | 'loading' | 'playing' | 'paused' | 'ended' | 'failed';
export type PlayerEvent = 'play' | 'loaded' | 'pause' | 'line_ended' | 'last_ended' | 'failed';

export function playerNext(phase: PlayerPhase, event: PlayerEvent): PlayerPhase {
  switch (event) {
    case 'play':
      return phase === 'playing' || phase === 'loading' ? phase : 'loading';
    case 'loaded':
      return phase === 'loading' ? 'playing' : phase;
    case 'pause':
      return phase === 'playing' || phase === 'loading' ? 'paused' : phase;
    case 'line_ended':
      return phase === 'playing' ? 'loading' : phase;
    case 'last_ended':
      return phase === 'playing' || phase === 'loading' ? 'ended' : phase;
    case 'failed':
      return 'failed';
    default:
      return phase;
  }
}

/** Listen first: hidden until the end, «Lire», or a bulletin that cannot sound. */
export function textVisible(phase: PlayerPhase, readRequested: boolean, audio: RadioBulletin['audio']): boolean {
  return readRequested || phase === 'ended' || phase === 'failed' || audio !== 'ready';
}

/** The press's label in each phase. */
export function playLabel(phase: PlayerPhase, copy: Pick<RadioCopy, 'listen' | 'pause' | 'resume' | 'listen_again' | 'loading_audio'>): string {
  if (phase === 'playing') return copy.pause;
  if (phase === 'loading') return copy.loading_audio;
  if (phase === 'paused') return copy.resume;
  if (phase === 'ended') return copy.listen_again;
  return copy.listen;
}

/** 0..1 — the lines before `index` by length, plus `fraction` of the line playing. */
export function bulletinProgress(lines: Pick<RadioLine, 'textFr'>[], index: number, fraction: number): number {
  const weights = lines.map((line) => Math.max(1, line.textFr.length));
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  if (!total) return 0;
  const clampedIndex = Math.max(0, Math.min(index, lines.length));
  const done = weights.slice(0, clampedIndex).reduce((sum, weight) => sum + weight, 0);
  const current = clampedIndex < lines.length ? weights[clampedIndex] * Math.max(0, Math.min(1, fraction || 0)) : 0;
  return Math.max(0, Math.min(1, (done + current) / total));
}

export function progressLabel(progress: number, copy: Pick<RadioCopy, 'progress_aria'>): string {
  return fill(copy.progress_aria, { p: Math.round(progress * 100) });
}

/** Is this line the dictée's, still hidden behind its mask? */
export function lineMasked(line: Pick<RadioLine, 'index'>, dicteeIndex: number, graded: boolean): boolean {
  return !graded && line.index === dicteeIndex;
}

/** The stage's cast: Romy, and the guest from their first line on; the speaker in front. */
export function stageMembers(
  bulletin: Pick<RadioBulletin, 'lines' | 'guestId'>,
  index: number,
  phase: PlayerPhase,
): Array<{ id: string; hold: string | null; speaking: boolean }> {
  const guestLine = bulletin.lines.findIndex((line) => line.role === 'guest');
  const playing = phase === 'playing' || phase === 'loading' || phase === 'paused';
  const speaker = playing ? bulletin.lines[index]?.speaker ?? 'romy_tremblay' : 'romy_tremblay';
  const members = [{ id: 'romy_tremblay', hold: 'notebook' as string | null, speaking: speaker === 'romy_tremblay' }];
  const guestOn = bulletin.guestId && guestLine >= 0 && (index >= guestLine || phase === 'ended');
  if (guestOn) members.push({ id: bulletin.guestId, hold: null, speaking: speaker === bulletin.guestId });
  return members;
}

/** The dictée's verdict line, in the chrome language (the server's note when it has one). */
export function dicteeVerdict(
  outcome: 'met' | 'partially_met' | 'not_yet',
  copy: Pick<RadioCopy, 'dictee_met' | 'dictee_partial' | 'dictee_not_yet'>,
): string {
  if (outcome === 'met') return copy.dictee_met;
  if (outcome === 'partially_met') return copy.dictee_partial;
  return copy.dictee_not_yet;
}

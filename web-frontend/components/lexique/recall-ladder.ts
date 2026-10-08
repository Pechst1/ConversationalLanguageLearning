/**
 * WP-115b — the recall ladder, as the word drill reads it. Pure: no React, no fetch.
 *
 * The server sends each card's rung (`ladder`): recognition → production → audio →
 * cloze by memory stability, `scene` (a kept word's own line, first two reviews) or
 * `rescue` (a word that keeps failing, with a cue). The drill draws the rung, grades an
 * answered card by the answer, and brings a wrong card back at the end of the session
 * until it is right once (successive relearning).
 */

export type CardMode = 'recognition' | 'production' | 'audio' | 'cloze' | 'scene' | 'rescue';

export type LadderCue = {
  sentence_fr?: string | null;
  speaker_id?: string | null;
  first_letter?: string;
  length?: number;
};

type LadderItem = {
  ladder?: string | null;
  scene_cue?: LadderCue | null;
  rescue_cue?: LadderCue | null;
} | null | undefined;

/** The scene's or the rescue's cue, for the rung the card is on. */
export function ladderCue(item: LadderItem): LadderCue | null {
  if (!item) return null;
  return item.ladder === 'rescue' ? item.rescue_cue ?? null : item.scene_cue ?? null;
}

/**
 * The card's mode from the server's rung, or `null` when it sent none (an older
 * server: the page falls back to its own rule). A cloze whose sentence could not be
 * blanked is asked as production; a scene with no line is too.
 */
export function ladderRung(item: LadderItem, clozeBlanked: boolean): CardMode | null {
  const rung = item?.ladder;
  if (rung === 'cloze') return clozeBlanked ? 'cloze' : 'production';
  if (rung === 'scene') return ladderCue(item)?.sentence_fr ? 'scene' : 'production';
  if (rung === 'rescue') return 'rescue';
  if (rung === 'recognition' || rung === 'production' || rung === 'audio') return rung;
  return null;
}

/** The format an answered card reports, so the server can earn its grade. */
export function gradedFormat(mode: CardMode, spoken: boolean): 'typed' | 'audio' | 'cloze' | 'spoken' {
  if (spoken) return 'spoken';
  if (mode === 'audio') return 'audio';
  if (mode === 'cloze' || mode === 'scene' || mode === 'rescue') return 'cloze';
  return 'typed';
}

/** Successive relearning: a wrong card goes (back) to the end; a right one leaves. */
export function nextAgainQueue(queue: number[], wordId: number, wrong: boolean): number[] {
  const rest = queue.filter((id) => id !== wordId);
  return wrong ? [...rest, wordId] : rest;
}

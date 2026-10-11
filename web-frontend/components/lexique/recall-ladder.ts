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
  /**
   * Owner decision 2026-10-08: the word's own line is blanked at the form it had
   * there («Vous _____ d'où ?» → «venez»); that form is the answer and the lemma
   * («venir») is the hint. Absent on an older server: the card's French stands.
   */
  expected_fr?: string | null;
  hint_fr?: string | null;
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

/** The line as the card shows it: the blanked line, with the lemma as a hint when the
 *  blank is an inflected form — «Vous _____ d'où ? (venir)». */
export function linePrompt(cue: LadderCue | null): string {
  const sentence = cue?.sentence_fr?.trim() || '';
  if (!sentence) return '';
  const hint = cue?.hint_fr?.trim();
  return hint ? `${sentence} (${hint})` : sentence;
}

/** The answer a line card expects: the form in the line, else the card's French. */
export function lineAnswer(mode: CardMode, cue: LadderCue | null, french: string): string {
  if ((mode === 'scene' || mode === 'rescue') && cue?.sentence_fr && cue.expected_fr) return cue.expected_fr;
  return french;
}

const ELIDED = new Set(['j', 'l', 'd', 'n', 'm', 't', 's', 'c', 'qu', 'lorsqu', 'puisqu', 'jusqu']);

/**
 * The device's own fold of a line answer (the server's verdict decides): the
 * normalised answer equals the form, or is the form with its elided clitic
 * («j etais» for «etais» — the apostrophe already folded to a space).
 */
export function matchesLineForm(typed: string, expected: string): boolean {
  if (!typed || !expected) return false;
  if (typed === expected) return true;
  const [clitic, ...rest] = typed.split(' ');
  return ELIDED.has(clitic) && rest.join(' ') === expected;
}

/** Successive relearning: a wrong card goes (back) to the end; a right one leaves. */
export function nextAgainQueue(queue: number[], wordId: number, wrong: boolean): number[] {
  const rest = queue.filter((id) => id !== wordId);
  return wrong ? [...rest, wordId] : rest;
}

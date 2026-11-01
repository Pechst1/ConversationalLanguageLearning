/**
 * WP-115b — the recall ladder, as the word drill reads it. Pure: no React, no fetch.
 *
 * The server sends each card's rung (`ladder`): recognition → production → audio →
 * production by memory stability, `scene` (a kept word's own line, first two reviews) or
 * `rescue` (a word that keeps failing, with a cue). The drill draws the rung, grades an
 * answered card by the answer, and brings a wrong card back at the end of the session
 * until it is right once (successive relearning).
 *
 * Owner decision 2026-11-01: no cloze card (a new sentence with the word blanked) in the
 * daily review — it was too hard to reach the word from the sentence. A well-held word is
 * translated and its card carries the example sentence. The server's rung decides; with
 * none (an older server) the drill falls back to the same table as the server
 * (`app/services/recall_ladder.py`, THRESHOLDS and RUNGS — a test holds the two together),
 * never to a rule of its own.
 */

export type CardMode = 'recognition' | 'production' | 'audio' | 'scene' | 'rescue';
export type LadderRung = 'recognition' | 'production' | 'audio';

type Band = 'A1' | 'A2' | 'B1' | 'B2' | 'C1';

/** Stability (days) at which a card moves up a step — `THRESHOLDS` on the server. */
export const LADDER_THRESHOLDS: Readonly<Record<Band, readonly [number, number, number]>> = {
  A1: [5.0, 14.0, 30.0],
  A2: [3.0, 10.0, 30.0],
  B1: [1.0, 7.0, 21.0],
  B2: [1.0, 5.0, 14.0],
  C1: [1.0, 4.0, 10.0],
};

/** The format from each threshold on — `RUNGS` on the server. No step is a cloze. */
export const LADDER_RUNGS: readonly [LadderRung, LadderRung, LadderRung] = ['production', 'audio', 'production'];

/** The learner's band as the server reads it (`_band`): C2 → C1, anything else → A2. */
export function ladderBand(level?: string | null): Band {
  const code = String(level || '').trim().toUpperCase().slice(0, 2);
  if (code in LADDER_THRESHOLDS) return code as Band;
  return code === 'C2' ? 'C1' : 'A2';
}

/** The server's `rung()`, for a card that came without one. */
export function fallbackRung({
  stability,
  isNew,
  level,
}: {
  stability?: number | null;
  isNew: boolean;
  level?: string | null;
}): LadderRung {
  if (isNew) return 'recognition';
  const held = Number(stability || 0);
  const thresholds = LADDER_THRESHOLDS[ladderBand(level)];
  for (let index = thresholds.length - 1; index >= 0; index -= 1) {
    if (held >= thresholds[index]) return LADDER_RUNGS[index];
  }
  return 'recognition';
}

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

type DeckItem = {
  ladder?: string | null;
  scene_cue?: LadderCue | null;
  rescue_cue?: LadderCue | null;
  stability?: number | null;
  is_new?: boolean | null;
  bucket?: string | null;
} | null | undefined;

/** The scene's or the rescue's cue, for the rung the card is on. */
export function ladderCue(item: LadderItem): LadderCue | null {
  if (!item) return null;
  return item.ladder === 'rescue' ? item.rescue_cue ?? null : item.scene_cue ?? null;
}

/**
 * The card's mode from the server's rung, or `null` when it sent none. A `cloze` from a
 * deck loaded before the owner's decision of 2026-11-01 is asked as production (the
 * meaning → the French, with the example); a scene with no line is too.
 */
export function ladderRung(item: LadderItem): CardMode | null {
  const rung = item?.ladder;
  if (rung === 'cloze') return 'production';
  if (rung === 'scene') return ladderCue(item)?.sentence_fr ? 'scene' : 'production';
  if (rung === 'rescue') return 'rescue';
  if (rung === 'recognition' || rung === 'production' || rung === 'audio') return rung;
  return null;
}

/** The card's mode: the server's rung, else the server's table (never a cloze). */
export function cardMode(item: DeckItem): CardMode {
  if (!item) return 'recognition';
  return (
    ladderRung(item)
    ?? fallbackRung({ stability: item.stability, isNew: Boolean(item.is_new) || item.bucket === 'new', level: null })
  );
}

/**
 * The meaning printed under a line card's blanked line (scene, rescue): a blank with no
 * other cue was the cloze the owner retired on 2026-11-01, so the line keeps its cue
 * (the rescue's first letter and length) and also says what the word means. A line card
 * with no line already asks by the meaning, so it prints nothing more.
 */
export function lineMeaning(mode: CardMode, cue: LadderCue | null, meaning: string): string {
  if (mode !== 'scene' && mode !== 'rescue') return '';
  return linePrompt(cue) ? String(meaning || '').trim() : '';
}

/** The format an answered card reports, so the server can earn its grade. */
export function gradedFormat(mode: CardMode, spoken: boolean): 'typed' | 'audio' | 'cloze' | 'spoken' {
  if (spoken) return 'spoken';
  if (mode === 'audio') return 'audio';
  // A line card (scene, rescue) is graded against the form in its line: the
  // server's `cloze` review format, which re-reads that line.
  if (mode === 'scene' || mode === 'rescue') return 'cloze';
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

/**
 * #88 — the deck's count is `done / total` with a total fixed for the session.
 * A card answered «Again» is back in the queue, so it is not done yet; a card
 * answered right is done and never leaves that state. Counting the re-queued
 * cards on top of the reviewed ones (the old `remaining + reviewed`) made the
 * total grow with every «Again» and shrink with every «I know it».
 */
export function deckProgress(
  deckIds: readonly number[],
  reviewedIds: ReadonlySet<number>,
  againQueue: readonly number[],
): { done: number; total: number } {
  const total = new Set(deckIds).size;
  const again = new Set(againQueue);
  let done = 0;
  reviewedIds.forEach((id) => {
    if (!again.has(id)) done += 1;
  });
  return { done: Math.min(done, total), total };
}

/** Successive relearning: a wrong card goes (back) to the end; a right one leaves. */
export function nextAgainQueue(queue: number[], wordId: number, wrong: boolean): number[] {
  const rest = queue.filter((id) => id !== wordId);
  return wrong ? [...rest, wordId] : rest;
}

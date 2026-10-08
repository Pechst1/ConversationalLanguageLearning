/**
 * WP-S7 — Éclair, the 60-second minimal-pair sprint, as data.
 *
 * The round's items arrive with their keys, so every tap is graded here, at
 * once (no request per answer); the server grades the same answers again when
 * the round is filed. Pure: node tests read it directly.
 */

export const ECLAIR_SECONDS = 60;

export type EclairItem = {
  id: string;
  concept_id: number;
  prompt?: string | null;
  prompt_l10n?: Record<string, string> | null;
  labels: string[];
  correct_answer: string;
};

export type EclairRound = {
  eclair_id: string;
  pair: string;
  concept_ids: number[];
  rules: Array<{ concept_id: number; title_fr: string; category?: string | null; subskill?: string | null; name?: string | null }>;
  seconds: number;
  best: number;
  plays: number;
  items: EclairItem[];
};

export type EclairAnswer = { id: string; answer: string; correct: boolean };

export type EclairResult = {
  pair: string;
  score: number;
  answered: number;
  best_before: number;
  best: number;
  new_best: boolean;
};

/** Typography-folded comparison (curly quotes, spacing, final stop), like the server's. */
export function normalizeAnswer(value: unknown): string {
  return String(value ?? '')
    .normalize('NFC')
    .replace(/[‘’‚‛′`´ʹʻʼ]/g, "'")
    .replace(/[«»“”„"]/g, '"')
    .replace(/[.!?…]+\s*$/, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

export function gradeEclair(item: EclairItem, answer: string): boolean {
  return normalizeAnswer(answer) === normalizeAnswer(item.correct_answer);
}

export function eclairScore(answers: EclairAnswer[]): number {
  return answers.filter((answer) => answer.correct).length;
}

/** Whole seconds left, never below zero. */
export function secondsLeft(startedAt: number, now: number, seconds: number = ECLAIR_SECONDS): number {
  return Math.max(0, Math.ceil(seconds - (now - startedAt) / 1000));
}

export function roundOver(startedAt: number | null, now: number, answered: number, items: number, seconds: number = ECLAIR_SECONDS): boolean {
  if (startedAt == null) return false;
  return secondsLeft(startedAt, now, seconds) <= 0 || answered >= items;
}

/** The cue in the chrome language when the item offers one, else its own. */
export function eclairCue(item: EclairItem | null | undefined, language: string): string {
  const table = item?.prompt_l10n;
  if (table && typeof table === 'object' && typeof table[language] === 'string' && table[language].trim()) {
    return table[language].trim();
  }
  return String(item?.prompt ?? '').trim();
}

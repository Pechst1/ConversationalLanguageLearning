/* Reading position for the Feuilleton reader.
 *
 * One record per scene, under the storage key the reader has always used
 * (`pilot:reader:<sceneId>`), so drafts written by the previous vertical reader
 * survive this change. The record adds the paged reader's own state:
 *
 *   stageKey     the stage the learner was on, by identity not index, so a
 *                panel that arrives late (art still printing) cannot silently
 *                move the learner somewhere else
 *   stageIndex   a fallback for the same, when the key is no longer present
 *   furthest     the furthest stage reached — what makes "already read" a fact
 *                and not a guess
 *
 * Pure module: no React, no storage access, no network. The caller owns I/O.
 */

export type ReaderPositionRecord = {
  answers: Record<string, string>;
  scrollY: number;
  stageKey: string | null;
  stageIndex: number;
  furthest: number;
};

export const READER_STORAGE_PREFIX = 'pilot:reader:';

export function readerStorageKey(sceneId: string): string {
  return `${READER_STORAGE_PREFIX}${sceneId}`;
}

function safeInteger(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.trunc(parsed) : fallback;
}

function safeAnswers(value: unknown): Record<string, string> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const out: Record<string, string> = {};
  Object.entries(value as Record<string, unknown>).forEach(([key, entry]) => {
    if (typeof entry === 'string') out[key] = entry;
  });
  return out;
}

/* Accepts the legacy `{ answers, scrollY }` shape without losing the draft. */
export function normalizeReaderPosition(raw: unknown): ReaderPositionRecord {
  const record = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const stageKey = typeof record.stageKey === 'string' && record.stageKey ? record.stageKey : null;
  const stageIndex = Math.max(0, safeInteger(record.stageIndex, 0));
  return {
    answers: safeAnswers(record.answers),
    scrollY: Math.max(0, safeInteger(record.scrollY, 0)),
    stageKey,
    stageIndex,
    furthest: Math.max(stageIndex, Math.max(0, safeInteger(record.furthest, stageIndex))),
  };
}

export function clampStageIndex(index: number, count: number): number {
  if (count <= 0) return 0;
  const value = safeInteger(index, 0);
  if (value < 0) return 0;
  if (value > count - 1) return count - 1;
  return value;
}

/* Where to open the reader. Identity first, index second, start of the episode
   last. Never past the end of what the server actually sent. */
export function resolveStartIndex(saved: ReaderPositionRecord, stageKeys: string[]): number {
  if (!stageKeys.length) return 0;
  if (saved.stageKey) {
    const byKey = stageKeys.indexOf(saved.stageKey);
    if (byKey >= 0) return byKey;
  }
  return clampStageIndex(saved.stageIndex, stageKeys.length);
}

/* The furthest point reached, re-anchored onto the stage list that is actually
   present now. A shorter list can only shrink it, never invent progress. */
export function resolveFurthest(saved: ReaderPositionRecord, stageKeys: string[], startIndex: number): number {
  if (!stageKeys.length) return 0;
  return Math.max(clampStageIndex(saved.furthest, stageKeys.length), clampStageIndex(startIndex, stageKeys.length));
}

export function withStage(
  position: ReaderPositionRecord,
  index: number,
  stageKeys: string[],
): ReaderPositionRecord {
  const stageIndex = clampStageIndex(index, stageKeys.length);
  return {
    ...position,
    stageIndex,
    stageKey: stageKeys[stageIndex] ?? null,
    furthest: Math.max(position.furthest, stageIndex),
  };
}

export function withAnswers(
  position: ReaderPositionRecord,
  answers: Record<string, string>,
): ReaderPositionRecord {
  return { ...position, answers: safeAnswers(answers) };
}

export function emptyReaderPosition(): ReaderPositionRecord {
  return { answers: {}, scrollY: 0, stageKey: null, stageIndex: 0, furthest: 0 };
}

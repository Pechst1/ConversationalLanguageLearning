/**
 * P11 · a word graded offline is kept (pages/vocabulary/review.tsx).
 *
 * 17 Nov walk: on a lost connection the deck said «La reprise n’a pas pu être
 * classée» and put the card back at the end; the grade itself was gone. Now a
 * grade the network did not carry is held on the device (the journey's pattern,
 * `lib/journey-recovery.ts`: a fail-soft store under a `pilot:` key, cleared on
 * sign-out), counted as filed, and sent in order on reconnect or on the next open.
 *
 * Framework-free, so the node harness pins it.
 */
import { errorKind } from '@/lib/app-errors';
import type { ConnectionView } from '@/lib/journey-recovery';
import {
  safeReadJson,
  safeRemove,
  safeWriteJson,
  type StorageLike,
  type StorageOutcome,
} from '@/lib/pilot-resilience';

export const GRADE_QUEUE_KEY = 'pilot:review-grades:v1';
/** A queue never grows past this; the oldest grade goes first. */
export const GRADE_QUEUE_LIMIT = 200;
/** A grade older than this is not sent: the card has long been asked again. */
export const GRADE_QUEUE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

export type QueuedGrade = {
  word_id: number;
  rating: number;
  format: 'flashcard';
  queued_at: number;
};

/** Only a grade the network lost is kept; a refusal from the server is not retried. */
export function gradeLostToNetwork(error: unknown): boolean {
  const kind = errorKind(error);
  return kind === 'offline' || kind === 'slow' || kind === 'down';
}

function isGrade(value: unknown): value is QueuedGrade {
  const item = value as QueuedGrade | null;
  return Boolean(
    item &&
      Number.isInteger(item.word_id) &&
      Number.isInteger(item.rating) &&
      item.format === 'flashcard' &&
      typeof item.queued_at === 'number',
  );
}

export function readGradeQueue(storage?: StorageLike | null, now: number = Date.now()): QueuedGrade[] {
  const stored = safeReadJson<unknown>(GRADE_QUEUE_KEY, [], storage);
  if (!Array.isArray(stored)) return [];
  return stored.filter(isGrade).filter((item) => now - item.queued_at < GRADE_QUEUE_MAX_AGE_MS);
}

function writeGradeQueue(queue: QueuedGrade[], storage?: StorageLike | null): StorageOutcome {
  return queue.length ? safeWriteJson(GRADE_QUEUE_KEY, queue, storage) : safeRemove(GRADE_QUEUE_KEY, storage);
}

/** Keep a grade the network lost. The last grade of a word is the one that stands. */
export function enqueueGrade(
  grade: Omit<QueuedGrade, 'queued_at'>,
  storage?: StorageLike | null,
  now: number = Date.now(),
): QueuedGrade[] {
  const queue = readGradeQueue(storage, now).filter((item) => item.word_id !== grade.word_id);
  const next = [...queue, { ...grade, queued_at: now }].slice(-GRADE_QUEUE_LIMIT);
  writeGradeQueue(next, storage);
  return next;
}

export type FlushResult = { sent: number; left: number };

/**
 * Send the held grades in order. A grade the network loses again stops the run
 * and stays (with everything after it); a grade the server refuses is dropped.
 */
export async function flushGradeQueue(
  send: (grade: QueuedGrade) => Promise<unknown>,
  storage?: StorageLike | null,
  now: number = Date.now(),
): Promise<FlushResult> {
  const queue = readGradeQueue(storage, now);
  let sent = 0;
  let index = 0;
  for (; index < queue.length; index += 1) {
    try {
      await send(queue[index]);
      sent += 1;
    } catch (error) {
      if (gradeLostToNetwork(error)) break;
    }
  }
  // Grades queued while this run was sending are kept too.
  const done = new Set(queue.slice(0, index).map((item) => `${item.word_id}:${item.queued_at}`));
  const left = readGradeQueue(storage, now).filter((item) => !done.has(`${item.word_id}:${item.queued_at}`));
  writeGradeQueue(left, storage);
  return { sent, left: left.length };
}

/**
 * The deck's connection banner (`ConnectionNotice`, the journey's): offline, sending,
 * or grades held on this device; nothing when online with nothing held.
 */
export function deckConnection({
  online,
  queued,
  syncing,
}: {
  online: boolean;
  queued: number;
  syncing: boolean;
}): ConnectionView {
  const state: ConnectionView['state'] = !online
    ? 'offline_cached'
    : syncing
      ? 'syncing'
      : queued > 0
        ? 'pending_sync'
        : 'live';
  return { state, online, readingCache: false, unsent: queued > 0, stale: false, lastSyncedAt: null };
}

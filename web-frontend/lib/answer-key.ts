/**
 * WP-76 — grade a pick on the device against the server's hashed key.
 *
 * The server (`app/services/journey_answer_key.py`) sends, for choice,
 * classify, tiles and word-bank recall only:
 *
 *   answer_key = { version: 1, salt, digests: [sha256hex(salt + ":" + material)] }
 *
 * `material` is the option id, or the tile ids joined with U+001F, each id
 * normalised exactly as the server's `normalize_answer_text` does (iOS smart
 * quotes and exotic spaces folded, whitespace collapsed). The server grades by
 * id, never by text, so this agrees with it by construction.
 *
 * The result is a preview. The attempt is still posted, and the server's
 * verdict wins whenever the two disagree. Anything unexpected — no key, an
 * unknown version, no Web Crypto (an insecure origin) — answers `null`, which
 * means "wait for the server", exactly as before WP-76.
 */

import type { RecallAnswerKey, RecallFormat, RecallPrompt } from '@/types/daily-journey';

export type LocalVerdict = 'correct' | 'wrong';

export const ANSWER_KEY_VERSION = 1;
export const TILE_JOINER = '\u001f';

const PICK_FORMATS: ReadonlySet<string> = new Set(['choice', 'classify', 'listen_tap']);
const ORDER_FORMATS: ReadonlySet<string> = new Set(['tiles', 'word_bank', 'unscramble']);
/**
 * WP-78. A matching item's key holds one digest per pair (the French card's id
 * and the meaning card's id, joined like tiles), so each pair is coloured the
 * moment it is made. `tileIds` is then exactly one `[fr, native]` pair.
 */
const PAIR_FORMATS: ReadonlySet<string> = new Set(['match_pairs']);

/** Mirror of `journey_contracts._QUOTE_FOLD`. Keep the two tables identical. */
const QUOTE_FOLD: Record<string, string> = {
  '‘': "'",
  '’': "'",
  '‛': "'",
  '′': "'",
  '´': "'",
  '`': "'",
  '“': '"',
  '”': '"',
  '„': '"',
  '″': '"',
  ' ': ' ',
  ' ': ' ',
  ' ': ' ',
};

/** `normalize_answer_text` on the client: fold, then collapse whitespace. */
export function normalizeKeyPart(value: unknown): string {
  let text = value == null ? '' : String(value);
  for (const [source, replacement] of Object.entries(QUOTE_FOLD)) {
    text = text.split(source).join(replacement);
  }
  return text.split(/\s+/).filter(Boolean).join(' ');
}

export function isKeyedFormat(taskType: RecallFormat | string | null | undefined): boolean {
  return (
    PICK_FORMATS.has(String(taskType)) ||
    ORDER_FORMATS.has(String(taskType)) ||
    PAIR_FORMATS.has(String(taskType))
  );
}

/** The string that is hashed for one answer, or `null` when there is none. */
export function answerMaterial(
  taskType: RecallFormat | string,
  answer: { optionId?: string | null; tileIds?: readonly string[] | null },
): string | null {
  if (PICK_FORMATS.has(taskType)) {
    const part = normalizeKeyPart(answer.optionId);
    return part || null;
  }
  if (ORDER_FORMATS.has(taskType) || PAIR_FORMATS.has(taskType)) {
    const parts = (answer.tileIds ?? []).map(normalizeKeyPart);
    if (!parts.length || parts.some((part) => !part)) return null;
    if (PAIR_FORMATS.has(taskType) && parts.length !== 2) return null;
    return parts.join(TILE_JOINER);
  }
  return null;
}

function subtle(): SubtleCrypto | null {
  const api = typeof globalThis !== 'undefined' ? (globalThis as { crypto?: Crypto }).crypto : undefined;
  return api?.subtle ?? null;
}

export async function sha256Hex(text: string): Promise<string | null> {
  const engine = subtle();
  if (!engine) return null;
  try {
    const bytes = new TextEncoder().encode(text);
    const digest = await engine.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
  } catch {
    return null;
  }
}

function usableKey(key: RecallAnswerKey | null | undefined): key is RecallAnswerKey {
  return Boolean(
    key &&
      key.version === ANSWER_KEY_VERSION &&
      typeof key.salt === 'string' &&
      key.salt &&
      Array.isArray(key.digests) &&
      key.digests.length,
  );
}

/** Does this prompt carry a key this build can use? */
export function promptHasAnswerKey(prompt: Pick<RecallPrompt, 'task_type' | 'answer_key'>): boolean {
  return isKeyedFormat(prompt.task_type) && usableKey(prompt.answer_key);
}

/**
 * The local verdict for one pick: `correct`, `wrong`, or `null` for "cannot
 * tell — wait for the server".
 */
export async function checkAnswerLocally(
  prompt: Pick<RecallPrompt, 'task_type' | 'answer_key'>,
  answer: { optionId?: string | null; tileIds?: readonly string[] | null },
): Promise<LocalVerdict | null> {
  if (!promptHasAnswerKey(prompt)) return null;
  const key = prompt.answer_key as RecallAnswerKey;
  const material = answerMaterial(prompt.task_type, answer);
  if (material == null) return null;
  const digest = await sha256Hex(`${key.salt}:${material}`);
  if (!digest) return null;
  return key.digests.includes(digest) ? 'correct' : 'wrong';
}

/**
 * After a wrong pick: which option the key says was right, if any. Only for a
 * single pick — the learner has already committed, so showing the right card
 * is feedback, not a hint.
 */
export async function correctOptionLocally(
  prompt: Pick<RecallPrompt, 'task_type' | 'answer_key' | 'options'>,
): Promise<string | null> {
  if (!promptHasAnswerKey(prompt) || !PICK_FORMATS.has(prompt.task_type)) return null;
  for (const option of prompt.options) {
    // eslint-disable-next-line no-await-in-loop -- two to four options, microseconds each
    const verdict = await checkAnswerLocally(prompt, { optionId: option.id });
    if (verdict === 'correct') return option.id;
  }
  return null;
}

/**
 * The verdict the screen shows. The server's word is final: once it has
 * graded, a disagreeing local preview is simply replaced (quietly — no second
 * sound, no second buzz).
 */
export function shownVerdict(
  local: LocalVerdict | null,
  server: 'correct' | 'supported' | 'wrong' | null,
): LocalVerdict | null {
  if (server) return server === 'wrong' ? 'wrong' : 'correct';
  return local;
}

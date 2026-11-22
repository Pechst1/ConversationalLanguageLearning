/**
 * «Papier · la voix» · the pure rules, pinned by `voix.test.js`:
 *
 *  * which line on screen is one the session may speak (the server's manifest, by its words);
 *  * which of the counter's lines are heard before they are read: a regular's take not yet
 *    answered, the reply before the learner's comeback — and only while clips can be made and
 *    none has failed (otherwise every text shows at once);
 *  * the veil's ruled lines (as many as the text would set, the last one shorter);
 *  * autoplay only after a gesture on this page, with the voices-aloud setting on, once per line.
 */

import type { VxLine, VxManifest } from '@/lib/revue-voix';
import type { RvComptoirView } from '@/lib/revue-types';

/** How a text is compared with the manifest's lines: quotes, spaces and case folded. */
export function lineForm(text: string): string {
  return text
    .replace(/[‘’‛′´]/g, "'")
    .replace(/[“”„]/g, '"')
    .replace(/[   ]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

export function findLine(manifest: VxManifest | null, textFr: string, kinds?: readonly VxLine['kind'][]): VxLine | null {
  if (!manifest) return null;
  const wanted = lineForm(textFr);
  if (!wanted) return null;
  return manifest.lines.find((line) => lineForm(line.textFr) === wanted && (!kinds || kinds.includes(line.kind))) ?? null;
}

/** The key a heard line is remembered and spoken under. */
export function heardKey(speakerId: string, textFr: string): string {
  return `vx|${speakerId}|${lineForm(textFr)}`;
}

/** The counter's lines still to be heard first: the takes not yet answered, the reply before the comeback. */
export function pendingLines(view: RvComptoirView | null | undefined): string[] {
  if (!view) return [];
  const keys = view.cast.filter((member) => !member.reaction && member.take.fr).map((member) => heardKey(member.id, member.take.fr));
  const opinion = view.opinion;
  if (opinion?.reply?.line.fr && !opinion.comeback) keys.push(heardKey(opinion.reply.by, opinion.reply.line.fr));
  return keys;
}

export type VeilState = {
  manifest: VxManifest | null;
  /** Lines still to be heard first (`pendingLines`). */
  pending: readonly string[];
  /** Lines played to the end, or opened with «Lire». */
  revealed: ReadonlySet<string>;
  /** A clip could not be had: from now on every text shows at once. */
  failed: boolean;
};

/**
 * The lines heard before they are read: the regulars' opinions (their takes, the reply) — the
 * counter's listening task. Romy's own lines (her intro, her asks, her marks) are what the
 * learner acts on: on every desk («Au comptoir», «Le titre») they are read at once (integration
 * 2026-11-22: one rule for both desks).
 */
export const HEARD_FIRST_KINDS: readonly VxLine['kind'][] = ['take', 'reply'];

/** Is this regular's line shown as a veil (heard before it is read)? */
export function isVeiled(state: VeilState, speakerId: string, textFr: string): boolean {
  if (!state.manifest || state.manifest.audio !== 'ready' || state.failed) return false;
  const line = findLine(state.manifest, textFr, HEARD_FIRST_KINDS);
  if (!line) return false;
  const key = heardKey(speakerId, textFr);
  return state.pending.includes(key) && !state.revealed.has(key);
}

/** The veil's lines: one per ~34 characters a phone column sets, the last one as long as it runs. */
export function veilLines(textFr: string, perLine = 34): number[] {
  const length = textFr.trim().length;
  if (!length) return [];
  const full = Math.floor(length / perLine);
  const rest = length % perLine;
  const lines = Array.from({ length: full }, () => 100);
  if (rest) lines.push(Math.max(18, Math.round((rest / perLine) * 100)));
  return lines.slice(0, 6);
}

/** Speak a line unasked? Only after a gesture on this page, with the setting on. */
export function mayAutoplay({ voicesAloud, gesture }: { voicesAloud: boolean; gesture: boolean }): boolean {
  return voicesAloud && gesture;
}

/** Is any of these lines (`[speakerId, textFr]`) still waiting to be heard? */
export function anyVeiled(state: VeilState | null | undefined, lines: readonly (readonly [string, string])[]): boolean {
  return Boolean(state) && lines.some(([speakerId, textFr]) => isVeiled(state as VeilState, speakerId, textFr));
}

type StorageLike = { getItem: (key: string) => string | null; setItem: (key: string, value: string) => void };

const revealedKey = (sessionId: string) => `vx-revealed:${sessionId}`;

/**
 * The lines this viewer heard or opened in a session (integration 2026-11-22): a reload must
 * not veil again a line already heard while its answer is on screen. Per session, on this
 * device; a blocked or broken storage reads as nothing.
 */
export function readRevealed(storage: StorageLike | null | undefined, sessionId: string): Set<string> {
  try {
    const raw = storage?.getItem(revealedKey(sessionId));
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(parsed) ? parsed.filter((key): key is string => typeof key === 'string') : []);
  } catch {
    return new Set();
  }
}

export function writeRevealed(storage: StorageLike | null | undefined, sessionId: string, keys: ReadonlySet<string>): void {
  try {
    storage?.setItem(revealedKey(sessionId), JSON.stringify(Array.from(keys).slice(-40)));
  } catch {
    // A private window: the line is revealed for this visit only.
  }
}

/** Lines to be heard first that the manifest does not know yet (it was read before they came). */
export function unknownPending(manifest: VxManifest | null, pending: readonly string[]): string[] {
  if (!manifest) return [];
  const known = new Set(manifest.lines.map((line) => heardKey(line.speakerId, line.textFr)));
  return pending.filter((key) => !known.has(key));
}

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

/** Is this regular's line shown as a veil (heard before it is read)? */
export function isVeiled(state: VeilState, speakerId: string, textFr: string): boolean {
  if (!state.manifest || state.manifest.audio !== 'ready' || state.failed) return false;
  const line = findLine(state.manifest, textFr, ['take', 'reply']);
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

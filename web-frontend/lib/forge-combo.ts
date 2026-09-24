/**
 * WP-S7 — La Forge's combo, as data.
 *
 * Consecutive *checked* right answers light up shape tokens in the rule's
 * shape (the top bar). WP-S1's semantics hold: a verdict the server has not
 * checked — an unavailable reading, a provisional local check whose relecture
 * is still running — neither extends nor breaks the run. Only a checked error
 * resets it.
 *
 * The server's forge view carries the run (`forge.combo.run`, from the same
 * rule over the séance's ledger) and is authoritative; the corrections on the
 * page are the fallback for a server that does not send it.
 *
 * Pure: no React, no audio — node tests read it directly.
 */

import { correctRunFrom, runOutcome } from './seance-feedback';

/** Tokens drawn in the top bar; a longer run keeps them all lit and shows its number. */
export const COMBO_TOKENS = 5;

export type ComboView = { run: number; best: number };

type ForgeLike = {
  combo?: { run?: unknown; best?: unknown } | null;
  features?: { combo?: unknown } | null;
} | null | undefined;

function count(value: unknown): number | null {
  const n = Math.floor(Number(value));
  return Number.isFinite(n) && n >= 0 ? n : null;
}

/** Is the combo on? The owner's switch (`features.combo`), on unless it says false. */
export function comboEnabled(forge: ForgeLike): boolean {
  return forge?.features?.combo !== false;
}

/** The run and best run over corrections in submission order (the fallback). */
export function comboFromCorrections(corrections: Array<Record<string, any> | null | undefined>): ComboView {
  let run = 0;
  let best = 0;
  for (const correction of corrections) {
    const outcome = runOutcome(correction);
    if (outcome === 'extends') {
      run += 1;
      best = Math.max(best, run);
    } else if (outcome === 'breaks') {
      run = 0;
    }
  }
  return { run, best };
}

/** The server's run when it sends one, else the page's own count. */
export function comboOf(forge: ForgeLike, corrections: Array<Record<string, any> | null | undefined>): ComboView {
  const run = count(forge?.combo?.run);
  const best = count(forge?.combo?.best);
  if (run !== null) return { run, best: Math.max(run, best ?? 0) };
  const local = comboFromCorrections(corrections);
  return { run: correctRunFrom(corrections), best: local.best };
}

export type ComboStep = 'extend' | 'reset' | 'hold';

/** What changed between two readings of the run. */
export function comboStep(previous: number, next: number): ComboStep {
  if (next > previous) return 'extend';
  if (next < previous && previous > 0) return 'reset';
  return 'hold';
}

/** Five tokens, lit from the left: `true` = lit in the rule's colour, `false` = a ghost. */
export function comboTokens(run: number, slots: number = COMBO_TOKENS): boolean[] {
  const lit = Math.max(0, Math.min(slots, Math.floor(Number(run) || 0)));
  return Array.from({ length: slots }, (_, index) => index < lit);
}

/**
 * What the learner feels when the run moves. The first right answer is the
 * ordinary «correct» tap (no sound: the combo has not started); from the
 * second on, the combo's double tap and its soft tone, rising with the run.
 * A reset is felt by the wrong answer itself, never twice.
 */
export function comboFeel(step: ComboStep, run: number): { haptic: 'correct' | 'token' | null; tone: boolean } {
  if (step !== 'extend') return { haptic: null, tone: false };
  if (run >= 2) return { haptic: 'token', tone: true };
  return { haptic: 'correct', tone: false };
}

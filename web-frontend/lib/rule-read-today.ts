/**
 * R2 item 1 — a day teaches its rule once.
 *
 * The day's rule card (the journey's «Règle» step) is the one place the rule is
 * explained; La Forge is where it is practised. Before this, the Forge opened on
 * the same card again (real play, 17 Nov: être shown three times on day 1). When
 * the learner read today's card for a rule, the Forge opened from the day starts
 * on its first item, with the card one tap away under «La règle».
 *
 * Per-viewer and best-effort: sessionStorage, wrapped in try/catch. Without it the
 * Forge simply shows its card as before.
 */

const STORE_KEY = 'atelier.rule-read.';

function todayKey(now: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function storage(): Storage | null {
  try {
    return typeof window !== 'undefined' ? window.sessionStorage : null;
  } catch {
    return null;
  }
}

/** The learner read today's card for this rule (the journey's rule step was answered). */
export function markRuleRead(conceptId: unknown, now: Date = new Date(), store: Storage | null = storage()): void {
  const id = Number(conceptId);
  if (!store || !Number.isFinite(id) || id <= 0) return;
  try {
    store.setItem(STORE_KEY + id, todayKey(now));
  } catch {
    // A full or blocked store only costs the shortcut.
  }
}

/** Was today's card for this rule read today? */
export function ruleReadToday(conceptId: unknown, now: Date = new Date(), store: Storage | null = storage()): boolean {
  const id = Number(conceptId);
  if (!store || !Number.isFinite(id) || id <= 0) return false;
  try {
    return store.getItem(STORE_KEY + id) === todayKey(now);
  } catch {
    return false;
  }
}

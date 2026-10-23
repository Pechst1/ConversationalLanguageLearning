/**
 * #88 — «Stop here?» is a two-tap control: the first tap asks, the second
 * answers. The ask stays open until it is answered. It used to close by itself
 * after 4 s, so a second tap could land on the reverted button and ask again.
 * The way out without answering is Escape, or a séance that is no longer partial.
 */
export type FinishEvent = 'tap' | 'escape' | 'partial_changed';

export interface FinishState {
  confirming: boolean;
}

export function nextFinishState(
  state: FinishState,
  event: FinishEvent,
  partial: boolean,
): { state: FinishState; finish: boolean } {
  if (event === 'tap') {
    // A complete séance stops at once; a partial one asks first.
    if (partial && !state.confirming) return { state: { confirming: true }, finish: false };
    return { state: { confirming: false }, finish: true };
  }
  if (event === 'escape') return { state: { confirming: false }, finish: false };
  // `partial_changed`: only a séance that is no longer partial closes the ask.
  return { state: partial ? state : { confirming: false }, finish: false };
}

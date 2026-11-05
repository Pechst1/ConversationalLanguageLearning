/**
 * Le Lexique · the swipe that files a turned card (pages/vocabulary/review.tsx).
 *
 * Owner, 4 Nov: «less taps to say whether one knew it or not, maybe by swiping».
 * A turned card is dragged sideways: right files «Je sais» (grade 2), left «Encore»
 * (grade 0). A short flick counts as much as a long drag. Pure: no React, no DOM.
 */

export type SwipeSide = 'know' | 'again';

/** The grade each side files, on the deck's four-grade scale. */
export const SWIPE_RATING: Readonly<Record<SwipeSide, number>> = { know: 2, again: 0 };

/** Pixels the finger travels before the gesture is read as a drag, not a tap. */
export const DRAG_SLOP = 8;

/** How far a card is dragged before letting go files it: a quarter of its width, 70–120px. */
export function swipeThreshold(width: number): number {
  return Math.max(70, Math.min(120, (Number(width) || 0) * 0.25));
}

/** A drag starts only once it is clearly sideways; a vertical move is the page's scroll. */
export function dragStarts(dx: number, dy: number): 'drag' | 'scroll' | null {
  if (Math.abs(dx) > DRAG_SLOP && Math.abs(dx) > Math.abs(dy)) return 'drag';
  if (Math.abs(dy) > DRAG_SLOP * 1.5) return 'scroll';
  return null;
}

/**
 * Where a released drag lands: past the threshold, or a flick (≥ 0.5 px/ms over at
 * least 40px) in the same direction, files that side; anything else springs back.
 */
export function swipeVerdict({ dx, velocity, width }: { dx: number; velocity: number; width: number }): SwipeSide | null {
  const flick = Math.abs(velocity) >= 0.5 && Math.abs(dx) >= 40 && Math.sign(velocity) === Math.sign(dx);
  if (Math.abs(dx) < swipeThreshold(width) && !flick) return null;
  return dx > 0 ? 'know' : 'again';
}

/** How sure the drag looks, −1 (again) … 1 (know): drives the stamps' opacity. */
export function swipeProgress(dx: number, width: number): number {
  const value = dx / swipeThreshold(width);
  return Math.max(-1, Math.min(1, value));
}

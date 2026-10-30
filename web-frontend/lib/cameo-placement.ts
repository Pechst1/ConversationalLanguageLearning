/**
 * #282 (live walk 22 Oct, phone size): «Two mistakes in a row» and its speech bubble sat
 * on top of the prompt and the answer box of the item the learner had just missed.
 * A cameo is a visitor: it stands where it covers nothing the learner is reading or
 * answering, and when there is no such place it does not come.
 *
 * Pure geometry, so the layer and the node suite share it.
 */

export type Zone = { left: number; right: number; top: number; bottom: number };

/** The screen's own furniture a cameo's bubble must not cover. */
export const KEEP_CLEAR_SELECTOR = [
  '.ep-exercise',
  '.ep-repair',
  '.ep-galley',
  '.ep-foot',
  '[data-cameo-clear]',
].join(', ');

const overlaps = (zone: Zone, bubble: Zone) =>
  bubble.left < zone.right && bubble.right > zone.left && bubble.top < zone.bottom && bubble.bottom > zone.top;

/**
 * The top edge for a bubble of `bubble`'s width and height: the one nearest `preferred` that
 * leaves `margin` clear of every zone and stays inside the viewport, or `null` when the
 * zones leave no such place.
 */
export function clearBubbleTop(
  bubble: { left: number; right: number; height: number },
  zones: Zone[],
  viewportHeight: number,
  preferred: number,
  { margin = 6, step = 4, edge = 8 }: { margin?: number; step?: number; edge?: number } = {},
): number | null {
  const fits = (top: number) =>
    !zones.some((zone) =>
      overlaps(zone, { left: bubble.left, right: bubble.right, top: top - margin, bottom: top + bubble.height + margin }),
    );
  let best: number | null = null;
  for (let top = edge; top + bubble.height <= viewportHeight - edge; top += step) {
    if (!fits(top)) continue;
    if (best === null || Math.abs(top - preferred) < Math.abs(best - preferred)) best = top;
  }
  return best;
}

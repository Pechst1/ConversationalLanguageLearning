/**
 * #239 — La Forge's correction stays above the verdict sheet.
 *
 * Walk 2026-10-19 / 20 (375 px): after a miss the correction card (the right
 * sentence and why) started under the questions and ran on under the sticky
 * «Noch nicht» sheet, so the reason could not be read without scrolling — and a
 * learner does not know there is anything to scroll to. The sheet stays sticky
 * (its primary must not leave the thumb); the page scrolls the card up above it.
 */

export type KeepAboveBox = {
  /** The card's top and bottom, in viewport pixels. */
  cardTop: number;
  cardBottom: number;
  /** The sticky sheet's top (the visible area's bottom edge). */
  sheetTop: number;
  /** The sticky header's bottom (the visible area's top edge); 0 without one. */
  headerBottom: number;
  /** Air between the card and either edge. */
  margin?: number;
};

/**
 * How far to scroll (positive: down) so the card sits between the header and the
 * sheet. A card taller than that space is aligned under the header, so its first
 * lines — the right sentence — are the ones in view. 0 when it already fits.
 */
export function scrollToKeepAbove({ cardTop, cardBottom, sheetTop, headerBottom, margin = 12 }: KeepAboveBox): number {
  const top = headerBottom + margin;
  const bottom = sheetTop - margin;
  if (cardTop < top) return Math.round(cardTop - top);
  if (cardBottom <= bottom) return 0;
  const down = cardBottom - bottom;
  const room = cardTop - top;
  return Math.round(Math.min(down, room));
}

function scrollParent(node: HTMLElement | null): HTMLElement | null {
  for (let el = node?.parentElement ?? null; el; el = el.parentElement) {
    // The body's «overflow: auto» moves to the viewport: the window scrolls, and
    // body.scrollBy does nothing (walk 2026-10-20: the card never moved).
    if (el === document.body || el === document.documentElement) return null;
    const { overflowY } = getComputedStyle(el);
    if ((overflowY === 'auto' || overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 1) return el;
  }
  return null;
}

/** How long after the verdict a change in the card's or the sheet's size is still followed. */
const SETTLE_MS = 2000;

/**
 * Scrolls the feedback's first card above its sticky sheet (`.ep-foot`) and under
 * the sticky header (`.ep-top`). Browser only; a no-op when either is missing.
 *
 * #319: the scroll is worked out from one reading, and a French correction is long
 * enough to change after it (a late font, the notes under the right sentence, the
 * sheet settling): the card then stayed where the first reading put it, under the
 * sheet. For `SETTLE_MS` the card and the sheet are watched, and the card is put
 * back above the sheet whenever either changes size. The returned function stops
 * the watching (the verdict went away, or the learner moved on).
 */
export function keepCardAboveSheet(feedback: HTMLElement | null, { smooth = true } = {}): () => void {
  const nothing = () => {};
  if (!feedback || typeof window === 'undefined') return nothing;
  const sheet = feedback.querySelector<HTMLElement>('.ep-foot') ?? document.querySelector<HTMLElement>('.ep-foot');
  const card = Array.from(feedback.children).find((el) => !el.classList.contains('ep-foot')) as HTMLElement | undefined;
  if (!sheet || !card) return nothing;
  const header = document.querySelector<HTMLElement>('.ep-top');
  const align = (behavior: ScrollBehavior) => {
    const cardBox = card.getBoundingClientRect();
    const sheetBox = sheet.getBoundingClientRect();
    const delta = scrollToKeepAbove({
      cardTop: cardBox.top,
      cardBottom: cardBox.bottom,
      sheetTop: Math.min(sheetBox.top, window.innerHeight),
      headerBottom: header ? Math.max(0, header.getBoundingClientRect().bottom) : 0,
    });
    if (!delta) return;
    const parent = scrollParent(feedback);
    if (parent) parent.scrollBy({ top: delta, behavior });
    else window.scrollBy({ top: delta, behavior });
  };
  align(smooth ? 'smooth' : 'auto');

  if (typeof ResizeObserver === 'undefined') return nothing;
  const until = Date.now() + SETTLE_MS;
  const sizes = () => `${Math.round(card.getBoundingClientRect().height)}|${Math.round(sheet.getBoundingClientRect().height)}`;
  let seen = sizes();
  // A change in size is followed at once, not smoothly: the card is already on its way.
  // (A ResizeObserver also reports once when it starts; that is not a change.)
  const observer = new ResizeObserver(() => {
    if (Date.now() > until) {
      observer.disconnect();
      return;
    }
    const now = sizes();
    if (now === seen) return;
    seen = now;
    align('auto');
  });
  observer.observe(card);
  observer.observe(sheet);
  return () => observer.disconnect();
}

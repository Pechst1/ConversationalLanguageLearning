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

/**
 * Scrolls the feedback's first card above its sticky sheet (`.ep-foot`) and under
 * the sticky header (`.ep-top`). Browser only; a no-op when either is missing.
 */
export function keepCardAboveSheet(feedback: HTMLElement | null, { smooth = true } = {}): void {
  if (!feedback || typeof window === 'undefined') return;
  const sheet = feedback.querySelector<HTMLElement>('.ep-foot') ?? document.querySelector<HTMLElement>('.ep-foot');
  const card = Array.from(feedback.children).find((el) => !el.classList.contains('ep-foot')) as HTMLElement | undefined;
  if (!sheet || !card) return;
  const header = document.querySelector<HTMLElement>('.ep-top');
  const cardBox = card.getBoundingClientRect();
  const sheetBox = sheet.getBoundingClientRect();
  const delta = scrollToKeepAbove({
    cardTop: cardBox.top,
    cardBottom: cardBox.bottom,
    sheetTop: Math.min(sheetBox.top, window.innerHeight),
    headerBottom: header ? Math.max(0, header.getBoundingClientRect().bottom) : 0,
  });
  if (!delta) return;
  const behavior: ScrollBehavior = smooth ? 'smooth' : 'auto';
  const parent = scrollParent(feedback);
  if (parent) parent.scrollBy({ top: delta, behavior });
  else window.scrollBy({ top: delta, behavior });
}

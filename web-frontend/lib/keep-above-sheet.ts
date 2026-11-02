/**
 * #239 — La Forge's correction stays above the verdict sheet.
 *
 * Walk 2026-10-19 / 20 (375 px): after a miss the correction card (the right
 * sentence and why) started under the questions and ran on under the sticky
 * «Noch nicht» sheet, so the reason could not be read without scrolling — and a
 * learner does not know there is anything to scroll to. The sheet stays sticky
 * (its primary must not leave the thumb); the page scrolls the card up above it.
 *
 * #282 — the last repair (and «Compare») must stand clear of the sheet too.
 *
 * #319 — this module is the ONE owner of the miss scroll. It used to share the job
 * with `clearTheSheet` (another timer, another target, instant against smooth), and
 * the final position depended on which of them ran last. Now one function works out
 * one delta that satisfies both rules, and re-applies it until the layout is still.
 */

import { scrollToClearSheet } from './sheet-clearance';

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
  /**
   * The bottom of the last thing the miss asks of the learner (the last repair or
   * galley, «Compare» in it), when it is below the card. It must clear the sheet
   * too, as far as the first card allows.
   */
  anchorBottom?: number | null;
};

/**
 * How far to scroll (positive: down) so the card sits between the header and the
 * sheet, and the last repair below it clears the sheet. Both rules at once, one answer:
 * the first card wins when they cannot both fit (#239), so the card is never taken up
 * under the header to make room for a repair. A card taller than the space is aligned
 * under the header, so its first lines — the right sentence — are the ones in view.
 * 0 when everything already fits.
 */
export function scrollToKeepAbove({ cardTop, cardBottom, sheetTop, headerBottom, margin = 12, anchorBottom = null }: KeepAboveBox): number {
  const top = headerBottom + margin;
  const bottom = sheetTop - margin;
  const room = cardTop - top; // how far down the card may still go before it meets the header
  const cardNeeds = cardTop < top ? room : cardBottom <= bottom ? 0 : cardBottom - bottom;
  const anchorNeeds = anchorBottom == null ? 0 : scrollToClearSheet(anchorBottom, sheetTop, margin);
  return Math.round(Math.min(Math.max(cardNeeds, anchorNeeds), room));
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
/** Fonts and the coach's portrait settle after the first reading (#282): look again at these moments. */
const RECHECK_MS = [150, 600, 1200];
/** No scroll for this long: the scroll has ended (`scrollend` is not everywhere yet). */
const QUIET_MS = 120;

/**
 * Scrolls the feedback's first card above its sticky sheet (`.ep-foot`) and under
 * the sticky header (`.ep-top`), and the last repair clear of the sheet. Browser
 * only; a no-op when either is missing.
 *
 * One owner (#319): the first move is smooth, every later one is instant and is
 * worked out from the live layout, so whichever runs last lands on the same
 * position. The card and the sheet are watched for `SETTLE_MS` (a late font, the
 * notes under the right sentence), the layout is looked at again at `RECHECK_MS`,
 * and the feedback says what it is doing in `data-scroll`: «settling» until nothing
 * is left to move and the scroll has been quiet, then «settled». The walk measures
 * only then. The returned function stops it all (the verdict went away).
 */
export function keepCardAboveSheet(
  feedback: HTMLElement | null,
  { smooth = true, clearLast = true }: { smooth?: boolean; clearLast?: boolean } = {},
): () => void {
  const nothing = () => {};
  if (!feedback || typeof window === 'undefined') return nothing;
  const sheet = feedback.querySelector<HTMLElement>('.ep-foot') ?? document.querySelector<HTMLElement>('.ep-foot');
  const card = Array.from(feedback.children).find((el) => !el.classList.contains('ep-foot')) as HTMLElement | undefined;
  if (!sheet || !card) return nothing;
  const header = document.querySelector<HTMLElement>('.ep-top');
  const repairs = feedback.querySelectorAll<HTMLElement>('.ep-repair, .ep-galley');
  const anchor = clearLast && repairs.length ? repairs[repairs.length - 1] : null;
  /** Moves the page to the one position that satisfies both rules; true when it had to move. */
  const align = (behavior: ScrollBehavior): boolean => {
    const cardBox = card.getBoundingClientRect();
    const sheetBox = sheet.getBoundingClientRect();
    const delta = scrollToKeepAbove({
      cardTop: cardBox.top,
      cardBottom: cardBox.bottom,
      sheetTop: Math.min(sheetBox.top, window.innerHeight),
      headerBottom: header ? Math.max(0, header.getBoundingClientRect().bottom) : 0,
      anchorBottom: anchor ? anchor.getBoundingClientRect().bottom : null,
    });
    if (!delta) return false;
    const parent = scrollParent(feedback);
    if (parent) parent.scrollBy({ top: delta, behavior });
    else window.scrollBy({ top: delta, behavior });
    return true;
  };

  let live = true;
  let rechecksLeft = RECHECK_MS.length;
  const timers: number[] = [];
  let quiet: number | undefined;
  const say = (state: 'settling' | 'settled') => feedback.setAttribute('data-scroll', state);
  /** Looks again once the scroll has been quiet: moves if it must, else says it is settled. */
  const whenQuiet = () => {
    window.clearTimeout(quiet);
    quiet = window.setTimeout(() => {
      if (!live) return;
      if (align('auto')) {
        say('settling');
        whenQuiet();
      } else if (rechecksLeft === 0) {
        say('settled');
      }
    }, QUIET_MS);
  };
  const onScroll = () => whenQuiet();
  window.addEventListener('scroll', onScroll, { capture: true, passive: true });
  RECHECK_MS.forEach((ms) => {
    timers.push(window.setTimeout(() => {
      if (!live) return;
      rechecksLeft -= 1;
      if (align('auto')) say('settling');
      whenQuiet();
    }, ms));
  });

  say('settling');
  align(smooth ? 'smooth' : 'auto');
  whenQuiet();

  let observer: ResizeObserver | null = null;
  if (typeof ResizeObserver !== 'undefined') {
    const until = Date.now() + SETTLE_MS;
    const sizes = () => `${Math.round(card.getBoundingClientRect().height)}|${Math.round(sheet.getBoundingClientRect().height)}`;
    let seen = sizes();
    // A change in size is followed at once, not smoothly: the card is already on its way.
    // (A ResizeObserver also reports once when it starts; that is not a change.)
    const watcher = new ResizeObserver(() => {
      if (Date.now() > until) {
        watcher.disconnect();
        return;
      }
      const now = sizes();
      if (now === seen) return;
      seen = now;
      align('auto');
      say('settling');
      whenQuiet();
    });
    watcher.observe(card);
    watcher.observe(sheet);
    observer = watcher;
  }
  return () => {
    live = false;
    observer?.disconnect();
    timers.forEach((id) => window.clearTimeout(id));
    window.clearTimeout(quiet);
    window.removeEventListener('scroll', onScroll, true);
  };
}

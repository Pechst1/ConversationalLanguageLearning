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
 *
 * #665 — «until the layout is still» means all of it. The owner used to follow only the
 * card's and the sheet's sizes; a note mounting between the card and the last repair, or
 * the repair growing a line, moved «Compare» under the sheet and nothing looked again
 * before the next timer. It now follows the size of everything it places: the whole
 * feedback, the card, the sheet and the last repair.
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

/** How long after the verdict the page owns the scroll: after it the page is the learner's. */
const SETTLE_MS = 2000;
/** Fonts and the coach's portrait settle after the first reading (#282): look again at these moments. */
const RECHECK_MS = [150, 600, 1200];
/** No scroll for this long: the scroll has ended (`scrollend` is not everywhere yet). */
const QUIET_MS = 120;
/** What a learner does to take the scroll over (a scroll event alone cannot tell them from us). */
const TAKEOVER_EVENTS = ['wheel', 'touchstart', 'keydown'] as const;

/**
 * Scrolls the feedback's first card above its sticky sheet (`.ep-foot`) and under
 * the sticky header (`.ep-top`), and the last repair clear of the sheet. Browser
 * only; a no-op when either is missing.
 *
 * One owner (#319): the first move is smooth, every later one is instant and is
 * worked out from the live layout (the last repair is looked up each time, so one
 * that mounts late counts), so whichever runs last lands on the same position. For
 * `SETTLE_MS` after the verdict the page owns the scroll: a change in the size of the
 * feedback, the card, the sheet or the last repair is followed at once (#665), the layout is
 * looked at again at `RECHECK_MS`, and the feedback says what it is doing in
 * `data-scroll`, «settling» until nothing is left to move and the scroll has been
 * quiet, then «settled». The walk measures only then. The window ends at `SETTLE_MS`,
 * or at once when the learner scrolls (wheel, touch, keys): from then on nothing here
 * moves the page, whatever the learner does with it. The returned function ends it
 * early (the verdict went away).
 */
export function keepCardAboveSheet(
  feedback: HTMLElement | null,
  {
    smooth = true,
    clearLast = true,
    card: chosen = null,
  }: {
    smooth?: boolean;
    clearLast?: boolean;
    /** The card to keep above the sheet, when it is not the feedback's first child (the rafale's first missed row). */
    card?: HTMLElement | null;
  } = {},
): () => void {
  const nothing = () => {};
  if (!feedback || typeof window === 'undefined') return nothing;
  const sheet = feedback.querySelector<HTMLElement>('.ep-foot') ?? document.querySelector<HTMLElement>('.ep-foot');
  const card = chosen ?? (Array.from(feedback.children).find((el) => !el.classList.contains('ep-foot')) as HTMLElement | undefined);
  if (!sheet || !card) return nothing;
  const header = document.querySelector<HTMLElement>('.ep-top');
  /** The last repair or galley, looked up live: one can mount after the verdict.
      Owner 2026-11-13: the task's one quiet line under the cards counts too — the
      sticky sheet never covers what it refers to. */
  const lastRepair = (): HTMLElement | null => {
    if (!clearLast) return null;
    const repairs = feedback.querySelectorAll<HTMLElement>('.ep-repair, .ep-galley, .ep-task-line');
    return repairs.length ? repairs[repairs.length - 1] : null;
  };
  let live = true;
  /** Moves the page to the one position that satisfies both rules; true when it had to move. */
  const align = (behavior: ScrollBehavior): boolean => {
    if (!live) return false;
    const cardBox = card.getBoundingClientRect();
    const sheetBox = sheet.getBoundingClientRect();
    const anchor = lastRepair();
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

  let rechecksLeft = RECHECK_MS.length;
  const timers: number[] = [];
  let quiet: number | undefined;
  let observer: ResizeObserver | null = null;
  const say = (state: 'settling' | 'settled') => feedback.setAttribute('data-scroll', state);
  const onScroll = () => whenQuiet();
  const takeOver = () => release('settled');
  /** Ends the page's hold on the scroll for good: no timer, listener or observer is left to move it. */
  function release(state?: 'settled') {
    live = false;
    observer?.disconnect();
    timers.forEach((id) => window.clearTimeout(id));
    window.clearTimeout(quiet);
    window.removeEventListener('scroll', onScroll, true);
    TAKEOVER_EVENTS.forEach((type) => window.removeEventListener(type, takeOver, true));
    if (state) say(state);
  }
  /** Looks again once the scroll has been quiet: moves if it must, else says it is settled. */
  function whenQuiet() {
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
  }
  // Our own scrolls fire scroll events too; they only restart the quiet clock.
  window.addEventListener('scroll', onScroll, { capture: true, passive: true });
  TAKEOVER_EVENTS.forEach((type) => window.addEventListener(type, takeOver, { capture: true, passive: true }));
  RECHECK_MS.forEach((ms) => {
    timers.push(window.setTimeout(() => {
      if (!live) return;
      rechecksLeft -= 1;
      if (align('auto')) say('settling');
      whenQuiet();
    }, ms));
  });
  // The window ends here, whatever the scroll is doing: after this the page is the learner's.
  timers.push(window.setTimeout(() => release('settled'), SETTLE_MS));

  say('settling');
  align(smooth ? 'smooth' : 'auto');
  whenQuiet();

  if (typeof ResizeObserver !== 'undefined') {
    // #665: every box whose size can move what is placed: the card, the sheet, the last
    // repair («Compare» is in it) and the whole feedback, which grows with anything that
    // mounts between them. A repair that mounts late is watched from its first look.
    const height = (el: HTMLElement | null) => (el ? Math.round(el.getBoundingClientRect().height) : -1);
    const sizes = () => [feedback, card, sheet, lastRepair()].map(height).join('|');
    let seen = sizes();
    const watched = new Set<HTMLElement>();
    const watch = (el: HTMLElement | null) => {
      if (!el || watched.has(el) || !observer) return;
      watched.add(el);
      observer.observe(el);
    };
    // A change in size is followed at once, not smoothly: the card is already on its way.
    // (A ResizeObserver also reports once when it starts; that is not a change.)
    observer = new ResizeObserver(() => {
      if (!live) return;
      watch(lastRepair());
      const now = sizes();
      if (now === seen) return;
      seen = now;
      align('auto');
      say('settling');
      whenQuiet();
    });
    [feedback, card, sheet, lastRepair()].forEach(watch);
  }
  return () => release();
}

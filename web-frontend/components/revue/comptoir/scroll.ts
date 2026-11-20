/**
 * The players' scroll (the counter's since 2026-10-19, «Le titre» and «L'intox express» since
 * 2026-11-20): a new screen starts at its top; on the same screen, after an act, the newest
 * part (`[data-ct-anchor]`) comes into the band between the sticky head and the sticky foot.
 */

/**
 * The element that scrolls the page: the nearest ancestor that scrolls, else the
 * document. The body's own `overflow-x: hidden` computes its `overflow-y` to `auto`
 * but, while `html` is `visible`, it is handed to the viewport (CSS overflow
 * propagation), so the body never scrolls itself: skipped then. In the native
 * shell (`overflow-x: clip`) the document scrolls too.
 */
export function scrollerOf(node: HTMLElement | null): HTMLElement | null {
  if (typeof window === 'undefined' || !node) return null;
  const root = document.documentElement;
  const rootStyle = window.getComputedStyle(root);
  const propagated = rootStyle.overflowX === 'visible' && rootStyle.overflowY === 'visible';
  for (let el: HTMLElement | null = node.parentElement; el && el !== root; el = el.parentElement) {
    if (el === document.body && propagated) continue;
    const style = window.getComputedStyle(el);
    if (/(auto|scroll)/.test(style.overflowY) && el.scrollHeight > el.clientHeight) return el;
  }
  return (document.scrollingElement as HTMLElement | null) ?? root;
}

/**
 * How far to scroll so a box (`top`, `bottom`) sits in the band (`bandTop`, `bandBottom`):
 * its top under the head (`start`), or just enough to show it whole above the foot
 * (`nearest`, never pushing its top under the head). 0 when it already fits.
 */
export function anchorDelta(top: number, bottom: number, bandTop: number, bandBottom: number, block: 'start' | 'nearest'): number {
  let delta = 0;
  if (block === 'start' || top < bandTop) delta = top - bandTop;
  else if (bottom > bandBottom) delta = Math.min(bottom - bandBottom, top - bandTop);
  return Math.abs(delta) < 2 ? 0 : delta;
}

/** Brings `node` into the band between the sticky head and the sticky foot. */
export function bringIntoView(node: HTMLElement, head: HTMLElement | null, foot: HTMLElement | null, block: 'start' | 'nearest') {
  const scroller = scrollerOf(node);
  if (!scroller) return;
  const rect = node.getBoundingClientRect();
  const top = (head?.getBoundingClientRect().bottom ?? 0) + 8;
  const bottom = (foot?.getBoundingClientRect().top ?? window.innerHeight) - 12;
  const delta = anchorDelta(rect.top, rect.bottom, top, bottom, block);
  if (!delta) return;
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  scroller.scrollBy({ top: delta, behavior: reduce ? 'auto' : 'smooth' });
}

/** The newest anchor under `body` brought into view (the last `[data-ct-anchor]`). */
export function bringNewestIntoView(body: HTMLElement | null, head: HTMLElement | null, foot: HTMLElement | null) {
  if (!body || typeof body.querySelectorAll !== 'function') return;
  const anchors = body.querySelectorAll<HTMLElement>('[data-ct-anchor]');
  const node = anchors[anchors.length - 1];
  if (!node || typeof node.getBoundingClientRect !== 'function') return;
  bringIntoView(node, head, foot, node.dataset.ctAnchor === 'start' ? 'start' : 'nearest');
}

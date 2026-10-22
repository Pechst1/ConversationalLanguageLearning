/**
 * #282 (live walk 22 Oct, phone size): on a miss the pink verdict sheet is stuck to the
 * bottom of the screen, and the correction, the field and «Compare» sit in the page above
 * it. Opened on the item's top, they were all behind the sheet, and «Compare» was
 * unreachable until the learner scrolled on their own.
 *
 * When a miss opens, the page scrolls just far enough for the last thing it asks of the
 * learner to stand clear above the sheet.
 */

/** How far to scroll down so an element ending at `anchorBottom` clears a sheet starting at
 *  `sheetTop` by `gap`; 0 when it already does (or there is nothing to clear). */
export function scrollToClearSheet(anchorBottom: number, sheetTop: number, gap = 12): number {
  if (!Number.isFinite(anchorBottom) || !Number.isFinite(sheetTop)) return 0;
  const behind = anchorBottom + gap - sheetTop;
  return behind > 0 ? Math.ceil(behind) : 0;
}

/** Scroll the page so the last repair (else the last correction) inside `feedback` clears its sheet. */
export function clearTheSheet(feedback: HTMLElement | null): void {
  if (!feedback || typeof window === 'undefined') return;
  const sheet = feedback.querySelector<HTMLElement>('.ep-foot');
  const anchors = feedback.querySelectorAll<HTMLElement>('.ep-repair, .ep-galley');
  const anchor = anchors.length ? anchors[anchors.length - 1] : null;
  if (!sheet || !anchor) return;
  const by = scrollToClearSheet(anchor.getBoundingClientRect().bottom, sheet.getBoundingClientRect().top);
  if (by > 0) window.scrollBy({ top: by, behavior: 'auto' });
}

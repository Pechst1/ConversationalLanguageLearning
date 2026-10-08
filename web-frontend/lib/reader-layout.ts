/**
 * WP-144 · which page the story reader draws: the current one (`list`, a plate
 * band with the lines as cards under it) or the vertical page (`vertical`, the
 * panel full-bleed with the lines as balloons in it). The one place that decides.
 *
 * Built like `lib/art-set.ts`, so the owner can compare the two blind:
 *
 * - The build default is `readerLayout` in `launch-flags.json`; absent means
 *   `vertical` (WP-144b: the vertical page won the owner's blind A/B once its
 *   three-speaker panels were fixed). `"readerLayout": "list"` brings the old page back
 *   for a build.
 * - A device can override it through the localStorage key `atelier.readerLayout`.
 * - `?readerLayout=list` (or `vertical`) on any URL sets that override and keeps it
 *   for the next pages — the way back to the old page; `?readerLayout=default` clears it.
 *
 * WP-144b: the default is only a wish. A scene the vertical page cannot stage —
 * the painted art set, or a panel whose speakers have no drawn figure — falls back
 * to the list for the whole scene (`sceneFitsVertical`), unless the device or the
 * URL asked for the vertical page explicitly.
 *
 * Components never read the flag, the key or the URL directly; they call
 * `useReaderLayout()` / `useReaderLayoutState()`.
 */
import { useEffect, useState } from 'react';
import launchFlags from '../launch-flags.json';

export type ReaderLayout = 'list' | 'vertical';
export const READER_LAYOUT_STORAGE_KEY = 'atelier.readerLayout';
export const READER_LAYOUT_QUERY = 'readerLayout';
const CHANGE_EVENT = 'atelier:reader-layout';

export function isReaderLayout(value: unknown): value is ReaderLayout {
  return value === 'list' || value === 'vertical';
}

/** The build default (`launch-flags.json`). Anything unknown means the vertical page. */
export function defaultReaderLayout(flags: Record<string, unknown> = launchFlags as Record<string, unknown>): ReaderLayout {
  const value = flags.readerLayout;
  return isReaderLayout(value) ? value : 'vertical';
}

/** This device's override, if any. */
export function storedReaderLayout(): ReaderLayout | null {
  if (typeof window === 'undefined') return null;
  try {
    const value = window.localStorage.getItem(READER_LAYOUT_STORAGE_KEY);
    return isReaderLayout(value) ? value : null;
  } catch {
    return null;
  }
}

/** Set this device's reader; `null` returns to the build default. */
export function setReaderLayout(value: ReaderLayout | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (value) window.localStorage.setItem(READER_LAYOUT_STORAGE_KEY, value);
    else window.localStorage.removeItem(READER_LAYOUT_STORAGE_KEY);
  } catch {
    /* storage refused: the build default stays */
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

/**
 * What a `?readerLayout=` value asks for: a layout to keep, `null` to clear the
 * override (`default`), `undefined` when the URL says nothing usable.
 */
export function readerLayoutFromQuery(search: string): ReaderLayout | null | undefined {
  let value: string | null = null;
  try {
    value = new URLSearchParams(search).get(READER_LAYOUT_QUERY);
  } catch {
    return undefined;
  }
  if (value === null) return undefined;
  if (value === 'default') return null;
  return isReaderLayout(value) ? value : undefined;
}

/** The layout to draw: the URL's ask, else this device's override, else the build default. */
export function readerLayout(): ReaderLayout {
  return storedReaderLayout() ?? defaultReaderLayout();
}

export type ReaderLayoutState = {
  layout: ReaderLayout;
  /** True when this device or the URL chose the layout (not the build default). */
  explicit: boolean;
};

function currentState(): ReaderLayoutState {
  const stored = storedReaderLayout();
  return { layout: stored ?? defaultReaderLayout(), explicit: stored !== null };
}

/**
 * The reader layout to render, and whether someone chose it. The first render
 * uses the build default (as the server does), then follows the URL, this
 * device's override and any later change.
 */
export function useReaderLayoutState(): ReaderLayoutState {
  const [value, setValue] = useState<ReaderLayoutState>(() => ({ layout: defaultReaderLayout(), explicit: false }));
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const asked = readerLayoutFromQuery(window.location.search);
      if (asked !== undefined) {
        try {
          if (asked) window.localStorage.setItem(READER_LAYOUT_STORAGE_KEY, asked);
          else window.localStorage.removeItem(READER_LAYOUT_STORAGE_KEY);
        } catch {
          /* storage refused: the URL still decides this page */
        }
        setValue(asked ? { layout: asked, explicit: true } : { layout: defaultReaderLayout(), explicit: false });
      } else {
        setValue(currentState());
      }
    }
    const sync = () => setValue(currentState());
    window.addEventListener(CHANGE_EVENT, sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener(CHANGE_EVENT, sync);
      window.removeEventListener('storage', sync);
    };
  }, []);
  return value;
}

/** The reader layout to render (see `useReaderLayoutState`). */
export function useReaderLayout(): ReaderLayout {
  return useReaderLayoutState().layout;
}

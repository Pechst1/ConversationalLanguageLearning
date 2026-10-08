/**
 * WP-116 · which art set shows the cast: the painted portraits and panels, or the
 * drawn SVG rigs. The one place that decides it.
 *
 * - The build default is `artSet` in `launch-flags.json`.
 * - A device can override it (Settings › Affichage › Personnages) through the
 *   localStorage key `atelier.artSet`, so the owner can swap back without a rebuild.
 *
 * Components never read the flag or the key directly; they call `useArtSet()`.
 */
import { useEffect, useState } from 'react';
import launchFlags from '../launch-flags.json';

export type ArtSet = 'painted' | 'drawn';
export const ART_SET_STORAGE_KEY = 'atelier.artSet';
const CHANGE_EVENT = 'atelier:art-set';

function isArtSet(value: unknown): value is ArtSet {
  return value === 'painted' || value === 'drawn';
}

/** The build default (`launch-flags.json`). Anything unknown means painted. */
export function defaultArtSet(): ArtSet {
  const value = (launchFlags as Record<string, unknown>).artSet;
  return isArtSet(value) ? value : 'painted';
}

/** This device's override, if any. */
export function storedArtSet(): ArtSet | null {
  if (typeof window === 'undefined') return null;
  try {
    const value = window.localStorage.getItem(ART_SET_STORAGE_KEY);
    return isArtSet(value) ? value : null;
  } catch {
    return null;
  }
}

export function artSet(): ArtSet {
  return storedArtSet() ?? defaultArtSet();
}

/** Set this device's art set; `null` returns to the build default. */
export function setArtSet(value: ArtSet | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (value) window.localStorage.setItem(ART_SET_STORAGE_KEY, value);
    else window.localStorage.removeItem(ART_SET_STORAGE_KEY);
  } catch {
    /* storage refused: the build default stays */
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

/**
 * The art set to render. The first render uses the build default (as the server
 * does), then follows this device's override and any later change.
 */
export function useArtSet(): ArtSet {
  const [value, setValue] = useState<ArtSet>(defaultArtSet);
  useEffect(() => {
    const sync = () => setValue(artSet());
    sync();
    window.addEventListener(CHANGE_EVENT, sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener(CHANGE_EVENT, sync);
      window.removeEventListener('storage', sync);
    };
  }, []);
  return value;
}

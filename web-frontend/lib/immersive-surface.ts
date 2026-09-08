/**
 * "An immersive surface is on screen" — a one-bit signal, shared.
 *
 * The feuilleton reader takes over the whole screen: it draws its own exit,
 * its own progress rail and its own action bar. Anything else that draws a
 * fixed exit, a fixed progress rule or a floating control has to stand down
 * while it is up, or the learner gets two identical marks with different
 * consequences (WP-20 D-4) and a legacy button sitting on the reader's own
 * action bar (WP-20 D-9).
 *
 * Deliberately a counter rather than a boolean: a reader can be replaced by
 * another reader in the same tick, and React mounts the next one before it
 * unmounts the previous. A boolean would flicker the chrome back on.
 */

import { useSyncExternalStore } from 'react';

let mounted = 0;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

/** Declare an immersive surface mounted. Returns the release for `useEffect`. */
export function enterImmersiveSurface(): () => void {
  mounted += 1;
  emit();
  let released = false;
  return () => {
    if (released) return;
    released = true;
    mounted = Math.max(0, mounted - 1);
    emit();
  };
}

export function isImmersiveSurface(): boolean {
  return mounted > 0;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * Server rendering has no mounted reader by definition, so the server snapshot
 * is a constant `false` and hydration matches the first client render.
 */
export function useImmersiveSurface(): boolean {
  return useSyncExternalStore(subscribe, isImmersiveSurface, () => false);
}

/**
 * What Home draws while it is still finding out which Home it is
 * (2026-09-24 walkthrough).
 *
 * Home has two kinds: the journey Home (WP-81 — the day's card, the plan row,
 * two chips) and the legacy, journey-off Home (the prescription, the Séance /
 * Lexique / Errata tiles). Which one a learner gets is the server's answer to
 * `GET /journey/today`, and that answer arrives *after* `GET /atelier/today`
 * and after the cached edition has been painted. Rendering Home before it
 * arrived drew the legacy Home — «Édition précédente · mise à jour en cours…»,
 * «Continuer le feuilleton», «Plus long que les 15 minutes demandées» — for a
 * second, in front of a learner who has never had it.
 *
 * The rule:
 *
 *   * While the kind is unknown, Home is the skeleton — unless this device's
 *     last Home was the legacy one, in which case the cached legacy edition is
 *     the same kind and may paint straight away, as it always did.
 *   * A journey Home is never preceded by the legacy one.
 *   * A load error is shown, not hidden behind a skeleton that never ends.
 *
 * The remembered kind lives under the `pilot:` prefix, so sign-out (and the
 * account-scope sweep) forgets it with the rest of the learner's caches.
 */

import { safeReadJson, safeWriteJson, type StorageLike } from '@/lib/pilot-resilience';

export type HomeKind = 'journey' | 'legacy';

export const HOME_KIND_KEY = 'pilot:home-kind:v1';

export function readHomeKind(storage?: StorageLike | null): HomeKind | null {
  const value = safeReadJson<unknown>(HOME_KIND_KEY, null, storage);
  return value === 'journey' || value === 'legacy' ? value : null;
}

export function rememberHomeKind(kind: HomeKind, storage?: StorageLike | null) {
  safeWriteJson(HOME_KIND_KEY, kind, storage);
}

/** The journey controller's phase kinds that settle the question. */
export function resolvedHomeKind(input: {
  journeyEnabled: boolean;
  journeyPhaseKind: string;
}): HomeKind | null {
  if (input.journeyEnabled) return 'journey';
  if (input.journeyPhaseKind === 'disabled') return 'legacy';
  // `loading` has not answered; `load_failed` is not an answer about the flag.
  return null;
}

export type HomeRender = 'skeleton' | 'home';

/**
 * Whether Home may render yet.
 *
 * `loading` is the page's own `/atelier/today` read with nothing cached;
 * `rememberedKind` is what this device's last settled Home was.
 */
export function homeRender(input: {
  loading: boolean;
  loadError: boolean;
  journeyEnabled: boolean;
  journeyPhaseKind: string;
  rememberedKind: HomeKind | null;
}): HomeRender {
  if (input.loading) return 'skeleton';
  if (input.loadError) return 'home';
  if (resolvedHomeKind(input)) return 'home';
  // The capability read failed outright: Home says so rather than waiting.
  if (input.journeyPhaseKind === 'load_failed') return 'home';
  // Still unknown. Only a learner whose last Home was the legacy one may see
  // the cached legacy edition now; everyone else sees the skeleton.
  return input.rememberedKind === 'legacy' ? 'home' : 'skeleton';
}

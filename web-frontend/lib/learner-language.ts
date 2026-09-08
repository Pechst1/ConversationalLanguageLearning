/**
 * The learner's own language, on screens that are not inside a journey envelope.
 *
 * `components/atelier-v2/journey/*` reads `control_language` straight off the
 * today envelope, and `AtelierV2Root` turns that into a copy table. Three
 * screens have no envelope — Le Lexique's review deck, Le Courrier and Le Studio
 * — so they had no way to know whether the person reading them speaks English,
 * German or French. Their failure toasts were therefore written once, in French,
 * for everyone (WP-21).
 *
 * The rule they now follow is the design contract's: the *fiction* and the
 * publication chrome stay French, and anything that **explains** something —
 * "the microphone was refused", "nothing was transcribed" — follows
 * `native_language`.
 *
 * Resolution is deliberately cheap and never blocks a render:
 *
 *  1. the value cached in `localStorage` by the last profile load, so the first
 *     paint is already right and an offline deck still reads correctly;
 *  2. one background `GET /users/me/settings`, which refreshes the cache;
 *  3. `en`, the signup default, when both are unavailable.
 */

import { useEffect, useState } from 'react';

import apiService from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { normalizeControlLanguage } from './atelier-v2-copy';

export const LEARNER_LANGUAGE_STORAGE_KEY = 'atelier.learnerLanguage';

/** Persist the language a profile response reported. Safe in private mode. */
export function rememberLearnerLanguage(value: unknown): ControlLanguage {
  const language = normalizeControlLanguage(value);
  try {
    window.localStorage.setItem(LEARNER_LANGUAGE_STORAGE_KEY, language);
  } catch {
    // Storage can be denied outright; the value simply is not cached.
  }
  return language;
}

/** The cached language, for a synchronous first render. Never throws. */
export function readLearnerLanguage(): ControlLanguage {
  try {
    return normalizeControlLanguage(window.localStorage.getItem(LEARNER_LANGUAGE_STORAGE_KEY));
  } catch {
    return 'en';
  }
}

/**
 * The learner's language for a page outside the journey envelope.
 *
 * Starts at `en` so the server and the first client render agree — reading
 * storage during render would be a hydration mismatch — then settles on the
 * cached value and finally on what the profile says.
 */
export function useLearnerLanguage(): ControlLanguage {
  const [language, setLanguage] = useState<ControlLanguage>('en');

  useEffect(() => {
    let alive = true;
    const cached = readLearnerLanguage();
    if (cached !== 'en') setLanguage(cached);

    void (async () => {
      try {
        const profile: any = await apiService.getSettings();
        if (!alive) return;
        const resolved = rememberLearnerLanguage(profile?.native_language);
        setLanguage(resolved);
      } catch {
        // An expired session or an offline deck keeps the cached answer.
      }
    })();

    return () => {
      alive = false;
    };
  }, []);

  return language;
}

export default useLearnerLanguage;

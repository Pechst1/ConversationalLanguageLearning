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
import { chromeLanguage, levelBand } from './language-rule';
import { oncePerLoad } from './once-per-load';

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

/** WP-82: the learner's CEFR estimate, cached next to the language. */
export const LEARNER_LEVEL_STORAGE_KEY = 'atelier.learnerLevel';

/** Persist the level a profile response reported. Safe in private mode. */
export function rememberLearnerLevel(value: unknown): string | null {
  const level = levelBand(value) && typeof value === 'string' ? value.trim().toUpperCase() : null;
  try {
    if (level) window.localStorage.setItem(LEARNER_LEVEL_STORAGE_KEY, level);
  } catch {
    // Storage can be denied outright; the value simply is not cached.
  }
  return level;
}

/** The cached level, for a synchronous first render. Never throws. */
export function readLearnerLevel(): string | null {
  try {
    const value = window.localStorage.getItem(LEARNER_LEVEL_STORAGE_KEY);
    return levelBand(value) ? value : null;
  } catch {
    return null;
  }
}

export type LearnerProfile = { language: ControlLanguage; level: string | null };

/**
 * The learner's language and CEFR estimate for a page outside the journey
 * envelope.
 *
 * Starts at `en` / unknown so the server and the first client render agree —
 * reading storage during render would be a hydration mismatch — then settles
 * on the cached values and finally on what the profile says (one coalesced
 * `GET /users/me/settings` per page load, however many rows ask).
 */
export function useLearnerProfile(): LearnerProfile {
  const [profile, setProfile] = useState<LearnerProfile>({ language: 'en', level: null });

  useEffect(() => {
    let alive = true;
    const cached: LearnerProfile = { language: readLearnerLanguage(), level: readLearnerLevel() };
    if (cached.language !== 'en' || cached.level) setProfile(cached);

    void (async () => {
      try {
        const settings: any = await oncePerLoad('users/me/settings', () => apiService.getSettings());
        if (!alive) return;
        setProfile({
          language: rememberLearnerLanguage(settings?.native_language),
          level: rememberLearnerLevel(settings?.cefr_estimate) ?? cached.level,
        });
      } catch {
        // An expired session or an offline deck keeps the cached answer.
      }
    })();

    return () => {
      alive = false;
    };
  }, []);

  return profile;
}

/**
 * The learner's own language, whatever the level — for text that *explains* a
 * failure (a refused microphone) and for the WP-L10 rule card.
 */
export function useLearnerLanguage(): ControlLanguage {
  return useLearnerProfile().language;
}

/**
 * WP-82 — the chrome language of a screen outside the journey envelope: the
 * learner's language up to A2, French from B1 (`lib/language-rule.ts`).
 * `level` overrides the profile's estimate when the screen knows better; an
 * unknown level reads as a beginner's.
 */
export function useChromeLanguage(level?: unknown): ControlLanguage {
  const profile = useLearnerProfile();
  return chromeLanguage(profile.language, levelBand(level) ? level : profile.level);
}

export default useLearnerLanguage;


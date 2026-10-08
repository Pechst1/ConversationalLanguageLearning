/**
 * WP-75 — the language the signed-out screens explain themselves in.
 *
 * Before an account exists there is no `native_language` to read, so the
 * landing, the taste and the sign-up guess it from the browser and let the
 * learner switch. The guess is only ever one of the three languages the app
 * explains itself in (en / de / fr); anything else lands on English. The
 * choice is remembered for the session and sent at sign-up as
 * `native_language`, so the first journey already speaks it.
 *
 * Story content (Romy's lines) and navigation labels stay French regardless.
 */

export type OnboardingLanguage = 'en' | 'de' | 'fr';

export const ONBOARDING_LANGUAGES: OnboardingLanguage[] = ['en', 'de', 'fr'];

export const ONBOARDING_LANGUAGE_LABELS: Record<OnboardingLanguage, string> = {
  en: 'English',
  de: 'Deutsch',
  fr: 'Français',
};

export const ONBOARDING_LANGUAGE_STORAGE_KEY = 'atelier.onboardingLanguage';

/** The primary subtag of one BCP 47 tag, if it is one of ours. */
export function onboardingLanguageOf(tag: unknown): OnboardingLanguage | null {
  if (typeof tag !== 'string') return null;
  const base = tag.trim().toLowerCase().replace('_', '-').split('-')[0];
  return (ONBOARDING_LANGUAGES as string[]).includes(base) ? (base as OnboardingLanguage) : null;
}

/**
 * The first of the browser's preferred languages that we speak.
 * `navigator.languages` is ordered by preference, so a German speaker whose
 * list reads `['de-AT', 'en']` gets German, not English.
 */
export function detectOnboardingLanguage(
  languages: readonly unknown[] | null | undefined,
  fallback: OnboardingLanguage = 'en',
): OnboardingLanguage {
  for (const tag of languages ?? []) {
    const hit = onboardingLanguageOf(tag);
    if (hit) return hit;
  }
  return fallback;
}

/** The browser's language list, never throwing (SSR, locked-down webviews). */
function browserLanguages(): string[] {
  try {
    if (typeof navigator === 'undefined') return [];
    if (Array.isArray(navigator.languages) && navigator.languages.length > 0) {
      return [...navigator.languages];
    }
    return navigator.language ? [navigator.language] : [];
  } catch {
    return [];
  }
}

/** A stored explicit choice wins over the browser's guess. */
export function readOnboardingLanguage(): OnboardingLanguage {
  try {
    const stored = onboardingLanguageOf(window.localStorage.getItem(ONBOARDING_LANGUAGE_STORAGE_KEY));
    if (stored) return stored;
  } catch {
    // Storage can be refused outright; the browser's guess stands.
  }
  return detectOnboardingLanguage(browserLanguages());
}

export function rememberOnboardingLanguage(language: OnboardingLanguage): void {
  try {
    window.localStorage.setItem(ONBOARDING_LANGUAGE_STORAGE_KEY, language);
  } catch {
    // Not remembered; the switch still works for this screen.
  }
}

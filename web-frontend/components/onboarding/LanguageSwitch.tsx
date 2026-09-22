/**
 * WP-75 — the signed-out language: guessed from the browser, switchable.
 *
 * Renders `en` on the server and first client paint (no hydration mismatch),
 * then settles on the stored choice or the browser's guess.
 */

import React from 'react';

import {
  ONBOARDING_LANGUAGES,
  readOnboardingLanguage,
  rememberOnboardingLanguage,
  type OnboardingLanguage,
} from '@/lib/onboarding-locale';

export function useOnboardingLanguage(): [OnboardingLanguage, (next: OnboardingLanguage) => void] {
  const [language, setLanguage] = React.useState<OnboardingLanguage>('en');
  React.useEffect(() => {
    setLanguage(readOnboardingLanguage());
  }, []);
  const choose = React.useCallback((next: OnboardingLanguage) => {
    rememberOnboardingLanguage(next);
    setLanguage(next);
  }, []);
  return [language, choose];
}

/** Three quiet letters, «EN · DE · FR». The current one is pressed. */
export function LanguageSwitch({
  value,
  onChange,
  label,
}: {
  value: OnboardingLanguage;
  onChange: (next: OnboardingLanguage) => void;
  /** Group name, in the current language. */
  label: string;
}) {
  return (
    <div className="ob-lang" role="group" aria-label={label}>
      {ONBOARDING_LANGUAGES.map((code) => (
        <button
          key={code}
          type="button"
          className="ob-lang__opt"
          aria-pressed={code === value}
          lang={code}
          onClick={() => onChange(code)}
        >
          {code.toUpperCase()}
        </button>
      ))}
      <style jsx>{`
        .ob-lang {
          display: inline-flex;
          gap: 2px;
          padding: 2px;
          border-radius: 999px;
          background: var(--av2-line);
        }
        .ob-lang__opt {
          min-width: 44px;
          min-height: 32px;
          padding: 0 10px;
          border: 0;
          border-radius: 999px;
          background: transparent;
          font: inherit;
          font-size: var(--av2-t-meta);
          font-weight: 700;
          color: var(--av2-muted);
          cursor: pointer;
        }
        .ob-lang__opt[aria-pressed='true'] {
          background: var(--av2-paper);
          color: var(--av2-ink);
        }
      `}</style>
    </div>
  );
}

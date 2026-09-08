/**
 * The scope boundary for the Atelier V2 design system (WP-01).
 *
 * Everything in `styles/atelier-v2.css` is scoped under `.av2`, so a page that
 * does not render this component is untouched by the visual migration. That is
 * the whole isolation strategy: no `:root` tokens, no element selectors, no
 * reset — one class, applied here.
 *
 * Light / dark / system is handled by CSS alone, keyed off the `data-theme`
 * attribute `lib/app-preferences.ts` already writes on `<html>`. Nothing here
 * reads `window`, so there is no hydration mismatch and no theme flash. The
 * `forceTheme` prop exists only for the dev gallery, which must show both.
 *
 * Text size likewise needs no code: every size in the stylesheet is `rem`, so
 * `:root[data-font-size]` (14.5 / 16 / 19px) moves this screen as it moves the
 * rest of the app.
 */

import React, { createContext, useContext, useMemo } from 'react';

import { atelierCopy, normalizeControlLanguage, type AtelierCopy } from '@/lib/atelier-v2-copy';
import type { ControlLanguage } from '@/types/daily-journey';

type AtelierContextValue = {
  copy: AtelierCopy;
  language: ControlLanguage;
};

const AtelierContext = createContext<AtelierContextValue | null>(null);

/**
 * The copy table for the current control language.
 *
 * Falls back to English rather than throwing when a primitive is rendered
 * outside a root — a missing provider must not be able to blank a screen.
 */
export function useAtelierCopy(): AtelierCopy {
  return useContext(AtelierContext)?.copy ?? atelierCopy('en');
}

export function useControlLanguage(): ControlLanguage {
  return useContext(AtelierContext)?.language ?? 'en';
}

export type AtelierV2RootProps = {
  /** Any tag; `main` for a screen, `div` for a fragment inside a legacy page. */
  as?: 'div' | 'main' | 'section' | 'article';
  /** Learner control language. Regional tags and nulls are normalized. */
  language?: unknown;
  /** Dev gallery only. Production reads the real theme attribute from `<html>`. */
  forceTheme?: 'light' | 'dark';
  className?: string;
  children: React.ReactNode;
} & Omit<React.HTMLAttributes<HTMLElement>, 'children' | 'className'>;

export function AtelierV2Root({
  as: Tag = 'div',
  language,
  forceTheme,
  className,
  children,
  ...rest
}: AtelierV2RootProps) {
  const resolved = normalizeControlLanguage(language);
  const value = useMemo<AtelierContextValue>(
    () => ({ copy: atelierCopy(resolved), language: resolved }),
    [resolved],
  );

  const classes = [
    'av2',
    forceTheme === 'dark' ? 'av2--dark' : null,
    // `.av2--light` carries no tokens: it opts out of the contextual dark
    // selectors, so the light block already on `.av2` simply stands.
    forceTheme === 'light' ? 'av2--light' : null,
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <AtelierContext.Provider value={value}>
      <Tag className={classes} {...rest}>
        {children}
      </Tag>
    </AtelierContext.Provider>
  );
}

export default AtelierV2Root;

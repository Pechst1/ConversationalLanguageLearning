/**
 * «Le bilan» in the dev gallery — DEVELOPMENT ONLY (imported by
 * `pages/atelier-v2-gallery.tsx`, which is `notFound` in production).
 *
 *   /atelier-v2-gallery?bilan=full|thin|empty|card&lang=en|de|fr&theme=light|dark
 *
 * The real page (`pages/bilan.tsx`) sits behind sign-in, so the screenshots in the PR
 * are taken here: the same `BilanView` and `BilanCardView`, the same page frame and
 * classes, with the wire fixtures of `bilan-fixtures.ts` run through the real parser.
 */

import React from 'react';

import { ArrowLeftIcon, AtelierV2Root, IconAction } from '@/components/atelier-v2/ui';
import { parseBilan, type BilanLanguage } from '@/lib/bilan-types';

import { BilanCardView } from './BilanHomeCard';
import { BilanView } from './BilanView';
import { bilanCopy } from './bilan-copy';
import { bilanFixture } from './bilan-fixtures';

export type BilanGalleryState = 'full' | 'thin' | 'empty' | 'card';

export function isBilanGalleryState(value: unknown): value is BilanGalleryState {
  return value === 'full' || value === 'thin' || value === 'empty' || value === 'card';
}

export function BilanGalleryScreen({
  state,
  language,
  theme,
}: {
  state: BilanGalleryState;
  language: BilanLanguage;
  theme: 'light' | 'dark';
}) {
  const copy = bilanCopy(language);
  const bilan = parseBilan(bilanFixture(state === 'card' ? 'full' : state, language));
  return (
    <AtelierV2Root as="main" language={language} forceTheme={theme} className="bl-page" aria-label={copy.page_title}>
      <div className="bl-top">
        <IconAction label={copy.back} onClick={() => undefined}>
          <ArrowLeftIcon size={18} />
        </IconAction>
        <p className="bl-top__name">{copy.page_title}</p>
      </div>
      <div className="bl-body">
        {state === 'card' ? (
          <BilanCardView card={{ weekStart: bilan.weekStart, daysPlayed: bilan.daysPlayed }} language={language} copy={copy} onDismiss={() => undefined} />
        ) : (
          <BilanView bilan={bilan} copy={copy} onContinue={() => undefined} hrefFor={() => '#'} />
        )}
      </div>
    </AtelierV2Root>
  );
}

/**
 * Home's daily news card (owner, 2026-10-18: «it's not indicated that it's the
 * news-based feature… a little cute sticker… with an exclamation mark»).
 *
 * Under the day's card, every day until today's Papier is filed (`lib/revue-une.ts`
 * decides when): the story's picture, the «À la une !» sticker on its corner and the
 * headline in six words or fewer (the dossier's `headline_fr`, else its title). The
 * whole card is the link; its label says what it is in the learner's language. The
 * sticker pops in once (still under Reduce Motion).
 *
 * WP-81's word budget: the card spends at most nine words (the sticker's three and
 * the headline's six) and takes the place of the «Le Papier» chip.
 */

import React from 'react';

import { ArrowRightIcon } from '@/components/atelier-v2/ui';
import { resolveMediaUrl } from '@/lib/media-url';
import type { RvStoryCard } from '@/lib/revue-types';

import { fill, type RevueCopy } from './revue-copy';

export type RvNewsCardProps = {
  story: RvStoryCard;
  href: string;
  copy: RevueCopy;
  /** Client-side navigation; without it the link navigates. */
  onOpen?: () => void;
};

/** The headline the card prints: the six-word one, else the story's title. */
export function newsHeadline(story: Pick<RvStoryCard, 'headlineFr' | 'titleFr'>): string {
  return (story.headlineFr || '').trim() || story.titleFr;
}

/** The red press sticker, tilted, with three yellow sparks: «À la une !». */
export function RvNewsSticker({ label }: { label: string }) {
  return (
    <span className="rv-news__sticker" aria-hidden="true">
      {label}
      <svg className="rv-news__spark" viewBox="0 0 16 16" focusable="false">
        <path d="M3 9.5 0.8 11.2M5.6 5.4 4.6 2.6M10 4.6 12.2 2.4" />
      </svg>
    </span>
  );
}

export function RvNewsCard({ story, href, copy, onOpen }: RvNewsCardProps) {
  const headline = newsHeadline(story);
  const plate = story.plateUrl ?? story.stage.plateUrl;
  const src = plate ? resolveMediaUrl(plate) ?? plate : null;
  return (
    <a
      className="rv-news"
      href={href}
      data-revue-card="news"
      aria-label={fill(copy.news_aria, { headline })}
      onClick={(event) => {
        if (!onOpen) return;
        event.preventDefault();
        onOpen();
      }}
    >
      <span className="rv-news__pic" aria-hidden="true">
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt="" decoding="async" loading="lazy" />
        ) : (
          <span className="rv-news__pic-fallback" />
        )}
      </span>
      <RvNewsSticker label={copy.news_sticker} />
      <span className="rv-news__hl" lang="fr" aria-hidden="true">
        {headline}
      </span>
      <span className="rv-news__go" aria-hidden="true">
        <ArrowRightIcon size={18} />
      </span>
    </a>
  );
}

export default RvNewsCard;

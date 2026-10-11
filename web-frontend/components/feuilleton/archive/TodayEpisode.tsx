/**
 * WP-109 «Une seule maison»: the Feuilleton opens on today's episode, then the
 * archive and the cast. One tap reads it: the day starts, or resumes where it is.
 *
 * The headline is the server's (`TodayEnvelope.headline`): the episode's number,
 * its title when known, yesterday's «À suivre…» and who is in it. When there is no
 * episode to read today (the day is over, or the story is between seasons) the card
 * is absent: the finished day is already the archive's newest page.
 */

import Link from 'next/link';
import React, { useEffect, useState } from 'react';

import { ArrowRightIcon } from '@/components/atelier-v2/ui';
import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import { readerCopy } from '@/components/feuilleton/reader/reader-copy';
import {
  headlineKicker,
  headlineTeaser,
  headlineTitle,
  TODAY_EPISODE_HREF,
  type EpisodeHeadline,
} from '@/lib/episode-headline';
import { frenchQuote, frenchSpacing } from '@/lib/french-typography';
import apiService from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { archiveCopy } from './archive-copy';

export function useTodayHeadline(): EpisodeHeadline | null {
  const [headline, setHeadline] = useState<EpisodeHeadline | null>(null);
  useEffect(() => {
    let live = true;
    void apiService
      .getDailyJourneyToday()
      .then((today) => {
        if (live) setHeadline(today?.headline ?? null);
      })
      .catch(() => {
        /* the archive stands on its own; no card is not an error */
      });
    return () => {
      live = false;
    };
  }, []);
  return headline;
}

export function TodayEpisode({
  headline,
  language,
}: {
  headline: EpisodeHeadline | null;
  language: ControlLanguage | null;
}) {
  if (!headline) return null;
  const t = archiveCopy(language);
  const title = headlineTitle(headline);
  const teaser = headlineTeaser(headline, title);
  const kicker = [t.today_kicker, headlineKicker(headline)].filter(Boolean).join(' · ');
  return (
    <section className="fa-today" data-today-episode="" aria-label={t.today_kicker}>
      <p className="av2-label av2-label--story">{kicker}</p>
      {title && (
        <h2 className="av2-headline av2-headline--title" lang="fr">
          {frenchSpacing(title)}
        </h2>
      )}
      {teaser && (
        <p className="av2-body">
          <span className="av2-label">{readerCopy(language).to_follow}</span>{' '}
          <span className="av2-fr" lang="fr">
            {frenchQuote(teaser)}
          </span>
        </p>
      )}
      {headline.cast.length > 0 && (
        <ul className="fa-today__cast" aria-label={headline.cast.map((member) => member.name).join(', ')}>
          {headline.cast.map((member) => (
            <li key={member.id}>
              <CastPortrait characterId={member.id} name={member.name} size="xs" alt={member.name} />
            </li>
          ))}
        </ul>
      )}
      <Link className="av2-btn av2-btn--primary" data-press="3d" href={TODAY_EPISODE_HREF}>
        {t.today_open} <ArrowRightIcon size={18} />
      </Link>
    </section>
  );
}

export default TodayEpisode;

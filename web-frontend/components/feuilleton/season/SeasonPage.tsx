/**
 * «La saison» — the Feuilleton tab (WP-44, `Feuilleton.dc.html`).
 *
 * The tab used to apologise: a striped placeholder and «L'illustration de cet
 * épisode n'est pas encore parue» in place of a page. It now tells the season
 * back to the learner with what the story already knows — the scene waiting in
 * today's séance, the promises still open, and every episode they have read,
 * each with the art of the place it happened in.
 *
 * Three rules it keeps:
 *   · it starts nothing. The one button routes into the séance, which is where
 *     a scene is actually played; this page never creates or advances anything.
 *   · it shows no picture it does not have. A row without art gets no art, not
 *     a hatched rectangle standing in for one.
 *   · when nothing has been read it says so in one sentence, and stops.
 */

import React from 'react';
import Link from 'next/link';

import { Action, ArrowRightIcon } from '@/components/atelier-v2/ui';
import { resolveMediaUrl } from '@/lib/media-url';

import {
  seasonEpisodeMeta,
  seasonHasNothingRead,
  seasonStoryLabel,
  seasonThreadLabel,
  seasonThreads,
  seasonTodayLabel,
  type SeasonEpisode,
  type SeasonPayload,
} from './season-model';

export function SeasonPage({
  season,
  onOpenSeance,
}: {
  season: SeasonPayload;
  /** Routes into the daily séance. The only action on this screen. */
  onOpenSeance: () => void;
}) {
  const label = seasonStoryLabel(season);
  const today = season.today;
  const todayArt = today ? resolveMediaUrl(today.image_url) : null;
  const threads = seasonThreads(season);

  return (
    <section className="wp44-season" aria-label="La saison">
      {label && <p className="av2-label av2-label--story">{label}</p>}
      <h1 className="av2-headline av2-headline--screen">La saison jusqu’ici</h1>

      {today && (
        <article className="wp44-today">
          {todayArt && (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img src={todayArt} alt="" />
          )}
          <div className="wp44-today__body">
            <p className="av2-label av2-label--story">{seasonTodayLabel(today)}</p>
            <h2 className="wp44-today__title" lang="fr">
              {today.title_fr}
            </h2>
            {today.brief_fr && (
              <p className="av2-body" lang="fr">
                {today.brief_fr}
              </p>
            )}
            <div className="wp44-today__action">
              <Action tone="story" onClick={onOpenSeance} iconAfter={<ArrowRightIcon size={18} />}>
                Ouvrir la séance
              </Action>
            </div>
          </div>
        </article>
      )}

      {season.commitments.length > 0 && (
        <div className="wp44-commitment">
          <p className="wp44-commitment__label">
            {season.commitments.length > 1 ? 'Engagements en cours' : 'Engagement en cours'}
          </p>
          {season.commitments.map((commitment) => (
            <p className="wp44-commitment__text" lang="fr" key={commitment.id || commitment.text_fr}>
              {commitment.text_fr}
            </p>
          ))}
        </div>
      )}

      {threads.length > 0 && (
        <div className="wp44-threads" data-season-threads="true">
          <p className="av2-label av2-label--story">Les fils de la saison</p>
          <ul className="wp44-threads__list">
            {threads.map((thread) => (
              <li className="wp44-threads__row" key={thread.key} data-thread-state={thread.state}>
                <span className="wp44-threads__text" lang="fr">
                  {thread.text_fr}
                </span>
                <span className="wp44-threads__state">{seasonThreadLabel(thread.state)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {seasonHasNothingRead(season) ? (
        <p className="av2-body" data-season-empty="true">
          Votre première scène s’ouvre dans la séance.
        </p>
      ) : (
        <ul className="wp44-read">
          {season.read_episodes.map((episode) => (
            <li key={episode.scene_id}>
              <ReadRow episode={episode} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ReadRow({ episode }: { episode: SeasonEpisode }) {
  const art = resolveMediaUrl(episode.image_url);
  const meta = seasonEpisodeMeta(episode);
  return (
    <Link className="wp44-read__row" href={`/graphic-novel?scene=${encodeURIComponent(episode.scene_id)}`}>
      {art ? (
        /* eslint-disable-next-line @next/next/no-img-element */
        <img className="wp44-read__art" src={art} alt="" />
      ) : (
        <span className="wp44-read__art" aria-hidden="true" />
      )}
      <span className="wp44-read__text">
        <span className="av2-label">Épisode {episode.number}</span>
        <span className="wp44-read__title" lang="fr">
          {episode.title_fr}
        </span>
        {meta && <span className="wp44-read__meta">{meta}</span>}
      </span>
      <ArrowRightIcon size={18} />
    </Link>
  );
}

export default SeasonPage;

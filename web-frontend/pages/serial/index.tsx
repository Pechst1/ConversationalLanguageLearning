/* "Le feuilleton" — the season list.
 *
 * This screen exists verbatim in the Claude design (Atelier App.dc.html, the
 * FEUILLETON artboard): kicker, one Garamond italic headline, a blue story hero
 * for the current episode with a paper-on-blue 3D press, then read episodes as
 * paper rows with an ink "done" badge.
 *
 * Every row is a real server episode. The design also shows a locked "Épisode 4
 * · demain" row; the API publishes no future episode, so none is drawn — a
 * padlock for a chapter that may not exist would be a promise the product
 * cannot keep.
 *
 * WP-82: the page's own words follow the one language rule
 * (`components/feuilleton/feuilleton-copy.ts`, `useChromeLanguage()`); the
 * episode titles and hooks are story and stay French. */

import { useEffect, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import PhoneProductNav from '@/components/layout/PhoneProductNav';
import { FeuilletonReaderStyles } from '@/components/feuilleton/reader';
import { ArrowRightIcon, AtelierV2Root, CheckIcon } from '@/components/atelier-v2/ui';
import apiService, { SerialArchiveEpisode, SerialToday } from '@/services/api';
import { getStoryEpisodes } from '@/services/daily-journey';
import type { StoryEpisode } from '@/types/daily-journey';
import { resolveMediaUrl } from '@/lib/media-url';
import { CrEnvelope, crReadAndReplyLabel } from '@/components/courrier/Courrier';
import { fbFill, fbPlural, feuilletonCopy, type FeuilletonCopy } from '@/components/feuilleton/feuilleton-copy';
import { useChromeLanguage } from '@/lib/learner-language';

type CurrentEpisode = (SerialToday & Record<string, any>) | null;

function episodeNumber(index: number | null | undefined, t: FeuilletonCopy): string {
  return typeof index === 'number' ? fbFill(t.episode_n, { n: index + 1 }) : t.episode;
}

function firstText(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
}

/* The route that actually continues the story, built from the server's own
   thread/episode references. Never a guess. */
function continueHref(episode: CurrentEpisode): string | null {
  // Engine-managed learners continue through today's journey, never through a
  // scene route the engine has not published (ENGINE-FRONTEND-CONTRACT §5).
  if (episode && String(episode.status || '') === 'journey_required') {
    return String((episode as any).continue_href || '/atelier');
  }
  if (!episode?.thread_id || typeof episode.episode_index !== 'number') return null;
  const params = new URLSearchParams({
    serial_thread_id: episode.thread_id,
    episode_index: String(episode.episode_index),
  });
  if (episode.kind === 'mission') {
    if (episode.mission_id) params.set('mission', episode.mission_id);
    return `/missions?${params.toString()}`;
  }
  if (episode.scene_id) params.set('scene', episode.scene_id);
  return `/graphic-novel?${params.toString()}`;
}

function archiveHref(episode: SerialArchiveEpisode): string {
  if (episode.kind === 'mission' && episode.mission_id) {
    return `/missions?mission=${encodeURIComponent(episode.mission_id)}`;
  }
  if (episode.scene_id) return `/graphic-novel?scene=${encodeURIComponent(episode.scene_id)}`;
  return `/serial/episode?index=${episode.episode_index}`;
}

export default function SerialSeasonPage() {
  const language = useChromeLanguage();
  const t = feuilletonCopy(language);
  const [episodes, setEpisodes] = useState<SerialArchiveEpisode[]>([]);
  const [current, setCurrent] = useState<CurrentEpisode>(null);
  const [threadId, setThreadId] = useState<string>('');
  const [seasonNumber, setSeasonNumber] = useState(1);
  const [storyEpisodes, setStoryEpisodes] = useState<StoryEpisode[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    apiService.getSerialEpisodes()
      .then(async (payload) => {
        if (!alive) return;
        setEpisodes(payload.episodes || []);
        setSeasonNumber(Number(payload.season_number || 1));
        setCurrent((payload.current_episode as CurrentEpisode) || null);
        setThreadId(String(payload.thread_id || ''));
        // Generated episodes live in the story-engine projection. A GET only:
        // it neither generates nor completes anything.
        if ((payload.current_episode as any)?.story_engine) {
          try {
            const page = await getStoryEpisodes();
            if (alive) setStoryEpisodes(page.episodes || []);
          } catch {
            /* the legacy rows still render; the generated list is additive */
          }
        }
      })
      .catch((error) => {
        console.error(error);
        if (alive) {
          setEpisodes([]);
          setCurrent(null);
          setFailed(true);
        }
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const filed = episodes.length + storyEpisodes.filter((entry) => entry.status !== 'available').length;
  // The hero is the current episode only while it is genuinely still open.
  const heroEpisode: CurrentEpisode =
    current && current.status !== 'completed'
      ? { ...current, thread_id: current.thread_id || threadId }
      : null;
  const heroHref = continueHref(heroEpisode);
  const heroArt = resolveMediaUrl(
    firstText(
      (heroEpisode as any)?.lead_image_url,
      (heroEpisode as any)?.thumbnail_url,
    ),
  );
  const heroTitle = firstText(
    heroEpisode?.hook?.text,
    heroEpisode?.hook?.teaser,
    heroEpisode?.brief_payload?.title,
    heroEpisode?.previously,
  );
  const heroIsJourney = String(heroEpisode?.status || '') === 'journey_required';
  // WP-D7: a letter waiting in the Courrier is drawn as the sealed envelope,
  // with its sender's face as the seal — a letter has no illustration.
  const heroIsLetter = !heroIsJourney && heroEpisode?.kind === 'mission';
  const heroBrief = (heroEpisode?.brief_payload || {}) as Record<string, any>;
  const heroSender = firstText(...(Array.isArray(heroBrief.required_cast) ? heroBrief.required_cast : []));
  const heroSenderName = firstText(heroBrief.correspondent_name, heroBrief.character_name);
  const heroCta = heroIsJourney
    ? t.continue_day
    : heroIsLetter
      ? // The serial payload carries no reading time; no minutes are invented.
        crReadAndReplyLabel(null, language)
      : t.read_reply;

  return (
    <>
      <Head>
        <title>Le feuilleton · L’Atelier</title>
      </Head>
      <FeuilletonReaderStyles />
      <AtelierV2Root as="main" language={language} className="fr-page" aria-label={t.feuilleton}>
        <header className="fr-page-head">
          <div className="k">
            {loading ? t.season_opening : fbPlural(t, 'season_count', filed, { season: seasonNumber })}
          </div>
          {/* the one Garamond italic headline on this screen */}
          <h1>Le feuilleton</h1>
        </header>

        {loading ? (
          <div className="fr-skeleton" aria-live="polite" aria-busy="true">
            <span className="fr-sr">{t.season_loading}</span>
            <i />
            <i />
            <i />
          </div>
        ) : failed ? (
          <div className="fr-empty" role="status">
            <h2>{t.season_failed_title}</h2>
            <p>{t.season_failed_body}</p>
            <button
              type="button"
              className="fr-btn is-action"
              data-press="3d"
              onClick={() => window.location.reload()}
            >
              {t.retry} <ArrowRightIcon size={18} />
            </button>
          </div>
        ) : (
          <>
            {heroEpisode && heroHref && (
              <section className="fr-hero" aria-label={t.current_aria}>
                <div className="art">
                  {heroIsLetter ? (
                    <CrEnvelope senderId={heroSender} senderName={heroSenderName} language={language} />
                  ) : heroArt ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={heroArt} alt="" />
                  ) : (
                    <span>{t.illustration_missing}</span>
                  )}
                </div>
                <div className="body">
                  <div className="k">
                    {heroIsJourney
                      ? `${t.feuilleton} · ${t.kicker_today}`
                      : `${episodeNumber(heroEpisode.episode_index, t)} · ${heroEpisode.status === 'delayed' ? t.kicker_delayed : t.kicker_today}`}
                  </div>
                  {heroIsJourney ? (
                    <h2>{t.toast_in_journey}</h2>
                  ) : heroTitle ? (
                    <h2 lang="fr">{heroTitle}</h2>
                  ) : (
                    <h2>{t.hero_fallback}</h2>
                  )}
                  {/* the one tactile 3D press on this screen */}
                  <Link className="cta" href={heroHref}>
                    {heroCta} <ArrowRightIcon size={18} />
                  </Link>
                </div>
              </section>
            )}

            {storyEpisodes.length > 0 && (
              <div className="fr-rows" aria-label={t.generated_aria}>
                {storyEpisodes.map((entry) => {
                  const settled = entry.status !== 'available';
                  return (
                    <Link
                      className="fr-row"
                      href={`/graphic-novel?scene=${encodeURIComponent(entry.id)}`}
                      key={entry.id}
                    >
                      <span className="thumb" aria-hidden="true" />
                      <span className="meta">
                        <span className="k">
                          {entry.chapter?.title_fr || t.feuilleton} ·{' '}
                          {settled ? (entry.status === 'completed' ? t.status_read : t.status_abandoned) : t.status_open}
                        </span>
                        <span className="t">{entry.title_fr || t.episode}</span>
                      </span>
                      {settled ? (
                        <span className="done" aria-hidden="true">
                          <CheckIcon size={14} />
                        </span>
                      ) : (
                        <span className="go" aria-hidden="true"><ArrowRightIcon size={18} /></span>
                      )}
                    </Link>
                  );
                })}
              </div>
            )}

            {episodes.length > 0 ? (
              <div className="fr-rows">
                {[...episodes]
                  .sort((left, right) => right.episode_index - left.episode_index)
                  .map((episode) => {
                    const thumb = resolveMediaUrl(episode.thumbnail_url);
                    // The row is titled with the episode's title; the hook (its last line or
                    // resolution) only stands in when no title was published.
                    const title = firstText(episode.title, episode.hook_text, t.episode_filed);
                    return (
                      <Link className="fr-row" href={archiveHref(episode)} key={episode.id}>
                        <span className="thumb">
                          {thumb ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={thumb} alt="" />
                          ) : null}
                        </span>
                        <span className="meta">
                          <span className="k">{episodeNumber(episode.episode_index, t)} · {t.status_read}</span>
                          <span className="t">{title}</span>
                        </span>
                        <span className="done" aria-hidden="true">
                          <CheckIcon size={14} />
                        </span>
                      </Link>
                    );
                  })}
              </div>
            ) : (
              !heroEpisode && storyEpisodes.length === 0 && (
                <div className="fr-empty">
                  <h2>{t.first_title}</h2>
                  <p>{t.first_body}</p>
                  <Link className="fr-btn is-action" data-press="3d" href="/graphic-novel">
                    {t.open_first} <ArrowRightIcon size={18} />
                  </Link>
                </div>
              )
            )}

            <div className="fr-rows">
              <Link className="fr-row" href="/serial/cast">
                <span className="thumb" aria-hidden="true" />
                <span className="meta">
                  <span className="k">{t.cast_register}</span>
                  <span className="t">Les personnages</span>
                </span>
                <span className="go" aria-hidden="true"><ArrowRightIcon size={18} /></span>
              </Link>
            </div>
          </>
        )}
      </AtelierV2Root>
      <PhoneProductNav active="feuilleton" />
      <style jsx global>{`
        body { background: var(--app-paper); }
        .av2.fr-page { min-height: 100vh; padding-bottom: calc(var(--phone-bottom-nav-space, 88px)); }
      `}</style>
    </>
  );
}

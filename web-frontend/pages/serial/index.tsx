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
 * cannot keep. */

import { useEffect, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { ArrowRight, Check } from 'lucide-react';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import { FeuilletonReaderStyles } from '@/components/feuilleton/reader';
import apiService, { SerialArchiveEpisode, SerialToday } from '@/services/api';
import { resolveMediaUrl } from '@/lib/media-url';

type CurrentEpisode = (SerialToday & Record<string, any>) | null;

function episodeNumber(index: number | null | undefined): string {
  return typeof index === 'number' ? `Épisode ${index + 1}` : 'Épisode';
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
  const [episodes, setEpisodes] = useState<SerialArchiveEpisode[]>([]);
  const [current, setCurrent] = useState<CurrentEpisode>(null);
  const [threadId, setThreadId] = useState<string>('');
  const [seasonNumber, setSeasonNumber] = useState(1);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    apiService.getSerialEpisodes()
      .then((payload) => {
        if (!alive) return;
        setEpisodes(payload.episodes || []);
        setSeasonNumber(Number(payload.season_number || 1));
        setCurrent((payload.current_episode as CurrentEpisode) || null);
        setThreadId(String(payload.thread_id || ''));
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

  const filed = episodes.length;
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
    'La suite de votre histoire vous attend.',
  );
  const heroCta = heroEpisode?.kind === 'mission' ? 'Répondre dans Le Courrier' : 'Lire et répondre';

  return (
    <>
      <Head>
        <title>Le feuilleton · L’Atelier</title>
      </Head>
      <FeuilletonReaderStyles />
      <main className="fr-page" aria-label="Le feuilleton">
        <header className="fr-page-head">
          <div className="k">
            {loading
              ? 'Ouverture de la saison…'
              : `Saison ${seasonNumber} · ${filed} épisode${filed === 1 ? '' : 's'} paru${filed === 1 ? '' : 's'}`}
          </div>
          {/* the one Garamond italic headline on this screen */}
          <h1>Le feuilleton</h1>
        </header>

        {loading ? (
          <div className="fr-skeleton" aria-live="polite" aria-busy="true">
            <span className="fr-sr">Chargement de la saison</span>
            <i />
            <i />
            <i />
          </div>
        ) : failed ? (
          <div className="fr-empty" role="status">
            <h2>La saison n’a pas pu être ouverte.</h2>
            <p>La liaison avec la rédaction a échoué. Rien n’est perdu ; réessayez dans un instant.</p>
            <button
              type="button"
              className="fr-btn is-action"
              data-press="3d"
              onClick={() => window.location.reload()}
            >
              Réessayer <ArrowRight size={16} aria-hidden="true" />
            </button>
          </div>
        ) : (
          <>
            {heroEpisode && heroHref && (
              <section className="fr-hero" aria-label="Épisode en cours">
                <div className="art">
                  {heroArt ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={heroArt} alt="" />
                  ) : (
                    <span>L’illustration de cet épisode n’est pas encore parue.</span>
                  )}
                </div>
                <div className="body">
                  <div className="k">
                    {episodeNumber(heroEpisode.episode_index)} ·{' '}
                    {heroEpisode.status === 'delayed' ? 'retardé' : "aujourd’hui"}
                  </div>
                  <h2>{heroTitle}</h2>
                  {/* the one tactile 3D press on this screen */}
                  <Link className="cta" href={heroHref}>
                    {heroCta} <ArrowRight size={16} aria-hidden="true" />
                  </Link>
                </div>
              </section>
            )}

            {episodes.length > 0 ? (
              <div className="fr-rows">
                {[...episodes]
                  .sort((left, right) => right.episode_index - left.episode_index)
                  .map((episode) => {
                    const thumb = resolveMediaUrl(episode.thumbnail_url);
                    const title = firstText(episode.hook_text, episode.title, 'Épisode classé');
                    return (
                      <Link className="fr-row" href={archiveHref(episode)} key={episode.id}>
                        <span className="thumb">
                          {thumb ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={thumb} alt="" />
                          ) : null}
                        </span>
                        <span className="meta">
                          <span className="k">{episodeNumber(episode.episode_index)} · lu</span>
                          <span className="t">{title}</span>
                        </span>
                        <span className="done" aria-hidden="true">
                          <Check size={14} color="#f8f3e8" strokeWidth={3} />
                        </span>
                      </Link>
                    );
                  })}
              </div>
            ) : (
              !heroEpisode && (
                <div className="fr-empty">
                  <h2>Le premier numéro n’est pas encore paru.</h2>
                  <p>
                    Dès qu’un épisode est lu ou qu’un acte est joué, il se range ici, planche par
                    planche, avec votre réplique.
                  </p>
                  <Link className="fr-btn is-action" data-press="3d" href="/graphic-novel">
                    Ouvrir le premier épisode <ArrowRight size={16} aria-hidden="true" />
                  </Link>
                </div>
              )
            )}

            <div className="fr-rows">
              <Link className="fr-row" href="/serial/cast">
                <span className="thumb" aria-hidden="true" />
                <span className="meta">
                  <span className="k">Le registre du théâtre</span>
                  <span className="t">Les personnages</span>
                </span>
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
            </div>
          </>
        )}
      </main>
      <PhoneProductNav active="feuilleton" />
      <style jsx global>{`
        body { background: var(--app-paper); }
        .fr-page { min-height: 100vh; padding-bottom: calc(var(--phone-bottom-nav-space, 88px)); }
      `}</style>
    </>
  );
}

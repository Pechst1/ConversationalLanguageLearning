import { useEffect, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { ArrowRight, Loader2, Users } from 'lucide-react';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import apiService, { SerialArchiveEpisode } from '@/services/api';

export default function SerialArchivePage() {
  const [episodes, setEpisodes] = useState<SerialArchiveEpisode[]>([]);
  const [seasonNumber, setSeasonNumber] = useState(1);
  const [currentEpisodeIndex, setCurrentEpisodeIndex] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    apiService.getSerialEpisodes()
      .then((payload) => {
        if (alive) {
          setEpisodes(payload.episodes || []);
          setSeasonNumber(Number(payload.season_number || 1));
          setCurrentEpisodeIndex(Number(payload.current_episode_index || 0));
        }
      })
      .catch((error) => {
        console.error(error);
        if (alive) setEpisodes([]);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <>
      <SerialStyles />
      <main className="serial-page">
        <EditorialMasthead active="studio" />
        <section className="serial-head">
          <div>
            <span>Le Feuilleton</span>
            <h1>Season {seasonNumber}</h1>
            <p>The living archive of acts, scenes, and the hooks they left behind.</p>
          </div>
          <Link className="serial-link" href="/serial/cast">
            <Users size={16} /> Cast
          </Link>
        </section>

        {loading ? (
          <div className="serial-loading"><Loader2 className="spin" /> Loading the archive</div>
        ) : (
          <>
            <SeasonProgressStrip episodes={episodes} seasonNumber={seasonNumber} currentEpisodeIndex={currentEpisodeIndex} />
            <section className="episode-list" aria-label={`Season ${seasonNumber} episodes`}>
              {episodes.length ? episodes.map((episode) => (
                <Link className="episode-row" key={episode.id} href={`/serial/episode/${episode.episode_index}`}>
                  <div className="episode-thumb">
                    {episode.thumbnail_url ? (
                      <Image src={episode.thumbnail_url} alt="" fill sizes="96px" unoptimized />
                    ) : (
                      <span>{episode.kind === 'mission' ? 'Act' : 'See'}</span>
                    )}
                  </div>
                  <div>
                    <span>{episode.episode_label} · {episode.kind}</span>
                    <h2>{episode.title}</h2>
                    {episode.hook_text && <p>{episode.hook_text}</p>}
                  </div>
                  <ArrowRight size={18} />
                </Link>
              )) : (
                <div className="serial-empty">
                  <h2>No filed episodes yet.</h2>
                  <p>Once you complete an act or Feuilleton scene, it will land here.</p>
                  <Link className="serial-link" href="/atelier">Back to Atelier</Link>
                </div>
              )}
            </section>
          </>
        )}
      </main>
    </>
  );
}

function SeasonProgressStrip({
  episodes,
  seasonNumber,
  currentEpisodeIndex,
}: {
  episodes: SerialArchiveEpisode[];
  seasonNumber: number;
  currentEpisodeIndex: number;
}) {
  const byIndex = new Map(episodes.map((episode) => [episode.episode_index, episode]));
  const total = Math.max(currentEpisodeIndex + 1, episodes.length, 1);
  return (
    <section className="season-strip" aria-label={`Season ${seasonNumber} progress`}>
      <div>
        <span>Season {seasonNumber}</span>
        <strong>{episodes.length}/{total} filed</strong>
      </div>
      <div className="season-track">
        {Array.from({ length: total }).map((_, index) => {
          const episode = byIndex.get(index);
          const state = episode ? 'done' : index === currentEpisodeIndex ? 'current' : 'future';
          const label = `Episode ${index + 1}`;
          return episode ? (
            <Link key={index} className={`season-dot ${state}`} href={`/serial/episode/${index}`} aria-label={`${label} filed`}>
              {index + 1}
            </Link>
          ) : (
            <span key={index} className={`season-dot ${state}`} aria-label={`${label} ${state}`}>
              {index + 1}
            </span>
          );
        })}
      </div>
    </section>
  );
}

function SerialStyles() {
  return (
    <style jsx global>{`
      .serial-page {
        min-height: 100vh;
        background: #f4efe3;
        color: #14110d;
        padding: 0 18px 48px;
      }
      .serial-head {
        display: flex;
        align-items: end;
        justify-content: space-between;
        gap: 18px;
        max-width: 980px;
        margin: 28px auto 22px;
        border-bottom: 3px solid #14110d;
        padding-bottom: 18px;
      }
      .serial-head span,
      .episode-row span {
        font-size: 11px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .serial-head h1 {
        margin: 6px 0;
        font-family: Georgia, serif;
        font-size: 46px;
        line-height: .95;
      }
      .serial-head p,
      .episode-row p,
      .serial-empty p {
        margin: 0;
        color: #554d43;
        line-height: 1.45;
      }
      .serial-link {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border: 2px solid #14110d;
        background: #fff9ec;
        color: #14110d;
        padding: 10px 12px;
        font-weight: 900;
        text-decoration: none;
        white-space: nowrap;
      }
      .season-strip {
        display: grid;
        grid-template-columns: auto 1fr;
        align-items: center;
        gap: 18px;
        max-width: 980px;
        margin: 0 auto 18px;
        border: 2px solid #14110d;
        background: #fff9ec;
        padding: 12px;
      }
      .season-strip > div:first-child {
        display: grid;
        gap: 3px;
        min-width: 120px;
      }
      .season-strip span,
      .season-strip strong {
        font-size: 11px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .season-strip strong {
        font-size: 16px;
        letter-spacing: 0;
        text-transform: none;
      }
      .season-track {
        display: flex;
        align-items: center;
        gap: 8px;
        overflow-x: auto;
        padding-bottom: 2px;
      }
      .season-dot {
        display: grid;
        place-items: center;
        flex: 0 0 auto;
        width: 34px;
        height: 34px;
        border: 2px solid #14110d;
        color: #14110d;
        background: #e8ddc8;
        text-decoration: none;
        font-weight: 900;
      }
      .season-dot.done {
        background: #f7c516;
        box-shadow: 2px 2px 0 #14110d;
      }
      .season-dot.current {
        background: #1d3a8a;
        color: #fff9ec;
      }
      .episode-list {
        display: grid;
        gap: 14px;
        max-width: 980px;
        margin: 0 auto;
      }
      .episode-row {
        display: grid;
        grid-template-columns: 96px 1fr auto;
        align-items: center;
        gap: 16px;
        border: 2px solid #14110d;
        background: #fff9ec;
        box-shadow: 4px 4px 0 #14110d;
        color: #14110d;
        padding: 12px;
        text-decoration: none;
      }
      .episode-thumb {
        position: relative;
        width: 96px;
        aspect-ratio: 1;
        overflow: hidden;
        border: 2px solid #14110d;
        background: #e8ddc8;
      }
      .episode-thumb img {
        object-fit: cover;
      }
      .episode-thumb span {
        display: grid;
        place-items: center;
        width: 100%;
        height: 100%;
        color: #1d3a8a;
      }
      .episode-row h2,
      .serial-empty h2 {
        margin: 4px 0 6px;
        font-family: Georgia, serif;
        font-size: 24px;
      }
      .serial-loading,
      .serial-empty {
        max-width: 980px;
        margin: 0 auto;
        border: 2px solid #14110d;
        background: #fff9ec;
        padding: 18px;
      }
      .serial-loading {
        display: flex;
        align-items: center;
        gap: 10px;
        font-weight: 900;
      }
      .spin {
        animation: spin 1s linear infinite;
      }
      @keyframes spin { to { transform: rotate(360deg); } }
      @media (max-width: 720px) {
        .serial-head {
          align-items: start;
          flex-direction: column;
        }
        .serial-head h1 {
          font-size: 38px;
        }
        .episode-row {
          grid-template-columns: 72px 1fr;
        }
        .episode-row > svg {
          display: none;
        }
        .episode-thumb {
          width: 72px;
        }
        .season-strip {
          grid-template-columns: 1fr;
        }
      }
    `}</style>
  );
}

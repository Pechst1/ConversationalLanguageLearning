import { useEffect, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Loader2, Users } from 'lucide-react';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import apiService, { SerialArchiveEpisode } from '@/services/api';

const ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII'];
const FRENCH_MONTHS = ['janv.', 'févr.', 'mars', 'avril', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];

function roman(index: number): string {
  return ROMAN[index] || String(index + 1);
}

function frenchDate(iso?: string | null): string {
  if (!iso) return 'à suivre';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'à suivre';
  return `${d.getDate()} ${FRENCH_MONTHS[d.getMonth()]}`;
}

function leadChar(episode: SerialArchiveEpisode): string | undefined {
  const cast = episode.required_cast;
  if (Array.isArray(cast) && cast.length) return String(cast[0]).toLowerCase();
  return undefined;
}

function pick(payload: Record<string, any> | undefined, keys: string[]): string | undefined {
  if (!payload) return undefined;
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return undefined;
}

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

  const filed = episodes.filter((episode) => episode.completed_at || episode.status === 'completed').length;

  return (
    <>
      <SerialStyles />
      <main className="serial-page">
        <EditorialMasthead active="studio" />
        <div className="serial-column">
          <header className="serial-head">
            <p className="rubric">Le Feuilleton · index</p>
            <h1>The story so far</h1>
            <p className="sub">
              {filed > 0 ? `${filed} installment${filed === 1 ? '' : 's'} with these people` : 'Season ' + seasonNumber}
            </p>
            <Link className="cast-link" href="/serial/cast">
              <Users size={14} aria-hidden="true" /> The cast
            </Link>
          </header>

          {loading ? (
            <div className="serial-loading"><Loader2 className="spin" aria-hidden="true" /> Loading the archive</div>
          ) : episodes.length ? (
            <ol className="s-map" aria-label={`Season ${seasonNumber} thread`}>
              {episodes.map((episode, index) => {
                const done = Boolean(episode.completed_at) || episode.status === 'completed';
                const up = !done && episode.episode_index >= currentEpisodeIndex;
                const who = leadChar(episode);
                const date = frenchDate(episode.completed_at);
                const loc = pick(episode.brief_payload, ['location', 'setting', 'place', 'scene_label']);
                const choice = pick(episode.brief_payload, ['choice', 'user_choice', 'decision', 'outcome']);
                const plate = pick(episode.brief_payload, ['plate', 'shot', 'scene_label', 'setting']);
                const showPlate = !up && (Boolean(episode.thumbnail_url) || Boolean(choice));
                const classes = ['s-ep'];
                if (up) classes.push('up');
                if (index === 0) classes.push('first');
                if (index === episodes.length - 1) classes.push('last');

                return (
                  <li className={classes.join(' ')} key={episode.id} data-char={who}>
                    <Link className="s-ep-link" href={`/serial/episode?index=${episode.episode_index}`} aria-label={`${episode.title}`}>
                      <span className="dot2">{roman(episode.episode_index)}</span>
                      <div className="ebody">
                        <div className="edate">
                          Ép. {roman(episode.episode_index)} · {date}{loc ? ` · ${loc}` : ''} · {episode.kind === 'mission' ? 'act' : 'scene'}
                        </div>
                        <div className="ehook">{episode.hook_text || episode.title}</div>
                        {showPlate && (
                          <div className="eplate">
                            <div className="thumb">
                              {episode.thumbnail_url ? (
                                <Image src={episode.thumbnail_url} alt="" fill sizes="72px" unoptimized />
                              ) : (
                                <span>{plate || (episode.kind === 'mission' ? 'act' : 'scene')}</span>
                              )}
                            </div>
                            {choice && (
                              <div className="choice">
                                <b>You chose</b>
                                <em>{choice}</em>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ol>
          ) : (
            <div className="serial-empty">
              <h2>No installments filed yet.</h2>
              <p>Once you act in a scene or finish a Feuilleton episode, it lands here as part of the story.</p>
              <Link className="cast-link" href="/atelier">Back to today</Link>
            </div>
          )}
        </div>
      </main>
    </>
  );
}

function SerialStyles() {
  return (
    <style jsx global>{`
      .serial-page {
        min-height: 100vh;
        background: var(--app-paper);
        color: var(--app-ink);
      }
      .serial-column {
        width: min(640px, 100%);
        margin: 0 auto;
        padding: var(--space-5) var(--space-4) calc(var(--space-8) + env(safe-area-inset-bottom));
      }
      .serial-head {
        border-bottom: 1px solid var(--app-ink);
        padding-bottom: var(--space-4);
      }
      .serial-head .rubric {
        margin: 0;
        color: var(--app-red);
        font-family: var(--mono);
        font-size: var(--type-mono);
        font-weight: var(--weight-medium);
        letter-spacing: 0.13em;
        text-transform: uppercase;
      }
      .serial-head h1 {
        margin: var(--space-2) 0 0;
        font-family: var(--app-serif);
        font-style: italic;
        font-weight: var(--weight-medium);
        font-size: var(--type-title);
        line-height: 1;
      }
      .serial-head .sub {
        margin: var(--space-2) 0 0;
        color: var(--app-ink-2);
        font-size: 0.95rem;
      }
      .cast-link {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        margin-top: var(--space-3);
        color: var(--app-blue);
        font-family: var(--mono);
        font-size: var(--type-mono);
        font-weight: var(--weight-medium);
        letter-spacing: 0.06em;
        text-transform: uppercase;
        text-decoration: none;
      }
      .s-map {
        list-style: none;
        margin: var(--space-5) 0 0;
        padding: 0;
      }
      .s-ep {
        position: relative;
        --accent: var(--app-ink);
      }
      .s-ep::before {
        content: "";
        position: absolute;
        left: 14px;
        top: 0;
        bottom: 0;
        border-left: 2px solid var(--app-ink);
        z-index: 0;
      }
      .s-ep.up::before { border-left: 1.5px dashed var(--app-ink-3); }
      .s-ep.first::before { top: 16px; }
      .s-ep.last::before { bottom: calc(100% - 16px); }
      .s-ep-link {
        position: relative;
        display: grid;
        grid-template-columns: 30px minmax(0, 1fr);
        gap: 14px;
        padding-bottom: var(--space-2);
        color: inherit;
        text-decoration: none;
      }
      .s-ep .dot2 {
        position: relative;
        z-index: 1;
        width: 30px;
        height: 30px;
        border: 1.5px solid var(--app-ink);
        background: var(--accent);
        display: grid;
        place-items: center;
        color: var(--app-paper);
        font-family: var(--app-serif);
        font-style: italic;
        font-weight: 700;
        font-size: 14px;
      }
      .s-ep.up .dot2 {
        background: var(--app-paper);
        color: var(--app-ink-3);
        border-color: var(--app-ink-3);
      }
      .s-ep .ebody {
        padding-bottom: var(--space-5);
        min-width: 0;
      }
      .s-ep .edate {
        font-family: var(--mono);
        font-size: 0.62rem;
        font-weight: var(--weight-medium);
        letter-spacing: 0.13em;
        text-transform: uppercase;
        color: var(--app-ink-3);
      }
      .s-ep .ehook {
        margin: var(--space-1) 0 0;
        font-family: var(--app-serif);
        font-style: italic;
        font-weight: var(--weight-medium);
        font-size: 1.18rem;
        line-height: 1.14;
        color: var(--app-ink);
      }
      .s-ep.up .ehook { color: var(--app-ink-3); }
      .s-ep .eplate {
        margin-top: var(--space-3);
        display: flex;
        gap: var(--space-3);
        align-items: stretch;
      }
      .s-ep .eplate .thumb {
        position: relative;
        flex: 0 0 72px;
        height: 50px;
        overflow: hidden;
        border: 1px solid var(--app-ink);
        background: var(--app-paper-2);
        background-image: repeating-linear-gradient(135deg, rgba(20, 17, 13, 0.07) 0 2px, transparent 2px 9px);
        display: grid;
        place-items: end start;
        padding: 4px;
      }
      .s-ep .eplate .thumb img { object-fit: cover; }
      .s-ep .eplate .thumb span {
        font-family: var(--mono);
        font-size: 0.5rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--app-ink-3);
      }
      .s-ep .eplate .choice {
        min-width: 0;
        font-size: 0.78rem;
        line-height: 1.35;
        color: var(--app-ink-2);
      }
      .s-ep .eplate .choice b {
        display: block;
        margin-bottom: 2px;
        font-family: var(--mono);
        font-size: 0.56rem;
        font-weight: var(--weight-medium);
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--app-ink-3);
      }
      .s-ep .eplate .choice em {
        font-family: var(--app-serif);
        font-style: italic;
        font-size: 0.92rem;
        color: var(--app-ink);
      }
      .serial-loading,
      .serial-empty {
        margin-top: var(--space-5);
        border: 1px solid var(--app-ink);
        background: var(--app-sheet);
        padding: var(--space-4);
      }
      .serial-loading {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        color: var(--app-ink-2);
      }
      .serial-empty h2 {
        margin: 0 0 var(--space-2);
        font-family: var(--app-serif);
        font-style: italic;
        font-weight: var(--weight-medium);
        font-size: 1.4rem;
      }
      .serial-empty p {
        margin: 0 0 var(--space-3);
        color: var(--app-ink-2);
        line-height: 1.45;
      }
      .spin { animation: spin 1s linear infinite; }
      @keyframes spin { to { transform: rotate(360deg); } }
      @media (prefers-reduced-motion: reduce) { .spin { animation: none; } }
    `}</style>
  );
}

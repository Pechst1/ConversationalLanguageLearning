import { useEffect, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import {
  FeuilletonStyles,
  FeMastheadBar,
  FeSectionNav,
  FeArchivePlate,
  FeIco,
} from '@/components/feuilleton/Feuilleton';
import apiService, { SerialArchiveEpisode } from '@/services/api';
import { resolveMediaUrl } from '@/lib/media-url';

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

function initial(slug?: string): string {
  if (!slug) return '·';
  return slug.charAt(0).toUpperCase();
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
  const total = Math.max(episodes.length, filed);
  const seasonPct = total ? Math.round((filed / total) * 100) : 0;

  return (
    <>
      <Head>
        <title>La saison reliée · Le Feuilleton · L’Atelier</title>
      </Head>
      <main className="fe-stage">
        <div className="fe" aria-label="Le Feuilleton · la saison reliée">
          <FeMastheadBar />
          <FeSectionNav active="season" />
          <div className="fe-body fe-scroll">
            <div className="fe-arc-head">
              <div className="kicker">Le Feuilleton · La saison reliée</div>
              <h2>La saison reliée</h2>
              <div className="sub">
                {filed > 0
                  ? `Saison ${seasonNumber} — ${filed} planche${filed === 1 ? '' : 's'} classée${filed === 1 ? '' : 's'}`
                  : `Saison ${seasonNumber} · le premier cahier, à peine relié`}
              </div>
            </div>

            {loading ? (
              <FeSkelList />
            ) : episodes.length ? (
              <>
                <div className="fe-season-line" aria-hidden="true">
                  <div className="cap">
                    <span>Reliure de la saison</span>
                    <span>{filed} / {total}</span>
                  </div>
                  <div className="bar">
                    <i style={{ width: `${seasonPct}%` }} />
                  </div>
                </div>

                <div className="fe-season">
                  {episodes.map((episode) => {
                    const done = Boolean(episode.completed_at) || episode.status === 'completed';
                    const who = leadChar(episode);
                    const loc = pick(episode.brief_payload, ['location', 'setting', 'place', 'scene_label'])
                      || (episode.kind === 'mission' ? 'un acte' : 'une planche');
                    const choice = pick(episode.brief_payload, ['choice', 'user_choice', 'decision']);
                    const outcome = pick(episode.brief_payload, ['outcome', 'consequence', 'result']);
                    const plate = pick(episode.brief_payload, ['plate', 'shot', 'scene_label', 'setting']);
                    const state: 'filed' | 'current' | 'up' = done
                      ? 'filed'
                      : episode.episode_index === currentEpisodeIndex
                        ? 'current'
                        : 'up';
                    return (
                      <FeArchivePlate
                        key={episode.id}
                        href={`/serial/episode?index=${episode.episode_index}`}
                        roman={roman(episode.episode_index)}
                        title={episode.hook_text || episode.title}
                        date={frenchDate(episode.completed_at)}
                        location={loc}
                        char={who}
                        ini={initial(who)}
                        slug={episode.thumbnail_url ? undefined : plate}
                        thumbnailUrl={resolveMediaUrl(episode.thumbnail_url)}
                        choice={choice}
                        outcome={outcome}
                        state={state}
                      />
                    );
                  })}
                </div>

                <Link className="fe-cast-entry" href="/serial/cast">
                  <div className="l">
                    <div className="k">Le registre du théâtre</div>
                    <div className="t">Les personnages</div>
                  </div>
                  {FeIco.arrow}
                </Link>
              </>
            ) : (
              <div className="fe-arc-empty">
                <div className="mark" />
                <h3>Le premier numéro n’est pas encore paru.</h3>
                <p>Une fois un épisode lu ou un acte joué, il se relie ici — planche par planche, avec votre réplique.</p>
                <Link className="cta" href="/graphic-novel">
                  Ouvrir l’épisode 1 {FeIco.arrow}
                </Link>
              </div>
            )}
          </div>
        </div>
      </main>
      <PhoneProductNav active="feuilleton" />
      <FeuilletonStyles />
      <style jsx global>{`
        .fe-stage { min-height: 100vh; background: var(--app-paper); color: var(--app-ink); }
      `}</style>
    </>
  );
}

function FeSkelList() {
  return (
    <div className="fe-skel" aria-hidden="true">
      <div className="l" style={{ width: '55%', margin: '0 0 12px' }} />
      <div className="l" style={{ width: '80%', height: 40, marginBottom: 12 }} />
      <div className="l" style={{ width: '75%', height: 40, marginBottom: 12 }} />
      <div className="l" style={{ width: '70%', height: 40 }} />
      <div className="press">— on relie la saison —</div>
    </div>
  );
}

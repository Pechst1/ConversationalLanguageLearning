/* Episode replay — a filed episode read again from the archive.
 *
 * No artboard in the Claude design covers a replay, so it is extended from the
 * reader's own primitives: the Feuilleton index head (kicker + one Garamond-
 * italic headline), the reader's plate + speech cards for a scene, and the
 * Missions chat bubbles for a mission's turns. Reading is read-only: nothing
 * here submits, completes or scores. */

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import { ArrowLeftIcon, AtelierV2Root, Skeleton } from '@/components/atelier-v2/ui';
import { FeuilletonReaderStyles } from '@/components/feuilleton/reader';
import apiService, { GraphicNovelScene, RealWorldMission, SerialArchiveEpisode } from '@/services/api';
import { resolveMediaUrl } from '@/lib/media-url';

const STATIC_REPLAY_EPISODES = 24;

function resolveEpisodeIndex(rawIndex: string | string[] | undefined, asPath: string): number | null {
  const direct = Array.isArray(rawIndex) ? rawIndex[0] : rawIndex;
  const fallback = asPath.includes('?') ? new URLSearchParams(asPath.split('?')[1]).get('index') : null;
  const browserFallback = typeof window === 'undefined' ? null : new URLSearchParams(window.location.search).get('index');
  const parsed = Number(direct ?? fallback ?? browserFallback);
  return Number.isFinite(parsed) ? parsed : null;
}

export async function getStaticPaths() {
  return {
    paths: Array.from({ length: STATIC_REPLAY_EPISODES }, (_, index) => ({
      params: { index: String(index) },
    })),
    fallback: false,
  };
}

export async function getStaticProps() {
  return { props: {} };
}

export default function SerialEpisodeReplayPage() {
  const router = useRouter();
  const episodeIndex = useMemo(
    () => resolveEpisodeIndex(router.query.index, router.asPath),
    [router.asPath, router.query.index],
  );
  const [episode, setEpisode] = useState<SerialArchiveEpisode | null>(null);
  const [scene, setScene] = useState<GraphicNovelScene | null>(null);
  const [mission, setMission] = useState<RealWorldMission | null>(null);
  const [seasonNumber, setSeasonNumber] = useState(1);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!router.isReady || episodeIndex === null) return;
    let alive = true;
    setLoading(true);
    apiService.getSerialEpisodes()
      .then(async (payload) => {
        const match = (payload.episodes || []).find((item) => item.episode_index === episodeIndex) || null;
        if (!alive) return;
        setSeasonNumber(Number(payload.season_number || 1));
        setEpisode(match);
        setScene(null);
        setMission(null);
        if (match?.scene_id) {
          const loaded = await apiService.getGraphicNovelScene(match.scene_id);
          if (alive) setScene(loaded);
        } else if (match?.mission_id) {
          const loaded = await apiService.getMission(match.mission_id);
          if (alive) setMission(loaded);
        }
      })
      .catch((error) => {
        console.error(error);
        if (alive) {
          setEpisode(null);
          setScene(null);
          setMission(null);
        }
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [episodeIndex, router.isReady]);

  const title = useMemo(() => episode?.title || scene?.title || mission?.title || 'Épisode', [episode, mission, scene]);

  /* The fiction speaks: the character's name from the mission messenger
     (same source as pages/missions.tsx), never the raw LLM role. */
  const correspondentName = useMemo(() => {
    const messenger = mission?.prompt_payload?.messenger;
    const name = messenger && typeof messenger === 'object'
      ? String((messenger as Record<string, any>).contact_name || '').trim()
      : '';
    return name || 'La correspondance';
  }, [mission]);

  const kicker = episodeIndex === null
    ? 'Le feuilleton'
    : `Saison ${seasonNumber} · Épisode ${episodeIndex + 1} · relecture`;

  return (
    <>
      <FeuilletonReaderStyles />
      <AtelierV2Root as="main" className="fr-page replay-page" aria-label="Relecture de l’épisode">
        <div className="replay-back">
          <Link className="av2-btn av2-btn--secondary av2-btn--inline" href="/serial">
            <ArrowLeftIcon size={18} /> Saison {seasonNumber}
          </Link>
        </div>
        <header className="fr-page-head">
          <div className="k">{kicker}</div>
          {/* the one Garamond italic headline on this screen */}
          <h1>{title}</h1>
        </header>

        {loading ? (
          <div className="replay-stack" aria-live="polite" aria-busy="true">
            <span className="fr-sr">On tire l’épisode</span>
            <Skeleton height={260} radius={24} />
            <Skeleton height={96} radius={18} />
            <Skeleton height={96} radius={18} />
          </div>
        ) : scene ? (
          <section className="replay-stack" aria-label="Planches de l’épisode">
            {(scene.panels || []).map((panel) => {
              const caption = panel.overlay_payload?.caption || {};
              const imageUrl = resolveMediaUrl(panel.image_url || panel.image_payload?.url);
              return (
                <article className="replay-panel" key={panel.id}>
                  {imageUrl ? (
                    <figure className="fr-plate">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={imageUrl} alt={panel.title ? `Planche : ${panel.title}` : ''} loading="lazy" />
                    </figure>
                  ) : (
                    <figure className="fr-plate is-missing">
                      <figcaption className="fr-plate-note">Cette planche est parue sans illustration.</figcaption>
                    </figure>
                  )}
                  <div className="fr-speech">
                    <p className="fr-speaker">
                      <span className="glyph" aria-hidden="true" />
                      Planche {panel.panel_index}{panel.title ? ` · ${panel.title}` : ''}
                    </p>
                    <p className="fr-line" lang="fr">{caption.fr || panel.beat}</p>
                    {caption.en && <p className="fr-line-en">{caption.en}</p>}
                  </div>
                </article>
              );
            })}
          </section>
        ) : mission ? (
          <section className="replay-stack mission-replay" aria-label="L’acte rejoué">
            <div className="fr-notice">
              <p className="fr-eyebrow">L’acte</p>
              <h2>{mission.title}</h2>
              <p>{mission.brief}</p>
            </div>
            <div className="replay-thread">
              {(mission.turns || []).map((turn) => (
                <div key={turn.id} className={turn.role === 'user' ? 'replay-turn' : 'replay-turn replay-turn--them'}>
                  <span className="av2-label">{turn.role === 'user' ? 'Vous' : correspondentName}</span>
                  <p className={turn.role === 'user' ? 'av2-bubble av2-bubble--mine' : 'av2-bubble'} lang="fr">
                    {turn.text}
                  </p>
                </div>
              ))}
              {(mission.attempts || []).map((attempt) => (
                <div key={attempt.id} className="replay-turn">
                  <span className="av2-label">Vous</span>
                  <p className="av2-bubble av2-bubble--mine" lang="fr">
                    {attempt.answer_payload?.text || attempt.answer_payload?.answer || ''}
                  </p>
                </div>
              ))}
            </div>
          </section>
        ) : (
          <div className="fr-empty" role="status">
            <h2>Épisode non classé.</h2>
            <p>Cette entrée ne figure pas encore aux archives.</p>
          </div>
        )}
      </AtelierV2Root>
      <PhoneProductNav active="feuilleton" />
      <style jsx global>{`
        body { background: var(--app-paper); }
        .av2.replay-page { min-height: 100vh; padding-bottom: calc(var(--phone-bottom-nav-space, 88px)); }
        .av2 .replay-back { padding-top: calc(16px + env(safe-area-inset-top, 0px)); }
        .av2 .replay-back .av2-btn { min-height: 44px; padding: 0.5rem 1rem; font-size: var(--av2-t-label); }
        .av2 .replay-page .fr-page-head { padding-top: 14px; }
        .av2 .replay-stack { display: flex; flex-direction: column; gap: 14px; padding: 18px 0 0; }
        .av2 .replay-panel { display: flex; flex-direction: column; gap: 10px; }
        .av2 .replay-panel .fr-plate { max-block-size: none; aspect-ratio: 1 / 1; }
        .av2 .replay-thread { display: flex; flex-direction: column; gap: 12px; }
        .av2 .replay-turn { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; min-width: 0; }
        .av2 .replay-turn--them { align-items: flex-start; }
        .av2 .replay-turn .av2-bubble { margin: 0; }
      `}</style>
    </>
  );
}

import { useEffect, useMemo, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { ArrowLeft, Loader2 } from 'lucide-react';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
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
    ? 'Le Feuilleton'
    : `Saison ${seasonNumber} · Épisode ${episodeIndex + 1}`;

  return (
    <>
      <ReplayStyles />
      <main className="replay-page">
        <EditorialMasthead active="studio" />
        <section className="replay-head">
          <Link href="/serial"><ArrowLeft size={15} /> Saison {seasonNumber}</Link>
          <div>
            <span>{kicker}</span>
            <h1>{title}</h1>
          </div>
        </section>

        {loading ? (
          <div className="replay-loading"><Loader2 className="spin" /> On tire l’épisode…</div>
        ) : scene ? (
          <section className="replay-panels" aria-label="Planches de l’épisode">
            {(scene.panels || []).map((panel) => {
              const caption = panel.overlay_payload?.caption || {};
              const imageUrl = resolveMediaUrl(panel.image_url || panel.image_payload?.url);
              return (
                <article className="replay-panel" key={panel.id}>
                  <div className="replay-image">
                    {imageUrl ? <Image src={imageUrl} alt="" fill sizes="(max-width: 760px) 100vw, 50vw" unoptimized /> : <span>Planche {panel.panel_index}</span>}
                  </div>
                  <div className="replay-copy">
                    <span>Planche {panel.panel_index}</span>
                    <h2>{panel.title}</h2>
                    <p>{caption.fr || panel.beat}</p>
                    {caption.en && <small>{caption.en}</small>}
                  </div>
                </article>
              );
            })}
          </section>
        ) : mission ? (
          <section className="mission-replay">
            <article>
              <span>L’acte</span>
              <h2>{mission.title}</h2>
              <p>{mission.brief}</p>
            </article>
            {(mission.turns || []).map((turn) => (
              <blockquote key={turn.id} className={turn.role === 'user' ? 'user' : ''}>
                <span>{turn.role === 'user' ? 'Vous' : correspondentName}</span>
                <p>{turn.text}</p>
              </blockquote>
            ))}
            {(mission.attempts || []).map((attempt) => (
              <blockquote key={attempt.id} className="user">
                <span>Vous</span>
                <p>{attempt.answer_payload?.text || attempt.answer_payload?.answer || ''}</p>
              </blockquote>
            ))}
          </section>
        ) : (
          <div className="replay-empty">
            <h2>Épisode non classé.</h2>
            <p>Cette entrée ne figure pas encore aux archives.</p>
          </div>
        )}
      </main>
    </>
  );
}

/* Journal furniture only — every colour is an --app-* token so the page sets
   itself in light and dark; serif headlines, uppercase letter-spaced kickers,
   hairline rules, one phone-first reading column. */
function ReplayStyles() {
  return (
    <style jsx global>{`
      .replay-page {
        min-height: 100vh;
        background: var(--app-paper);
        color: var(--app-ink);
        padding: 0 18px 48px;
      }
      .replay-head {
        display: flex;
        justify-content: space-between;
        align-items: end;
        gap: 18px;
        max-width: 680px;
        margin: 28px auto 22px;
        border-bottom: 3px double var(--app-ink);
        padding-bottom: 16px;
      }
      .replay-head a {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border: 1px solid var(--app-ink);
        background: var(--app-sheet);
        color: var(--app-ink);
        padding: 10px 12px;
        font-size: var(--t-label);
        font-weight: 800;
        letter-spacing: .12em;
        text-transform: uppercase;
        text-decoration: none;
        white-space: nowrap;
      }
      .replay-head span,
      .replay-copy span,
      .mission-replay span {
        display: block;
        font-size: var(--t-label);
        font-weight: 800;
        letter-spacing: .14em;
        text-transform: uppercase;
        color: var(--app-ink-3);
      }
      .replay-head span {
        color: var(--app-red);
        letter-spacing: .18em;
      }
      .replay-head h1 {
        margin: 6px 0 0;
        max-width: 700px;
        font-family: var(--app-serif);
        font-style: italic;
        font-weight: 700;
        font-size: var(--t-head);
        line-height: 1.04;
        text-align: right;
        text-wrap: balance;
      }
      .replay-panels {
        display: grid;
        grid-template-columns: 1fr;
        gap: 18px;
        max-width: 680px;
        margin: 0 auto;
      }
      .replay-panel,
      .mission-replay article,
      .mission-replay blockquote,
      .replay-loading,
      .replay-empty {
        border: 1px solid var(--app-ink);
        background: var(--app-sheet);
      }
      .replay-image {
        position: relative;
        aspect-ratio: 1;
        overflow: hidden;
        border-bottom: 1px solid var(--app-ink);
        background: var(--app-paper-2);
      }
      .replay-image img {
        object-fit: cover;
      }
      .replay-image span {
        display: grid;
        place-items: center;
        height: 100%;
        color: var(--app-blue);
        font-size: var(--t-label);
        font-weight: 800;
        letter-spacing: .14em;
        text-transform: uppercase;
      }
      .replay-copy,
      .mission-replay article {
        padding: 14px 16px 16px;
      }
      .replay-copy h2,
      .mission-replay h2,
      .replay-empty h2 {
        margin: 6px 0;
        font-family: var(--app-serif);
        font-style: italic;
        font-weight: 600;
        font-size: var(--t-lead);
        line-height: 1.15;
        color: var(--app-ink);
      }
      .replay-copy p {
        margin: 0;
        font-family: var(--app-serif);
        font-style: italic;
        font-size: var(--t-body);
        line-height: 1.35;
        color: var(--app-ink);
      }
      .mission-replay article > p,
      .replay-empty p {
        margin: 0;
        font-size: var(--t-small);
        line-height: 1.5;
        color: var(--app-ink-2);
      }
      .replay-copy small {
        display: block;
        margin-top: 8px;
        font-size: var(--t-label);
        line-height: 1.4;
        color: var(--app-ink-3);
      }
      .mission-replay {
        display: grid;
        gap: 14px;
        max-width: 680px;
        margin: 0 auto;
      }
      .mission-replay article > span {
        color: var(--app-red);
      }
      .mission-replay blockquote {
        margin: 0;
        padding: 12px 16px 14px;
      }
      .mission-replay blockquote p {
        margin: 4px 0 0;
        font-family: var(--app-serif);
        font-style: italic;
        font-size: var(--t-body);
        line-height: 1.35;
        color: var(--app-ink);
      }
      .mission-replay blockquote.user {
        border-left: 3px solid var(--app-blue);
      }
      .mission-replay blockquote.user span {
        color: var(--app-blue);
      }
      .replay-loading,
      .replay-empty {
        max-width: 680px;
        margin: 0 auto;
        padding: 16px 18px;
      }
      .replay-loading {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: var(--t-label);
        font-weight: 800;
        letter-spacing: .14em;
        text-transform: uppercase;
        color: var(--app-ink-2);
      }
      .spin { animation: spin 1s linear infinite; }
      @keyframes spin { to { transform: rotate(360deg); } }
      @media (max-width: 760px) {
        .replay-head {
          align-items: start;
          flex-direction: column;
        }
        .replay-head h1 {
          text-align: left;
        }
      }
    `}</style>
  );
}

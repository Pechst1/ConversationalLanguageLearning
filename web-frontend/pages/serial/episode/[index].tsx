import { useEffect, useMemo, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { ArrowLeft, Loader2 } from 'lucide-react';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import apiService, { GraphicNovelScene, RealWorldMission, SerialArchiveEpisode } from '@/services/api';

export default function SerialEpisodeReplayPage() {
  const router = useRouter();
  const episodeIndex = Number(router.query.index);
  const [episode, setEpisode] = useState<SerialArchiveEpisode | null>(null);
  const [scene, setScene] = useState<GraphicNovelScene | null>(null);
  const [mission, setMission] = useState<RealWorldMission | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!router.isReady || !Number.isFinite(episodeIndex)) return;
    let alive = true;
    setLoading(true);
    apiService.getSerialEpisodes()
      .then(async (payload) => {
        const match = (payload.episodes || []).find((item) => item.episode_index === episodeIndex) || null;
        if (!alive) return;
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

  const title = useMemo(() => episode?.title || scene?.title || mission?.title || 'Episode', [episode, mission, scene]);

  return (
    <>
      <ReplayStyles />
      <main className="replay-page">
        <EditorialMasthead active="studio" />
        <section className="replay-head">
          <Link href="/serial"><ArrowLeft size={15} /> Season 1</Link>
          <div>
            <span>{episode?.episode_label || 'Le Feuilleton'}</span>
            <h1>{title}</h1>
          </div>
        </section>

        {loading ? (
          <div className="replay-loading"><Loader2 className="spin" /> Loading episode</div>
        ) : scene ? (
          <section className="replay-panels" aria-label="Episode panels">
            {(scene.panels || []).map((panel) => {
              const caption = panel.overlay_payload?.caption || {};
              const imageUrl = panel.image_url || panel.image_payload?.url;
              return (
                <article className="replay-panel" key={panel.id}>
                  <div className="replay-image">
                    {imageUrl ? <Image src={imageUrl} alt="" fill sizes="(max-width: 760px) 100vw, 50vw" unoptimized /> : <span>Panel {panel.panel_index}</span>}
                  </div>
                  <div className="replay-copy">
                    <span>Panel {panel.panel_index}</span>
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
              <span>Act</span>
              <h2>{mission.title}</h2>
              <p>{mission.brief}</p>
            </article>
            {(mission.turns || []).map((turn) => (
              <blockquote key={turn.id} className={turn.role === 'user' ? 'user' : ''}>
                <span>{turn.role}</span>
                <p>{turn.text}</p>
              </blockquote>
            ))}
            {(mission.attempts || []).map((attempt) => (
              <blockquote key={attempt.id} className="user">
                <span>message</span>
                <p>{attempt.answer_payload?.text || attempt.answer_payload?.answer || ''}</p>
              </blockquote>
            ))}
          </section>
        ) : (
          <div className="replay-empty">
            <h2>Episode not filed.</h2>
            <p>This entry is not available in the archive yet.</p>
          </div>
        )}
      </main>
    </>
  );
}

function ReplayStyles() {
  return (
    <style jsx global>{`
      .replay-page {
        min-height: 100vh;
        background: #f4efe3;
        color: #14110d;
        padding: 0 18px 48px;
      }
      .replay-head {
        display: flex;
        justify-content: space-between;
        align-items: end;
        gap: 18px;
        max-width: 980px;
        margin: 28px auto 22px;
        border-bottom: 3px solid #14110d;
        padding-bottom: 18px;
      }
      .replay-head a {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border: 2px solid #14110d;
        background: #fff9ec;
        color: #14110d;
        padding: 10px 12px;
        font-weight: 900;
        text-decoration: none;
      }
      .replay-head span,
      .replay-copy span,
      .mission-replay span {
        display: block;
        font-size: 11px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .replay-head h1 {
        margin: 6px 0 0;
        max-width: 700px;
        font-family: Georgia, serif;
        font-size: 40px;
        line-height: 1;
        text-align: right;
      }
      .replay-panels {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 18px;
        max-width: 980px;
        margin: 0 auto;
      }
      .replay-panel,
      .mission-replay article,
      .mission-replay blockquote,
      .replay-loading,
      .replay-empty {
        border: 2px solid #14110d;
        background: #fff9ec;
        box-shadow: 4px 4px 0 #14110d;
      }
      .replay-image {
        position: relative;
        aspect-ratio: 1;
        overflow: hidden;
        border-bottom: 2px solid #14110d;
        background: #e8ddc8;
      }
      .replay-image img {
        object-fit: cover;
      }
      .replay-image span {
        display: grid;
        place-items: center;
        height: 100%;
        color: #1d3a8a;
        font-weight: 900;
      }
      .replay-copy,
      .mission-replay article {
        padding: 14px;
      }
      .replay-copy h2,
      .mission-replay h2,
      .replay-empty h2 {
        margin: 6px 0;
        font-family: Georgia, serif;
        font-size: 24px;
      }
      .replay-copy p,
      .mission-replay p,
      .replay-empty p {
        margin: 0;
        color: #554d43;
        line-height: 1.45;
      }
      .replay-copy small {
        display: block;
        margin-top: 8px;
        color: #6d6357;
        line-height: 1.35;
      }
      .mission-replay {
        display: grid;
        gap: 14px;
        max-width: 760px;
        margin: 0 auto;
      }
      .mission-replay blockquote {
        margin: 0;
        padding: 14px;
      }
      .mission-replay blockquote.user {
        border-left: 8px solid #1d3a8a;
      }
      .replay-loading,
      .replay-empty {
        max-width: 980px;
        margin: 0 auto;
        padding: 18px;
      }
      .replay-loading {
        display: flex;
        align-items: center;
        gap: 10px;
        font-weight: 900;
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
          font-size: 34px;
        }
        .replay-panels {
          grid-template-columns: 1fr;
        }
      }
    `}</style>
  );
}

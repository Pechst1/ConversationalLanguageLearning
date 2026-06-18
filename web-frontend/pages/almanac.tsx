import { useCallback, useEffect, useState, type CSSProperties } from 'react';
import Image from 'next/image';
import { Loader2 } from 'lucide-react';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import { Seal, SealMini, LogoToken, type SealVariant } from '@/components/ui/Seal';
import apiService, {
  AtelierAlmanac,
  AtelierCollectible,
  AtelierWorkshopTarget,
} from '@/services/api';

const TARGET_ORDER: AtelierWorkshopTarget[] = ['plate_semaine', 'plate_chapter', 'colophon'];
const TARGET_LABEL: Record<string, string> = {
  plate_semaine: '« Semaine » gilt plate',
  plate_chapter: 'Bound chapter plate',
  colophon: 'The annual colophon',
};
const MEMBER_LABEL: Record<string, string> = {
  logo_token: 'logo tokens',
  story_seal: 'story seals',
  gilt_seal: 'gilt seals',
};

function variantOf(item: AtelierCollectible): SealVariant {
  const v = item.metadata?.seal_variant;
  return (v as SealVariant) || 'row';
}

function dateOf(item: AtelierCollectible): string {
  return String(item.metadata?.date || '');
}

type StorySealCrop = {
  image_url?: string;
  focal_point?: { x?: number; y?: number };
  region?: { x?: number; y?: number; width?: number; height?: number };
  fallback?: boolean;
};

function numberUnit(value: unknown, fallback: number): number {
  if (typeof value !== 'number' || Number.isNaN(value)) return fallback;
  return Math.max(0, Math.min(1, value));
}

function storySealCrop(item: AtelierCollectible): StorySealCrop | null {
  const crop = item.metadata?.seal_crop;
  return crop && typeof crop === 'object' ? (crop as StorySealCrop) : null;
}

function storySealImageUrl(item: AtelierCollectible): string | null {
  const crop = storySealCrop(item);
  const url = crop?.image_url;
  return !crop?.fallback && typeof url === 'string' && url.trim() ? url : null;
}

function storySealImageStyle(item: AtelierCollectible): CSSProperties {
  const crop = storySealCrop(item);
  const region = crop?.region;
  const focal = crop?.focal_point;
  const x = focal?.x ?? (
    region && typeof region.x === 'number' && typeof region.width === 'number'
      ? region.x + region.width / 2
      : undefined
  );
  const y = focal?.y ?? (
    region && typeof region.y === 'number' && typeof region.height === 'number'
      ? region.y + region.height / 2
      : undefined
  );
  return {
    objectPosition: `${Math.round(numberUnit(x, 0.5) * 100)}% ${Math.round(numberUnit(y, 0.5) * 100)}%`,
  };
}

function StorySealCard({ seal, no }: { seal: AtelierCollectible; no: number }) {
  const imageUrl = storySealImageUrl(seal);
  const title = String(seal.metadata?.scene_title || seal.metadata?.name || 'Story seal');
  const episode = String(seal.metadata?.episode_label || '');
  return (
    <article className={`story-seal-card ${imageUrl ? 'has-crop' : 'fallback'}`}>
      <div className="story-seal-art" aria-hidden="true">
        {imageUrl ? (
          <>
            <Image src={imageUrl} alt="" fill sizes="76px" unoptimized style={storySealImageStyle(seal)} />
            <span className="story-seal-ring" />
          </>
        ) : (
          <SealMini no={no} variant={variantOf(seal)} state="earned" />
        )}
      </div>
      <div className="story-seal-meta">
        <span>{episode || `Nº ${no}`}</span>
        <strong>{title}</strong>
        {dateOf(seal) && <em>{dateOf(seal)}</em>}
      </div>
    </article>
  );
}

export default function AlmanacPage() {
  const [almanac, setAlmanac] = useState<AtelierAlmanac | null>(null);
  const [loading, setLoading] = useState(true);
  const [composing, setComposing] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiService.getAtelierAlmanac();
      setAlmanac(data);
    } catch (error) {
      console.error(error);
      setAlmanac(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const compose = useCallback(
    async (target: AtelierWorkshopTarget) => {
      setComposing(target);
      try {
        await apiService.composeAtelierWorkshop(target);
        await load();
      } catch (error) {
        console.error(error);
      } finally {
        setComposing(null);
      }
    },
    [load],
  );

  const collectibles = almanac?.collectibles || {};
  const logoTokens = (collectibles.logo_token || []).filter((c) => !c.composed);
  const giltSeals = (collectibles.gilt_seal || []).filter((c) => !c.composed);
  const storySeals = (collectibles.story_seal || []).filter((c) => !c.composed);
  const plates = almanac?.plates || [];
  const featured = giltSeals[0] || null;
  const earnedCount = logoTokens.length + giltSeals.length + storySeals.length + plates.length;

  return (
    <>
      <AlmanacStyles />
      <main className="almanac-page">
        <EditorialMasthead active="notebook" />
        <div className="almanac-column">
          <header className="almanac-head">
            <p className="rubric">L&apos;almanach des sceaux</p>
            <h1>Seal collection</h1>
            <p className="sub">An editorial archive of earned seals. Endowed progress toward a complete week — minted by playing, never bought.</p>
          </header>

          {loading ? (
            <div className="almanac-loading"><Loader2 className="spin" aria-hidden="true" /> Opening the almanac</div>
          ) : !almanac || earnedCount === 0 ? (
            <div className="almanac-empty">
              <h2>The case is empty — for now.</h2>
              <p>Finish a flawless screen to mint your first logo token, end a session clean for a gilt seal, or reach a serial beat for a story seal.</p>
            </div>
          ) : (
            <>
              {featured && (
                <section className="almanac-featured" aria-label="Latest gilt seal">
                  <Seal variant={variantOf(featured)} no={giltSeals.length} date={dateOf(featured)} size="lg" tone="gilt" />
                  <div className="featured-meta">
                    <span className="k">Latest gilt seal</span>
                    <strong>{String(featured.metadata?.name || 'Gilt seal')}</strong>
                    <span className="d">{dateOf(featured)}</span>
                  </div>
                </section>
              )}

              <section className="almanac-workshop" aria-label="The workshop">
                <span className="section-k">The workshop · compose your tokens</span>
                {TARGET_ORDER.map((target) => {
                  const p = almanac.progress?.[target];
                  if (!p) return null;
                  const pct = p.required ? Math.min(100, Math.round((p.progress / p.required) * 100)) : 0;
                  const ready = p.shortfall <= 0;
                  return (
                    <div className="workshop-row" key={target}>
                      <div className="workshop-info">
                        <strong>{TARGET_LABEL[target] || target}</strong>
                        <span>{p.progress}/{p.required} {MEMBER_LABEL[p.member_kind] || p.member_kind}</span>
                        <div className="workshop-bar"><span style={{ width: `${pct}%` }} /></div>
                      </div>
                      <button
                        className="compose-btn"
                        disabled={!ready || composing === target}
                        onClick={() => compose(target)}
                      >
                        {composing === target ? 'Composing…' : ready ? 'Compose' : `${p.shortfall} to go`}
                      </button>
                    </div>
                  );
                })}
              </section>

              {plates.length > 0 && (
                <section className="almanac-section" aria-label="Composed plates">
                  <span className="section-k">Composed plates</span>
                  <div className="seal-grid">
                    {plates.map((plate) => (
                      <SealMini key={plate.id} no={plate.members?.length || 0} variant={variantOf(plate)} state="earned" />
                    ))}
                  </div>
                </section>
              )}

              {(giltSeals.length > 0 || storySeals.length > 0) && (
                <section className="almanac-section" aria-label="Seals">
                  <span className="section-k">Seals</span>
                  {giltSeals.length > 0 && (
                    <div className="seal-grid">
                      {giltSeals.map((seal, i) => (
                        <SealMini key={seal.id} no={giltSeals.length - i} variant={variantOf(seal)} state="earned" tone="gilt" />
                      ))}
                    </div>
                  )}
                  {storySeals.length > 0 && (
                    <div className="story-seal-grid" aria-label="Story seals">
                      {storySeals.map((seal, i) => (
                        <StorySealCard key={seal.id} seal={seal} no={storySeals.length - i} />
                      ))}
                    </div>
                  )}
                </section>
              )}

              {logoTokens.length > 0 && (
                <section className="almanac-section" aria-label="Logo tokens">
                  <span className="section-k">Logo tokens · {logoTokens.length}</span>
                  <div className="token-grid">
                    {logoTokens.map((token) => (
                      <LogoToken key={token.id} size="sm" />
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </main>
    </>
  );
}

function AlmanacStyles() {
  return (
    <style jsx global>{`
      .almanac-page {
        min-height: 100vh;
        background: var(--app-paper);
        color: var(--app-ink);
      }
      .almanac-column {
        width: min(680px, 100%);
        margin: 0 auto;
        padding: var(--space-5) var(--space-4) calc(var(--space-8) + env(safe-area-inset-bottom));
      }
      .almanac-head {
        border-bottom: 1px solid var(--app-ink);
        padding-bottom: var(--space-4);
      }
      .almanac-head .rubric {
        margin: 0;
        color: var(--app-red);
        font-family: var(--mono);
        font-size: var(--type-mono);
        font-weight: var(--weight-medium);
        letter-spacing: 0.13em;
        text-transform: uppercase;
      }
      .almanac-head h1 {
        margin: var(--space-2) 0 0;
        font-family: var(--app-serif);
        font-style: italic;
        font-weight: var(--weight-medium);
        font-size: var(--type-title);
        line-height: 1;
      }
      .almanac-head .sub {
        margin: var(--space-2) 0 0;
        max-width: 46ch;
        color: var(--app-ink-2);
        font-size: 0.95rem;
        line-height: 1.45;
      }
      .almanac-featured {
        display: flex;
        align-items: center;
        gap: var(--space-5);
        flex-wrap: wrap;
        margin-top: var(--space-6);
      }
      .almanac-featured .featured-meta {
        display: grid;
        gap: 4px;
      }
      .almanac-featured .featured-meta .k {
        color: var(--app-ink-3);
        font-family: var(--mono);
        font-size: var(--type-mono);
        font-weight: var(--weight-medium);
        letter-spacing: 0.1em;
        text-transform: uppercase;
      }
      .almanac-featured .featured-meta strong {
        font-family: var(--app-serif);
        font-style: italic;
        font-weight: var(--weight-medium);
        font-size: 1.5rem;
      }
      .almanac-featured .featured-meta .d {
        color: var(--app-ink-2);
        font-size: 0.9rem;
      }
      .section-k {
        display: block;
        margin: var(--space-6) 0 var(--space-4);
        color: var(--app-ink-3);
        font-family: var(--mono);
        font-size: var(--type-mono);
        font-weight: var(--weight-medium);
        letter-spacing: 0.13em;
        text-transform: uppercase;
      }
      .workshop-row {
        display: flex;
        align-items: center;
        gap: var(--space-4);
        padding: var(--space-3) 0;
        border-bottom: 1px solid var(--app-paper-3);
      }
      .workshop-info {
        flex: 1 1 auto;
        min-width: 0;
        display: grid;
        gap: 6px;
      }
      .workshop-info strong {
        font-family: var(--app-serif);
        font-style: italic;
        font-weight: var(--weight-medium);
        font-size: 1.1rem;
      }
      .workshop-info span {
        color: var(--app-ink-3);
        font-family: var(--mono);
        font-size: var(--type-mono);
        letter-spacing: 0.06em;
        text-transform: uppercase;
      }
      .workshop-bar {
        height: 6px;
        border: 1px solid var(--app-ink);
        background: var(--app-paper-2);
        overflow: hidden;
      }
      .workshop-bar span {
        display: block;
        height: 100%;
        background: var(--accent-reward);
        transition: width var(--dur) var(--ease-standard);
      }
      .compose-btn {
        flex: 0 0 auto;
        min-height: 44px;
        border: 1px solid var(--app-ink);
        background: transparent;
        color: var(--app-ink);
        padding: 0 var(--space-4);
        font-family: var(--mono);
        font-size: var(--type-mono);
        font-weight: var(--weight-medium);
        letter-spacing: 0.08em;
        text-transform: uppercase;
        cursor: pointer;
      }
      .compose-btn:disabled {
        border-color: var(--app-paper-3);
        color: var(--app-ink-3);
        cursor: default;
      }
      .compose-btn:not(:disabled) {
        background: var(--app-ink);
        color: var(--app-paper);
      }
      .seal-grid {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-5);
      }
      .story-seal-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: var(--space-4);
        margin-top: var(--space-4);
      }
      .story-seal-card {
        display: grid;
        grid-template-columns: 76px minmax(0, 1fr);
        align-items: center;
        gap: var(--space-3);
        min-height: 96px;
        border: 1px solid var(--app-ink);
        background: var(--app-sheet);
        padding: var(--space-2);
      }
      .story-seal-art {
        position: relative;
        width: 76px;
        aspect-ratio: 1;
        display: grid;
        place-items: center;
        overflow: hidden;
        border: 1px solid var(--app-ink);
        background: var(--app-paper-2);
      }
      .story-seal-art :global(img) {
        object-fit: cover;
      }
      .story-seal-ring {
        position: absolute;
        inset: 7px;
        border: 1.5px solid var(--app-paper);
        border-radius: 999px;
        box-shadow: 0 0 0 1px color-mix(in srgb, var(--app-ink) 38%, transparent);
        pointer-events: none;
      }
      .story-seal-card.fallback .story-seal-art {
        border: 0;
        background: transparent;
        overflow: visible;
      }
      .story-seal-meta {
        min-width: 0;
        display: grid;
        gap: 4px;
      }
      .story-seal-meta span,
      .story-seal-meta em {
        color: var(--app-ink-3);
        font-family: var(--mono);
        font-size: var(--type-mono);
        font-style: normal;
        font-weight: var(--weight-medium);
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }
      .story-seal-meta strong {
        min-width: 0;
        overflow-wrap: anywhere;
        font-family: var(--app-serif);
        font-style: italic;
        font-weight: var(--weight-medium);
        font-size: 1.05rem;
        line-height: 1.12;
      }
      .token-grid {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-3);
      }
      .almanac-loading,
      .almanac-empty {
        margin-top: var(--space-5);
        border: 1px solid var(--app-ink);
        background: var(--app-sheet);
        padding: var(--space-4);
      }
      .almanac-loading {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        color: var(--app-ink-2);
      }
      .almanac-empty h2 {
        margin: 0 0 var(--space-2);
        font-family: var(--app-serif);
        font-style: italic;
        font-weight: var(--weight-medium);
        font-size: 1.4rem;
      }
      .almanac-empty p {
        margin: 0;
        color: var(--app-ink-2);
        line-height: 1.45;
      }
      .spin { animation: spin 1s linear infinite; }
      @keyframes spin { to { transform: rotate(360deg); } }
      @media (prefers-reduced-motion: reduce) { .spin { animation: none; } }
    `}</style>
  );
}

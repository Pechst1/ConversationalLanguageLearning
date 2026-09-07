/* La Bibliothèque — the imported-books index, on the Claude design (Atelier V2).
 *
 * This is the migrated home of the old `/stories` screen (WP-20). The data flow
 * is unchanged — one GET of `/stories`, the same `Story` row shape, the same
 * upload affordance — but the chrome is the design system's: a kicker, one
 * Garamond italic headline, a blue story hero for the text most recently in
 * hand, then paper rows for the rest of the shelf. Every rule below is an
 * `--av2-*` token, written `.av2 .bib-…`.
 *
 * The route stays behind `STORY_FEATURE_VISIBLE`: with the flag off the page
 * renders nothing and sends the learner to the Atelier, exactly as before.
 */

import React, { useCallback, useEffect, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import UploadBookModal from '@/components/story/UploadBookModal';
import {
  Action,
  ArrowRightIcon,
  AtelierV2Root,
  Chip,
  DoneBadge,
  LockIcon,
  Row,
  Skeleton,
  StateBlock,
} from '@/components/atelier-v2/ui';
import { STORY_FEATURE_VISIBLE } from '@/lib/launch-flags';
import apiService from '@/services/api';

interface Story {
  id: string;
  title: string;
  subtitle: string | null;
  source_book: string | null;
  source_author: string | null;
  target_levels: string[];
  themes: string[];
  estimated_duration_minutes: number;
  cover_image_url: string | null;
  is_unlocked: boolean;
  progress: {
    current_chapter_title: string | null;
    completion_percentage: number;
    status: string;
    last_played_at: string | null;
  } | null;
}

interface BibliothequePageProps {
  stories?: Story[];
}

function hasStarted(story: Story) {
  return Boolean(story.progress && story.progress.status !== 'not_started');
}

function isFinished(story: Story) {
  return story.progress?.status === 'completed';
}

/** The meta line under a row: level, reading time, and real progress only. */
function metaLine(story: Story): string {
  const parts: string[] = [];
  const level = story.target_levels?.[0];
  if (level) parts.push(level);
  if (story.estimated_duration_minutes) parts.push(`${story.estimated_duration_minutes} min`);
  if (story.progress && story.progress.status !== 'not_started') {
    parts.push(`${Math.round(story.progress.completion_percentage)} %`);
  }
  return parts.join(' · ');
}

export default function BibliothequePage({ stories = [] }: BibliothequePageProps) {
  const router = useRouter();
  const [storyList, setStoryList] = useState(stories);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

  const loadStories = useCallback(async () => {
    if (!STORY_FEATURE_VISIBLE) return;
    try {
      const rows = await apiService.get<Story[]>('/stories');
      setStoryList(Array.isArray(rows) ? rows : []);
      setFailed(false);
    } catch (error) {
      console.error('Failed to fetch stories:', error);
      setStoryList([]);
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!STORY_FEATURE_VISIBLE) {
      void router.replace('/atelier');
      return;
    }
    void loadStories();
  }, [loadStories, router]);

  const handleUploadSuccess = () => {
    void loadStories();
  };

  if (!STORY_FEATURE_VISIBLE) return null;

  /* The hero is the first text on the shelf; the rows are everything after it,
     so nothing is drawn twice. */
  const featured = storyList[0] || null;
  const rest = storyList.slice(1);

  return (
    <>
      <Head>
        <title>La bibliothèque · L’Atelier</title>
      </Head>
      <AtelierV2Root as="main" className="bib-page" aria-label="La bibliothèque">
        <header className="bib-head">
          <p className="av2-label">
            {loading
              ? 'Ouverture de la bibliothèque…'
              : `${storyList.length} texte${storyList.length === 1 ? '' : 's'} sur l’étagère`}
          </p>
          {/* the one Garamond italic headline on this screen */}
          <h1 className="av2-headline av2-headline--screen">La bibliothèque</h1>
          <p className="av2-body av2-body--lg">
            Les livres importés et les lectures d’à-côté vivent ici. Le feuilleton du jour reste
            dans Le Feuilleton.
          </p>
          <Action
            tone="secondary"
            inline
            onClick={() => setIsUploadModalOpen(true)}
            iconAfter={<ArrowRightIcon size={16} />}
          >
            Importer un livre
          </Action>
        </header>

        {loading ? (
          <div className="bib-skeleton" aria-busy="true" aria-live="polite">
            <span className="bib-sr">Chargement de la bibliothèque</span>
            <Skeleton height={168} radius={24} />
            <Skeleton height={64} radius={16} />
            <Skeleton height={64} radius={16} />
          </div>
        ) : failed ? (
          <StateBlock
            tone="error"
            title="L’étagère n’a pas pu être ouverte."
            body="La liaison avec la bibliothèque a échoué. Rien n’est perdu ; réessayez dans un instant."
            action={{ label: 'Réessayer', onSelect: () => void loadStories() }}
          />
        ) : storyList.length === 0 ? (
          <StateBlock
            tone="empty"
            title="L’étagère est encore vide."
            body="Importez un livre et il sera découpé en courtes épisodes de lecture, rangés ici."
            action={{ label: 'Importer un premier livre', onSelect: () => setIsUploadModalOpen(true) }}
          />
        ) : (
          <>
            {featured && (
              <section className="bib-hero av2-surface av2-surface--blue av2-surface--hero" aria-label="Texte en cours">
                <div className="bib-hero__art">
                  {featured.cover_image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={featured.cover_image_url} alt="" />
                  ) : (
                    <span className="av2-body">
                      {featured.source_book || 'La couverture de ce texte n’est pas encore parue.'}
                    </span>
                  )}
                </div>
                <div className="bib-hero__body">
                  <p className="av2-label">{metaLine(featured) || 'Sur l’étagère'}</p>
                  <h2 className="av2-headline av2-headline--title">{featured.title}</h2>
                  {featured.subtitle && <p className="av2-body">{featured.subtitle}</p>}
                  {featured.source_author && (
                    <p className="av2-body">De {featured.source_author}</p>
                  )}
                  {featured.themes && featured.themes.length > 0 && (
                    <div className="bib-chips">
                      {featured.themes.slice(0, 3).map((theme) => (
                        <Chip key={theme} tone="quiet">
                          {theme}
                        </Chip>
                      ))}
                    </div>
                  )}
                  {hasStarted(featured) && featured.progress?.current_chapter_title && (
                    <p className="av2-body">En cours : {featured.progress.current_chapter_title}</p>
                  )}
                  {/* the one tactile 3D press on this screen */}
                  <Action
                    tone="secondary"
                    disabled={!featured.is_unlocked}
                    onClick={() => router.push(`/bibliotheque/${featured.id}`)}
                    iconAfter={<ArrowRightIcon size={18} />}
                  >
                    {!featured.is_unlocked
                      ? 'Verrouillé'
                      : hasStarted(featured)
                        ? 'Reprendre la lecture'
                        : 'Commencer la lecture'}
                  </Action>
                </div>
              </section>
            )}

            {rest.length > 0 && (
              <div className="bib-rows" aria-label="Le reste de l’étagère">
                {rest.map((story) => {
                  const isLocked = !story.is_unlocked;
                  return (
                    <Row
                      key={story.id}
                      className="bib-row"
                      eyebrow={metaLine(story) || 'Sur l’étagère'}
                      title={story.title}
                      lead={
                        <span className="bib-thumb" aria-hidden="true">
                          {story.cover_image_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={story.cover_image_url} alt="" />
                          ) : null}
                        </span>
                      }
                      badge={
                        isLocked ? (
                          <span className="bib-row__lock" role="img" aria-label="Verrouillé">
                            <LockIcon size={16} />
                          </span>
                        ) : isFinished(story) ? (
                          <DoneBadge label="Lu" />
                        ) : (
                          <span className="bib-row__go" aria-hidden="true">
                            <ArrowRightIcon size={18} />
                          </span>
                        )
                      }
                      disabled={isLocked}
                      onSelect={() => router.push(`/bibliotheque/${story.id}`)}
                    />
                  );
                })}
              </div>
            )}
          </>
        )}

        <UploadBookModal
          isOpen={isUploadModalOpen}
          onClose={() => setIsUploadModalOpen(false)}
          onSuccess={handleUploadSuccess}
        />
      </AtelierV2Root>
      <PhoneProductNav active="atelier" />
      <style jsx global>{`
        body { background: var(--app-paper); }
        .av2.bib-page {
          min-height: 100vh;
          max-width: 560px;
          margin: 0 auto;
          padding: 22px 18px calc(var(--phone-bottom-nav-space, 88px) + 24px);
          display: flex;
          flex-direction: column;
          gap: 18px;
        }
        .av2 .bib-head { display: flex; flex-direction: column; gap: 8px; align-items: flex-start; }
        .av2 .bib-head .av2-btn { margin-top: 4px; }
        .av2 .bib-skeleton { display: flex; flex-direction: column; gap: 12px; }
        .av2 .bib-sr {
          position: absolute; width: 1px; height: 1px; overflow: hidden;
          clip: rect(0 0 0 0); white-space: nowrap;
        }
        .av2 .bib-hero { display: flex; flex-direction: column; }
        .av2 .bib-hero__art {
          aspect-ratio: 16 / 9;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 16px;
          text-align: center;
          background: var(--av2-blue-deep);
          overflow: hidden;
        }
        .av2 .bib-hero__art img { width: 100%; height: 100%; object-fit: cover; display: block; }
        .av2 .bib-hero__body {
          display: flex;
          flex-direction: column;
          gap: 8px;
          align-items: flex-start;
          padding: 16px 18px 18px;
        }
        .av2 .bib-hero__body .av2-btn { margin-top: 6px; }
        .av2 .bib-rows { display: flex; flex-direction: column; gap: 10px; }
        .av2 .bib-thumb {
          flex: none;
          width: 44px;
          height: 56px;
          border-radius: 8px;
          background: var(--av2-line);
          overflow: hidden;
        }
        .av2 .bib-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
        .av2 .bib-row__go,
        .av2 .bib-row__lock {
          flex: none;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 28px;
          height: 28px;
          color: var(--av2-muted);
        }
        .av2 .bib-row__lock { border: 2px dashed var(--av2-line-2); border-radius: 999px; }
      `}</style>
    </>
  );
}

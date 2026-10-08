/* La Bibliothèque — one text: what it is, where you are in it, and the one way
 * forward. Migrated from the legacy `/stories/[storyId]` screen (WP-20) onto
 * the Claude design (Atelier V2).
 *
 * The data flow is untouched: `useStoryDetail` for the text and its chapters,
 * `useStartStory` to open the first one. What changed is the chrome — a blue
 * story hero, one Garamond headline, an av2 progress rule and an av2 chapter
 * timeline instead of the old ruled cards — and every route now points at
 * `/bibliotheque/…`.
 */

import React from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import ChapterTimeline from '@/components/stories/ChapterTimeline';
import StoryProgressOverview from '@/components/stories/StoryProgressOverview';
import {
  Action,
  ArrowLeftIcon,
  ArrowRightIcon,
  AtelierV2Root,
  Chip,
  IconAction,
  Skeleton,
  StateBlock,
} from '@/components/atelier-v2/ui';
import { useStoryDetail, useStartStory } from '@/hooks/useStories';
import { bibliothequeCopy, fill } from '@/components/stories/bibliotheque-copy';
import { STORY_FEATURE_VISIBLE } from '@/lib/launch-flags';
import { useChromeLanguage } from '@/lib/learner-language';

export default function BibliothequeStoryPage() {
  const router = useRouter();
  const language = useChromeLanguage();
  const t = bibliothequeCopy(language);
  const { storyId } = router.query;
  const resolvedStoryId = STORY_FEATURE_VISIBLE && typeof storyId === 'string' ? storyId : null;

  const { storyDetail, loading, error } = useStoryDetail(resolvedStoryId);
  const { startStory, loading: startingStory } = useStartStory();

  React.useEffect(() => {
    if (!STORY_FEATURE_VISIBLE) void router.replace('/atelier');
  }, [router]);

  if (!STORY_FEATURE_VISIBLE) return null;

  const handleStartStory = async () => {
    if (!resolvedStoryId) return;

    try {
      const result = await startStory(resolvedStoryId);

      // Navigate to first chapter
      if (result.chapter?.id) {
        router.push(`/bibliotheque/${resolvedStoryId}/chapter/${result.chapter.id}`);
      }
    } catch (err) {
      console.error('Failed to start story:', err);
    }
  };

  const handleContinueStory = () => {
    if (!storyDetail?.user_progress?.current_chapter_id) return;
    router.push(`/bibliotheque/${resolvedStoryId}/chapter/${storyDetail.user_progress.current_chapter_id}`);
  };

  const shell = (children: React.ReactNode) => (
    <>
      <Head>
        <title>La bibliothèque · L’Atelier</title>
      </Head>
      <AtelierV2Root as="main" className="bib-detail" aria-label={t.detail_aria}>
        <div className="bib-detail__nav">
          <IconAction label={t.back_to_library} onClick={() => router.push('/bibliotheque')}>
            <ArrowLeftIcon size={18} />
          </IconAction>
          <p className="av2-label">La bibliothèque</p>
        </div>
        {children}
      </AtelierV2Root>
      <PhoneProductNav active="atelier" />
      <BibliothequeDetailStyles />
    </>
  );

  if (loading) {
    return shell(
      <div className="bib-skeleton" aria-busy="true" aria-live="polite">
        <span className="bib-sr">{t.text_opening}</span>
        <Skeleton height={180} radius={24} />
        <Skeleton height={96} radius={16} />
        <Skeleton height={64} radius={16} />
      </div>,
    );
  }

  if (error || !storyDetail) {
    return shell(
      <StateBlock
        tone="error"
        title={t.text_not_found}
        body={error || t.text_removed}
        action={{ label: t.back_to_library, onSelect: () => router.push('/bibliotheque') }}
      />,
    );
  }

  const { story, chapters, user_progress } = storyDetail;
  const isStarted = user_progress?.status === 'in_progress';
  const isCompleted = user_progress?.status === 'completed';
  const totalChapters = story.total_chapters ?? chapters.length;
  const level = story.difficulty_level || story.target_levels?.[0] || null;
  const themes = story.theme_tags || story.themes || [];

  return shell(
    <>
      <section className="bib-hero av2-surface av2-surface--blue av2-surface--hero">
        <div className="bib-hero__art">
          {story.cover_image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={story.cover_image_url} alt="" />
          ) : (
            <span className="av2-body">{t.no_cover}</span>
          )}
        </div>
        <div className="bib-hero__body">
          <p className="av2-label">
            {[level, fill(totalChapters === 1 ? t.chapter_count_one : t.chapter_count_many, { n: totalChapters }),
              story.estimated_duration_minutes ? `${story.estimated_duration_minutes} min` : null]
              .filter(Boolean)
              .join(' · ')}
          </p>
          {/* the one Garamond italic headline on this screen */}
          <h1 className="av2-headline av2-headline--display">{story.title}</h1>
          {story.author || story.source_author ? (
            <p className="av2-body">{fill(t.by_author, { author: story.author || story.source_author || '' })}</p>
          ) : null}
        </div>
      </section>

      {story.description && (
        <section className="av2-surface bib-block" aria-label={t.about_text}>
          <p className="av2-label">{t.about_text}</p>
          <p className="av2-body av2-body--lg">{story.description}</p>
          {themes.length > 0 && (
            <div className="bib-chips">
              {themes.map((tag) => (
                <Chip key={tag} tone="quiet">
                  {tag}
                </Chip>
              ))}
            </div>
          )}
        </section>
      )}

      {user_progress && (
        <StoryProgressOverview progress={user_progress} totalChapters={totalChapters} />
      )}

      <section className="av2-surface bib-block" aria-label={t.chapters}>
        <p className="av2-label">
          {isCompleted
            ? t.chapters_all_read
            : isStarted
              ? t.chapters_pick_up
              : t.chapters_unlock}
        </p>
        <h2 className="av2-headline av2-headline--title">{t.chapters}</h2>
        <ChapterTimeline
          chapters={chapters}
          currentChapterId={user_progress?.current_chapter_id || null}
        />
      </section>

      <div className="bib-detail__foot">
        {isCompleted ? (
          <Action tone="secondary" onClick={() => router.push('/bibliotheque')} iconAfter={<ArrowRightIcon size={18} />}>
            {t.back_to_shelf}
          </Action>
        ) : isStarted ? (
          /* the one tactile 3D press on this screen */
          <Action
            tone="story"
            onClick={handleContinueStory}
            disabled={!user_progress?.current_chapter_id}
            iconAfter={<ArrowRightIcon size={18} />}
          >
            {t.resume_reading}
          </Action>
        ) : (
          <Action
            tone="story"
            onClick={handleStartStory}
            pending={startingStory}
            pendingLabel={t.opening}
            iconAfter={<ArrowRightIcon size={18} />}
          >
            {t.start_reading}
          </Action>
        )}
      </div>
    </>,
  );
}

function BibliothequeDetailStyles() {
  return (
    <style jsx global>{`
      body { background: var(--app-paper); }
      .av2.bib-detail {
        min-height: 100vh;
        max-width: 560px;
        margin: 0 auto;
        padding: 16px 18px calc(var(--phone-bottom-nav-space, 88px) + 24px);
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .av2 .bib-detail__nav { display: flex; align-items: center; gap: 10px; }
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
      .av2 .bib-hero__body { display: flex; flex-direction: column; gap: 6px; padding: 16px 18px 18px; }
      .av2 .bib-detail__foot { display: flex; flex-direction: column; }
    `}</style>
  );
}

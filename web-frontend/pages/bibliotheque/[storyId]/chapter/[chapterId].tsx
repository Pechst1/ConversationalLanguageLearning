/* La Bibliothèque — one chapter session. Migrated from the legacy
 * `/stories/[storyId]/chapter/[chapterId]` screen (WP-20).
 *
 * The page owns exactly what it owned before: resolve the route, load the
 * chapter, open one session for it, and hand the session to
 * `StorySessionLayout`. Only the waiting and failure states are drawn here, and
 * they are now the design's own `StateBlock`/`Skeleton` rather than a spinner
 * on a grey field.
 */

import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import StorySessionLayout from '@/components/stories/StorySessionLayout';
import { AtelierV2Root, Skeleton, StateBlock } from '@/components/atelier-v2/ui';
import { useChapter, useStartChapterSession } from '@/hooks/useStories';
import { STORY_FEATURE_VISIBLE } from '@/lib/launch-flags';

export default function BibliothequeChapterPage() {
  const router = useRouter();
  const { storyId, chapterId } = router.query;

  const resolvedStoryId = STORY_FEATURE_VISIBLE && typeof storyId === 'string' ? storyId : null;
  const resolvedChapterId = STORY_FEATURE_VISIBLE && typeof chapterId === 'string' ? chapterId : null;

  const { chapter, loading: loadingChapter } = useChapter(resolvedStoryId, resolvedChapterId);
  const { startChapterSession, loading: startingSession } = useStartChapterSession();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!STORY_FEATURE_VISIBLE) void router.replace('/atelier');
  }, [router]);

  // Auto-start session when chapter loads
  useEffect(() => {
    if (!resolvedStoryId || !resolvedChapterId || sessionId || startingSession) {
      return;
    }

    const initializeSession = async () => {
      try {
        const sessionData = await startChapterSession({
          storyId: resolvedStoryId,
          chapterId: resolvedChapterId,
          planned_duration_minutes: 15,
        });

        if (sessionData?.session?.id) {
          setSessionId(sessionData.session.id);
        } else {
          throw new Error('Failed to create session');
        }
      } catch (err) {
        console.error('Failed to start chapter session:', err);
        setError(err instanceof Error ? err.message : 'Failed to start session');
      }
    };

    initializeSession();
  }, [resolvedStoryId, resolvedChapterId, sessionId, startChapterSession, startingSession]);

  if (!STORY_FEATURE_VISIBLE) return null;

  const gate = (children: React.ReactNode) => (
    <>
      <Head>
        <title>La bibliothèque · L’Atelier</title>
      </Head>
      <AtelierV2Root as="main" className="bib-gate" aria-label="Ouverture du chapitre">
        {children}
      </AtelierV2Root>
      <style jsx global>{`
        body { background: var(--app-paper); }
        .av2.bib-gate {
          min-height: 100vh;
          max-width: 560px;
          margin: 0 auto;
          padding: 24px 18px;
          display: flex;
          flex-direction: column;
          justify-content: center;
          gap: 14px;
        }
        .av2 .bib-sr {
          position: absolute; width: 1px; height: 1px; overflow: hidden;
          clip: rect(0 0 0 0); white-space: nowrap;
        }
      `}</style>
    </>
  );

  // Loading state
  if (loadingChapter || startingSession || !sessionId) {
    if (error) {
      return gate(
        <StateBlock
          tone="error"
          title="La séance n’a pas pu s’ouvrir."
          body={error}
          action={{
            label: 'Retour au texte',
            onSelect: () => router.push(`/bibliotheque/${storyId}`),
          }}
        />,
      );
    }
    return gate(
      <div aria-busy="true" aria-live="polite">
        <span className="bib-sr">
          {loadingChapter ? 'Ouverture du chapitre…' : 'Ouverture de la séance…'}
        </span>
        <Skeleton height={120} radius={24} />
      </div>,
    );
  }

  // Error state
  if (error || !chapter) {
    return gate(
      <StateBlock
        tone="error"
        title="Ce chapitre est introuvable."
        body={error || 'Il a peut-être été retiré du texte.'}
        action={{
          label: 'Retour au texte',
          onSelect: () => router.push(`/bibliotheque/${storyId}`),
        }}
      />,
    );
  }

  return (
    <StorySessionLayout
      storyId={resolvedStoryId!}
      chapterId={resolvedChapterId!}
      sessionId={sessionId}
      chapter={chapter}
    />
  );
}

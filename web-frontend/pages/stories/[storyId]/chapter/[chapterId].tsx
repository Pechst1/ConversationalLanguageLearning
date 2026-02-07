import React, { useState, useEffect } from 'react';
import { getSession } from 'next-auth/react';
import { useRouter } from 'next/router';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useChapter, useStartChapterSession } from '@/hooks/useStories';
import StorySessionLayout from '@/components/stories/StorySessionLayout';

export default function StoryChapterPage() {
  const router = useRouter();
  const { storyId, chapterId } = router.query;

  const numericStoryId = typeof storyId === 'string' ? parseInt(storyId, 10) : null;
  const numericChapterId = typeof chapterId === 'string' ? parseInt(chapterId, 10) : null;

  const { chapter, loading: loadingChapter } = useChapter(numericStoryId, numericChapterId);
  const { startChapterSession, loading: startingSession } = useStartChapterSession();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Auto-start session when chapter loads
  useEffect(() => {
    if (!numericStoryId || !numericChapterId || sessionId || startingSession) {
      return;
    }

    const initializeSession = async () => {
      try {
        const sessionData = await startChapterSession({
          storyId: numericStoryId,
          chapterId: numericChapterId,
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
  }, [numericStoryId, numericChapterId, sessionId, startChapterSession, startingSession]);

  // Loading state
  if (loadingChapter || startingSession || !sessionId) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">
            {loadingChapter ? 'Loading chapter...' : 'Starting session...'}
          </p>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !chapter) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error || 'Chapter not found'}</p>
          <Button onClick={() => router.push(`/stories/${storyId}`)}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Story
          </Button>
        </div>
      </div>
    );
  }

  return (
    <StorySessionLayout
      storyId={numericStoryId!}
      chapterId={numericChapterId!}
      sessionId={sessionId}
      chapter={chapter}
    />
  );
}

export async function getServerSideProps(context: any) {
  const session = await getSession(context);

  if (!session) {
    return {
      redirect: {
        destination: '/auth/signin',
        permanent: false,
      },
    };
  }

  return {
    props: {},
  };
}

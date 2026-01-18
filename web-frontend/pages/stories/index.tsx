import React, { useState } from 'react';
import { getSession } from 'next-auth/react';
import { useRouter } from 'next/router';
import { BookOpen } from 'lucide-react';
import { useStories } from '@/hooks/useStories';
import StoryCard from '@/components/stories/StoryCard';
import StoryFilters from '@/components/stories/StoryFilters';

export default function StoriesLibraryPage() {
  const router = useRouter();
  const [difficulty, setDifficulty] = useState<string | undefined>(undefined);
  const [theme, setTheme] = useState<string | undefined>(undefined);

  const { stories, loading, error } = useStories({ difficulty, theme });

  // Debug logging
  React.useEffect(() => {
    console.log('Stories Hook State:', { stories, loading, error, count: stories?.length });
  }, [stories, loading, error]);

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <BookOpen className="h-8 w-8 text-primary-600" />
          <h1 className="text-3xl font-bold text-gray-900">Interactive Stories</h1>
        </div>
        <p className="text-gray-600">
          Learn French through engaging narrative adventures. Complete chapters, make choices, and unlock new vocabulary in context.
        </p>
      </div>

      {/* Filters */}
      <StoryFilters
        difficulty={difficulty}
        theme={theme}
        onDifficultyChange={setDifficulty}
        onThemeChange={setTheme}
      />

      {/* Loading State */}
      {loading && (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading stories...</p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="text-center py-12">
          <p className="text-red-600">{error}</p>
        </div>
      )}

      {/* Story Grid */}
      {!loading && !error && (
        <>
          {stories.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {stories.map((storyItem) => (
                <StoryCard
                  key={storyItem.story.id}
                  story={storyItem.story}
                  progress={storyItem.user_progress}
                  onClick={() => router.push(`/stories/${storyItem.story.id}`)}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <BookOpen className="h-16 w-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No stories found</h3>
              <p className="text-gray-600">
                {difficulty || theme
                  ? 'Try adjusting your filters to see more stories.'
                  : 'Check back soon for new stories!'}
              </p>
            </div>
          )}
        </>
      )}
    </div>
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

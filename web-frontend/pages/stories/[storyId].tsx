import React from 'react';
import { getSession } from 'next-auth/react';
import { useRouter } from 'next/router';
import { ArrowLeft, BookOpen, Clock, User } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { useStoryDetail, useStartStory } from '@/hooks/useStories';
import DifficultyBadge from '@/components/stories/DifficultyBadge';
import ChapterTimeline from '@/components/stories/ChapterTimeline';
import StoryProgressOverview from '@/components/stories/StoryProgressOverview';

export default function StoryDetailPage() {
  const router = useRouter();
  const { storyId } = router.query;
  const resolvedStoryId = typeof storyId === 'string' ? storyId : null;

  const { storyDetail, loading, error } = useStoryDetail(resolvedStoryId);
  const { startStory, loading: startingStory } = useStartStory();

  const handleStartStory = async () => {
    if (!resolvedStoryId) return;

    try {
      const result = await startStory(resolvedStoryId);

      // Navigate to first chapter
      if (result.chapter?.id) {
        router.push(`/stories/${resolvedStoryId}/chapter/${result.chapter.id}`);
      }
    } catch (err) {
      console.error('Failed to start story:', err);
    }
  };

  const handleContinueStory = () => {
    if (!storyDetail?.user_progress?.current_chapter_id) return;
    router.push(`/stories/${resolvedStoryId}/chapter/${storyDetail.user_progress.current_chapter_id}`);
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading story...</p>
        </div>
      </div>
    );
  }

  if (error || !storyDetail) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="text-center py-12">
          <p className="text-red-600">{error || 'Story not found'}</p>
          <Button className="mt-4" onClick={() => router.push('/stories')}>
            Back to Stories
          </Button>
        </div>
      </div>
    );
  }

  const { story, chapters, user_progress } = storyDetail;
  const isStarted = user_progress?.status === 'in_progress';
  const isCompleted = user_progress?.status === 'completed';

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Back Button */}
      <Button
        variant="ghost"
        onClick={() => router.push('/stories')}
        leftIcon={<ArrowLeft className="h-4 w-4" />}
      >
        Back to Stories
      </Button>

      {/* Hero Section */}
      <div className="relative h-64 rounded-xl overflow-hidden bg-gradient-to-br from-primary-500 to-primary-700">
        {story.cover_image_url ? (
          <img
            src={story.cover_image_url}
            alt={story.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <BookOpen className="h-24 w-24 text-white opacity-50" />
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
        <div className="absolute bottom-0 left-0 right-0 p-6 text-white">
          <div className="mb-2">
            <DifficultyBadge level={story.difficulty_level || 'B1'} />
          </div>
          <h1 className="text-3xl font-bold mb-2">{story.title}</h1>
          {story.author && (
            <div className="flex items-center gap-2 text-sm text-white/90">
              <User className="h-4 w-4" />
              <span>By {story.author}</span>
            </div>
          )}
        </div>
      </div>

      {/* Description */}
      <Card>
        <CardHeader>
          <CardTitle>About this story</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-700 leading-relaxed">{story.description}</p>

          {/* Story Stats */}
          <div className="flex flex-wrap gap-4 mt-4 pt-4 border-t border-gray-200">
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <BookOpen className="h-4 w-4" />
              <span>{story.total_chapters} chapters</span>
            </div>
            {story.estimated_duration_minutes && (
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <Clock className="h-4 w-4" />
                <span>{story.estimated_duration_minutes} minutes</span>
              </div>
            )}
          </div>

          {/* Theme Tags */}
          {story.theme_tags && story.theme_tags.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-4">
              {story.theme_tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-block bg-gray-100 text-gray-700 text-sm px-3 py-1 rounded"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Progress Overview (if started) */}
      {user_progress && (
        <StoryProgressOverview progress={user_progress} totalChapters={story.total_chapters ?? chapters.length} />
      )}

      {/* Chapter List */}
      <Card>
        <CardHeader>
          <CardTitle>Chapters</CardTitle>
          <CardDescription>
            {isCompleted
              ? 'You have completed all chapters!'
              : isStarted
              ? 'Continue your journey through the story'
              : 'Unlock chapters as you progress'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ChapterTimeline
            chapters={chapters}
            currentChapterId={user_progress?.current_chapter_id || null}
          />
        </CardContent>
      </Card>

      {/* Action Button */}
      <div className="flex justify-center pb-8">
        {isCompleted ? (
          <Button
            size="lg"
            variant="outline"
            onClick={() => router.push('/stories')}
          >
            Browse More Stories
          </Button>
        ) : isStarted ? (
          <Button
            size="lg"
            onClick={handleContinueStory}
            disabled={!user_progress?.current_chapter_id}
          >
            Continue Story
          </Button>
        ) : (
          <Button
            size="lg"
            onClick={handleStartStory}
            disabled={startingStory}
          >
            {startingStory ? 'Starting...' : 'Begin Story'}
          </Button>
        )}
      </div>
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

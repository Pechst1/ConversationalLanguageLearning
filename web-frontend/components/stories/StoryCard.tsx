import React from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Clock, BookOpen } from 'lucide-react';
import { StoryBase, StoryProgressSummary } from '@/hooks/useStories';
import DifficultyBadge from './DifficultyBadge';
import ProgressBar from './ProgressBar';

interface StoryCardProps {
  story: StoryBase;
  progress: StoryProgressSummary | null;
  onClick: () => void;
}

export default function StoryCard({ story, progress, onClick }: StoryCardProps) {
  const completionPercent = progress?.completion_percentage || 0;
  const isStarted = progress?.is_started || false;
  const isCompleted = progress?.is_completed || false;

  return (
    <Card className="overflow-hidden hover:shadow-lg transition-shadow duration-200 cursor-pointer" onClick={onClick}>
      {/* Cover Image */}
      <div className="relative h-48 bg-gradient-to-br from-primary-500 to-primary-700 overflow-hidden">
        {story.cover_image_url ? (
          <img
            src={story.cover_image_url}
            alt={story.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <BookOpen className="h-16 w-16 text-white opacity-50" />
          </div>
        )}

        {/* Difficulty Badge */}
        <div className="absolute top-3 right-3">
          <DifficultyBadge level={story.difficulty_level || 'B1'} />
        </div>

        {/* Completion Badge */}
        {isCompleted && (
          <div className="absolute top-3 left-3 bg-green-500 text-white text-xs font-bold px-2 py-1 rounded">
            ✓ Completed
          </div>
        )}

        {/* Progress Bar */}
        {isStarted && !isCompleted && (
          <div className="absolute bottom-0 left-0 right-0">
            <ProgressBar value={completionPercent} />
          </div>
        )}
      </div>

      {/* Content */}
      <CardContent className="p-4">
        <h3 className="font-bold text-lg mb-2 text-gray-900 line-clamp-1">{story.title}</h3>
        <p className="text-sm text-gray-600 mb-4 line-clamp-2">{story.description}</p>

        {/* Progress Info */}
        {isStarted && (
          <div className="mb-4 text-xs text-gray-600">
            {isCompleted ? (
              <span className="text-green-600 font-medium">
                Story completed! Earned {progress?.total_xp_earned} XP
              </span>
            ) : (
              <span>
                Chapter {progress?.current_chapter_number} • {progress?.chapters_completed}/{story.total_chapters} completed
              </span>
            )}
          </div>
        )}

        {/* Stats */}
        <div className="flex gap-4 mb-4 text-xs text-gray-500">
          <div className="flex items-center gap-1">
            <BookOpen className="h-3 w-3" />
            <span>{story.total_chapters} chapters</span>
          </div>
          {story.estimated_duration_minutes && (
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              <span>{story.estimated_duration_minutes} min</span>
            </div>
          )}
        </div>

        {/* Tags */}
        {story.theme_tags && story.theme_tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {story.theme_tags.slice(0, 3).map((tag) => (
              <span
                key={tag}
                className="inline-block bg-gray-100 text-gray-700 text-xs px-2 py-1 rounded"
              >
                {tag}
              </span>
            ))}
            {story.theme_tags.length > 3 && (
              <span className="text-xs text-gray-500">+{story.theme_tags.length - 3} more</span>
            )}
          </div>
        )}

        {/* Action Button */}
        <Button
          variant={isStarted ? 'default' : 'outline'}
          className="w-full"
          onClick={(e) => {
            e.stopPropagation();
            onClick();
          }}
        >
          {isCompleted ? (
            'View Story'
          ) : isStarted ? (
            <>Continue • Ch. {progress?.current_chapter_number}</>
          ) : (
            'Start Story'
          )}
        </Button>
      </CardContent>
    </Card>
  );
}

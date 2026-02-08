import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { TrendingUp, BookOpen, Star, Clock } from 'lucide-react';
import { UserStoryProgressBase } from '@/hooks/useStories';
import ProgressBar from './ProgressBar';

interface StoryProgressOverviewProps {
  progress: UserStoryProgressBase;
  totalChapters: number;
}

export default function StoryProgressOverview({ progress, totalChapters }: StoryProgressOverviewProps) {
  const isCompleted = progress.status === 'completed';
  const chaptersCompleted =
    progress.total_chapters_completed ??
    (Array.isArray(progress.chapters_completed) ? progress.chapters_completed.length : 0);
  const minutesSpent = progress.total_time_spent_minutes ?? 0;
  const lastAccessedAt = progress.last_accessed_at ?? progress.last_played_at ?? progress.started_at;

  const stats = [
    {
      label: 'XP Earned',
      value: progress.total_xp_earned,
      icon: TrendingUp,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
    },
    {
      label: 'Chapters Complete',
      value: `${chaptersCompleted}/${totalChapters}`,
      icon: BookOpen,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
    },
    {
      label: 'Perfect Chapters',
      value: progress.perfect_chapters_count,
      icon: Star,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-100',
    },
    {
      label: 'Time Spent',
      value: `${minutesSpent} min`,
      icon: Clock,
      color: 'text-purple-600',
      bgColor: 'bg-purple-100',
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {isCompleted ? '🎉 Story Completed!' : 'Your Progress'}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Progress Bar */}
        {!isCompleted && (
          <div>
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm font-medium text-gray-700">Overall Progress</span>
              <span className="text-sm font-medium text-primary-600">
                {Math.round(progress.completion_percentage)}%
              </span>
            </div>
            <ProgressBar value={progress.completion_percentage} height="h-3" />
          </div>
        )}

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {stats.map((stat) => (
            <div
              key={stat.label}
              className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg"
            >
              <div className={`p-2 rounded ${stat.bgColor}`}>
                <stat.icon className={`h-4 w-4 ${stat.color}`} />
              </div>
              <div>
                <p className="text-xs text-gray-600">{stat.label}</p>
                <p className="text-lg font-bold text-gray-900">{stat.value}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Vocabulary Progress */}
        {(progress.vocabulary_mastered_count ?? 0) > 0 && (
          <div className="pt-4 border-t border-gray-200">
            <p className="text-sm text-gray-600">
              <span className="font-medium text-gray-900">{progress.vocabulary_mastered_count ?? 0}</span>{' '}
              words mastered through this story
            </p>
          </div>
        )}

        {/* Started/Completed Timestamps */}
        <div className="pt-4 border-t border-gray-200 text-xs text-gray-500 space-y-1">
          <p>Started: {new Date(progress.started_at).toLocaleDateString()}</p>
          {progress.completed_at && (
            <p>Completed: {new Date(progress.completed_at).toLocaleDateString()}</p>
          )}
          <p>Last accessed: {new Date(lastAccessedAt).toLocaleDateString()}</p>
        </div>
      </CardContent>
    </Card>
  );
}

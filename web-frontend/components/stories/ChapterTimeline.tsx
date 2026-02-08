import React from 'react';
import { Lock, CheckCircle, Circle } from 'lucide-react';
import { ChapterWithStatus } from '@/hooks/useStories';

interface ChapterTimelineProps {
  chapters: ChapterWithStatus[];
  currentChapterId: string | null;
}

export default function ChapterTimeline({ chapters, currentChapterId }: ChapterTimelineProps) {
  return (
    <div className="relative">
      {/* Vertical line connecting chapters */}
      <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-gray-200" />

      {chapters.map((chapterWithStatus, idx) => {
        const { chapter, is_locked, is_completed, was_perfect } = chapterWithStatus;
        const isCurrent = chapter.id === currentChapterId;

        return (
          <div key={chapter.id} className="relative flex items-start gap-4 mb-8 last:mb-0">
            {/* Chapter Node */}
            <div
              className={`
                w-16 h-16 rounded-full flex items-center justify-center z-10 flex-shrink-0
                border-4 border-white shadow-md
                ${
                  is_completed
                    ? 'bg-green-500 text-white'
                    : isCurrent
                    ? 'bg-primary-500 text-white animate-pulse'
                    : is_locked
                    ? 'bg-gray-300 text-gray-500'
                    : 'bg-white border-primary-500 text-primary-600'
                }
              `}
            >
              {is_completed ? (
                <CheckCircle className="h-8 w-8" />
              ) : is_locked ? (
                <Lock className="h-6 w-6" />
              ) : isCurrent ? (
                <Circle className="h-8 w-8 fill-current" />
              ) : (
                <span className="text-2xl font-bold">{chapter.sequence_order ?? chapter.order_index + 1}</span>
              )}
            </div>

            {/* Chapter Info */}
            <div className="flex-1 pt-3">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <h3 className={`font-bold text-lg ${is_locked ? 'text-gray-400' : 'text-gray-900'}`}>
                    {chapter.title}
                  </h3>
                  {chapter.synopsis && (
                    <p className={`text-sm mt-1 ${is_locked ? 'text-gray-400' : 'text-gray-600'}`}>
                      {chapter.synopsis}
                    </p>
                  )}

                  {/* Chapter Stats */}
                  {!is_locked && !is_completed && (
                    <div className="mt-3 flex flex-wrap gap-3 text-xs text-gray-500">
                      <span>{chapter.min_turns}-{chapter.max_turns} turns</span>
                      {chapter.narrative_goals && chapter.narrative_goals.length > 0 && (
                        <span>{chapter.narrative_goals.length} goals</span>
                      )}
                      <span className="text-primary-600 font-medium">{chapter.completion_xp} XP</span>
                    </div>
                  )}

                  {/* Completion Status */}
                  {is_completed && (
                    <div className="mt-2 flex items-center gap-2 text-sm">
                      <span className="text-green-600 font-medium flex items-center gap-1">
                        <CheckCircle className="h-4 w-4" />
                        Completed
                      </span>
                      {was_perfect && (
                        <span className="text-yellow-600 font-medium">⭐ Perfect</span>
                      )}
                    </div>
                  )}

                  {/* Current Chapter Indicator */}
                  {isCurrent && !is_completed && (
                    <div className="mt-2">
                      <span className="inline-block bg-primary-100 text-primary-700 text-xs font-medium px-2 py-1 rounded">
                        Current Chapter
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Branching Indicator */}
              {chapter.branching_choices && chapter.branching_choices.length > 0 && !is_locked && (
                <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                  <p className="text-xs font-medium text-amber-800">
                    🔀 This chapter has {chapter.branching_choices.length} branching paths
                  </p>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

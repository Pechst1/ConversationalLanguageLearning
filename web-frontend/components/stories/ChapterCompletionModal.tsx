import React from 'react';
import { useRouter } from 'next/router';
import { Trophy, Star, Gift, ArrowRight, BookOpen } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { ChapterCompletionResponse, ChapterBase } from '@/hooks/useStories';

interface ChapterCompletionModalProps {
  isOpen: boolean;
  onClose: () => void;
  result: ChapterCompletionResponse;
  storyId: number;
  storyTitle: string;
}

export default function ChapterCompletionModal({
  isOpen,
  onClose,
  result,
  storyId,
  storyTitle,
}: ChapterCompletionModalProps) {
  const router = useRouter();

  if (!isOpen) return null;

  const handleContinue = () => {
    if (result.story_completed) {
      // Navigate back to story detail to see completion
      router.push(`/stories/${storyId}`);
    } else if (result.next_chapter_id) {
      // Navigate to next chapter
      router.push(`/stories/${storyId}/chapter/${result.next_chapter_id}`);
    } else {
      onClose();
    }
  };

  const handleReturnToStory = () => {
    router.push(`/stories/${storyId}`);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden animate-scale-in">
        {/* Header with celebration icon */}
        <div className={`p-8 text-center ${
          result.story_completed
            ? 'bg-gradient-to-br from-purple-500 to-pink-500'
            : result.is_perfect
            ? 'bg-gradient-to-br from-yellow-400 to-orange-500'
            : 'bg-gradient-to-br from-blue-500 to-indigo-600'
        }`}>
          <div className="text-6xl mb-4 animate-bounce">
            {result.story_completed ? '🎊' : result.is_perfect ? '⭐' : '🎉'}
          </div>
          <h2 className="text-3xl font-bold text-white mb-2">
            {result.story_completed
              ? 'Story Completed!'
              : result.is_perfect
              ? 'Perfect Chapter!'
              : 'Chapter Complete!'}
          </h2>
          <p className="text-white text-opacity-90">
            {result.story_completed
              ? `You've finished "${storyTitle}"!`
              : result.is_perfect
              ? 'All goals achieved perfectly!'
              : 'Great work! The story continues...'}
          </p>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* XP Earned */}
          <div className="bg-gradient-to-r from-yellow-400 to-orange-400 text-white rounded-xl p-6 text-center shadow-lg">
            <div className="flex items-center justify-center gap-2 mb-2">
              <Star className="h-6 w-6" />
              <span className="text-sm font-semibold uppercase tracking-wide">XP Earned</span>
            </div>
            <div className="text-5xl font-bold">+{result.xp_earned}</div>
            {result.is_perfect && (
              <div className="text-sm mt-2 font-medium">Perfect Bonus Applied!</div>
            )}
          </div>

          {/* Achievements Unlocked */}
          {result.achievements_unlocked && result.achievements_unlocked.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                <Trophy className="h-5 w-5 text-yellow-600" />
                <span>Achievements Unlocked</span>
              </div>
              <div className="space-y-2">
                {result.achievements_unlocked.map((achievement, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-3 p-3 bg-yellow-50 border-2 border-yellow-200 rounded-lg"
                  >
                    <div className="flex-shrink-0 w-10 h-10 bg-yellow-400 rounded-full flex items-center justify-center">
                      <Trophy className="h-5 w-5 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-gray-900">
                        {achievement.name || achievement.title || 'New Achievement'}
                      </p>
                      {achievement.description && (
                        <p className="text-xs text-gray-600 truncate">
                          {achievement.description}
                        </p>
                      )}
                    </div>
                    {achievement.xp_reward && (
                      <div className="flex-shrink-0 text-sm font-bold text-yellow-700">
                        +{achievement.xp_reward} XP
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Next Chapter Preview */}
          {result.next_chapter && !result.story_completed && (
            <div className="bg-blue-50 border-2 border-blue-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <BookOpen className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-blue-900 mb-1">Next Chapter</p>
                  <p className="text-base font-bold text-gray-900">
                    {result.next_chapter.title}
                  </p>
                  {result.next_chapter.synopsis && (
                    <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                      {result.next_chapter.synopsis}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Story Completed Message */}
          {result.story_completed && (
            <div className="bg-gradient-to-r from-purple-100 to-pink-100 border-2 border-purple-300 rounded-lg p-4 text-center">
              <Gift className="h-12 w-12 text-purple-600 mx-auto mb-2" />
              <p className="text-lg font-semibold text-purple-900 mb-1">
                Félicitations!
              </p>
              <p className="text-sm text-purple-700">
                You've completed the entire story. Your progress has been saved.
              </p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 pt-2">
            {result.story_completed ? (
              <>
                <Button
                  variant="outline"
                  onClick={handleReturnToStory}
                  className="flex-1"
                >
                  View Summary
                </Button>
                <Button
                  onClick={() => router.push('/stories')}
                  className="flex-1"
                >
                  Browse Stories
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="outline"
                  onClick={handleReturnToStory}
                  className="flex-1"
                >
                  Story Overview
                </Button>
                <Button
                  onClick={handleContinue}
                  className="flex-1 group"
                >
                  Continue
                  <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

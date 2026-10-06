/* The end of a chapter, on the Claude design.
 *
 * The design's bottom sheet, not a confetti overlay: one headline, the real XP,
 * the achievements the server actually unlocked, and the next chapter if there
 * is one. Every route it offers points at `/bibliotheque/…`.
 */

import React from 'react';
import { useRouter } from 'next/router';

import { Action, ArrowRightIcon, BottomSheet, Chip } from '@/components/atelier-v2/ui';
import { ChapterCompletionResponse } from '@/hooks/useStories';
import { useChromeLanguage } from '@/lib/learner-language';

import { bibliothequeCopy, fill } from './bibliotheque-copy';

interface ChapterCompletionModalProps {
  isOpen: boolean;
  onClose: () => void;
  result: ChapterCompletionResponse;
  storyId: string;
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
  const language = useChromeLanguage();
  const t = bibliothequeCopy(language);

  if (!isOpen) return null;

  const handleContinue = () => {
    if (result.story_completed) {
      // Navigate back to story detail to see completion
      router.push(`/bibliotheque/${storyId}`);
    } else if (result.next_chapter_id) {
      // Navigate to next chapter
      router.push(`/bibliotheque/${storyId}/chapter/${result.next_chapter_id}`);
    } else {
      onClose();
    }
  };

  const handleReturnToStory = () => {
    router.push(`/bibliotheque/${storyId}`);
  };

  const title = result.story_completed
    ? t.done_story
    : result.is_perfect
      ? t.done_perfect
      : t.done_chapter;

  return (
    <BottomSheet open={isOpen} onClose={onClose} eyebrow="La bibliothèque" title={title}>
      <div className="bib-done">
        <p className="av2-body av2-body--lg">
          {result.story_completed
            ? fill(t.finished_story, { title: storyTitle })
            : result.is_perfect
              ? t.all_goals
              : t.reading_goes_on}
        </p>

        <div className="av2-surface av2-surface--reward bib-done__xp">
          <span className="av2-label">{t.xp_earned}</span>
          <span className="av2-headline av2-headline--display">+{result.xp_earned}</span>
          {result.is_perfect && <span className="av2-label">{t.perfect_bonus}</span>}
        </div>

        {result.achievements_unlocked && result.achievements_unlocked.length > 0 && (
          <div className="bib-block">
            <p className="av2-label">{t.achievements}</p>
            <div className="bib-chips">
              {result.achievements_unlocked.map((achievement, index) => (
                <Chip key={index} tone="reward">
                  {achievement.name || achievement.title || t.new_achievement}
                  {achievement.xp_reward ? ` · +${achievement.xp_reward} XP` : ''}
                </Chip>
              ))}
            </div>
          </div>
        )}

        {result.next_chapter && !result.story_completed && (
          <div className="av2-surface bib-block">
            <p className="av2-label">{t.next_chapter}</p>
            <p className="av2-headline av2-headline--rule">{result.next_chapter.title}</p>
            {result.next_chapter.synopsis && (
              <p className="av2-body">{result.next_chapter.synopsis}</p>
            )}
          </div>
        )}

        <div className="bib-done__actions">
          {result.story_completed ? (
            <>
              <Action tone="done" onClick={handleReturnToStory} iconAfter={<ArrowRightIcon size={18} />}>
                {t.see_recap}
              </Action>
              <Action tone="quiet" onClick={() => router.push('/bibliotheque')}>
                {t.back_to_shelf}
              </Action>
            </>
          ) : (
            <>
              {/* the one tactile 3D press of this sheet */}
              <Action tone="story" onClick={handleContinue} iconAfter={<ArrowRightIcon size={18} />}>
                {t.continue}
              </Action>
              <Action tone="quiet" onClick={handleReturnToStory}>
                {t.return_to_text}
              </Action>
            </>
          )}
        </div>
      </div>
    </BottomSheet>
  );
}

/* The chapter timeline of a Bibliothèque text, on the Claude design (Atelier V2).
 *
 * One node per real chapter, in reading order: an ink check for a chapter that
 * is read, a blue circle for the one in hand, a dashed lock for one that is not
 * open yet, its number otherwise. Colour is never alone — every node also
 * carries a word.
 *
 * Rendered inside an `AtelierV2Root`; its rules live in the Bibliotheque block
 * at the end of `styles/atelier-v2.css`.
 */

import React from 'react';

import { CheckIcon, LockIcon } from '@/components/atelier-v2/ui';
import { ChapterWithStatus } from '@/hooks/useStories';

interface ChapterTimelineProps {
  chapters: ChapterWithStatus[];
  currentChapterId: string | null;
}

export default function ChapterTimeline({ chapters, currentChapterId }: ChapterTimelineProps) {
  return (
    <ol className="bib-timeline">
      {chapters.map((chapterWithStatus) => {
        const { chapter, is_locked, is_completed, was_perfect } = chapterWithStatus;
        const isCurrent = chapter.id === currentChapterId;
        const state = is_completed ? 'done' : isCurrent ? 'current' : is_locked ? 'locked' : 'open';

        return (
          <li className="bib-timeline__item" key={chapter.id} data-state={state}>
            <span className="bib-timeline__node" aria-hidden="true">
              {is_completed ? (
                <CheckIcon size={14} />
              ) : is_locked ? (
                <LockIcon size={14} />
              ) : (
                <span>{chapter.sequence_order ?? chapter.order_index + 1}</span>
              )}
            </span>
            <div className="bib-timeline__body">
              <h3 className="av2-headline av2-headline--rule">{chapter.title}</h3>
              {chapter.synopsis && <p className="av2-body">{chapter.synopsis}</p>}

              <p className="av2-label">
                {is_completed
                  ? was_perfect
                    ? 'Lu · sans faute'
                    : 'Lu'
                  : is_locked
                    ? 'Pas encore ouvert'
                    : isCurrent
                      ? 'Chapitre en cours'
                      : [
                          chapter.min_turns && chapter.max_turns
                            ? `${chapter.min_turns}–${chapter.max_turns} répliques`
                            : null,
                          chapter.narrative_goals?.length
                            ? `${chapter.narrative_goals.length} objectif${chapter.narrative_goals.length === 1 ? '' : 's'}`
                            : null,
                          `${chapter.completion_xp} XP`,
                        ]
                          .filter(Boolean)
                          .join(' · ')}
              </p>

              {chapter.branching_choices && chapter.branching_choices.length > 0 && !is_locked && (
                <p className="av2-label av2-label--story">
                  {chapter.branching_choices.length} chemin
                  {chapter.branching_choices.length === 1 ? '' : 's'} possible
                  {chapter.branching_choices.length === 1 ? '' : 's'}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

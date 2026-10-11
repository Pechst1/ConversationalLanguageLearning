/* Where the learner stands inside one chapter, and the one way to close it.
 *
 * The completion control never lies about why it is unavailable: when the
 * chapter's own criteria are not met yet, the label says what is missing
 * instead of simply going grey.
 */

import React from 'react';

import { Action, ProgressRule } from '@/components/atelier-v2/ui';
import { useChromeLanguage } from '@/lib/learner-language';

import { bibliothequeCopy, fill } from './bibliotheque-copy';

interface ChapterProgressCardProps {
  goalsCompleted: number;
  totalGoals: number;
  vocabularyUsed: number;
  xpEarned?: number;
  canComplete: boolean;
  onComplete: () => void;
  loading?: boolean;
}

export default function ChapterProgressCard({
  goalsCompleted,
  totalGoals,
  vocabularyUsed,
  xpEarned = 0,
  canComplete,
  onComplete,
  loading = false,
}: ChapterProgressCardProps) {
  const language = useChromeLanguage();
  const t = bibliothequeCopy(language);
  const needed = Math.ceil(totalGoals / 2);
  const isPerfect = totalGoals > 0 && goalsCompleted === totalGoals;

  return (
    <section className="av2-surface bib-block" aria-label={t.progress_heading}>
      <p className="av2-label">{t.progress_heading}</p>

      <ProgressRule
        value={goalsCompleted}
        max={totalGoals}
        label={t.goals_reached}
        caption={`${goalsCompleted} / ${totalGoals}`}
      />

      <div className="bib-stats">
        <div className="bib-stat">
          <span className="av2-label">{t.words_used}</span>
          <span className="av2-headline av2-headline--rule">{vocabularyUsed}</span>
        </div>
        {xpEarned > 0 && (
          <div className="bib-stat">
            <span className="av2-label">{t.xp_earned}</span>
            <span className="av2-headline av2-headline--rule">+{xpEarned}</span>
          </div>
        )}
      </div>

      {isPerfect && <p className="av2-label">{t.perfect_possible}</p>}

      {/* the one tactile 3D press of this column */}
      <Action
        tone="done"
        onClick={onComplete}
        disabled={!canComplete}
        pending={loading}
        pendingLabel={t.closing}
      >
        {canComplete ? t.finish_chapter : t.goals_missing}
      </Action>

      <p className="av2-label">
        {canComplete
          ? t.can_close
          : fill(needed === 1 ? t.reach_goals_one : t.reach_goals_many, { n: needed })}
      </p>
    </section>
  );
}

/* Where the learner stands inside one chapter, and the one way to close it.
 *
 * The completion control never lies about why it is unavailable: when the
 * chapter's own criteria are not met yet, the label says what is missing
 * instead of simply going grey.
 */

import React from 'react';

import { Action, ProgressRule } from '@/components/atelier-v2/ui';

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
  const isPerfect = totalGoals > 0 && goalsCompleted === totalGoals;

  return (
    <section className="av2-surface bib-block" aria-label="Progression dans le chapitre">
      <p className="av2-label">Progression dans le chapitre</p>

      <ProgressRule
        value={goalsCompleted}
        max={totalGoals}
        label="Objectifs atteints"
        caption={`${goalsCompleted} / ${totalGoals}`}
      />

      <div className="bib-stats">
        <div className="bib-stat">
          <span className="av2-label">Mots employés</span>
          <span className="av2-headline av2-headline--rule">{vocabularyUsed}</span>
        </div>
        {xpEarned > 0 && (
          <div className="bib-stat">
            <span className="av2-label">XP gagnés</span>
            <span className="av2-headline av2-headline--rule">+{xpEarned}</span>
          </div>
        )}
      </div>

      {isPerfect && <p className="av2-label">Un chapitre sans faute est encore possible.</p>}

      {/* the one tactile 3D press of this column */}
      <Action
        tone="done"
        onClick={onComplete}
        disabled={!canComplete}
        pending={loading}
        pendingLabel="Clôture…"
      >
        {canComplete ? 'Terminer le chapitre' : 'Encore quelques objectifs à atteindre'}
      </Action>

      <p className="av2-label">
        {canComplete
          ? 'Vous pouvez clore ce chapitre dès maintenant.'
          : `Atteignez au moins ${Math.ceil(totalGoals / 2)} objectif${Math.ceil(totalGoals / 2) === 1 ? '' : 's'} pour le clore.`}
      </p>
    </section>
  );
}

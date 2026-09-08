/* Where the learner stands in one Bibliothèque text, on the Claude design.
 *
 * Every figure below is a real server figure; nothing is fabricated to fill a
 * tile. The progress rule is the design's own blue rule — progress through a
 * text is information, not an action.
 */

import React from 'react';

import { ProgressRule } from '@/components/atelier-v2/ui';
import { UserStoryProgressBase } from '@/hooks/useStories';

interface StoryProgressOverviewProps {
  progress: UserStoryProgressBase;
  totalChapters: number;
}

function shortDate(value: string | null | undefined) {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toLocaleDateString();
}

export default function StoryProgressOverview({ progress, totalChapters }: StoryProgressOverviewProps) {
  const isCompleted = progress.status === 'completed';
  const chaptersCompleted =
    progress.total_chapters_completed ??
    (Array.isArray(progress.chapters_completed) ? progress.chapters_completed.length : 0);
  const minutesSpent = progress.total_time_spent_minutes ?? 0;
  const lastAccessedAt = progress.last_accessed_at ?? progress.last_played_at ?? progress.started_at;

  const stats = [
    { label: 'XP gagnés', value: String(progress.total_xp_earned) },
    { label: 'Chapitres lus', value: `${chaptersCompleted}/${totalChapters}` },
    { label: 'Sans faute', value: String(progress.perfect_chapters_count ?? 0) },
    { label: 'Temps de lecture', value: `${minutesSpent} min` },
  ];

  return (
    <section className="av2-surface bib-block" aria-label="Votre progression dans ce texte">
      <p className="av2-label">{isCompleted ? 'Texte terminé' : 'Votre progression'}</p>

      {!isCompleted && (
        <ProgressRule
          value={Math.round(progress.completion_percentage)}
          max={100}
          label="Progression dans ce texte"
          caption={`${Math.round(progress.completion_percentage)} %`}
        />
      )}

      <div className="bib-stats">
        {stats.map((stat) => (
          <div className="bib-stat" key={stat.label}>
            <span className="av2-label">{stat.label}</span>
            <span className="av2-headline av2-headline--rule">{stat.value}</span>
          </div>
        ))}
      </div>

      {(progress.vocabulary_mastered_count ?? 0) > 0 && (
        <p className="av2-body">
          {progress.vocabulary_mastered_count} mots acquis grâce à ce texte.
        </p>
      )}

      <p className="av2-label">
        {[
          shortDate(progress.started_at) ? `Commencé le ${shortDate(progress.started_at)}` : null,
          progress.completed_at && shortDate(progress.completed_at)
            ? `Terminé le ${shortDate(progress.completed_at)}`
            : null,
          shortDate(lastAccessedAt) ? `Dernière lecture le ${shortDate(lastAccessedAt)}` : null,
        ]
          .filter(Boolean)
          .join(' · ')}
      </p>
    </section>
  );
}

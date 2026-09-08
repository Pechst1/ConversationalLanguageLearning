/* The grammar this chapter leans on, on the Claude design.
 *
 * A collapsible paper surface: the concepts the server attached to the chapter,
 * each with its real SRS state and score, and one way through to Le Relevé for
 * the ones that are due. Nothing is shown when the chapter has no concepts.
 */

import { useState } from 'react';

import { Action, Chip, Skeleton } from '@/components/atelier-v2/ui';
import { ChapterGrammarConcept } from '@/types/grammar';

interface ChapterGrammarPreviewProps {
  concepts: ChapterGrammarConcept[];
  onReviewClick?: (conceptId: number) => void;
  loading?: boolean;
}

const STATE_LABEL: Record<string, string> = {
  neu: 'nouveau',
  'ausbaufähig': 'à consolider',
  in_arbeit: 'en cours',
  gefestigt: 'assuré',
  gemeistert: 'acquis',
};

export default function ChapterGrammarPreview({
  concepts,
  onReviewClick,
  loading = false,
}: ChapterGrammarPreviewProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  if (loading) {
    return (
      <section className="av2-surface bib-block" aria-busy="true" aria-label="Point de grammaire">
        <p className="av2-label">Point de grammaire</p>
        <Skeleton height={48} radius={16} />
        <Skeleton height={48} radius={16} />
      </section>
    );
  }

  if (concepts.length === 0) return null;

  const dueCount = concepts.filter((concept) => concept.is_due).length;
  const masteredCount = concepts.filter((concept) => concept.state === 'gemeistert').length;

  return (
    <section className="av2-surface bib-block" aria-label="Point de grammaire">
      <button
        type="button"
        className="bib-grammar__head"
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
      >
        <span className="bib-grammar__headings">
          <span className="av2-label">
            {concepts.length} point{concepts.length === 1 ? '' : 's'} dans ce chapitre
          </span>
          <span className="av2-headline av2-headline--rule">Point de grammaire</span>
        </span>
        <span className="bib-chips">
          {dueCount > 0 && <Chip tone="story">{dueCount} à revoir</Chip>}
          {masteredCount > 0 && <Chip tone="quiet">{masteredCount} acquis</Chip>}
        </span>
      </button>

      {isExpanded && (
        <>
          <ul className="bib-grammar__list">
            {concepts.map((concept) => (
              <li className="bib-grammar__item" key={concept.id}>
                <span className="bib-grammar__body">
                  <span className="av2-body">{concept.name}</span>
                  <span className="av2-label">
                    {[concept.level, STATE_LABEL[concept.state] || concept.state,
                      concept.reps > 0 ? `${concept.score.toFixed(1)}/10` : null]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </span>
                {onReviewClick && (
                  <Action tone="quiet" inline onClick={() => onReviewClick(concept.id)}>
                    {concept.state === 'neu' ? 'Apprendre' : concept.is_due ? 'Revoir' : 'Pratiquer'}
                  </Action>
                )}
              </li>
            ))}
          </ul>

          {dueCount > 0 && onReviewClick && (
            <Action
              tone="secondary"
              onClick={() => concepts.filter((concept) => concept.is_due).forEach((concept) => onReviewClick(concept.id))}
            >
              Revoir les {dueCount} point{dueCount === 1 ? '' : 's'} dus
            </Action>
          )}
        </>
      )}
    </section>
  );
}

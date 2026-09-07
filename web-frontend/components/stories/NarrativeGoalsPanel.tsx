/* The chapter's narrative goals, on the Claude design.
 *
 * A goal that is met carries the ink check and the word "atteint"; colour is
 * never the only carrier. The counter is the real goal count — with no goals
 * the panel does not render at all rather than showing an empty promise.
 */

import React from 'react';

import { CheckIcon, ProgressRule } from '@/components/atelier-v2/ui';
import { NarrativeGoal } from '@/hooks/useStories';

interface NarrativeGoalsPanelProps {
  goals: NarrativeGoal[];
  completedGoals: string[];
}

export default function NarrativeGoalsPanel({ goals, completedGoals }: NarrativeGoalsPanelProps) {
  if (goals.length === 0) return null;
  const done = goals.filter((goal) => completedGoals.includes(goal.goal_id)).length;

  return (
    <section className="av2-surface bib-block" aria-label="Objectifs du chapitre">
      <p className="av2-label">Objectifs du chapitre</p>

      <ul className="bib-goals">
        {goals.map((goal) => {
          const isCompleted = completedGoals.includes(goal.goal_id);
          return (
            <li className="bib-goal" key={goal.goal_id} data-state={isCompleted ? 'done' : 'open'}>
              <span className="bib-goal__mark" aria-hidden="true">
                {isCompleted ? <CheckIcon size={12} /> : null}
              </span>
              <span className="bib-goal__body">
                <span className="av2-body">{goal.description}</span>
                {isCompleted ? (
                  <span className="av2-label">Atteint</span>
                ) : goal.hint ? (
                  <span className="av2-label">Indice : {goal.hint}</span>
                ) : null}
              </span>
            </li>
          );
        })}
      </ul>

      <ProgressRule
        value={done}
        max={goals.length}
        label="Objectifs atteints"
        caption={`${done} / ${goals.length}`}
      />
    </section>
  );
}

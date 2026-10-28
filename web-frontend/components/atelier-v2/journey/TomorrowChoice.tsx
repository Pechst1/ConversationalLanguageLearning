/**
 * «Demain» (steering read 2026-10-24): under «La suite demain», the threads the
 * season's next day may follow, the plan's own first, as a row of chips. A tap
 * picks one; the server answers with the day's new tomorrow line («On va cuisiner
 * avec Lila.»), which the teaser above then says. Picking again replaces the pick.
 *
 * Presentation only: the choice is the server's (`recap.tomorrow`), the pick is the
 * caller's action. The picked chip is blue and carries a check, never colour alone.
 */

import React from 'react';

import { CheckIcon, Chip } from '@/components/atelier-v2/ui';
import { frenchSpacing } from '@/lib/french-typography';
import type { ControlLanguage } from '@/types/daily-journey';

import type { TomorrowChoiceView } from './journey-recap-model';
import { recapChrome } from './recap-copy';

export type TomorrowChoiceProps = {
  choice: TomorrowChoiceView | null;
  language: ControlLanguage;
  /** A request is in flight: the chips wait for its answer. */
  busy?: boolean;
  onPick?: (premiseId: string) => void;
};

export function TomorrowChoice({ choice, language, busy = false, onPick }: TomorrowChoiceProps) {
  if (!choice || !onPick) return null;
  const chrome = recapChrome(language);
  return (
    <div className="av2-tomorrow" role="group" aria-label={chrome.tomorrow_group} data-picked={choice.picked ?? ''}>
      <p className="av2-label" aria-hidden="true">
        {chrome.tomorrow_label}
      </p>
      <div className="av2-tomorrow__options">
        {choice.options.map((option) => (
          <Chip
            key={option.id}
            tone={option.picked ? 'story' : 'plain'}
            icon={option.picked ? <CheckIcon size={12} /> : undefined}
            aria-pressed={option.picked}
            disabled={busy}
            data-planned={option.planned ? '' : undefined}
            onClick={() => onPick(option.id)}
          >
            <span lang="fr">{frenchSpacing(option.labelFr)}</span>
          </Chip>
        ))}
      </div>
    </div>
  );
}

export default TomorrowChoice;

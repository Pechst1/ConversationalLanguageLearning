/**
 * WP-86 — «Qui a dit ça ?» : a line of today's scene, and the faces of the
 * people who could have said it. Tap the one who did.
 *
 * A pick, answered like a choice (`recallAnswerMode`), so the step's hashed
 * key (WP-76) colours it on the device. The face is the card: each option
 * names a cast member (`character_id`), drawn with `CastPortrait` — happy when
 * the pick is right, cross when it is wrong. Status is never colour alone: the
 * card also carries a glyph-free status word for screen readers.
 */

import React from 'react';

import type { ChoiceOption } from '@/components/atelier-v2/ui';
import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import type { PortraitMood } from '@/lib/onboarding-portraits';
import type { RecallOption } from '@/types/daily-journey';

import { whoSaidCards } from './practice-formats';

export type WhoSaidProps = {
  /** The raw options (they carry the character ids). */
  options: readonly RecallOption[];
  /** The same options with their graded state, as the choice list gets them. */
  states: readonly ChoiceOption[];
  selectedId: string | null;
  label: string;
  disabled?: boolean;
  onSelect: (id: string) => void;
  statusLabels: { selected: string; correct: string; wrong: string };
};

function moodFor(state: ChoiceOption['state']): PortraitMood {
  if (state === 'correct') return 'happy';
  if (state === 'wrong') return 'cross';
  return 'neutral';
}

export function WhoSaid({
  options,
  states,
  selectedId,
  label,
  disabled = false,
  onSelect,
  statusLabels,
}: WhoSaidProps) {
  const stateOf = new Map(states.map((option) => [option.id, option.state]));
  return (
    <ul className="av2-who-said" role="radiogroup" aria-label={label}>
      {whoSaidCards(options).map((card) => {
        const state = stateOf.get(card.id) ?? (card.id === selectedId ? 'selected' : 'idle');
        const shown = state === 'idle' && card.id === selectedId ? 'selected' : state;
        const status =
          shown === 'correct'
            ? statusLabels.correct
            : shown === 'wrong'
              ? statusLabels.wrong
              : shown === 'selected'
                ? statusLabels.selected
                : '';
        return (
          <li key={card.id}>
            <button
              type="button"
              role="radio"
              aria-checked={card.id === selectedId}
              className="av2-who-said__card"
              data-state={shown}
              disabled={disabled}
              onClick={() => onSelect(card.id)}
            >
              <CastPortrait characterId={card.characterId} name={card.name} mood={moodFor(shown)} size="md" />
              <span className="av2-who-said__name">{card.name}</span>
              {status && <span className="av2-sr">{status}</span>}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

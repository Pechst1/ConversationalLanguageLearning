/**
 * «La suite demain» in a few words: where the story goes tomorrow, with who says
 * it. One component for the two places a finished day shows it, Home's finished
 * card and the Done screen, so neither can drop it or word it differently
 * (#359). The words come from `tomorrowLine` (season-return-model.ts).
 */

import React from 'react';

import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import { frenchSpacing } from '@/lib/french-typography';
import type { ControlLanguage } from '@/types/daily-journey';

import { seasonReturnCopy } from './season-return-copy';
import type { TomorrowLine as TomorrowLineView } from './season-return-model';

export function TomorrowLine({ line, language }: { line: TomorrowLineView | null; language: ControlLanguage }) {
  if (!line) return null;
  const { teaser, hint } = line;
  return (
    <p className="av2-body journey-today-card__teaser" data-teaser={teaser.source} data-tomorrow="">
      <span className="av2-label">{seasonReturnCopy(language).teaser_label}</span>
      {teaser.character_id ? (
        <CastPortrait characterId={teaser.character_id} name={teaser.character_name ?? undefined} size="xs" alt="" />
      ) : null}
      <span className="av2-fr journey-today-card__hint" lang="fr">
        {frenchSpacing(hint)}
      </span>
    </p>
  );
}

export default TomorrowLine;

/**
 * «La suite demain» in a few words: where the story goes tomorrow, with who says
 * it. One component for the two places a finished day shows it, Home's finished
 * card and the Done screen, so neither can drop it or word it differently
 * (#359). The words come from `tomorrowLine` (season-return-model.ts).
 */

import React from 'react';

import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import { drawnFaceId } from '@/components/cast/CastFace';
import { useArtSet } from '@/lib/art-set';
import { castIdFor } from '@/lib/cast-faces';
import { frenchSpacing } from '@/lib/french-typography';
import type { ControlLanguage } from '@/types/daily-journey';

import { seasonReturnCopy } from './season-return-copy';
import type { TomorrowLine as TomorrowLineView } from './season-return-model';

export function TomorrowLine({ line, language }: { line: TomorrowLineView | null; language: ControlLanguage }) {
  const drawnSet = useArtSet() === 'drawn';
  if (!line) return null;
  const { teaser, hint } = line;
  // P8 (walk of 17 Nov): a speaker with no face (Maître Vasseur) drew a lone initial «M»
  // beside the hook. The face only when there is one to show.
  const id = teaser.character_id;
  const face =
    Boolean(id) && (castIdFor(id, teaser.character_name) !== null || (drawnSet && drawnFaceId(id, teaser.character_name) !== null));
  return (
    <p className="av2-body journey-today-card__teaser" data-teaser={teaser.source} data-tomorrow="">
      <span className="av2-label">{seasonReturnCopy(language).teaser_label}</span>
      {face && id ? (
        <CastPortrait characterId={id} name={teaser.character_name ?? undefined} size="xs" alt="" />
      ) : null}
      <span className="av2-fr journey-today-card__hint" lang="fr">
        {frenchSpacing(hint)}
      </span>
    </p>
  );
}

export default TomorrowLine;

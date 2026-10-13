/**
 * La troupe vivante · a cast member who acts where the app used to show a still face: the
 * character asking a drill, the rule's coach reacting to an answer, someone thinking while a
 * reply is read. One rule for all of them: they act after the learner answers, never while.
 *
 *   <CastActor characterId="margaux_barman" mood="surprised" gesture="oups" />
 *
 * Anyone without a jointed figure (and everyone in the painted art set) keeps the round
 * portrait, so a screen never loses a face.
 */
import React from 'react';

import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import { useArtSet } from '@/lib/art-set';
import { castIdFor } from '@/lib/cast-faces';
import type { FaceMood } from '@/lib/onboarding-portraits';
import type { RigCrop } from '../rig-kit';
import type { ExpressionId, GestureId } from './kit';
import { figureFor } from './registry';
import { VivantFigure } from './VivantFigure';

/** The app's moods as the troupe's faces. Nobody is ever cross at the learner (`expressionForVerdict`). */
export const MOOD_EXPRESSION: Record<FaceMood | 'cold', ExpressionId> = {
  neutral: 'neutre',
  happy: 'joie',
  cross: 'fache',
  moved: 'emu',
  surprised: 'surprise',
  cold: 'neutre',
};

/** What a graded answer makes the one who asked do: their own «bravo» or their own «oups». */
export function verdictGesture(verdict: string | null | undefined): GestureId | null {
  if (verdict === 'correct') return 'bravo';
  if (verdict === 'wrong') return 'oups';
  return null;
}

/** The jointed figure for a payload's character (any id or name the cast answers to), if any. */
export function actorFigure(characterId: string | null | undefined, name?: string | null) {
  return figureFor(castIdFor(characterId, name) ?? characterId ?? null);
}

export type CastActorProps = {
  characterId: string;
  name?: string;
  mood?: FaceMood | 'cold';
  /** played once when it changes; `loop` keeps it going (a wait) */
  gesture?: GestureId | null;
  loop?: boolean;
  /** the figure's width; the bust is a little taller than wide */
  width?: number;
  crop?: RigCrop;
  /** the round portrait's size for anyone who cannot act */
  fallback?: 'xs' | 'sm' | 'md' | 'lg';
};

export function CastActor({
  characterId,
  name,
  mood = 'neutral',
  gesture = null,
  loop = false,
  width = 80,
  crop = 'bust',
  fallback = 'sm',
}: CastActorProps) {
  const drawn = useArtSet() === 'drawn';
  const fig = drawn ? actorFigure(characterId, name) : null;
  if (!fig) {
    return <CastPortrait characterId={characterId} name={name} mood={mood === 'cold' ? 'neutral' : mood} size={fallback} ring />;
  }
  return (
    <span className="cast-actor" data-figure={fig.key} data-crop={crop} data-gesture={gesture || undefined}>
      {/* A new gesture or face is a new take: remounting restarts the CSS from its first frame. */}
      <VivantFigure
        key={`${gesture ?? 'rest'}-${mood}`}
        id={fig.key}
        expression={MOOD_EXPRESSION[mood] ?? 'neutre'}
        gesture={gesture}
        loop={loop}
        crop={crop}
        size={width}
        label=""
      />
    </span>
  );
}

export default CastActor;

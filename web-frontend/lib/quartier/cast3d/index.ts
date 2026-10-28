/**
 * Le Quartier · the cast in the round, for the troupe (`../cast.ts`): whoever has a body
 * (`people/`) stands up as a `ModelFigure`; anyone else stays on paper. The people the avatar
 * kit draws (the passers-by, a forged place's stallholders) stand up from their record.
 */
import type { AvatarConfig } from '@/lib/avatar';
import { castVariant } from '@/lib/cast-variants';

import type { FigureSpec, Seat } from '../cast';
import type { World } from '../materials';

import { avatarPerson } from './avatar';
import { ModelFigure } from './figure';
import { personFor } from './people';

export { GESTURES, ModelFigure } from './figure';
export { PEOPLE, personFor } from './people';

/**
 * Someone of the cast in the round (Camille as the learner chose them), sitting where `seats`
 * offer, or null for paper.
 */
export function roundFigure(world: World, spec: FigureSpec, seats: readonly Seat[] = []): ModelFigure | null {
  const person = personFor(spec.key);
  if (!person) return null;
  const chosen = castVariant(person.key);
  const variant = chosen && person.variants?.includes(chosen) ? chosen : undefined;
  return new ModelFigure(world, person, spec, { variant, seats });
}

/**
 * Someone the avatar kit draws, in the round: the same record as their card (`cast-art.tsx`),
 * so the same person. `seed` varies the body a little; `cell` is the face print's (the street's
 * people are printed smaller than the ones you talk to).
 */
export function avatarRound(world: World, cfg: AvatarConfig, spec: FigureSpec, seed: number, cell = 160): ModelFigure {
  return new ModelFigure(world, avatarPerson(cfg, { key: spec.key, height: spec.height, seed }), spec, { cell });
}

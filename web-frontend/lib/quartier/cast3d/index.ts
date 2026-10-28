/**
 * Le Quartier · the cast in the round, for the troupe (`../cast.ts`): whoever has a body
 * (`people/`) stands up as a `ModelFigure`; anyone else stays on paper.
 */
import { castVariant } from '@/lib/cast-variants';

import type { FigureSpec, Seat } from '../cast';
import type { World } from '../materials';

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

/**
 * La troupe vivante · who has a jointed figure. The ids and short names are the cast's own
 * (`rigFor` takes the same), so a cameo can ask for «romy» or «romy_tremblay» alike.
 */
import { rigFor } from '../cast-registry';
import type { FigureDef } from './kit';
import { romy } from './figures/romy';

export const FIGURES: readonly FigureDef[] = [romy];

export function figureFor(id: string | null | undefined): FigureDef | null {
  if (!id) return null;
  const key = String(id).trim().toLowerCase();
  const direct = FIGURES.find((f) => f.key === key);
  if (direct) return direct;
  const rig = rigFor(key);
  return rig ? FIGURES.find((f) => f.rig.id === rig.id) ?? null : null;
}

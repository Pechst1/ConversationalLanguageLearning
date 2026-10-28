/**
 * Le Quartier · who has a body in the round. Keys are the quarter's own (`margaux_barman`); the
 * short names the app uses for the same people work too.
 */
import type { Person } from '../model';
import { camille } from './camille';
import { gus } from './gus';
import { lila } from './lila';
import { marchand } from './marchand';
import { margaux } from './margaux';
import { marin } from './marin';
import { odile } from './odile';
import { romy } from './romy';

export const PEOPLE: readonly Person[] = [margaux, gus, lila, marin, romy, marchand, camille, odile];

const ALIASES: Record<string, string> = {
  margaux: 'margaux_barman',
  gus: 'augustin_de_roncourt',
  augustin: 'augustin_de_roncourt',
  lila: 'lila_bonnet',
  marin: 'marin_leveque',
  romy: 'romy_tremblay',
  marchand: 'landlord_marchand',
  camille: 'camille_marchand',
  odile: 'odile_ferrand',
};

export function personFor(key: string | null | undefined): Person | null {
  if (!key) return null;
  const k = String(key).trim().toLowerCase();
  const id = ALIASES[k] ?? k;
  return PEOPLE.find((p) => p.key === id) ?? null;
}

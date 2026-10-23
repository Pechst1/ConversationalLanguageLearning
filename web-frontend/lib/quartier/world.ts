/**
 * Le Quartier · the world: which places of Paris are in the game, where they are, and how far
 * along each one is.
 *
 * The quarter is not built all at once. The quai de Valmy and Le Mistral are drawn by hand; every
 * other place is forged when the story or the news asks for it (`scripts/forge`, run by the
 * `forge` skill): the address a Papier or an episode names is surveyed from open map data, turned
 * into a site, rendered, looked at, revised, and written here with its site file. A place the
 * forge is working on shows on the map under scaffolding (`en_chantier`); a place of the season the
 * story has not reached yet is `locked`.
 */
import type { Value, Words } from './memory';
import registry from './world/world.json';

export type WorldStatus = 'open' | 'en_chantier' | 'locked';

export interface WorldPlace {
  id: string;
  name: Words;
  lat: number;
  lon: number;
  status: WorldStatus;
  /** home: the hand-drawn quarter; season: a place of the story; news: a Papier asked for it */
  kind: 'home' | 'season' | 'news';
  /** one line on what is there, or why it is in the world */
  why: Words;
  source?: { kind: 'season' | 'papier'; id: string; title_fr?: string };
  /** the forged site (`world/sites/<id>.json`), once there is one */
  site?: string | null;
  /** how you get there from the quai */
  ride?: Words;
}

export interface World {
  version: number;
  updated: string;
  places: WorldPlace[];
}

export const WORLD = registry as unknown as World;

export function placeOf(id: string, world: World = WORLD): WorldPlace | null {
  return world.places.find((p) => p.id === id) ?? null;
}

/** The world as storylet state: `world.marche_aligre` is `en_chantier`, then `open`. */
export function worldState(world: World = WORLD): Record<string, Value> {
  const s: Record<string, Value> = {};
  world.places.forEach((p) => {
    s[`world.${p.id}`] = p.status;
  });
  return s;
}

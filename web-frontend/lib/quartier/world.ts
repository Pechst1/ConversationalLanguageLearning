/**
 * Le Quartier · the world: which places of Paris are in the game, where they are, and how far
 * along each one is.
 *
 * The quarter is not built all at once. The quai de Valmy and Le Mistral are drawn by hand; every
 * other place is forged when the story or the news asks for it (`scripts/forge`, run by the
 * `quartier-forge` skill): the address a Papier or an episode names is surveyed from open map
 * data, turned into a site, rendered, looked at, revised, and written here with its site file. A
 * place the forge is working on shows on the map under scaffolding (`en_chantier`); a place of the
 * season the story has not reached yet is `locked`.
 */
import type { Value, Words } from './memory';
import news from './world/news.json';
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

/** A place the Papier names with an exact position in Paris (`world/news.json`, written by `forge.py news`). */
export interface NewsPlace {
  id: string;
  name_fr: string;
  lat: number;
  lon: number;
  article: { id: string; title_fr: string; week: string | null; topic: string | null };
}

export const NEWS = (news as { places: NewsPlace[] }).places;

/**
 * Every place on the map: the registry's, then each place the news names that the registry
 * lacks yet. The news puts a pin on the map the day an article names a place; it stands under
 * scaffolding until the forge has built it and the registry opens it.
 */
export function mapPlaces(world: World = WORLD, papier: NewsPlace[] = NEWS): WorldPlace[] {
  const have = new Set(world.places.map((p) => p.id));
  const fresh = papier
    .filter((n) => !have.has(n.id))
    .map(
      (n): WorldPlace => ({
        id: n.id,
        name: { fr: n.name_fr, en: n.name_fr, de: n.name_fr },
        lat: n.lat,
        lon: n.lon,
        status: 'en_chantier',
        kind: 'news',
        why: {
          fr: `Le Papier : « ${n.article.title_fr} ».`,
          en: `The Papier: “${n.article.title_fr}”.`,
          de: `Das Papier: „${n.article.title_fr}“.`,
        },
        source: { kind: 'papier', id: n.article.id, title_fr: n.article.title_fr },
        site: null,
      }),
    );
  return world.places.concat(fresh);
}

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

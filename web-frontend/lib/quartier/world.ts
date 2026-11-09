/**
 * Le Quartier · the world: which places of Paris are in the game, where they are, and how far
 * along each one is.
 *
 * The quarter is not built all at once. The quai de Valmy and Le Mistral are drawn by hand; every
 * other place is forged when the story or the news asks for it (`scripts/forge`, run by the
 * `quartier-forge` skill): the address a Papier or an episode names is surveyed from open map
 * data, turned into a site, rendered, looked at, revised, and written here with its site file. A
 * place the forge is working on shows on the map under scaffolding (`en_chantier`); a place of the
 * season the story has not reached yet is `locked`. A room of the season (the stairwell, a flat) is
 * written from the canon instead (`world/rooms`, `room.ts`); it is inside another place (`in`), and
 * has no pin of its own.
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
  /**
   * home: the hand-drawn quarter; season: a place of the season's bible; story: a place the
   * learners' own pages named, built by the forge (a page names it first, then goes there);
   * news: a Papier asked for it
   */
  kind: 'home' | 'season' | 'story' | 'news';
  /** one line on what is there, or why it is in the world */
  why: Words;
  source?: { kind: 'season' | 'papier'; id: string; title_fr?: string };
  /** the forged site (`world/sites/<id>.json`), once there is one */
  site?: string | null;
  /** a room of the season (`world/rooms/<id>.json`), written from the canon */
  room?: string | null;
  /** the place a room is inside: it is reached from there, not from the map */
  in?: string;
  /** how you get there from the quai */
  ride?: Words;
  /**
   * The season's places (`app/services/season/world.py`) this place is the stage for: a page set
   * at one of them plays here. The one register between the story's places and the built world:
   * the forge writes it with the room or site it builds, and its queue reads it to know what the
   * season still lacks.
   */
  stages?: string[];
  /** places seen from here without going in (Odile's kitchen through the stairwell's open door) */
  sees?: string[];
}

export interface World {
  version: number;
  updated: string;
  places: WorldPlace[];
}

export const WORLD = registry as unknown as World;

/** The hand-drawn quarter: the quai de Valmy and Le Mistral, where the season starts. */
export const HOME_PLACE = 'quai_de_valmy';

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
  // a room is inside a place on the map, not a pin of its own
  const pinned = world.places.filter((p) => !p.in);
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
  return pinned.concat(fresh);
}

export function placeOf(id: string, world: World = WORLD): WorldPlace | null {
  return world.places.find((p) => p.id === id) ?? null;
}

/** The place a room of the season (`world/rooms`) or a forged site (`world/sites`) is built for. */
export function placeBuiltAs(built: { room?: string; site?: string }, world: World = WORLD): string | null {
  const p = world.places.find((q) => (built.room && q.room === built.room) || (built.site && q.site === built.site));
  return p?.id ?? built.room ?? built.site ?? null;
}

/** Built: the hand-drawn quarter, or a place the forge has written a room or a site for. */
export function isBuilt(p: WorldPlace): boolean {
  return p.kind === 'home' || Boolean(p.room) || Boolean(p.site);
}

/**
 * The built place a season location plays in, or null while nothing stages it yet. A room or a
 * site the forge wrote for exactly that location comes before the quarter it is inside.
 */
export function stageOf(location: string | null | undefined, world: World = WORLD): WorldPlace | null {
  if (!location) return null;
  const built = world.places.filter((p) => isBuilt(p) && (p.stages ?? []).includes(location));
  return built.find((p) => p.kind !== 'home') ?? built[0] ?? null;
}

/** Whether a page's moment at `location` plays in the room `room`: one it is the stage for, or one seen from it. */
export function playsIn(location: string | null | undefined, room: string, world: World = WORLD): boolean {
  if (!location) return false;
  const p = world.places.find((q) => q.room === room);
  return Boolean(p && ((p.stages ?? []).includes(location) || (p.sees ?? []).includes(location)));
}

/** The world as storylet state: `world.marche_aligre` is `en_chantier`, then `open`. */
export function worldState(world: World = WORLD): Record<string, Value> {
  const s: Record<string, Value> = {};
  world.places.forEach((p) => {
    s[`world.${p.id}`] = p.status;
  });
  return s;
}

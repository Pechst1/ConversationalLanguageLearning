/**
 * Le Quartier · where today's scene stands, kept on the device, so that leaving it mid-scene and
 * coming back plays on from there, as the page version resumes at the current exchange.
 *
 * Round 3 (walk 17 Nov, day 1 in 3D): a stray tap left the scene for Home; «Im Quartier spielen»
 * then started the scene again from its first panel. The engine keeps what was answered (the talk's
 * `turn_index`); the beat the quarter was playing and the replies it took are the quarter's own,
 * so they are kept here, by journey and page, with the `turn_index` they were kept at. A place kept
 * at another `turn_index` (answered elsewhere since, on another device or as pages) is not used:
 * the Feuilleton has where the day stands.
 *
 * Read and written behind try/catch: a refused storage plays the scene from the top, as before.
 */

export const SCENE_PLACE_KEY = 'quartier.scenePlace';

export interface ScenePlace {
  journey: string;
  page: string;
  /** the talk's `turn_index` when the place was kept */
  at: number;
  /** the movement the scene plays on from */
  from: string;
  /** the reply each question took */
  routes: Record<string, string>;
  /** the question the engine asks next, or `null` once the talk is over */
  asking: string | null;
}

type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

function store(given?: Store | null): Store | null {
  if (given !== undefined) return given;
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

const isPlace = (x: unknown): x is ScenePlace => {
  if (!x || typeof x !== 'object') return false;
  const p = x as Record<string, unknown>;
  return (
    typeof p.journey === 'string' &&
    typeof p.page === 'string' &&
    typeof p.at === 'number' &&
    typeof p.from === 'string' &&
    Boolean(p.routes) &&
    typeof p.routes === 'object' &&
    (p.asking === null || typeof p.asking === 'string')
  );
};

/** The place kept for this journey's page at this `turn_index`, or null. */
export function readScenePlace(journey: string, page: string, at: number, storage?: Store | null): ScenePlace | null {
  try {
    const raw = store(storage)?.getItem(SCENE_PLACE_KEY);
    if (!raw) return null;
    const p: unknown = JSON.parse(raw);
    return isPlace(p) && p.journey === journey && p.page === page && p.at === at ? p : null;
  } catch {
    return null;
  }
}

export function writeScenePlace(place: ScenePlace, storage?: Store | null): void {
  try {
    store(storage)?.setItem(SCENE_PLACE_KEY, JSON.stringify(place));
  } catch {
    /* storage refused: the scene starts from the top next time */
  }
}

/** The scene has played to its hook: nothing to pick up any more. */
export function clearScenePlace(journey: string, storage?: Store | null): void {
  try {
    const s = store(storage);
    const raw = s?.getItem(SCENE_PLACE_KEY);
    if (!raw) return;
    const p: unknown = JSON.parse(raw);
    if (!isPlace(p) || p.journey === journey) s?.removeItem(SCENE_PLACE_KEY);
  } catch {
    /* nothing kept, or nothing to clear */
  }
}

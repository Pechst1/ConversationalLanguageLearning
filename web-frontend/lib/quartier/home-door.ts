/**
 * P12 · Le Quartier beside the page (owner decision 9, proposal (b)): Home offers today's scene
 * both ways, on the days the quarter can stage it, and remembers on the device which way the
 * learner took last, so that one is the primary action next time.
 *
 * Pure but for the device's storage (read and written behind try/catch: a refused storage keeps
 * the page as the default).
 */
import type { JourneyPhase } from '@/components/atelier-v2/journey/journey-state';
import { QUARTIER_VISIBLE } from '@/lib/launch-flags';

import { todayOf } from './journey-story';
import { stageOf } from './world';

export const QUARTIER_HREF = '/quartier';

/** The learner's last way into the scene, on this device. */
export const SCENE_WAY_KEY = 'atelier.sceneWay';

export type SceneWay = 'page' | 'quartier';

/**
 * Whether the quarter can play today's scene: the scene is still ahead (or the warm-up before it)
 * and goes nowhere the quarter has not built (`todayOf`, the page's own check). Before the day is
 * opened only the scenario is known: its place must be one the quarter has built.
 */
export function quartierCanStage(phase: JourneyPhase, visible: boolean = QUARTIER_VISIBLE): boolean {
  if (!visible) return false;
  if (phase.kind === 'offer') {
    const location = phase.scenario?.location_id ?? null;
    return Boolean(phase.scenario && location && stageOf(location));
  }
  if (phase.kind === 'session' || phase.kind === 'paused') {
    const kind = todayOf(phase.journey).kind;
    return kind === 'play' || kind === 'before';
  }
  return false;
}

type Store = Pick<Storage, 'getItem' | 'setItem'>;

function store(given?: Store | null): Store | null {
  if (given !== undefined) return given;
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

/** The way the learner took last; the page until they have taken the quarter. */
export function readSceneWay(storage?: Store | null): SceneWay {
  try {
    return store(storage)?.getItem(SCENE_WAY_KEY) === 'quartier' ? 'quartier' : 'page';
  } catch {
    return 'page';
  }
}

export function writeSceneWay(way: SceneWay, storage?: Store | null): void {
  try {
    store(storage)?.setItem(SCENE_WAY_KEY, way);
  } catch {
    /* storage refused: the page stays the default */
  }
}

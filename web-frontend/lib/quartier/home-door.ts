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

import { awayOf, todayOf } from './journey-story';
import type { StoryPage } from './story';
import { stageOf } from './world';

export const QUARTIER_HREF = '/quartier';

/** The learner's last way into the scene, on this device. */
export const SCENE_WAY_KEY = 'atelier.sceneWay';

export type SceneWay = 'page' | 'quartier';

/** Today's planned page as Home's headline places it before Start (`headline.stage`). */
export interface PlannedStage {
  key: string;
  location_id?: string | null;
  locations?: Array<string | null> | null;
}

/** The planned page as the quarter's own check reads a page: its key and each movement's place. */
export function plannedPage(stage: PlannedStage): StoryPage {
  const [segment = '', day = ''] = stage.key.split('.');
  return {
    season_id: '',
    segment,
    day,
    key: stage.key,
    title_fr: '',
    location_id: stage.location_id ?? null,
    movements: (stage.locations ?? []).map((location_id, i) => ({ kind: 'panel', id: `${stage.key}.${i}`, location_id, lines: [] })),
    storylets: [],
  };
}

/**
 * Whether the quarter can play today's scene: the scene is still ahead (or the warm-up before it)
 * and goes nowhere the quarter has not built (`todayOf`, the page's own check).
 *
 * Before the day is opened (round 2, walk 17 Nov): with the story engine on, the offer is the
 * engine's invitation («Votre prochain chapitre», `location_id: ""`), so its place says nothing;
 * the headline carries where the planned page plays (`headline.stage`, a tentpole's), read by the
 * same check as the quarter's (`awayOf`). A day whose page is not known before Start (a gap day,
 * written at night) is offered as a page only: the quarter's chip stays for roaming.
 */
export function quartierCanStage(phase: JourneyPhase, visible: boolean = QUARTIER_VISIBLE): boolean {
  if (!visible) return false;
  if (phase.kind === 'offer') {
    if (!phase.scenario) return false;
    const planned: PlannedStage | null = phase.envelope?.headline?.stage ?? null;
    if (planned?.key) {
      const page = plannedPage(planned);
      return Boolean(stageOf(page.location_id ?? planned.locations?.find(Boolean) ?? null)) && !awayOf(page);
    }
    const location = phase.scenario.location_id || null;
    return Boolean(location && stageOf(location));
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

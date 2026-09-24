/**
 * WP-D1 / WP-D3 — the mark is the day's plan.
 *
 * The logo's four shapes are the day's four parts, and they fill in as the
 * learner goes. This file is the one step → shape mapping both the mark
 * (Home, the session head) and the step tokens (`StepProgress`) read:
 *
 *   scene       blue circle     («Scène»)
 *   recall      yellow square   («Mots»)
 *   respond     red triangle    («Réponse»)
 *   resolution  ink square      («Bouclé» — ink is done, the day's close)
 *
 * WP-L4: the Règle (`rule`) belongs to the Scène movement — a blue circle, and
 * counted with the scene — so the mark keeps four shapes on an introduction day.
 *
 * WP-S4: La Forge folded into a Soutenu/Intensif day (`forge`) is retrieval
 * work — the yellow square (Rappel) counts it, so the square is done only when
 * the forge block is too, and the mark keeps its four shapes.
 *
 * Pure: no React, no styling, no transport. It sits beside `journey-state.ts`
 * rather than inside it so the renderers and the node tests share it without
 * touching the controller's state machine.
 */

import type { ControlLanguage, JourneySnapshot, PublicStep, StepKind } from '@/types/daily-journey';

import type { ShapeKind } from '@/components/atelier-v2/ui/Shapes';

export type DayMarkGroup = Exclude<StepKind, 'rule' | 'forge'>;

/**
 * `done` — every step of the group is resolved; `active` — the learner is in
 * it; `todo` — still ahead; `absent` — today's shape deals none (a «jour
 * court» has no recall). `absent` draws like `todo`, a ghost, never an outline.
 */
export type DayMarkGroupState = 'done' | 'active' | 'todo' | 'absent';

export type DayMarkState = {
  groups: Record<DayMarkGroup, DayMarkGroupState>;
  /** Groups done. */
  done: number;
  /** Groups today's plan actually has (3 on a «jour court», else 4). */
  total: number;
  /** «Aujourd'hui : 2 sur 4 — scène vue, mots revus, réponse en cours, fin à venir» */
  label: string;
};

/** The order the mark and the label row read in. */
export const DAY_MARK_GROUPS: readonly DayMarkGroup[] = ['scene', 'recall', 'respond', 'resolution'];

/** The step → shape mapping (WP-D1, reused by WP-D3's tokens). */
export const STEP_SHAPE: Record<StepKind, ShapeKind> = {
  scene: 'story',
  recall: 'reward',
  respond: 'action',
  resolution: 'done',
  rule: 'story',
  forge: 'reward',
};

/** The mark's group a step counts in: the Règle is part of the Scène, the Forge of the Rappel. */
export function dayMarkGroupOf(kind: StepKind): DayMarkGroup {
  if (kind === 'rule') return 'scene';
  if (kind === 'forge') return 'recall';
  return kind;
}

/** The word paired with each shape in Home's label row (French, for B1+). */
export const DAY_MARK_WORD: Record<DayMarkGroup, string> = {
  scene: 'Scène',
  recall: 'Mots',
  respond: 'Réponse',
  resolution: 'Bouclé',
};

/**
 * WP-82: the row's words and the mark's accessible name are status, so they
 * follow the screen's chrome language (the learner's up to A2).
 */
const WORDS: Record<ControlLanguage, Record<DayMarkGroup, string>> = {
  en: { scene: 'Scene', recall: 'Words', respond: 'Reply', resolution: 'Done' },
  de: { scene: 'Szene', recall: 'Wörter', respond: 'Antwort', resolution: 'Fertig' },
  fr: DAY_MARK_WORD,
};

export function dayMarkWords(language: ControlLanguage = 'fr'): Record<DayMarkGroup, string> {
  return WORDS[language] ?? WORDS.en;
}

type Phrases = Record<DayMarkGroup, Record<'done' | 'active' | 'todo', string>>;

const STATE_PHRASES: Record<ControlLanguage, { today: string; of: string; phrases: Phrases }> = {
  fr: {
    today: 'Aujourd’hui',
    of: 'sur',
    phrases: {
      scene: { done: 'scène vue', active: 'scène en cours', todo: 'scène à venir' },
      recall: { done: 'mots revus', active: 'mots en cours', todo: 'mots à venir' },
      respond: { done: 'réponse donnée', active: 'réponse en cours', todo: 'réponse à venir' },
      resolution: { done: 'journée bouclée', active: 'fin en cours', todo: 'fin à venir' },
    },
  },
  en: {
    today: 'Today',
    of: 'of',
    phrases: {
      scene: { done: 'scene read', active: 'scene in progress', todo: 'scene to come' },
      recall: { done: 'words reviewed', active: 'words in progress', todo: 'words to come' },
      respond: { done: 'reply given', active: 'reply in progress', todo: 'reply to come' },
      resolution: { done: 'day done', active: 'ending in progress', todo: 'ending to come' },
    },
  },
  de: {
    today: 'Heute',
    of: 'von',
    phrases: {
      scene: { done: 'Szene gelesen', active: 'Szene läuft', todo: 'Szene kommt noch' },
      recall: { done: 'Wörter wiederholt', active: 'Wörter laufen', todo: 'Wörter kommen noch' },
      respond: { done: 'Antwort gegeben', active: 'Antwort läuft', todo: 'Antwort kommt noch' },
      resolution: { done: 'Tag geschafft', active: 'Ende läuft', todo: 'Ende kommt noch' },
    },
  },
};

const RESOLVED = new Set(['completed', 'skipped']);

function groupState(
  steps: PublicStep[],
  currentStepId: string | null,
  endedEarly: boolean,
): DayMarkGroupState {
  if (steps.length === 0) return 'absent';
  const resolved = steps.every((step) => RESOLVED.has(step.status));
  // An early end marks every unreached step `skipped`. That is not the
  // learner having done it: a group nothing in which was completed stays a
  // ghost, so a day stopped after the words never reads «Bouclé».
  if (resolved && (!endedEarly || steps.some((step) => step.status === 'completed'))) {
    return 'done';
  }
  if (steps.some((step) => step.id === currentStepId || step.status === 'active')) {
    return 'active';
  }
  return 'todo';
}

/** «Aujourd'hui : 2 sur 4 — …». Never colour alone: every state is a word. */
export function dayMarkLabel(
  groups: Record<DayMarkGroup, DayMarkGroupState>,
  language: ControlLanguage = 'fr',
): string {
  const table = STATE_PHRASES[language] ?? STATE_PHRASES.en;
  const present = DAY_MARK_GROUPS.filter((group) => groups[group] !== 'absent');
  const done = present.filter((group) => groups[group] === 'done').length;
  const parts = present.map((group) => table.phrases[group][groups[group] as 'done' | 'active' | 'todo']);
  // An accessible name, never wrapped: the ordinary French space is kept.
  const colon = language === 'fr' ? ' :' : ':';
  return `${table.today}${colon} ${done} ${table.of} ${present.length} — ${parts.join(', ')}`;
}

/**
 * Each group's state for today's journey.
 *
 * No journey yet (the day is offered, not started) is four parts still ahead:
 * the shape is unknown, so nothing is `absent`. A day shape with no recall
 * steps («jour court») marks the recall group `absent`.
 */
export function dayMarkState(
  journey: JourneySnapshot | null | undefined,
  language: ControlLanguage = 'fr',
): DayMarkState {
  const groups = {} as Record<DayMarkGroup, DayMarkGroupState>;
  if (!journey || journey.steps.length === 0) {
    for (const group of DAY_MARK_GROUPS) groups[group] = 'todo';
  } else {
    const endedEarly = journey.status === 'ended_early';
    for (const group of DAY_MARK_GROUPS) {
      groups[group] = groupState(
        journey.steps.filter((step) => dayMarkGroupOf(step.kind) === group),
        journey.current_step_id,
        endedEarly,
      );
    }
  }
  const present = DAY_MARK_GROUPS.filter((group) => groups[group] !== 'absent');
  return {
    groups,
    done: present.filter((group) => groups[group] === 'done').length,
    total: present.length,
    label: dayMarkLabel(groups, language),
  };
}

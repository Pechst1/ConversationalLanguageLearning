/**
 * GENTLE-ONBOARDING (owner, 2026-10-12) — a new learner is walked in, not dropped in.
 *
 * Three pieces, all pure (no React) so the node tests read them directly:
 *
 *  1. **The walkthrough** — four cards before the very first scene: what the
 *     app is, what the four shapes mean, how to read the progress row at the
 *     top, and what the first day holds. Once per device.
 *  2. **The first day's route** — the story first, then La Forge (grammar),
 *     then the words (Lexique). The server keeps the first day to the story
 *     (`_plan_and_bind`, `opening`), and the two others follow it here, in
 *     that order, with what is done ticked off.
 *  3. **The stickers** — the first time each kind of step appears, one small
 *     card says what this step is and what to do. Once per kind, per device.
 *
 * Device memory is `localStorage`, like the cast intro and the preludes: a
 * learner on a second device sees the explanations once more, which is
 * harmless, and nothing here can block a step when storage is unreachable.
 */

import type { ControlLanguage } from '@/types/daily-journey';
import type { ShapeKind } from '@/components/atelier-v2/ui/Shapes';

// ---------------------------------------------------------------------------
// Stickers — one per kind of step
// ---------------------------------------------------------------------------

export type FirstStepKey =
  | 'scene'
  | 'rule'
  | 'recall'
  | 'respond'
  | 'resolution'
  | 'read'
  | 'desk'
  | 'forge'
  | 'words';

export const FIRST_STEP_SHAPE: Record<FirstStepKey, ShapeKind> = {
  scene: 'story',
  rule: 'story',
  read: 'story',
  recall: 'reward',
  desk: 'reward',
  forge: 'reward',
  words: 'reward',
  respond: 'action',
  resolution: 'done',
};

type StickerCopy = { title: string; body: string };

type FirstStepsCopy = {
  kicker: string;
  got_it: string;
  stickers: Record<FirstStepKey, StickerCopy>;
  walkthrough: {
    aria: string;
    next: string;
    start: string;
    skip: string;
    welcome_title: string;
    welcome_body: string;
    shapes_title: string;
    shapes_body: string;
    shapes: Record<'story' | 'reward' | 'action' | 'done', string>;
    progress_title: string;
    progress_body: string;
    progress_points: string[];
    day_title: string;
    day_body: string;
  };
  route: {
    title: string;
    story: string;
    forge: string;
    words: string;
    forge_hint: string;
    words_hint: string;
    next_forge: string;
    next_words: string;
    all_done: string;
  };
};

const COPY: Record<ControlLanguage, FirstStepsCopy> = {
  de: {
    kicker: 'Zum ersten Mal',
    got_it: 'Verstanden',
    stickers: {
      scene: {
        title: 'Die Szene',
        body: 'Lesen und hören. Übersetzung per Tipp.',
      },
      rule: {
        title: 'Die Regel',
        body: 'Die Regel des Tages. Gleich danach kommt sie im Einsatz.',
      },
      recall: {
        title: 'Die Wörter',
        body: 'Kurze Wortübungen. Bei Fehlern siehst du die Lösung.',
      },
      respond: {
        title: 'Deine Antwort',
        body: 'Antworte auf Französisch, schriftlich oder laut. Die Geschichte reagiert.',
      },
      resolution: {
        title: 'Das Ende der Folge',
        body: 'Hier endet die Szene. Danach kommen deine Wörter und die Grammatik.',
      },
      read: {
        title: 'Eine Seite zum Lesen',
        body: 'Eine Extra-Seite zum Lesen. Freiwillig.',
      },
      desk: {
        title: 'Der Schreibtisch',
        body: 'Eine kurze Extra-Übung. Freiwillig.',
      },
      forge: {
        title: 'La Forge',
        body: 'Eine Regel, Schritt für Schritt. Etwa fünf Minuten.',
      },
      words: {
        title: 'Der Lexique',
        body: 'Tippen zum Umdrehen. Sag, ob du es wusstest.',
      },
    },
    walkthrough: {
      aria: 'Kurze Einführung',
      next: 'Weiter',
      start: 'Los geht’s',
      skip: 'Überspringen',
      welcome_title: 'Willkommen im Atelier',
      welcome_body: 'Jeden Tag eine Folge in Paris. Du antwortest auf Französisch, und die Geschichte ändert sich.',
      shapes_title: 'Die vier Formen',
      shapes_body: 'Jeder Teil des Tages hat eine Form.',
      shapes: {
        story: 'Blauer Kreis: die Szene. Lesen und hören.',
        reward: 'Gelbes Quadrat: die Wörter. Kurze Übungen.',
        action: 'Rotes Dreieck: deine Antwort. Du schreibst oder sprichst.',
        done: 'Schwarzes Quadrat: das Ende. Der Tag ist geschafft.',
      },
      progress_title: 'Wo du gerade bist',
      progress_body: 'Oben auf jeder Seite siehst du, wo du bist.',
      progress_points: [
        'Eine Form pro Schritt. Augen zeigen, wo du bist.',
        'Fertig ist farbig, Kommendes grau.',
        'Rechts oben: dein Tag füllt sich.',
      ],
      day_title: 'Dein erster Tag',
      day_body: 'Szene, dann deine Wörter, dann Grammatik. Gelbe Zettel erklären Neues.',
    },
    route: {
      title: 'Dein erster Tag',
      story: 'Die Geschichte',
      forge: 'La Forge',
      words: 'Deine Wörter',
      forge_hint: 'Grammatik, etwa 5 Min.',
      words_hint: 'Wortkarten aus der Szene',
      next_forge: 'Weiter: La Forge',
      next_words: 'Weiter: deine Wörter',
      all_done: 'Alles geschafft. Morgen geht die Geschichte weiter.',
    },
  },
  en: {
    kicker: 'First time',
    got_it: 'Got it',
    stickers: {
      scene: {
        title: 'The scene',
        body: 'Read and listen. Translation is one tap away.',
      },
      rule: {
        title: 'The rule',
        body: 'One grammar rule for today. It comes up next.',
      },
      recall: {
        title: 'The words',
        body: 'Quick word drills. A miss shows the answer.',
      },
      respond: {
        title: 'Your reply',
        body: 'Answer in French, typed or spoken. The story reacts.',
      },
      resolution: {
        title: 'The end of the episode',
        body: 'The scene ends here. Next come your words and the grammar.',
      },
      read: {
        title: 'A page to read',
        body: 'An extra page to read. Optional.',
      },
      desk: {
        title: 'The desk',
        body: 'A short extra drill. Optional.',
      },
      forge: {
        title: 'La Forge',
        body: 'One rule, step by step. About five minutes.',
      },
      words: {
        title: 'The Lexique',
        body: 'Tap to turn. Say if you knew it.',
      },
    },
    walkthrough: {
      aria: 'Short introduction',
      next: 'Next',
      start: 'Let’s go',
      skip: 'Skip',
      welcome_title: 'Welcome to the Atelier',
      welcome_body: 'One episode a day, set in Paris. You answer in French, and the story changes.',
      shapes_title: 'The four shapes',
      shapes_body: 'Each part of the day has a shape.',
      shapes: {
        story: 'Blue circle: the scene. Read and listen.',
        reward: 'Yellow square: the words. Quick exercises.',
        action: 'Red triangle: your reply. You write or speak.',
        done: 'Black square: the ending. The day is done.',
      },
      progress_title: 'Where you are',
      progress_body: 'The top of each page shows where you are.',
      progress_points: [
        'One shape per step. Eyes mark where you are.',
        'Done is colour, ahead is grey.',
        'Top right: your day fills in.',
      ],
      day_title: 'Your first day',
      day_body: 'Scene, then your words, then grammar. Yellow notes explain new things.',
    },
    route: {
      title: 'Your first day',
      story: 'The story',
      forge: 'La Forge',
      words: 'Your words',
      forge_hint: 'Grammar, about 5 min',
      words_hint: 'Word cards from the scene',
      next_forge: 'Next: La Forge',
      next_words: 'Next: your words',
      all_done: 'All done. The story goes on tomorrow.',
    },
  },
  fr: {
    kicker: 'Première fois',
    got_it: 'Compris',
    stickers: {
      scene: {
        title: 'La scène',
        body: 'Lis et écoute. La traduction est à un geste.',
      },
      rule: {
        title: 'La règle',
        body: 'La règle du jour. Elle revient tout de suite.',
      },
      recall: {
        title: 'Les mots',
        body: 'De courts exercices. Une erreur montre la réponse.',
      },
      respond: {
        title: 'Ta réponse',
        body: 'Réponds en français, à l’écrit ou à l’oral. L’histoire réagit.',
      },
      resolution: {
        title: 'La fin de l’épisode',
        body: 'La scène se termine ici. Ensuite viennent tes mots et la grammaire.',
      },
      read: {
        title: 'Une page à lire',
        body: 'Une page en plus, à lire. Facultatif.',
      },
      desk: {
        title: 'Le bureau',
        body: 'Un court exercice en plus. Facultatif.',
      },
      forge: {
        title: 'La Forge',
        body: 'Une règle, pas à pas. Cinq minutes environ.',
      },
      words: {
        title: 'Le Lexique',
        body: 'Touche pour retourner. Dis si tu savais.',
      },
    },
    walkthrough: {
      aria: 'Courte présentation',
      next: 'Suivant',
      start: 'C’est parti',
      skip: 'Passer',
      welcome_title: 'Bienvenue à l’Atelier',
      welcome_body: 'Un épisode par jour, à Paris. Tu réponds en français, et l’histoire change.',
      shapes_title: 'Les quatre formes',
      shapes_body: 'Chaque partie de la journée a sa forme.',
      shapes: {
        story: 'Cercle bleu : la scène. Lire et écouter.',
        reward: 'Carré jaune : les mots. De courts exercices.',
        action: 'Triangle rouge : ta réponse, écrite ou dite.',
        done: 'Carré noir : la fin. La journée est bouclée.',
      },
      progress_title: 'Où tu en es',
      progress_body: 'En haut de chaque page, tu vois où tu en es.',
      progress_points: [
        'Une forme par étape. Les yeux marquent l’étape en cours.',
        'Fait en couleur, à venir en gris.',
        'En haut à droite : ta journée se remplit.',
      ],
      day_title: 'Ton premier jour',
      day_body: 'La scène, puis tes mots, puis la grammaire. Les notes jaunes expliquent le nouveau.',
    },
    route: {
      title: 'Ton premier jour',
      story: 'L’histoire',
      forge: 'La Forge',
      words: 'Tes mots',
      forge_hint: 'Grammaire, 5 min environ',
      words_hint: 'Les cartes de la scène',
      next_forge: 'Ensuite : La Forge',
      next_words: 'Ensuite : tes mots',
      all_done: 'Tout est fait. L’histoire continue demain.',
    },
  },
};

export function firstStepsCopy(language: ControlLanguage | string | null | undefined): FirstStepsCopy {
  return COPY[(language as ControlLanguage) || 'en'] ?? COPY.en;
}

// ---------------------------------------------------------------------------
// Device memory
// ---------------------------------------------------------------------------

export type KeyValueStore = Pick<Storage, 'getItem' | 'setItem'>;

const STICKER_PREFIX = 'atelier.firstStep.';
const WALKTHROUGH_KEY = 'atelier.walkthroughSeen';
const ROUTE_KEY = 'atelier.firstDayRoute';

/** A store kept in memory for this page's life. */
export function memoryStore(): KeyValueStore {
  const values = new Map<string, string>();
  return {
    getItem: (key) => (values.has(key) ? (values.get(key) as string) : null),
    setItem: (key, value) => {
      values.set(key, String(value));
    },
  };
}

let fallbackStore: KeyValueStore | null = null;

/** This device's memory; when localStorage is missing or refuses writes (a private
 * window, a full quota), an in-memory store for this page's life, so the first
 * day's route still carries the learner from La Forge to the words. */
export function deviceStore(): KeyValueStore | null {
  if (typeof window === 'undefined') return null;
  try {
    const storage = window.localStorage;
    const probe = `${ROUTE_KEY}.probe`;
    storage.setItem(probe, '1');
    storage.removeItem(probe);
    return storage;
  } catch {
    fallbackStore = fallbackStore ?? memoryStore();
    return fallbackStore;
  }
}

function read(store: KeyValueStore | null, key: string): string | null {
  try {
    return store ? store.getItem(key) : null;
  } catch {
    return null;
  }
}

function write(store: KeyValueStore | null, key: string, value: string): void {
  try {
    store?.setItem(key, value);
  } catch {
    // Not remembered: the note may show once more. Harmless.
  }
}

/** Has this kind of step been explained on this device? Unreachable storage reads as seen: never nag. */
export function stickerSeen(store: KeyValueStore | null, key: FirstStepKey): boolean {
  if (!store) return true;
  return read(store, STICKER_PREFIX + key) === '1';
}

export function rememberSticker(store: KeyValueStore | null, key: FirstStepKey): void {
  write(store, STICKER_PREFIX + key, '1');
}

export function walkthroughSeen(store: KeyValueStore | null): boolean {
  if (!store) return true;
  return read(store, WALKTHROUGH_KEY) === '1';
}

export function rememberWalkthrough(store: KeyValueStore | null): void {
  write(store, WALKTHROUGH_KEY, '1');
}

/** The sticker a step kind shows, or `null` for a kind with nothing to explain. */
export function stickerFor(kind: string | null | undefined): FirstStepKey | null {
  switch (kind) {
    case 'scene':
    case 'rule':
    case 'recall':
    case 'respond':
    case 'resolution':
    case 'read':
    case 'desk':
    case 'forge':
      return kind;
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// The first day's route: story → words → La Forge
// ---------------------------------------------------------------------------

export type RouteStage = 'story' | 'forge' | 'words';
/**
 * #152: the order is the server's day plan (scene, words, grammar), written here
 * in the route's own names (story, words, forge). `day-plan.test.js` holds the
 * two to each other.
 */
export const ROUTE_STAGES: readonly RouteStage[] = ['story', 'words', 'forge'];

type RouteMemory = { date: string; done: RouteStage[] };

function readRoute(store: KeyValueStore | null): RouteMemory | null {
  const raw = read(store, ROUTE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed.date !== 'string' || !Array.isArray(parsed.done)) return null;
    return {
      date: parsed.date,
      done: parsed.done.filter((stage: unknown): stage is RouteStage =>
        ROUTE_STAGES.includes(stage as RouteStage),
      ),
    };
  } catch {
    return null;
  }
}

/**
 * The learner's first day is on (`localDate`, the journey's own date). Called
 * from the first day's journey; a later day never starts a route, and the one
 * stored for an earlier date is replaced, so the route is that one day only.
 */
export function beginFirstDay(store: KeyValueStore | null, localDate: string): void {
  const current = readRoute(store);
  if (current && current.date === localDate) return;
  write(store, ROUTE_KEY, JSON.stringify({ date: localDate, done: [] }));
}

/** Is today (`localDate`) the learner's first day, as this device remembers it? */
export function onFirstDay(store: KeyValueStore | null, localDate: string | null | undefined): boolean {
  if (!localDate) return false;
  return readRoute(store)?.date === localDate;
}

/** Tick a stage off — only on the first day itself; any other day is a no-op. */
export function markRouteStage(
  store: KeyValueStore | null,
  stage: RouteStage,
  localDate: string | null | undefined,
): void {
  const current = readRoute(store);
  if (!current || !localDate || current.date !== localDate) return;
  if (current.done.includes(stage)) return;
  write(store, ROUTE_KEY, JSON.stringify({ ...current, done: [...current.done, stage] }));
}

export function routeDone(store: KeyValueStore | null): RouteStage[] {
  return readRoute(store)?.done ?? [];
}

/** The stage the learner goes to next, in the owner's order; `null` once all three are done. */
export function nextRouteStage(done: readonly RouteStage[]): RouteStage | null {
  return ROUTE_STAGES.find((stage) => !done.includes(stage)) ?? null;
}

/** Today's date as the journey writes it (`YYYY-MM-DD`, the device's local day). */
export function localDateToday(now: Date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

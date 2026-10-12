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
        body: 'Hier liest und hörst du, was in der Geschichte passiert. Eine Übersetzung kannst du dir jederzeit anzeigen lassen. Der blaue Kreis oben steht für die Szene.',
      },
      rule: {
        title: 'Die Regel',
        body: 'Eine kleine Grammatikregel, genommen aus der Szene, die du gerade gelesen hast. Lies sie einmal, gleich danach kommt sie in der Geschichte vor.',
      },
      recall: {
        title: 'Die Wörter',
        body: 'Kurze Übungen mit Wörtern aus der Szene. Falsch ist hier nicht schlimm: du siehst sofort die richtige Lösung. Das gelbe Quadrat steht für die Wörter.',
      },
      respond: {
        title: 'Deine Antwort',
        body: 'Jetzt bist du dran: Antworte der Person auf Französisch, mit deinen eigenen Worten. Schreiben oder sprechen, beides geht. Die Geschichte reagiert auf das, was du sagst. Das rote Dreieck steht für deine Antwort.',
      },
      resolution: {
        title: 'Das Ende des Tages',
        body: 'So geht die Szene heute aus. Danach ist der Tag geschafft und das schwarze Quadrat oben füllt sich.',
      },
      read: {
        title: 'Eine Seite zum Lesen',
        body: 'Eine zusätzliche Seite, nur zum Lesen. Du kannst sie auch überspringen.',
      },
      desk: {
        title: 'Der Schreibtisch',
        body: 'Eine kurze Extra-Übung nach der Szene, ganz freiwillig.',
      },
      forge: {
        title: 'La Forge',
        body: 'Hier übst du eine Grammatikregel gezielt, Schritt für Schritt: erst erkennen, dann selbst bilden. Etwa fünf Minuten, und die Regel kommt danach wieder in deiner Geschichte vor.',
      },
      words: {
        title: 'Der Lexique',
        body: 'Deine Wortkarten. Tippe auf die Karte, um sie umzudrehen, dann sag ehrlich, ob du das Wort wusstest. Was du nicht weißt, kommt bald wieder, was du weißt, später.',
      },
    },
    walkthrough: {
      aria: 'Kurze Einführung',
      next: 'Weiter',
      start: 'Los geht’s',
      skip: 'Überspringen',
      welcome_title: 'Willkommen im Atelier',
      welcome_body: 'Jeden Tag spielst du eine Folge einer Geschichte in Paris. Du liest, was passiert, und antwortest den Figuren auf Französisch. Was du schreibst, verändert die Geschichte.',
      shapes_title: 'Die vier Formen',
      shapes_body: 'Jeder Tag hat vier Teile, und jeder Teil hat eine Form. Du findest sie überall in der App.',
      shapes: {
        story: 'Blauer Kreis: die Szene. Lesen und hören.',
        reward: 'Gelbes Quadrat: die Wörter. Kurze Übungen.',
        action: 'Rotes Dreieck: deine Antwort. Du schreibst oder sprichst.',
        done: 'Schwarzes Quadrat: das Ende. Der Tag ist geschafft.',
      },
      progress_title: 'Wo du gerade bist',
      progress_body: 'Oben auf jeder Seite siehst du, wie weit du bist.',
      progress_points: [
        'Die Reihe kleiner Formen: ein Feld pro Schritt. Das Feld mit Augen ist der Schritt, auf dem du gerade bist.',
        'Fertige Schritte sind farbig, kommende sind grau.',
        'Das Logo rechts oben ist dein Tag: jede Form füllt sich, wenn ihr Teil fertig ist.',
      ],
      day_title: 'Dein erster Tag',
      day_body: 'Erst die Geschichte, dann La Forge für die Grammatik, dann deine Wörter. Wenn etwas zum ersten Mal auftaucht, erklärt es dir ein kleiner gelber Zettel.',
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
        body: 'Here you read and hear what happens in the story. You can show a translation whenever you need one. The blue circle at the top stands for the scene.',
      },
      rule: {
        title: 'The rule',
        body: 'One small grammar rule, taken from the scene you just read. Read it once; it comes up in the story right after.',
      },
      recall: {
        title: 'The words',
        body: 'Quick exercises on words from the scene. Getting one wrong is fine: you see the right answer straight away. The yellow square stands for the words.',
      },
      respond: {
        title: 'Your reply',
        body: 'Your turn: answer the character in French, in your own words. Type or speak, either works. The story reacts to what you say. The red triangle stands for your reply.',
      },
      resolution: {
        title: 'The end of the day',
        body: 'This is how the scene ends today. After it the day is done and the black square at the top fills in.',
      },
      read: {
        title: 'A page to read',
        body: 'An extra page, just for reading. You can skip it.',
      },
      desk: {
        title: 'The desk',
        body: 'A short extra exercise after the scene. It is optional.',
      },
      forge: {
        title: 'La Forge',
        body: 'Here you practise one grammar rule on its own, step by step: first recognise it, then build it yourself. About five minutes, and the rule comes back in your story afterwards.',
      },
      words: {
        title: 'The Lexique',
        body: 'Your word cards. Tap a card to turn it over, then say honestly whether you knew it. What you don’t know comes back soon, what you know comes back later.',
      },
    },
    walkthrough: {
      aria: 'Short introduction',
      next: 'Next',
      start: 'Let’s go',
      skip: 'Skip',
      welcome_title: 'Welcome to the Atelier',
      welcome_body: 'Every day you play one episode of a story set in Paris. You read what happens and answer the characters in French. What you write changes the story.',
      shapes_title: 'The four shapes',
      shapes_body: 'Every day has four parts, and each part has a shape. You will see them everywhere in the app.',
      shapes: {
        story: 'Blue circle: the scene. Read and listen.',
        reward: 'Yellow square: the words. Quick exercises.',
        action: 'Red triangle: your reply. You write or speak.',
        done: 'Black square: the ending. The day is done.',
      },
      progress_title: 'Where you are',
      progress_body: 'At the top of every page you can see how far you have come.',
      progress_points: [
        'The row of small shapes: one per step. The one with eyes is the step you are on.',
        'Finished steps are in colour, steps still ahead are grey.',
        'The logo at the top right is your day: each shape fills in when its part is done.',
      ],
      day_title: 'Your first day',
      day_body: 'First the story, then La Forge for grammar, then your words. The first time something new appears, a small yellow note explains it.',
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
        body: 'Ici, vous lisez et écoutez ce qui se passe dans l’histoire. Une traduction est toujours à portée de main. Le cercle bleu, en haut, c’est la scène.',
      },
      rule: {
        title: 'La règle',
        body: 'Une petite règle de grammaire, tirée de la scène que vous venez de lire. Lisez-la une fois ; elle revient tout de suite dans l’histoire.',
      },
      recall: {
        title: 'Les mots',
        body: 'De courts exercices sur les mots de la scène. Une erreur n’est pas grave : la bonne réponse s’affiche aussitôt. Le carré jaune, ce sont les mots.',
      },
      respond: {
        title: 'Votre réponse',
        body: 'À vous : répondez au personnage en français, avec vos propres mots, à l’écrit ou à l’oral. L’histoire réagit à ce que vous dites. Le triangle rouge, c’est votre réponse.',
      },
      resolution: {
        title: 'La fin du jour',
        body: 'Voici comment la scène se termine aujourd’hui. Ensuite la journée est bouclée et le carré noir, en haut, se remplit.',
      },
      read: {
        title: 'Une page à lire',
        body: 'Une page en plus, seulement à lire. Vous pouvez la passer.',
      },
      desk: {
        title: 'Le bureau',
        body: 'Un court exercice en plus, après la scène. Il est facultatif.',
      },
      forge: {
        title: 'La Forge',
        body: 'Ici, vous travaillez une règle de grammaire à part, pas à pas : d’abord la reconnaître, puis la former vous-même. Cinq minutes environ, et la règle revient ensuite dans votre histoire.',
      },
      words: {
        title: 'Le Lexique',
        body: 'Vos cartes de mots. Touchez une carte pour la retourner, puis dites honnêtement si vous la saviez. Ce que vous ne savez pas revient vite, le reste plus tard.',
      },
    },
    walkthrough: {
      aria: 'Courte présentation',
      next: 'Suivant',
      start: 'C’est parti',
      skip: 'Passer',
      welcome_title: 'Bienvenue à l’Atelier',
      welcome_body: 'Chaque jour, vous jouez un épisode d’une histoire à Paris. Vous lisez ce qui se passe et vous répondez aux personnages en français. Ce que vous écrivez change l’histoire.',
      shapes_title: 'Les quatre formes',
      shapes_body: 'Chaque journée a quatre parties, et chaque partie a sa forme. Vous les retrouverez partout.',
      shapes: {
        story: 'Cercle bleu : la scène. Lire et écouter.',
        reward: 'Carré jaune : les mots. De courts exercices.',
        action: 'Triangle rouge : votre réponse, écrite ou dite.',
        done: 'Carré noir : la fin. La journée est bouclée.',
      },
      progress_title: 'Où vous en êtes',
      progress_body: 'En haut de chaque page, vous voyez où vous en êtes.',
      progress_points: [
        'La rangée de petites formes : une par étape. Celle qui a des yeux, c’est l’étape en cours.',
        'Les étapes faites sont en couleur, celles à venir en gris.',
        'Le logo en haut à droite, c’est votre journée : chaque forme se remplit quand sa partie est faite.',
      ],
      day_title: 'Votre premier jour',
      day_body: 'D’abord l’histoire, puis La Forge pour la grammaire, puis vos mots. La première fois que quelque chose de nouveau apparaît, une petite note jaune l’explique.',
    },
    route: {
      title: 'Votre premier jour',
      story: 'L’histoire',
      forge: 'La Forge',
      words: 'Vos mots',
      forge_hint: 'Grammaire, 5 min environ',
      words_hint: 'Les cartes de la scène',
      next_forge: 'Ensuite : La Forge',
      next_words: 'Ensuite : vos mots',
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

export function deviceStore(): KeyValueStore | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
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
// The first day's route: story → La Forge → words
// ---------------------------------------------------------------------------

export type RouteStage = 'story' | 'forge' | 'words';
export const ROUTE_STAGES: readonly RouteStage[] = ['story', 'forge', 'words'];

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

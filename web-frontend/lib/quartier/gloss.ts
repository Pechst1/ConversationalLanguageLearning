/**
 * P12 · a beginner can read the quarter. Observed 17 Nov: day 1 was about 27 French cards with no
 * translation unless the learner found that the round «DE» chip puts a German line under each.
 *
 * - Below B1 the mother-tongue line is on by default; the learner can switch it off, and the
 *   choice is remembered on the device.
 * - The first time, a one-line note next to the chip says what it does.
 * - A stage direction («to Lila, a whisper», «crying with laughter») is authored in English only:
 *   it is shown only to a learner whose language that is, otherwise not at all.
 *
 * Pure but for the device's storage, read and written behind try/catch.
 */
import type { Level, Native } from './stage';

/** The learner's own switch: `on` / `off`. Absent until they have touched the chip. */
export const GLOSS_KEY = 'quartier.gloss';
/** The note beside the chip has been shown once. */
export const GLOSS_NOTE_KEY = 'quartier.glossNote';

type Store = Pick<Storage, 'getItem' | 'setItem'>;

function store(given?: Store | null): Store | null {
  if (given !== undefined) return given;
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

/** The line under each card is on below B1. */
export function glossByDefault(level: Level): boolean {
  return level !== 'b1';
}

/** The learner's own choice when they made one, else the level's default. */
export function readGloss(level: Level, storage?: Store | null): boolean {
  try {
    const kept = store(storage)?.getItem(GLOSS_KEY);
    if (kept === 'on') return true;
    if (kept === 'off') return false;
  } catch {
    /* storage refused: the default */
  }
  return glossByDefault(level);
}

export function writeGloss(on: boolean, storage?: Store | null): void {
  try {
    store(storage)?.setItem(GLOSS_KEY, on ? 'on' : 'off');
  } catch {
    /* storage refused: this visit only */
  }
}

/** Whether the note beside the chip is still to be shown; marks it shown. */
export function takeGlossNote(storage?: Store | null): boolean {
  try {
    const s = store(storage);
    if (!s || s.getItem(GLOSS_NOTE_KEY)) return false;
    s.setItem(GLOSS_NOTE_KEY, '1');
    return true;
  } catch {
    return false;
  }
}

export type NoteLanguage = 'en' | 'de' | 'fr';

/** The note's language: the learner's below B1, French from B1 (the interface rule). */
export function noteLanguage(native: Native, level: Level): NoteLanguage {
  return level === 'b1' ? 'fr' : native;
}

/** One line beside the chip: what it does, as it stands. */
export const GLOSS_NOTE: Record<NoteLanguage, { on: string; off: string }> = {
  en: { on: 'Your language under every line. Tap to hide it.', off: 'Tap for your language under every line.' },
  de: { on: 'Deine Sprache unter jeder Zeile. Tippe, um sie auszublenden.', off: 'Tippe für deine Sprache unter jeder Zeile.' },
  fr: { on: 'Ta langue sous chaque ligne. Touche pour la masquer.', off: 'Touche pour avoir ta langue sous chaque ligne.' },
};

/** The language stage directions are written in (the season's files, the quarter's own lines). */
export const DIRECTION_LANGUAGE: Native = 'en';

/** A stage direction as the card shows it: only in the learner's own language, else none. */
export function shownDirection(direction: string | null | undefined, native: Native): string | null {
  const text = direction?.trim();
  return text && native === DIRECTION_LANGUAGE ? text : null;
}

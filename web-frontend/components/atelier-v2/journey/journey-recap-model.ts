/**
 * WP-79 — what the end-of-day screen shows, as a pure function.
 *
 * Every fact is read from the finished journey (the recap the server stored
 * and the streak on the snapshot). Nothing is estimated here: a missing field
 * is a missing row, never a placeholder number.
 *
 *   Série  — `journey.streak.days`, «N jours»; absent at 0 (nothing to reward).
 *   Mots   — `recap.words` (or, on a pre-WP-79 recap, the vocabulary targets
 *            the steps observed, minus "not yet"); absent at 0.
 *   Scène  — measured minutes when the server measured them, else the number
 *            of steps completed. The owner's rule (2026-09-22): no goal ring,
 *            minutes stay a line of text.
 *   Face   — the day's character; the mood line only when the living story's
 *            ledger moved on *this* day's exchange.
 *   Keepsake, teaser, level-up — the server's, verbatim.
 */

import { castIdFor, expressionForMood } from '@/lib/cast-faces';
import type { PortraitMood } from '@/lib/onboarding-portraits';
import type {
  ControlLanguage,
  JourneyRecap,
  JourneySnapshot,
  RecapForecastLine,
  RecapKeepsake,
  RecapLevelUp,
  RecapTeaser,
  RecapWord,
} from '@/types/daily-journey';

import { sealForEdition, type SealVariant } from '@/components/ui/Seal';
import { momentumCopy, sealRingsLabel } from '@/lib/momentum-copy';

import { formatDuration } from './journey-state';
import { fill, recapChrome, recapStatusCopy } from './recap-copy';

export type RecapFact = { id: 'streak' | 'words' | 'scene'; label: string; value: string };

export type RecapFace = {
  characterId: string;
  name: string;
  expression: PortraitMood;
  /** «Lila vous sourit» — only when the ledger moved on this day's exchange. */
  moodLine: string | null;
  moodDirection: 'up' | 'down' | null;
  /** The character's own words about the day (the story callback), if any. */
  lineFr: string | null;
};

export type RecapSeal = {
  /** The edition (`journey.edition_no`); `null` on a server that does not send it. */
  no: number | null;
  variant: SealVariant;
  /** «22 sept.», the journey's own local day. */
  date: string | null;
  /** WP-S7: one ring per rule held on this day. */
  rings: number;
  /** WP-S7: the rings' accessible words, in the chrome language. */
  ringsLabel: string | null;
};

export type RewardView = {
  partial: boolean;
  /** WP-D4: only a *completed* day presses a seal; an early stop never does. */
  seal: RecapSeal | null;
  facts: RecapFact[];
  /** «Un jour de relâche a gardé la série» — the learner's language. */
  freezeNote: string | null;
  words: RecapWord[];
  face: RecapFace | null;
  keepsake: RecapKeepsake | null;
  teaser: RecapTeaser | null;
  levelUp: (RecapLevelUp & { evidence: string | null }) | null;
  /** WP-L6: «Cette semaine, on consolide.» while the auto-throttle is on. */
  consolidating: string | null;
  /** WP-L8: «À ce rythme : A1.2 vers novembre.» — once a week, a completed day only. */
  forecast: string | null;
  /** The first server-issued practice href among the day's targets. */
  practiceHref: string | null;
  practiceLabelFr: string | null;
};

/** The words the day practised: the server's list, or derived from old recaps. */
export function recapWords(recap: JourneyRecap | null | undefined): RecapWord[] {
  if (!recap) return [];
  if (Array.isArray(recap.words)) return recap.words;
  const seen = new Set<string>();
  const out: RecapWord[] = [];
  for (const item of recap.practiced_targets || []) {
    if (item.target.kind !== 'vocabulary' || item.evidence_kind === 'not_yet') continue;
    if (seen.has(item.target.id)) continue;
    seen.add(item.target.id);
    out.push({
      id: item.target.id,
      label_fr: item.target.label_fr,
      label_native: item.target.label_native ?? null,
      evidence_kind: item.evidence_kind,
    });
  }
  return out;
}

function sceneValue(recap: JourneyRecap, journey: JourneySnapshot, language: ControlLanguage): string | null {
  const chrome = recapChrome(language);
  const minutes = formatDuration(recap.active_seconds, language);
  if (minutes) return minutes;
  const done =
    typeof recap.steps_done === 'number'
      ? recap.steps_done
      : (journey.steps || []).filter((step) => step.status === 'completed').length;
  if (done <= 0) return null;
  return done === 1 ? chrome.step_value : fill(chrome.steps_value, { n: done });
}

function faceOf(recap: JourneyRecap, journey: JourneySnapshot, language: ControlLanguage): RecapFace | null {
  const chrome = recapChrome(language);
  const mood = recap.mood ?? null;
  const characterId = mood?.character_id || journey.scenario?.character_id || '';
  const name = mood?.character_name || journey.scenario?.character_name || '';
  if (!name || !castIdFor(characterId, name)) return null;
  const shift = mood?.shift ?? null;
  const expression: PortraitMood =
    shift === 'warmer'
      ? 'happy'
      : shift === 'colder'
        ? 'cross'
        : mood
          ? expressionForMood(mood.mood)
          : recap.objective_outcome === 'met'
            ? 'happy'
            : 'neutral';
  const moodLine =
    shift === 'warmer'
      ? fill(chrome.mood_warmer, { name })
      : shift === 'colder'
        ? fill(chrome.mood_colder, { name })
        : null;
  return {
    characterId,
    name,
    expression,
    moodLine,
    moodDirection: shift === 'warmer' ? 'up' : shift === 'colder' ? 'down' : null,
    lineFr: recap.story_outcome?.callback_fr?.trim() || null,
  };
}

function levelEvidence(level: RecapLevelUp, language: ControlLanguage): string | null {
  const copy = recapStatusCopy(language);
  const w = Math.max(0, Number(level.mastered_vocabulary) || 0);
  const g = Math.max(0, Number(level.mastered_grammar) || 0);
  if (w > 0 && g > 0) return fill(copy.level_evidence, { w, g });
  if (w > 0) return fill(copy.level_evidence_words, { w });
  if (g > 0) return fill(copy.level_evidence_rules, { g });
  return null;
}

/** WP-S7: how many rules became held on the journey's day (the Seal's rings). */
export function heldToday(journey: JourneySnapshot): number {
  const ids = journey.mastery_today?.held_concept_ids;
  return Array.isArray(ids) ? new Set(ids.map(Number).filter(Number.isFinite)).size : 0;
}

export function rewardView(
  journey: JourneySnapshot,
  recap: JourneyRecap | null,
  language: ControlLanguage = 'en',
): RewardView | null {
  if (!recap) return null;
  const partial = recap.completion_kind === 'early' || journey.status === 'ended_early';
  // WP-D4: Scène · Mots · Série, in the order the day was lived.
  const facts: RecapFact[] = [];
  const chrome = recapChrome(language);
  const scene = sceneValue(recap, journey, language);
  if (scene) facts.push({ id: 'scene', label: chrome.scene_label, value: scene });
  const words = recapWords(recap);
  if (words.length > 0) {
    facts.push({ id: 'words', label: chrome.words_label, value: `+${words.length}` });
  }
  const streakDays = Number(journey.streak?.days ?? 0);
  if (Number.isFinite(streakDays) && streakDays > 0) {
    const n = Math.round(streakDays);
    facts.push({
      id: 'streak',
      label: chrome.streak_label,
      value: n === 1 ? chrome.streak_value_one : fill(chrome.streak_value, { n }),
    });
  }

  const freezeUsed = Boolean(journey.streak?.freeze_used_on) && streakDays > 0;
  const firstPractice = (recap.practiced_targets || []).find((item) => item.practice_href);
  const teaser = recap.teaser && recap.teaser.text_fr?.trim() ? recap.teaser : null;

  const completed = !partial && journey.status === 'completed';
  const editionNo =
    typeof journey.edition_no === 'number' && Number.isFinite(journey.edition_no) ? journey.edition_no : null;

  return {
    partial,
    seal: completed
      ? {
          no: editionNo,
          variant: editionNo != null ? sealForEdition(editionNo).variant : 'quad',
          date: keepsakeDate(recap.keepsake?.local_date ?? journey.local_date),
          rings: heldToday(journey),
          ringsLabel: sealRingsLabel(momentumCopy(language), heldToday(journey)),
        }
      : null,
    facts,
    freezeNote: freezeUsed ? recapStatusCopy(language).freeze_used : null,
    words,
    face: faceOf(recap, journey, language),
    // A keepsake is a completed day's; an early stop never shows one.
    keepsake: partial ? null : recap.keepsake ?? null,
    teaser: partial ? null : teaser,
    levelUp: recap.level_up ? { ...recap.level_up, evidence: levelEvidence(recap.level_up, language) } : null,
    consolidating: recap.consolidating ? recapStatusCopy(language).consolidating : null,
    forecast: completed ? forecastLineText(recap.forecast_line, language, journey.local_date) : null,
    practiceHref: firstPractice?.practice_href ?? null,
    practiceLabelFr: firstPractice?.target.label_fr ?? null,
  };
}

/** «22 sept.» for the keepsake caption. `null` for an unreadable date. */
export function keepsakeDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(`${value}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return null;
  try {
    return new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' }).format(parsed);
  } catch {
    return null;
  }
}

const MONTH_LOCALE: Record<ControlLanguage, string> = { en: 'en-GB', de: 'de-DE', fr: 'fr-FR' };

/**
 * WP-L8 — «At this rhythm: A1.2 around November.» in the chrome language, from
 * a *measured* forecast only (the server never sends a prior; a line not
 * marked measured is dropped here too). The year is added when the month is
 * not in the day's own year.
 */
export function forecastLineText(
  line: RecapForecastLine | null | undefined,
  language: ControlLanguage,
  localDate?: string | null,
): string | null {
  if (!line || !line.measured || !line.target) return null;
  const match = /^(\d{4})-(\d{2})$/.exec(String(line.month || ''));
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (!(month >= 1 && month <= 12)) return null;
  const today = localDate ? new Date(`${localDate}T12:00:00`) : new Date();
  const sameYear = !Number.isNaN(today.getTime()) && today.getFullYear() === year;
  let name: string;
  try {
    name = new Intl.DateTimeFormat(MONTH_LOCALE[language] ?? 'en-GB', {
      month: 'long',
      ...(sameYear ? {} : { year: 'numeric' }),
    }).format(new Date(year, month - 1, 15, 12));
  } catch {
    return null;
  }
  return fill(recapStatusCopy(language).forecast_line, { level: line.target, month: name });
}

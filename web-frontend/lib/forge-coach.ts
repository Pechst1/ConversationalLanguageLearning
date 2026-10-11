/**
 * WP-S5 — La Forge's coaches.
 *
 * Every rule has a coach: one cast member per family of units (Margaux at the
 * counter, Gus for the past, Romy for questions, Lila for describing, Marin
 * for everyday verbs and pronouns, M. Marchand for the flat). The server puts
 * the coach on the atelier concept (`concept.coach`), on the forge's `next`
 * and `rules`, and on every observed answer (`correction.forge.coach` and
 * `coach_mood`). These helpers pick the coach for the screen and the face they
 * make; the rule card and the feedback band draw it with `CastPortrait`.
 */

import type { PortraitMood } from './onboarding-portraits';

export type ForgeCoach = {
  id: string;
  name: string;
  register?: 'tu' | 'vous' | string;
  family?: string | null;
  family_title?: Record<string, string> | null;
};

const MOODS: PortraitMood[] = ['neutral', 'happy', 'cross', 'moved'];

function isCoach(value: unknown): value is ForgeCoach {
  return Boolean(
    value && typeof value === 'object' && typeof (value as ForgeCoach).id === 'string' && (value as ForgeCoach).id
      && typeof (value as ForgeCoach).name === 'string',
  );
}

/** The rule's coach: the forge's word first (next, then the rule), then the concept's. */
export function coachFor(...sources: Array<{ coach?: unknown } | null | undefined>): ForgeCoach | null {
  for (const source of sources) {
    if (source && isCoach(source.coach)) return source.coach;
  }
  return null;
}

/**
 * The coach's face after an answer: the server's `coach_mood` when it sent one;
 * otherwise happy on a checked right answer, cross on a checked wrong one,
 * moved when the answer made the rule held, neutral while it is unchecked.
 */
export function coachMood(
  correction: Record<string, any> | null | undefined,
  fallback: { correct?: boolean | null; checked?: boolean } = {},
): PortraitMood {
  const forge = correction && typeof correction === 'object' ? correction.forge : null;
  const sent = forge && typeof forge === 'object' ? forge.coach_mood : null;
  if (typeof sent === 'string' && (MOODS as string[]).includes(sent)) return sent as PortraitMood;
  if (forge && forge.held === true) return 'moved';
  const checked = fallback.checked ?? correction?.assessment_status !== 'provisional';
  if (!checked || fallback.correct == null) return 'neutral';
  return fallback.correct ? 'happy' : 'cross';
}

/** The two lines of a free-use scene, when the item is one. */
export function sceneLines(item: Record<string, any> | null | undefined): Array<{ speaker: string; name?: string; fr: string; en?: string }> {
  const lines = item?.scene?.lines;
  if (!Array.isArray(lines)) return [];
  return lines
    .filter((line: any) => line && typeof line.fr === 'string' && typeof line.speaker === 'string')
    .map((line: any) => ({ speaker: line.speaker, name: line.name, fr: line.fr, en: line.en }));
}

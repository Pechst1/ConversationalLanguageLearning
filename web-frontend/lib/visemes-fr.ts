/**
 * WP-116 phase 4 · French text → the six mouth shapes of the drawn cast.
 *
 * The voice clips carry no phoneme timings (the TTS returns audio only), so the
 * mouth follows the text: each grapheme group becomes a shape with a weight (how
 * long it is held), and the playback position (0…1) of the line picks the shape.
 * Rough on purpose: a mouth that opens on vowels, closes on m/b/p, bites on f/v
 * and rests on pauses reads as speech; exact phonetics would not read better.
 */
import type { Viseme } from '@/components/cast/rig-kit';

export type MouthStep = { viseme: Viseme; weight: number };

/** Longest first: a group is matched before its letters. */
const GROUPS: Array<[RegExp, Viseme, number]> = [
  [/^(eau|aux|au|ô|o|ou|où|oû|u|û|ù|eu|œu|œ|on|om)/, 'o', 1],
  [/^(ai|aî|ei|é|è|ê|ë|e|i|î|ï|y|in|im|ain|ein|un)/, 'e', 0.9],
  [/^(an|am|en|em|a|à|â)/, 'a', 1],
  [/^(m|b|p)/, 'm', 0.6],
  [/^(f|v|ph)/, 'f', 0.6],
  [/^[cdgjklnqrstwxzhç]/, 'rest', 0.35],
];

function fold(text: string): string {
  return text.toLowerCase().replace(/[’']/g, ' ');
}

/** The line as a sequence of mouth shapes with their relative durations. */
export function mouthSteps(text: string): MouthStep[] {
  const steps: MouthStep[] = [];
  let rest = fold(text);
  while (rest.length) {
    const char = rest[0];
    if (/[.!?…;:]/.test(char)) {
      steps.push({ viseme: 'rest', weight: 1.4 });
      rest = rest.slice(1);
      continue;
    }
    if (/[\s,—–-]/.test(char)) {
      steps.push({ viseme: 'rest', weight: char === ',' ? 0.9 : 0.25 });
      rest = rest.slice(1);
      continue;
    }
    const group = GROUPS.find(([pattern]) => pattern.test(rest));
    if (!group) {
      rest = rest.slice(1);
      continue;
    }
    const match = rest.match(group[0]);
    const length = match ? match[0].length : 1;
    const last = steps[steps.length - 1];
    // Two vowels of one shape in a row hold the shape instead of flickering.
    if (last && last.viseme === group[1] && group[1] !== 'rest') last.weight += group[2] * 0.6;
    else steps.push({ viseme: group[1], weight: group[2] });
    rest = rest.slice(length);
  }
  return steps;
}

/** The shape at `progress` (0…1) of the line; `rest` outside it. */
export function visemeAt(steps: MouthStep[], progress: number): Viseme {
  if (!steps.length || !(progress >= 0) || progress >= 1) return 'rest';
  const total = steps.reduce((sum, step) => sum + step.weight, 0);
  let at = progress * total;
  for (const step of steps) {
    if (at < step.weight) return step.viseme;
    at -= step.weight;
  }
  return 'rest';
}

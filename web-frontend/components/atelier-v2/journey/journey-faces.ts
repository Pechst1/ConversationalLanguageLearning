/**
 * WP-77 — who is on screen in the daily journey.
 *
 * The scene's speaker and the one who reacts to a recall answer is the day's
 * scenario character; a respond step names its own speaker (a letter day's
 * correspondent first). Pure, so the node harness can check it.
 */

import { castIdFor } from '@/lib/cast-faces';
import type { JourneySnapshot, PublicStep } from '@/types/daily-journey';

export type JourneySpeaker = { id: string | null; name: string };

/** The cast's short names, as the rule cards and La Forge say them. */
const COACH_NAMES: Record<string, string> = {
  margaux_barman: 'Margaux',
  marin_leveque: 'Marin',
  romy_tremblay: 'Romy',
  lila_bonnet: 'Lila',
  augustin_de_roncourt: 'Gus',
  landlord_marchand: 'M. Marchand',
};

/**
 * One name per face (#155): a payload may say «Augustin « Gus » de Roncourt» while the rule card
 * and La Forge say «Gus». The name the learner reads is always the cast's short name for the same
 * registry entry the face is drawn from; anyone outside the cast keeps the name they came with.
 */
export function speakerOf(id: string | null | undefined, name: string): JourneySpeaker {
  const castId = castIdFor(id, name);
  return { id: id || null, name: (castId && COACH_NAMES[castId]) || name };
}

export function journeySpeaker(
  journey: Pick<JourneySnapshot, 'scenario'> | null | undefined,
  step?: PublicStep | null,
): JourneySpeaker | null {
  if (step?.kind === 'respond') {
    const letter = step.prompt.letter;
    if (letter?.correspondent_name) {
      return speakerOf(letter.correspondent_id, letter.correspondent_name);
    }
    if (step.prompt.character_name) {
      return speakerOf(step.prompt.character_id, step.prompt.character_name);
    }
  }
  // WP-93: «Coulisses» is someone's evening — theirs is the face on screen.
  if (step?.kind === 'read' && step.prompt.character_name) {
    return speakerOf(step.prompt.character_id, step.prompt.character_name);
  }
  const scenario = journey?.scenario;
  if (scenario?.character_name) {
    return speakerOf(scenario.character_id, scenario.character_name);
  }
  return null;
}

/**
 * La troupe vivante: who asks a drill and reacts to its answer. A grammar drill on a rule the
 * day introduces belongs to that rule's coach (the card's speaker, as in La Forge); anything else
 * stays with the scene's character. `null` when nobody is known.
 */
export function drillSpeaker(
  journey: Pick<JourneySnapshot, 'scenario' | 'steps'> | null | undefined,
  step: PublicStep | null | undefined,
): JourneySpeaker | null {
  if (step?.kind === 'recall' && step.prompt.target?.kind === 'grammar') {
    const concept = Number(step.prompt.target.id);
    for (const other of journey?.steps ?? []) {
      if (other.kind !== 'rule' || other.prompt.concept_id !== concept) continue;
      const id = other.prompt.rule_card?.speaker;
      if (id && COACH_NAMES[id]) return speakerOf(id, COACH_NAMES[id]);
    }
  }
  return journeySpeaker(journey, step);
}

/**
 * WP-77 — who is on screen in the daily journey.
 *
 * The scene's speaker and the one who reacts to a recall answer is the day's
 * scenario character; a respond step names its own speaker (a letter day's
 * correspondent first). Pure, so the node harness can check it.
 */

import { drawnCastIdFor } from '@/lib/cast-faces';
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
  camille_marchand: 'Camille',
  odile_ferrand: 'Odile',
};

/**
 * The one name the learner reads for a person of the drawn cast, or `null` for anyone outside it
 * (a clerk, a generated character). Every surface that prints a speaker's name goes through this
 * (#155, #217): the opening line, each later line of a many-voiced reply, the listen button, the
 * rule card. It mirrors the server's cast registry (`app/services/cast_registry.py`), which sends
 * the same name; this is the net for a payload that still carries the world bible's full name.
 */
export function castDisplayName(id: string | null | undefined, name: string | null | undefined): string | null {
  const castId = drawnCastIdFor(id, name);
  return (castId && COACH_NAMES[castId]) || null;
}

/**
 * One name per face (#155): a payload may say «Augustin « Gus » de Roncourt» while the rule card
 * and La Forge say «Gus». The name the learner reads is always the cast's short name for the same
 * registry entry the face is drawn from; anyone outside the cast keeps the name they came with.
 */
export function speakerOf(id: string | null | undefined, name: string): JourneySpeaker {
  return { id: id || null, name: castDisplayName(id, name) || name };
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

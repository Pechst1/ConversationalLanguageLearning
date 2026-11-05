/**
 * WP-77 — who is on screen in the daily journey.
 *
 * The scene's speaker is the day's scenario character; a respond step names its
 * own speaker (a letter day's correspondent first). A recall item cut from a line
 * of the scene is that line's speaker's (#155, `drillSpeaker`). Pure, so the node
 * harness can check it.
 */

import { castDisplayName } from '@/lib/cast-faces';
import type { JourneySnapshot, PublicStep } from '@/types/daily-journey';

export type JourneySpeaker = { id: string | null; name: string };

/** The cast's names live in `lib/cast-faces.ts` (#147, #473); re-exported for the journey's callers. */
export { castDisplayName };

/**
 * One name per face (#155): a payload may say «Augustin « Gus » de Roncourt» while the rule card
 * and La Forge say «Gus». The name the learner reads is always the cast's short name for the same
 * registry entry the face is drawn from; anyone outside the cast keeps the name they came with.
 */
export function speakerOf(id: string | null | undefined, name: string): JourneySpeaker {
  return { id: id || null, name: castDisplayName(id, name) || name };
}

function actOfStep(step: { act?: number | null } | null | undefined): number {
  const act = step?.act;
  return typeof act === 'number' && Number.isFinite(act) && act >= 1 ? Math.floor(act) : 1;
}

export function journeySpeaker(
  journey: (Pick<JourneySnapshot, 'scenario'> & Partial<Pick<JourneySnapshot, 'steps'>>) | null | undefined,
  step?: PublicStep | null,
): JourneySpeaker | null {
  // Phase 2 «Folge in Akten»: a later act's scene and ending belong to that act's
  // character — the one who asks its reply — not to the day's (the first act's).
  if ((step?.kind === 'scene' || step?.kind === 'resolution') && actOfStep(step) > 1) {
    const act = actOfStep(step);
    const reply = (journey?.steps ?? []).find((other) => other.kind === 'respond' && actOfStep(other) === act);
    if (reply?.kind === 'respond' && reply.prompt.character_name) {
      return speakerOf(reply.prompt.character_id, reply.prompt.character_name);
    }
  }
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
 * La troupe vivante: who asks a drill and reacts to its answer. A drill cut from a line of
 * today's scene belongs to whoever says that line (#155: the server names them in
 * `prompt.speaker`, so a rebuilt line of Marin's is Marin's face and «Marin te sourit», not the
 * day's character's). Otherwise a grammar drill on a rule the day introduces belongs to that
 * rule's coach (the card's speaker, as in La Forge), and anything else stays with the scene's
 * character. `null` when nobody is known.
 */
export function drillSpeaker(
  journey: Pick<JourneySnapshot, 'scenario' | 'steps'> | null | undefined,
  step: PublicStep | null | undefined,
): JourneySpeaker | null {
  const line = step?.kind === 'recall' ? step.prompt.speaker : null;
  if (line?.id && line.name) return speakerOf(line.id, line.name);
  if (step?.kind === 'recall' && step.prompt.target?.kind === 'grammar') {
    const concept = Number(step.prompt.target.id);
    for (const other of journey?.steps ?? []) {
      if (other.kind !== 'rule' || other.prompt.concept_id !== concept) continue;
      const id = other.prompt.rule_card?.speaker;
      const coach = castDisplayName(id, null);
      if (id && coach) return speakerOf(id, coach);
    }
  }
  return journeySpeaker(journey, step);
}

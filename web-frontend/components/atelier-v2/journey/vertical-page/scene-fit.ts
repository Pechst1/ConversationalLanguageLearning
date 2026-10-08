/**
 * WP-144b · can the vertical page stage this scene?
 *
 * The vertical page draws the speakers as the drawn cast standing on the plate,
 * with the balloons pointing at them. It has nothing to point at when:
 *
 *   · the art set is `painted` (the production default until WP-116 phase 6):
 *     the plate is an empty room and the people are portrait discs;
 *   · a panel where someone speaks has no plate, or none of its speakers has a
 *     drawn figure on its stage.
 *
 * Then the whole scene is read in the list layout. The decision is per scene,
 * never per panel: switching layouts between two panels is jarring.
 *
 * Pure: no React, no DOM.
 */

import { drawnFaceId } from '../../../cast/CastFace';
import { rigFor } from '../../../cast/cast-registry';
import { stageMembers, type StageMember } from '../../../cast/PanelStage';
import type { ReaderLine } from '../../../feuilleton/reader/panel-model';

type PanelLike = {
  kind: string;
  lines?: Array<Pick<ReaderLine, 'you' | 'character' | 'speakerId' | 'who'>>;
  plateUrl?: string;
  cast?: StageMember[] | null;
};

/** The learner's line (a reply, or the story's own «Vous»): never a cast figure. */
function learner(line: Pick<ReaderLine, 'you' | 'character'>): boolean {
  return Boolean(line.you) || line.character === 'toi';
}

/** The rig a line's speaker is drawn with, if any. */
function speakerRig(line: Pick<ReaderLine, 'speakerId' | 'who'>): string | null {
  const rigId = drawnFaceId(line.speakerId || '', line.who || '');
  return rigId && rigId !== 'user' && rigFor(rigId) ? rigId : null;
}

/** Does this panel have someone to point at for every voice in it? */
export function panelFitsVertical(stage: PanelLike): boolean {
  if (stage.kind !== 'panel') return true;
  const speakers = (stage.lines ?? []).filter((line) => !learner(line) && (line.speakerId || line.who));
  if (!speakers.length) return true;
  if (!stage.plateUrl) return false;
  const standing = new Set(stageMembers(stage.cast ?? []).filter((member) => rigFor(member.rigId)).map((member) => member.rigId));
  return speakers.some((line) => {
    const rigId = speakerRig(line);
    return Boolean(rigId && standing.has(rigId));
  });
}

/** The vertical page for this scene, or the list: drawn art and a figure for every panel's voices. */
export function sceneFitsVertical(stages: PanelLike[], artSet: 'painted' | 'drawn'): boolean {
  if (artSet !== 'drawn') return false;
  return stages.every(panelFitsVertical);
}

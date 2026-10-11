/**
 * WP-116 · which rig draws which cast member, and how the app's moods map onto
 * the rigs' moods.
 */
import type { StageMood } from '@/lib/cast-faces';
import type { PortraitMood } from '@/lib/onboarding-portraits';

import type { HeldMouth, RigDef, RigMood } from './rig-kit';
import { camille } from './rigs/camille';
import { generatedRig } from './rigs/generated';
import { RIG_ALIASES, generatedSpec } from './generated-cast';
import { gus } from './rigs/gus';
import { lila } from './rigs/lila';
import { marchand } from './rigs/marchand';
import { margaux } from './rigs/margaux';
import { marin } from './rigs/marin';
import { odile } from './rigs/odile';
import { romy } from './rigs/romy';
import { toi } from './rigs/toi';

export const RIGS: readonly RigDef[] = [margaux, lila, gus, marin, romy, marchand, camille, odile, toi];

const BY_ID: Record<string, RigDef> = {};
RIGS.forEach((rig) => {
  BY_ID[rig.id] = rig;
});

/** Short names and older ids the app and the story engine use for the same people. */
const ALIASES: Readonly<Record<string, string>> = RIG_ALIASES;

/**
 * WP-168 · the characters a written season invented (`generated-cast.ts` holds who
 * they are), drawn from their parameters the first time the stage asks for them and
 * again only when the server sends them changed.
 */
const GENERATED: Record<string, { key: string; rig: RigDef }> = {};

function generatedRigDef(id: string): RigDef | null {
  const spec = generatedSpec(id);
  if (!spec) return null;
  const cached = GENERATED[spec.id];
  if (cached && cached.key === spec.key) return cached.rig;
  const rig = generatedRig(spec.id, spec.name, spec.rig);
  GENERATED[spec.id] = { key: spec.key, rig };
  return rig;
}

export { registerGeneratedRigs, generatedRigId } from './generated-cast';
export type { GeneratedCastRig } from './generated-cast';

export function rigFor(id: string | null | undefined): RigDef | null {
  if (!id) return null;
  const key = String(id).trim().toLowerCase();
  return BY_ID[key] ?? BY_ID[ALIASES[key] ?? ''] ?? generatedRigDef(key);
}

export function hasRig(id: string | null | undefined): boolean {
  return rigFor(id) !== null;
}

const FROM_PORTRAIT: Record<PortraitMood, RigMood> = {
  neutral: 'neutre',
  happy: 'ravie',
  cross: 'fachee',
  moved: 'emue',
};

/** The app speaks in portrait moods; the rigs add `surprise`. */
export function rigMoodFor(mood: PortraitMood | RigMood | 'surprised' | null | undefined): RigMood {
  if (!mood) return 'neutre';
  if (mood === 'surprised') return 'surprise';
  if (mood in FROM_PORTRAIT) return FROM_PORTRAIT[mood as PortraitMood];
  return ['neutre', 'ravie', 'surprise', 'fachee', 'emue'].indexOf(mood) >= 0 ? (mood as RigMood) : 'neutre';
}

/**
 * WP-137 C-4 · the face a figure makes on the stage. The four app moods are the
 * rigs' own; `cold` (a dry «Non.», a frosty welcome) is the neutral face held on
 * the level `flat` mouth — every neutral rig mouth is a smile or a smirk, and a
 * cold beat never renders one. No new drawing: eyes, brows and mouth all exist.
 */
export function rigFaceFor(
  mood: StageMood | RigMood | 'surprised' | null | undefined,
): { mood: RigMood; mouth: HeldMouth | 'auto' } {
  if (mood === 'cold') return { mood: 'neutre', mouth: 'flat' };
  return { mood: rigMoodFor(mood), mouth: 'auto' };
}

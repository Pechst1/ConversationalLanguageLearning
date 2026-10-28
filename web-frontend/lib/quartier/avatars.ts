/**
 * Le Quartier · the records behind the people the avatar kit draws for the quarter: a passer-by
 * rolled from a seed, and someone a forged place names (a stallholder, the clerk at the window)
 * rolled the same way, then dressed by the brief's `look`. The card (`cast-art.tsx`) and the body
 * in the round (`cast3d/avatar.ts`) are made from the same record, so they are the same person.
 */
import type { AvatarConfig } from '@/lib/avatar';
import { normalizeAvatar, randomAvatar } from '@/lib/avatar';

import { seeded } from './geo';

export function passerbyAvatar(seed: number): AvatarConfig {
  return randomAvatar(seeded(seed).next);
}

export function personAvatar(seed: number, look: Record<string, string | boolean> = {}): AvatarConfig {
  return normalizeAvatar({ ...randomAvatar(seeded(seed).next), ...look });
}

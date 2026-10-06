/**
 * WP-77 (portrait part) — the cast's faces.
 *
 * Four 256px expression portraits per character: `portrait-{neutral,happy,cross,moved}.webp`.
 * Since WP-D8 (2026-09-23) they are head crops of the owner-approved screen-print cast: one
 * approved chest-up portrait per character, each mood an edit of it. They no longer come from
 * the old model sheets (`scripts/crop-portraits.py` is retired for these files). Only characters
 * with a drawn face have them — the learner is never drawn, so a `user` portrait never exists
 * and falls back to an initial.
 */

export type PortraitMood = 'neutral' | 'happy' | 'cross' | 'moved';

export const PORTRAIT_MOODS: PortraitMood[] = ['neutral', 'happy', 'cross', 'moved'];

/**
 * WP-116 phase 4: the reaction to a wrong answer. The drawn cast shows surprise,
 * never anger at the learner; the painted set has no surprised portrait and keeps
 * its cross one.
 */
export type FaceMood = PortraitMood | 'surprised';

/** Characters whose sheet has three expression busts. */
export const CAST_WITH_PORTRAITS = [
  'romy_tremblay',
  'marin_leveque',
  'lila_bonnet',
  'margaux_barman',
  'augustin_de_roncourt',
  'landlord_marchand',
] as const;

const WITH_PORTRAITS = new Set<string>(CAST_WITH_PORTRAITS);

/** The static path of one portrait, or `null` when that character has none. */
export function portraitSrc(characterId: string | null | undefined, mood: FaceMood = 'neutral'): string | null {
  const id = (characterId ?? '').trim();
  if (!WITH_PORTRAITS.has(id)) return null;
  const painted: PortraitMood = mood === 'surprised' ? 'cross' : mood;
  const safeMood = PORTRAIT_MOODS.includes(painted) ? painted : 'neutral';
  return `/assets/serial/characters/${id}/portrait-${safeMood}.webp`;
}

/** The initial drawn when there is no portrait (or it failed to load). */
export function portraitInitial(name: string | null | undefined, characterId?: string | null): string {
  const source = (name ?? '').trim() || (characterId ?? '').trim();
  return source.charAt(0).toUpperCase() || '·';
}

/**
 * WP-77 (portrait part) — the cast's faces.
 *
 * `scripts/crop-portraits.py` cuts three 256px expression portraits out of each
 * model sheet: `portrait-{neutral,happy,cross}.webp`. Only characters with a
 * drawn face have them — the learner's own sheet is drawn from behind, so a
 * `user` portrait never exists and falls back to an initial.
 */

export type PortraitMood = 'neutral' | 'happy' | 'cross';

export const PORTRAIT_MOODS: PortraitMood[] = ['neutral', 'happy', 'cross'];

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
export function portraitSrc(characterId: string | null | undefined, mood: PortraitMood = 'neutral'): string | null {
  const id = (characterId ?? '').trim();
  if (!WITH_PORTRAITS.has(id)) return null;
  const safeMood = PORTRAIT_MOODS.includes(mood) ? mood : 'neutral';
  return `/assets/serial/characters/${id}/portrait-${safeMood}.webp`;
}

/** The initial drawn when there is no portrait (or it failed to load). */
export function portraitInitial(name: string | null | undefined, characterId?: string | null): string {
  const source = (name ?? '').trim() || (characterId ?? '').trim();
  return source.charAt(0).toUpperCase() || '·';
}

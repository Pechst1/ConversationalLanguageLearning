/**
 * WP-168 · the parameters a written season's new character is drawn from.
 *
 * The fixed cast (`rigs/<id>.tsx`) is hand-drawn art with a computed face. A character
 * the season writer invents (a ferry captain in Marseille, a radio host in Dakar) has no
 * hand-drawn file: the writer chooses a value for each parameter below, the server
 * stores them on the character (`season.written_world.RIG_VOCABULARY`, mirrored here
 * value for value, a backend test reads this file), and `rigs/generated.tsx` builds the
 * figure from them, with the same face machinery as the fixed cast.
 *
 * Every colour is one the drawn cast already wears (`rigs/*`): no new colour enters
 * the stage. A value outside the vocabulary is the default (`normaliseRigParams`), so a
 * new face always draws.
 */

export const RIG_VOCABULARY = {
  build: ['slim', 'medium', 'broad'],
  height: ['short', 'medium', 'tall'],
  head: ['round', 'oval', 'long', 'square'],
  skin: ['porcelain', 'light', 'rose', 'warm', 'olive', 'tan', 'brown', 'deep', 'deeper', 'deepest'],
  hair: ['bald', 'cropped', 'short', 'bob', 'long', 'wavy', 'curly', 'afro', 'bun', 'braids', 'ponytail', 'locs'],
  hair_colour: ['black', 'dark_brown', 'brown', 'chestnut', 'auburn', 'copper', 'blond', 'grey', 'white'],
  facial_hair: ['none', 'stubble', 'moustache', 'beard'],
  glasses: ['none', 'round', 'square'],
  top: ['coat', 'jacket', 'jumper', 'shirt', 'dress', 'apron', 'overalls', 'hoodie', 'boubou', 'suit', 'uniform'],
  top_colour: ['ink', 'navy', 'cobalt', 'sky', 'red', 'brick', 'green', 'pine', 'olive', 'ochre', 'yellow', 'charcoal', 'slate', 'grey', 'stone', 'cream', 'brown'],
  bottom_colour: ['ink', 'navy', 'cobalt', 'sky', 'red', 'brick', 'green', 'pine', 'olive', 'ochre', 'yellow', 'charcoal', 'slate', 'grey', 'stone', 'cream', 'brown'],
  accessory: ['none', 'scarf', 'beret', 'cap', 'headwrap', 'earrings', 'necklace'],
  accessory_colour: ['ink', 'navy', 'cobalt', 'sky', 'red', 'brick', 'green', 'pine', 'olive', 'ochre', 'yellow', 'charcoal', 'slate', 'grey', 'stone', 'cream', 'brown'],
  idle: ['bob', 'bounce', 'sway', 'nod'],
} as const;

export type RigParamKey = keyof typeof RIG_VOCABULARY;
export type RigParams = { [K in RigParamKey]: (typeof RIG_VOCABULARY)[K][number] };

export const RIG_DEFAULTS: RigParams = {
  build: 'medium',
  height: 'medium',
  head: 'oval',
  skin: 'warm',
  hair: 'short',
  hair_colour: 'brown',
  facial_hair: 'none',
  glasses: 'none',
  top: 'jumper',
  top_colour: 'cobalt',
  bottom_colour: 'ink',
  accessory: 'none',
  accessory_colour: 'red',
  idle: 'bob',
};

/** The cast's own skin tones, lightest to deepest (Odile … Marin, then the cast's darker browns). */
export const SKIN: Record<RigParams['skin'], string> = {
  porcelain: '#ecbfa0',
  light: '#ecb896',
  rose: '#e3a98a',
  warm: '#e0a985',
  olive: '#d8a07a',
  tan: '#cf946a',
  brown: '#c98a62',
  deep: '#9a6643',
  deeper: '#774a2c',
  deepest: '#5a3a26',
};

export const HAIR: Record<RigParams['hair_colour'], string> = {
  black: '#1c1611',
  dark_brown: '#2a1a12',
  brown: '#4a2e1a',
  chestnut: '#5a3a22',
  auburn: '#9c2411',
  copper: '#a5683f',
  blond: '#c49a0a',
  grey: '#a59e8f',
  white: '#e9e4d8',
};

export const COLOURS: Record<RigParams['top_colour'], string> = {
  ink: '#1f1b16',
  navy: '#14285f',
  cobalt: '#1d3a8a',
  sky: '#7f9bd0',
  red: '#d8321a',
  brick: '#9c2411',
  green: '#2c6a5d',
  pine: '#1f4f45',
  olive: '#5d6e35',
  ochre: '#c49a0a',
  yellow: '#f3c318',
  charcoal: '#3e4542',
  slate: '#59615d',
  grey: '#8a8476',
  stone: '#c9c2b2',
  cream: '#f8f3e8',
  brown: '#8a5a32',
};

function fold(value: unknown): string {
  return String(value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_')
    .replace(/_colour$/, '');
}

/** Every parameter from the vocabulary; anything else is the default. */
export function normaliseRigParams(raw: unknown): RigParams {
  const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};
  const out = { ...RIG_DEFAULTS } as Record<RigParamKey, string>;
  (Object.keys(RIG_VOCABULARY) as RigParamKey[]).forEach((key) => {
    const value = fold(source[key]);
    if ((RIG_VOCABULARY[key] as readonly string[]).indexOf(value) >= 0) out[key] = value;
  });
  return out as RigParams;
}

/** A darker shade of a colour (folds, shadows, lids): mixed toward the cast's ink. */
export function shade(hex: string, amount = 0.18): string {
  const value = hex.replace('#', '');
  const ink = [0x14, 0x11, 0x0d];
  const mixed = [0, 2, 4].map((at, index) => {
    const channel = parseInt(value.slice(at, at + 2), 16) || 0;
    return Math.max(0, Math.min(255, Math.round(channel + (ink[index] - channel) * amount)));
  });
  return `#${mixed.map((channel) => channel.toString(16).padStart(2, '0')).join('')}`;
}

/** A small stable number from a string (an idle's tempo, so two new faces never bob in step). */
export function hashOf(text: string): number {
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

/**
 * Ton personnage · the learner's own drawn character, as data.
 *
 * The cast is drawn (components/cast); until now the learner was only ever Toi, seen from behind.
 * This is the learner's face-on character, made in the editor (`/personnage`) and shown in the
 * Cahier. A character is a small flat record of part ids and colour ids, so the server stores it
 * as JSON (`users.avatar`) and checks it without knowing how anything is drawn.
 *
 * Every colour is one the troupe already wears (skins, hair, cloth, metal), so the learner stands
 * in the same print as Romy, Gus and Margaux. Tones (a darker hem, a lighter strand) are mixed
 * from those colours, never picked freely.
 *
 * Some pieces are earned, never bought: each is the reward of one achievement on the server's
 * catalogue (`app/services/achievement.py`, `reward` and `REWARD_SLOTS`). `REWARDS` below mirrors
 * that table; `tests/test_avatar_contract.py` holds the two together.
 */

export type AvatarSlot =
  | 'skin'
  | 'face'
  | 'hair'
  | 'hairColor'
  | 'eyes'
  | 'eyeColor'
  | 'brows'
  | 'beard'
  | 'glasses'
  | 'hat'
  | 'hatColor'
  | 'top'
  | 'topColor'
  | 'neck'
  | 'wrist'
  | 'ears'
  | 'pin';

export type AvatarToggle = 'freckles' | 'blush' | 'lashes';

export interface AvatarConfig {
  v: 1;
  skin: string;
  face: string;
  freckles: boolean;
  blush: boolean;
  hair: string;
  hairColor: string;
  eyes: string;
  eyeColor: string;
  brows: string;
  lashes: boolean;
  beard: string;
  glasses: string;
  hat: string;
  hatColor: string;
  top: string;
  topColor: string;
  neck: string;
  wrist: string;
  ears: string;
  pin: string;
}

/* ------------------------------------------------------------------------------------------ */
/* Colours                                                                                      */

export interface SkinTone {
  skin: string;
  /** nose, hand rims, the jaw's shadow */
  shade: string;
  /** cheeks when `blush` is on */
  cheek: string;
}

/** Light to deep. All but the deepest are the troupe's own (named in the comment). */
export const SKINS: Record<string, SkinTone> = {
  s1: { skin: '#ecbfa0', shade: '#c9937a', cheek: '#e9a48a' }, // Odile
  s2: { skin: '#ecb896', shade: '#d49a76', cheek: '#f1a98f' }, // Romy
  s3: { skin: '#e3a98a', shade: '#c0846a', cheek: '#e9a48a' }, // M. Marchand
  s4: { skin: '#e0a985', shade: '#cf956f', cheek: '#e9a48a' }, // Gus
  s5: { skin: '#d8a07a', shade: '#b47d58', cheek: '#e5604a' }, // Camille
  s6: { skin: '#cf946a', shade: '#a96f47', cheek: '#e5604a' }, // Margaux
  s7: { skin: '#c98a62', shade: '#a5683f', cheek: '#d8742a' }, // Lila
  s8: { skin: '#9a6643', shade: '#774a2c', cheek: '#b9755a' }, // Marin
  s9: { skin: '#774a2c', shade: '#5a3a22', cheek: '#9a6643' }, // Marin's shade, a step deeper
};

export interface HairColour {
  hair: string;
  /** a strand of light on the hair */
  light: string;
  /** brows and beard */
  brow: string;
}

export const HAIR_COLOURS: Record<string, HairColour> = {
  noir: { hair: '#1c1611', light: '#3d3832', brow: '#1c1611' },
  brun: { hair: '#2a1a12', light: '#5a3a26', brow: '#2a1a12' },
  chatain: { hair: '#4a2e1a', light: '#6b4428', brow: '#4a2e1a' },
  noisette: { hair: '#8a5a32', light: '#b07a4e', brow: '#6b4428' },
  auburn: { hair: '#8f5534', light: '#b9755a', brow: '#774a2c' },
  roux: { hair: '#d8742a', light: '#f0a050', brow: '#b07a4e' },
  dore: { hair: '#c49a0a', light: '#f3c318', brow: '#a7830a' },
  blond: { hair: '#d6c4a0', light: '#ecdfc3', brow: '#b07a4e' },
  gris: { hair: '#a59e8f', light: '#c9c2b2', brow: '#8a8476' },
  blanc: { hair: '#dcd6c8', light: '#ece7db', brow: '#a59e8f' },
  bleu: { hair: '#1d3a8a', light: '#2c4fae', brow: '#14285f' },
  rouge: { hair: '#d8321a', light: '#e5604a', brow: '#9c2411' },
  vert: { hair: '#2c6a5d', light: '#5d6e35', brow: '#1f4f45' },
  rose: { hair: '#f07f86', light: '#f0c3a6', brow: '#b9755a' },
};

/** Irises. */
export const EYE_COLOURS: Record<string, string> = {
  sombres: '#2a1a12',
  bruns: '#6b4428',
  noisette: '#a7830a',
  verts: '#2c6a5d',
  bleus: '#3b5f9e',
  gris: '#6f6857',
};

/** Cloth: hats and tops share it. */
export const FABRICS: Record<string, string> = {
  marine: '#14285f',
  bleu: '#1d3a8a',
  ciel: '#7f9bd0',
  rouge: '#d8321a',
  bordeaux: '#9c2411',
  vert: '#2c6a5d',
  olive: '#5d6e35',
  moutarde: '#c49a0a',
  jaune: '#f3c318',
  rose: '#f07f86',
  brun: '#8a5a32',
  pierre: '#a59e8f',
  creme: '#e9e4d8',
  noir: '#1f1b16',
};

/* ------------------------------------------------------------------------------------------ */
/* Parts                                                                                        */

export const FACE_SHAPES = ['ovale', 'rond', 'carre'] as const;
export const HAIR_STYLES = [
  'court',
  'rase',
  'meche',
  'boucles',
  'afro',
  'carre',
  'mi_long',
  'long',
  'queue',
  'chignon',
  'tresses',
  'chauve',
] as const;
export const EYE_SHAPES = ['ronds', 'amande', 'petits'] as const;
export const BROW_STYLES = ['fins', 'naturels', 'epais'] as const;
export const BEARDS = ['aucune', 'trois_jours', 'moustache', 'bouc', 'courte', 'pleine'] as const;
export const GLASSES = ['aucunes', 'rondes', 'carrees', 'grandes', 'soleil'] as const;
export const HATS = ['aucun', 'beret', 'bonnet', 'casquette', 'bob', 'canotier'] as const;
export const TOPS = ['pull', 'tshirt', 'chemise', 'veste', 'sweat', 'manteau', 'mariniere'] as const;
export const NECKS = ['aucun', 'echarpe', 'foulard', 'collier_cle', 'badge_presse'] as const;
export const WRISTS = ['aucun', 'jonc', 'montre', 'bracelet'] as const;
export const EARS = ['aucunes', 'anneaux', 'perles', 'crayon', 'boucles_or'] as const;
export const PINS = ['aucun', 'fleur', 'pins_atelier'] as const;

/** Every choice a slot offers, in the editor's order. */
export const SLOT_OPTIONS: Record<AvatarSlot, readonly string[]> = {
  skin: Object.keys(SKINS),
  face: FACE_SHAPES,
  hair: HAIR_STYLES,
  hairColor: Object.keys(HAIR_COLOURS),
  eyes: EYE_SHAPES,
  eyeColor: Object.keys(EYE_COLOURS),
  brows: BROW_STYLES,
  beard: BEARDS,
  glasses: GLASSES,
  hat: HATS,
  hatColor: Object.keys(FABRICS),
  top: TOPS,
  topColor: Object.keys(FABRICS),
  neck: NECKS,
  wrist: WRISTS,
  ears: EARS,
  pin: PINS,
};

export const AVATAR_SLOTS = Object.keys(SLOT_OPTIONS) as AvatarSlot[];
export const AVATAR_TOGGLES: readonly AvatarToggle[] = ['freckles', 'blush', 'lashes'];

/* ------------------------------------------------------------------------------------------ */
/* Earned pieces                                                                                */

export interface Reward {
  slot: AvatarSlot;
  /** the achievement on the server's catalogue that unlocks it */
  achievement: string;
}

/** Mirror of the server's `REWARD_SLOTS` and each achievement's `reward`. */
export const REWARDS: Record<string, Reward> = {
  pins_atelier: { slot: 'pin', achievement: 'first_scene' },
  montre: { slot: 'wrist', achievement: 'session_streak_3' },
  soleil: { slot: 'glasses', achievement: 'session_streak_7' },
  canotier: { slot: 'hat', achievement: 'session_streak_30' },
  crayon: { slot: 'ears', achievement: 'first_letter' },
  foulard: { slot: 'neck', achievement: 'helps_10' },
  bracelet: { slot: 'wrist', achievement: 'helps_50' },
  boucles_or: { slot: 'ears', achievement: 'helps_100' },
  mariniere: { slot: 'top', achievement: 'words_kept_50' },
  collier_cle: { slot: 'neck', achievement: 'first_chapter' },
  badge_presse: { slot: 'neck', achievement: 'scenes_10' },
};

/** Whether `value` in `slot` is an earned piece the learner does not have yet. */
export function isLocked(slot: AvatarSlot, value: string, unlocked: Iterable<string> = []): boolean {
  const reward = REWARDS[value];
  if (!reward || reward.slot !== slot) return false;
  for (const item of Array.from(unlocked)) {
    if (item === value) return false;
  }
  return true;
}

/* ------------------------------------------------------------------------------------------ */
/* Records                                                                                      */

/** A first character: neutral, warm, wearing the troupe's navy. */
export const DEFAULT_AVATAR: AvatarConfig = {
  v: 1,
  skin: 's3',
  face: 'ovale',
  freckles: false,
  blush: true,
  hair: 'court',
  hairColor: 'chatain',
  eyes: 'ronds',
  eyeColor: 'bruns',
  brows: 'naturels',
  lashes: false,
  beard: 'aucune',
  glasses: 'aucunes',
  hat: 'aucun',
  hatColor: 'rouge',
  top: 'pull',
  topColor: 'marine',
  neck: 'aucun',
  wrist: 'aucun',
  ears: 'aucunes',
  pin: 'aucun',
};

const TOGGLE_DEFAULTS: Record<AvatarToggle, boolean> = { freckles: false, blush: true, lashes: false };

/**
 * A stored or pasted record made safe to draw: unknown keys dropped, unknown or missing values
 * replaced by the default, and earned pieces the learner does not hold taken off. Never throws.
 */
export function normalizeAvatar(raw: unknown, unlocked?: Iterable<string>): AvatarConfig {
  const source = raw && typeof raw === 'object' && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {};
  const held = unlocked ? Array.from(unlocked) : null;
  const out = { ...DEFAULT_AVATAR } as AvatarConfig & Record<string, unknown>;
  AVATAR_SLOTS.forEach((slot) => {
    const value = source[slot];
    if (typeof value !== 'string' || SLOT_OPTIONS[slot].indexOf(value) < 0) return;
    if (held && isLocked(slot, value, held)) return;
    out[slot] = value;
  });
  AVATAR_TOGGLES.forEach((key) => {
    out[key] = typeof source[key] === 'boolean' ? (source[key] as boolean) : TOGGLE_DEFAULTS[key];
  });
  return out as AvatarConfig;
}

/** A stored record, or null when the learner has none (or it is not a record at all). */
export function readAvatar(raw: unknown): AvatarConfig | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  return normalizeAvatar(raw);
}

/** Slots `randomAvatar` leaves bare most of the time, so a roll rarely looks like a costume. */
const OFTEN_BARE: Partial<Record<AvatarSlot, number>> = {
  beard: 0.6,
  glasses: 0.65,
  hat: 0.6,
  neck: 0.6,
  wrist: 0.7,
  ears: 0.6,
  pin: 0.75,
};

/**
 * A character at random, for the dice: every slot from what the learner may wear (free pieces
 * and the ones they earned). `rand` returns [0, 1), so tests can pass their own dice.
 */
export function randomAvatar(rand: () => number = Math.random, unlocked: Iterable<string> = []): AvatarConfig {
  const held = Array.from(unlocked);
  const pick = <T,>(list: readonly T[]): T => list[Math.min(list.length - 1, Math.floor(rand() * list.length))];
  const out = { ...DEFAULT_AVATAR } as AvatarConfig & Record<string, unknown>;
  AVATAR_SLOTS.forEach((slot) => {
    const open = SLOT_OPTIONS[slot].filter((value) => !isLocked(slot, value, held));
    const bare = OFTEN_BARE[slot];
    if (bare !== undefined && rand() < bare) {
      out[slot] = SLOT_OPTIONS[slot][0];
      return;
    }
    out[slot] = pick(open);
  });
  out.freckles = rand() < 0.25;
  out.blush = rand() < 0.6;
  out.lashes = rand() < 0.4;
  return out as AvatarConfig;
}

/** Two records draw the same character. */
export function sameAvatar(a: AvatarConfig | null, b: AvatarConfig | null): boolean {
  if (!a || !b) return a === b;
  return (
    AVATAR_SLOTS.every((slot) => a[slot] === b[slot]) && AVATAR_TOGGLES.every((key) => a[key] === b[key])
  );
}

/* ------------------------------------------------------------------------------------------ */
/* Tones                                                                                        */

function channels(hex: string): [number, number, number] {
  const h = hex.replace('#', '');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

function hex2(n: number): string {
  const v = Math.max(0, Math.min(255, Math.round(n)));
  return (v < 16 ? '0' : '') + v.toString(16);
}

/** `a` moved toward `b` by `t` (0 = a, 1 = b). */
export function mix(a: string, b: string, t: number): string {
  const x = channels(a);
  const y = channels(b);
  return `#${hex2(x[0] + (y[0] - x[0]) * t)}${hex2(x[1] + (y[1] - x[1]) * t)}${hex2(x[2] + (y[2] - x[2]) * t)}`;
}

/** A darker tone of a colour, toward the troupe's ink. */
export function deeper(colour: string, t = 0.28): string {
  return mix(colour, '#14110d', t);
}

/** A lighter tone of a colour, toward the paper. */
export function lighter(colour: string, t = 0.3): string {
  return mix(colour, '#f8f3e8', t);
}

/** Whether ink or paper reads better on a colour (stripes, a badge's letters). */
export function isPale(colour: string): boolean {
  const [r, g, b] = channels(colour);
  return 0.299 * r + 0.587 * g + 0.114 * b > 165;
}

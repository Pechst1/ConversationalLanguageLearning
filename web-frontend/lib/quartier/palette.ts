/**
 * Le Quartier · the inks and the light.
 *
 * The quarter is printed, not photographed. Every surface is one of the house inks
 * (`docs/story/season-1/10-lieux-et-images.md`: paper, ink, cobalt, vermilion, sunflower,
 * deep green, ochre) or one of them mixed with paper, and light is a choice of second ink for
 * the shadows, the way a screen print darkens with a blue pass rather than with grey.
 *
 * Colours are display values. The engine never converts them, so the vermilion of the neon is
 * #D8321A on screen before grain and lines are laid over it.
 */

export type Hex = number;

export const INKS = {
  paper: 0xf1ece1,
  card: 0xf8f3e8,
  ink: 0x14110d,
  cobalt: 0x1d3a8a,
  vermilion: 0xd8321a,
  sunflower: 0xf3c318,
  green: 0x2c6a5d,
  ochre: 0xc2890f,
} as const;

/** `a` toward `b` by `t` (0 = a, 1 = b), per channel, as a new hex. */
export function mix(a: Hex, b: Hex, t: number): Hex {
  const ch = (h: Hex, s: number) => (h >> s) & 255;
  const m = (s: number) => Math.round(ch(a, s) + (ch(b, s) - ch(a, s)) * t);
  return (m(16) << 16) | (m(8) << 8) | m(0);
}

export function rgb(h: Hex): [number, number, number] {
  return [((h >> 16) & 255) / 255, ((h >> 8) & 255) / 255, (h & 255) / 255];
}

export function css(h: Hex): string {
  return `#${h.toString(16).padStart(6, '0')}`;
}

const { paper, card, ink, cobalt, vermilion, sunflower, green, ochre } = INKS;

/** The materials of the quarter, each a named mix of the inks. */
export const TONES = {
  stone: mix(paper, ochre, 0.1),
  stoneLight: mix(card, ochre, 0.04),
  stoneShade: mix(paper, ochre, 0.24),
  stoneGround: mix(paper, ochre, 0.18),
  partyWall: mix(paper, ochre, 0.32),
  zinc: mix(cobalt, paper, 0.5),
  zincDark: mix(cobalt, ink, 0.2),
  chimney: mix(ochre, vermilion, 0.35),
  pot: mix(vermilion, ochre, 0.4),
  pane: mix(cobalt, ink, 0.55),
  paneLit: mix(sunflower, card, 0.15),
  curtain: card,
  shutter: mix(cobalt, paper, 0.62),
  iron: mix(green, ink, 0.45),
  ironLight: green,
  pavement: mix(paper, ink, 0.1),
  curb: mix(paper, ink, 0.2),
  asphalt: mix(mix(ink, cobalt, 0.35), paper, 0.2),
  quayStone: mix(paper, ochre, 0.28),
  quayWall: mix(paper, ochre, 0.38),
  water: mix(green, ink, 0.3),
  bark: mix(paper, green, 0.28),
  barkDark: mix(green, paper, 0.25),
  leafSun: sunflower,
  leafOchre: ochre,
  leafRust: mix(ochre, vermilion, 0.3),
  leafGreen: mix(green, sunflower, 0.25),
  wood: mix(ochre, ink, 0.35),
  woodLight: mix(ochre, paper, 0.25),
  brass: 0xc49a0a,
  oxblood: mix(vermilion, ink, 0.42),
  zincTop: mix(paper, cobalt, 0.18),
  /** the bar's top: worn zinc, a cool grey that stays grey under the amber globes */
  pewter: mix(mix(paper, cobalt, 0.38), ink, 0.15),
  marble: mix(card, ink, 0.04),
  neon: vermilion,
  glass: mix(cobalt, paper, 0.7),
  wainscot: green,
} as const;

/** The brand inks in the order the print pass may pull toward. */
export const PRINT_INKS: Hex[] = [paper, ink, cobalt, vermilion, sunflower, green, ochre, card];

export type AmbianceId = 'nuit' | 'matin';

export interface Ambiance {
  id: AmbianceId;
  label: string;
  /** sky gradient, top then horizon; fog melts into the horizon */
  skyTop: Hex;
  skyHorizon: Hex;
  fogNear: number;
  fogFar: number;
  /** where the light comes from (normalised by the engine) */
  sunDir: [number, number, number];
  /** multipliers on an ink for the lit, the middle and the shadow band */
  sun: [number, number, number];
  shade: [number, number, number];
  /** sky light added from above */
  ambient: [number, number, number];
  /** 1 lights the windows, the lamps and the neon */
  night: number;
  rain: boolean;
  /** strength of the lamps' pools */
  lamp: [number, number, number];
  /** colour of a lit window */
  window: Hex;
}

export const AMBIANCES: Record<AmbianceId, Ambiance> = {
  // T1 opens here: «Paris. Le 11 novembre. Il pleut.» Cobalt night, the red neon in the wet.
  nuit: {
    id: 'nuit',
    label: 'Nuit · pluie',
    skyTop: mix(cobalt, ink, 0.62),
    skyHorizon: mix(cobalt, ink, 0.2),
    fogNear: 26,
    fogFar: 150,
    sunDir: [-0.35, 0.8, 0.45],
    sun: [0.36, 0.42, 0.74],
    shade: [0.16, 0.2, 0.44],
    ambient: [0.03, 0.04, 0.09],
    night: 1,
    rain: true,
    lamp: [1.05, 0.78, 0.34],
    window: mix(sunflower, card, 0.12),
  },
  // Morning on the quai: sunflower light off the canal, long cobalt shadows.
  matin: {
    id: 'matin',
    label: 'Matin',
    skyTop: mix(cobalt, paper, 0.58),
    skyHorizon: mix(paper, sunflower, 0.12),
    fogNear: 60,
    fogFar: 260,
    sunDir: [0.55, 0.62, -0.42],
    sun: [1.04, 1.0, 0.92],
    shade: [0.62, 0.66, 0.86],
    ambient: [0.02, 0.02, 0.03],
    night: 0,
    rain: false,
    lamp: [0, 0, 0],
    window: mix(sunflower, card, 0.12),
  },
};

/**
 * WP-143 «One stage, one light» · the light and the colour of a plate, read once from
 * a downscaled copy of it, so the drawn cast stands in the same light as the painting
 * behind it (finding C-6).
 *
 *   samplePalette(pixels)   the plate's palette: mean, highlight and shadow tones, how
 *                           saturated and how textured it is, and where its light comes
 *                           from (the centroid of its brightest pixels).
 *   gradeFromPalette(p)     what the stage does with it: a per-channel lift/gain that
 *                           pulls the rigs' ink toward the plate's shadow and their paper
 *                           toward its highlight, a saturation to the plate's, a rim light
 *                           in the plate's highlight on the lit side, a cast shadow in its
 *                           shadow tone on the other, and a grain as strong as its texture.
 *   usePlateGrade(src)      the browser side: draws the plate once into a 32×24 canvas,
 *                           derives the grade, caches it per URL (memory and
 *                           sessionStorage). A plate the canvas may not read (another
 *                           origin without CORS) gets NEUTRAL_GRADE.
 *
 * No colour here is a token: every colour comes out of the plate, and the neutral grade
 * uses only the rigs' own ink and paper (rig-kit's INK, the paper #f8f3e8 the rigs draw).
 */
import { useEffect, useState } from 'react';

export type Rgb = [number, number, number];

export type PlatePalette = {
  mean: Rgb;
  /** mean of the brightest tenth of the pixels */
  highlight: Rgb;
  /** mean of the darkest tenth of the pixels */
  shadow: Rgb;
  /** mean chroma (max − min channel), 0–1 */
  saturation: number;
  /** mean absolute luminance step between neighbours, 0–1: how much grain the plate has */
  texture: number;
  /** where the light comes from: the brightest pixels' centroid, −1 (left/top) to 1 (right/bottom) */
  light: { x: number; y: number };
};

export type StageGrade = {
  /** per channel: out = in × slope + intercept (feComponentTransfer, linear) */
  slope: Rgb;
  intercept: Rgb;
  /** feColorMatrix saturate value */
  saturate: number;
  /** the side the light comes from: −1 left, 1 right */
  side: -1 | 1;
  /** the light's height: 0 level, 1 straight above */
  height: number;
  rim: string;
  rimOpacity: number;
  shadow: string;
  shadowOpacity: number;
  /** opacity of the paper grain laid over the rigs */
  grain: number;
  /** false when nothing was read from the plate */
  sampled: boolean;
};

/** The rigs' own ink and paper (rig-kit INK, the rigs' #f8f3e8): the grade when the plate is unreadable. */
const INK: Rgb = [20, 17, 13];
const PAPER: Rgb = [248, 243, 232];

/** How far the rigs are pulled into the plate's tones (0: not at all, 1: a duotone). */
const PULL = 0.26;
/** How much of the plate's mean colour washes over the rigs. */
const AMBIENT = 0.14;

function luminance([r, g, b]: Rgb): number {
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

function round(value: number, places = 3): number {
  const k = 10 ** places;
  return Math.round(value * k) / k;
}

export function hex([r, g, b]: Rgb): string {
  const part = (v: number) => clamp(Math.round(v), 0, 255).toString(16).padStart(2, '0');
  return `#${part(r)}${part(g)}${part(b)}`;
}

function mix(a: Rgb, b: Rgb, t: number): Rgb {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

function meanOf(pixels: Rgb[]): Rgb {
  if (!pixels.length) return [128, 128, 128];
  const sum = pixels.reduce<Rgb>((acc, p) => [acc[0] + p[0], acc[1] + p[1], acc[2] + p[2]], [0, 0, 0]);
  return [sum[0] / pixels.length, sum[1] / pixels.length, sum[2] / pixels.length];
}

/**
 * The palette of an RGBA pixel buffer (`ImageData.data`), `width` × `height`.
 * Transparent pixels are skipped.
 */
export function samplePalette(data: ArrayLike<number>, width: number, height: number): PlatePalette {
  const pixels: Array<{ c: Rgb; l: number; x: number; y: number }> = [];
  const lum: number[] = new Array(width * height).fill(NaN);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const i = (y * width + x) * 4;
      if ((data[i + 3] ?? 255) < 16) continue;
      const c: Rgb = [data[i], data[i + 1], data[i + 2]];
      const l = luminance(c);
      lum[y * width + x] = l;
      pixels.push({ c, l, x, y });
    }
  }
  if (!pixels.length) {
    return { mean: [128, 128, 128], highlight: PAPER, shadow: INK, saturation: 0, texture: 0, light: { x: -0.3, y: -0.5 } };
  }
  const sorted = [...pixels].sort((a, b) => a.l - b.l);
  const tenth = Math.max(1, Math.round(sorted.length / 10));
  const dark = sorted.slice(0, tenth);
  const bright = sorted.slice(-tenth);
  const saturation =
    pixels.reduce((acc, p) => acc + (Math.max(...p.c) - Math.min(...p.c)) / 255, 0) / pixels.length;
  let steps = 0;
  let stepSum = 0;
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const here = lum[y * width + x];
      if (Number.isNaN(here)) continue;
      const right = x + 1 < width ? lum[y * width + x + 1] : NaN;
      const below = y + 1 < height ? lum[(y + 1) * width + x] : NaN;
      if (!Number.isNaN(right)) { stepSum += Math.abs(here - right); steps += 1; }
      if (!Number.isNaN(below)) { stepSum += Math.abs(here - below); steps += 1; }
    }
  }
  // The light: where the brightest pixels sit, against the frame's centre.
  const cx = (width - 1) / 2 || 1;
  const cy = (height - 1) / 2 || 1;
  const lx = bright.reduce((acc, p) => acc + (p.x - cx) / cx, 0) / bright.length;
  const ly = bright.reduce((acc, p) => acc + (p.y - cy) / cy, 0) / bright.length;
  return {
    mean: meanOf(pixels.map((p) => p.c)),
    highlight: meanOf(bright.map((p) => p.c)),
    shadow: meanOf(dark.map((p) => p.c)),
    saturation: round(saturation),
    texture: round(steps ? stepSum / steps / 255 : 0),
    light: { x: round(clamp(lx, -1, 1)), y: round(clamp(ly, -1, 1)) },
  };
}

/** What the stage does with a plate's palette. Deterministic: the same palette, the same grade. */
export function gradeFromPalette(palette: PlatePalette, sampled = true): StageGrade {
  const { highlight, shadow, mean } = palette;
  const grey = luminance(mean) || 1;
  const slope = [0, 1, 2].map((c) => {
    // A duotone pull (ink → plate shadow, paper → plate highlight) …
    const pulled = 1 - PULL + (PULL * (highlight[c] - shadow[c])) / 255;
    // … under a wash of the plate's mean colour (its cast, normalised to its brightness).
    const wash = 1 - AMBIENT + (AMBIENT * mean[c]) / grey;
    return round(clamp(pulled * wash, 0.55, 1.15));
  }) as Rgb;
  const intercept = [0, 1, 2].map((c) => round(clamp((PULL * shadow[c]) / 255, 0, 0.3))) as Rgb;
  // Gouache is quieter than flat vector: the rigs come down toward the plate's saturation.
  const saturate = round(clamp(0.72 + palette.saturation * 0.6, 0.72, 1));
  // The light's side; a plate lit from the middle reads as lit from the upper left.
  const side: -1 | 1 = palette.light.x > 0.06 ? 1 : -1;
  const height = round(clamp(0.5 - palette.light.y * 0.5, 0.2, 1));
  const strength = clamp(Math.abs(palette.light.x) * 1.6, 0.25, 1);
  const contrast = clamp((luminance(highlight) - luminance(shadow)) / 255, 0.2, 1);
  return {
    slope,
    intercept,
    saturate,
    side,
    height,
    rim: hex(mix(highlight, PAPER, 0.35)),
    rimOpacity: round(clamp(0.4 + 0.45 * strength * contrast, 0.4, 0.8)),
    shadow: hex(mix(shadow, INK, 0.4)),
    shadowOpacity: round(clamp(0.22 + 0.25 * contrast, 0.22, 0.45)),
    grain: round(clamp(0.08 + palette.texture * 1.6, 0.08, 0.22)),
    sampled,
  };
}

/** The grade when the plate cannot be read: no colour shift, the light from the upper left. */
export const NEUTRAL_GRADE: StageGrade = {
  slope: [1, 1, 1],
  intercept: [0.02, 0.02, 0.02],
  saturate: 0.92,
  side: -1,
  height: 0.75,
  rim: hex(PAPER),
  rimOpacity: 0.35,
  shadow: hex(INK),
  shadowOpacity: 0.28,
  grain: 0.16,
  sampled: false,
};

/** The size the plate is drawn at for sampling: enough for a palette, nothing for a phone. */
export const SAMPLE_SIZE = { width: 32, height: 24 } as const;

const STORE_KEY = 'atelier.stageGrade.v1:';
const memory = new Map<string, StageGrade>();

function readStored(src: string): StageGrade | null {
  try {
    const raw = window.sessionStorage.getItem(STORE_KEY + src);
    if (!raw) return null;
    const grade = JSON.parse(raw) as StageGrade;
    return Array.isArray(grade.slope) && Array.isArray(grade.intercept) ? grade : null;
  } catch {
    return null;
  }
}

function store(src: string, grade: StageGrade): void {
  try {
    window.sessionStorage.setItem(STORE_KEY + src, JSON.stringify(grade));
  } catch {
    /* storage refused: the memory cache still holds it for this page */
  }
}

/** The cached grade of a plate, if this page has read it before. */
export function cachedGrade(src: string | null | undefined): StageGrade | null {
  if (!src) return null;
  return memory.get(src) ?? null;
}

/** Reads a plate into a small canvas and derives its grade; null when the browser may not. */
export function sampleImage(src: string): Promise<StageGrade | null> {
  if (typeof window === 'undefined' || typeof document === 'undefined' || typeof Image === 'undefined') {
    return Promise.resolve(null);
  }
  return new Promise((resolve) => {
    const image = new Image();
    image.crossOrigin = 'anonymous';
    image.decoding = 'async';
    image.onload = () => {
      try {
        const canvas = document.createElement('canvas');
        canvas.width = SAMPLE_SIZE.width;
        canvas.height = SAMPLE_SIZE.height;
        const context = canvas.getContext('2d', { willReadFrequently: true });
        if (!context) return resolve(null);
        context.drawImage(image, 0, 0, SAMPLE_SIZE.width, SAMPLE_SIZE.height);
        const { data } = context.getImageData(0, 0, SAMPLE_SIZE.width, SAMPLE_SIZE.height);
        resolve(gradeFromPalette(samplePalette(data, SAMPLE_SIZE.width, SAMPLE_SIZE.height)));
      } catch {
        // A tainted canvas (a plate from another origin without CORS): no grade.
        resolve(null);
      }
    };
    image.onerror = () => resolve(null);
    image.src = src;
  });
}

/**
 * The grade of the plate at `src`, read once per URL and cached; NEUTRAL_GRADE while
 * it is read (and when it cannot be), null without a plate. Renders the same on the
 * server and on the first client pass (the cache is read in an effect).
 */
export function usePlateGrade(src: string | null | undefined): StageGrade | null {
  const [grade, setGrade] = useState<StageGrade | null>(src ? NEUTRAL_GRADE : null);
  useEffect(() => {
    if (!src) {
      setGrade(null);
      return undefined;
    }
    const hit = memory.get(src) ?? readStored(src);
    if (hit) {
      memory.set(src, hit);
      setGrade(hit);
      return undefined;
    }
    setGrade(NEUTRAL_GRADE);
    let live = true;
    void sampleImage(src).then((read) => {
      const next = read ?? NEUTRAL_GRADE;
      memory.set(src, next);
      if (read) store(src, next);
      if (live) setGrade(next);
    });
    return () => {
      live = false;
    };
  }, [src]);
  return grade;
}

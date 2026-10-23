/**
 * Le Quartier · lettering.
 *
 * Every word in the street is set in the app's two faces (Garamond italic and Instrument Sans),
 * printed once into an atlas, and hung on flat cards: shop fascias, the blue enamel street
 * plaques, the posters on the Morris column, the café's slate. Diegetic text must be legible
 * (canon rule 5), so cards are printed at a generous density. The neon has a texture of its own,
 * since it lights, flickers, and one day goes out letter by letter.
 */
import { CanvasTexture, LinearFilter, LinearMipmapLinearFilter, NoColorSpace, Vector3 } from 'three';

import { CardPress } from './geo';
import { css, INKS, mix, TONES } from './palette';
import type { SignSpec } from './kit';
import { fitText } from './kit';

export const SERIF = (size: number, weight = 500) => `italic ${weight} ${size}px AtelierSerif, 'EB Garamond', Georgia, serif`;
export const SANS = (size: number, weight = 600) => `${weight} ${size}px AtelierSans, 'Instrument Sans', system-ui, sans-serif`;

/** Wait for the app's faces, so the atlas never prints in a fallback. */
export async function fontsReady(): Promise<void> {
  if (typeof document === 'undefined' || !document.fonts) return;
  try {
    await Promise.all([document.fonts.load(SERIF(40)), document.fonts.load(SANS(40)), document.fonts.load(SANS(40, 700))]);
  } catch {
    // a missing face falls back; the street stays legible
  }
}

export interface Atlas {
  texture: CanvasTexture;
  cards: CardPress;
}

/** Pack every card into one canvas (shelf packing), print it, and hang the cards. */
export function printAtlas(specs: SignSpec[], size = 2048): Atlas {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('No 2D canvas for the atlas');
  const placed = specs
    .map((s) => {
      const d = s.density ?? 150;
      return { s, w: Math.min(size, Math.ceil(s.width * d)), h: Math.min(size, Math.ceil(s.height * d)) };
    })
    .sort((a, b) => b.h - a.h);
  let x = 0;
  let y = 0;
  let row = 0;
  const pad = 4;
  const cards = new CardPress();
  for (const p of placed) {
    if (x + p.w > size) {
      x = 0;
      y += row + pad;
      row = 0;
    }
    if (y + p.h > size) break;
    ctx.save();
    ctx.translate(x, y);
    ctx.beginPath();
    ctx.rect(0, 0, p.w, p.h);
    ctx.clip();
    p.s.draw(ctx, p.w, p.h);
    ctx.restore();
    const u0 = x / size;
    const u1 = (x + p.w) / size;
    const v1 = 1 - y / size;
    const v0 = 1 - (y + p.h) / size;
    const lift = p.s.normal.clone().multiplyScalar(0.012);
    cards.card(p.s.center.clone().add(lift), p.s.normal.clone().normalize(), p.s.width, p.s.height, [u0, v0, u1, v1], p.s.tilt ?? 0, p.s.indoor);
    x += p.w + pad;
    row = Math.max(row, p.h);
  }
  const texture = new CanvasTexture(canvas);
  // the shaders work in display colour, so the canvas goes up as it is
  texture.colorSpace = NoColorSpace;
  texture.anisotropy = 4;
  texture.minFilter = LinearMipmapLinearFilter;
  texture.magFilter = LinearFilter;
  return { texture, cards };
}

/* ------------------------------------------------------------------------------------------ */
/* the pieces of lettering                                                                    */
/* ------------------------------------------------------------------------------------------ */

/** A Paris street plaque: cobalt enamel, a green frame, white capitals, the arrondissement. */
export function plaqueArt(name: string, arrondissement = '10e Arrt') {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    const r = h * 0.12;
    ctx.fillStyle = css(mix(INKS.green, INKS.ink, 0.2));
    roundRect(ctx, 0, 0, w, h, r);
    ctx.fill();
    ctx.fillStyle = css(INKS.cobalt);
    roundRect(ctx, h * 0.07, h * 0.07, w - h * 0.14, h - h * 0.14, r * 0.7);
    ctx.fill();
    ctx.strokeStyle = css(INKS.card);
    ctx.lineWidth = Math.max(1.5, h * 0.025);
    roundRect(ctx, h * 0.12, h * 0.12, w - h * 0.24, h - h * 0.24, r * 0.5);
    ctx.stroke();
    ctx.fillStyle = css(INKS.card);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const small = Math.round(h * 0.15);
    ctx.font = SANS(small, 600);
    ctx.fillText(arrondissement, w / 2, h * 0.27);
    const big = fitText(ctx, name.toUpperCase(), w * 0.84, Math.round(h * 0.34), SANS(0, 700).replace('0px', '{s}px'));
    ctx.font = SANS(big, 700);
    ctx.fillText(name.toUpperCase(), w / 2, h * 0.62);
  };
}

/** A poster for the Morris column: two inks on paper, the words large. */
export function posterArt(title: string, lines: string[], ink: number, ground: number) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = css(ground);
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = css(ink);
    ctx.fillRect(w * 0.08, h * 0.06, w * 0.84, h * 0.34);
    ctx.fillStyle = css(ground);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const s = fitText(ctx, title, w * 0.76, Math.round(w * 0.26), SERIF(0).replace('0px', '{s}px'));
    ctx.font = SERIF(s);
    ctx.fillText(title, w / 2, h * 0.23);
    ctx.fillStyle = css(INKS.ink);
    lines.forEach((line, i) => {
      const ls = fitText(ctx, line, w * 0.84, Math.round(w * 0.11), SANS(0, 600).replace('0px', '{s}px'));
      ctx.font = SANS(ls, 600);
      ctx.fillText(line, w / 2, h * (0.5 + i * 0.1));
    });
    // a torn corner and the paste's shine
    ctx.fillStyle = 'rgba(20,17,13,0.12)';
    ctx.beginPath();
    ctx.moveTo(w, h * 0.9);
    ctx.lineTo(w * 0.86, h);
    ctx.lineTo(w, h);
    ctx.fill();
  };
}

/** The café's slate by the door. */
export function slateArt(lines: string[]) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = css(mix(TONES.wood, INKS.ink, 0.45));
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = css(mix(INKS.ink, INKS.green, 0.25));
    ctx.fillRect(w * 0.06, h * 0.05, w * 0.88, h * 0.9);
    ctx.fillStyle = css(INKS.card);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    lines.forEach((line, i) => {
      const s = fitText(ctx, line, w * 0.8, Math.round(w * 0.12), SERIF(0).replace('0px', '{s}px'));
      ctx.font = i === 0 ? SERIF(Math.round(s * 1.15)) : SERIF(s);
      ctx.fillText(line, w / 2, h * (0.16 + i * (0.74 / Math.max(1, lines.length - 1))));
    });
  };
}

/** Lettering painted straight on glass or a board: one line, one colour. */
export function letteringArt(text: string, color: number, opts: { serif?: boolean; weight?: number } = {}) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = css(color);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const font = opts.serif ? SERIF(0, opts.weight ?? 500) : SANS(0, opts.weight ?? 700);
    const s = fitText(ctx, text, w * 0.94, Math.round(h * 0.72), font.replace('0px', '{s}px'));
    ctx.font = font.replace('0px', `${s}px`);
    ctx.fillText(text, w / 2, h * 0.55);
  };
}

/**
 * The neon: «MISTRAL» in vertical vermilion letters on an ink plate, both faces. Returns the
 * texture and the uv rects of each letter, so the director can put them out one by one.
 */
export function neonTexture(word = 'MISTRAL') {
  const letters = word.split('');
  const cell = 128;
  const canvas = document.createElement('canvas');
  canvas.width = cell + 32;
  canvas.height = cell * letters.length + 32;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('No 2D canvas for the neon');
  // the plate
  ctx.fillStyle = css(mix(INKS.ink, INKS.cobalt, 0.25));
  roundRect(ctx, 4, 4, canvas.width - 8, canvas.height - 8, 18);
  ctx.fill();
  ctx.strokeStyle = css(mix(INKS.ink, INKS.paper, 0.2));
  ctx.lineWidth = 4;
  roundRect(ctx, 10, 10, canvas.width - 20, canvas.height - 20, 14);
  ctx.stroke();
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  letters.forEach((ch, i) => {
    const cx = canvas.width / 2;
    const cy = 16 + cell * (i + 0.5);
    ctx.font = SANS(Math.round(cell * 0.78), 700);
    // the tube: a vermilion stroke with a pale core, as a lit tube reads
    ctx.lineJoin = 'round';
    ctx.strokeStyle = css(INKS.vermilion);
    ctx.lineWidth = 16;
    ctx.strokeText(ch, cx, cy);
    ctx.strokeStyle = css(mix(INKS.vermilion, INKS.card, 0.55));
    ctx.lineWidth = 7;
    ctx.strokeText(ch, cx, cy);
    ctx.strokeStyle = css(mix(INKS.card, INKS.sunflower, 0.15));
    ctx.lineWidth = 2.5;
    ctx.strokeText(ch, cx, cy);
  });
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = NoColorSpace;
  texture.minFilter = LinearMipmapLinearFilter;
  texture.magFilter = LinearFilter;
  texture.anisotropy = 4;
  return { texture, aspect: canvas.width / canvas.height };
}

export function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

export { Vector3 };

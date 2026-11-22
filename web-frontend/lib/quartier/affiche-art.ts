/**
 * Le Quartier · today's Papier on the Morris column, printed (`affiche-model.ts` says what it shows).
 *
 * The Papier's own front page (`styles/revue-papier.css`, `components/revue/papier/`) in the street's
 * two faces and inks: the masthead in the serif italic over a thick rule and a hairline, the
 * dateline in tracked sans capitals, red only for the kicker and the «lu» stamp.
 */
import { HEADLINE_MAX_LINES, wrapHeadline } from './affiche-model';
import type { Affiche } from './affiche-model';
import { INKS, css, mix } from './palette';
import { SANS, SERIF } from './signs';

/* -------------------------------------------------------------------------------------------- */
/* the print                                                                                    */
/* -------------------------------------------------------------------------------------------- */

const PAPER = INKS.card;
const INK = INKS.ink;
const INK_2 = mix(INKS.ink, INKS.card, 0.28);
const RED = INKS.vermilion;
const RED_DEEP = 0x9c2411; // --av2-red-deep

/** Tracked capitals, the paper's small caps: drawn letter by letter, centred on `x`. */
function tracked(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, track: number) {
  const chars = Array.from(text);
  const widths = chars.map((c) => ctx.measureText(c).width);
  const total = widths.reduce((a, b) => a + b, 0) + track * (chars.length - 1);
  let at = x - total / 2;
  ctx.textAlign = 'left';
  chars.forEach((c, i) => {
    ctx.fillText(c, at, y);
    at += widths[i] + track;
  });
  ctx.textAlign = 'center';
}

/** The largest size (≤ `max`) at which every line fits `maxW`. */
function sizeFor(ctx: CanvasRenderingContext2D, lines: string[], maxW: number, max: number, font: (s: number) => string) {
  let s = max;
  for (; s > 8; s -= 1) {
    ctx.font = font(s);
    if (lines.every((l) => ctx.measureText(l).width <= maxW)) break;
  }
  return s;
}

/** The poster, drawn on the atlas: a front page pasted on the column. */
export function afficheArt(affiche: Affiche) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    const m = w * 0.08;
    const inner = w - 2 * m;
    ctx.fillStyle = css(PAPER);
    ctx.fillRect(0, 0, w, h);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'alphabetic';

    // the masthead, as large as the sheet allows, over a thick rule and a hairline
    const mast = 'Le Papier';
    const ms = sizeFor(ctx, [mast], inner, Math.round(w * 0.24), (s) => SERIF(s, 800));
    ctx.font = SERIF(ms, 800);
    ctx.fillStyle = css(INK);
    let y = h * 0.035 + ms * 0.92;
    ctx.fillText(mast, w / 2, y);
    y += ms * 0.22;
    ctx.fillRect(m, y, inner, Math.max(3, w * 0.022));
    y += Math.max(3, w * 0.022) + w * 0.012;
    ctx.fillRect(m, y, inner, Math.max(1, w * 0.005));

    // the dateline, in tracked capitals
    const ds = Math.max(9, Math.round(w * 0.05));
    ctx.font = SANS(ds, 700);
    ctx.fillStyle = css(INK_2);
    y += ds * 1.55;
    const date = affiche.date.toUpperCase();
    const dsize = sizeFor(ctx, [date], inner * 0.94, ds, (s) => SANS(s, 700));
    ctx.font = SANS(dsize, 700);
    tracked(ctx, date, w / 2, y, dsize * 0.14);
    y += ds * 0.75;
    ctx.fillStyle = css(INK);
    ctx.fillRect(m, y, inner, Math.max(1, w * 0.005));

    // the kicker in red, then the headline, as large as the column takes it
    const ks = Math.max(9, Math.round(w * 0.056));
    ctx.font = SANS(ks, 700);
    ctx.fillStyle = css(RED);
    y += ks * 2.3;
    tracked(ctx, 'À LA UNE', w / 2, y, ks * 0.2);
    const top = y + ks * 1.1;
    const bottom = h * 0.83;
    // the headline as large as the column takes it: every measure tried, the one that reads largest
    // (at the same size, give or take, the setting with the fewest lines)
    let lines = affiche.lines.length ? affiche.lines : [''];
    let hs = 0;
    const sets: Array<{ set: string[]; size: number }> = [];
    for (let measure = 7; measure <= 22; measure++) {
      const set = wrapHeadline(affiche.headline || affiche.lines.join(' '), measure, HEADLINE_MAX_LINES);
      if (!set.length || set[set.length - 1].endsWith('…')) continue;
      const size = Math.min(
        sizeFor(ctx, set, inner, Math.round(w * 0.24), (s) => SERIF(s, 600)),
        Math.floor((bottom - top) / (set.length * 1.08)),
      );
      sets.push({ set, size });
    }
    const largest = Math.max(0, ...sets.map((x) => x.size));
    const chosen = sets
      .filter((x) => x.size >= largest * 0.97)
      .sort((a, b) => a.set.length - b.set.length || b.size - a.size)[0];
    if (chosen) {
      hs = chosen.size;
      lines = chosen.set;
    }
    if (!hs) hs = Math.min(sizeFor(ctx, lines, inner, Math.round(w * 0.24), (s) => SERIF(s, 600)), Math.floor((bottom - top) / (lines.length * 1.08)));
    ctx.font = SERIF(hs, 600);
    ctx.fillStyle = css(INK);
    const block = lines.length * hs * 1.08;
    let ly = top + Math.max(0, (bottom - top - block) / 2) + hs * 0.86;
    for (const line of lines) {
      ctx.fillText(line, w / 2, ly);
      ly += hs * 1.08;
    }

    // the foot: a hairline, the quarter's name
    ctx.fillStyle = css(INK);
    ctx.fillRect(m, h * 0.875, inner, Math.max(3, w * 0.022));
    const fs = Math.max(9, Math.round(w * 0.045));
    ctx.font = SANS(fs, 700);
    ctx.fillStyle = css(INK_2);
    tracked(ctx, 'QUAI DE VALMY', w / 2, h * 0.875 + w * 0.022 + fs * 1.6, fs * 0.16);

    // «lu»: a rubber stamp, struck askew over the headline's corner
    if (affiche.done) {
      ctx.save();
      ctx.translate(w * 0.7, h * 0.74);
      ctx.rotate(-0.21);
      const ss = Math.round(w * 0.12);
      ctx.font = SANS(ss, 700);
      const label = 'LU';
      const tw = ctx.measureText(label).width + ss * 0.35;
      const bw = tw + ss * 0.9;
      const bh = ss * 1.55;
      ctx.globalAlpha = 0.86;
      ctx.strokeStyle = css(RED_DEEP);
      ctx.lineWidth = Math.max(2, ss * 0.11);
      ctx.strokeRect(-bw / 2, -bh / 2, bw, bh);
      ctx.lineWidth = Math.max(1, ss * 0.04);
      ctx.strokeRect(-bw / 2 + ss * 0.16, -bh / 2 + ss * 0.16, bw - ss * 0.32, bh - ss * 0.32);
      ctx.fillStyle = css(RED_DEEP);
      ctx.textBaseline = 'middle';
      tracked(ctx, label, 0, ss * 0.04, ss * 0.35);
      ctx.restore();
    }

    // the paste's shine and a lifted corner, as on the column's other posters
    ctx.fillStyle = 'rgba(20,17,13,0.12)';
    ctx.beginPath();
    ctx.moveTo(w, h * 0.93);
    ctx.lineTo(w * 0.88, h);
    ctx.lineTo(w, h);
    ctx.fill();
  };
}

/** The front page of the tied bundle at the column's foot: the masthead, its rule, the columns. */
export function bundleArt() {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    const m = w * 0.06;
    ctx.fillStyle = css(PAPER);
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = css(INK);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'alphabetic';
    const s = sizeFor(ctx, ['Le Papier'], w - 2 * m, Math.round(h * 0.3), (n) => SERIF(n, 800));
    ctx.font = SERIF(s, 800);
    ctx.fillText('Le Papier', w / 2, h * 0.06 + s * 0.85);
    const ry = h * 0.06 + s * 1.05;
    ctx.fillRect(m, ry, w - 2 * m, Math.max(2, h * 0.025));
    ctx.fillRect(m, ry + h * 0.045, w - 2 * m, Math.max(1, h * 0.006));
    // the columns of type, as grey bars, in three columns under a short headline
    ctx.fillStyle = css(mix(INKS.ink, INKS.card, 0.25));
    ctx.fillRect(m, ry + h * 0.09, (w - 2 * m) * 0.72, h * 0.05);
    ctx.fillStyle = css(mix(INKS.ink, INKS.card, 0.62));
    const cw = (w - 2 * m - 2 * m * 0.6) / 3;
    for (let c = 0; c < 3; c++) {
      for (let y = ry + h * 0.19; y < h - m; y += h * 0.05) ctx.fillRect(m + c * (cw + m * 0.6), y, cw * (y > h * 0.8 && c === 2 ? 0.6 : 1), h * 0.018);
    }
  };
}

/**
 * Le Quartier · a racehorse and its jockey, drawn for the paper theatre: side on, at full
 * gallop, in the inks of the print. The jockey's silks are the runner's colours (a body, the
 * sleeves, the cap, a pattern); the saddle cloth carries the runner's number, the way the
 * stands read a race. One pose: the card bobs and rocks as it goes, like a toy theatre's horse
 * on its rod.
 */
import { INKS, css, mix } from './palette';
import type { Hex } from './palette';

export type SilkPattern = 'plain' | 'hoops' | 'sash' | 'halves' | 'stars' | 'chevrons';

export interface Silks {
  body: Hex;
  /** the pattern's colour, the sleeves', the cap's */
  second: Hex;
  pattern: SilkPattern;
  cap: Hex;
}

/** The coats a horse can have: bay, chestnut, dark bay, grey. */
export const COATS: Hex[] = [mix(INKS.ochre, INKS.ink, 0.42), mix(INKS.vermilion, INKS.ochre, 0.55), mix(INKS.ink, INKS.ochre, 0.2), mix(INKS.paper, INKS.ink, 0.32)];

/**
 * The drawing, facing right (`flip` faces it left). The jockey's legs and the saddle sit on
 * the near side, the side the stands see.
 */
export function horseArt(n: number, silks: Silks, coat: Hex, flip = false): { svg: string; aspect: number } {
  const W = 300;
  const H = 216;
  const ink = css(INKS.ink);
  const c = css(coat);
  const dark = css(mix(coat, INKS.ink, 0.45));
  const s1 = css(silks.body);
  const s2 = css(silks.second);
  const cap = css(silks.cap);
  const paper = css(INKS.card);
  const id = `s${n}`;
  // a leg: thigh to hoof, drawn twice (the ink, then the coat) so it reads as a cut-out
  const leg = (pts: Array<[number, number]>, far: boolean) => {
    const d = `M${pts.map((p) => p.join(',')).join(' L')}`;
    const fill = far ? dark : c;
    const hoof = pts[pts.length - 1];
    return `<path d="${d}" fill="none" stroke="${ink}" stroke-width="13" stroke-linecap="round" stroke-linejoin="round"/><path d="${d}" fill="none" stroke="${fill}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="${hoof[0]}" cy="${hoof[1]}" r="5.5" fill="${ink}"/>`;
  };
  const pattern = (() => {
    switch (silks.pattern) {
      case 'hoops':
        return `<g clip-path="url(#${id})"><rect x="120" y="52" width="90" height="9" fill="${s2}"/><rect x="120" y="70" width="90" height="9" fill="${s2}"/><rect x="120" y="88" width="90" height="9" fill="${s2}"/></g>`;
      case 'sash':
        return `<g clip-path="url(#${id})"><path d="M136,44 L152,44 L196,98 L180,98 Z" fill="${s2}"/></g>`;
      case 'halves':
        return `<g clip-path="url(#${id})"><rect x="164" y="40" width="50" height="60" fill="${s2}"/></g>`;
      case 'stars':
        return `<g clip-path="url(#${id})" fill="${s2}">${[
          [150, 62],
          [176, 58],
          [162, 80],
          [186, 78],
        ]
          .map(([x, y]) => `<path d="M${x},${y - 6} L${x + 2},${y - 1} L${x + 7},${y - 1} L${x + 3},${y + 2} L${x + 5},${y + 7} L${x},${y + 4} L${x - 5},${y + 7} L${x - 3},${y + 2} L${x - 7},${y - 1} L${x - 2},${y - 1} Z"/>`)
          .join('')}</g>`;
      case 'chevrons':
        return `<g clip-path="url(#${id})" fill="none" stroke="${s2}" stroke-width="7"><path d="M140,58 L160,72 L180,58 L200,72"/><path d="M140,78 L160,92 L180,78 L200,92"/></g>`;
      default:
        return '';
    }
  })();
  const body = [
    // the far legs, a shade darker
    leg(
      [
        [206, 120],
        [232, 146],
        [258, 152],
      ],
      true,
    ),
    leg(
      [
        [104, 124],
        [80, 152],
        [52, 168],
      ],
      true,
    ),
    // the tail, streaming
    `<path d="M86,96 C60,92 44,104 26,126 C46,118 60,114 80,112 Z" fill="${dark}" stroke="${ink}" stroke-width="4" stroke-linejoin="round"/>`,
    // the body, the neck and the head
    `<path d="M88,104 C88,82 112,74 150,76 C176,77 196,72 214,58 L238,30 C244,22 254,22 262,28 L290,56 C294,62 290,70 282,68 L262,62 C254,74 240,96 226,112 C214,128 190,132 160,132 C126,132 92,128 88,104 Z" fill="${c}" stroke="${ink}" stroke-width="5" stroke-linejoin="round"/>`,
    // the mane, the eye, the nostril, the bridle
    `<path d="M214,58 C224,46 232,36 240,28" fill="none" stroke="${ink}" stroke-width="7" stroke-linecap="round"/>`,
    `<circle cx="256" cy="38" r="3" fill="${ink}"/><circle cx="284" cy="60" r="2.4" fill="${ink}"/>`,
    `<path d="M246,26 L252,12 L258,28" fill="${c}" stroke="${ink}" stroke-width="3.5" stroke-linejoin="round"/>`,
    `<path d="M262,30 L282,66 M234,96 L262,58" fill="none" stroke="${ink}" stroke-width="2.4"/>`,
    // the near legs
    leg(
      [
        [196,118],
        [224, 158],
        [236, 190],
      ],
      false,
    ),
    leg(
      [
        [116, 126],
        [104, 166],
        [92, 196],
      ],
      false,
    ),
    // the saddle cloth and its number (turned back on itself when the horse faces left, so the
    // 13 never reads as a mirrored «ƐI»)
    `<path d="M126,84 L184,84 L180,122 L130,122 Z" fill="${paper}" stroke="${ink}" stroke-width="3.5" stroke-linejoin="round"/>`,
    `<g${flip ? ' transform="translate(310,0) scale(-1,1)"' : ''}><text x="155" y="114" font-family="Georgia, 'Times New Roman', serif" font-weight="700" font-size="30" text-anchor="middle" fill="${ink}">${n}</text></g>`,
    // the jockey: the boot along the horse, the silks crouched over the withers, the cap
    `<path d="M150,88 L172,98 L178,112" fill="none" stroke="${ink}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>`,
    `<path d="M150,88 L172,98 L178,112" fill="none" stroke="${paper}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>`,
    `<clipPath id="${id}"><path d="M134,72 C136,56 150,46 174,44 C192,44 206,50 210,58 C204,70 188,82 170,88 C156,92 140,88 134,72 Z"/></clipPath>`,
    `<path d="M134,72 C136,56 150,46 174,44 C192,44 206,50 210,58 C204,70 188,82 170,88 C156,92 140,88 134,72 Z" fill="${s1}"/>`,
    pattern,
    `<path d="M134,72 C136,56 150,46 174,44 C192,44 206,50 210,58 C204,70 188,82 170,88 C156,92 140,88 134,72 Z" fill="none" stroke="${ink}" stroke-width="4" stroke-linejoin="round"/>`,
    // the arm to the reins
    `<path d="M190,58 L214,72 L232,66" fill="none" stroke="${ink}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>`,
    `<path d="M190,58 L214,72 L232,66" fill="none" stroke="${s2}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>`,
    `<circle cx="214" cy="40" r="11" fill="${cap}" stroke="${ink}" stroke-width="4"/>`,
    `<path d="M220,34 L232,38" stroke="${ink}" stroke-width="4" stroke-linecap="round"/>`,
  ].join('');
  const g = flip ? `<g transform="translate(${W},0) scale(-1,1)">${body}</g>` : body;
  return { svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${g}</svg>`, aspect: W / H };
}

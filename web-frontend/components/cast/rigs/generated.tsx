/* WP-168 · a character a written season invented, drawn from parameters.
 *
 * The fixed cast is hand-drawn (one file each). A new face is built here from
 * `rig-params.ts`: a body (build, height, what they wear), a head (shape, skin, hair,
 * facial hair, glasses, one accessory) and the same computed face as everyone else
 * (`rig-kit`: eyes, brows, the visemes, the moods). Same frame (200 × 420), same crops,
 * same idle and blink, so the stage, the light and the framing rule treat it like any
 * other rig. Colours are only the cast's own (rig-params.ts). */
import React from 'react';
import { circles, dots, ellipse } from '../rig-kit';
import type { Brow, RigDef, RigMood, RigValues } from '../rig-kit';
import { COLOURS, HAIR, SKIN, hashOf, normaliseRigParams, shade } from '../rig-params';
import type { RigParams } from '../rig-params';

const INK = '#14110d';
const CREAM = '#f8f3e8';
const GOLD = '#c49a0a';

type Head = { d: string; top: number; hw: number; eye: number };

const HEADS: Record<RigParams['head'], Head> = {
  round: { d: 'M-42,-14 C-42,-48 -22,-58 0,-58 C22,-58 42,-48 42,-14 C42,22 26,48 0,50 C-26,48 -42,22 -42,-14 Z', top: -58, hw: 42, eye: 16 },
  oval: { d: 'M-38,-24 C-38,-56 -20,-64 0,-64 C20,-64 38,-56 38,-24 C38,14 22,46 0,50 C-22,46 -38,14 -38,-24 Z', top: -64, hw: 38, eye: 15 },
  long: { d: 'M-34,-28 C-34,-62 -18,-70 0,-70 C18,-70 34,-62 34,-28 C34,18 20,52 0,56 C-20,52 -34,18 -34,-28 Z', top: -70, hw: 34, eye: 13 },
  square: { d: 'M-40,-24 C-40,-54 -22,-62 0,-62 C22,-62 40,-54 40,-24 L40,16 C40,36 24,50 0,51 C-24,50 -40,36 -40,16 Z', top: -62, hw: 40, eye: 15 },
};

const HEAD_Y: Record<RigParams['height'], number> = { tall: 146, medium: 160, short: 174 };
const HALF_WIDTH: Record<RigParams['build'], number> = { slim: 40, medium: 47, broad: 56 };
const HIP = 336;

function brows(e: number): Record<RigMood, [Brow, Brow]> {
  const a = e + 9;
  const b = e - 9;
  return {
    neutre: [[-a, -21, -e, -26, -b, -22], [b, -22, e, -26, a, -21]],
    ravie: [[-a, -24, -e, -29, -b, -25], [b, -25, e, -29, a, -24]],
    surprise: [[-a, -28, -e, -34, -b, -29], [b, -29, e, -34, a, -28]],
    fachee: [[-a, -24, -e, -22, -b, -16], [b, -16, e, -22, a, -24]],
    emue: [[-a, -18, -e, -21, -b, -25], [b, -25, e, -21, a, -18]],
  };
}

function mix(a: string, b: string, t: number): string {
  const ch = (hex: string, at: number) => parseInt(hex.replace('#', '').slice(at, at + 2), 16) || 0;
  return `#${[0, 2, 4].map((at) => Math.round(ch(a, at) + (ch(b, at) - ch(a, at)) * t).toString(16).padStart(2, '0')).join('')}`;
}

/** The hair behind the head (and over the shoulders), in head coordinates. */
function hairBack(p: RigParams, h: Head): string {
  const { top: t, hw } = h;
  switch (p.hair) {
    case 'bob':
      return `M${-hw - 10},-18 C${-hw - 12},${t - 6} ${-hw * 0.5},${t - 14} 0,${t - 14} C${hw * 0.5},${t - 14} ${hw + 12},${t - 6} ${hw + 10},-18 L${hw + 12},34 Q${hw + 2},42 ${hw - 6},34 L${-hw + 6},34 Q${-hw - 2},42 ${-hw - 12},34 Z`;
    case 'long':
      return `M${-hw - 10},-16 C${-hw - 12},${t - 8} ${-hw * 0.5},${t - 14} 0,${t - 14} C${hw * 0.5},${t - 14} ${hw + 12},${t - 8} ${hw + 10},-16 C${hw + 12},30 ${hw + 8},70 ${hw + 14},96 L${hw - 10},98 C${hw - 4},70 ${hw - 2},40 ${hw - 8},10 L${-hw + 8},10 C${-hw + 2},40 ${-hw + 4},70 ${-hw + 10},98 L${-hw - 14},96 C${-hw - 8},70 ${-hw - 12},30 ${-hw - 10},-16 Z`;
    case 'wavy':
      return `M${-hw - 10},-16 C${-hw - 12},${t - 8} ${-hw * 0.5},${t - 14} 0,${t - 14} C${hw * 0.5},${t - 14} ${hw + 12},${t - 8} ${hw + 10},-16 C${hw + 18},6 ${hw + 6},22 ${hw + 14},40 C${hw + 18},52 ${hw + 4},60 ${hw - 6},52 L${-hw + 6},52 C${-hw - 4},60 ${-hw - 18},52 ${-hw - 14},40 C${-hw - 6},22 ${-hw - 18},6 ${-hw - 10},-16 Z`;
    case 'curly':
      return circles([
        [-hw + 2, t + 16, 16], [-hw * 0.45, t + 2, 18], [hw * 0.1, t - 2, 18], [hw * 0.6, t + 6, 17],
        [hw + 2, t + 22, 14], [-hw - 6, t + 38, 12], [hw + 8, t + 40, 11],
      ]);
    case 'afro':
      return circles([
        [0, t + 16, hw + 18], [-hw - 4, t + 30, 22], [hw + 4, t + 30, 22], [-hw * 0.5, t - 4, 22],
        [hw * 0.5, t - 4, 22], [-hw - 10, t + 52, 16], [hw + 10, t + 52, 16],
      ]);
    case 'bun':
      return circles([[0, t - 12, 16]]);
    case 'ponytail':
      return `M${hw - 8},${t + 12} C${hw + 18},${t + 10} ${hw + 22},${t + 46} ${hw + 16},70 C${hw + 12},78 ${hw + 4},76 ${hw + 6},66 C${hw + 10},40 ${hw + 2},${t + 30} ${hw - 10},${t + 24} Z`;
    case 'braids': {
      const plaits: Array<[number, number, number]> = [];
      for (let y = 6; y <= 84; y += 13) {
        plaits.push([-hw - 6, y, 6.5], [hw + 6, y, 6.5]);
      }
      return circles(plaits);
    }
    case 'locs': {
      // Rounded strands that fall from the crown and sway a little, longer at the back.
      let d = '';
      const xs = [-hw - 9, -hw - 2, -hw * 0.6, hw * 0.6, hw + 2, hw + 9];
      xs.forEach((x, index) => {
        const end = 46 + ((index * 23) % 34);
        const sway = index % 2 ? 4 : -4;
        const r = 4.2;
        d += `M${x - r},${t + 14} C${x - r + sway},${t + 40} ${x - r - sway},${end - 30} ${x - r},${end} A${r},${r} 0 0 0 ${x + r},${end} C${x + r - sway},${end - 30} ${x + r + sway},${t + 40} ${x + r},${t + 14} Z `;
      });
      return d;
    }
    default:
      return '';
  }
}

/** The hair in front: the hairline over the forehead. */
function hairFront(p: RigParams, h: Head): string {
  const { top: t, hw } = h;
  const cap = (lift: number, depth: number) =>
    `M${-hw - 1},-14 C${-hw - 2},${t + 4} ${-hw * 0.5},${t - lift} 0,${t - lift} C${hw * 0.5},${t - lift} ${hw + 2},${t + 4} ${hw + 1},-14 C${hw - 4},${t + depth + 8} ${hw * 0.45},${t + depth} 0,${t + depth} C${-hw * 0.45},${t + depth} ${-hw + 4},${t + depth + 8} ${-hw - 1},-14 Z`;
  switch (p.hair) {
    case 'bald':
      return '';
    case 'cropped':
      return cap(3, 12);
    case 'short':
      return `M${-hw - 2},-12 C${-hw - 6},${t - 2} ${-hw * 0.5},${t - 10} 2,${t - 10} C${hw * 0.6},${t - 10} ${hw + 6},${t} ${hw + 2},-12 C${hw - 4},${t + 24} ${hw * 0.35},${t + 16} ${hw * 0.1},${t + 22} C${-hw * 0.2},${t + 30} ${-hw * 0.6},${t + 24} ${-hw - 2},-12 Z`;
    case 'bob':
      return `M${-hw - 3},-12 C${-hw - 5},${t + 2} ${-hw * 0.5},${t - 10} 0,${t - 10} C${hw * 0.5},${t - 10} ${hw + 5},${t + 2} ${hw + 3},-12 L${hw - 2},${t + 24} Q0,${t + 18} ${-hw + 2},${t + 24} Z`;
    case 'long':
    case 'wavy':
      return `M0,${t - 10} C${-hw * 0.6},${t - 10} ${-hw - 5},${t + 4} ${-hw - 4},-4 L${-hw + 4},-8 C${-hw + 6},${t + 24} ${-hw * 0.4},${t + 12} 0,${t + 6} C${hw * 0.4},${t + 12} ${hw - 6},${t + 24} ${hw - 4},-8 L${hw + 4},-4 C${hw + 5},${t + 4} ${hw * 0.6},${t - 10} 0,${t - 10} Z`;
    case 'curly':
      return circles([
        [-hw + 6, t + 18, 10], [-hw * 0.4, t + 10, 11], [hw * 0.05, t + 8, 11], [hw * 0.45, t + 12, 10], [hw - 4, t + 20, 9],
      ]);
    case 'afro':
      return circles([[-hw + 4, t + 18, 11], [-hw * 0.35, t + 10, 12], [hw * 0.2, t + 10, 12], [hw - 4, t + 18, 11]]);
    case 'bun':
    case 'ponytail':
    case 'braids':
      return cap(6, 10);
    case 'locs':
      return cap(8, 16);
    default:
      return cap(4, 12);
  }
}

function hairHighlights(p: RigParams, h: Head): string {
  if (p.hair === 'bald') return `M${-h.hw * 0.5},${h.top + 10} Q${-h.hw * 0.2},${h.top + 2} ${h.hw * 0.15},${h.top + 4}`;
  if (p.hair === 'curly' || p.hair === 'afro') return '';
  return `M${-h.hw * 0.55},${h.top + 4} Q${-h.hw * 0.2},${h.top - 4} ${h.hw * 0.2},${h.top - 2}`;
}

function beard(h: Head): string {
  const hw = h.hw;
  return `M${-hw},-2 C${-hw - 2},32 -24,58 0,60 C24,58 ${hw + 2},32 ${hw},-2 C${hw - 6},12 ${hw - 14},18 16,18 C8,14 -8,14 -16,18 C${-hw + 14},18 ${-hw + 6},12 ${-hw},-2 Z`;
}

const STUBBLE = dots(
  [[-24, 22], [-18, 30], [-11, 36], [-4, 40], [4, 40], [11, 36], [18, 30], [24, 22], [-14, 24], [14, 24], [-7, 44], [7, 44], [0, 46]],
  1,
);

const MOUSTACHE = 'M-15,22 C-9,16 -3,18 0,20 C3,18 9,16 15,22 C9,25 3,23 0,22 C-3,23 -9,25 -15,22 Z';

/** A top in this build, between the shoulders `s` and the hip; ends where it hangs to. */
function torso(w: number, s: number, hem: number, flare = 0): string {
  const L = 100 - w;
  const R = 100 + w;
  return `M${L + 4},${s + 18} Q${L + 6},${s} ${L + 24},${s - 2} L${R - 24},${s - 2} Q${R - 6},${s} ${R - 4},${s + 18} L${R + 2 + flare},${hem - 8} Q${R + 2 + flare},${hem + 4} ${R - 10 + flare},${hem + 4} L${L + 10 - flare},${hem + 4} Q${L - 2 - flare},${hem + 4} ${L - 2 - flare},${hem - 8} Z`;
}

function Body({ p, s, w }: { p: RigParams; s: number; w: number }) {
  const top = COLOURS[p.top_colour];
  const fold = shade(top, 0.22);
  const bottom = p.top === 'overalls' ? top : COLOURS[p.bottom_colour];
  const shirt = p.top_colour === 'cream' ? COLOURS.stone : CREAM;
  const skin = SKIN[p.skin];
  const long = p.top === 'boubou';
  const skirt = p.top === 'dress';
  const sleeve = long ? 26 : 15;
  const L = 100 - w;
  const R = 100 + w;
  const handY = HIP - 34;
  const parts: React.ReactElement[] = [];
  parts.push(
    <path key="legs" d={`M88,${HIP - 4} L87,392 M112,${HIP - 4} L113,392`} fill="none" stroke={bottom} strokeWidth={15} strokeLinecap="round" />,
    <ellipse key="shoe-l" cx="85" cy="399" rx="12" ry="6.5" fill={INK} />,
    <ellipse key="shoe-r" cx="115" cy="399" rx="12" ry="6.5" fill={INK} />,
    <path key="neck" d={`M93,${s - 40} L107,${s - 40} L107,${s + 8} L93,${s + 8} Z`} fill={shade(skin, 0.08)} />,
  );
  if (p.top === 'overalls') {
    parts.push(<path key="shirt" d={torso(w, s, HIP)} fill={shirt} />);
    parts.push(<path key="bib" d={`M${L + 12},${s + 44} L${R - 12},${s + 44} L${R - 4},${HIP + 4} L${L + 4},${HIP + 4} Z`} fill={top} />);
    parts.push(<path key="straps" d={`M${L + 18},${s + 46} L${L + 22},${s} M${R - 18},${s + 46} L${R - 22},${s}`} fill="none" stroke={top} strokeWidth={7} strokeLinecap="round" />);
    parts.push(<path key="pocket" d={`M90,${s + 58} L110,${s + 58} L110,${s + 76} Q100,${s + 80} 90,${s + 76} Z`} fill={fold} />);
    parts.push(<circle key="b1" cx={L + 18} cy={s + 50} r="2.6" fill={GOLD} />, <circle key="b2" cx={R - 18} cy={s + 50} r="2.6" fill={GOLD} />);
  } else if (long) {
    parts.push(<path key="robe" d={`M${L - 6},${s + 22} Q${L - 4},${s} ${L + 22},${s - 2} L${R - 22},${s - 2} Q${R + 4},${s} ${R + 6},${s + 22} L${R + 18},384 Q${R + 18},392 ${R + 6},392 L${L - 6},392 Q${L - 18},392 ${L - 18},384 Z`} fill={top} />);
    parts.push(<path key="neckline" d={`M88,${s - 2} Q100,${s + 24} 112,${s - 2} M92,${s + 14} L92,${s + 70} M108,${s + 14} L108,${s + 70}`} fill="none" stroke={GOLD} strokeWidth={2.4} strokeLinecap="round" />);
    parts.push(<path key="hem" d={`M${L - 14},378 L${R + 14},378`} fill="none" stroke={fold} strokeWidth={4} />);
  } else if (skirt) {
    parts.push(<path key="dress" d={`M${L + 4},${s + 18} Q${L + 6},${s} ${L + 24},${s - 2} L${R - 24},${s - 2} Q${R - 6},${s} ${R - 4},${s + 18} L${R - 6},${HIP - 46} L${R + 14},${HIP + 34} Q${R + 14},${HIP + 40} ${R + 6},${HIP + 40} L${L - 6},${HIP + 40} Q${L - 14},${HIP + 40} ${L - 14},${HIP + 34} L${L + 6},${HIP - 46} Z`} fill={top} />);
    parts.push(<path key="neckline" d={`M86,${s - 2} Q100,${s + 22} 114,${s - 2} Z`} fill={shade(skin, 0.08)} />);
    parts.push(<path key="waist" d={`M${L + 6},${HIP - 46} L${R - 6},${HIP - 46}`} fill="none" stroke={fold} strokeWidth={5} />);
  } else {
    const hem = p.top === 'coat' ? HIP + 22 : HIP;
    parts.push(<path key="torso" d={torso(w, s, hem, p.top === 'coat' ? 6 : 0)} fill={top} />);
    if (p.top === 'coat' || p.top === 'jacket' || p.top === 'suit' || p.top === 'uniform') {
      parts.push(<path key="shirt" d={`M86,${s - 2} L100,${s + 34} L114,${s - 2} Z`} fill={shirt} />);
      parts.push(<path key="lapels" d={`M86,${s - 2} L${84 - 10},${s + 6} L98,${s + 52} L100,${s + 34} Z M114,${s - 2} L${116 + 10},${s + 6} L102,${s + 52} L100,${s + 34} Z`} fill={fold} />);
      parts.push(<circle key="b1" cx="103" cy={s + 66} r="2.6" fill={p.top === 'uniform' ? GOLD : INK} />, <circle key="b2" cx="103" cy={s + 84} r="2.6" fill={p.top === 'uniform' ? GOLD : INK} />);
      if (p.top === 'suit') {
        parts.push(<path key="tie" d={`M97,${s + 2} L103,${s + 2} L106,${s + 40} L100,${s + 48} L94,${s + 40} Z`} fill={COLOURS[p.accessory_colour]} />);
      }
      if (p.top === 'uniform') {
        parts.push(<path key="badge" d={`M${R - 26},${s + 30} L${R - 14},${s + 30} L${R - 14},${s + 44} L${R - 20},${s + 48} L${R - 26},${s + 44} Z`} fill={GOLD} />);
        parts.push(<path key="epaulettes" d={`M${L + 10},${s + 4} L${L + 28},${s} M${R - 10},${s + 4} L${R - 28},${s}`} fill="none" stroke={fold} strokeWidth={6} strokeLinecap="round" />);
      }
      if (p.top === 'coat') {
        parts.push(<path key="belt" d={`M${L},${HIP - 30} L${R},${HIP - 30}`} fill="none" stroke={fold} strokeWidth={6} />);
      }
    } else if (p.top === 'shirt') {
      parts.push(<path key="collar" d={`M88,${s - 2} L100,${s + 10} L112,${s - 2} L114,${s + 12} L100,${s + 14} L86,${s + 12} Z`} fill={shade(top, 0.1)} />);
      parts.push(<path key="placket" d={`M100,${s + 14} L100,${HIP}`} fill="none" stroke={fold} strokeWidth={1.8} />);
      parts.push(<circle key="b1" cx="103" cy={s + 34} r="2" fill={fold} />, <circle key="b2" cx="103" cy={s + 58} r="2" fill={fold} />);
    } else if (p.top === 'hoodie') {
      parts.push(<path key="hood" d={`M80,${s - 4} Q100,${s + 14} 120,${s - 4} L124,${s + 6} Q100,${s + 28} 76,${s + 6} Z`} fill={fold} />);
      parts.push(<path key="strings" d={`M95,${s + 12} L94,${s + 40} M105,${s + 12} L106,${s + 40}`} fill="none" stroke={CREAM} strokeWidth={2.4} strokeLinecap="round" />);
      parts.push(<path key="pocket" d={`M${L + 18},${HIP - 36} L${R - 18},${HIP - 36} L${R - 10},${HIP - 6} L${L + 10},${HIP - 6} Z`} fill={fold} />);
    } else {
      // jumper and apron: a crew neck and a ribbed hem
      parts.push(<path key="crew" d={`M86,${s - 2} Q100,${s + 12} 114,${s - 2}`} fill="none" stroke={fold} strokeWidth={5} />);
      parts.push(<path key="rib" d={`M${L},${HIP - 4} L${R},${HIP - 4}`} fill="none" stroke={fold} strokeWidth={7} />);
      if (p.top === 'apron') {
        const apron = p.top_colour === 'cream' || p.top_colour === 'stone' ? COLOURS.ink : CREAM;
        parts.push(<path key="apron" d={`M84,${s + 26} L116,${s + 26} L118,${HIP - 34} L${R - 6},${HIP - 34} L${R - 2},376 L${L + 2},376 L${L + 6},${HIP - 34} L82,${HIP - 34} Z`} fill={apron} />);
        parts.push(<path key="strap" d={`M86,${s + 26} Q100,${s - 4} 114,${s + 26}`} fill="none" stroke={apron} strokeWidth={3} />);
      }
    }
  }
  parts.push(
    <path key="arm-l" d={`M${L + 8},${s + 16} Q${L - 12},${s + 60} ${L - 2},${handY}`} fill="none" stroke={top} strokeWidth={sleeve} strokeLinecap="round" />,
    <path key="arm-r" d={`M${R - 8},${s + 16} Q${R + 12},${s + 60} ${R + 2},${handY}`} fill="none" stroke={top} strokeWidth={sleeve} strokeLinecap="round" />,
    <circle key="hand-l" cx={L - 2} cy={handY + 6} r="8.5" fill={skin} />,
    <circle key="hand-r" cx={R + 2} cy={handY + 6} r="8.5" fill={skin} />,
  );
  const accent = COLOURS[p.accessory_colour];
  if (p.accessory === 'scarf') {
    parts.push(<path key="scarf" d={`M76,${s - 4} Q100,${s + 12} 124,${s - 4} L126,${s + 8} Q100,${s + 26} 74,${s + 8} Z`} fill={accent} />);
    parts.push(<path key="scarf-end" d={`M108,${s + 10} L118,${s + 62} L106,${s + 64} L98,${s + 14} Z`} fill={shade(accent, 0.15)} />);
  } else if (p.accessory === 'necklace') {
    parts.push(<path key="necklace" d={`M84,${s + 2} Q100,${s + 26} 116,${s + 2}`} fill="none" stroke={GOLD} strokeWidth={2.4} />);
    parts.push(<circle key="pendant" cx="100" cy={s + 16} r="3.6" fill={accent} />);
  }
  return <>{parts}</>;
}

function makeArt(p: RigParams, h: Head, s: number, w: number) {
  const skin = SKIN[p.skin];
  const lid = skin;
  const hair = HAIR[p.hair_colour];
  const nose = shade(skin, 0.16);
  const blush = mix(skin, '#d8321a', 0.18);
  const back = hairBack(p, h);
  const front = hairFront(p, h);
  const sheen = hairHighlights(p, h);
  const wrapped = p.accessory === 'headwrap';
  const accent = COLOURS[p.accessory_colour];
  const { top: t, hw, eye: e } = h;
  return function GeneratedArt({ v }: { v: RigValues }) {
    return (
      <g>
        <Body p={p} s={s} w={w} />
        <g transform={v.headT}>
          <g className="cast-rig__idle">
            {back && !(wrapped && (p.hair === 'afro' || p.hair === 'bun' || p.hair === 'curly')) ? <path d={back} fill={hair} /> : null}
            <ellipse cx={-hw - 1} cy="2" rx="7" ry="10.5" fill={skin} />
            <ellipse cx={hw + 1} cy="2" rx="7" ry="10.5" fill={skin} />
            <path d={h.d} fill={skin} />
            <ellipse cx={-e - 7} cy="13" rx="6.5" ry="3.6" fill={blush} />
            <ellipse cx={e + 7} cy="13" rx="6.5" ry="3.6" fill={blush} />
            {p.facial_hair === 'beard' ? (
              <>
                <path d={beard(h)} fill={hair} />
                <ellipse cx="0" cy="31" rx="15" ry="8.5" fill={skin} />
              </>
            ) : null}
            {p.facial_hair === 'stubble' ? <path d={STUBBLE} fill={hair} fillOpacity={0.45} /> : null}
            <path display={v.eL.sD} d={v.eL.sclera} fill="#ffffff" />
            <path display={v.eL.sD} d={v.eL.pupil} fill={INK} />
            <path display={v.eL.sD} d={v.eL.glint} fill="#ffffff" />
            <path d={v.eL.lid} fill={lid} />
            <path d={v.eL.lidLine} fill="none" stroke={INK} strokeWidth={2.6} strokeLinecap="round" />
            <path d={v.eL.arc} fill="none" stroke={INK} strokeWidth={4} strokeLinecap="round" />
            <path d={v.eL.tear} fill="#1d3a8a" />
            <path display={v.eR.sD} d={v.eR.sclera} fill="#ffffff" />
            <path display={v.eR.sD} d={v.eR.pupil} fill={INK} />
            <path display={v.eR.sD} d={v.eR.glint} fill="#ffffff" />
            <path d={v.eR.lid} fill={lid} />
            <path d={v.eR.lidLine} fill="none" stroke={INK} strokeWidth={2.6} strokeLinecap="round" />
            <path d={v.eR.arc} fill="none" stroke={INK} strokeWidth={4} strokeLinecap="round" />
            <path d={v.eR.tear} fill="#1d3a8a" />
            <path d={v.browL} fill="none" stroke={p.hair === 'bald' ? shade(skin, 0.5) : hair} strokeWidth={4.6} strokeLinecap="round" />
            <path d={v.browR} fill="none" stroke={p.hair === 'bald' ? shade(skin, 0.5) : hair} strokeWidth={4.6} strokeLinecap="round" />
            <path d="M0,-1 C3,2 5,10 4,13 C2,15.5 -2,15.5 -4,13 C-5,10 -3,2 0,-1 Z" fill={nose} />
            <g transform="translate(-3.6 4) scale(1.8)">
              <path d={v.mouthD} fill={v.mouthFill} />
              <path d={v.teethD} fill="#ffffff" />
              <path d={v.tongueD} fill="#d8321a" />
            </g>
            {p.facial_hair === 'moustache' || p.facial_hair === 'beard' ? <path d={MOUSTACHE} fill={hair} /> : null}
            {front && !wrapped ? <path d={front} fill={hair} /> : null}
            {sheen && !wrapped ? (
              <path d={sheen} fill="none" stroke={p.hair === 'bald' ? '#ffffff' : shade(hair, -0.4)} strokeOpacity={0.35} strokeWidth={2.4} strokeLinecap="round" />
            ) : null}
            {p.glasses === 'round' ? (
              <path d={`${ellipse(-e, -4, 12.5, 12.5)} ${ellipse(e, -4, 12.5, 12.5)} M${-e + 12.5},-6 Q0,-11 ${e - 12.5},-6`} fill="none" stroke={INK} strokeWidth={2.6} />
            ) : null}
            {p.glasses === 'square' ? (
              <path d={`M${-e - 13},-15 L${-e + 13},-15 L${-e + 12},7 L${-e - 12},7 Z M${e - 13},-15 L${e + 13},-15 L${e + 12},7 L${e - 12},7 Z M${-e + 13},-8 L${e - 13},-8`} fill="none" stroke={INK} strokeWidth={2.6} strokeLinejoin="round" />
            ) : null}
            {wrapped ? (
              <>
                <path d={`M${-hw - 7},-6 C${-hw - 12},${t - 26} ${hw + 12},${t - 26} ${hw + 7},-6 C${hw - 6},${t + 16} ${-hw + 6},${t + 16} ${-hw - 7},-6 Z`} fill={accent} />
                <path d={`M${-hw * 0.6},${t + 2} Q0,${t - 14} ${hw * 0.6},${t + 2}`} fill="none" stroke={shade(accent, 0.25)} strokeWidth={3} />
                <path d={circles([[8, t - 14, 11], [-6, t - 10, 8]])} fill={shade(accent, 0.12)} />
              </>
            ) : null}
            {p.accessory === 'beret' ? (
              <>
                <ellipse cx="-6" cy={t + 2} rx={hw + 6} ry="11" transform={`rotate(-8 -6 ${t + 2})`} fill={accent} />
                <path d={`M-6,${t - 9} L-4,${t - 16}`} fill="none" stroke={accent} strokeWidth={3} strokeLinecap="round" />
              </>
            ) : null}
            {p.accessory === 'cap' ? (
              <>
                <path d={`M${-hw - 2},-16 C${-hw - 2},${t - 12} ${hw + 2},${t - 12} ${hw + 2},-16 Z`} fill={accent} />
                <path d={`M${-hw * 0.2},-20 Q${hw + 20},-24 ${hw + 30},-14 Q${hw + 10},-11 ${-hw * 0.2},-14 Z`} fill={shade(accent, 0.25)} />
              </>
            ) : null}
            {p.accessory === 'earrings' ? (
              <path d={`${ellipse(-hw - 1, 15, 3.4, 3.4)} ${ellipse(hw + 1, 15, 3.4, 3.4)}`} fill="none" stroke={GOLD} strokeWidth={1.8} />
            ) : null}
          </g>
        </g>
      </g>
    );
  };
}

/** A rig for a written season's character; unknown parameters fall back to the defaults. */
export function generatedRig(id: string, name: string, raw: unknown): RigDef {
  const p = normaliseRigParams(raw);
  const h = HEADS[p.head];
  const headY = HEAD_Y[p.height];
  const s = headY + 62;
  const w = HALF_WIDTH[p.build];
  const tall = p.hair === 'afro' || p.hair === 'bun' || p.accessory === 'headwrap';
  const hash = hashOf(id);
  return {
    id,
    name,
    head: [100, headY],
    crops: {
      full: [0, 0, 200, 420],
      bust: [10, headY - 92, 180, 220],
      head: tall ? [20, headY - 108, 160, 160] : [28, headY - 96, 144, 144],
    },
    idle: { kind: p.idle, seconds: 4 + (hash % 15) / 10, amount: p.idle === 'sway' ? -2 : 1.8 },
    tilt: { neutre: 0, ravie: -3, surprise: 0, fachee: 0, emue: 3 },
    brows: brows(h.eye),
    eyeL: [-h.eye, -4],
    eyeR: [h.eye, -4],
    eye: { rx: 9.5, ry: 11, pr: 6.2 },
    mouths: { neutre: 'smile' },
    mouthSet: 'symmetric',
    Art: makeArt(p, h, s, w),
  };
}

/* WP-116 · Romy, variant C. Ported from the Claude Design canvas rig (2026-10-01).
 * WP-119 §8.3 · `hold: 'notebook'`, the first authored prop (WP-116 §12.3 tier 1): her right
 * hand leaves the camera and lifts a reporter's notebook to her chest; the camera hangs on its
 * strap in the left hand. Head, face, mouth and crops never change. */
import { circles, dots } from '../rig-kit';
import type { RigDef, RigValues } from '../rig-kit';

const FRECKLES = [[-22, 7], [-26, 10], [-18, 10], [-12, 5], [-8, 9], [-3, 4], [22, 7], [26, 10], [18, 10], [12, 5], [8, 9], [3, 4]] as const;
const FRECKLE_D = dots(FRECKLES, 1.1);
function lash(c: [number, number], side: -1 | 1): string {
  return `M${c[0] - 10.5},${c[1] - 3} Q${c[0]},${c[1] - 15} ${c[0] + 10.5},${c[1] - 3} M${c[0] + side * 10},${c[1] - 4} L${c[0] + side * 14},${c[1] - 6.5}`;
}

/**
 * The notebook, drawn about its handle point (0,0), where the hand grips it, so the rig only
 * places the handle and the tilt. Paper and ink only.
 */
export const NOTEBOOK = {
  handle: [117, 269] as [number, number],
  tilt: -8,
  /** the page in the prop's own frame: x, y, width, height */
  page: [-8, -31, 26, 33] as [number, number, number, number],
};
const NOTEBOOK_PAGE = 'M-8,-26 Q-8,-29 -5,-29 L15,-29 Q18,-29 18,-26 L18,-1 Q18,2 15,2 L-5,2 Q-8,2 -8,-1 Z';
const NOTEBOOK_BAND = 'M-8,-26 Q-8,-29 -5,-29 L15,-29 Q18,-29 18,-26 L18,-24 L-8,-24 Z';
const NOTEBOOK_COIL = circles([[-3, -29, 2], [2, -29, 2], [7, -29, 2], [12, -29, 2]]);
const NOTEBOOK_HOLES = dots([[-3, -28.6], [2, -28.6], [7, -28.6], [12, -28.6]], 0.9);
const NOTEBOOK_LINES = 'M1,-19 L14,-19 M1,-14 L15,-14 M1,-9 L10,-9';

function Notebook() {
  return (
    <g className="cast-rig__prop" data-prop="notebook" transform={`translate(${NOTEBOOK.handle[0]} ${NOTEBOOK.handle[1]}) rotate(${NOTEBOOK.tilt})`}>
      <path d={NOTEBOOK_PAGE} fill="#f8f3e8" />
      <path d={NOTEBOOK_BAND} fill="#14110d" />
      <path d={NOTEBOOK_COIL} fill="#14110d" />
      <path d={NOTEBOOK_HOLES} fill="#f8f3e8" />
      <path d={NOTEBOOK_LINES} fill="none" stroke="#14110d" strokeWidth={1.6} strokeLinecap="round" />
    </g>
  );
}

function RomyArt({ v }: { v: RigValues }) {
  const notebook = v.extra.prop === 'notebook';
  return (
    <g>
      <path d="M46,128 C40,80 70,64 100,64 C130,64 160,80 154,128 C160,160 148,180 156,200 C164,220 152,236 162,252 C150,266 128,262 118,250 L82,250 C72,262 50,266 38,252 C48,236 36,220 44,200 C52,180 40,160 46,128 Z" fill="#4a2e1a" />
      <path d="M88,340 L87,392 M112,340 L113,392" fill="none" stroke="#14285f" strokeWidth={14} strokeLinecap="round" />
      <ellipse cx="84" cy="399" rx="12" ry="6.5" fill="#14110d" />
      <ellipse cx="116" cy="399" rx="12" ry="6.5" fill="#14110d" />
      <path d="M93,192 L107,192 L107,222 L93,222 Z" fill="#ecb896" />
      <path d="M60,232 Q62,216 80,214 L120,214 Q138,216 140,232 L146,330 Q146,342 134,342 L66,342 Q54,342 54,330 Z" fill="#1f1b16" />
      <path d="M85,214 L100,250 L115,214 Z" fill="#1d3a8a" />
      <path d="M85,214 L74,220 L94,262 L100,250 Z M115,214 L126,220 L106,262 L100,250 Z" fill="#2e2924" />
      <path d="M63,250 Q60,288 64,322 M137,250 Q140,288 136,322" fill="none" stroke="#4a4640" strokeWidth={2.5} strokeLinecap="round" />
      <circle cx="106" cy="232" r="2.4" fill="#14110d" />
      <path d="M105,234 L107,234 L107,239 L105,239 Z" fill="#14110d" />
      <path d="M84,292 L89,224 M116,292 L111,224" fill="none" stroke="#14110d" strokeWidth={2} />
      <path d="M62,238 Q50,270 66,296" fill="none" stroke="#1f1b16" strokeWidth={15} strokeLinecap="round" />
      <path d="M138,238 Q150,270 134,296" fill="none" stroke="#1f1b16" strokeWidth={15} strokeLinecap="round" />
      {notebook ? (
        <path d="M66,296 Q76,304 82,306" fill="none" stroke="#2e2924" strokeWidth={13} strokeLinecap="round" />
      ) : (
        <path d="M66,296 Q76,304 82,306 M134,296 Q124,304 118,306" fill="none" stroke="#2e2924" strokeWidth={13} strokeLinecap="round" />
      )}
      <path d="M92,286 L108,286 L108,291 L92,291 Z" fill="#14110d" />
      <path d="M80,296 Q80,290 86,290 L114,290 Q120,290 120,296 L120,318 Q120,324 114,324 L86,324 Q80,324 80,318 Z" fill="#14110d" />
      <circle cx="100" cy="307" r="10" fill="#3d3832" />
      <circle cx="100" cy="307" r="6" fill="#1d3a8a" />
      <circle cx="97.6" cy="304.6" r="1.8" fill="#f8f3e8" />
      <circle className="cast-rig__tally" cx="114" cy="295.5" r="2.4" fill="#d8321a" />
      <circle cx="81" cy="309" r="8" fill="#ecb896" />
      {notebook ? (
        <>
          <path d="M134,296 Q133,281 120,272" fill="none" stroke="#2e2924" strokeWidth={13} strokeLinecap="round" />
          <Notebook />
          <circle cx={NOTEBOOK.handle[0]} cy={NOTEBOOK.handle[1]} r="8" fill="#ecb896" />
        </>
      ) : (
        <circle cx="119" cy="309" r="8" fill="#ecb896" />
      )}
      <g transform={v.headT}>
      <g className="cast-rig__idle">
      <path d="M-38,-24 C-38,-56 -20,-64 0,-64 C20,-64 38,-56 38,-24 C38,14 22,46 0,50 C-22,46 -38,14 -38,-24 Z" fill="#ecb896" />
      <ellipse cx="-22" cy="13" rx="6.5" ry="3.6" fill="#f1a98f" />
      <ellipse cx="22" cy="13" rx="6.5" ry="3.6" fill="#f1a98f" />
      <circle cx="-37" cy="12" r="3.4" fill="none" stroke="#c49a0a" strokeWidth={1.8} />
      <circle cx="37" cy="12" r="3.4" fill="none" stroke="#c49a0a" strokeWidth={1.8} />
      <path d="M0,-80 C-30,-80 -54,-60 -52,-24 C-50,4 -58,28 -52,52 C-48,66 -56,74 -54,82 L-42,80 C-44,64 -39,50 -41,30 C-43,8 -42,-14 -40,-26 Z M0,-80 C30,-80 54,-60 52,-24 C50,4 58,28 52,52 C48,66 56,74 54,82 L42,80 C44,64 39,50 41,30 C43,8 42,-14 40,-26 Z" fill="#4a2e1a" />
      <path d="M-41,6 C-44,-40 -26,-80 0,-80 C26,-80 44,-40 41,6 L36,4 C35,-16 30,-36 18,-46 C12,-50 6,-52 2,-53 L0,-57 L-2,-53 C-6,-52 -12,-50 -18,-46 C-30,-36 -35,-16 -36,4 Z" fill="#4a2e1a" />
      <path d="M-1,-56 L-1,-78" fill="none" stroke="#6b4428" strokeWidth={1.4} strokeLinecap="round" />
      <path d="M-24,-46 C-30,-38 -33,-28 -34,-16 M-47,10 C-49,26 -50,42 -48,60 M24,-46 C30,-38 33,-28 34,-16 M47,10 C49,26 50,42 48,60" fill="none" stroke="#c49a0a" strokeWidth={1.8} strokeLinecap="round" />
      <path d={v.extra.freckles} fill="#b9755a" />
      <path display={v.eL.sD} d={v.eL.sclera} fill="#ffffff" />
      <path display={v.eL.sD} d={v.eL.iris} fill="#3b5f9e" />
      <path display={v.eL.sD} d={v.eL.pupil} fill="#14110d" />
      <path display={v.eL.sD} d={v.eL.glint} fill="#ffffff" />
      <path d={v.eL.lid} fill="#ecb896" />
      <path d={v.eL.lidLine} fill="none" stroke="#14110d" strokeWidth={2.6} strokeLinecap="round" />
      <path display={v.eL.sD} d={v.extra.lashL} fill="none" stroke="#14110d" strokeWidth={2.8} strokeLinecap="round" />
      <path d={v.eL.arc} fill="none" stroke="#14110d" strokeWidth={4} strokeLinecap="round" />
      <path d={v.eL.tear} fill="#1d3a8a" />
      <path display={v.eR.sD} d={v.eR.sclera} fill="#ffffff" />
      <path display={v.eR.sD} d={v.eR.iris} fill="#3b5f9e" />
      <path display={v.eR.sD} d={v.eR.pupil} fill="#14110d" />
      <path display={v.eR.sD} d={v.eR.glint} fill="#ffffff" />
      <path d={v.eR.lid} fill="#ecb896" />
      <path d={v.eR.lidLine} fill="none" stroke="#14110d" strokeWidth={2.6} strokeLinecap="round" />
      <path display={v.eR.sD} d={v.extra.lashR} fill="none" stroke="#14110d" strokeWidth={2.8} strokeLinecap="round" />
      <path d={v.eR.arc} fill="none" stroke="#14110d" strokeWidth={4} strokeLinecap="round" />
      <path d={v.browL} fill="none" stroke="#5a3a22" strokeWidth={4.4} strokeLinecap="round" />
      <path d={v.browR} fill="none" stroke="#5a3a22" strokeWidth={4.4} strokeLinecap="round" />
      <path d="M0,-1 C3,2 5,10 4,13 C2,15.5 -2,15.5 -4,13 C-5,10 -3,2 0,-1 Z" fill="#d49a76" />
      <g transform="translate(-3.6 1.8) scale(1.8)">
      <path d={v.mouthD} fill={v.mouthFill} />
      <path d={v.teethD} fill="#ffffff" />
      <path d={v.tongueD} fill="#d8321a" />
      </g>
      </g>
      </g>
    </g>
  );
}

export const romy: RigDef = {
  id: 'romy_tremblay',
  name: 'Romy',
  head: [100, 150],
  crops: { full: [0, 0, 200, 420], bust: [10, 62, 180, 220], head: [28, 60, 144, 144] },
  idle: { kind: 'bob', seconds: 5, amount: 1.4 },
  tilt: { neutre: 0, ravie: -3, surprise: 0, fachee: 0, emue: 3 },
  brows: {
    neutre: [[-24, -21, -15, -26, -6, -22], [6, -22, 15, -26, 24, -21]],
    ravie: [[-24, -24, -15, -29, -6, -25], [6, -25, 15, -29, 24, -24]],
    surprise: [[-24, -28, -15, -34, -6, -29], [6, -29, 15, -34, 24, -28]],
    fachee: [[-24, -24, -15, -22, -6, -16], [6, -16, 15, -22, 24, -24]],
    emue: [[-24, -18, -15, -21, -6, -25], [6, -25, 15, -21, 24, -18]],
  },
  eyeL: [-15, -4],
  eyeR: [15, -4],
  eye: { rx: 10, ry: 11.5, pr: 6.2, dx: 0, iris: true },
  mouths: { neutre: 'smile' },
  mouthSet: 'symmetric',
  lips: '#b84a3c',
  holds: ['notebook'],
  extra: (p) => {
    const open = !p.blink && (p.mood === 'neutre' || p.mood === 'surprise');
    return {
      freckles: FRECKLE_D,
      lashL: open ? lash([-15, -4], -1) : '',
      lashR: open ? lash([15, -4], 1) : '',
      prop: p.hold === 'notebook' ? 'notebook' : '',
    };
  },
  Art: RomyArt,
};

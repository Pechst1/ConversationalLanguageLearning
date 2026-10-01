/* WP-116 · Lila, variant C. Ported from the Claude Design canvas rig (2026-10-01). */
import { circles, curlSpirals, dots } from '../rig-kit';
import type { RigDef, RigValues } from '../rig-kit';

const BACK = [[-42, -30, 13], [-47, -8, 12], [-44, 14, 11], [-40, 32, 9], [-46, 44, 6.5], [42, -30, 13], [47, -8, 12], [44, 14, 11], [40, 32, 9], [46, 44, 6.5], [-28, -48, 14], [28, -48, 14], [-10, -56, 14], [10, -56, 14]] as const;
const FRONT = [[-34, -36, 9], [34, -36, 9], [-21, -46, 8.5], [21, -46, 8.5], [-40, -20, 7], [40, -20, 7], [-6, -51, 7], [8, -51, 7]] as const;
const BUN = [[0, -82, 20], [-15, -74, 13], [15, -74, 13], [-7, -94, 11], [9, -95, 11]] as const;
const FRECKLES = [[-24, 8], [-28, 12], [-20, 13], [-31, 5], [-25, 16], [24, 8], [28, 12], [20, 13], [31, 5], [25, 16], [-5, 3], [5, 3]] as const;
const STATIC = {
  curlsBack: circles(BACK),
  curlsFront: circles(FRONT),
  bun: circles(BUN),
  curlLines: curlSpirals([...BACK, ...FRONT, ...BUN]),
  freckles: dots(FRECKLES, 1.3),
};

function LilaArt({ v }: { v: RigValues }) {
  return (
    <g>
      <path d="M90,326 L87,390 M110,326 L114,390" fill="none" stroke="#1d3a8a" strokeWidth={14} strokeLinecap="round" />
      <ellipse cx="84" cy="399" rx="12" ry="6.5" fill="#d8321a" />
      <ellipse cx="117" cy="399" rx="12" ry="6.5" fill="#d8321a" />
      <path d="M73,402 L95,402 M106,402 L128,402" fill="none" stroke="#f8f3e8" strokeWidth={2.2} strokeLinecap="round" />
      <path d="M93,234 L107,234 L107,256 L93,256 Z" fill="#c98a62" />
      <path d="M78,264 Q78,252 90,252 L110,252 Q122,252 122,264 L126,318 Q126,330 114,330 L86,330 Q74,330 74,318 Z" fill="#f3c318" />
      <path d="M93,252 L100,262 L107,252 Z" fill="#c98a62" />
      <path d="M92,252 L84,256 L96,270 L100,262 Z M108,252 L116,256 L104,270 L100,262 Z" fill="#c49a0a" />
      <path d="M120,262 Q140,278 134,296" fill="none" stroke="#f3c318" strokeWidth={11} strokeLinecap="round" />
      <path d="M134,296 Q128,304 122,306" fill="none" stroke="#c98a62" strokeWidth={9} strokeLinecap="round" />
      <circle cx="120" cy="306" r="7" fill="#c98a62" />
      <path d="M80,262 Q62,282 70,298" fill="none" stroke="#f3c318" strokeWidth={11} strokeLinecap="round" />
      <path d="M70,298 Q74,286 80,274" fill="none" stroke="#c98a62" strokeWidth={9} strokeLinecap="round" />
      <path d="M84,268 L95,246" fill="none" stroke="#d8321a" strokeWidth={4.5} />
      <path d="M93.2,245 L97.8,247.2 L98,239.5 Z" fill="#14110d" />
      <circle cx="82" cy="270" r="7" fill="#c98a62" />
      <ellipse cx="77" cy="268" rx="3" ry="2.2" fill="#c49a0a" />
      <g transform={v.headT}>
      <g className="cast-rig__idle">
      <path d={v.extra.curlsBack} fill="#2a1a12" />
      <path d={v.extra.bun} fill="#2a1a12" />
      <path d="M-24,-64 Q0,-56 24,-64 L22,-55 Q0,-47 -22,-55 Z" fill="#c49a0a" />
      <path d="M-20,-60 Q0,-53 20,-60" fill="none" stroke="#f3c318" strokeWidth={1.6} />
      <path d="M18,-58 C22,-44 20,-32 26,-20 L20,-18 C14,-32 14,-46 18,-58 Z" fill="#a7830a" />
      <path d="M22,-62 C28,-80 44,-80 40,-66 C38,-62 30,-60 22,-62 Z M22,-62 C38,-60 46,-48 38,-44 C32,-42 26,-52 22,-62 Z" fill="#c49a0a" />
      <circle cx="22" cy="-61" r="5" fill="#a7830a" />
      <path d="M-42,-14 C-42,-46 -22,-54 0,-54 C22,-54 42,-46 42,-14 C42,16 26,44 0,48 C-26,44 -42,16 -42,-14 Z" fill="#c98a62" />
      <path d={v.extra.curlsFront} fill="#2a1a12" />
      <path d={v.extra.curlLines} fill="none" stroke="#5a3a26" strokeWidth={1.6} strokeLinecap="round" />
      <circle cx="-40" cy="20" r="9" fill="none" stroke="#c49a0a" strokeWidth={3.2} />
      <circle cx="40" cy="20" r="9" fill="none" stroke="#c49a0a" strokeWidth={3.2} />
      <path d={v.extra.freckles} fill="#8f5534" />
      <path display={v.eL.sD} d={v.eL.sclera} fill="#ffffff" />
      <path display={v.eL.sD} d={v.eL.pupil} fill="#14110d" />
      <path display={v.eL.sD} d={v.eL.glint} fill="#ffffff" />
      <path d={v.eL.lid} fill="#c98a62" />
      <path d={v.eL.lidLine} fill="none" stroke="#14110d" strokeWidth={2.6} strokeLinecap="round" />
      <path d={v.eL.arc} fill="none" stroke="#14110d" strokeWidth={4.2} strokeLinecap="round" />
      <path d={v.eL.tear} fill="#1d3a8a" />
      <path display={v.eR.sD} d={v.eR.sclera} fill="#ffffff" />
      <path display={v.eR.sD} d={v.eR.pupil} fill="#14110d" />
      <path display={v.eR.sD} d={v.eR.glint} fill="#ffffff" />
      <path d={v.eR.lid} fill="#c98a62" />
      <path d={v.eR.lidLine} fill="none" stroke="#14110d" strokeWidth={2.6} strokeLinecap="round" />
      <path d={v.eR.arc} fill="none" stroke="#14110d" strokeWidth={4.2} strokeLinecap="round" />
      <path d="M-25,-9 L-30,-13 M25,-9 L30,-13" fill="none" stroke="#14110d" strokeWidth={2.6} strokeLinecap="round" />
      <path d={v.browL} fill="none" stroke="#2a1a12" strokeWidth={5.5} strokeLinecap="round" />
      <path d={v.browR} fill="none" stroke="#2a1a12" strokeWidth={5.5} strokeLinecap="round" />
      <path d="M0,4 C4,4 6,10 4,13 C2,15 -3,15 -4,13 C-6,10 -4,4 0,4 Z" fill="#a5683f" />
      <g transform="translate(-3.8 2) scale(1.9)">
      <path d={v.mouthD} fill="#14110d" />
      <path d={v.teethD} fill="#ffffff" />
      <path d={v.tongueD} fill="#d8321a" />
      </g>
      </g>
      </g>
    </g>
  );
}

export const lila: RigDef = {
  id: 'lila_bonnet',
  name: 'Lila',
  head: [100, 192],
  crops: { full: [0, 0, 200, 420], bust: [10, 80, 180, 256], head: [17, 84, 166, 166] },
  idle: { kind: 'bounce', seconds: 2.8, amount: 2.6 },
  tilt: { neutre: 6, ravie: -3, surprise: 0, fachee: -2, emue: 4 },
  eyes: { neutre: ['wry', 'wry'] },
  brows: {
    neutre: [[-26, -21, -16, -25, -7, -22], [7, -24, 16, -30, 26, -26]],
    ravie: [[-26, -25, -16, -31, -7, -27], [7, -27, 16, -32, 26, -26]],
    surprise: [[-26, -28, -16, -35, -7, -31], [7, -31, 16, -35, 26, -28]],
    fachee: [[-26, -25, -16, -23, -7, -17], [7, -17, 16, -23, 26, -25]],
    emue: [[-26, -18, -16, -21, -7, -26], [7, -26, 16, -21, 26, -18]],
  },
  eyeL: [-16, -4],
  eyeR: [16, -4],
  eye: { rx: 9.5, ry: 11, pr: 5.8, dx: 4, centreOnEmotion: true },
  mouths: { neutre: 'smirk' },
  extra: () => STATIC,
  Art: LilaArt,
};

/* WP-116 · Marin, variant C. Ported from the Claude Design canvas rig (2026-10-01). */
import { circles, curlArcs } from '../rig-kit';
import type { RigDef, RigValues } from '../rig-kit';

const BACK = [[-36, -38, 16], [-18, -54, 18], [4, -58, 18], [26, -50, 17], [40, -32, 14], [-46, -16, 12], [48, -14, 11], [-28, -48, 14], [14, -56, 16]] as const;
const FRONT = [[-28, -40, 10], [-11, -45, 11], [7, -46, 11], [24, -41, 10], [37, -32, 8]] as const;
let CABLES = '';
for (const x of [68, 100, 132]) {
  for (let y = 246; y < 344; y += 12) {
    CABLES += `M${x - 7},${y} L${x},${y + 7} L${x + 7},${y} L${x + 7},${y + 5} L${x},${y + 12} L${x - 7},${y + 5} Z `;
  }
}
const STATIC = { cables: CABLES, curlsBack: circles(BACK), curlsFront: circles(FRONT), glints: curlArcs([...BACK, ...FRONT]) };

function MarinArt({ v }: { v: RigValues }) {
  return (
    <g>
      <path d="M80,360 L80,390 M120,360 L120,390" fill="none" stroke="#4a4338" strokeWidth={20} strokeLinecap="round" />
      <ellipse cx="76" cy="400" rx="17" ry="8" fill="#14110d" />
      <ellipse cx="124" cy="400" rx="17" ry="8" fill="#14110d" />
      <path d="M44,262 Q48,232 76,228 L124,228 Q152,232 156,262 L170,338 Q172,366 144,368 L56,368 Q28,366 30,338 Z" fill="#2c6a5d" />
      <path d={v.extra.cables} fill="#1f4f45" />
      <path d="M31,350 L169,350 Q168,366 144,368 L56,368 Q32,366 31,350 Z" fill="#1f4f45" />
      <path d="M74,226 Q100,242 126,226 L128,236 Q100,254 72,236 Z" fill="#1f4f45" />
      <path d="M82,238 Q88,262 100,268 Q112,262 118,238" fill="none" stroke="#4a3020" strokeWidth={1.8} />
      <path d="M97,266 C94,276 100,284 106,280 C103,278.5 100.5,274 101.5,268 Z" fill="#f8f3e8" />
      <path d="M152,262 Q172,300 164,334" fill="none" stroke="#2c6a5d" strokeWidth={22} strokeLinecap="round" />
      <circle cx="162" cy="345" r="12" fill="#9a6643" />
      <path d="M48,262 Q28,296 38,320" fill="none" stroke="#2c6a5d" strokeWidth={22} strokeLinecap="round" />
      <path d="M38,320 Q54,310 64,296" fill="none" stroke="#2c6a5d" strokeWidth={18} strokeLinecap="round" />
      <path d="M50,266 L82,261 L87,303 L55,308 Z" fill="#1d3a8a" />
      <path d="M82,261 L86,262 L91,304 L87,303 Z" fill="#f8f3e8" />
      <path d="M54,272 L80,268 L80.5,272 L54.5,276 Z" fill="#f3c318" />
      <circle cx="73" cy="292" r="12" fill="#9a6643" />
      <circle cx="62" cy="286" r="5.5" fill="#9a6643" />
      <g transform={v.headT}>
      <g className="cast-rig__idle">
      <path d={v.extra.curlsBack} fill="#1c1611" />
      <ellipse cx="-46" cy="0" rx="8.5" ry="11" fill="#9a6643" />
      <ellipse cx="47" cy="0" rx="8.5" ry="11" fill="#9a6643" />
      <path d="M-46,-14 C-46,-46 -24,-54 0,-54 C24,-54 46,-46 46,-14 C46,20 32,48 0,50 C-32,48 -46,20 -46,-14 Z" fill="#9a6643" />
      <path d={v.extra.curlsFront} fill="#1c1611" />
      <path d={v.extra.glints} fill="none" stroke="#c49a0a" strokeWidth={2.4} strokeLinecap="round" />
      <path display={v.eL.sD} d={v.eL.sclera} fill="#ffffff" />
      <path display={v.eL.sD} d={v.eL.pupil} fill="#14110d" />
      <path display={v.eL.sD} d={v.eL.glint} fill="#ffffff" />
      <path d={v.eL.lid} fill="#9a6643" />
      <path d={v.eL.lidLine} fill="none" stroke="#14110d" strokeWidth={2.4} strokeLinecap="round" />
      <path d={v.eL.arc} fill="none" stroke="#14110d" strokeWidth={4.5} strokeLinecap="round" />
      <path d={v.eL.tear} fill="#1d3a8a" />
      <path display={v.eR.sD} d={v.eR.sclera} fill="#ffffff" />
      <path display={v.eR.sD} d={v.eR.pupil} fill="#14110d" />
      <path display={v.eR.sD} d={v.eR.glint} fill="#ffffff" />
      <path d={v.eR.lid} fill="#9a6643" />
      <path d={v.eR.lidLine} fill="none" stroke="#14110d" strokeWidth={2.4} strokeLinecap="round" />
      <path d={v.eR.arc} fill="none" stroke="#14110d" strokeWidth={4.5} strokeLinecap="round" />
      <path d={v.eR.tear} fill="#1d3a8a" />
      <path d={v.browL} fill="none" stroke="#1c1611" strokeWidth={7} strokeLinecap="round" />
      <path d={v.browR} fill="none" stroke="#1c1611" strokeWidth={7} strokeLinecap="round" />
      <path d="M-46,-2 C-48,32 -26,60 0,62 C26,60 48,32 46,-2 C40,10 30,15 17,13 C8,9 -8,9 -17,13 C-30,15 -40,10 -46,-2 Z" fill="#1c1611" />
      <ellipse cx="-1" cy="33" rx="19" ry="12" fill="#9a6643" />
      <g transform="translate(-5 -1) scale(2)">
      <path d={v.mouthD} fill="#14110d" />
      <path d={v.teethD} fill="#ffffff" />
      <path d={v.tongueD} fill="#d8321a" />
      </g>
      <path d="M-23,21 C-12,13 10,13 21,21 C10,24 -12,24 -23,21 Z" fill="#1c1611" />
      <path d="M0,0 C6,0 10,10 8,15 C6,19 -6,19 -8,15 C-10,10 -6,0 0,0 Z" fill="#774a2c" />
      </g>
      </g>
    </g>
  );
}

export const marin: RigDef = {
  id: 'marin_leveque',
  name: 'Marin',
  head: [100, 172],
  crops: { full: [0, 0, 200, 420], bust: [10, 88, 180, 220], head: [26, 92, 148, 148] },
  idle: { kind: 'bob', seconds: 4.8, amount: 2.2 },
  tilt: { neutre: 4, ravie: -5, surprise: -2, fachee: 0, emue: 7 },
  brows: {
    neutre: [[-30, -23, -19, -27, -8, -29], [10, -29, 21, -27, 32, -23]],
    ravie: [[-30, -27, -19, -33, -8, -32], [10, -32, 21, -33, 32, -27]],
    surprise: [[-30, -30, -19, -37, -8, -35], [10, -35, 21, -37, 32, -30]],
    fachee: [[-30, -28, -19, -26, -8, -20], [10, -20, 21, -26, 32, -28]],
    emue: [[-30, -20, -19, -24, -8, -33], [10, -33, 21, -24, 32, -20]],
  },
  eyeL: [-18, -6],
  eyeR: [19, -6],
  eye: { rx: 10, ry: 11.5, pr: 6.6, dx: -2, bothTears: true },
  mouths: { neutre: 'smile', emue: 'wobble' },
  extra: () => STATIC,
  Art: MarinArt,
};

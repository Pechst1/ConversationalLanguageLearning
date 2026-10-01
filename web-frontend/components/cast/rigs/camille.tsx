/* WP-116 · Camille, variant C. Ported from the Claude Design canvas rig (2026-10-01). */
import type { RigDef, RigValues } from '../rig-kit';

function CamilleArt({ v }: { v: RigValues }) {
  return (
    <g>
      <path d="M88,344 L87,392 M112,344 L113,392" fill="none" stroke="#14285f" strokeWidth={13} strokeLinecap="round" />
      <ellipse cx="84" cy="399" rx="12" ry="6.5" fill="#14110d" />
      <ellipse cx="116" cy="399" rx="12" ry="6.5" fill="#14110d" />
      <path d="M93,194 L107,194 L107,220 L93,220 Z" fill="#d8a07a" />
      <path d="M62,232 Q64,216 80,214 L120,214 Q136,216 138,232 L142,338 Q142,348 132,348 L68,348 Q58,348 58,338 Z" fill="#3e4542" />
      <path d="M88,214 L100,240 L112,214 Z" fill="#f8f3e8" />
      <path d="M84,214 L74,220 L96,246 L100,240 Z M116,214 L126,220 L104,246 L100,240 Z" fill="#6b4a2a" />
      <path d="M70,300 L92,300 L92,306 L70,306 Z M108,300 L130,300 L130,306 L108,306 Z" fill="#2f3533" />
      <path d="M66,250 Q63,290 67,330 M134,250 Q137,290 133,330" fill="none" stroke="#59615d" strokeWidth={2} strokeLinecap="round" />
      <path d="M134,236 Q150,262 145,280" fill="none" stroke="#3e4542" strokeWidth={14} strokeLinecap="round" />
      <path d="M139,280 L151,280" fill="none" stroke="#59615d" strokeWidth={6} strokeLinecap="round" />
      <path d="M145,284 Q145,296 139,304" fill="none" stroke="#d8a07a" strokeWidth={10} strokeLinecap="round" />
      <path d="M118,314 C118,288 162,284 166,310 L166,314 Z" fill="#d8321a" />
      <path d="M128,298 L134,294 M140,292 L146,292 M152,294 L158,298" fill="none" stroke="#9c2411" strokeWidth={3} strokeLinecap="round" />
      <path d="M116,315 L168,315" fill="none" stroke="#14110d" strokeWidth={3} strokeLinecap="round" />
      <path d="M124,316 Q130,328 142,323" fill="none" stroke="#14110d" strokeWidth={1.6} strokeLinecap="round" />
      <path d="M150,290 c2,3 2,5 0,5 c-2,0 -2,-2 0,-5 Z M160,300 c2,3 2,5 0,5 c-2,0 -2,-2 0,-5 Z M70,226 c2,3 2,5 0,5 c-2,0 -2,-2 0,-5 Z" fill="#1d3a8a" />
      <circle cx="139" cy="306" r="7.5" fill="#d8a07a" />
      <path d="M66,236 Q54,262 62,280" fill="none" stroke="#3e4542" strokeWidth={14} strokeLinecap="round" />
      <path d="M56,278 L68,282" fill="none" stroke="#59615d" strokeWidth={6} strokeLinecap="round" />
      <path d="M62,283 Q74,289 86,279" fill="none" stroke="#d8a07a" strokeWidth={10} strokeLinecap="round" />
      <path d="M70,244 L102,240 L106,288 L74,292 Z" fill="#1d3a8a" />
      <path d="M102,240 L105,241 L109,289 L106,288 Z" fill="#f8f3e8" />
      <path d="M76,256 L96,253 M77,264 L91,262 M78,272 L98,269 M79,280 L89,279" fill="none" stroke="#f8f3e8" strokeWidth={1.6} strokeLinecap="round" />
      <circle cx="88" cy="278" r="7.5" fill="#d8a07a" />
      <g transform={v.headT}>
      <g className="cast-rig__idle">
      <circle display={v.extra.fD} cx="-30" cy="34" r="12" fill="#1f1a16" />
      <ellipse cx="-37" cy="2" rx="7" ry="10" fill="#d8a07a" />
      <ellipse cx="37" cy="2" rx="7" ry="10" fill="#d8a07a" />
      <path d="M-37,-26 C-37,-58 -20,-66 0,-66 C20,-66 37,-58 37,-26 C37,10 22,48 0,52 C-22,48 -37,10 -37,-26 Z" fill="#d8a07a" />
      <path display={v.extra.mD} d="M-37,-2 C-36,30 -20,52 0,54 C20,52 36,30 37,-2 C33,16 24,28 14,28 C8,24 -8,24 -14,28 C-24,28 -33,16 -37,-2 Z" fill="#3a312a" />
      <ellipse display={v.extra.mD} cx="0" cy="33" rx="13" ry="8" fill="#d8a07a" />
      <path display={v.extra.mD} d="M-40,-22 C-42,-58 -18,-72 2,-72 C24,-72 42,-58 40,-22 C36,-38 24,-46 6,-46 C-12,-46 -30,-40 -40,-22 Z" fill="#1f1a16" />
      <path display={v.extra.fD} d="M-41,-14 C-46,-60 -16,-74 4,-72 C26,-72 46,-56 41,-14 C38,-36 24,-48 8,-50 L2,-50 C-14,-48 -32,-40 -41,-14 Z M-41,-14 L-36,10 L-33,-12 Z M41,-14 L36,10 L33,-12 Z" fill="#1f1a16" />
      <circle display={v.extra.fD} cx="-37" cy="13" r="2.4" fill="#d9d4c8" />
      <circle display={v.extra.fD} cx="37" cy="13" r="2.4" fill="#d9d4c8" />
      <path d="M-30,-56 Q0,-64 30,-56" fill="none" stroke="#3a312a" strokeWidth={2} strokeLinecap="round" />
      <path d="M-20,-62 c2,3 2,5 0,5 c-2,0 -2,-2 0,-5 Z M14,-66 c2,3 2,5 0,5 c-2,0 -2,-2 0,-5 Z M30,-52 c2,3 2,5 0,5 c-2,0 -2,-2 0,-5 Z" fill="#7f9bd0" />
      <path display={v.eL.sD} d={v.eL.sclera} fill="#ffffff" />
      <path display={v.eL.sD} d={v.eL.pupil} fill="#14110d" />
      <path display={v.eL.sD} d={v.eL.glint} fill="#ffffff" />
      <path d={v.eL.lid} fill="#d8a07a" />
      <path d={v.eL.lidLine} fill="none" stroke="#14110d" strokeWidth={2.4} strokeLinecap="round" />
      <path d={v.eL.arc} fill="none" stroke="#14110d" strokeWidth={4} strokeLinecap="round" />
      <path d={v.eL.tear} fill="#1d3a8a" />
      <path display={v.eR.sD} d={v.eR.sclera} fill="#ffffff" />
      <path display={v.eR.sD} d={v.eR.pupil} fill="#14110d" />
      <path display={v.eR.sD} d={v.eR.glint} fill="#ffffff" />
      <path d={v.eR.lid} fill="#d8a07a" />
      <path d={v.eR.lidLine} fill="none" stroke="#14110d" strokeWidth={2.4} strokeLinecap="round" />
      <path d={v.eR.arc} fill="none" stroke="#14110d" strokeWidth={4} strokeLinecap="round" />
      <path d={v.browL} fill="none" stroke="#1f1a16" strokeWidth={5} strokeLinecap="round" />
      <path d={v.browR} fill="none" stroke="#1f1a16" strokeWidth={5} strokeLinecap="round" />
      <path d="M1,-8 C5,-2 10,14 8,19 C6,22 -2,22 -3,19 C-4,14 -2,-4 1,-8 Z" fill="#b47d58" />
      <g transform="translate(-3.4 4.8) scale(1.7)">
      <path d={v.mouthD} fill="#14110d" />
      <path d={v.teethD} fill="#ffffff" />
      <path d={v.tongueD} fill="#d8321a" />
      </g>
      </g>
      </g>
    </g>
  );
}

export const camille: RigDef = {
  id: 'camille_marchand',
  name: 'Camille',
  head: [100, 150],
  crops: { full: [0, 0, 200, 420], bust: [10, 60, 180, 256], head: [26, 72, 148, 148] },
  idle: { kind: 'bob', seconds: 4.6, amount: 1 },
  tilt: { neutre: 0, ravie: 3, surprise: -2, fachee: 0, emue: -4 },
  eyes: { neutre: ['level', 'level'] },
  brows: {
    neutre: [[-24, -21, -14, -22, -5, -21], [5, -21, 14, -22, 24, -21]],
    ravie: [[-24, -25, -14, -29, -5, -26], [5, -26, 14, -29, 24, -25]],
    surprise: [[-24, -29, -14, -35, -5, -31], [5, -31, 14, -35, 24, -29]],
    fachee: [[-24, -23, -14, -21, -5, -16], [5, -16, 14, -21, 24, -23]],
    emue: [[-24, -19, -14, -22, -5, -26], [5, -26, 14, -22, 24, -19]],
  },
  eyeL: [-14, -6],
  eyeR: [14, -6],
  eye: { rx: 8.5, ry: 9.5, pr: 5, dx: 0 },
  mouths: { neutre: 'flat', ravie: 'smile' },
  variants: ['f', 'm'],
  extra: (p) => ({ fD: p.variant === 'm' ? 'none' : 'inline', mD: p.variant === 'm' ? 'inline' : 'none' }),
  Art: CamilleArt,
};

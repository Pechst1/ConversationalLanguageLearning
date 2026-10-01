/* WP-116 · Gus, variant C. Ported from the Claude Design canvas rig (2026-10-01). */
import type { RigDef, RigValues } from '../rig-kit';

function GusArt({ v }: { v: RigValues }) {
  return (
    <g>
      <path d="M90,336 L88,392 M110,336 L113,392" fill="none" stroke="#14285f" strokeWidth={14} strokeLinecap="round" />
      <path d="M72,398 Q76,391 92,393 L96,398 Q96,404 90,404 L74,404 Q69,402 72,398 Z M128,398 Q124,391 108,393 L104,398 Q104,404 110,404 L126,404 Q131,402 128,398 Z" fill="#14110d" />
      <path d="M93,176 L107,176 L107,214 L93,214 Z" fill="#e0a985" />
      <path d="M46,228 Q48,212 68,210 L132,210 Q152,212 154,228 L126,332 Q124,340 116,340 L84,340 Q76,340 74,332 Z" fill="#1d3a8a" />
      <path d="M84,210 L100,262 L116,210 Z" fill="#f8f3e8" />
      <path d="M96,213 L104,213 L102,222 L98,222 Z" fill="#9c2411" />
      <path d="M98,222 L102,222 L106,256 L100,264 L94,256 Z" fill="#d8321a" />
      <path d="M84,210 L70,214 L96,270 L100,262 Z M116,210 L130,214 L104,270 L100,262 Z" fill="#14285f" />
      <circle cx="100" cy="290" r="2.6" fill="#c49a0a" />
      <circle cx="100" cy="306" r="2.6" fill="#c49a0a" />
      <path d="M121,238 L127,221 L132,223 L126,240 Z M125,238 L135,223 L139,226 L129,241 Z" fill="#f8f3e8" />
      <path d="M119,240 L140,235 L137,247 L123,249 Z M123,240 L127,231 L132,239 Z M131,238 L137,230 L139,236 Z" fill="#d8321a" />
      <path d="M148,226 Q168,262 152,288" fill="none" stroke="#1d3a8a" strokeWidth={14} strokeLinecap="round" />
      <path d="M145,296 L163,292 L165,306 L147,310 Z" fill="#f8f3e8" />
      <path d="M149,300 L160,297.6 M149.6,304 L158,302" fill="none" stroke="#6f6857" strokeWidth={1.2} />
      <circle cx="151" cy="292" r="8" fill="#e0a985" />
      <path d="M54,224 Q30,226 26,196" fill="none" stroke="#1d3a8a" strokeWidth={14} strokeLinecap="round" />
      <path d="M20,200 L32,195" fill="none" stroke="#f8f3e8" strokeWidth={5} strokeLinecap="round" />
      <ellipse cx="25" cy="185" rx="9.5" ry="7.5" fill="#e0a985" />
      <circle cx="34" cy="188" r="3.6" fill="#e0a985" />
      <g transform={v.headT}>
      <g className="cast-rig__idle">
      <path d="M-42,-20 C-50,-60 -20,-92 14,-88 C44,-86 54,-58 44,-22 L30,-40 L-30,-40 Z" fill="#3d2817" />
      <ellipse cx="-38" cy="2" rx="7" ry="11" fill="#e0a985" />
      <ellipse cx="40" cy="2" rx="7" ry="11" fill="#e0a985" />
      <path d="M-38,-28 C-38,-60 -20,-68 2,-68 C24,-68 40,-58 40,-28 L40,8 C40,34 26,54 2,58 C-22,54 -38,34 -38,8 Z" fill="#e0a985" />
      <path d="M-30,30 Q-14,48 2,51 Q18,48 33,30 Q22,55 2,58 Q-18,55 -30,30 Z" fill="#cf956f" />
      <path d="M2,50 L2,56" fill="none" stroke="#b97f5c" strokeWidth={2} strokeLinecap="round" />
      <path d="M-42,-22 C-50,-64 -14,-96 18,-90 C46,-86 54,-58 44,-24 C40,-42 30,-52 16,-54 C4,-46 -18,-54 -30,-42 C-36,-36 -40,-30 -42,-22 Z" fill="#3d2817" />
      <path d="M-24,-70 C-10,-82 10,-84 26,-78 C10,-78 -6,-74 -18,-64 Z M20,-72 C32,-70 42,-62 44,-50 C38,-58 30,-64 20,-66 Z" fill="#8a5a32" />
      <path d="M6,-52 C0,-42 6,-32 14,-34 C9,-37 8,-43 12,-50 Z" fill="#3d2817" />
      <path display={v.eL.sD} d={v.eL.sclera} fill="#ffffff" />
      <path display={v.eL.sD} d={v.eL.pupil} fill="#14110d" />
      <path display={v.eL.sD} d={v.eL.glint} fill="#ffffff" />
      <path d={v.eL.lid} fill="#e0a985" />
      <path d={v.eL.lidLine} fill="none" stroke="#14110d" strokeWidth={2.6} strokeLinecap="round" />
      <path d={v.eL.arc} fill="none" stroke="#14110d" strokeWidth={4.2} strokeLinecap="round" />
      <path d={v.eL.tear} fill="#1d3a8a" />
      <path display={v.eR.sD} d={v.eR.sclera} fill="#ffffff" />
      <path display={v.eR.sD} d={v.eR.pupil} fill="#14110d" />
      <path display={v.eR.sD} d={v.eR.glint} fill="#ffffff" />
      <path d={v.eR.lid} fill="#e0a985" />
      <path d={v.eR.lidLine} fill="none" stroke="#14110d" strokeWidth={2.6} strokeLinecap="round" />
      <path d={v.eR.arc} fill="none" stroke="#14110d" strokeWidth={4.2} strokeLinecap="round" />
      <path d={v.browL} fill="none" stroke="#3d2817" strokeWidth={5.5} strokeLinecap="round" />
      <path d={v.browR} fill="none" stroke="#3d2817" strokeWidth={5.5} strokeLinecap="round" />
      <path d="M1,-10 C5,-6 11,14 10,20 C8,24 -1,24 -3,20 C-3,12 -1,-6 1,-10 Z" fill="#b97f5c" />
      <g transform="translate(-1.6 7) scale(1.8)">
      <path d={v.mouthD} fill="#14110d" />
      <path d={v.teethD} fill="#ffffff" />
      <path d={v.tongueD} fill="#d8321a" />
      </g>
      </g>
      </g>
    </g>
  );
}

export const gus: RigDef = {
  id: 'augustin_de_roncourt',
  name: 'Gus',
  head: [100, 128],
  crops: { full: [0, 0, 200, 420], bust: [10, 32, 180, 256], head: [22, 32, 156, 156] },
  idle: { kind: 'sway', seconds: 3.6, amount: -2.5 },
  tilt: { neutre: -7, ravie: -11, surprise: -3, fachee: 2, emue: 4 },
  eyes: { neutre: ['heavy', 'heavy'] },
  brows: {
    neutre: [[-26, -24, -16, -31, -6, -26], [7, -26, 18, -32, 29, -25]],
    ravie: [[-26, -27, -16, -34, -6, -29], [7, -29, 18, -35, 29, -27]],
    surprise: [[-26, -31, -16, -38, -6, -33], [7, -33, 18, -39, 29, -31]],
    fachee: [[-26, -28, -16, -26, -6, -19], [7, -19, 18, -26, 29, -28]],
    emue: [[-26, -20, -16, -24, -6, -29], [7, -29, 18, -24, 29, -20]],
  },
  eyeL: [-15, -6],
  eyeR: [17, -6],
  eye: { rx: 9, ry: 10, pr: 5, dx: 1, dy: 2 },
  mouths: { neutre: 'smirk' },
  Art: GusArt,
};

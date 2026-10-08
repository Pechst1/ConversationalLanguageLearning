/* WP-116 · Margaux, variant C. Ported from the Claude Design canvas rig (2026-10-01). */
import React from 'react';
import type { RigDef, RigValues } from '../rig-kit';

function MargauxArt({ v }: { v: RigValues }) {
  return (
    <g>
      <path d="M90,366 L89,394 M110,366 L111,394" fill="none" stroke="#14285f" strokeWidth={12} strokeLinecap="round" />
      <ellipse cx="86" cy="401" rx="12" ry="6" fill="#14110d" />
      <ellipse cx="114" cy="401" rx="12" ry="6" fill="#14110d" />
      <path d="M92,196 L108,196 L108,232 L92,232 Z" fill="#cf946a" />
      <path d="M70,236 Q70,226 82,226 L118,226 Q130,226 130,236 L134,330 Q134,340 124,340 L76,340 Q66,340 66,330 Z" fill="#2c6a5d" />
      <path d="M90,226 L100,242 L110,226 Z" fill="#cf946a" />
      <path d="M88,226 L81,230 L96,250 L100,242 Z M112,226 L119,230 L104,250 L100,242 Z" fill="#1f4f45" />
      <path d="M78,256 Q78,250 84,250 L116,250 Q122,250 122,256 L126,364 Q126,370 120,370 L80,370 Q74,370 74,364 Z" fill="#2a231c" />
      <path d="M81,252 L86,252 L92,228 L87,228 Z M114,252 L119,252 L113,228 L108,228 Z" fill="#2a231c" />
      <circle cx="83.5" cy="253" r="3.4" fill="#c49a0a" />
      <circle cx="116.5" cy="253" r="3.4" fill="#c49a0a" />
      <path d="M128,240 Q142,266 138,290" fill="none" stroke="#2c6a5d" strokeWidth={13} strokeLinecap="round" />
      <path d="M138,290 Q136,306 128,314" fill="none" stroke="#cf946a" strokeWidth={10} strokeLinecap="round" />
      <path d="M116,316 L138,314 L141,356 L119,358 Z" fill="#f8f3e8" />
      <path d="M122,316 L125,316 L125,357 L122,357 Z M129,315 L131.5,315 L132.5,356 L130,356 Z" fill="#d8321a" />
      <circle cx="126" cy="318" r="8" fill="#cf946a" />
      <path d="M72,240 Q58,270 66,292" fill="none" stroke="#2c6a5d" strokeWidth={13} strokeLinecap="round" />
      <path d="M66,292 Q80,294 92,284" fill="none" stroke="#cf946a" strokeWidth={10} strokeLinecap="round" />
      <g display={v.extra.verreD}>
      <path d="M84,236 Q84,260 95,261 Q106,260 106,236 Z" fill="#f8f3e8" />
      <path d="M87.5,240 Q88.5,253 92.5,257 L90.5,257 Q86.5,251 86.5,240 Z" fill="#1d3a8a" />
      <path d="M94.2,261 L95.8,261 L95.8,276 L94.2,276 Z" fill="#f8f3e8" />
      </g>
      <g display={v.extra.tasseD}>
      <path d="M80,268 Q95,263 110,268 Q95,273 80,268 Z" fill="#f8f3e8" />
      <circle cx="108" cy="254" r="4.5" fill="none" stroke="#f8f3e8" strokeWidth={3} />
      <path d="M84,246 L106,246 L104,262 Q95,267 86,262 Z" fill="#f8f3e8" />
      <path d="M84,246 Q95,242.5 106,246 Q95,249.5 84,246 Z" fill="#b07a4e" />
      </g>
      <g display={v.extra.cleD}>
      <circle cx="96" cy="244" r="9" fill="none" stroke="#c49a0a" strokeWidth={4} />
      <path d="M94.3,253 L97.7,253 L97.7,298 L94.3,298 Z M97.7,289 L103,289 L103,293 L97.7,293 Z M97.7,294.5 L102,294.5 L102,298 L97.7,298 Z" fill="#c49a0a" />
      <circle cx="108.5" cy="250" r="2.4" fill="none" stroke="#c49a0a" strokeWidth={1.5} />
      <path d="M110.5,255 L104,268 L109.5,266.5 Z M113.5,255 L120,268 L114.5,266.5 Z" fill="#f3c318" />
      <path d="M112,253 C115.5,253 117,259 114.6,266.5 C113.9,268.8 110.1,268.8 109.4,266.5 C107,259 108.5,253 112,253 Z" fill="#2c6a5d" />
      </g>
      <circle cx="95" cy="281" r="8" fill="#cf946a" />
      <g transform={v.headT}>
      <g className="cast-rig__idle">
      <path d="M-46,-14 C-50,-56 -22,-84 8,-82 C40,-80 54,-56 48,-14 L30,-34 L-30,-34 Z" fill="#dcd6c8" />
      <path d="M-10,-76 C-4,-96 16,-100 26,-92 C16,-90 10,-84 8,-76 Z M18,-72 C30,-88 48,-86 52,-74 C44,-75 38,-71 33,-64 Z M-28,-66 C-32,-80 -22,-88 -14,-86 C-19,-82 -20,-76 -18,-70 Z" fill="#dcd6c8" />
      <ellipse cx="-41" cy="0" rx="7.5" ry="11" fill="#cf946a" />
      <ellipse cx="42" cy="0" rx="7.5" ry="11" fill="#cf946a" />
      <path d="M-40,-30 C-40,-62 -22,-70 0,-70 C24,-70 42,-62 42,-30 L42,8 C42,36 22,58 2,58 C-18,58 -40,36 -40,8 Z" fill="#cf946a" />
      <circle cx="-42" cy="15" r="4.5" fill="none" stroke="#c49a0a" strokeWidth={2.4} />
      <circle cx="43" cy="15" r="4.5" fill="none" stroke="#c49a0a" strokeWidth={2.4} />
      <path d="M-42,-24 C-44,-58 -16,-78 10,-76 C34,-76 50,-60 48,-34 C40,-46 28,-50 16,-48 C6,-40 -12,-44 -24,-38 C-34,-36 -40,-30 -42,-24 Z" fill="#dcd6c8" />
      <path d="M-26,-62 C-12,-72 8,-74 24,-68 C8,-68 -6,-64 -18,-56 Z M26,-58 C36,-56 44,-48 46,-40 C40,-46 34,-50 26,-52 Z" fill="#a59e8f" />
      <path d="M-30,-4 L-35,-7 M-30,2 L-35,3 M31,-4 L36,-7 M31,2 L36,3 M-32,12 Q-27,20 -21,23 M33,12 Q28,20 22,23" fill="none" stroke="#a96f47" strokeWidth={2} strokeLinecap="round" />
      <path display={v.eL.sD} d={v.eL.sclera} fill="#ffffff" />
      <path display={v.eL.sD} d={v.eL.pupil} fill="#14110d" />
      <path display={v.eL.sD} d={v.eL.glint} fill="#ffffff" />
      <path d={v.eL.lid} fill="#cf946a" />
      <path d={v.eL.lidLine} fill="none" stroke="#14110d" strokeWidth={2.4} strokeLinecap="round" />
      <path d={v.eL.arc} fill="none" stroke="#14110d" strokeWidth={4.2} strokeLinecap="round" />
      <path d={v.eL.tear} fill="#1d3a8a" />
      <path display={v.eR.sD} d={v.eR.sclera} fill="#ffffff" />
      <path display={v.eR.sD} d={v.eR.pupil} fill="#14110d" />
      <path display={v.eR.sD} d={v.eR.glint} fill="#ffffff" />
      <path d={v.eR.lid} fill="#cf946a" />
      <path d={v.eR.lidLine} fill="none" stroke="#14110d" strokeWidth={2.4} strokeLinecap="round" />
      <path d={v.eR.arc} fill="none" stroke="#14110d" strokeWidth={4.2} strokeLinecap="round" />
      <path d={v.browL} fill="none" stroke="#6e675b" strokeWidth={5} strokeLinecap="round" />
      <path d={v.browR} fill="none" stroke="#6e675b" strokeWidth={5} strokeLinecap="round" />
      <path d="M1,-4 C5,-2 10,12 8,17 C6,21 -2,21 -3,17 C-4,12 -2,-2 1,-4 Z" fill="#a96f47" />
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

export const margaux: RigDef = {
  id: 'margaux_barman',
  name: 'Margaux',
  head: [100, 150],
  crops: { full: [0, 0, 200, 420], bust: [10, 44, 180, 220], head: [22, 52, 156, 156] },
  idle: { kind: 'bob', seconds: 4.2, amount: 1.6 },
  tilt: { neutre: -4, ravie: 4, surprise: 2, fachee: 0, emue: -7 },
  eyes: { neutre: ['wry', 'wry'] },
  brows: {
    neutre: [[-26, -22, -16, -25, -7, -22], [7, -27, 17, -35, 27, -29]],
    ravie: [[-26, -26, -16, -31, -7, -27], [7, -28, 17, -34, 27, -28]],
    surprise: [[-26, -30, -16, -37, -7, -32], [7, -32, 17, -38, 27, -30]],
    fachee: [[-26, -27, -16, -25, -7, -19], [7, -19, 17, -25, 27, -27]],
    emue: [[-26, -20, -16, -23, -7, -28], [7, -28, 17, -23, 27, -20]],
  },
  eyeL: [-16, -6],
  eyeR: [16, -6],
  eye: { rx: 9, ry: 10.5, pr: 5.2, dx: 2 },
  mouths: { neutre: 'smirk' },
  holds: ['verre', 'tasse', 'cle'],
  extra: (p) => {
    const hold = p.hold === 'tasse' || p.hold === 'cle' ? p.hold : 'verre';
    return {
      verreD: hold === 'verre' ? 'inline' : 'none',
      tasseD: hold === 'tasse' ? 'inline' : 'none',
      cleD: hold === 'cle' ? 'inline' : 'none',
    };
  },
  Art: MargauxArt,
};

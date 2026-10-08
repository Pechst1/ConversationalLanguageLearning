/* WP-116 · M. Marchand, variant C. Ported from the Claude Design canvas rig (2026-10-01). */
import type { RigDef, RigValues } from '../rig-kit';

function MarchandArt({ v }: { v: RigValues }) {
  return (
    <g>
      <path d="M86,352 L84,392 M116,352 L120,392" fill="none" stroke="#4a4338" strokeWidth={13} strokeLinecap="round" />
      <ellipse cx="82" cy="400" rx="13" ry="6.5" fill="#14110d" />
      <ellipse cx="123" cy="400" rx="13" ry="6.5" fill="#14110d" />
      <path d="M64,262 Q56,290 66,306" fill="none" stroke="#8a8476" strokeWidth={13} strokeLinecap="round" />
      <path d="M104,216 L122,216 L124,236 L102,236 Z" fill="#e3a98a" />
      <path d="M58,262 C52,236 70,222 96,222 L124,226 Q144,232 146,252 L144,346 Q144,358 130,358 L70,358 Q58,358 58,346 Z" fill="#a59e8f" />
      <path d="M62,250 C64,236 76,228 92,226 C80,232 70,240 66,256 Z" fill="#c9c2b2" />
      <path d="M101,262 L103,350" fill="none" stroke="#8a8476" strokeWidth={2} />
      <circle cx="102" cy="292" r="2.6" fill="#c49a0a" />
      <circle cx="102.5" cy="318" r="2.6" fill="#c49a0a" />
      <path d="M82,228 Q112,246 142,230 L140,246 Q112,262 84,244 Z" fill="#2c6a5d" />
      <path d="M116,244 L132,244 L136,306 L118,308 Z" fill="#2c6a5d" />
      <path d="M117.2,284 L134.8,283 L135,287 L117.4,288 Z M117.6,292 L135.3,291 L135.5,294 L117.8,295 Z" fill="#c49a0a" />
      <path d="M119,308 L119,314 M123,308 L123,314 M127,308 L127,313 M131,307 L131,313 M135,306 L135,312" fill="none" stroke="#2c6a5d" strokeWidth={1.8} strokeLinecap="round" />
      <path d="M140,254 Q160,282 152,304" fill="none" stroke="#a59e8f" strokeWidth={14} strokeLinecap="round" />
      <path d="M148,326 L145,350 M158,325 L162,348" fill="none" stroke="#c49a0a" strokeWidth={3} strokeLinecap="round" />
      <path d="M153,327 L153,352" fill="none" stroke="#8a8476" strokeWidth={3} strokeLinecap="round" />
      <path d="M142,346 L147,346 L146.5,351 L141.5,351 Z M150,348 L156,348 L156,352 L150,352 Z M160,344 L165,343 L165.8,348 L160.8,349 Z" fill="#c49a0a" />
      <circle cx="153" cy="320" r="7" fill="none" stroke="#c49a0a" strokeWidth={2.5} />
      <circle cx="151" cy="309" r="8" fill="#e3a98a" />
      <g transform={v.headT}>
      <g className="cast-rig__idle">
      <ellipse cx="-37" cy="4" rx="9" ry="14" fill="#e3a98a" />
      <ellipse cx="40" cy="4" rx="8" ry="13" fill="#e3a98a" />
      <path d="M-36,-20 C-38,-62 -18,-76 4,-76 C28,-76 42,-62 40,-20 L40,10 C40,36 26,52 4,54 C-20,52 -36,36 -36,10 Z" fill="#e3a98a" />
      <ellipse cx="-6" cy="-60" rx="10" ry="4.5" fill="#f0c3a6" />
      <path d="M-16,-44 Q2,-48 20,-44 M-12,-36 Q2,-39 16,-36" fill="none" stroke="#c0846a" strokeWidth={2} strokeLinecap="round" />
      <path d="M-35,-30 C-54,-46 -66,-24 -52,-14 C-64,-8 -58,10 -41,3 C-43,-8 -41,-20 -35,-30 Z M-48,-38 L-60,-48 L-44,-34 Z M39,-30 C56,-46 68,-24 54,-14 C66,-8 60,10 43,3 C45,-8 43,-20 39,-30 Z M52,-38 L64,-48 L48,-34 Z" fill="#ece7db" />
      <path d="M-50,-22 C-46,-20 -44,-16 -44,-10 M52,-22 C48,-20 46,-16 46,-10" fill="none" stroke="#c9c2b2" strokeWidth={2} strokeLinecap="round" />
      <path display={v.eL.sD} d={v.eL.sclera} fill="#ffffff" />
      <path display={v.eL.sD} d={v.eL.pupil} fill="#14110d" />
      <path display={v.eL.sD} d={v.eL.glint} fill="#ffffff" />
      <path d={v.eL.lid} fill="#e3a98a" />
      <path d={v.eL.lidLine} fill="none" stroke="#14110d" strokeWidth={2.2} strokeLinecap="round" />
      <path d={v.eL.arc} fill="none" stroke="#14110d" strokeWidth={3.6} strokeLinecap="round" />
      <path d={v.eL.tear} fill="#1d3a8a" />
      <path display={v.eR.sD} d={v.eR.sclera} fill="#ffffff" />
      <path display={v.eR.sD} d={v.eR.pupil} fill="#14110d" />
      <path display={v.eR.sD} d={v.eR.glint} fill="#ffffff" />
      <path d={v.eR.lid} fill="#e3a98a" />
      <path d={v.eR.lidLine} fill="none" stroke="#14110d" strokeWidth={2.2} strokeLinecap="round" />
      <path d={v.eR.arc} fill="none" stroke="#14110d" strokeWidth={3.6} strokeLinecap="round" />
      <path d="M-24,-8 A12,12 0 1 0 0,-8 A12,12 0 1 0 -24,-8 Z M6,-8 A12,12 0 1 0 30,-8 A12,12 0 1 0 6,-8 Z M0,-9 Q3,-12 6,-9 M-24,-9 L-35,-5 M30,-9 L39,-5" fill="none" stroke="#c49a0a" strokeWidth={2.2} strokeLinecap="round" />
      <path d={v.browL} fill="none" stroke="#b5ad9d" strokeWidth={7} strokeLinecap="round" />
      <path d={v.browR} fill="none" stroke="#b5ad9d" strokeWidth={7} strokeLinecap="round" />
      <path d="M3,-8 C9,-2 18,16 14,23 C11,28 -1,27 -2,22 C-3,14 0,-2 3,-8 Z" fill="#c0846a" />
      <path d="M-8,24 Q-12,33 -8,41 M20,24 Q24,33 20,41" fill="none" stroke="#c0846a" strokeWidth={2} strokeLinecap="round" />
      <g transform="translate(-1.6 13.4) scale(1.6)">
      <path d={v.mouthD} fill="#14110d" />
      <path d={v.teethD} fill="#ffffff" />
      <path d={v.tongueD} fill="#d8321a" />
      </g>
      </g>
      </g>
    </g>
  );
}

export const marchand: RigDef = {
  id: 'landlord_marchand',
  name: 'M. Marchand',
  head: [112, 178],
  crops: { full: [0, 0, 200, 420], bust: [12, 94, 180, 220], head: [44, 96, 140, 140] },
  idle: { kind: 'nod', seconds: 5.2, amount: 3 },
  tilt: { neutre: 6, ravie: 0, surprise: -2, fachee: 8, emue: 10 },
  eyes: { neutre: ['heavy', 'heavy'] },
  brows: {
    neutre: [[-22, -23, -12, -27, -3, -24], [8, -24, 18, -28, 28, -23]],
    ravie: [[-22, -26, -12, -31, -3, -27], [8, -27, 18, -31, 28, -26]],
    surprise: [[-22, -30, -12, -36, -3, -31], [8, -31, 18, -36, 28, -30]],
    fachee: [[-22, -27, -12, -25, -3, -19], [8, -19, 18, -25, 28, -27]],
    emue: [[-22, -20, -12, -23, -3, -28], [8, -28, 18, -23, 28, -20]],
  },
  eyeL: [-12, -8],
  eyeR: [18, -8],
  eye: { rx: 7, ry: 7.5, pr: 4, dx: 2 },
  mouths: { neutre: 'm', ravie: 'smile' },
  Art: MarchandArt,
};

/* WP-116 · Odile, variant C. Ported from the Claude Design canvas rig (2026-10-01). */
import type { RigDef, RigValues } from '../rig-kit';

function OdileArt({ v }: { v: RigValues }) {
  return (
    <g>
      <path d="M88,376 L88,394 M112,376 L112,394" fill="none" stroke="#a59e8f" strokeWidth={9} strokeLinecap="round" />
      <ellipse cx="86" cy="400" rx="10" ry="5.5" fill="#14110d" />
      <ellipse cx="114" cy="400" rx="10" ry="5.5" fill="#14110d" />
      <path d="M72,350 L128,350 L132,378 L68,378 Z" fill="#6f6857" />
      <path d="M94,244 L106,244 L106,264 L94,264 Z" fill="#ecbfa0" />
      <path d="M70,272 Q72,260 84,260 L116,260 Q128,260 130,272 L134,344 Q134,354 124,354 L76,354 Q66,354 66,344 Z" fill="#5d6e35" />
      <path d="M90,260 L100,276 L110,260 Z" fill="#f8f3e8" />
      <path d="M100,276 L100,352" fill="none" stroke="#47552a" strokeWidth={2} />
      <circle cx="104" cy="288" r="2.4" fill="#c49a0a" />
      <circle cx="104" cy="340" r="2.4" fill="#c49a0a" />
      <path d="M86,262 L93,300 M114,262 L107,300" fill="none" stroke="#14110d" strokeWidth={2} />
      <path d="M72,276 Q60,300 74,316" fill="none" stroke="#5d6e35" strokeWidth={11} strokeLinecap="round" />
      <path d="M128,276 Q140,300 126,316" fill="none" stroke="#5d6e35" strokeWidth={11} strokeLinecap="round" />
      <path d="M80,304 Q80,298 86,298 L114,298 Q120,298 120,304 L120,326 Q120,332 114,332 L86,332 Q80,332 80,326 Z" fill="#f8f3e8" />
      <path d="M80,304 Q80,298 86,298 L114,298 Q120,298 120,304 L120,309 L80,309 Z" fill="#14110d" />
      <path d="M84,301 L92,301 L92,306 L84,306 Z" fill="#f8f3e8" />
      <circle cx="99" cy="320" r="8" fill="#14110d" />
      <circle cx="99" cy="320" r="4.5" fill="#3d3832" />
      <circle cx="97.5" cy="318.5" r="1.4" fill="#f8f3e8" />
      <path d="M110,312 L112.5,312 L112.5,328 L110,328 Z" fill="#d8321a" />
      <path d="M112.5,312 L115,312 L115,328 L112.5,328 Z" fill="#f3c318" />
      <path d="M115,312 L117.5,312 L117.5,328 L115,328 Z" fill="#1d3a8a" />
      <circle cx="77" cy="318" r="7" fill="#ecbfa0" />
      <circle cx="123" cy="318" r="7" fill="#ecbfa0" />
      <g transform={v.headT}>
      <g className="cast-rig__idle">
      <path d="M-48,-12 C-50,-58 -24,-70 0,-70 C24,-70 50,-58 48,-12 L48,24 L-48,24 Z" fill="#e9e4d8" />
      <path d="M-40,-16 C-40,-48 -22,-56 0,-56 C22,-56 40,-48 40,-16 C40,18 24,44 0,46 C-24,44 -40,18 -40,-16 Z" fill="#ecbfa0" />
      <path d="M-48,-30 L-36,-30 C-38,-6 -38,10 -36,24 L-48,24 Z M48,-30 L36,-30 C38,-6 38,10 36,24 L48,24 Z" fill="#e9e4d8" />
      <path d="M-44,-28 C-46,-58 -22,-66 0,-66 C22,-66 46,-58 44,-28 Z" fill="#e9e4d8" />
      <path d="M-30,-30 L-32,-50 M-14,-30 L-15,-56 M2,-30 L2,-58 M18,-30 L19,-56 M32,-30 L33,-50 M-44,-2 L-44,20 M44,-2 L44,20" fill="none" stroke="#c9c2b2" strokeWidth={1.6} strokeLinecap="round" />
      <ellipse cx="-24" cy="14" rx="7" ry="4" fill="#e9a48a" />
      <ellipse cx="24" cy="14" rx="7" ry="4" fill="#e9a48a" />
      <path d="M-28,-8 L-34,-12 M-28,-3 L-35,-3 M-28,2 L-34,6 M28,-8 L34,-12 M28,-3 L35,-3 M28,2 L34,6 M-22,9 Q-15,13 -8,9 M8,9 Q15,13 22,9" fill="none" stroke="#c9937a" strokeWidth={1.8} strokeLinecap="round" />
      <path display={v.eL.sD} d={v.eL.sclera} fill="#ffffff" />
      <path display={v.eL.sD} d={v.eL.pupil} fill="#14110d" />
      <path display={v.eL.sD} d={v.eL.glint} fill="#ffffff" />
      <path d={v.eL.lid} fill="#ecbfa0" />
      <path d={v.eL.lidLine} fill="none" stroke="#14110d" strokeWidth={2.4} strokeLinecap="round" />
      <path d={v.eL.arc} fill="none" stroke="#14110d" strokeWidth={4.4} strokeLinecap="round" />
      <path d={v.eL.tear} fill="#1d3a8a" />
      <path display={v.eR.sD} d={v.eR.sclera} fill="#ffffff" />
      <path display={v.eR.sD} d={v.eR.pupil} fill="#14110d" />
      <path display={v.eR.sD} d={v.eR.glint} fill="#ffffff" />
      <path d={v.eR.lid} fill="#ecbfa0" />
      <path d={v.eR.lidLine} fill="none" stroke="#14110d" strokeWidth={2.4} strokeLinecap="round" />
      <path d={v.eR.arc} fill="none" stroke="#14110d" strokeWidth={4.4} strokeLinecap="round" />
      <path d={v.browL} fill="none" stroke="#a59e8f" strokeWidth={3.6} strokeLinecap="round" />
      <path d={v.browR} fill="none" stroke="#a59e8f" strokeWidth={3.6} strokeLinecap="round" />
      <path d="M0,2 C5,2 7,9 5,12 C3,15 -3,15 -5,12 C-7,9 -5,2 0,2 Z" fill="#c9937a" />
      <g transform="translate(-3.6 1.2) scale(1.8)">
      <path d={v.mouthD} fill="#14110d" />
      <path d={v.teethD} fill="#ffffff" />
      <path d={v.tongueD} fill="#d8321a" />
      </g>
      </g>
      </g>
    </g>
  );
}

export const odile: RigDef = {
  id: 'odile_ferrand',
  name: 'Odile',
  head: [100, 206],
  crops: { full: [0, 0, 200, 420], bust: [10, 128, 180, 220], head: [30, 130, 140, 140] },
  idle: { kind: 'bob', seconds: 3.2, amount: 1.8 },
  tilt: { neutre: 3, ravie: -6, surprise: 0, fachee: 0, emue: 5 },
  brows: {
    neutre: [[-24, -21, -15, -25, -6, -22], [6, -22, 15, -25, 24, -21]],
    ravie: [[-24, -23, -15, -27, -6, -24], [6, -24, 15, -27, 24, -23]],
    surprise: [[-24, -25, -15, -29, -6, -26], [6, -26, 15, -29, 24, -25]],
    fachee: [[-24, -24, -15, -22, -6, -18], [6, -18, 15, -22, 24, -24]],
    emue: [[-24, -19, -15, -21, -6, -25], [6, -25, 15, -21, 24, -19]],
  },
  eyeL: [-15, -6],
  eyeR: [15, -6],
  eye: { rx: 10.5, ry: 12, pr: 7.6, dx: 0 },
  mouths: { neutre: 'smile' },
  Art: OdileArt,
};

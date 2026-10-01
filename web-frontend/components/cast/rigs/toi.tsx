/* WP-116 · Toi, variant C. Ported from the Claude Design canvas rig (2026-10-01). */
import type { RigDef, RigValues } from '../rig-kit';

function ToiArt({ v }: { v: RigValues }) {
  return (
    <g>
      <path d="M86,366 L86,392 M114,366 L114,392" fill="none" stroke="#14285f" strokeWidth={13} strokeLinecap="round" />
      <ellipse cx="85" cy="399" rx="12" ry="6" fill="#14110d" />
      <ellipse cx="115" cy="399" rx="12" ry="6" fill="#14110d" />
      <path d="M52,196 Q40,250 46,296" fill="none" stroke="#5b5346" strokeWidth={18} strokeLinecap="round" />
      <circle cx="46" cy="303" r="8" fill="#2a231c" />
      <path d="M50,190 Q56,168 80,166 L120,166 Q144,168 150,190 L160,360 Q160,372 148,372 L52,372 Q40,372 40,360 Z" fill="#5b5346" />
      <path d="M100,306 L100,372" fill="none" stroke="#4a4338" strokeWidth={2} />
      <path d="M70,288 L130,288 L130,297 L70,297 Z" fill="#4a4338" />
      <circle cx="76" cy="292.5" r="2.4" fill="#2a231c" />
      <circle cx="124" cy="292.5" r="2.4" fill="#2a231c" />
      <path d="M148,196 Q160,250 154,296" fill="none" stroke="#5b5346" strokeWidth={18} strokeLinecap="round" />
      <path d="M148,312 Q154,300 160,312" fill="none" stroke="#14110d" strokeWidth={3.5} strokeLinecap="round" />
      <path d="M138,312 L182,312 Q186,312 186,316 L186,354 Q186,358 182,358 L138,358 Q134,358 134,354 L134,316 Q134,312 138,312 Z" fill="#8a5a32" />
      <path d="M146,312 L146,358 M174,312 L174,358" fill="none" stroke="#4a3020" strokeWidth={3} />
      <circle cx="154" cy="303" r="8" fill="#2a231c" />
      <g transform={v.headT}>
      <g className="cast-rig__idle">
      <path d="M-30,10 Q0,26 30,10 L34,36 Q0,50 -34,36 Z" fill="#4a4338" />
      <path d="M-28,20 Q0,34 28,20 L28,28 Q0,42 -28,28 Z" fill="#9c2411" />
      <path d="M-38,10 C-40,-34 -20,-48 0,-48 C20,-48 40,-34 38,10 Z" fill="#1d3a8a" />
      <path d="M-39,-2 L39,-2 L39,12 L-39,12 Z" fill="#14285f" />
      <path d="M-26,-2 L-26,12 M-13,-2 L-13,12 M0,-2 L0,12 M13,-2 L13,12 M26,-2 L26,12" fill="none" stroke="#1d3a8a" strokeWidth={2} />
      <circle cx="0" cy="-52" r="11" fill="#f8f3e8" />
      </g>
      </g>
    </g>
  );
}

export const toi: RigDef = {
  id: 'user',
  name: 'Toi',
  head: [100, 150],
  crops: { full: [0, 0, 200, 420], bust: [10, 76, 180, 220], head: [40, 84, 120, 120] },
  idle: { kind: 'bob', seconds: 4, amount: 1.4 },
  faceless: true,
  Art: ToiArt,
};

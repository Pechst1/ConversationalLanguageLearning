/**
 * The episode card's drawing when the day has no graphic-novel picture (owner,
 * 2026-10-18): the place it happens in, drawn, and the people on its page in
 * front of it, the drawn cast as the reader stands them (PanelStage, flat).
 *
 * Six places cover the season's locations (`app/data/season/s1`): Le Mistral,
 * a flat, the stairwell, the canal outside, an office and the station. Drawn
 * like the location plates and the cast: flat fills, no outlines, the details
 * in a darker or lighter shade of the same colour. A place this file does not
 * know is Le Mistral, where most days happen. Decorative: the card's title and
 * byline say what the picture shows.
 */
import React, { useId } from 'react';

import { PanelStage, type StageMember } from '@/components/cast/PanelStage';

export type VignettePlace = 'cafe' | 'flat' | 'stairs' | 'canal' | 'office' | 'station';

const PLACE_OF: Record<string, VignettePlace> = {
  le_mistral: 'cafe',
  mistral_back_room: 'cafe',
  boulangerie: 'cafe',
  odile_flat: 'flat',
  user_apartment: 'flat',
  marin_lila_flat: 'flat',
  gus_loft: 'flat',
  ecole: 'flat',
  stairwell: 'stairs',
  quai_de_valmy: 'canal',
  rue_de_lancry: 'canal',
  marche_canal: 'canal',
  toit: 'canal',
  brocante: 'canal',
  buttes_chaumont: 'canal',
  marchand_office: 'office',
  mairie: 'office',
  notaire: 'office',
  office_admin: 'office',
  ngo_office: 'office',
  newsroom: 'office',
  gare_de_lest: 'station',
  metro_platform: 'station',
};

const PLACE_WORDS: Array<[RegExp, VignettePlace]> = [
  [/gare|m[ée]tro|station|train|quai de la gare/i, 'station'],
  [/escalier|stair/i, 'stairs'],
  [/office|bureau|mairie|notaire|g[ée]rance|admin/i, 'office'],
  [/quai|canal|rue|toit|parc|march[ée]|brocante|dehors|outdoor/i, 'canal'],
  [/flat|appart|loft|chez|classe|[ée]cole|chambre/i, 'flat'],
];

/** The drawn place for a scenario's location: its id first, then its words. */
export function vignettePlace(locationId?: string | null, locationName?: string | null): VignettePlace {
  const id = String(locationId || '').trim().toLowerCase();
  if (id && PLACE_OF[id]) return PLACE_OF[id];
  const words = `${id} ${String(locationName || '')}`;
  for (const [pattern, place] of PLACE_WORDS) if (pattern.test(words)) return place;
  return 'cafe';
}

export function EpisodeVignette({
  place,
  cast,
  still = false,
}: {
  place: VignettePlace;
  /** Who is on today's page, lead first. Toi and people with no drawing are left out. */
  cast: StageMember[];
  still?: boolean;
}) {
  return (
    <div className="journey-vignette" data-vignette={place}>
      <PlaceDrawing place={place} />
      <PanelStage members={cast} light={false} plateUrl={null} aspect={16 / 9} still={still} />
    </div>
  );
}

function PlaceDrawing({ place }: { place: VignettePlace }) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '');
  const body =
    place === 'flat' ? <Flat /> :
    place === 'stairs' ? <Stairs /> :
    place === 'canal' ? <Canal /> :
    place === 'office' ? <Office /> :
    place === 'station' ? <Station /> :
    <Cafe uid={uid} />;
  return (
    <svg className="journey-vignette__place" viewBox="0 0 320 180" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      {body}
    </svg>
  );
}

/** Le Mistral: the zinc, the bottles, the mirror, the red banquette, the night window. */
function Cafe({ uid }: { uid: string }) {
  const floor = `vignette-floor-${uid}`;
  return (
    <g>
      <defs>
        <pattern id={floor} width="16" height="16" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="16" height="16" fill="#efe8da" />
          <rect width="8" height="8" fill="#2a231c" />
          <rect x="8" y="8" width="8" height="8" fill="#2a231c" />
        </pattern>
      </defs>
      <rect width="320" height="180" fill="#efe6d2" />
      {/* the night window, its lit façades and the half curtain */}
      <rect x="236" y="0" width="84" height="132" fill="#1d2f6b" />
      <rect x="246" y="22" width="30" height="60" fill="#29408a" />
      <rect x="282" y="12" width="38" height="70" fill="#29408a" />
      {[[250, 30], [262, 30], [250, 46], [262, 58], [288, 22], [302, 22], [288, 40], [302, 56], [288, 58]].map(([x, y]) => (
        <rect key={`${x}-${y}`} x={x} y={y} width="7" height="9" fill="#f3c318" />
      ))}
      <rect x="236" y="0" width="5" height="132" fill="#2c6a5d" />
      <rect x="236" y="84" width="84" height="48" fill="#f8f3e8" />
      <path d="M244,84 L244,132 M256,84 L256,132 M268,84 L268,132 M280,84 L280,132 M292,84 L292,132 M304,84 L304,132" stroke="#e3d8c3" strokeWidth="3" />
      <rect x="236" y="81" width="84" height="4" fill="#c49a0a" />
      {/* the bottle shelves */}
      <rect x="0" y="0" width="74" height="104" fill="#2a231c" />
      <rect x="0" y="34" width="74" height="4" fill="#c49a0a" />
      <rect x="0" y="70" width="74" height="4" fill="#c49a0a" />
      {[[6, '#2c6a5d'], [16, '#c8432b'], [26, '#1d3a8a'], [38, '#f3c318'], [50, '#2c6a5d'], [60, '#c8432b']].map(([x, colour]) => (
        <g key={`a${x}`}>
          <rect x={Number(x)} y="12" width="7" height="22" rx="2" fill={String(colour)} />
          <rect x={Number(x) + 2} y="6" width="3" height="7" fill={String(colour)} />
        </g>
      ))}
      {[[8, '#1d3a8a'], [20, '#f3c318'], [32, '#2c6a5d'], [44, '#c8432b'], [58, '#f8f3e8']].map(([x, colour]) => (
        <g key={`b${x}`}>
          <rect x={Number(x)} y="48" width="8" height="22" rx="2" fill={String(colour)} />
          <rect x={Number(x) + 2.5} y="42" width="3" height="7" fill={String(colour)} />
        </g>
      ))}
      {/* the mirror and its sign */}
      <rect x="120" y="22" width="62" height="70" fill="#c49a0a" />
      <rect x="125" y="27" width="52" height="60" fill="#3f6f63" />
      <path d="M131,80 L150,34 L158,34 L139,80 Z" fill="#5b8a7c" />
      <text x="151" y="15" textAnchor="middle" fontFamily="Georgia, serif" fontStyle="italic" fontWeight="700" fontSize="13" fill="#d8321a">Le Mistral</text>
      {/* the pendant lamp */}
      <path d="M98,0 L98,22" stroke="#2a231c" strokeWidth="1.5" />
      <path d="M84,34 Q98,14 112,34 Z" fill="#c49a0a" />
      <ellipse cx="98" cy="35" rx="9" ry="2.6" fill="#f8e7a1" />
      {/* the banquette, the dado and the floor */}
      <rect x="132" y="96" width="104" height="26" rx="6" fill="#c8432b" />
      <rect x="132" y="112" width="104" height="10" fill="#a3341f" />
      <rect x="0" y="122" width="320" height="22" fill="#2c6a5d" />
      <rect x="0" y="122" width="320" height="3" fill="#c49a0a" />
      <rect x="0" y="144" width="320" height="36" fill={`url(#${floor})`} />
      {/* the zinc and a table */}
      <path d="M0,112 L104,118 Q116,119 116,130 L116,180 L0,180 Z" fill="#2c6a5d" />
      <path d="M0,106 L106,112 Q120,113 120,122 L0,118 Z" fill="#d6d1c6" />
      <path d="M0,130 L112,136" stroke="#c49a0a" strokeWidth="2" />
      <ellipse cx="270" cy="146" rx="26" ry="6" fill="#f8f3e8" />
      <rect x="268" y="150" width="4" height="26" fill="#c49a0a" />
      <ellipse cx="270" cy="177" rx="12" ry="3" fill="#a07c08" />
      <rect x="262" y="136" width="9" height="10" rx="1" fill="#f8f3e8" />
      <rect x="262" y="136" width="9" height="3" fill="#b07a4e" />
    </g>
  );
}

/** Odile's flat: shutters on the canal, the green coat on its hook, a lamp. */
function Flat() {
  return (
    <g>
      <rect width="320" height="180" fill="#f1e9d6" />
      <rect x="0" y="0" width="320" height="10" fill="#e6dcc4" />
      {/* the tall window and its shutters */}
      <rect x="112" y="18" width="96" height="116" fill="#c49a0a" />
      <rect x="118" y="24" width="84" height="110" fill="#1d3a8a" />
      <path d="M118,98 L132,84 L146,92 L160,78 L176,90 L190,80 L202,88 L202,134 L118,134 Z" fill="#29408a" />
      {[[128, 104], [150, 98], [178, 102], [192, 112]].map(([x, y]) => (
        <rect key={`${x}-${y}`} x={x} y={y} width="6" height="8" fill="#f3c318" />
      ))}
      <rect x="158" y="24" width="4" height="110" fill="#c49a0a" />
      <path d="M124,118 L196,118 M124,126 L196,126" stroke="#14110d" strokeWidth="2" />
      <rect x="86" y="18" width="24" height="116" fill="#2c6a5d" />
      <rect x="210" y="18" width="24" height="116" fill="#2c6a5d" />
      {[30, 44, 58, 72, 86, 100, 114].map((y) => (
        <g key={y}>
          <rect x="89" y={y} width="18" height="4" fill="#1f4f45" />
          <rect x="213" y={y} width="18" height="4" fill="#1f4f45" />
        </g>
      ))}
      {/* the coat on its hook */}
      <circle cx="40" cy="38" r="3" fill="#c49a0a" />
      <path d="M40,40 L26,52 Q20,92 24,118 L56,118 Q60,92 54,52 Z" fill="#2c6a5d" />
      <path d="M40,40 L34,58 L40,64 L46,58 Z" fill="#1f4f45" />
      <path d="M40,64 L40,116" stroke="#1f4f45" strokeWidth="2" />
      {/* the lamp and a shelf of books */}
      <path d="M262,72 L292,72 L300,96 L254,96 Z" fill="#f3c318" />
      <rect x="275" y="96" width="4" height="40" fill="#2a231c" />
      <path d="M248,40 L304,40" stroke="#2c6a5d" strokeWidth="4" />
      {[['#c8432b', 6, 18], ['#1d3a8a', 5, 22], ['#f3c318', 7, 16], ['#2c6a5d', 5, 20]].map(([colour, w, hgt], index) => (
        <rect key={index} x={254 + index * 9} y={38 - Number(hgt)} width={Number(w)} height={Number(hgt)} fill={String(colour)} />
      ))}
      {/* the red floor and the skirting */}
      <rect x="0" y="134" width="320" height="6" fill="#2c6a5d" />
      <rect x="0" y="140" width="320" height="40" fill="#c8432b" />
      <path d="M0,160 L320,150" stroke="#b33a24" strokeWidth="10" />
    </g>
  );
}

/** The stairwell: worn steps, the timed light, the brass «1» on Odile's door. */
function Stairs() {
  return (
    <g>
      <rect width="320" height="180" fill="#ece0c3" />
      <rect x="0" y="0" width="320" height="70" fill="#e3d2ac" />
      {/* the door with its brass number */}
      <rect x="196" y="26" width="72" height="154" fill="#2c6a5d" />
      <rect x="204" y="36" width="56" height="58" fill="#1f4f45" />
      <rect x="204" y="102" width="56" height="70" fill="#1f4f45" />
      <circle cx="258" cy="104" r="4" fill="#c49a0a" />
      <text x="232" y="74" textAnchor="middle" fontFamily="Georgia, serif" fontWeight="700" fontSize="26" fill="#c49a0a">1</text>
      {/* the steps going up, and the banister */}
      <path d="M0,180 L0,150 L30,150 L30,132 L60,132 L60,114 L90,114 L90,96 L120,96 L120,78 L150,78 L150,60 L180,60 L180,180 Z" fill="#a8743f" />
      <path d="M0,150 L30,150 L30,154 L0,154 Z M30,132 L60,132 L60,136 L30,136 Z M60,114 L90,114 L90,118 L60,118 Z M90,96 L120,96 L120,100 L90,100 Z M120,78 L150,78 L150,82 L120,82 Z M150,60 L180,60 L180,64 L150,64 Z" fill="#c8915a" />
      <path d="M6,118 L170,24" stroke="#2a231c" strokeWidth="5" strokeLinecap="round" />
      {[[16, 112, 148], [46, 95, 130], [76, 78, 112], [106, 61, 94], [136, 44, 76]].map(([x, top, bottom]) => (
        <path key={x} d={`M${x},${top} L${x},${bottom}`} stroke="#2a231c" strokeWidth="2.5" />
      ))}
      {/* the minuterie and its light */}
      <rect x="282" y="58" width="14" height="18" rx="2" fill="#f8f3e8" />
      <circle cx="289" cy="67" r="4" fill="#d8321a" />
      <path d="M100,0 L100,16" stroke="#2a231c" strokeWidth="1.5" />
      <circle cx="100" cy="22" r="8" fill="#f8e7a1" />
    </g>
  );
}

/** The quai de Valmy: plane trees, the green iron footbridge, black water, the red neon. */
function Canal() {
  return (
    <g>
      <rect width="320" height="180" fill="#f2e3b8" />
      {/* the façades across the canal */}
      <rect x="0" y="34" width="320" height="64" fill="#efe6d2" />
      {[10, 52, 94, 136, 178, 220, 262, 300].map((x) => (
        <g key={x}>
          <rect x={x} y="44" width="12" height="16" fill="#1d3a8a" />
          <rect x={x} y="70" width="12" height="16" fill="#1d3a8a" />
          <rect x={x - 2} y="60" width="16" height="3" fill="#2a231c" />
        </g>
      ))}
      <rect x="0" y="28" width="320" height="8" fill="#b9ae96" />
      {/* plane trees */}
      {[[30, 30], [120, 22], [250, 26]].map(([x, y]) => (
        <g key={x}>
          <circle cx={x} cy={y} r="26" fill="#2c6a5d" />
          <circle cx={x + 22} cy={y + 10} r="20" fill="#3f8a6a" />
          <circle cx={x - 18} cy={y + 14} r="16" fill="#c49a0a" />
          <rect x={x - 2} y={y + 20} width="5" height="80" fill="#6e675b" />
        </g>
      ))}
      {/* the water and the footbridge */}
      <rect x="0" y="98" width="320" height="44" fill="#1f4f45" />
      <path d="M0,112 L320,112 M0,126 L320,126" stroke="#2c6a5d" strokeWidth="3" strokeDasharray="22 14" />
      <path d="M96,98 Q170,44 244,98 L236,98 Q170,56 104,98 Z" fill="#2c6a5d" />
      <path d="M100,86 L240,86" stroke="#2c6a5d" strokeWidth="4" />
      {[118, 136, 154, 172, 190, 208, 226].map((x) => (
        <path key={x} d={`M${x},86 L${x},${x < 170 ? 98 - (x - 104) * 0.45 : 98 - (236 - x) * 0.45}`} stroke="#2c6a5d" strokeWidth="2" />
      ))}
      {/* the quai, a bollard and the neon */}
      <rect x="0" y="142" width="320" height="38" fill="#d8cdb4" />
      <rect x="0" y="142" width="320" height="5" fill="#b9ae96" />
      <path d="M40,150 L40,170 M40,158 L80,156" stroke="#2a231c" strokeWidth="3" />
      <rect x="276" y="146" width="12" height="18" rx="5" fill="#2a231c" />
      <rect x="258" y="4" width="58" height="20" rx="3" fill="#2a231c" />
      <text x="287" y="19" textAnchor="middle" fontFamily="Inter, Arial, sans-serif" fontWeight="800" fontSize="10" letterSpacing="0.5" fill="#ff6a4d">MISTRAL</text>
    </g>
  );
}

/** The gérance and the mairie: key boards, a filing cabinet, the desk lamp. */
function Office() {
  return (
    <g>
      <rect width="320" height="180" fill="#e9e4d6" />
      {/* the key board */}
      <rect x="20" y="20" width="108" height="76" fill="#a8743f" />
      <rect x="26" y="26" width="96" height="64" fill="#c8915a" />
      {[0, 1, 2, 3].map((row) => [0, 1, 2, 3, 4, 5].map((col) => (
        <g key={`${row}-${col}`}>
          <circle cx={36 + col * 15} cy={34 + row * 15} r="1.8" fill="#2a231c" />
          <path d={`M${36 + col * 15},${36 + row * 15} L${36 + col * 15},${44 + row * 15}`} stroke={(row + col) % 3 === 0 ? '#c49a0a' : '#6e675b'} strokeWidth="2.4" />
        </g>
      )))}
      {/* the window with its blind */}
      <rect x="150" y="16" width="70" height="80" fill="#1d3a8a" />
      {[24, 34, 44, 54].map((y) => <rect key={y} x="150" y={y} width="70" height="5" fill="#f8f3e8" />)}
      <rect x="150" y="14" width="70" height="4" fill="#6e675b" />
      {/* the grey cabinet */}
      <rect x="240" y="40" width="62" height="140" fill="#9aa0a3" />
      {[52, 92, 132].map((y) => (
        <g key={y}>
          <rect x="246" y={y} width="50" height="34" fill="#b4b9bb" />
          <rect x="264" y={y + 12} width="14" height="4" fill="#5b5346" />
        </g>
      ))}
      {/* the desk, the lamp and the papers */}
      <rect x="0" y="120" width="320" height="60" fill="#d8cdb4" />
      <rect x="10" y="112" width="214" height="12" fill="#6b4a2c" />
      <rect x="18" y="124" width="10" height="56" fill="#5a3d24" />
      <rect x="206" y="124" width="10" height="56" fill="#5a3d24" />
      <path d="M186,112 L186,86 L170,74" stroke="#2c6a5d" strokeWidth="4" strokeLinecap="round" />
      <path d="M156,80 L172,64 L184,78 Z" fill="#2c6a5d" />
      <rect x="40" y="104" width="34" height="8" fill="#f8f3e8" />
      <rect x="44" y="98" width="30" height="7" fill="#f3c318" />
      <path d="M100,112 L132,108 L134,112 Z" fill="#14110d" />
    </g>
  );
}

/** The Gare de l'Est: the glass roof, the long white train, the platform clock. */
function Station() {
  return (
    <g>
      <rect width="320" height="180" fill="#dfe3df" />
      {/* the glass roof */}
      <path d="M0,70 Q160,-30 320,70 L320,0 L0,0 Z" fill="#6e7a7d" />
      <path d="M0,70 Q160,-22 320,70" fill="none" stroke="#2a231c" strokeWidth="4" />
      {[40, 80, 120, 160, 200, 240, 280].map((x) => (
        <path key={x} d={`M${x},${x < 160 ? 70 - (x / 160) * 50 : 70 - ((320 - x) / 160) * 50} L${x},0`} stroke="#2a231c" strokeWidth="2" />
      ))}
      <path d="M0,40 Q160,-46 320,40" fill="none" stroke="#2a231c" strokeWidth="2" />
      {/* the clock */}
      <circle cx="160" cy="34" r="12" fill="#f8f3e8" />
      <path d="M160,34 L160,26 M160,34 L166,37" stroke="#14110d" strokeWidth="2" strokeLinecap="round" />
      {/* the train */}
      <path d="M20,84 L268,84 Q300,84 312,112 L312,128 L20,128 Z" fill="#f8f3e8" />
      <rect x="20" y="114" width="292" height="7" fill="#1d3a8a" />
      <rect x="20" y="121" width="292" height="3" fill="#d8321a" />
      {[34, 76, 118, 160, 202, 244].map((x) => <rect key={x} x={x} y="92" width="30" height="14" rx="3" fill="#29408a" />)}
      <path d="M276,92 L296,92 Q304,98 306,106 L276,106 Z" fill="#29408a" />
      {/* the platform and its edge */}
      <rect x="0" y="128" width="320" height="52" fill="#c9c2b0" />
      <rect x="0" y="128" width="320" height="5" fill="#f3c318" />
      <rect x="40" y="138" width="4" height="40" fill="#2a231c" />
      <rect x="28" y="136" width="28" height="12" fill="#1d3a8a" />
    </g>
  );
}

export default EpisodeVignette;

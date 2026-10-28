/**
 * Le Quartier · la carte: Paris as La Carte draws it, and the places of the game on it.
 *
 * The twenty arrondissements and the Seine are La Carte's own drawing (`world/paris.json`, synced
 * from public/assets/carte/paris.svg) and every point goes through La Carte's projection, so a pin
 * here and a pin there are the same corner of Paris. The canal comes from open map data. Each place
 * of the world registry is a pin: the open ones solid, the ones the forge is building under
 * scaffolding, the season's places faint until the story gets there.
 */
import React from 'react';

import { projectPoint } from '@/components/carte/carte-projection';
import type { Words } from '@/lib/quartier/memory';
import type { Native } from '@/lib/quartier/stage';
import { mapPlaces } from '@/lib/quartier/world';
import type { WorldPlace } from '@/lib/quartier/world';
import paris from '@/lib/quartier/world/paris.json';

interface Paris {
  viewBox: number[];
  arr: Array<{ code: string; n: number; name: string; d: string; label: { text: string; x: number; y: number } | null }>;
  seine: string;
  canal: { open: Array<Array<[number, number]>>; covered: Array<Array<[number, number]>> };
}

const PARIS = paris as unknown as Paris;

export interface QuartierMapProps {
  native: Native;
  translate: boolean;
  /** where you are now */
  here: string;
  /** what you know of each place (`Memory.places()`) */
  been: Record<string, string>;
  /** go there: offered for open places that have a site, and for home */
  onGo?: (id: string) => void;
  onClose: () => void;
}

type XY = [number, number];

const toXY = (lat: number, lon: number) => projectPoint('paris', lat, lon);

const path = (pts: Array<[number, number]>) =>
  pts
    .map(([lat, lon]) => toXY(lat, lon))
    .filter((p): p is XY => Boolean(p))
    .map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`)
    .join(' ');

const CANAL_OPEN = PARIS.canal.open.map(path);
const CANAL_COVERED = PARIS.canal.covered.map(path);

/** The square around the pins, padded, and never closer than `min` units across. */
function around(points: XY[], pad: number, min: number): [number, number, number, number] {
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  points.forEach(([x, y]) => {
    x0 = Math.min(x0, x);
    y0 = Math.min(y0, y);
    x1 = Math.max(x1, x);
    y1 = Math.max(y1, y);
  });
  const side = Math.max(min, x1 - x0 + pad * 2, y1 - y0 + pad * 2);
  return [(x0 + x1) / 2 - side / 2, (y0 + y1) / 2 - side / 2, side, side];
}

function tagOf(p: WorldPlace, here: string, been: string | undefined) {
  if (p.id === here) return 'Tu es ici';
  if (p.status === 'en_chantier') return 'En chantier';
  if (p.status === 'locked') return 'Plus tard';
  if (been === 'visited') return 'Tu connais';
  if (been === 'noticed') return 'On t’en a parlé';
  return 'À découvrir';
}

export function QuartierMap({ native, translate, here, been, onGo, onClose }: QuartierMapProps) {
  const pins = React.useMemo(
    () =>
      mapPlaces()
        .map((p) => ({ p, xy: toXY(p.lat, p.lon) }))
        .filter((x): x is { p: WorldPlace; xy: XY } => Boolean(x.xy)),
    [],
  );
  const [whole, setWhole] = React.useState(false);
  const [picked, setPicked] = React.useState<string>(here);
  const box = whole ? [0, 0, 1000, 544.4] : around(pins.map((x) => x.xy), 34, 150);
  const u = box[2] / 100;
  const sel = pins.find((x) => x.p.id === picked)?.p ?? null;
  const tr = (w: Words) => (translate ? <small>{w[native]}</small> : null);

  return (
    <div className="qz-map" role="dialog" aria-label="La carte">
      <div className="qz-map-page">
        <header className="qz-carnet-head">
          <h1 className="qz-h">La carte</h1>
          <button type="button" className="qz-x" aria-label="Fermer" onClick={onClose}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </header>
        <div className="qz-map-frame" data-whole={whole}>
          <svg viewBox={box.join(' ')} preserveAspectRatio="xMidYMid meet" role="img" aria-label="Paris, et les lieux de ton histoire">
            <g className="qz-map-land">
              {PARIS.arr.map((a) => (
                <path key={a.code} d={a.d} />
              ))}
            </g>
            <path className="qz-map-seine" d={PARIS.seine} style={{ strokeWidth: whole ? 7 : 3.4 }} />
            {CANAL_COVERED.map((d, i) => (
              <path key={`c${i}`} className="qz-map-canal qz-map-canal--covered" d={d} style={{ strokeWidth: u * 0.45, strokeDasharray: `${u * 0.9} ${u * 0.9}` }} />
            ))}
            {CANAL_OPEN.map((d, i) => (
              <path key={`o${i}`} className="qz-map-canal" d={d} style={{ strokeWidth: u * 0.75 }} />
            ))}
            <g className="qz-map-labels" style={{ fontSize: u * (whole ? 2.6 : 3.1) }}>
              {PARIS.arr.map((a) =>
                a.label ? (
                  <text key={a.code} x={a.label.x} y={a.label.y} textAnchor="middle" dominantBaseline="central">
                    {a.label.text}
                  </text>
                ) : null,
              )}
            </g>
            {pins.map(({ p, xy }) => (
              <g
                key={p.id}
                className="qz-pin"
                data-status={p.status}
                data-here={p.id === here || undefined}
                data-picked={p.id === picked || undefined}
                transform={`translate(${xy[0].toFixed(1)} ${xy[1].toFixed(1)})`}
                onClick={() => setPicked(p.id)}
              >
                <circle className="qz-pin-hit" r={u * 5} />
                {p.id === here ? <circle className="qz-pin-ring" r={u * 3.2} style={{ strokeWidth: u * 0.5 }} /> : null}
                <circle className="qz-pin-dot" r={u * 1.7} style={{ strokeWidth: u * 0.45 }} />
                {p.status === 'en_chantier' ? (
                  <path className="qz-pin-scaffold" d={`M${-u * 1.2} ${u * 1.2}L${u * 1.2} ${-u * 1.2}M${-u * 1.2} ${-u * 1.2}L${u * 1.2} ${u * 1.2}`} style={{ strokeWidth: u * 0.35 }} />
                ) : null}
                <text x={u * 2.6} y={u * 0.1} dominantBaseline="central" style={{ fontSize: u * 3.4, strokeWidth: u * 0.9 }}>
                  {p.name.fr}
                </text>
              </g>
            ))}
          </svg>
          <button type="button" className="qz-quiet qz-map-zoom" onClick={() => setWhole(!whole)}>
            {whole ? 'Ton quartier' : 'Tout Paris'}
          </button>
        </div>
        {sel ? (
          <div className="qz-map-card" data-status={sel.status}>
            <p className="qz-tag">{tagOf(sel, here, been[sel.id])}</p>
            <h2 lang="fr">
              {sel.name.fr}
              {tr(sel.name)}
            </h2>
            <p lang="fr">
              {sel.why.fr}
              {tr(sel.why)}
            </p>
            {sel.ride && sel.status === 'open' && sel.id !== here ? (
              <p className="qz-ride" lang="fr">
                {sel.ride.fr}
                {tr(sel.ride)}
              </p>
            ) : null}
            {sel.status === 'en_chantier' ? (
              <p className="qz-note">Ce coin de Paris se construit en ce moment, rue par rue, d’après les données ouvertes de la carte.</p>
            ) : null}
            {onGo && sel.status === 'open' && (sel.site || sel.kind === 'home') && sel.id !== here ? (
              <button type="button" className="qz-primary qz-wide" onClick={() => onGo(sel.id)}>
                Y aller
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

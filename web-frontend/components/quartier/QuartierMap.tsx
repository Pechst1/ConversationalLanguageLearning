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
import { LABEL, placeLabels, spreadPins } from '@/lib/quartier/map-labels';
import type { PlacedLabel } from '@/lib/quartier/map-labels';
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

/** The frame «Ton quartier» shows: the square around the pins, padded, never under 150 units across. */
export function quarterBox(points: XY[]): [number, number, number, number] {
  return around(points, 34, 150);
}

/** «Tout Paris»: La Carte's whole drawing. */
export const WHOLE_BOX: [number, number, number, number] = [0, 0, 1000, 544.4];

/** Where each pin is drawn in `box`: its place, moved just enough that no pin touches another (`spreadPins`). */
export function pinsIn<T extends { p: WorldPlace; xy: XY }>(pins: T[], box: [number, number, number, number], here: string): T[] {
  const at = spreadPins(
    pins.map(({ p, xy }) => ({ id: p.id, xy, here: p.id === here })),
    box[2] / 100,
  );
  return pins.map((x) => ({ ...x, xy: at.get(x.p.id) ?? x.xy }));
}

/** The pins' names, placed so none runs over another or off the frame (`map-labels.ts`). */
export function labelsFor(pins: Array<{ p: WorldPlace; xy: XY }>, box: [number, number, number, number], here: string) {
  const rank = (p: WorldPlace) => (p.id === here ? 0 : p.status === 'open' ? 1 : p.status === 'en_chantier' ? 2 : 3);
  return placeLabels(
    pins.map(({ p, xy }) => ({ id: p.id, name: p.name.fr, xy, rank: rank(p) })),
    box,
    box[2] / 100,
  );
}

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

/** A pin's name where `placeLabels` put it (relative to the pin), or none when no place was free. */
function PinLabel({ at, label, u }: { at: XY; label: PlacedLabel | undefined; u: number }) {
  if (!label) return null;
  return (
    <text x={(label.x - at[0]).toFixed(1)} y={(label.y - at[1]).toFixed(1)} textAnchor={label.anchor} dominantBaseline="central" style={{ fontSize: u * LABEL.size, strokeWidth: u * 0.9 }}>
      {label.text}
    </text>
  );
}

export function QuartierMap({ native, translate, here, been, onGo, onClose }: QuartierMapProps) {
  const placed = React.useMemo(
    () =>
      mapPlaces()
        .map((p) => ({ p, xy: toXY(p.lat, p.lon) }))
        .filter((x): x is { p: WorldPlace; xy: XY } => Boolean(x.xy)),
    [],
  );
  const [whole, setWhole] = React.useState(false);
  const [picked, setPicked] = React.useState<string>(here);
  const box = whole ? WHOLE_BOX : quarterBox(placed.map((x) => x.xy));
  const u = box[2] / 100;
  // the pins as drawn at this zoom: none touches another
  const pins = React.useMemo(() => pinsIn(placed, box, here), [placed, box[0], box[1], box[2], box[3], here]); // eslint-disable-line react-hooks/exhaustive-deps
  const labels = React.useMemo(() => new Map(labelsFor(pins, box, here).map((l) => [l.id, l])), [pins, box[0], box[1], box[2], box[3], here]); // eslint-disable-line react-hooks/exhaustive-deps
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
                <PinLabel at={xy} label={labels.get(p.id)} u={u} />
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

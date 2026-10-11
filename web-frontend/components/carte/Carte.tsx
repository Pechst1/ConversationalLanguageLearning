/**
 * WP-120 §5.2 · La Carte: the learner's Papiers on a drawing of France that opens
 * onto the Île-de-France and Paris.
 *
 * The drawing is a static SVG (`public/assets/carte/<level>.svg`, fetched once and
 * inlined, decorative); the pins are real buttons laid over it at the projected
 * point (`carte-projection.ts`), in tab order, oldest Papier first. Each pin is the
 * Papier's vignette at 28 px (or a plain ink pin before one was minted), with a
 * dotted ring when the place is only known to the city, a wider one for a region.
 * Marks that overlap cluster into an ink disc with the count: a tap zooms one level
 * when the whole cluster is on the next drawing, else lists its Papiers. «France» in
 * the corner (and Escape) zooms back out. «Mon quartier», the season's places
 * already lived, toggles on the Paris level only. Level changes fade in, not under
 * reduced motion.
 *
 * WP-121 A.2: a pin (or a cluster) holding due words carries a small ink dot on its
 * ring — a dot, never a number (the number is in the card); static under reduced
 * motion. The card's first row then offers «Réviser ici».
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { BottomSheet, Chip } from '@/components/atelier-v2/ui';
import { ArrowLeftIcon } from '@/components/atelier-v2/ui/Shapes';
import { WordHelpSheet, type WordHelpRequest } from '@/components/feuilleton/reader/WordHelpSheet';
import { RvVignette } from '@/components/revue/RvVignette';
import type { CarteLanguage, CarteLevel, CartePin, CarteQuartierPlace } from '@/lib/carte-types';

import type { CarteCopy } from './carte-copy';
import {
  DEFAULT_MAP_PX,
  clusterTarget,
  layoutLevel,
  previousLevel,
  weekNo,
  type Cluster,
} from './carte-model';
import { drawingUrl } from './carte-projection';
import { CartePinCard } from './CartePinCard';
import { clusterDue } from './palais-model';

const drawingCache = new Map<CarteLevel, Promise<string>>();

function loadDrawing(level: CarteLevel): Promise<string> {
  let pending = drawingCache.get(level);
  if (!pending) {
    pending = fetch(drawingUrl(level)).then((response) => {
      if (!response.ok) throw new Error(`carte drawing ${response.status}`);
      return response.text();
    });
    pending.catch(() => drawingCache.delete(level));
    drawingCache.set(level, pending);
  }
  return pending;
}

const ARTICLE = /^(?:le|la|les|un|une|des|du|de la|l['’])\s*/i;

function wordRequest(word: string, pin: CartePin): WordHelpRequest {
  return { surface: word, term: word.replace(ARTICLE, '').trim() || word, sentence: pin.headlineFr };
}

const pct = (value: number, total: number) => `${((value / total) * 100).toFixed(3)}%`;

export type CarteProps = {
  pins: readonly CartePin[];
  quartier?: readonly CarteQuartierPlace[];
  copy: CarteCopy;
  language?: CarteLanguage;
  onRelire: (pin: CartePin) => void;
  onReleve: (pin: CartePin) => void;
  /** WP-121 A.3: «Réviser ici» on a pin with due words. */
  onReview?: (pin: CartePin) => void;
  /** WP-121 B: «Relire ta question» / «Relue le …». */
  onRelecture?: (pin: CartePin) => void;
  initialLevel?: CarteLevel;
  /** Tests and the first paint: the drawing's markup per level (else fetched). */
  drawings?: Partial<Record<CarteLevel, string>>;
  /** Tests: the map's width in CSS px (else measured). */
  mapPx?: number;
  /** Tests: a pin's card open on first render. */
  initialPinId?: string | null;
  /** WP-120 phase D · `/carte?focus=<session_id>`: that Papier's card open on load, on its own level. */
  focusSessionId?: string | null;
  initialQuartier?: boolean;
};

export function Carte({
  pins,
  quartier = [],
  copy,
  language = 'fr',
  onRelire,
  onReleve,
  onReview,
  onRelecture,
  initialLevel = 'france',
  drawings,
  mapPx: fixedPx,
  initialPinId = null,
  focusSessionId = null,
  initialQuartier = false,
}: CarteProps) {
  const focusPin = focusSessionId ? pins.find((p) => p.sessionId === focusSessionId) ?? null : null;
  const [level, setLevel] = useState<CarteLevel>(focusPin?.level ?? initialLevel);
  const [svg, setSvg] = useState<Partial<Record<CarteLevel, string>>>(drawings ?? {});
  const [measured, setMeasured] = useState<number>(fixedPx ?? DEFAULT_MAP_PX);
  const [showQuartier, setShowQuartier] = useState(initialQuartier);
  const [openPin, setOpenPin] = useState<CartePin | null>(() => focusPin ?? pins.find((p) => p.sessionId === initialPinId) ?? null);
  const [list, setList] = useState<Cluster<CartePin> | null>(null);
  const [place, setPlace] = useState<Cluster<CarteQuartierPlace> | null>(null);
  const [word, setWord] = useState<WordHelpRequest | null>(null);
  const mapRef = useRef<HTMLDivElement>(null);

  // The drawing: inlined from the static asset, once per level per page load.
  useEffect(() => {
    if (svg[level]) return undefined;
    let alive = true;
    loadDrawing(level)
      .then((text) => alive && setSvg((current) => ({ ...current, [level]: text })))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [level, svg]);

  // Clusters are decided in screen pixels: measure the map.
  useEffect(() => {
    if (fixedPx || !mapRef.current || typeof ResizeObserver === 'undefined') return undefined;
    const node = mapRef.current;
    const observer = new ResizeObserver(() => setMeasured(node.clientWidth || DEFAULT_MAP_PX));
    observer.observe(node);
    setMeasured(node.clientWidth || DEFAULT_MAP_PX);
    return () => observer.disconnect();
  }, [fixedPx]);

  const layout = useMemo(
    () => layoutLevel(level, pins, { mapPx: fixedPx ?? measured, quartier: showQuartier ? quartier : [] }),
    [level, pins, fixedPx, measured, showQuartier, quartier],
  );

  const zoomOut = useCallback(() => setLevel('france'), []);
  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape' && level !== 'france' && !openPin && !list && !place && !word) {
      event.preventDefault();
      setLevel(previousLevel(level) ?? 'france');
    }
  };

  const tapCluster = (cluster: Cluster<CartePin>) => {
    const target = clusterTarget(level, cluster);
    if (target.kind === 'zoom') setLevel(target.level);
    else setList(cluster);
  };

  const count = layout.clusters.reduce((sum, c) => sum + c.members.length, 0);
  const marks = [...layout.clusters].sort((a, b) => a.y - b.y || a.x - b.x);

  return (
    <section className="carte" data-level={level} aria-label={copy.map_label} onKeyDown={onKeyDown}>
      <header className="carte__bar">
        <div className="carte__where">
          <h2 className="carte__level" lang="fr">
            {copy.level_name[level]}
          </h2>
          <p className="carte__count" aria-live="polite">
            {copy.count_pins(count)}
          </p>
        </div>
        <div className="carte__tools">
          {level === 'paris' && quartier.length > 0 && (
            <Chip
              tone={showQuartier ? 'story' : 'plain'}
              aria-pressed={showQuartier}
              title={copy.quartier_hint}
              onClick={() => setShowQuartier((value) => !value)}
              className="carte__quartier-toggle"
            >
              <span lang="fr">{copy.quartier_toggle}</span>
            </Chip>
          )}
          {level !== 'france' && (
            <button type="button" className="av2-chip carte__france" onClick={zoomOut} aria-label={copy.zoom_out_label}>
              <ArrowLeftIcon size={14} />
              <span lang="fr">{copy.zoom_out_france}</span>
            </button>
          )}
        </div>
      </header>

      <div
        ref={mapRef}
        key={level}
        className="carte__map"
        data-level={level}
        style={{ aspectRatio: `${layout.width} / ${layout.height}` }}
      >
        <div className="carte__drawing" aria-hidden="true" dangerouslySetInnerHTML={{ __html: svg[level] ?? '' }} />
        <ol className="carte__marks">
          {marks.map((cluster) => {
            const style = { left: pct(cluster.x, layout.width), top: pct(cluster.y, layout.height) };
            if (cluster.members.length > 1) {
              const due = clusterDue(cluster);
              return (
                <li key={`c-${cluster.id}`} className="carte__mark" style={style}>
                  <button
                    type="button"
                    className="carte-cluster"
                    data-count={cluster.members.length}
                    data-due={due > 0 ? '' : undefined}
                    aria-label={[copy.cluster_label(cluster.members.length), due > 0 ? copy.due_pin_label(due) : null].filter(Boolean).join(' · ')}
                    onClick={() => tapCluster(cluster)}
                  >
                    <span aria-hidden="true">{cluster.members.length}</span>
                    {due > 0 && <i className="carte-due-dot" aria-hidden="true" />}
                  </button>
                </li>
              );
            }
            const pin = cluster.members[0].item;
            return (
              <li key={pin.sessionId} className="carte__mark" style={style}>
                <button
                  type="button"
                  className="carte-pin"
                  data-precision={pin.precision}
                  data-session={pin.sessionId}
                  data-due={pin.dueWords > 0 ? '' : undefined}
                  aria-label={[copy.pin_label(pin.placeLabelFr, weekNo(pin.week), pin.headlineFr), pin.dueWords > 0 ? copy.due_pin_label(pin.dueWords) : null].filter(Boolean).join(' · ')}
                  onClick={() => setOpenPin(pin)}
                >
                  {pin.precision !== 'exact' && <span className="carte-pin__ring" aria-hidden="true" />}
                  {pin.vignette ? (
                    <span className="carte-pin__stamp" aria-hidden="true">
                      <RvVignette
                      week={pin.week}
                      placeLabelFr={pin.placeLabelFr}
                      ring={pin.vignette.ring}
                      keptContribution={pin.vignette.keptContribution}
                      pictogramSvg={pin.vignette.pictogramSvg}
                      size="pin"
                      />
                    </span>
                  ) : (
                    <span className="carte-pin__plain" aria-hidden="true" />
                  )}
                  {pin.dueWords > 0 && <i className="carte-due-dot" aria-hidden="true" />}
                </button>
              </li>
            );
          })}
          {layout.quartier.map((cluster) => (
            <li
              key={`q-${cluster.id}`}
              className="carte__mark carte__mark--quartier"
              style={{ left: pct(cluster.x, layout.width), top: pct(cluster.y, layout.height) }}
            >
              <button
                type="button"
                className="carte-quartier"
                data-count={cluster.members.length}
                aria-label={`${copy.quartier_toggle} · ${cluster.members.map((m) => m.item.nameFr).join(', ')}`}
                onClick={() => setPlace(cluster)}
              />
            </li>
          ))}
        </ol>
      </div>

      {layout.elsewhere > 0 && level !== 'france' && (
        <p className="carte__elsewhere">
          <button type="button" className="av2-btn av2-btn--quiet av2-btn--inline" onClick={zoomOut}>
            <span>{copy.elsewhere(layout.elsewhere)}</span>
          </button>
        </p>
      )}

      <CartePinCard
        pin={word ? null : openPin}
        copy={copy}
        onClose={() => setOpenPin(null)}
        onRelire={onRelire}
        onReleve={onReleve}
        onReview={onReview}
        onRelecture={onRelecture}
        onWord={(text, pin) => setWord(wordRequest(text, pin))}
      />

      <BottomSheet open={Boolean(list)} title={copy.cluster_list_title} onClose={() => setList(null)}>
        <ul className="carte-list">
          {(list?.members ?? []).map(({ item: pin }) => (
            <li key={pin.sessionId}>
              <button
                type="button"
                className="carte-list__row"
                onClick={() => {
                  setList(null);
                  setOpenPin(pin);
                }}
              >
                <span className="carte-list__week">{copy.week_fr(weekNo(pin.week))}</span>
                <span className="carte-list__headline" lang="fr">
                  {pin.headlineFr}
                </span>
                <span className="carte-list__place" lang="fr">
                  {pin.placeLabelFr}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </BottomSheet>

      <BottomSheet
        open={Boolean(place)}
        title={(place?.members ?? []).map((m) => m.item.nameFr).join(' · ')}
        eyebrow={<span lang="fr">{copy.quartier_toggle}</span>}
        onClose={() => setPlace(null)}
      >
        <div className="carte-card">
          {place?.members[0]?.item.plateUrl && (
            <div className="carte-card__plate" aria-hidden="true">
              {/* eslint-disable-next-line @next/next/no-img-element -- a static plate, already sized */}
              <img src={place.members[0].item.plateUrl} alt="" loading="lazy" decoding="async" />
            </div>
          )}
          <p className="carte-card__made" lang="fr">
            {place?.members[0]?.item.labelFr}
          </p>
          <p className="av2-body">{copy.quartier_place}</p>
        </div>
      </BottomSheet>

      <WordHelpSheet request={word} onClose={() => setWord(null)} language={language} />
    </section>
  );
}

export default Carte;

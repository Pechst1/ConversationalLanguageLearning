/**
 * Le Quartier · ton carnet: what the quarter remembers, read back to you.
 *
 * The people you have met and what each one thinks of you (a sentence that names them and never
 * agrees with you), what you did, what you know and who told you, what is in your pocket, and the
 * places of Paris you know or have heard of. Everything is read from the quarter's `Memory`; the
 * carnet keeps nothing of its own but the «Tout oublier» confirmation.
 */
import React from 'react';

import { CastRig } from '@/components/cast/CastRig';
import { rigFor } from '@/components/cast/cast-registry';
import { PlotItem } from '@/components/cast/items/PlotItem';
import { VivantFigure } from '@/components/cast/vivant/VivantFigure';
import type { ExpressionId } from '@/components/cast/vivant/kit';
import { figureFor } from '@/components/cast/vivant/registry';
import { ITEMS, NAMES, NOTES, regardWords } from '@/lib/quartier/agency';
import { eligible } from '@/lib/quartier/memory';
import type { CastId, Memory, Words } from '@/lib/quartier/memory';
import { personOf } from '@/lib/quartier/stage';
import type { Native } from '@/lib/quartier/stage';
import { WORLD, worldState } from '@/lib/quartier/world';
import type { WorldPlace } from '@/lib/quartier/world';
import type { SeasonItemId } from '@/lib/season-items';

export interface CarnetProps {
  memory: Memory;
  native: Native;
  translate: boolean;
  onClose: () => void;
  onMap: () => void;
}

const DAYS: Record<string, string> = { t1a: 'Épisode 1', roam: 'En te promenant' };

/** The label of a day in the carnet: an episode, a walk, or a visit to a place (`visit.<place>`). */
const dayOf = (day: string) => DAYS[day] ?? (day.indexOf('visit.') === 0 ? WORLD.places.find((p) => p.id === day.slice(6))?.name.fr : undefined);

/** A face for the carnet: the troupe's own drawing, cropped to the head. */
function Portrait({ who, expression }: { who: string; expression: ExpressionId }) {
  const fig = figureFor(who);
  if (fig) return <VivantFigure id={fig.key} expression={expression} still crop="head" size={52} label="" />;
  const rig = rigFor(who);
  return rig ? <CastRig id={rig.id} crop="head" size={52} still label="" /> : null;
}

const faceFor = (r: number): ExpressionId => (r >= 1 ? 'joie' : r <= -2 ? 'fache' : 'neutre');

/** Where you stand with a place, in words that agree with nobody. */
function tagOf(p: WorldPlace, been: string | undefined): string {
  if (been === 'visited') return 'Tu connais';
  if (p.status === 'en_chantier') return 'En chantier';
  if (p.status === 'locked') return 'Plus tard';
  if (been === 'noticed') return 'On t’en a parlé';
  return 'À découvrir';
}

export function Carnet({ memory, native, translate, onClose, onMap }: CarnetProps) {
  const [, setTick] = React.useState(0);
  const [sure, setSure] = React.useState(false);
  React.useEffect(() => memory.subscribe(() => setTick((t) => t + 1)), [memory]);

  const state = { ...memory.state(), ...worldState() };
  const tr = (w: Words) => (translate ? <small>{w[native]}</small> : null);
  const met = memory.met();
  const notes = eligible(NOTES, state);
  const journal = memory.journal().slice(0, 14);
  const known = memory.known();
  const pocket = Object.keys(ITEMS).filter((id) => memory.holder(id) === 'toi');
  const been = memory.places();
  const places = WORLD.places.filter((p) => p.status !== 'locked' || been[p.id]);

  return (
    <div className="qz-carnet" role="dialog" aria-label="Ton carnet">
      <div className="qz-carnet-page">
        <header className="qz-carnet-head">
          <h1 className="qz-h">Ton carnet</h1>
          <button type="button" className="qz-x" aria-label="Fermer" onClick={onClose}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </header>

        <section>
          <h2>Les gens</h2>
          {met.length ? (
            <ul className="qz-people">
              {met.map((who) => {
                const r = memory.regard(who);
                const say = regardWords(who, r);
                const more = notes.filter((n) => n.who === who).slice(0, 2);
                return (
                  <li key={who} data-char={personOf(who)?.char}>
                    <span className="qz-portrait" aria-hidden>
                      <Portrait who={who} expression={faceFor(r)} />
                    </span>
                    <div>
                      <b>{NAMES[who as CastId]}</b>
                      <p lang="fr">
                        {say.fr}
                        {tr(say)}
                      </p>
                      {more.map((n) => (
                        <p key={n.id} className="qz-note" lang="fr">
                          {n.say.fr}
                          {tr(n.say)}
                        </p>
                      ))}
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="qz-empty">Personne encore. Entre au Mistral.</p>
          )}
        </section>

        {journal.length ? (
          <section>
            <h2>Ce que tu as fait</h2>
            <ul className="qz-did">
              {journal.map((j, i) => (
                <li key={i} lang="fr">
                  {j.words.fr}
                  {tr(j.words)}
                  {dayOf(j.day) ? <em>{dayOf(j.day)}</em> : null}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {known.length ? (
          <section>
            <h2>Ce que tu sais</h2>
            <ul className="qz-did">
              {known.map((k) => (
                <li key={k.key} lang="fr">
                  {k.words.fr}
                  {tr(k.words)}
                  {k.who ? <em>{NAMES[k.who]}</em> : k.from ? <em>{k.from}</em> : null}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {pocket.length ? (
          <section>
            <h2>Dans ta poche</h2>
            <ul className="qz-pocket">
              {pocket.map((id) => (
                <li key={id}>
                  <PlotItem id={ITEMS[id].art as SeasonItemId} size={56} still label="" />
                  <span lang="fr">
                    {ITEMS[id].name.fr}
                    {tr(ITEMS[id].name)}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <section>
          <h2>Les lieux</h2>
          <ul className="qz-places">
            {places.map((p) => (
              <li key={p.id} data-status={p.status}>
                <b lang="fr">{p.name.fr}</b>
                <span className="qz-tag">{tagOf(p, been[p.id])}</span>
                <p lang="fr">
                  {p.why.fr}
                  {tr(p.why)}
                </p>
              </li>
            ))}
          </ul>
          <button type="button" className="qz-primary qz-wide" onClick={onMap}>
            La carte
          </button>
        </section>

        <footer className="qz-carnet-foot">
          <button
            type="button"
            className="qz-quiet"
            onClick={() => {
              if (!sure) {
                setSure(true);
                return;
              }
              memory.clear();
              setSure(false);
            }}
          >
            {sure ? 'Vraiment ? Touche encore' : 'Tout oublier'}
          </button>
        </footer>
      </div>
    </div>
  );
}

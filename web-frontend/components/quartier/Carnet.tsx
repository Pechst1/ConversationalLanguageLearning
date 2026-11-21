/**
 * Le Quartier · ton carnet: what the quarter and the story remember, read back to you.
 *
 * The people the learner has met in the story and what each one knows of them, what they chose
 * (the end card's lines, under the day's own number), the places of the days they played, what
 * they know and who told them, what is in their pocket; Le Papier's places only while the news is
 * on. The sections are `carnetOf` (`lib/quartier/carnet-model.ts`); the story's part is read once
 * when the carnet opens (`story`), and the carnet keeps nothing of its own but the «Tout oublier»
 * confirmation.
 */
import React from 'react';

import { CastRig } from '@/components/cast/CastRig';
import { rigFor } from '@/components/cast/cast-registry';
import { PlotItem } from '@/components/cast/items/PlotItem';
import { VivantFigure } from '@/components/cast/vivant/VivantFigure';
import type { ExpressionId } from '@/components/cast/vivant/kit';
import { figureFor } from '@/components/cast/vivant/registry';
import { ITEMS, NAMES } from '@/lib/quartier/agency';
import { carnetOf } from '@/lib/quartier/carnet-model';
import type { CarnetPlace, CarnetStory } from '@/lib/quartier/carnet-model';
import type { Memory, Words } from '@/lib/quartier/memory';
import { personOf } from '@/lib/quartier/stage';
import type { Native } from '@/lib/quartier/stage';
import { worldState } from '@/lib/quartier/world';
import type { SeasonItemId } from '@/lib/season-items';

export interface CarnetProps {
  memory: Memory;
  native: Native;
  translate: boolean;
  onClose: () => void;
  onMap: () => void;
  /** the learner's story (the trombinoscope, the played days, whether the news is on), read when the carnet opens; none: the quarter's own memory only */
  story?: () => Promise<CarnetStory | null>;
}

/** A face for the carnet: the troupe's own drawing, cropped to the head. */
function Portrait({ who, expression }: { who: string; expression: ExpressionId }) {
  const fig = figureFor(who);
  if (fig) return <VivantFigure id={fig.key} expression={expression} still crop="head" size={52} label="" />;
  const rig = rigFor(who);
  return rig ? <CastRig id={rig.id} crop="head" size={52} still label="" /> : null;
}

const faceFor = (r: number): ExpressionId => (r >= 1 ? 'joie' : r <= -2 ? 'fache' : 'neutre');

/** Where you stand with a place, in words that agree with nobody. */
const TAGS: Record<CarnetPlace['tag'], string> = {
  known: 'Tu connais',
  building: 'En chantier',
  later: 'Plus tard',
  noticed: 'On t’en a parlé',
  discover: 'À découvrir',
};

export function Carnet({ memory, native, translate, onClose, onMap, story }: CarnetProps) {
  const [, setTick] = React.useState(0);
  const [sure, setSure] = React.useState(false);
  const [told, setTold] = React.useState<CarnetStory | null>(null);
  React.useEffect(() => memory.subscribe(() => setTick((t) => t + 1)), [memory]);
  React.useEffect(() => {
    let live = true;
    void story?.()
      .then((s) => live && setTold(s))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [story]);

  const tr = (w: Words) => (translate ? <small>{w[native]}</small> : null);
  // what is not fiction is in the learner's language below B1 (the gloss on), French from B1
  const plain = (w: Words) => (translate ? w[native] : w.fr);
  const model = carnetOf(memory, told, worldState());
  const known = memory.known();
  const pocket = Object.keys(ITEMS).filter((id) => memory.holder(id) === 'toi');
  const placeList = (list: CarnetPlace[]) => (
    <ul className="qz-places">
      {list.map((p) => (
        <li key={p.id} data-status={p.tag}>
          <b lang="fr">{p.name.fr}</b>
          <span className="qz-tag">{TAGS[p.tag]}</span>
          {p.why || p.editions.length ? (
            <p lang="fr">
              {p.editions.length ? `${p.editions.slice(0, 3).join(', ')}${p.why ? ' — ' : ''}` : null}
              {p.why ? p.why.fr : null}
              {p.why ? tr(p.why) : null}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );

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
          {model.people.length ? (
            <ul className="qz-people">
              {model.people.map((p) => (
                <li key={p.who} data-char={personOf(p.who)?.char}>
                  <span className="qz-portrait" aria-hidden>
                    <Portrait who={p.who} expression={faceFor(p.mood)} />
                  </span>
                  <div>
                    <b>{p.name}</b>
                    {p.register ? <span className="qz-tag">{p.register}</span> : null}
                    {p.knows ? <p lang="fr">{p.knows}</p> : null}
                    {p.regard ? (
                      <p className={p.knows ? 'qz-note' : undefined} lang="fr">
                        {p.regard.fr}
                        {tr(p.regard)}
                      </p>
                    ) : null}
                    {p.notes.map((n) => (
                      <p key={n.fr} className="qz-note" lang="fr">
                        {n.fr}
                        {tr(n)}
                      </p>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="qz-empty">{plain(model.empty.people)}</p>
          )}
        </section>

        <section>
          <h2>Ce que tu as fait</h2>
          {model.did.length ? (
            <ul className="qz-did">
              {model.did.map((j, i) => (
                <li key={i} lang="fr">
                  {j.words.fr}
                  {tr(j.words)}
                  {j.label ? <em>{j.label}</em> : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="qz-empty">{plain(model.empty.did)}</p>
          )}
        </section>

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
          {model.places.length ? placeList(model.places) : <p className="qz-empty">{plain(model.empty.places)}</p>}
          <button type="button" className="qz-primary qz-wide" onClick={onMap}>
            La carte
          </button>
        </section>

        {model.news ? (
          <section>
            <h2>Dans le journal</h2>
            {model.news.length ? placeList(model.news) : <p className="qz-empty">{plain(model.empty.news)}</p>}
          </section>
        ) : null}

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

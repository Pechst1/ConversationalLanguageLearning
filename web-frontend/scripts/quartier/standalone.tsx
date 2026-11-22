/**
 * Le Quartier · a page of its own: the 3D scene outside the app, for a phone's browser.
 * `node scripts/quartier/build-standalone.mjs` bundles this into one HTML file.
 * ?a=matin starts in the morning, ?place=marche_aligre starts at a place the forge built, ?stats
 * shows the frame counter, ?cast=paper stands the cast up as cut-out cards instead of in the round,
 * ?debug puts the quarter on `window.__qz` for a script to drive, ?detail=tasse_habituelle lays a
 * detail where it stands (Le Mistral's room; `&place=<room>` for one in a room; `&value=un thé`:
 * the season flag's value it shows), ?papier=<headline> hangs today's Papier on the Morris column
 * (&lu: already read; a tap on it logs the route it would open).
 */
import React from 'react';
import { createRoot } from 'react-dom/client';

import { QuartierScreen } from '../../components/quartier/QuartierScreen';
import { frenchDate, wrapHeadline } from '../../lib/quartier/affiche-model';

const params = new URLSearchParams(window.location.search);
const papier = params.get('papier');
const root = document.getElementById('root');
if (root) {
  createRoot(root).render(
    <QuartierScreen
      ambiance={params.get('a') === 'matin' ? 'matin' : 'nuit'}
      native={params.get('lang') === 'de' ? 'de' : params.get('lang') === 'en' ? 'en' : undefined}
      level={params.get('level') === 'b1' ? 'b1' : 'a2'}
      showStats={params.has('stats')}
      startPlace={params.get('place') ?? undefined}
      cast={params.get('cast') === 'paper' ? 'paper' : undefined}
      details={params.getAll('detail').map((id) => ({ id, value: params.get('value') ?? undefined }))}
      affiche={papier ? async () => ({ date: frenchDate(new Date()), headline: papier, lines: wrapHeadline(papier), done: params.has('lu'), route: '/revue' }) : undefined}
      onOpen={papier ? (route) => console.info(`[quartier] opens ${route}`) : undefined}
      onReady={params.has('debug') ? (engine, stage, memory) => Object.assign(window, { __qz: { engine, stage, memory } }) : undefined}
    />,
  );
}

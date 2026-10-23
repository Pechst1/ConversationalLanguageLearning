/**
 * Le Quartier · a page of its own: the 3D scene outside the app, for a phone's browser.
 * `node scripts/quartier/build-standalone.mjs` bundles this into one HTML file.
 * ?a=matin starts in the morning, ?stats shows the frame counter.
 */
import React from 'react';
import { createRoot } from 'react-dom/client';

import { QuartierScreen } from '../../components/quartier/QuartierScreen';

const params = new URLSearchParams(window.location.search);
const root = document.getElementById('root');
if (root) {
  createRoot(root).render(
    <QuartierScreen
      ambiance={params.get('a') === 'matin' ? 'matin' : 'nuit'}
      native={params.get('lang') === 'de' ? 'de' : params.get('lang') === 'en' ? 'en' : undefined}
      level={params.get('level') === 'b1' ? 'b1' : 'a2'}
      showStats={params.has('stats')}
    />,
  );
}

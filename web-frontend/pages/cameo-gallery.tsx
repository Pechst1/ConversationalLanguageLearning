/**
 * Les apparitions · a development page to see every cameo on demand
 * (lib/cameo.ts, components/cast/CameoLayer.tsx). Not in a production build.
 */
import Head from 'next/head';
import React from 'react';

import { CastRig } from '@/components/cast';
import { PlotItem } from '@/components/cast/items/PlotItem';
import { CAMEO_CAST, emitCameo } from '@/lib/cameo';
import { SEASON_ITEMS } from '@/lib/season-items';

export async function getStaticProps() {
  if (process.env.NODE_ENV === 'production') {
    return { notFound: true };
  }
  return { props: {} };
}

export default function CameoGallery() {
  // The gallery has met everybody, so every object comes with its own person.
  React.useEffect(() => {
    emitCameo({ type: 'met', ids: CAMEO_CAST.map((who) => who.id) });
  }, []);
  const rights = (n: number, coachId?: string) => {
    // A fresh run: one mistake first, so the count starts at zero.
    emitCameo({ type: 'answer', correct: false });
    for (let i = 0; i < n; i += 1) emitCameo({ type: 'answer', correct: true, coachId });
  };
  return (
    <>
      <Head>
        <title>Apparitions</title>
      </Head>
      <main style={{ padding: 20, maxWidth: 420, margin: '0 auto', fontFamily: 'var(--app-grotesk)' }}>
        <h1 style={{ fontFamily: 'var(--app-serif)', fontSize: 30, margin: '8px 0 4px' }}>Les apparitions</h1>
        <p style={{ opacity: 0.7, marginTop: 0 }}>Tap a face to poke it. Tap again, and again.</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, margin: '18px 0 24px' }}>
          {CAMEO_CAST.map((who) => (
            <span key={who.id} data-gallery-face={who.id} style={{ borderRadius: '50%', overflow: 'hidden', border: '2px solid var(--app-ink)', background: 'var(--app-paper)' }}>
              <CastRig id={who.id} crop="head" size={52} />
            </span>
          ))}
        </div>
        <div style={{ display: 'grid', gap: 8 }}>
          <button type="button" data-cameo="scene" onClick={() => emitCameo({ type: 'scene', ids: ['lila_bonnet', 'augustin_de_roncourt'] })}>Today’s page: Lila and Gus</button>
          <button type="button" data-cameo="streak" onClick={() => rights(5, 'augustin_de_roncourt')}>Five in a row (Gus’s rule)</button>
          <button type="button" data-cameo="troupe" onClick={() => rights(10)}>Ten in a row (the troupe)</button>
          <button type="button" data-cameo="comfort" onClick={() => { emitCameo({ type: 'answer', correct: true }); emitCameo({ type: 'answer', correct: false }); emitCameo({ type: 'answer', correct: false }); }}>Two mistakes</button>
          <button type="button" data-cameo="rebound" onClick={() => emitCameo({ type: 'answer', correct: true })}>…then a right answer</button>
          <button type="button" data-cameo="idle" onClick={() => emitCameo({ type: 'idle' })}>Stillness</button>
          <button type="button" data-cameo="finale" onClick={() => emitCameo({ type: 'finale' })}>Curtain call</button>
        </div>
        <h2 style={{ fontFamily: 'var(--app-serif)', fontSize: 22, margin: '28px 0 4px' }}>Les objets de la saison</h2>
        <p style={{ opacity: 0.7, marginTop: 0 }}>Tap one: its person hands it over, as after the first page of that part.</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
          {SEASON_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              data-chapter={item.segment}
              onClick={() => {
                // everybody met (the page's first announcement can come before the layer listens)
                emitCameo({ type: 'met', ids: CAMEO_CAST.map((who) => who.id) });
                emitCameo({ type: 'chapter', part: { season_id: item.season, segment: item.segment, kind: 'tentpole' }, replay: true });
              }}
              style={{ display: 'grid', justifyItems: 'center', gap: 4, padding: 6, background: 'var(--app-paper)', border: '1px solid var(--app-rule, #d9cfbb)', borderRadius: 12 }}
            >
              <PlotItem id={item.id} size={60} />
              <span style={{ fontSize: 11, lineHeight: 1.2 }}>{item.segment.toUpperCase()} · {item.name.fr}</span>
            </button>
          ))}
        </div>
      </main>
    </>
  );
}

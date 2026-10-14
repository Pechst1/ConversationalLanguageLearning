/**
 * Les apparitions · a development page to see every cameo on demand
 * (lib/cameo.ts, components/cast/CameoLayer.tsx). Not in a production build.
 */
import Head from 'next/head';
import React from 'react';

import { CastRig } from '@/components/cast';
import { CAMEO_CAST, emitCameo } from '@/lib/cameo';

export async function getStaticProps() {
  if (process.env.NODE_ENV === 'production') {
    return { notFound: true };
  }
  return { props: {} };
}

export default function CameoGallery() {
  const rights = (n: number, coachId?: string) => {
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
          <button type="button" data-cameo="streak" onClick={() => rights(3, 'augustin_de_roncourt')}>Three in a row (Gus’s rule)</button>
          <button type="button" data-cameo="troupe" onClick={() => rights(6)}>Six in a row (the troupe)</button>
          <button type="button" data-cameo="comfort" onClick={() => { emitCameo({ type: 'answer', correct: false }); emitCameo({ type: 'answer', correct: false }); }}>Two mistakes</button>
          <button type="button" data-cameo="idle" onClick={() => emitCameo({ type: 'idle' })}>Stillness</button>
          <button type="button" data-cameo="finale" onClick={() => emitCameo({ type: 'finale' })}>Curtain call</button>
        </div>
      </main>
    </>
  );
}

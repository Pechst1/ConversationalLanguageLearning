/**
 * La troupe vivante · a development page to see every jointed figure act: pick someone, a face,
 * a gesture; below, the whole troupe doing the same thing their own way
 * (components/cast/vivant). Not in a production build.
 */
import Head from 'next/head';
import React from 'react';

import { VivantFigure } from '@/components/cast/vivant/VivantFigure';
import { EXPRESSIONS, GESTURES } from '@/components/cast/vivant/kit';
import type { ExpressionId, GestureId } from '@/components/cast/vivant/kit';
import { FIGURES } from '@/components/cast/vivant/registry';

export async function getStaticProps() {
  if (process.env.NODE_ENV === 'production') {
    return { notFound: true };
  }
  return { props: {} };
}

const chip = (on: boolean): React.CSSProperties => ({
  border: '1.5px solid var(--app-ink)',
  borderRadius: 999,
  padding: '4px 10px',
  background: on ? 'var(--app-ink)' : 'transparent',
  color: on ? 'var(--app-paper)' : 'var(--app-ink)',
  font: 'inherit',
  fontSize: 13,
});

export default function TroupeVivante() {
  const [who, setWho] = React.useState(FIGURES[0]?.key ?? 'romy');
  const [expression, setExpression] = React.useState<ExpressionId>('neutre');
  const [gesture, setGesture] = React.useState<GestureId | null>(null);
  const [loop, setLoop] = React.useState(false);
  const [take, setTake] = React.useState(0);
  const fig = FIGURES.find((f) => f.key === who) ?? FIGURES[0];
  if (!fig) return null;
  const play = (g: GestureId) => {
    setGesture(g);
    setTake((t) => t + 1);
  };
  return (
    <>
      <Head>
        <title>La troupe vivante</title>
      </Head>
      <main style={{ padding: 20, maxWidth: 760, margin: '0 auto', fontFamily: 'var(--app-grotesk)' }}>
        <h1 style={{ fontFamily: 'var(--app-serif)', fontSize: 30, margin: '8px 0 4px' }}>La troupe vivante</h1>
        <p style={{ opacity: 0.7, marginTop: 0 }}>The cast, cut at the joints: ten faces and six gestures each, everyone in their own way.</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, margin: '14px 0' }}>
          {FIGURES.map((f) => (
            <button key={f.key} type="button" data-figure={f.key} style={chip(f.key === fig.key)} onClick={() => setWho(f.key)}>
              {f.name}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 20, alignItems: 'flex-start' }}>
          <div style={{ background: 'var(--app-paper)', border: '1.5px solid var(--app-ink)', borderRadius: 12 }}>
            <VivantFigure key={`${fig.key}-${take}`} id={fig.key} expression={expression} gesture={gesture} loop={loop} size={240} />
          </div>
          <div style={{ flex: '1 1 280px', display: 'grid', gap: 14 }}>
            <div>
              <h2 style={{ fontSize: 15, margin: '0 0 6px' }}>Visages</h2>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {EXPRESSIONS.map((e) => (
                  <button key={e} type="button" data-expression={e} title={fig.expressions[e].note} style={chip(e === expression)} onClick={() => setExpression(e)}>
                    {fig.expressions[e].label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <h2 style={{ fontSize: 15, margin: '0 0 6px' }}>Gestes</h2>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {GESTURES.map((g) => (
                  <button key={g} type="button" data-gesture={g} title={fig.gestures[g].note} style={chip(g === gesture)} onClick={() => play(g)}>
                    {fig.gestures[g].label}
                  </button>
                ))}
                <button type="button" style={chip(gesture === null)} onClick={() => setGesture(null)}>
                  Repos
                </button>
              </div>
              {gesture ? <p style={{ margin: '8px 0 0', fontStyle: 'italic' }}>«&nbsp;{fig.gestures[gesture].line}&nbsp;» · {fig.gestures[gesture].note}</p> : null}
            </div>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 14 }}>
              <input type="checkbox" checked={loop} onChange={(e) => setLoop(e.target.checked)} /> En boucle
            </label>
          </div>
        </div>
        <h2 style={{ fontSize: 15, margin: '28px 0 8px' }}>Toute la troupe{gesture ? ` · ${gesture}` : ` · ${expression}`}</h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {FIGURES.map((f) => (
            <figure key={f.key} style={{ margin: 0, textAlign: 'center', fontSize: 12 }}>
              <VivantFigure key={`${f.key}-${take}`} id={f.key} expression={expression} gesture={gesture} loop={loop} size={110} />
              <figcaption>{gesture ? f.gestures[gesture].label : f.expressions[expression].label}</figcaption>
            </figure>
          ))}
        </div>
      </main>
    </>
  );
}

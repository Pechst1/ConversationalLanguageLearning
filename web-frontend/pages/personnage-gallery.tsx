/**
 * Ton personnage · a development page to see every part of the learner's character drawn:
 * each slot's choices side by side, the six gestures, and a few whole characters. Not in a
 * production build.
 */
import Head from 'next/head';
import { useRouter } from 'next/router';
import React from 'react';

import { Avatar } from '@/components/avatar/Avatar';
import { GESTURES } from '@/components/cast/vivant/kit';
import type { AvatarConfig, AvatarSlot } from '@/lib/avatar';
import { DEFAULT_AVATAR, SLOT_OPTIONS, randomAvatar } from '@/lib/avatar';

export async function getStaticProps() {
  if (process.env.NODE_ENV === 'production') {
    return { notFound: true };
  }
  return { props: {} };
}

/** A seeded dice, so the gallery draws the same crowd every time. */
function dice(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

const EVERYTHING = ['pins_atelier', 'montre', 'soleil', 'canotier', 'crayon', 'foulard', 'bracelet', 'boucles_or', 'mariniere', 'collier_cle', 'badge_presse'];

const SHOWN: Array<{ slot: AvatarSlot; crop: 'head' | 'bust' | 'full'; base?: Partial<AvatarConfig> }> = [
  { slot: 'skin', crop: 'head' },
  { slot: 'face', crop: 'head', base: { hair: 'rase' } },
  { slot: 'hair', crop: 'head' },
  { slot: 'hairColor', crop: 'head', base: { hair: 'mi_long' } },
  { slot: 'eyes', crop: 'head' },
  { slot: 'eyeColor', crop: 'head' },
  { slot: 'brows', crop: 'head' },
  { slot: 'beard', crop: 'head' },
  { slot: 'glasses', crop: 'head' },
  { slot: 'hat', crop: 'head' },
  { slot: 'top', crop: 'full' },
  { slot: 'topColor', crop: 'bust' },
  { slot: 'neck', crop: 'bust' },
  { slot: 'wrist', crop: 'full' },
  { slot: 'ears', crop: 'head', base: { hair: 'chignon' } },
  { slot: 'pin', crop: 'bust' },
];

export default function PersonnageGallery() {
  const router = useRouter();
  if (!router.isReady) return null;
  const only = typeof router.query.slot === 'string' ? router.query.slot : null;
  const still = router.query.still === '1';
  const crowd = Array.from({ length: 12 }, (_, i) => randomAvatar(dice(7 + i * 31), EVERYTHING));
  return (
    <>
      <Head>
        <title>Ton personnage</title>
      </Head>
      <main style={{ padding: 16, maxWidth: 980, margin: '0 auto', fontFamily: 'var(--app-grotesk)', background: '#f1ece1' }}>
        <h1 style={{ fontFamily: 'var(--app-serif)', fontSize: 28, margin: '8px 0 4px' }}>Ton personnage</h1>
        {!only || only === 'crowd' ? (
          <section data-gallery="crowd">
            <h2 style={{ fontSize: 16 }}>Au hasard</h2>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {crowd.map((cfg, i) => (
                <div key={i} style={{ background: '#f8f3e8', borderRadius: 12 }}>
                  <Avatar config={cfg} crop="full" size={140} still={still} />
                </div>
              ))}
            </div>
          </section>
        ) : null}
        {!only || only === 'gestures' ? (
          <section data-gallery="gestures">
            <h2 style={{ fontSize: 16 }}>Gestes</h2>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {GESTURES.map((g) => (
                <div key={g} style={{ background: '#f8f3e8', borderRadius: 12, textAlign: 'center', fontSize: 12 }}>
                  <Avatar config={{ ...DEFAULT_AVATAR, hair: 'boucles', hairColor: 'roux', freckles: true }} gesture={g} still crop="full" size={140} />
                  {g}
                </div>
              ))}
            </div>
          </section>
        ) : null}
        {SHOWN.filter((s) => !only || only === s.slot).map(({ slot, crop, base }) => (
          <section key={slot} data-gallery={slot}>
            <h2 style={{ fontSize: 16 }}>{slot}</h2>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {SLOT_OPTIONS[slot].map((value) => (
                <div key={value} style={{ background: '#f8f3e8', borderRadius: 12, textAlign: 'center', fontSize: 11 }}>
                  <Avatar config={{ ...DEFAULT_AVATAR, ...base, [slot]: value }} crop={crop} size={crop === 'full' ? 110 : 96} still={still} />
                  <div>{value}</div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </main>
    </>
  );
}

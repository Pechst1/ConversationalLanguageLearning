/**
 * Le mur du Mistral · the season's objects on the café's wall (components/cast/items/MurDuMistral).
 * Reached from Home once the learner has been handed the first one.
 */
import Head from 'next/head';
import React from 'react';

import { MurDuMistral } from '@/components/cast/items/MurDuMistral';
import { WALL_COPY } from '@/lib/season-wall';

export default function MurPage() {
  return (
    <>
      <Head>
        <title>{WALL_COPY.title}</title>
      </Head>
      <MurDuMistral />
    </>
  );
}

/**
 * Le Quartier · the season's first day (T1, day a) played in a walkable Paris: the quai de
 * Valmy at night in the rain, Le Mistral, the cast (components/quartier, lib/quartier).
 *
 * Behind `quartierVisible` in launch-flags.json in a production build; a development build
 * always has it. The street is WebGL, so it never renders on the server.
 */
import dynamic from 'next/dynamic';
import Head from 'next/head';
import { useRouter } from 'next/router';
import React from 'react';

import { QUARTIER_VISIBLE } from '@/lib/launch-flags';
import { levelBand } from '@/lib/language-rule';
import { LEARNER_LANGUAGE_STORAGE_KEY, readLearnerLevel } from '@/lib/learner-language';
import type { Level, Native } from '@/lib/quartier/stage';

const QuartierScreen = dynamic(() => import('@/components/quartier/QuartierScreen').then((m) => m.QuartierScreen), {
  ssr: false,
  loading: () => <div style={{ position: 'fixed', inset: 0, background: '#14110d' }} />,
});

export async function getStaticProps() {
  if (process.env.NODE_ENV === 'production' && !QUARTIER_VISIBLE) {
    return { notFound: true };
  }
  return { props: {} };
}

/** The learner's language and level as the last profile load cached them; no language: the phone's. */
function learner(): { native?: Native; level: Level } {
  if (typeof window === 'undefined') return { level: 'a2' };
  let language: string | null = null;
  try {
    language = window.localStorage.getItem(LEARNER_LANGUAGE_STORAGE_KEY);
  } catch {
    // storage refused: the phone's language decides
  }
  const band = levelBand(readLearnerLevel());
  return {
    native: language === 'de' || language === 'en' ? language : undefined,
    level: band === 'A1' || band === 'A2' || band === null ? 'a2' : 'b1',
  };
}

export default function QuartierPage() {
  const router = useRouter();
  const [who] = React.useState(learner);
  const leave = React.useCallback(() => {
    if (window.history.length > 1) router.back();
    else void router.push('/');
  }, [router]);
  return (
    <>
      <Head>
        <title>Le Quartier</title>
      </Head>
      <QuartierScreen native={who.native} level={who.level} onExit={leave} />
    </>
  );
}

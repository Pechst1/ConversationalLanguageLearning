/**
 * SPEED-1 «Vérification du lexique» — `/vocabulary/verification`.
 *
 * `?from=placement` (the placement result) returns to the day; anything else
 * (Le lexique) returns to the word list. `?band=A1.2` opens that sub-band when
 * it is still uncredited, else the lowest one that is.
 */

import React from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { BandCheckFlow, bandCheckCopy, type BandCheckOrigin } from '@/components/atelier-v2/band-check';
import { useLearnerLanguage } from '@/lib/learner-language';

export default function VocabularyVerificationPage() {
  const router = useRouter();
  const copy = bandCheckCopy(useLearnerLanguage());
  const origin: BandCheckOrigin = router.query.from === 'placement' ? 'placement' : 'lexique';
  const band = typeof router.query.band === 'string' ? router.query.band : null;
  const leave = React.useCallback(() => {
    void router.replace(origin === 'placement' ? '/atelier' : '/vocabulary');
  }, [router, origin]);

  return (
    <>
      <Head>
        <title>{`${copy.screen_aria} · L’Atelier`}</title>
      </Head>
      {router.isReady ? <BandCheckFlow origin={origin} initialBand={band} onLeave={leave} /> : null}
    </>
  );
}

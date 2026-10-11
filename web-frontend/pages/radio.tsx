/* WP-122 A · /radio — La Radio: the week's Papier as a fifty-second bulletin.

   Own-shell like /revue (no tab: decision 7). Reached from La Une's chip
   «La Radio · 50 s» on the days between Papiers.

   Query:
     ?dossier=<id>   that bulletin (the chip names the rotation's next one)
     ?band=A1|A2|B1  the bulletin's band (default: the learner's)
     ?mock=1         DEV ONLY (never in a production build): the grève evergreen at A2
                     with silent clips (components/radio/radio-mock.ts). ?lang=de|en|fr
                     shapes the chrome.

   States: loading · the bulletin (listen first → read → dictée → «C'est entendu») ·
   heard (the close) · nothing left this week · the Radio switched off · the API
   failing (retry). */

import React, { useCallback, useEffect, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { Action, AtelierV2Root, Skeleton, StateBlock } from '@/components/atelier-v2/ui';
import { RadioBulletin, radioCopy } from '@/components/radio';
import { enterImmersiveSurface } from '@/lib/immersive-surface';
import { useChromeLanguage } from '@/lib/learner-language';
import { radioClient, type RadioClient } from '@/lib/radio-api';
import type { RadioBulletin as RadioBulletinWire, RadioLanguage } from '@/lib/radio-types';

type PageState =
  | { kind: 'loading' }
  | { kind: 'disabled' }
  | { kind: 'error' }
  | { kind: 'nothing' }
  | { kind: 'bulletin'; bulletin: RadioBulletinWire }
  | { kind: 'heard' };

const HOME = '/atelier';

function queryString(value: string | string[] | undefined): string | null {
  const one = Array.isArray(value) ? value[0] : value;
  return one && one.trim() ? one.trim() : null;
}

export default function RadioPage() {
  const router = useRouter();
  const learnerLanguage = useChromeLanguage();
  const mock = process.env.NODE_ENV !== 'production' && router.query.mock === '1';
  const langParam = queryString(router.query.lang);
  const language: RadioLanguage =
    mock && (langParam === 'de' || langParam === 'en' || langParam === 'fr') ? langParam : (learnerLanguage as RadioLanguage);
  const copy = radioCopy(language);
  const [client, setClient] = useState<RadioClient | null>(null);
  const [state, setState] = useState<PageState>({ kind: 'loading' });

  useEffect(() => {
    if (!router.isReady) return;
    let alive = true;
    // The literal NODE_ENV test lets the production build drop the mock chunk entirely.
    if (process.env.NODE_ENV !== 'production' && mock) {
      void import('@/components/radio/radio-mock').then(({ createMockRadioClient }) => {
        if (alive) setClient(createMockRadioClient());
      });
    } else {
      setClient(radioClient());
    }
    return () => {
      alive = false;
    };
  }, [router.isReady, mock]);

  const load = useCallback(async () => {
    if (!client) return;
    setState({ kind: 'loading' });
    const band = queryString(router.query.band);
    try {
      let dossierId = queryString(router.query.dossier);
      if (!dossierId) {
        const week = await client.week();
        if (!week.enabled) {
          setState({ kind: 'disabled' });
          return;
        }
        if (!week.week.current) {
          setState({ kind: 'nothing' });
          return;
        }
        dossierId = week.week.current.dossierId;
      }
      setState({ kind: 'bulletin', bulletin: await client.bulletin(dossierId, band) });
    } catch (error) {
      const status = (error as { status?: number } | null)?.status;
      setState(status === 404 ? { kind: 'disabled' } : { kind: 'error' });
    }
    // The query is read once per load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  const listening = state.kind === 'bulletin';
  useEffect(() => (listening ? enterImmersiveSurface() : undefined), [listening]);

  const exit = useCallback(() => void router.push(HOME), [router]);

  let body: React.ReactNode;
  if (state.kind === 'bulletin' && client) {
    body = (
      <RadioBulletin
        key={state.bulletin.dossierId}
        bulletin={state.bulletin}
        client={client}
        language={language}
        onExit={exit}
        onHeard={() => setState({ kind: 'heard' })}
      />
    );
  } else if (state.kind === 'heard') {
    body = (
      <div className="radio__close">
        <StateBlock tone="empty" title={copy.heard_title} body={copy.heard_body} />
        <Action tone="primary" onClick={exit}>
          {copy.back_home}
        </Action>
      </div>
    );
  } else if (state.kind === 'nothing') {
    body = <StateBlock tone="empty" title={copy.nothing_title} body={copy.nothing_body} action={{ label: copy.back_home, onSelect: exit }} />;
  } else if (state.kind === 'disabled') {
    body = <StateBlock tone="empty" title={copy.disabled_title} body={copy.disabled_body} action={{ label: copy.back_home, onSelect: exit }} />;
  } else if (state.kind === 'error') {
    body = <StateBlock tone="error" title={copy.error_title} body={copy.error_body} action={{ label: copy.retry, onSelect: () => void load() }} />;
  } else {
    body = (
      <div className="radio-loading" role="status" aria-busy="true" aria-label={copy.loading}>
        <Skeleton height={168} radius={0} />
        <Skeleton height={28} />
        <Skeleton height={4} />
        <Skeleton height={56} radius={16} />
      </div>
    );
  }

  return (
    <>
      <Head>
        <title>La Radio · L’Atelier</title>
      </Head>
      <AtelierV2Root as="main" language={language} className="radio-page" aria-label="La Radio" data-radio-mock={mock ? '' : undefined}>
        {body}
        {mock && <p className="radio-page__mock">{copy.mock_badge}</p>}
      </AtelierV2Root>
    </>
  );
}

/* WP-120 phase C · /carte — La Carte: where each Papier happened.

   An own-shell av2 page (no tab: the map is an archive, not a daily surface), the
   settings cog in its corner. Reached from the close screen of a Papier, the
   Relevé's «Le Papier» section and Settings' Bibliothèque row.

   Query:
     ?mock=1         DEV ONLY (never in a production build): six Papiers and three
                     «Mon quartier» places from components/carte/carte-mock.ts.
                     ?lang=de|en|fr shapes the chrome; ?level=idf|paris opens there.

   States: loading · the map (with the empty state above it when nothing is filed
   yet) · the Revue switched off · the API failing (retry). */

import React, { useCallback, useEffect, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { AtelierV2Root, IconAction, Skeleton, StateBlock } from '@/components/atelier-v2/ui';
import { ArrowLeftIcon } from '@/components/atelier-v2/ui/Shapes';
import { Carte, CarteEmpty, carteCopy } from '@/components/carte';
import { ShellCorner } from '@/components/layout/ShellCorner';
import { carteClient } from '@/lib/carte-api';
import type { CarteLanguage, CarteLevel, CartePin, CarteView } from '@/lib/carte-types';
import { useChromeLanguage } from '@/lib/learner-language';

type PageState = { kind: 'loading' } | { kind: 'disabled' } | { kind: 'error' } | { kind: 'ready'; view: CarteView };

const BACK = '/notebook?mode=releve';

function queryString(value: string | string[] | undefined): string | null {
  const one = Array.isArray(value) ? value[0] : value;
  return one && one.trim() ? one.trim() : null;
}

export default function CartePage() {
  const router = useRouter();
  const learnerLanguage = useChromeLanguage();
  const mock = process.env.NODE_ENV !== 'production' && router.query.mock === '1';
  const langParam = queryString(router.query.lang);
  const language: CarteLanguage =
    mock && (langParam === 'de' || langParam === 'en' || langParam === 'fr') ? langParam : (learnerLanguage as CarteLanguage);
  const levelParam = queryString(router.query.level);
  const initialLevel: CarteLevel = mock && (levelParam === 'idf' || levelParam === 'paris') ? levelParam : 'france';
  const copy = carteCopy(language);
  const [state, setState] = useState<PageState>({ kind: 'loading' });

  const load = useCallback(async () => {
    if (!router.isReady) return;
    setState({ kind: 'loading' });
    // The literal NODE_ENV test lets the production build drop the mock chunk entirely.
    if (process.env.NODE_ENV !== 'production' && mock) {
      const { CARTE_MOCK_VIEW } = await import('@/components/carte/carte-mock');
      setState({ kind: 'ready', view: CARTE_MOCK_VIEW });
      return;
    }
    try {
      const result = await carteClient().carte();
      setState(result.enabled ? { kind: 'ready', view: result.view } : { kind: 'disabled' });
    } catch {
      setState({ kind: 'error' });
    }
  }, [router.isReady, mock]);

  useEffect(() => {
    void load();
  }, [load]);

  const relire = (pin: CartePin) => void router.push(`/revue?session=${encodeURIComponent(pin.sessionId)}&readonly=1`);
  const releve = (pin: CartePin) => void router.push(`${BACK}#revue-${pin.week}`);
  const back = () => void router.push(BACK);

  let body: React.ReactNode;
  if (state.kind === 'ready') {
    const { view } = state;
    body = (
      <>
        {view.pins.length === 0 && <CarteEmpty copy={copy} onOpenPapier={() => void router.push('/revue')} />}
        <Carte
          key={initialLevel}
          pins={view.pins}
          quartier={view.quartier}
          copy={copy}
          language={language}
          initialLevel={initialLevel}
          onRelire={relire}
          onReleve={releve}
        />
      </>
    );
  } else if (state.kind === 'disabled') {
    body = <StateBlock tone="empty" title={copy.disabled_title} body={copy.disabled_body} action={{ label: copy.back, onSelect: back }} />;
  } else if (state.kind === 'error') {
    body = <StateBlock tone="error" title={copy.error_title} body={copy.error_body} action={{ label: copy.retry, onSelect: () => void load() }} />;
  } else {
    body = (
      <div className="carte-loading" role="status" aria-busy="true" aria-label={copy.loading}>
        <Skeleton height={20} />
        <Skeleton height={320} radius={16} />
      </div>
    );
  }

  return (
    <>
      <Head>
        <title>La Carte · L’Atelier</title>
      </Head>
      <AtelierV2Root as="main" language={language} className="carte-page" aria-label="La Carte" data-carte-mock={mock ? '' : undefined}>
        <ShellCorner />
        <header className="carte-page__head">
          <IconAction label={copy.back} onClick={back}>
            <ArrowLeftIcon size={18} />
          </IconAction>
          <h1 className="carte-page__title" lang="fr">
            {copy.page_title}
          </h1>
        </header>
        <div className="carte-page__body">{body}</div>
        {mock && <p className="carte-page__mock">{copy.mock_badge}</p>}
      </AtelierV2Root>
    </>
  );
}

/* «Papier · les rendez-vous» · /revue/une — «La une de la semaine» (2026-11-21).

   A front page composed ONLY from what the learner filed that week (GET /revue/une,
   app/services/revue/une.py): their headline over the story, their opinion as the vox-pop
   line, their retelling as a brief, their intox corrections; the week's «Lexique»; the count
   line. Reached from the Relevé's «Carte de presse» (any time) and from Home's chip on the
   last day of a week with two pieces or more.

   Query:
     ?week=2026-W47  that ISO week (else this one)
     ?mock=1         DEV ONLY: the canned page of lib/revue-mock-rdv.ts; ?lang=de|en|fr.

   The switch off (REVUE_UNE_ENABLED, or the Papier itself): the page says so and goes back. */

import React, { useCallback, useEffect, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { ArrowLeftIcon, AtelierV2Root, IconAction, Skeleton, StateBlock } from '@/components/atelier-v2/ui';
import { RDV_FR, RvUneSemaine, rdvCopy } from '@/components/revue/rdv';
import { useChromeLanguage } from '@/lib/learner-language';
import { createRdvClient, rdvClient, type RdvClient, type RvUneSemaine as UneData } from '@/lib/revue-rdv';
import type { RvLanguage } from '@/lib/revue-types';

type PageState = { kind: 'loading' } | { kind: 'off' } | { kind: 'error' } | { kind: 'une'; une: UneData };

const BACK = '/notebook?mode=releve#revue';

function queryString(value: string | string[] | undefined): string | null {
  const one = Array.isArray(value) ? value[0] : value;
  return one && one.trim() ? one.trim() : null;
}

export default function UnePage() {
  const router = useRouter();
  const chrome = useChromeLanguage();
  const mock = process.env.NODE_ENV !== 'production' && router.query.mock === '1';
  const langParam = queryString(router.query.lang);
  const language: RvLanguage = (mock && (langParam === 'de' || langParam === 'en' || langParam === 'fr') ? langParam : chrome) as RvLanguage;
  const copy = rdvCopy(language);
  const [client, setClient] = useState<RdvClient | null>(null);
  const [state, setState] = useState<PageState>({ kind: 'loading' });

  useEffect(() => {
    if (!router.isReady) return;
    let alive = true;
    if (process.env.NODE_ENV !== 'production' && mock) {
      void Promise.all([import('@/lib/revue-mock'), import('@/lib/revue-mock-rdv')]).then(([{ createMockRevueTransport }, { withRdvMock }]) => {
        if (alive) setClient(createRdvClient(withRdvMock(createMockRevueTransport({ language, latency: 250 }))));
      });
    } else {
      setClient(rdvClient());
    }
    return () => {
      alive = false;
    };
    // The client is built once per page load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.isReady, mock]);

  const load = useCallback(async () => {
    if (!client) return;
    setState({ kind: 'loading' });
    try {
      const week = queryString(router.query.week);
      const une = await client.une(week && /^\d{4}-W\d{2}$/.test(week) ? week : undefined);
      setState(une ? { kind: 'une', une } : { kind: 'off' });
    } catch {
      setState({ kind: 'error' });
    }
    // The query is read once per load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  const exit = useCallback(() => void router.push(BACK), [router]);

  let body: React.ReactNode;
  if (state.kind === 'une') body = <RvUneSemaine une={state.une} language={language} />;
  else if (state.kind === 'off') body = <StateBlock tone="empty" title={RDV_FR.une_title} body={copy.une_empty} action={{ label: copy.une_back, onSelect: exit }} />;
  else if (state.kind === 'error') body = <StateBlock tone="error" title={RDV_FR.une_title} body={copy.une_failed} action={{ label: copy.une_back, onSelect: exit }} />;
  else
    body = (
      <div role="status" aria-busy="true">
        <Skeleton height={28} />
        <Skeleton height={160} />
      </div>
    );

  return (
    <>
      <Head>
        <title>{RDV_FR.une_title}</title>
      </Head>
      <AtelierV2Root as="main" language={language} className="rv-page une-page" aria-label={RDV_FR.une_title} data-revue-mock={mock ? '' : undefined}>
        <div className="rv-top">
          <IconAction label={copy.une_back} onClick={exit}>
            <ArrowLeftIcon size={18} />
          </IconAction>
        </div>
        <div className="rv-body">{body}</div>
      </AtelierV2Root>
    </>
  );
}

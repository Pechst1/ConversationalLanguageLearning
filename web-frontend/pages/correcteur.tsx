/* WP-122 B · /correcteur — Le Correcteur: Romy's draft, marked before print.

   Own-shell, immersive like /revue: a head with × (back to La Une), the draft on
   paper, the field, the marks, the one primary «Bon à tirer», then the result.

   Query:
     ?dossier=<id>   correct that story's draft (else the first one of the week
                     the learner has not corrected yet)
     ?mock=1         DEV ONLY (never in a production build): the in-memory client of
                     components/correcteur/correcteur-mock.ts (the grève evergreen,
                     three «classiques»). ?band=A1|A2|B1 (options at A1–A2 only),
                     ?lang=de|en|fr.

   No entry point yet: the Relevé and the planner's `correcteur` recall step link
   here later (WP-122 §4.2); for now the page is reached by its URL. */

import React, { useCallback, useEffect, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { ArrowLeftIcon, AtelierV2Root, CastPortrait, IconAction, Skeleton, StateBlock } from '@/components/atelier-v2/ui';
import { CorrecteurDesk, correcteurCopy, normalizeLanguage } from '@/components/correcteur';
import { CorrecteurError, correcteurClient, type CorrecteurClient } from '@/lib/correcteur-api';
import type { CrDraft } from '@/lib/correcteur-types';
import { enterImmersiveSurface } from '@/lib/immersive-surface';
import { useChromeLanguage } from '@/lib/learner-language';

type PageState =
  | { kind: 'loading' }
  | { kind: 'disabled' }
  | { kind: 'empty' }
  | { kind: 'error' }
  | { kind: 'draft'; draft: CrDraft };

const HOME = '/atelier';

function queryString(value: string | string[] | undefined): string | null {
  const one = Array.isArray(value) ? value[0] : value;
  return one && one.trim() ? one.trim() : null;
}

export default function CorrecteurPage() {
  const router = useRouter();
  const chrome = useChromeLanguage();
  const mock = process.env.NODE_ENV !== 'production' && router.query.mock === '1';
  const langParam = queryString(router.query.lang);
  const language = normalizeLanguage(mock && langParam ? langParam : chrome);
  const copy = correcteurCopy(language);
  const [client, setClient] = useState<CorrecteurClient | null>(null);
  const [state, setState] = useState<PageState>({ kind: 'loading' });

  useEffect(() => {
    if (!router.isReady) return;
    let alive = true;
    if (process.env.NODE_ENV !== 'production' && mock) {
      const band = queryString(router.query.band) ?? 'A2';
      void import('@/components/correcteur/correcteur-mock').then(({ createMockCorrecteurClient }) => {
        if (alive) setClient(createMockCorrecteurClient({ band, latency: 350 }));
      });
    } else {
      setClient(correcteurClient());
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
      let dossierId = queryString(router.query.dossier);
      if (!dossierId) {
        const week = await client.week();
        if (!week.enabled) {
          setState({ kind: 'disabled' });
          return;
        }
        dossierId = week.week.dossiers[0]?.id ?? null;
        if (!dossierId) {
          setState({ kind: 'empty' });
          return;
        }
      }
      setState({ kind: 'draft', draft: await client.draft(dossierId) });
    } catch (error) {
      if (error instanceof CorrecteurError && error.code === 'correcteur_disabled') setState({ kind: 'disabled' });
      else setState({ kind: 'error' });
    }
    // The query is read once per load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  const immersive = state.kind === 'draft';
  useEffect(() => (immersive ? enterImmersiveSurface() : undefined), [immersive]);

  const exit = useCallback(() => void router.push(HOME), [router]);

  let body: React.ReactNode;
  if (state.kind === 'draft' && client) {
    const draft = state.draft;
    body = (
      <CorrecteurDesk
        key={draft.id}
        draft={draft}
        copy={copy}
        onSubmit={(marks) => client.marks(draft.id, marks)}
        onReleve={() => void router.push('/notebook?mode=releve')}
      />
    );
  } else if (state.kind === 'disabled') {
    body = <StateBlock tone="empty" title={copy.disabled_title} body={copy.disabled_body} action={{ label: copy.back_home, onSelect: exit }} />;
  } else if (state.kind === 'empty') {
    body = <StateBlock tone="empty" title={copy.empty_title} body={copy.empty_body} action={{ label: copy.back_home, onSelect: exit }} />;
  } else if (state.kind === 'error') {
    body = <StateBlock tone="error" title={copy.error_title} body={copy.error_body} action={{ label: copy.retry, onSelect: () => void load() }} />;
  } else {
    body = (
      <div className="cr-loading" role="status" aria-busy="true" aria-label={copy.loading}>
        <p className="cr-loading__line">
          <CastPortrait characterId="romy_tremblay" name="Romy" size="xs" ring />
          <span>{copy.loading}</span>
        </p>
        <Skeleton height={18} />
        <Skeleton height={140} />
      </div>
    );
  }

  return (
    <>
      <Head>
        <title>{copy.page_title}</title>
      </Head>
      <AtelierV2Root as="main" language={language} className="rv-page cr-page" aria-label={copy.page_title} data-correcteur-mock={mock ? '' : undefined}>
        <div className="rv-top cr-top">
          <div className="cr-head">
            <IconAction label={copy.exit} onClick={exit}>
              <ArrowLeftIcon size={18} />
            </IconAction>
            <h1 className="cr-head__title">{copy.page_title}</h1>
          </div>
        </div>
        <div className="rv-body">{body}</div>
        {mock && <p className="rv-mock">{copy.mock_badge}</p>}
      </AtelierV2Root>
    </>
  );
}

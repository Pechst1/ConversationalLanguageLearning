/* «Le bilan» · /bilan — the learner's week on one page.

   Own-shell, calm: a head with ← (back to the Cahier's Relevé), the week (BilanView),
   the one primary «Retour à l'histoire».

   Query:
     ?week=YYYY-MM-DD   any day of a past week (default: this week so far)

   Reached from the Cahier → Relevé («Le bilan», BilanReleveSection), from Home's card
   after the week closes (BilanHomeCard) and from the Monday push
   (app/tasks/notifications.py, `send_bilan_pushes`). Off (`BILAN_ENABLED`): a 404 from
   the server, and this page says the bilan is not open. The fixtures are rendered in
   the dev gallery: /atelier-v2-gallery?bilan=full|thin|empty&lang=en|de|fr&theme=dark. */

import React, { useCallback, useEffect, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { ArrowLeftIcon, AtelierV2Root, IconAction, Skeleton, StateBlock } from '@/components/atelier-v2/ui';
import { BilanView } from '@/components/bilan/BilanView';
import { bilanCopy, normalizeBilanLanguage } from '@/components/bilan/bilan-copy';
import { browserSeenStore, markBilanSeen } from '@/components/bilan/bilan-model';
import { bilanClient } from '@/lib/bilan-api';
import type { Bilan } from '@/lib/bilan-types';
import { useChromeLanguage } from '@/lib/learner-language';

type PageState = { kind: 'loading' } | { kind: 'disabled' } | { kind: 'error' } | { kind: 'week'; bilan: Bilan };

const CAHIER = '/notebook?mode=releve#bilan';
const HOME = '/atelier';

function queryDay(value: string | string[] | undefined): string | null {
  const one = Array.isArray(value) ? value[0] : value;
  return one && /^\d{4}-\d{2}-\d{2}$/.test(one) ? one : null;
}

export default function BilanPage() {
  const router = useRouter();
  const language = normalizeBilanLanguage(useChromeLanguage());
  const copy = bilanCopy(language);
  const [state, setState] = useState<PageState>({ kind: 'loading' });
  const week = queryDay(router.query.week);

  const load = useCallback(async () => {
    setState({ kind: 'loading' });
    try {
      const result = await bilanClient().week(week);
      if (!result.enabled) {
        setState({ kind: 'disabled' });
        return;
      }
      // Opening a closed week is what Home's card was asking for.
      if (result.bilan.closed) markBilanSeen(result.bilan.weekStart, browserSeenStore());
      setState({ kind: 'week', bilan: result.bilan });
    } catch {
      setState({ kind: 'error' });
    }
  }, [week]);

  useEffect(() => {
    if (!router.isReady) return;
    void load();
  }, [router.isReady, load]);

  const back = useCallback(() => void router.push(CAHIER), [router]);
  const home = useCallback(() => void router.push(HOME), [router]);

  let body: React.ReactNode;
  if (state.kind === 'week') {
    // The server's chrome language wins once it answered (it is the learner's).
    const shown = state.bilan.language;
    body = <BilanView key={state.bilan.weekStart} bilan={state.bilan} copy={bilanCopy(shown)} onContinue={home} />;
  } else if (state.kind === 'disabled') {
    body = <StateBlock tone="empty" title={copy.disabled_title} body={copy.disabled_body} action={{ label: copy.back, onSelect: back }} />;
  } else if (state.kind === 'error') {
    body = <StateBlock tone="error" title={copy.error_title} body={copy.error_body} action={{ label: copy.retry, onSelect: () => void load() }} />;
  } else {
    body = (
      <div className="bl-loading" role="status" aria-busy="true" aria-label={copy.loading}>
        <Skeleton height={14} />
        <Skeleton height={64} />
        <Skeleton height={120} />
      </div>
    );
  }

  return (
    <>
      <Head>
        <title>{copy.page_title}</title>
      </Head>
      <AtelierV2Root as="main" language={language} className="bl-page" aria-label={copy.page_title}>
        <div className="bl-top">
          <IconAction label={copy.back} onClick={back}>
            <ArrowLeftIcon size={18} />
          </IconAction>
          <p className="bl-top__name">{copy.page_title}</p>
        </div>
        <div className="bl-body">{body}</div>
      </AtelierV2Root>
    </>
  );
}

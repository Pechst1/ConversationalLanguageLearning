/* WP-119 phase 1 · /revue — La Revue de Romy.

   Immersive like the journey session: the encounter draws its own head (× ·
   beats · the column); the × and the OS back go to La Une with nothing lost.

   Query:
     ?session=<id>   resume (a pure replay of the state)
     ?dossier=<id>   start that story (`chosen_by: learner`); ?story= is the same
     ?mock=1         DEV ONLY (never in a production build): the scripted server of
                     lib/revue-mock.ts instead of the API. ?lang=de|en|fr and
                     ?band=A1|A2|B1 shape the mock learner; ?reset=1 forgets it.

   States (design §3.7): loading (the 4:3 frame holds its size, «Romy rassemble
   ses notes», skeletons after 400 ms) · choose (from the chip) · the encounter ·
   ended (read-only, this week's Revue is filed) · the Revue switched off · the
   API failing (retry). The model being down mid-encounter is the encounter's own
   state (a quiet notice and Romy's authored line). */

import React, { useCallback, useEffect, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { AtelierV2Root, CastPortrait, Skeleton, StateBlock } from '@/components/atelier-v2/ui';
import { RvChooser, RvEncounter, RvSessionHead, RvStage, revueCopy } from '@/components/revue';
import { enterImmersiveSurface } from '@/lib/immersive-surface';
import { useChromeLanguage } from '@/lib/learner-language';
import { RevueError, revueClient, type RevueClient } from '@/lib/revue-api';
import type { RvLanguage, RvOffer, RvSessionView } from '@/lib/revue-types';

type PageState =
  | { kind: 'loading' }
  | { kind: 'disabled' }
  | { kind: 'error' }
  | { kind: 'choose'; offer: RvOffer; starting: boolean }
  | { kind: 'session'; session: RvSessionView };

const HOME = '/atelier';
const EMPTY_ROOM = { used: 0, phase: 'open' as const, remainingTurns: 0 };

function queryString(value: string | string[] | undefined): string | null {
  const one = Array.isArray(value) ? value[0] : value;
  return one && one.trim() ? one.trim() : null;
}

export default function RevuePage() {
  const router = useRouter();
  const learnerLanguage = useChromeLanguage();
  const mock = process.env.NODE_ENV !== 'production' && router.query.mock === '1';
  const langParam = queryString(router.query.lang);
  const language: RvLanguage = mock && (langParam === 'de' || langParam === 'en' || langParam === 'fr') ? langParam : learnerLanguage;
  const copy = revueCopy(language);
  const [client, setClient] = useState<RevueClient | null>(null);
  const [state, setState] = useState<PageState>({ kind: 'loading' });
  const [slow, setSlow] = useState(false);

  // The client: the API, or (dev only) the scripted mock, loaded on demand so it
  // never reaches a production bundle's main chunk.
  useEffect(() => {
    if (!router.isReady) return;
    let alive = true;
    // The literal NODE_ENV test lets the production build drop the mock chunk entirely.
    if (process.env.NODE_ENV !== 'production' && mock) {
      const band = queryString(router.query.band);
      void import('@/lib/revue-mock').then(({ createMockRevueClient }) => {
        if (!alive) return;
        const next = createMockRevueClient({
          language,
          band: band === 'A1' || band === 'B1' || band === 'B2' ? band : 'A2',
          latency: 450,
        });
        if (router.query.reset === '1') next.reset();
        setClient(next);
      });
    } else {
      setClient(revueClient());
    }
    return () => {
      alive = false;
    };
    // The client is built once per page load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.isReady, mock]);

  // Skeleton lines only after 400 ms (design §3.7 #loading).
  useEffect(() => {
    if (state.kind !== 'loading') {
      setSlow(false);
      return undefined;
    }
    const timer = window.setTimeout(() => setSlow(true), 400);
    return () => window.clearTimeout(timer);
  }, [state.kind]);

  // Keep the session in the URL, so a reload resumes it.
  const showSession = useCallback(
    (session: RvSessionView) => {
      setState({ kind: 'session', session });
      const { session: current, dossier, story, reset, ...rest } = router.query;
      void current;
      void dossier;
      void story;
      void reset;
      if (router.query.session !== session.id) {
        void router.replace({ pathname: '/revue', query: { ...rest, session: session.id } }, undefined, { shallow: true });
      }
    },
    [router],
  );

  /** A start refused with «resume it instead» / «filed this week» opens that session. */
  const startOrResume = useCallback(
    async (active: RevueClient, dossierId: string | null) => {
      try {
        showSession(await active.start(dossierId ? { dossierId } : {}));
      } catch (error) {
        if (error instanceof RevueError && error.sessionId && (error.code === 'revue_session_active' || error.code === 'revue_week_filed')) {
          showSession(await active.session(error.sessionId));
          return;
        }
        throw error;
      }
    },
    [showSession],
  );

  const load = useCallback(async () => {
    if (!client) return;
    setState({ kind: 'loading' });
    const sessionId = queryString(router.query.session);
    const dossierId = queryString(router.query.dossier) ?? queryString(router.query.story);
    try {
      if (sessionId) {
        try {
          showSession(await client.session(sessionId));
          return;
        } catch (error) {
          if (!(error instanceof RevueError && error.code === 'revue_session_not_found')) throw error;
          // An old link: fall through to the week.
        }
      }
      if (dossierId) {
        await startOrResume(client, dossierId);
        return;
      }
      const week = await client.week();
      if (!week.enabled) {
        setState({ kind: 'disabled' });
        return;
      }
      const offer = week.offer;
      if (offer.resume) {
        showSession(await client.session(offer.resume.sessionId));
        return;
      }
      if (offer.filed) {
        showSession(await client.session(offer.filed.sessionId));
        return;
      }
      if (!offer.recommended) {
        setState({ kind: 'disabled' });
        return;
      }
      setState({ kind: 'choose', offer, starting: false });
    } catch (error) {
      if (error instanceof RevueError && error.code === 'revue_disabled') setState({ kind: 'disabled' });
      else setState({ kind: 'error' });
    }
    // The query is read once per load; a shallow replace after a start must not reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  // Immersive while the encounter is on screen: floating chrome stands down.
  const inEncounter = state.kind === 'session';
  useEffect(() => (inEncounter ? enterImmersiveSurface() : undefined), [inEncounter]);

  const exit = useCallback(() => {
    void router.push(HOME);
  }, [router]);

  const pick = async (dossierId: string | null) => {
    if (!client || state.kind !== 'choose') return;
    setState({ ...state, starting: true });
    try {
      await startOrResume(client, dossierId);
    } catch {
      setState({ kind: 'error' });
    }
  };

  let body: React.ReactNode;
  if (state.kind === 'session' && client) {
    const week = state.session.week.iso;
    body = (
      <RvEncounter
        key={state.session.id}
        client={client}
        session={state.session}
        language={language}
        onExit={exit}
        onReleve={() => void router.push(`/notebook?mode=releve#revue-${week}`)}
      />
    );
  } else if (state.kind === 'choose' && state.offer.recommended && client) {
    body = (
      <>
        <div className="rv-top">
          <RvSessionHead beat={null} room={EMPTY_ROOM} onExit={exit} copy={copy} />
        </div>
        <div className="rv-body">
          <RvChooser
            recommended={state.offer.recommended}
            alternatives={state.offer.alternatives}
            week={state.offer.week}
            pending={state.starting}
            onPick={(id) => void pick(id)}
            onAsk={(text) => client.match(text, state.offer.week.iso)}
            copy={copy}
          />
        </div>
      </>
    );
  } else if (state.kind === 'disabled') {
    body = (
      <div className="rv-body">
        <StateBlock tone="empty" title={copy.disabled_title} body={copy.disabled_body} action={{ label: copy.back_home, onSelect: exit }} />
      </div>
    );
  } else if (state.kind === 'error') {
    body = (
      <div className="rv-body">
        <StateBlock tone="error" title={copy.error_title} body={copy.error_body} action={{ label: copy.retry, onSelect: () => void load() }} />
      </div>
    );
  } else {
    body = (
      <div className="rv-loading" role="status" aria-busy="true" aria-label={copy.loading}>
        <div className="rv-top">
          <RvSessionHead beat={null} room={EMPTY_ROOM} onExit={exit} copy={copy} />
        </div>
        <RvStage plateUrl={null} size="full" cast={[]} />
        <div className="rv-body">
          <div className="rv-typing">
            <CastPortrait characterId="romy_tremblay" name="Romy" size="xs" ring />
            <p>
              <span>{copy.loading_line}</span>
              <span className="rv-dots" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
            </p>
          </div>
          {slow && (
            <>
              <Skeleton height={18} />
              <Skeleton height={18} />
              <Skeleton height={96} />
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <>
      <Head>
        <title>La Revue de Romy</title>
      </Head>
      <AtelierV2Root as="main" language={language} className="rv-page" aria-label="La Revue de Romy" data-revue-mock={mock ? '' : undefined}>
        {body}
        {mock && <p className="rv-mock">{copy.mock_badge}</p>}
      </AtelierV2Root>
    </>
  );
}

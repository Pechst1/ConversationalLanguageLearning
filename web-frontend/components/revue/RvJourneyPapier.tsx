/**
 * WP-119 phase 3 · the Papier inside the journey player (design §2 «Inside the
 * journey player»).
 *
 * On a Revue day (`DayShape.REVUE`) the planner deals a classic, short story day
 * (scene, recall, reply, ending); once it is finished the player mounts this in
 * place of the recap. It reads the week, opens the Papier — resume the one in
 * progress, else start the recommendation — and draws the ONE `RvEncounter`
 * (there is no second encounter built from step views). The × and «Classer la
 * Revue» both call `onDone`, and the player then shows the day's recap.
 *
 * Nothing to do (the Revue is off, nothing recommended, this week's Papier
 * already filed) calls `onDone` at once. A failure says so quietly and offers
 * «Continuer»: the day is never blocked by the Revue.
 */

import React, { useCallback, useEffect, useState } from 'react';
import Router from 'next/router';

import { AtelierV2Root, CastPortrait, StateBlock } from '@/components/atelier-v2/ui';
import { enterImmersiveSurface } from '@/lib/immersive-surface';
import { RevueError, revueClient, type RevueClient } from '@/lib/revue-api';
import { releveAnchor } from '@/lib/revue-releve';
import type { RvLanguage, RvSessionView, RvWeekResult } from '@/lib/revue-types';

import { releveCopy } from './releve-copy';
import { revueCopy } from './revue-copy';
import { RvEncounter } from './RvEncounter';

export type RvJourneyPapierProps = {
  language: unknown;
  onDone: () => void;
  client?: RevueClient;
};

export type PapierEntryAction = 'done' | 'resume' | 'start';

/** What the player does with the week's answer. Pure, tested. */
export function papierEntryAction(week: RvWeekResult | null | undefined): PapierEntryAction {
  if (!week || !week.enabled) return 'done';
  const offer = week.offer;
  if (offer.resume) return 'resume';
  if (offer.filed) return 'done';
  if (!offer.recommended) return 'done';
  return 'start';
}

/** The Relevé's anchor for a period: `/notebook?mode=releve#revue-2026-W40`. */
export function papierReleveHref(period: string): string {
  return `/notebook?mode=releve#${releveAnchor(period)}`;
}

const asLanguage = (language: unknown): RvLanguage => (language === 'en' || language === 'de' ? language : 'fr');

type State = { kind: 'loading' } | { kind: 'error' } | { kind: 'session'; session: RvSessionView };

export function RvJourneyPapier({ language, onDone, client: given }: RvJourneyPapierProps) {
  const chrome = asLanguage(language);
  const copy = revueCopy(chrome);
  const releve = releveCopy(chrome);
  const [client] = useState<RevueClient | null>(() => given ?? null);
  const [state, setState] = useState<State>({ kind: 'loading' });

  // The player's own header stands down: the encounter draws its head (× · beats).
  useEffect(() => enterImmersiveSurface(), []);

  const load = useCallback(async () => {
    const active = client ?? revueClient();
    setState({ kind: 'loading' });
    try {
      const week = await active.week();
      const action = papierEntryAction(week);
      if (action === 'done' || !week.enabled) {
        onDone();
        return;
      }
      if (action === 'resume' && week.offer.resume) {
        setState({ kind: 'session', session: await active.session(week.offer.resume.sessionId) });
        return;
      }
      try {
        setState({ kind: 'session', session: await active.start({}) });
      } catch (error) {
        // «Resume it instead» / «filed this week»: open that session (as /revue does).
        if (
          error instanceof RevueError &&
          error.sessionId &&
          (error.code === 'revue_session_active' || error.code === 'revue_week_filed')
        ) {
          setState({ kind: 'session', session: await active.session(error.sessionId) });
          return;
        }
        throw error;
      }
    } catch (error) {
      if (error instanceof RevueError && error.code === 'revue_disabled') onDone();
      else setState({ kind: 'error' });
    }
    // One read per mount; `onDone` is the player's setter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  let body: React.ReactNode;
  if (state.kind === 'session') {
    const period = state.session.week.iso;
    body = (
      <RvEncounter
        key={state.session.id}
        client={client ?? revueClient()}
        session={state.session}
        language={chrome}
        onExit={onDone}
        onReleve={() => void Router.push(papierReleveHref(period))}
      />
    );
  } else if (state.kind === 'error') {
    body = (
      <div className="rv-body">
        <StateBlock
          tone="error"
          title={copy.error_title}
          body={releve.papier_error}
          action={{ label: copy.continue, tone: 'primary', onSelect: onDone }}
        />
      </div>
    );
  } else {
    body = (
      <div className="rv-body">
        <div className="rv-typing" role="status" aria-busy="true" aria-label={copy.loading}>
          <CastPortrait characterId="romy_tremblay" name="Romy" size="xs" ring />
          <p>
            <span>{releve.papier_loading}</span>
            <span className="rv-dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
          </p>
        </div>
      </div>
    );
  }

  return (
    <AtelierV2Root language={chrome} className="rv-page" data-revue-journey={state.kind}>
      {body}
    </AtelierV2Root>
  );
}

export default RvJourneyPapier;

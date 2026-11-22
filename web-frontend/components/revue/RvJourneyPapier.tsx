/**
 * WP-119 phase 3 · the Papier inside the journey player (design §2 «Inside the
 * journey player»).
 *
 * On a Revue day (`DayShape.REVUE`) the planner deals a classic, short story day
 * (scene, recall, reply, ending); once it is finished the player mounts this in
 * place of the recap. It reads the week, opens the Papier — resume the one in
 * progress, else start the recommendation — and draws the ONE `RvEncounter`
 * (there is no second encounter built from step views) — or, for a session in
 * «Au comptoir» mode, the ONE `RvComptoir`. The × and «Classer la Revue» both call
 * `onDone`, and the player then shows the day's recap.
 *
 * «Papier · le choix» (2026-11-22): when the week carries a front page (`offer.choices`,
 * REVUE_CHOICE_ENABLED), the learner picks the story there; one tap starts it.
 *
 * Nothing to do (the Revue is off, nothing recommended, this week's Papier
 * already filed) calls `onDone` at once. A failure says so quietly and offers
 * «Continuer»: the day is never blocked by the Revue.
 */

import React, { useCallback, useEffect, useState } from 'react';
import Router from 'next/router';

import { AtelierV2Root, CastPortrait, CrossIcon, IconAction, StateBlock } from '@/components/atelier-v2/ui';
import { enterImmersiveSurface } from '@/lib/immersive-surface';
import { RevueError, revueClient, type RevueClient } from '@/lib/revue-api';
import { releveAnchor } from '@/lib/revue-releve';
import type { RvLanguage, RvOffer, RvSessionView, RvWeekResult } from '@/lib/revue-types';

import { RvChoix } from './choix/RvChoix';
import { PpBareHead } from './papier/PapierPrint';

import { releveCopy } from './releve-copy';
import { revueCopy } from './revue-copy';
import { RvComptoir } from './comptoir/RvComptoir';
import { RvFil } from './fil/RvFil';
import { RvRubrique } from './rubriques/RvRubrique';
import { RvEncounter } from './RvEncounter';
import { VoixProvider } from './voix/VoixContext';
import { voixClient } from '@/lib/revue-voix';

export type RvJourneyPapierProps = {
  language: unknown;
  onDone: () => void;
  client?: RevueClient;
};

export type PapierEntryAction = 'done' | 'resume' | 'choose' | 'start';

/** What the player does with the week's answer. Pure, tested. */
export function papierEntryAction(week: RvWeekResult | null | undefined): PapierEntryAction {
  if (!week || !week.enabled) return 'done';
  const offer = week.offer;
  if (offer.resume) return 'resume';
  if (offer.filed) return 'done';
  if (!offer.recommended) return 'done';
  return offer.choices?.length ? 'choose' : 'start';
}

/** The Relevé's anchor for a period: `/notebook?mode=releve#revue-2026-W40`. */
export function papierReleveHref(period: string): string {
  return `/notebook?mode=releve#${releveAnchor(period)}`;
}

const asLanguage = (language: unknown): RvLanguage => (language === 'en' || language === 'de' ? language : 'fr');

type State =
  | { kind: 'loading' }
  | { kind: 'error' }
  | { kind: 'choose'; offer: RvOffer; picked: string | null }
  | { kind: 'session'; session: RvSessionView };

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
      if (action === 'choose') {
        setState({ kind: 'choose', offer: week.offer, picked: null });
        return;
      }
      await open(active, null);
    } catch (error) {
      if (error instanceof RevueError && error.code === 'revue_disabled') onDone();
      else setState({ kind: 'error' });
    }
    // One read per mount; `onDone` is the player's setter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  /** Start the story (`null`: Romy's pick); «resume it instead» / «filed» opens that session. */
  const open = async (active: RevueClient, dossierId: string | null, assignment: string | null = null) => {
    try {
      setState({ kind: 'session', session: await active.start(dossierId ? { dossierId, ...(assignment ? { assignment } : {}) } : {}) });
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
  };

  const pick = (dossierId: string, assignment: string | null = null) => {
    if (state.kind !== 'choose' || state.picked) return;
    setState({ ...state, picked: dossierId });
    void open(client ?? revueClient(), dossierId, assignment).catch(() => setState({ kind: 'error' }));
  };

  useEffect(() => {
    void load();
  }, [load]);

  let body: React.ReactNode;
  if (state.kind === 'session') {
    const period = state.session.week.iso;
    // «Au comptoir»: the counter's debate in place of the chat, with the same props.
    // «Le fil» (2026-11-20): the assignment the session was dealt.
    // «Le titre», «L'intox express»: one player for both.
    const mode = state.session.mode;
    const Player = mode === 'comptoir' ? RvComptoir : mode === 'fil' ? RvFil : mode === 'titre' || mode === 'intox' || mode === 'photo' || mode === 'micro' ? RvRubrique : RvEncounter;
    body = (
      <Player
        key={state.session.id}
        client={client ?? revueClient()}
        session={state.session}
        language={chrome}
        onExit={onDone}
        onReleve={() => void Router.push(papierReleveHref(period))}
      />
    );
  } else if (state.kind === 'choose') {
    body = (
      <>
        <div className="rv-top">
          <PpBareHead>
            <IconAction label={copy.exit_label} onClick={onDone}>
              <CrossIcon size={16} />
            </IconAction>
          </PpBareHead>
        </div>
        <div className="rv-body">
          <RvChoix
            choices={state.offer.choices ?? []}
            week={state.offer.week}
            editionDate={state.offer.editionDate ?? null}
            whyLanguage={state.offer.whyLanguage ?? chrome}
            language={chrome}
            pending={state.picked}
            onPick={pick}
            copy={copy}
          />
        </div>
      </>
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
      {/* «Papier · la voix»: the real client only beside the real API (a scripted client stays silent). */}
      <VoixProvider client={state.kind === 'session' && !client ? voixClient() : null}>{body}</VoixProvider>
    </AtelierV2Root>
  );
}

export default RvJourneyPapier;

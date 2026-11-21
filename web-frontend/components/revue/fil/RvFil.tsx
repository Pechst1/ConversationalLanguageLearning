/**
 * «Le fil» (WIRE §10, owner 2026-11-20) · RvFil — the player of the assignment
 * «Le fil», mounted by `/revue` and the journey's Papier when the session's `mode`
 * is `fil`, with the same props as `RvComptoir`.
 *
 * Five screens — «Lire», «Remettre en ordre», «Les mots du fil», «Raconter», «La
 * page» — under the comptoir's head (× and the step dots), each with one main button
 * in a sticky foot. The server owns the state: every act goes to `POST …/fil` and the
 * returned view is rendered as is (a resume lands on the right screen). An act the
 * server does not record comes back with its `error` code, said here in the learner's
 * language; an act out of order (409) re-reads the session; a failure is one quiet line.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Notice } from '@/components/atelier-v2/ui';
import { useLineVoice } from '@/components/atelier-v2/journey/useLineVoice';
import { FeuilletonReaderStyles } from '@/components/feuilleton/reader/reader-styles';
import { WordHelpSheet, type WordHelpRequest } from '@/components/feuilleton/reader/WordHelpSheet';
import { RevueError, type RevueClient } from '@/lib/revue-api';
import type { RvFilBody, RvFilError, RvFilStep } from '@/lib/revue-fil-types';
import type { RvLanguage, RvSessionView } from '@/lib/revue-types';

import { comptoirCopy } from '../comptoir/comptoir-copy';
import { RvComptoirHead } from '../comptoir/RvComptoirParts';
import { scrollerOf } from '../comptoir/scroll';
import { revueCopy } from '../revue-copy';
import { knownGloss, sessionGlosses } from '../revue-model';
import type { RvWordEvent } from '../RvThread';
import { PpPlayerSection, PpTranslateSet } from '../papier/PapierPrint';
import { FIL_FR, filCopy, FIL_STEP_LABELS_FR } from './fil-copy';
import { clampStep, errorText, nextStep, openingStep, stepOrder } from './fil-model';
import { RvFilOrder, RvFilRead, RvFilWords, type FilStepProps } from './RvFilSteps';
import { RvFilPage } from './RvFilPage';
import { RvFilTell } from './RvFilTell';

export type RvFilProps = {
  client: RevueClient;
  /** The session as the server sent it; `mode` is `fil`. */
  session: RvSessionView;
  /** Chrome language; defaults to the plan's `ui_language`. */
  language?: RvLanguage;
  onExit: () => void;
  onReleve?: () => void;
  /** La Carte's «Relire»: the screens as they stand, nothing sent. */
  readOnly?: boolean;
  now?: Date;
};

const ROMY = 'romy_tremblay';

export function RvFil({ client, session: initial, language, onExit, onReleve, readOnly = false }: RvFilProps) {
  const [session, setSession] = useState<RvSessionView>(initial);
  const [ended] = useState(initial.status !== 'active');
  const closed = session.status !== 'active' || Boolean(session.closing);
  const view = session.fil;
  const [shown, setShown] = useState<RvFilStep>(() => (view ? openingStep(view, closed) : 'read'));
  const [pending, setPending] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<RvFilError | null>(null);
  const [failed, setFailed] = useState(false);
  const [word, setWord] = useState<WordHelpRequest | null>(null);
  const footRef = useRef<HTMLDivElement | null>(null);
  const voice = useLineVoice();

  const shownId = useRef(initial.id);
  useEffect(() => {
    if (shownId.current === initial.id) return;
    shownId.current = initial.id;
    setSession(initial);
    if (initial.fil) setShown(openingStep(initial.fil, initial.status !== 'active' || Boolean(initial.closing)));
  }, [initial]);

  const chrome: RvLanguage = language ?? session.plan.uiLanguage;
  const copy = revueCopy(chrome);
  const ccopy = comptoirCopy(chrome);
  const fcopy = filCopy(chrome);
  const glossLanguage = session.plan.glossLanguage;
  const xcopy = filCopy(glossLanguage);
  const glosses = useMemo(() => sessionGlosses(session), [session]);

  // As the counter and the rubriques (2026-11-21): a new screen opens at its top, never under the head.
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const firstStep = useRef(true);
  useEffect(() => {
    if (firstStep.current) {
      firstStep.current = false;
      return;
    }
    const scroller = scrollerOf(bodyRef.current);
    if (scroller && typeof scroller.scrollTo === 'function') scroller.scrollTo({ top: 0 });
  }, [shown]);

  const serverStep = view?.step ?? 'read';
  useEffect(() => {
    if (!view) return;
    setShown((current) => (closed ? 'page' : clampStep(view, current, closed)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverStep, closed]);

  const wordFor = useCallback(
    (speakerId: string | null, speakerName?: string) => (event: RvWordEvent) => {
      const term = event.word.toLowerCase().replace(/^(l|d|qu|j|n|s|c|m|t)['’]/, '');
      const known = event.gloss || knownGloss(event.word, glosses, event.sentence) || knownGloss(term, glosses, event.sentence);
      setWord({
        surface: event.word,
        term,
        sentence: event.sentence,
        speaker: event.speaker ?? speakerName,
        speakerId: speakerId ?? ROMY,
        knownGloss: known,
        knownGlossLanguage: known ? glossLanguage : null,
      });
    },
    [glossLanguage, glosses],
  );

  const reread = useCallback(async () => {
    try {
      setSession(await client.session(session.id));
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, [client, session.id]);

  const onAct = useCallback(
    async (body: RvFilBody, key: string): Promise<boolean> => {
      if (readOnly || pending || !client.fil) return false;
      setPending(key);
      setFailed(false);
      setRefusal(null);
      try {
        const result = await client.fil(session.id, body);
        setSession(result.session);
        setRefusal(result.error);
        return !result.error;
      } catch (error) {
        if (error instanceof RevueError && (error.code === 'revue_fil_out_of_order' || error.code === 'revue_session_closed' || error.code === 'revue_not_fil')) {
          await reread();
        } else {
          setFailed(true);
        }
        return false;
      } finally {
        setPending(null);
      }
    },
    [client, pending, readOnly, reread, session.id],
  );

  const closePapier = useCallback(async () => {
    if (pending) return;
    setPending('close');
    setFailed(false);
    try {
      const result = await client.close(session.id);
      setSession({ ...result.session, closing: result.closing });
      setShown('page');
    } catch (error) {
      if (error instanceof RevueError && error.code === 'revue_fil_out_of_order') await reread();
      else setFailed(true);
    } finally {
      setPending(null);
    }
  }, [client, pending, reread, session.id]);

  const onContinue = useCallback(() => {
    if (!view || pending) return;
    if (shown === 'tell') {
      void closePapier();
      return;
    }
    if (shown === 'read' && view.step === 'read') {
      void onAct({ act: 'open' }, 'open').then((ok) => ok && setShown('order'));
      return;
    }
    const next = nextStep(shown);
    if (!next || next === 'page' || stepOrder(next) > stepOrder(openingStep(view, closed))) return;
    setRefusal(null);
    setFailed(false);
    setShown(next);
  }, [closePapier, closed, onAct, pending, shown, view]);

  if (!view) return null;

  const notice = (
    <>
      {refusal && (
        <p className="ct-why fl-refusal" role="status" data-ct-anchor="nearest">
          {errorText(refusal.code.startsWith('tell_') ? xcopy : fcopy, refusal, view)}
        </p>
      )}
      {failed && (
        <Notice tone="quiet" shape="action">
          <p>{ccopy.act_failed}</p>
        </Notice>
      )}
    </>
  );

  const props: FilStepProps = {
    session,
    view,
    chrome,
    copy,
    ccopy,
    fcopy,
    xcopy,
    glossLanguage,
    glosses,
    voice,
    pending,
    readOnly: readOnly || ended,
    onAct,
    onContinue,
    wordFor,
    notice,
    footRef,
  };

  let step: React.ReactNode;
  if (shown === 'page' && closed) step = <RvFilPage props={props} ended={ended || readOnly} onExit={onExit} onReleve={onReleve} />;
  else if (shown === 'order' && view.order) step = <RvFilOrder {...props} />;
  else if (shown === 'words' && view.words) step = <RvFilWords {...props} />;
  else if ((shown === 'tell' || shown === 'page') && view.tell) step = <RvFilTell {...props} />;
  else step = <RvFilRead {...props} />;

  return (
    <div ref={bodyRef} className="rv-encounter ct-player fl-player" data-step={shown} data-band={view.band} data-ended={ended ? '' : undefined} data-readonly={readOnly ? '' : undefined}>
      <div className="rv-top">
        <RvComptoirHead
          steps={view.steps}
          shown={shown}
          closed={closed}
          back={ended || readOnly}
          onExit={onExit}
          copy={copy}
          ccopy={ccopy}
          labels={FIL_STEP_LABELS_FR}
          opening={shown === 'read'}
        />
      </div>
      <PpTranslateSet key={shown}>
        <PpPlayerSection
          session={session}
          section={FIL_FR.name}
          step={FIL_STEP_LABELS_FR[shown] ?? null}
          shown={shown}
          set={shown === 'order' || shown === 'words'}
          language={glossLanguage}
        />
        {step}
      </PpTranslateSet>
      <FeuilletonReaderStyles />
      <WordHelpSheet request={word} onClose={() => setWord(null)} language={chrome} note={null} quoteLabel={copy.word_in_text} />
    </div>
  );
}

export default RvFil;

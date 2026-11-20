/**
 * «Le titre» and «L'intox express» (WIRE §11, 2026-11-20) · RvRubrique — the player of both
 * assignments, mounted by `/revue` and the journey's Papier when the session's `mode` is
 * `titre` or `intox`, with the same props as `RvFil`.
 *
 * «Le titre»: «Lire», «Trois titres», «Le piège», «À toi», «La page». «L'intox express»:
 * «Lire», «Vrai ou faux», «Corrige», «La page». Under the comptoir's head (× and the step
 * dots), each screen with one main button in a sticky foot. The server owns the state: every
 * act goes to `POST …/rubrique` and the returned view is rendered as is (a resume lands on
 * the right screen). An act the server does not record comes back with its `error` code,
 * said here in the learner's language; an act out of order (409) re-reads the session; a
 * failure is one quiet line.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Notice } from '@/components/atelier-v2/ui';
import { useLineVoice } from '@/components/atelier-v2/journey/useLineVoice';
import { FeuilletonReaderStyles } from '@/components/feuilleton/reader/reader-styles';
import { WordHelpSheet, type WordHelpRequest } from '@/components/feuilleton/reader/WordHelpSheet';
import { RevueError, type RevueClient } from '@/lib/revue-api';
import type { RvRubriqueBody, RvRubriqueError } from '@/lib/revue-rubriques-types';
import type { RvLanguage, RvSessionView } from '@/lib/revue-types';

import { comptoirCopy } from '../comptoir/comptoir-copy';
import { RvComptoirHead } from '../comptoir/RvComptoirParts';
import { revueCopy } from '../revue-copy';
import { knownGloss, sessionGlosses } from '../revue-model';
import type { RvWordEvent } from '../RvThread';
import { INTOX_FR, INTOX_STEP_LABELS_FR, rubriqueCopy, TITRE_FR, TITRE_STEP_LABELS_FR } from './rubriques-copy';
import { bringNewestIntoView, scrollerOf } from '../comptoir/scroll';
import { clampStep, errorText, nextStep, openingStep, refusalCopy, rubriqueProgress, stepOrder } from './rubriques-model';
import { RvIntoxFix, RvIntoxRound } from './RvIntoxSteps';
import { RvRubriquePage } from './RvRubriquePages';
import { RvRubriqueRead, type RubriqueStepProps } from './RvRubriqueParts';
import { RvTitreBuild, RvTitreThree, RvTitreTrap } from './RvTitreSteps';
import { MICRO_FR, MICRO_STEP_LABELS_FR, PHOTO_FR, PHOTO_STEP_LABELS_FR, photoMicroCopy } from './photo-micro-copy';
import { photoMicroProgress, pmErrorText } from './photo-micro-model';
import { RvMicroInterview, RvMicroNotes, RvMicroPrepare, RvMicroReview } from './RvMicroSteps';
import { RvPhotoBuild, RvPhotoLegende, RvPhotoPlanche } from './RvPhotoSteps';

export type RvRubriqueProps = {
  client: RevueClient;
  /** The session as the server sent it; `mode` is `titre` or `intox`. */
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

/** An act the session has moved past: re-read it rather than say it failed. */
function stale(error: unknown): boolean {
  return (
    error instanceof RevueError &&
    (error.code === 'revue_titre_out_of_order' ||
      error.code === 'revue_intox_out_of_order' ||
      error.code === 'revue_photo_out_of_order' ||
      error.code === 'revue_micro_out_of_order' ||
      error.code === 'revue_session_closed' ||
      error.code === 'revue_not_rubrique')
  );
}

function viewOf(session: RvSessionView) {
  if (session.mode === 'titre') return session.titre;
  if (session.mode === 'intox') return session.intox;
  if (session.mode === 'photo') return session.photo;
  if (session.mode === 'micro') return session.micro;
  return null;
}

/** The modes this player plays (WIRE §11–12). */
export const RUBRIQUE_MODES = ['titre', 'intox', 'photo', 'micro'] as const;
export function isRubriqueMode(mode: string): boolean {
  return (RUBRIQUE_MODES as readonly string[]).includes(mode);
}

export function RvRubrique({ client, session: initial, language, onExit, onReleve, readOnly = false }: RvRubriqueProps) {
  const [session, setSession] = useState<RvSessionView>(initial);
  const [ended] = useState(initial.status !== 'active');
  const closed = session.status !== 'active' || Boolean(session.closing);
  const view = viewOf(session);
  const [shown, setShown] = useState<string>(() => (view ? openingStep(view, closed) : 'read'));
  const [pending, setPending] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<RvRubriqueError | null>(null);
  const [failed, setFailed] = useState(false);
  const [word, setWord] = useState<WordHelpRequest | null>(null);
  const footRef = useRef<HTMLDivElement | null>(null);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const headRef = useRef<HTMLDivElement | null>(null);
  const voice = useLineVoice();

  const shownId = useRef(initial.id);
  useEffect(() => {
    if (shownId.current === initial.id) return;
    shownId.current = initial.id;
    setSession(initial);
    const next = viewOf(initial);
    if (next) setShown(openingStep(next, initial.status !== 'active' || Boolean(initial.closing)));
  }, [initial]);

  const chrome: RvLanguage = language ?? session.plan.uiLanguage;
  const copy = revueCopy(chrome);
  const ccopy = comptoirCopy(chrome);
  const rcopy = rubriqueCopy(chrome);
  const glossLanguage = session.plan.glossLanguage;
  // The reasons (a wrong headline's lead-in, the trap's true words, a refused headline): the
  // mother tongue, as the counter's whys, while the chrome is French from B1.
  const xcopy = rubriqueCopy(glossLanguage);
  const glosses = useMemo(() => sessionGlosses(session), [session]);

  const serverStep = view?.step ?? 'read';
  useEffect(() => {
    if (!view) return;
    setShown((current) => (closed ? 'page' : clampStep(view, current, closed)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverStep, closed]);

  // As the counter (seen at 375 px, 2026-11-20): a new screen starts at its top; on the same
  // screen, after an act, the newest part (a verdict, a why, Romy's marks) comes into view.
  const firstStep = useRef(true);
  useEffect(() => {
    if (firstStep.current) {
      firstStep.current = false;
      return;
    }
    const scroller = scrollerOf(bodyRef.current);
    if (scroller && typeof scroller.scrollTo === 'function') scroller.scrollTo({ top: 0 });
  }, [shown]);
  const progress = `${rubriqueProgress(session)}#${photoMicroProgress(session)}`;
  const lastProgress = useRef(progress);
  useEffect(() => {
    if (lastProgress.current === progress) return;
    lastProgress.current = progress;
    bringNewestIntoView(bodyRef.current, headRef.current, footRef.current);
  }, [progress]);

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
    async (body: RvRubriqueBody, key: string): Promise<boolean> => {
      if (readOnly || pending || !client.rubrique) return false;
      setPending(key);
      setFailed(false);
      setRefusal(null);
      try {
        const result = await client.rubrique(session.id, body);
        setSession(result.session);
        setRefusal(result.error);
        return !result.error;
      } catch (error) {
        if (stale(error)) await reread();
        else setFailed(true);
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
      if (stale(error)) await reread();
      else setFailed(true);
    } finally {
      setPending(null);
    }
  }, [client, pending, reread, session.id]);

  const onContinue = useCallback(() => {
    if (!view || pending) return;
    if (nextStep(view, shown) === 'page') {
      void closePapier();
      return;
    }
    if (shown === 'read' && view.step === 'read') {
      void onAct({ act: 'open' }, 'open').then((ok) => ok && setShown(view.steps[1]));
      return;
    }
    const next = nextStep(view, shown);
    if (!next || stepOrder(view, next) > stepOrder(view, openingStep(view, closed))) return;
    setRefusal(null);
    setFailed(false);
    setShown(next);
  }, [closePapier, closed, onAct, pending, shown, view]);

  if (!view || !isRubriqueMode(session.mode)) return null;
  const pmMode = session.mode === 'photo' || session.mode === 'micro';

  const notice = (
    <>
      {refusal && (
        <p className="ct-why rb-refusal" role="status" data-ct-anchor="nearest">
          {pmMode
            ? pmErrorText(refusal, photoMicroCopy(chrome), photoMicroCopy(glossLanguage))
            : errorText(refusalCopy(refusal.code, rcopy, xcopy), refusal, session.titre?.build?.avoidFr ?? '')}
        </p>
      )}
      {failed && (
        <Notice tone="quiet" shape="action">
          <p>{ccopy.act_failed}</p>
        </Notice>
      )}
    </>
  );

  const props: RubriqueStepProps = {
    session,
    chrome,
    copy,
    ccopy,
    rcopy,
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
  if (shown === 'page' && closed) {
    const tiles = (session.titre?.build?.input ?? session.photo?.build?.input) === 'tiles';
    step = <RvRubriquePage props={props} ended={ended || readOnly} tiles={tiles} onExit={onExit} onReleve={onReleve} />;
  } else if (session.mode === 'titre' && session.titre) {
    const titre = session.titre;
    const tprops = { ...props, view: titre };
    if (shown === 'three' && titre.three) step = <RvTitreThree {...tprops} />;
    else if (shown === 'trap' && titre.trap) step = <RvTitreTrap {...tprops} />;
    else if ((shown === 'build' || shown === 'page') && titre.build) step = <RvTitreBuild {...tprops} />;
    else step = <RvRubriqueRead read={titre.read} press={TITRE_FR.press} props={props} />;
  } else if (session.mode === 'photo' && session.photo) {
    const photo = session.photo;
    const pprops = { ...props, view: photo };
    if (shown === 'planche' && photo.planche) step = <RvPhotoPlanche {...pprops} />;
    else if (shown === 'legende' && photo.legende) step = <RvPhotoLegende {...pprops} />;
    else if ((shown === 'build' || shown === 'page') && photo.build) step = <RvPhotoBuild {...pprops} />;
    else step = <RvRubriqueRead read={photo.read} press={PHOTO_FR.press} props={props} />;
  } else if (session.mode === 'micro' && session.micro) {
    const micro = session.micro;
    const mprops = { ...props, view: micro };
    if (shown === 'prepare' && micro.prepare) step = <RvMicroPrepare {...mprops} />;
    else if (shown === 'interview' && micro.interview) step = <RvMicroInterview {...mprops} />;
    else if (shown === 'notes' && micro.notes) step = <RvMicroNotes {...mprops} />;
    else if ((shown === 'review' || shown === 'page') && micro.review) step = <RvMicroReview {...mprops} />;
    else step = <RvRubriqueRead read={micro.read} press={MICRO_FR.press} props={props} />;
  } else if (session.intox) {
    const intox = session.intox;
    const iprops = { ...props, view: intox };
    if (shown === 'round' && intox.round) step = <RvIntoxRound {...iprops} />;
    else if ((shown === 'fix' || shown === 'page') && intox.fix) step = <RvIntoxFix {...iprops} />;
    else step = <RvRubriqueRead read={intox.read} press={INTOX_FR.press} props={props} />;
  }

  return (
    <div
      className="rv-encounter ct-player rb-player"
      data-mode={session.mode}
      data-step={shown}
      data-band={view.band}
      data-ended={ended ? '' : undefined}
      data-readonly={readOnly ? '' : undefined}
      ref={bodyRef}
    >
      <div className="rv-top" ref={headRef}>
        <RvComptoirHead
          steps={view.steps}
          shown={shown}
          closed={closed}
          back={ended || readOnly}
          onExit={onExit}
          copy={copy}
          ccopy={ccopy}
          labels={
            session.mode === 'titre'
              ? TITRE_STEP_LABELS_FR
              : session.mode === 'photo'
                ? PHOTO_STEP_LABELS_FR
                : session.mode === 'micro'
                  ? MICRO_STEP_LABELS_FR
                  : INTOX_STEP_LABELS_FR
          }
        />
      </div>
      {step}
      <FeuilletonReaderStyles />
      <WordHelpSheet request={word} onClose={() => setWord(null)} language={chrome} note={null} quoteLabel={copy.word_in_text} />
    </div>
  );
}

export default RvRubrique;

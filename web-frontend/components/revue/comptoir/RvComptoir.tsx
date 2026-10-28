/**
 * «Au comptoir» (WP-119-AU-COMPTOIR §5) · RvComptoir — the player that replaces
 * the chat when the session's `mode` is `comptoir`. `/revue` and the journey's
 * Papier mount it in place of `RvEncounter`, with the same props.
 *
 * Five short screens, one at a time — «Lire», «Les avis», «L'intox» (only when
 * the band has one: the dots then show four), «Ton avis», «La page» — under a
 * head with the × and the step dots, each with ONE main button in a sticky foot
 * (at most two controls there). The server owns the state: every act goes to
 * `POST …/comptoir` and the returned view is rendered as is, so a resume lands on
 * the right screen with the learner's earlier acts shown. The client only keeps
 * a finished screen on screen until its main button is pressed (the vote moves
 * the server on to the takes; «Lire» stays until «Au comptoir →»).
 *
 * Never stuck (§6): an act Romy refuses (`error_fr`) is said by her on the same
 * screen; an act out of order (409) re-reads the session and shows its step; a
 * failure is one quiet line and the screen stays as it was. «Voir la page» calls
 * the close; «La page» is what it prints.
 *
 * Words: every French word opens the word sheet (the Papier's known meanings in
 * their sentence, `knownGloss(word, glosses, sentence)`), «Traduire» on every
 * bubble, ▶ in the speaker's voice.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Notice } from '@/components/atelier-v2/ui';
import { useLineVoice } from '@/components/atelier-v2/journey/useLineVoice';
import { FeuilletonReaderStyles } from '@/components/feuilleton/reader/reader-styles';
import { WordHelpSheet, type WordHelpRequest } from '@/components/feuilleton/reader/WordHelpSheet';
import { RevueError, type RevueClient } from '@/lib/revue-api';
import type { RvComptoirBody, RvComptoirStep, RvLanguage, RvSessionView } from '@/lib/revue-types';

import { revueCopy } from '../revue-copy';
import { knownGloss, sessionGlosses } from '../revue-model';
import type { RvWordEvent } from '../RvThread';
import { comptoirCopy } from './comptoir-copy';
import { clampStep, nextStep, openingStep, stepOrder } from './comptoir-model';
import { RvComptoirHead, RomyRefusal, type ComptoirStepProps } from './RvComptoirParts';
import { RvComptoirIntox } from './RvComptoirIntox';
import { RvComptoirOpinion } from './RvComptoirOpinion';
import { RvComptoirPage } from './RvComptoirPage';
import { RvComptoirRead } from './RvComptoirRead';
import { RvComptoirTakes } from './RvComptoirTakes';

export type RvComptoirProps = {
  client: RevueClient;
  /** The session as the server sent it (start or resume); `mode` is `comptoir`. */
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

/**
 * The element that scrolls the page: the nearest ancestor that scrolls, else the
 * document. The body's own `overflow-x: hidden` computes its `overflow-y` to `auto`
 * but, while `html` is `visible`, it is handed to the viewport (CSS overflow
 * propagation), so the body never scrolls itself: skipped then. In the native
 * shell (`overflow-x: clip`) the document scrolls too.
 */
function scrollerOf(node: HTMLElement | null): HTMLElement | null {
  if (typeof window === 'undefined' || !node) return null;
  const root = document.documentElement;
  const rootStyle = window.getComputedStyle(root);
  const propagated = rootStyle.overflowX === 'visible' && rootStyle.overflowY === 'visible';
  for (let el: HTMLElement | null = node.parentElement; el && el !== root; el = el.parentElement) {
    if (el === document.body && propagated) continue;
    const style = window.getComputedStyle(el);
    if (/(auto|scroll)/.test(style.overflowY) && el.scrollHeight > el.clientHeight) return el;
  }
  return (document.scrollingElement as HTMLElement | null) ?? root;
}

/**
 * Brings `node` into the band between the sticky head and the sticky foot: its top
 * under the head (`start`), or just enough to show it whole above the foot (`nearest`).
 */
function bringIntoView(node: HTMLElement, head: HTMLElement | null, foot: HTMLElement | null, block: 'start' | 'nearest') {
  const scroller = scrollerOf(node);
  if (!scroller) return;
  const rect = node.getBoundingClientRect();
  const top = (head?.getBoundingClientRect().bottom ?? 0) + 8;
  const bottom = (foot?.getBoundingClientRect().top ?? window.innerHeight) - 12;
  let delta = 0;
  if (block === 'start' || rect.top < top) delta = rect.top - top;
  else if (rect.bottom > bottom) delta = Math.min(rect.bottom - bottom, rect.top - top);
  if (Math.abs(delta) < 2) return;
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  scroller.scrollBy({ top: delta, behavior: reduce ? 'auto' : 'smooth' });
}

/** What changed on screen after an act: the newest part is brought into view. */
function progressKey(session: RvSessionView): string {
  const view = session.comptoir;
  if (!view) return '';
  return [
    view.cast.map((member) => member.reaction ?? '-').join(''),
    view.intox ? `${view.intox.tries.length}${view.intox.fix ? 'f' : ''}` : '',
    view.opinion ? 'o' : '',
    view.opinion?.comeback ? 'c' : '',
  ].join('|');
}

export function RvComptoir({ client, session: initial, language, onExit, onReleve, readOnly = false }: RvComptoirProps) {
  const [session, setSession] = useState<RvSessionView>(initial);
  const [ended] = useState(initial.status !== 'active');
  const closed = session.status !== 'active' || Boolean(session.closing);
  const view = session.comptoir;
  const [shown, setShown] = useState<RvComptoirStep>(() => (view ? openingStep(view, closed) : 'read'));
  const [pending, setPending] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [word, setWord] = useState<WordHelpRequest | null>(null);
  const footRef = useRef<HTMLDivElement | null>(null);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const headRef = useRef<HTMLDivElement | null>(null);
  const voice = useLineVoice();

  // A different session from the page replaces this one; the same one never rewinds it.
  const shownId = useRef(initial.id);
  useEffect(() => {
    if (shownId.current === initial.id) return;
    shownId.current = initial.id;
    setSession(initial);
    if (initial.comptoir) setShown(openingStep(initial.comptoir, initial.status !== 'active' || Boolean(initial.closing)));
  }, [initial]);

  const chrome: RvLanguage = language ?? session.plan.uiLanguage;
  const copy = revueCopy(chrome);
  const ccopy = comptoirCopy(chrome);
  const glossLanguage = session.plan.glossLanguage;
  const glosses = useMemo(() => sessionGlosses(session), [session]);

  // Never ahead of the server (a re-read session after a 409, a close elsewhere).
  const serverStep = view?.step ?? 'read';
  useEffect(() => {
    if (!view) return;
    setShown((current) => (closed ? 'page' : clampStep(view, current, closed)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverStep, closed]);

  // A new screen starts at its top; on the same screen, the newest part comes into view.
  const firstStep = useRef(true);
  useEffect(() => {
    if (firstStep.current) {
      firstStep.current = false;
      return;
    }
    const scroller = scrollerOf(bodyRef.current);
    if (scroller && typeof scroller.scrollTo === 'function') scroller.scrollTo({ top: 0 });
  }, [shown]);
  const progress = progressKey(session);
  const lastProgress = useRef(progress);
  useEffect(() => {
    if (lastProgress.current === progress) return;
    lastProgress.current = progress;
    const body = bodyRef.current;
    if (!body || typeof body.querySelectorAll !== 'function') return;
    const anchors = body.querySelectorAll<HTMLElement>('[data-ct-anchor]');
    const node = anchors[anchors.length - 1];
    if (!node || typeof node.getBoundingClientRect !== 'function') return;
    bringIntoView(node, headRef.current, footRef.current, node.dataset.ctAnchor === 'start' ? 'start' : 'nearest');
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
    async (body: RvComptoirBody, key: string): Promise<boolean> => {
      if (readOnly || pending) return false;
      setPending(key);
      setFailed(false);
      setRefusal(null);
      try {
        const result = await client.comptoir(session.id, body);
        setSession(result.session);
        setRefusal(result.errorFr);
        return !result.errorFr;
      } catch (error) {
        if (error instanceof RevueError && (error.code === 'revue_comptoir_out_of_order' || error.code === 'revue_session_closed' || error.code === 'revue_not_comptoir')) {
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
      if (error instanceof RevueError && error.code === 'revue_comptoir_out_of_order') await reread();
      else setFailed(true);
    } finally {
      setPending(null);
    }
  }, [client, pending, reread, session.id]);

  const onContinue = useCallback(() => {
    if (!view || pending) return;
    if (shown === 'opinion') {
      void closePapier();
      return;
    }
    const next = nextStep(view, shown);
    if (!next) return;
    // The server's step is the limit: «La page» is reached only through the close.
    if (next === 'page' || stepOrder(next) > stepOrder(openingStep(view, closed))) return;
    setRefusal(null);
    setFailed(false);
    setShown(next);
  }, [closePapier, closed, pending, shown, view]);

  if (!view) return null;

  const notice = (
    <>
      {refusal && <RomyRefusal textFr={refusal} props={{ copy, ccopy, glossLanguage, glosses, voice, wordFor }} />}
      {failed && (
        <Notice tone="quiet" shape="action">
          <p>{ccopy.act_failed}</p>
        </Notice>
      )}
    </>
  );

  const props: ComptoirStepProps = {
    session,
    view,
    copy,
    ccopy,
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
    step = <RvComptoirPage props={props} ended={ended || readOnly} onExit={onExit} onReleve={onReleve} />;
  } else if (shown === 'takes') {
    step = <RvComptoirTakes {...props} />;
  } else if (shown === 'intox' && view.intox) {
    step = <RvComptoirIntox {...props} />;
  } else if (shown === 'opinion' || shown === 'page') {
    step = <RvComptoirOpinion {...props} />;
  } else {
    step = <RvComptoirRead {...props} />;
  }

  return (
    <div className="rv-encounter ct-player" data-step={shown} data-band={view.band} data-ended={ended ? '' : undefined} data-readonly={readOnly ? '' : undefined} ref={bodyRef}>
      <div className="rv-top" ref={headRef}>
        <RvComptoirHead steps={view.steps} shown={shown} closed={closed} back={ended || readOnly} onExit={onExit} copy={copy} ccopy={ccopy} />
      </div>
      {step}
      <FeuilletonReaderStyles />
      <WordHelpSheet request={word} onClose={() => setWord(null)} language={chrome} note={null} quoteLabel={copy.word_in_text} />
    </div>
  );
}

export default RvComptoir;

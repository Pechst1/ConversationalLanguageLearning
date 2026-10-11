/**
 * WP-119 · RvEncounter — one Revue, from `arrive` to `close` (design §3.2–3.8).
 *
 * The one implementation of the encounter: `/revue` mounts it, and the journey
 * player will mount the same component for `DayShape.REVUE` (phase 3). It owns
 * the session head, the stage (full 4:3 until the learner first speaks, then the
 * pinned band), the thread, the foot (the press / quick replies / composer) and
 * the make and close steps.
 *
 * Resume is a replay: the session the server sends (`GET /revue/sessions/{id}`)
 * is rendered as is — the same thread, the same ids — and when it started on an
 * earlier day an «Hier · tu reprends ici» marker sits where today begins.
 *
 * One red press per screen: the arrive line, «C'est parti», «Continuer», or «On
 * l'envoie à la rédaction»; the close's terminal press is ink («Classer le
 * Papier»), since nothing is left to do.
 *
 * Phase 2 («Les invités», WIRE §6): a guest who speaks stands beside Romy on the
 * stage (sliding in on their entrance) and talks in their own bubbles; Romy's
 * `make_intro` line opens the make, her `make_done` line follows each result;
 * B1+ may write the headline or tell a thirty-second report; the rubric's
 * register note is worded under the learner's line and its word outcomes mark
 * the kept words at the close; the close stamps the minted vignette (WP-120).
 *
 * `readOnly` (La Carte's «Relire», `/revue?session=…&readonly=1`): the thread
 * replayed, no composer, no press, nothing sent.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Action, Notice } from '@/components/atelier-v2/ui';
import { WordHelpSheet, type WordHelpRequest } from '@/components/feuilleton/reader/WordHelpSheet';
import { RevueError, newClientTurnId, type RevueClient } from '@/lib/revue-api';
import type {
  RvEvidence,
  RvHeadlineOption,
  RvLanguage,
  RvLineItem,
  RvMakeKind,
  RvMakeOffer,
  RvMade,
  RvPickResult,
  RvQuestionDraftData,
  RvReportResult,
  RvSessionView,
  RvWriteResult,
} from '@/lib/revue-types';

import { ROMY_CLIENT_LINES, fill, revueCopy } from './revue-copy';
import {
  appendItems,
  applyTurn,
  castWithGuests,
  enteringGuest,
  lastSpeaker,
  localDay,
  mergeWordOutcomes,
  openQuestion,
  shownRoom,
  sourceDate,
  type WordOutcomes,
} from './revue-model';
import { RvCloseCarteLink, RvCloseVignette, RvDispatch, RvKept } from './RvClose';
import { RvComposer } from './RvComposer';
import { RvHeadlineChoice, RvHeadlineWrite, RvMakePicker, RvQuestionDraft, RvShortReport } from './RvMake';
import { RvSessionHead } from './RvSessionHead';
import { RvStage, stageCast, stagePlateUrl } from './RvStage';
import { RvLine, RvMadeCard, RvQuickReplies, RvThread, type RvWordEvent } from './RvThread';

type MakeStep =
  | { step: 'none' }
  | { step: 'loading' }
  | { step: 'choose'; offer: RvMakeOffer; value: RvMakeKind }
  | { step: 'headline'; options: RvHeadlineOption[]; picked: string | null; result: RvPickResult | null; ask: boolean }
  | { step: 'write'; seed: string }
  | { step: 'draft'; draft: RvQuestionDraftData }
  | { step: 'headline_write'; maxWords: number; result: RvWriteResult | null; ask: boolean }
  | { step: 'report'; seconds: number; result: RvReportResult | null; ask: boolean };

export type RvEncounterProps = {
  client: RevueClient;
  /** The session as the server sent it (start or resume). */
  session: RvSessionView;
  /** Chrome language; defaults to the plan's `ui_language`. */
  language?: RvLanguage;
  onExit: () => void;
  onReleve?: () => void;
  /** La Carte's «Relire»: replay the thread, hide the composer and every press. */
  readOnly?: boolean;
  now?: Date;
};

/** A learner line that asks Romy to phrase the open question together. */
const FORMULATE = /formule la question|on l['’]écrit|on l['’]ecrit/i;

export function RvEncounter({ client, session: initial, language, onExit, onReleve, readOnly = false, now }: RvEncounterProps) {
  const [session, setSession] = useState<RvSessionView>(initial);
  // Phase 2: what the rubric said (never replayed by the server: kept for this visit).
  const [outcomes, setOutcomes] = useState<WordOutcomes>({});
  const [registerNotes, setRegisterNotes] = useState<Record<string, 'vous_to_tu' | 'tu_to_vous'>>({});
  const [entering, setEntering] = useState<string | null>(null);
  // Romy's `make_done` line, shown after the make step's result.
  const [doneLine, setDoneLine] = useState<RvLineItem | null>(null);
  const [make, setMake] = useState<MakeStep>({ step: 'none' });
  const [pendingMine, setPendingMine] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [modelDown, setModelDown] = useState(false);
  const [composerOpen, setComposerOpen] = useState(false);
  const [steerDismissed, setSteerDismissed] = useState(false);
  const [word, setWord] = useState<WordHelpRequest | null>(null);
  const [reread, setReread] = useState(false);
  // `ended`: opened after the close this week — read-only. A close made here shows the close page instead.
  const [ended] = useState(initial.status !== 'active');
  const showThread = !ended || reread || readOnly;
  const endRef = useRef<HTMLDivElement | null>(null);
  const footRef = useRef<HTMLDivElement | null>(null);

  // A different session from the page replaces this one; the same one never rewinds it.
  const shownId = useRef(initial.id);
  useEffect(() => {
    if (shownId.current === initial.id) return;
    shownId.current = initial.id;
    setSession(initial);
  }, [initial]);

  const chrome: RvLanguage = language ?? session.plan.uiLanguage;
  const copy = revueCopy(chrome);
  const glossLanguage = session.plan.glossLanguage;
  const support = session.plan.support;
  const closing = session.closing;
  const hasSpoken = session.thread.some((item) => item.kind === 'mine');
  const today = localDay((now ?? new Date()).toISOString());
  const resumeLabel = useMemo(() => {
    const first = session.thread[0];
    if (!first) return '';
    const yesterday = localDay(new Date((now ?? new Date()).getTime() - 86400000).toISOString());
    const when = localDay(first.at) === yesterday ? copy.day_yesterday : copy.day_earlier;
    return fill(copy.shift_resume, { when });
  }, [copy, now, session.thread]);

  // Keep the newest row in view.
  const rows = session.thread.length + (pendingMine ? 1 : 0) + (busy ? 1 : 0);
  useEffect(() => {
    // Not on arrival: the stage and Romy's purpose are read from the top until the
    // learner has said something (WP-143 C-8: a first-mount flag was not enough —
    // a second effect pass, as React's Strict Mode runs, scrolled Romy's face away).
    if (!hasSpoken && !pendingMine && !closing && make.step === 'none') return;
    const node = endRef.current;
    if (!node || typeof node.scrollIntoView !== 'function') return;
    const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    // The sticky foot covers the end of the thread: stop above it.
    node.style.scrollMarginBottom = `${(footRef.current?.offsetHeight ?? 0) + 12}px`;
    node.scrollIntoView({ block: 'end', behavior: reduce ? 'auto' : 'smooth' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, make.step, closing]);

  const onWord = useCallback((event: RvWordEvent) => {
    const term = event.word.toLowerCase().replace(/^(l|d|qu|j|n|s|c)['’]/, '');
    setWord({ surface: event.word, term, sentence: event.sentence, speakerId: 'romy_tremblay' });
  }, []);

  const noteEvidence = useCallback((evidence: RvEvidence | null | undefined, mineId: string | null) => {
    if (!evidence) return;
    setOutcomes((current) => mergeWordOutcomes(current, evidence));
    const note = evidence.registerNote;
    if (mineId && (note === 'vous_to_tu' || note === 'tu_to_vous')) setRegisterNotes((current) => ({ ...current, [mineId]: note }));
  }, []);

  // --- make ------------------------------------------------------------------

  const openMake = useCallback(
    async (prefer?: RvMakeKind) => {
      setMake({ step: 'loading' });
      try {
        const offer = await client.makeOffer(session.id);
        // Romy's intro is a thread item like any line: it replays on resume.
        if (offer.intro) {
          const intro = offer.intro;
          setSession((current) => appendItems(current, [intro]));
        }
        const kinds = offer.options.map((option) => option.kind);
        if (!kinds.length) {
          setMake({ step: 'none' });
          return;
        }
        const value = prefer && kinds.includes(prefer) ? prefer : kinds.includes(offer.recommended) ? offer.recommended : kinds[0];
        setMake({ step: 'choose', offer, value });
      } catch {
        setMake({ step: 'none' });
      }
    },
    [client, session.id],
  );

  const startMake = () => {
    if (make.step !== 'choose') return;
    const option = make.offer.options.find((row) => row.kind === make.value);
    if (!option) return;
    // Romy's own ask, unless her intro already asked for exactly this.
    const ask = !make.offer.intro || make.offer.recommended !== option.kind;
    setDoneLine(null);
    if (option.kind === 'headline_choice') {
      setMake({ step: 'headline', options: option.options, picked: null, result: null, ask: true });
    } else if (option.kind === 'headline_write') {
      setMake({ step: 'headline_write', maxWords: option.maxWords, result: null, ask });
    } else if (option.kind === 'short_report') {
      setMake({ step: 'report', seconds: option.seconds, result: null, ask });
    } else {
      setMake({ step: 'write', seed: option.seedFr ?? openQuestion(session.thread) ?? '' });
    }
  };

  // At 80 % Romy steers to the make herself (design §3.5 #choose).
  useEffect(() => {
    if (readOnly || ended || closing || busy || steerDismissed || make.step !== 'none') return;
    if (session.steerToMake && !session.artifact) void openMake();
  }, [busy, closing, ended, make.step, openMake, readOnly, session.artifact, session.steerToMake, steerDismissed]);

  /** A filed artefact: the make step shows it; the server's `made` item arrives with the close's replay. */
  const fileLocally = (made: RvMade) => {
    setSession((current) => ({ ...current, artifact: made }));
  };

  const doClose = useCallback(async () => {
    setBusy(true);
    try {
      const result = await client.close(session.id);
      setSession({ ...result.session, closing: result.closing });
      setMake({ step: 'none' });
    } catch {
      setModelDown(true);
    } finally {
      setBusy(false);
    }
  }, [client, session.id]);

  const pick = async (optionId: string) => {
    if (make.step !== 'headline' || make.result) return;
    setMake({ ...make, picked: optionId });
    setBusy(true);
    try {
      const result = await client.make(session.id, { kind: 'headline_choice', action: 'pick', optionId });
      if (result.kind === 'headline_choice') {
        setMake({ step: 'headline', options: make.options, picked: optionId, result, ask: make.ask });
        setDoneLine(result.line);
      }
    } catch (error) {
      if (error instanceof RevueError && error.code === 'revue_session_closed') await reload();
      else setModelDown(true);
    } finally {
      setBusy(false);
    }
  };

  const propose = async (text: string) => {
    setBusy(true);
    setPendingMine(text);
    try {
      const result = await client.make(session.id, { kind: 'reader_question', action: 'propose', text });
      if ('draft' in result) setMake({ step: 'draft', draft: result.draft });
    } catch {
      setModelDown(true);
    } finally {
      setPendingMine(null);
      setBusy(false);
    }
  };

  const writeHeadline = async (textFr: string) => {
    if (make.step !== 'headline_write' || busy) return;
    const step = make;
    setBusy(true);
    try {
      const result = await client.make(session.id, { kind: 'headline_write', action: 'write', textFr });
      if (result.kind === 'headline_write') {
        setMake({ ...step, result });
        setDoneLine(result.line);
        noteEvidence(result.evidence, null);
        if (result.accepted && result.made) fileLocally(result.made);
      }
    } catch (error) {
      if (error instanceof RevueError && error.code === 'revue_session_closed') await reload();
      else setModelDown(true);
    } finally {
      setBusy(false);
    }
  };

  const sendReport = async (transcript: string, mode: 'voice' | 'text') => {
    if (make.step !== 'report' || busy) return;
    const step = make;
    setBusy(true);
    try {
      const result = await client.make(session.id, { kind: 'short_report', action: 'report', transcript, mode });
      if (result.kind === 'short_report') {
        setMake({ ...step, result });
        setDoneLine(result.line);
        noteEvidence(result.evidence, null);
        fileLocally(result.made);
      }
    } catch (error) {
      if (error instanceof RevueError && error.code === 'revue_session_closed') await reload();
      else setModelDown(true);
    } finally {
      setBusy(false);
    }
  };

  const sendQuestion = async (textFr: string) => {
    setBusy(true);
    try {
      await client.make(session.id, { kind: 'reader_question', action: 'send', textFr });
      const result = await client.close(session.id);
      setSession({ ...result.session, closing: result.closing });
      setMake({ step: 'none' });
    } catch {
      setModelDown(true);
    } finally {
      setBusy(false);
    }
  };

  // --- turns -----------------------------------------------------------------

  const reload = useCallback(async () => {
    try {
      setSession(await client.session(session.id));
    } catch {
      /* keep what is on screen */
    }
  }, [client, session.id]);

  const sendTurn = async (text: string, mode: 'text' | 'voice' = 'text') => {
    if (busy || !text.trim()) return;
    setBusy(true);
    setPendingMine(text);
    setComposerOpen(false);
    try {
      const result = await client.turn(session.id, { text, mode, clientTurnId: newClientTurnId() });
      setSession((current) => applyTurn(current, result));
      setModelDown(false);
      const mine = result.items.find((item) => item.kind === 'mine');
      noteEvidence(result.evidence, mine ? mine.id : null);
      const guest = enteringGuest(result.items);
      if (guest) setEntering(guest);
      if (FORMULATE.test(text) && !result.steerToMake) void openMake('reader_question');
    } catch (error) {
      if (error instanceof RevueError && error.code === 'revue_session_closed') {
        await reload();
      } else {
        // The model (or the network) is down: keep what exists and go to what needs no generation.
        setModelDown(true);
        void openMake('headline_choice');
      }
    } finally {
      setPendingMine(null);
      setBusy(false);
    }
  };

  // --- the screen ------------------------------------------------------------

  // Romy's pick first (design §3.5 #choose).
  const makeOptions = make.step === 'choose'
    ? make.offer.options
      .slice()
      .sort((a, b) => Number(b.kind === make.offer.recommended) - Number(a.kind === make.offer.recommended))
      .map((option) => {
        const n = option.kind === 'headline_write' ? option.maxWords : option.kind === 'short_report' ? option.seconds : '';
        return {
          id: option.kind,
          titleFr: fill(copy.make_options[option.kind].title, { n }),
          detail: fill(copy.make_options[option.kind].detail, { n }),
        };
      })
    : [];

  const after: React.ReactNode[] = [];
  const romyRow = (key: string, text: string) => (
    <li key={key} className="av2-thread__line" data-kind="line" data-role="client" data-speaker="romy">
      <RvLine textFr={text} past={false} support={support} glosses={[]} glossLanguage={glossLanguage} copy={copy} />
    </li>
  );
  if (modelDown && !closing && !readOnly) {
    after.push(
      <li key="model-down" className="av2-thread__line" data-kind="notice">
        <Notice tone="quiet" shape="action">
          <p>{copy.model_down}</p>
        </Notice>
      </li>,
      romyRow('model-down-line', ROMY_CLIENT_LINES.model_down),
    );
  }
  if (make.step === 'choose') {
    after.push(
      <li key="make-choose" className="av2-thread__line" data-kind="make">
        <RvMakePicker options={makeOptions} recommended={make.offer.recommended} value={make.value} onChange={(value) => setMake({ ...make, value })} copy={copy} />
      </li>,
    );
  }
  if (make.step === 'headline') {
    if (make.ask) after.push(romyRow('headline-ask', ROMY_CLIENT_LINES.headline_ask));
    after.push(
      <li key="make-headline" className="av2-thread__line" data-kind="make">
        <RvHeadlineChoice options={make.options} result={make.result} picked={make.picked} pending={busy} onPick={(id) => void pick(id)} copy={copy} now={now} />
      </li>,
    );
  }
  if (make.step === 'headline_write') {
    if (make.ask) after.push(romyRow('headline-write-ask', ROMY_CLIENT_LINES.headline_write_ask));
    after.push(
      <li key="make-headline-write" className="av2-thread__line" data-kind="make" data-make="headline_write">
        <RvHeadlineWrite maxWords={make.maxWords} result={make.result} pending={busy} onSend={(text) => void writeHeadline(text)} copy={copy} />
      </li>,
    );
  }
  if (make.step === 'report') {
    if (make.ask) after.push(romyRow('report-ask', ROMY_CLIENT_LINES.report_ask));
    after.push(
      <li key="make-report" className="av2-thread__line" data-kind="make" data-make="short_report">
        {make.result ? <RvMadeCard made={make.result.made} copy={copy} /> : <RvShortReport seconds={make.seconds} pending={busy} onSend={(text, mode) => void sendReport(text, mode)} copy={copy} />}
      </li>,
    );
  }
  if (doneLine && !closing && (make.step === 'headline' || make.step === 'headline_write' || make.step === 'report')) {
    after.push(
      <li key={`done-${doneLine.id}`} className="av2-thread__line" data-kind="line" data-role="make_done" data-speaker="romy">
        <RvLine textFr={doneLine.textFr} past={false} translation={doneLine.translation} support={support} glosses={doneLine.glosses} glossLanguage={glossLanguage} copy={copy} />
      </li>,
    );
  }
  if (make.step === 'write') after.push(romyRow('write-ask', ROMY_CLIENT_LINES.write_question));
  if (make.step === 'draft') {
    after.push(
      <li key="draft-mine" className="av2-thread__line" data-kind="mine" data-speaker="learner">
        <p className="rv-thread__mine" lang="fr">
          <span className="av2-sr">{copy.you} : </span>
          {make.draft.learnerFr}
        </p>
      </li>,
      romyRow('draft-propose', ROMY_CLIENT_LINES.propose),
      <li key="make-draft" className="av2-thread__line" data-kind="make">
        <RvQuestionDraft
          learnerFr={make.draft.learnerFr}
          proposalFr={make.draft.proposalFr}
          contribution={make.draft.contribution}
          whyNative={make.draft.whyNative}
          glossLanguage={glossLanguage}
          pending={busy}
          onSend={(textFr) => void sendQuestion(textFr)}
          copy={copy}
        />
      </li>,
    );
  }
  if (closing && !ended) {
    after.push(
      romyRow('close-line', closing.romyLineFr),
      <li key="dispatch" className="av2-thread__line" data-kind="dispatch">
        <RvDispatch {...closing.dispatch} copy={copy} />
      </li>,
      <li key="kept" className="av2-thread__line" data-kind="kept">
        <RvKept words={closing.kept.words} claims={closing.kept.claims} glossLanguage={glossLanguage} copy={copy} now={now} outcomes={outcomes} />
      </li>,
    );
    // WP-120: the vignette is stamped in before «Classer»; no vignette, no stamp.
    if (closing.vignette) {
      after.push(
        <li key="vignette" className="av2-thread__line" data-kind="vignette">
          <RvCloseVignette vignette={closing.vignette} week={session.week.label} copy={copy} />
        </li>,
      );
    }
    after.push(
      <li key="colophon" className="av2-thread__line" data-kind="colophon">
        <p className="rv-colophon" lang="fr">
          {closing.colophonFr}
        </p>
      </li>,
    );
  }

  // The foot: one red press at most.
  let foot: React.ReactNode = null;
  if (ended || readOnly) {
    foot = null;
  } else if (closing) {
    foot = (
      <>
        <Action tone="done" onClick={onExit}>
          {copy.file_revue}
        </Action>
        <RvCloseCarteLink sessionId={session.id} language={chrome} />
        {onReleve && (
          <Action tone="quiet" onClick={onReleve}>
            {copy.see_releve}
          </Action>
        )}
      </>
    );
  } else if (make.step === 'choose') {
    foot = (
      <>
        <Action tone="primary" onClick={startMake}>
          {copy.make_go}
        </Action>
        {session.room.phase !== 'boucle' && !modelDown && (
          <Action
            tone="quiet"
            onClick={() => {
              setSteerDismissed(true);
              setMake({ step: 'none' });
              setComposerOpen(true);
            }}
          >
            {copy.one_more_question}
          </Action>
        )}
      </>
    );
  } else if (make.step === 'headline' || make.step === 'headline_write' || make.step === 'report') {
    const filed = make.step === 'headline' ? Boolean(make.result) : make.step === 'headline_write' ? Boolean(make.result?.accepted) : Boolean(make.result);
    foot = filed ? (
      <Action tone="primary" pending={busy} pendingLabel={copy.continue} onClick={() => void doClose()}>
        {copy.continue}
      </Action>
    ) : null;
  } else if (make.step === 'write') {
    foot = (
      <RvComposer
        key="write"
        initial={make.seed}
        label={copy.question_write_label}
        placeholder={copy.question_write_placeholder}
        disabled={busy}
        onSend={(text) => void propose(text)}
        copy={copy}
        autoFocus
      />
    );
  } else if (make.step === 'draft' || make.step === 'loading') {
    foot = null;
  } else if (session.artifact) {
    foot = (
      <Action tone="primary" pending={busy} pendingLabel={copy.see_paper} onClick={() => void doClose()}>
        {copy.see_paper}
      </Action>
    );
  } else if (!hasSpoken && !composerOpen) {
    const agree = session.quickReplies[0];
    foot = (
      <>
        {agree && (
          <Action tone="primary" lang="fr" pending={busy} pendingLabel={agree.label} onClick={() => void sendTurn(agree.sendFr)}>
            {agree.label}
          </Action>
        )}
        <Action tone="quiet" disabled={busy} onClick={() => setComposerOpen(true)}>
          {copy.agree_other}
        </Action>
      </>
    );
  } else {
    foot = (
      <>
        <RvQuickReplies replies={session.quickReplies} onSend={(fr) => void sendTurn(fr)} disabled={busy} />
        <RvComposer key="turn" disabled={busy} onSend={(text, mode) => void sendTurn(text, mode)} copy={copy} autoFocus={composerOpen} />
      </>
    );
  }

  // A guest stands beside Romy from their entrance on; whoever spoke last is in front.
  const cast = castWithGuests(session.stage.cast, session.thread);
  const stage = (
    <RvStage
      plateUrl={stagePlateUrl(session.stage, session.thread, make.step !== 'none' || Boolean(session.artifact) || session.beat === 'make')}
      size={hasSpoken || ended ? 'band' : 'full'}
      cast={stageCast(cast, lastSpeaker(session.thread))}
      you={{ outfit: session.stage.dress }}
      entering={entering}
      still={busy}
    />
  );
  const room = shownRoom(session.room, session.thread);

  return (
    <div className="rv-encounter" data-beat={session.beat} data-ended={ended ? '' : undefined} data-readonly={readOnly ? '' : undefined}>
      <div className="rv-top">
        <RvSessionHead beat={ended || closing ? 'close' : make.step !== 'none' || session.artifact ? 'make' : session.beat} room={room} onExit={onExit} ended={ended} back={ended || readOnly} copy={copy} />
        {(hasSpoken || ended) && stage}
      </div>
      {!hasSpoken && !ended && stage}
      <div className="rv-body">
        {session.dossier.evergreen && !ended && (
          <p className="rv-kicker">{copy.evergreen_label}</p>
        )}
        {ended && closing && (
          <>
            <p className="rv-ended">{fill(copy.filed_on, { date: sourceDate(localDay(session.closedAt ?? ''), now) })}</p>
            <RvDispatch {...closing.dispatch} readOnly copy={copy} />
            {closing.vignette && <RvCloseVignette vignette={closing.vignette} week={session.week.label} stamping={false} copy={copy} />}
            {!readOnly && (
              <Action tone="quiet" aria-expanded={reread} onClick={() => setReread((value) => !value)}>
                {reread ? copy.hide_thread : copy.reread}
              </Action>
            )}
          </>
        )}
        {showThread && (
          <RvThread
            items={session.thread}
            support={support}
            copy={copy}
            vocabulary={session.plan.vocabulary}
            band={session.plan.band}
            glossLanguage={glossLanguage}
            onWord={support.glosses === 'none' ? undefined : onWord}
            typing={busy && Boolean(pendingMine) && make.step !== 'write'}
            pendingMine={pendingMine}
            resumeToday={today}
            resumeLabel={resumeLabel}
            after={readOnly ? null : after}
            registerNotes={registerNotes}
            now={now}
          />
        )}
        {ended && closing && (
          <p className="rv-colophon" lang="fr">
            {closing.colophonFr}
          </p>
        )}
        <div ref={endRef} aria-hidden="true" />
      </div>
      {foot && (
        <div className="rv-foot" ref={footRef}>
          {foot}
        </div>
      )}
      <WordHelpSheet request={word} onClose={() => setWord(null)} language={chrome} />
    </div>
  );
}

export default RvEncounter;

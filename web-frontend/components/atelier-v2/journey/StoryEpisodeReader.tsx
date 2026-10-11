/**
 * The story-engine episode in the immersive reader (WP-14E, frontend side).
 *
 * Contract kept (ENGINE-FRONTEND-CONTRACT.md):
 *   * reading never mutates canon — Next/Previous and word help send nothing
 *     but the reading position, and that PUT does not touch the daily revision;
 *   * the position is bound to stable panel ids and restored from the server,
 *     so another device opens the same place;
 *   * continuing goes through the daily journey controller's own action, never
 *     through a request manufactured from the panel index;
 *   * a completed or abandoned scene is replay-only;
 *   * reused setting art is labelled, not passed off as a new illustration.
 */

import React, {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from 'react';

import { FeuilletonReader, FeuilletonReaderStyles } from '@/components/feuilleton/reader';
import { MarginNotes } from '@/components/feuilleton/archive/ArchiveMarks';
import { ArchiveStyles } from '@/components/feuilleton/archive/ArchiveStyles';
import { placeMarginNotes, type ArchiveMarginNote } from '@/components/feuilleton/archive/archive-model';

import { useSpecialKicker } from './special-edition';
import {
  Action,
  Byline,
  ChoiceList,
  Chip,
  Notice,
  ShapeToken,
  StateBlock,
  StepProgress,
  Surface,
} from '@/components/atelier-v2/ui';
import { frenchSpacing } from '@/lib/french-typography';
import { useArtSet } from '@/lib/art-set';
import { useReaderLayoutState, type ReaderLayout } from '@/lib/reader-layout';
import { sceneFitsVertical } from '@/components/atelier-v2/journey/vertical-page/scene-fit';
import { saveStoryReadingPosition } from '@/services/daily-journey';
import type { ReaderResolutionStage } from '@/components/feuilleton/reader/panel-model';
import type { ControlLanguage, StoryEpisode } from '@/types/daily-journey';

import type { JourneyCopy } from './journey-copy';
import {
  RADIO_INITIAL,
  RADIO_STAGES,
  RADIO_TEXT_INITIAL,
  buildEpisodeGuesses,
  buildStoryStages,
  episodeListenLines,
  episodeRetainPhrase,
  panelReaderVariant,
  radioLineShown,
  radioReduce,
  radioStageOrdinal,
  radioTask,
  radioTextControls,
  radioTextReduce,
  storyEpisodeLabel,
  storyRayonsTitle,
  storyStartIndex,
  storyStagesWithFinale,
  storyUsesSettingArt,
  verifyEpisodeGuess,
  type EpisodeGuessId,
  type EpisodeVerification,
  type RadioEvent,
  type RadioStage,
  type RadioState,
  type RadioText,
  type RadioTextEvent,
} from './story-episode-model';
import type { UseEpisodeAudio } from './useEpisodeAudio';
import type { LineVoice } from './useLineVoice';

export type StoryEpisodeReaderProps = {
  episode: StoryEpisode;
  /**
   * `continue` hands the end of the panels to the daily journey; `replay`
   * reads only. `reread` (WP-93, the READ step) reads a page that is already
   * filed — yesterday's, or «Coulisses» — and still closes with the day's
   * «Continuer»; it never saves a reading position.
   */
  mode: 'continue' | 'replay' | 'reread';
  /** The ✕. Absent: the reader draws none (the caller owns the way out). */
  onExit?: (() => void) | null;
  onContinue?: () => void;
  continuing?: boolean;
  continueLabel?: string;
  /** Where a replay can go next, if anywhere. */
  nextHref?: string | null;
  nextLabel?: string;
  /** WP-44. A quiet link under the nav — «Écouter d'abord» in the journey. */
  footLink?: React.ReactNode;
  /** WP-82: the reader's chrome language — the journey screen's. Absent keeps French. */
  language?: ControlLanguage | null;
  /** False for a page with no server episode (an authored scene): nowhere to save. */
  savePosition?: boolean;
  /**
   * WP-90/91 — the voice seam. Speaks a caption's line when its speaker's face
   * is tapped. The journey creates it (`useLineVoice` in StoryEpisodeStep and
   * ResolutionStepView); a server-backed `resolve` goes there. Absent: the
   * faces are plain portraits.
   */
  lineVoice?: LineVoice | null;
  /** «Écouter Margaux» for a face's button, in the learner's language. */
  listenLabel?: ((name: string) => string) | null;
  /**
   * WP-90 — the «case finale»: the day's ending drawn as the page's last panel
   * (it replaces the episode's own «À suivre» stage), and the reader opens on
   * it. The panels before it stay one swipe back.
   */
  finale?: ReaderResolutionStage | null;
  /** Under the finale: the register note, the chapter recap. */
  finaleExtra?: React.ReactNode;
  /** In the finale while the ending is being written: the speaker's face. */
  finaleWait?: React.ReactNode;
  /** The headline, when the caller knows better than the episode (the scenario's). */
  title?: string | null;
  /** WP-93: the kicker, when the caller knows better («Relecture · la page d'hier»). */
  eyebrow?: string | null;
  /**
   * WP-97 «Les suites»: the consequences this page pays back. Each is printed
   * in the margin of the panel where it happens (its `panel_id`, else the
   * first panel its character speaks in), else at the page's end.
   */
  marginNotes?: ArchiveMarginNote[] | null;
  /**
   * WP-144: force the page layout (the gallery, the tests). Absent: the device's
   * choice (`useReaderLayout`, `?readerLayout=vertical|list|default`), else the build default.
   */
  layout?: ReaderLayout | null;
};

const POSITION_DEBOUNCE_MS = 400;

export function StoryEpisodeReader({
  episode,
  mode,
  onExit,
  onContinue,
  continuing = false,
  continueLabel = 'Continuer',
  nextHref = null,
  nextLabel,
  footLink = null,
  language = null,
  savePosition = true,
  lineVoice = null,
  listenLabel = null,
  finale = null,
  finaleExtra = null,
  finaleWait = null,
  title = null,
  eyebrow = null,
  marginNotes = null,
  layout = null,
}: StoryEpisodeReaderProps) {
  // WP-144: the vertical page or the current one.
  const layoutChoice = useReaderLayoutState();
  const artSet = useArtSet();
  // WP-94: a «Numéro spécial» day names itself in the reader's kicker too.
  const specialKicker = useSpecialKicker();
  const reread = mode === 'reread';
  const keepsPosition = savePosition && !reread;
  const stages = useMemo(
    () => (finale ? storyStagesWithFinale(episode, finale) : buildStoryStages(episode)),
    [episode, finale],
  );
  // WP-144b: the vertical page only for a scene it can stage (drawn figures for
  // every panel's voices); otherwise the whole scene reads as the list, unless
  // this device or the URL asked for the vertical page by name.
  const fits = useMemo(() => sceneFitsVertical(stages, artSet), [stages, artSet]);
  const deviceLayout: ReaderLayout =
    layoutChoice.layout === 'vertical' && !layoutChoice.explicit && !fits ? 'list' : layoutChoice.layout;
  const panelCount = episode.panels?.length ?? 0;
  // The finale opens on itself: the ending is what the learner came back for.
  // A page re-read (WP-93) opens on its first panel, whatever was saved yesterday.
  const start = finale
    ? Math.max(0, stages.length - 1)
    : reread
      ? 0
      : storyStartIndex(episode, stages.length);
  const [index, setIndex] = useState(start);
  const [furthest, setFurthest] = useState(start);
  const timer = useRef<number | null>(null);

  // A different episode is a different place. The same episode re-read (its panel
  // art arriving) keeps the learner where they are, not the last saved position.
  const startRef = useRef(start);
  startRef.current = start;
  useEffect(() => {
    setIndex(startRef.current);
    setFurthest(startRef.current);
  }, [episode.id, finale?.key]);

  // WP-110: the finished page arrives while the ending is open (it has more
  // panels than the scene did). A learner still on the ending stays on it.
  const stageCount = useRef(stages.length);
  useEffect(() => {
    const before = stageCount.current;
    stageCount.current = stages.length;
    if (!finale || before === stages.length) return;
    setIndex((current) => (current === before - 1 ? stages.length - 1 : current));
    setFurthest((current) => (current === before - 1 ? stages.length - 1 : current));
  }, [stages.length, finale]);

  useEffect(
    () => () => {
      if (timer.current) window.clearTimeout(timer.current);
    },
    [],
  );

  const onIndexChange = useCallback(
    (next: number) => {
      setIndex(next);
      setFurthest((current) => Math.max(current, next));
      // Only a real panel index is a valid position: the server rejects an
      // index past its panels, and the resolution stage is not a panel.
      if (!keepsPosition || next < 0 || next >= panelCount) return;
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => {
        void saveStoryReadingPosition(episode.id, next).catch(() => {
          /* the place is still held locally; a failed save must not interrupt reading */
        });
      }, POSITION_DEBOUNCE_MS);
    },
    [episode.id, panelCount, keepsPosition],
  );

  const noop = useCallback(() => {}, []);
  // The finale belongs to the day, not to the episode: a scene the server has
  // already filed still closes with the day's own «Continuer».
  const replay = mode === 'replay' || (!reread && !finale && episode.status !== 'available');
  // WP-92: «Rayons X» — the day's rule, named in the reader's chrome language.
  const rayonsTitle = storyRayonsTitle(episode, language);
  const margins = useMemo(
    () => (marginNotes && marginNotes.length ? placeMarginNotes(episode.panels, marginNotes) : null),
    [episode.panels, marginNotes],
  );
  const lastStageKey = stages.length ? stages[stages.length - 1].key : null;
  const renderStageMargin = useCallback(
    (stage: (typeof stages)[number]) => {
      if (!margins) return null;
      const here = stage.kind === 'panel' ? margins.byPanel[String(stage.panelId)] || [] : [];
      const notes = stage.key === lastStageKey ? [...here, ...margins.end] : here;
      return notes.length ? <MarginNotes notes={notes} language={language} /> : null;
    },
    [language, lastStageKey, margins],
  );

  if (!stages.length) return null;

  return (
    <>
      <FeuilletonReaderStyles />
      {margins && <ArchiveStyles />}
      <FeuilletonReader
        episodeLabel={specialKicker ? `${specialKicker} · ${eyebrow || storyEpisodeLabel(episode)}` : eyebrow || storyEpisodeLabel(episode)}
        title={title || episode.title_fr || 'Le feuilleton'}
        stages={stages}
        index={index}
        furthest={furthest}
        onIndexChange={onIndexChange}
        answers={{}}
        setAnswer={noop}
        onSubmit={noop}
        submittingTask={null}
        attemptsByTask={{}}
        submitError={null}
        liveTaskId={null}
        onExit={onExit}
        onComplete={replay ? null : onContinue ?? null}
        completing={continuing}
        completeLabel={continueLabel}
        filed={replay}
        nextHref={replay ? nextHref : null}
        nextLabel={nextLabel}
        panelVariant={panelReaderVariant}
        footLink={footLink}
        language={language}
        lineVoice={lineVoice}
        listenLabel={listenLabel}
        finaleExtra={finaleExtra}
        finaleWait={finaleWait}
        rayonsTitle={rayonsTitle}
        rayonsReplay={reread}
        rayonsPast={reread}
        layout={layout ?? deviceLayout}
        renderStageMargin={margins ? renderStageMargin : undefined}
        /*
          WP-44. The «Décor de référence…» banner is gone. Reusing the
          location's art is a production fact, not a thing the learner has done
          or must act on, and stating it above every scene taught them to read a
          disclaimer before a story. The fact itself is not lost: it stays on
          the reader as `data-art`, where telemetry and QA can read it.
        */
        artProvenance={storyUsesSettingArt(episode) ? 'setting_reference' : null}
      />
    </>
  );
}

export default StoryEpisodeReader;

// ---------------------------------------------------------------------------
// WP-32 — «Écouter d'abord»: the same episode, heard before it is read
// ---------------------------------------------------------------------------

/**
 * The four-stage metacognitive listening cycle over one story-engine episode.
 *
 * The effect the package claims is the cycle's, not the audio's: predict →
 * listen → verify → debrief carries a consistent moderate benefit, largest for
 * the weakest listeners (Vandergrift & Tafaghodtari 2010; Vandergrift & Goh
 * 2012). Handing a learner a play button and the same page is the audio-only
 * condition, which is the one the literature says does least — so this
 * component refuses to let anyone skip *prédire*, and refuses to open
 * *vérifier* to anyone who has not heard (or genuinely could not hear) the
 * episode.
 *
 * Everything it shows comes from the episode the reader already has, plus the
 * spoken clips of exactly those lines. It generates nothing, asks no model
 * anything, and grades nobody: the prediction check is recorded as metadata and
 * never appears as a mark.
 *
 * When the audio cannot be had — the flag is off, the device will not play, the
 * connection is gone, the provider failed — the stage says which, in one
 * sentence, and «Lire la scène» is one tap away. There is no state here whose
 * only exit is a working speaker.
 */
/**
 * The cycle's own chrome (WP-44, Radio.dc.html) follows WP-82's one language
 * rule like every other journey screen: the stage names, the ask and the two
 * buttons come from `copy` (the learner's language up to A2, French from B1).
 * The scene's own words stay French.
 */
export function EpisodeRadio({
  episode,
  copy,
  audio,
  continuing = false,
  onContinue,
  onReadInstead,
  onPrediction,
}: {
  episode: StoryEpisode;
  copy: JourneyCopy;
  audio: UseEpisodeAudio;
  continuing?: boolean;
  onContinue: () => void;
  /** Leave the cycle for the ordinary text scene. Always available. */
  onReadInstead: () => void;
  /** Record the prediction check. Never awaited: measurement must not block. */
  onPrediction?: (guess: EpisodeGuessId, verification: EpisodeVerification) => void;
}) {
  const [state, dispatch] = useReducer(radioReduce, RADIO_INITIAL);
  // WP-103 T2: the text, hidden until asked for — at every stage.
  const [text, dispatchText] = useReducer(radioTextReduce, RADIO_TEXT_INITIAL);
  const verification = useMemo(
    () => verifyEpisodeGuess(episode, state.guess),
    [episode, state.guess],
  );
  const recorded = useRef(false);

  const { state: audioState, prepare, heard } = audio;
  const unavailable = audioState.kind === 'unavailable' ? audioState.reason : null;

  // Reading the cache is free; synthesis only happens when there is nothing
  // cached, and only once the learner has committed to listening.
  useEffect(() => {
    if (state.stage === 'ecouter') prepare();
  }, [state.stage, prepare]);

  // Heard it, or established that it cannot be heard: either way the learner
  // has done what this stage can ask of them, and *vérifier* opens.
  useEffect(() => {
    if (state.stage !== 'ecouter') return;
    if (heard || unavailable) dispatch({ type: 'heard' });
  }, [state.stage, heard, unavailable]);

  // The prediction is recorded once, at the moment it is checked — before that
  // it is a tap the learner may still change.
  useEffect(() => {
    if (state.stage !== 'verifier' || recorded.current || !state.guess) return;
    recorded.current = true;
    onPrediction?.(state.guess, verification);
  }, [state.stage, state.guess, verification, onPrediction]);

  return (
    <EpisodeRadioView
      episode={episode}
      copy={copy}
      audio={audio}
      state={state}
      text={text}
      verification={verification}
      continuing={continuing}
      onContinue={onContinue}
      onReadInstead={onReadInstead}
      dispatch={dispatch}
      dispatchText={dispatchText}
    />
  );
}

/**
 * The cycle as one screen for a given state. Split from `EpisodeRadio` so each
 * stage can be rendered without driving audio (the node suite and the gallery
 * do exactly that); it holds no state of its own.
 */
export function EpisodeRadioView({
  episode,
  copy,
  audio,
  state,
  text,
  verification,
  continuing = false,
  onContinue,
  onReadInstead,
  dispatch,
  dispatchText,
}: {
  episode: StoryEpisode;
  copy: JourneyCopy;
  audio: UseEpisodeAudio;
  state: RadioState;
  text: RadioText;
  verification: EpisodeVerification;
  continuing?: boolean;
  onContinue: () => void;
  onReadInstead: () => void;
  dispatch: (event: RadioEvent) => void;
  dispatchText: (event: RadioTextEvent) => void;
}) {
  const guesses = useMemo(() => buildEpisodeGuesses(episode), [episode]);
  const lines = useMemo(() => episodeListenLines(episode), [episode]);
  const retain = useMemo(() => episodeRetainPhrase(episode), [episode]);
  const task = radioTask(episode, state.guess);
  const controls = radioTextControls(state.stage);

  const { state: audioState, play, playFrom, stop, heard } = audio;
  const unavailable = audioState.kind === 'unavailable' ? audioState.reason : null;

  const stageSteps = RADIO_STAGES.map((stage) => ({
    id: stage,
    state:
      radioStageOrdinal(stage) < radioStageOrdinal(state.stage)
        ? ('done' as const)
        : stage === state.stage
          ? ('active' as const)
          : ('pending' as const),
  }));

  const stageLabel: Record<RadioStage, string> = {
    predire: copy.radio_stage_predire,
    ecouter: copy.radio_stage_ecouter,
    verifier: copy.radio_stage_verifier,
    retenir: copy.radio_stage_retenir,
  };

  const unavailableCopy: Record<string, string> = {
    disabled: copy.radio_audio_disabled,
    failed: copy.radio_audio_failed,
    offline: copy.radio_audio_offline,
    unsupported: copy.radio_audio_unsupported,
    empty: copy.radio_audio_empty,
  };

  // One line of the scene: who says it, and its words when they are shown.
  const lineWords = (line: (typeof lines)[number]) => (
    <p className="av2-fr" lang="fr" data-radio-line-text="">
      {frenchSpacing(line.fr)}
    </p>
  );

  // A per-line toggle: «Afficher le texte» / «Masquer le texte».
  const lineToggle = (line: (typeof lines)[number], index: number) => {
    const shown = radioLineShown(text, line.key);
    return (
      <Action
        tone="quiet"
        inline
        disabled={text.all}
        aria-pressed={shown}
        data-radio-line-toggle=""
        onClick={() => dispatchText({ type: 'line', key: line.key })}
      >
        {shown ? copy.radio_text_hide : copy.radio_text_show}
        <span className="av2-sr">
          {' · '}
          {line.who || stageLabel.ecouter} {index + 1}
        </span>
      </Action>
    );
  };

  // The whole page's text, for the stages that do not list the lines already.
  const pageText = text.all && !controls.lines && lines.length > 0 && (
    <ol className="av2-stack" data-radio-page-text="">
      {lines.map((line) => (
        <li key={line.key}>
          <Surface>
            {line.who && <Byline name={line.who} characterId={line.characterId} />}
            {lineWords(line)}
          </Surface>
        </li>
      ))}
    </ol>
  );

  // The listening question: shown before the audio and again after it.
  const question = (
    <Surface tone="outline" data-radio-task="">
      <p className="av2-label">{copy.radio_task_label}</p>
      <p className="av2-headline av2-headline--rule">{copy.radio_task_question}</p>
      {task.guessFr && (
        <p className="av2-body">
          <span className="av2-label">{copy.radio_guess_label}</span>{' '}
          <span lang="fr">{frenchSpacing(task.guessFr)}</span>
        </p>
      )}
    </Surface>
  );

  return (
    <section className="av2-stack av2-step wp44-radio" data-radio-stage={state.stage}>
      <p className="av2-label av2-label--story">
        <span lang="fr">{storyEpisodeLabel(episode)}</span>
        {' · '}
        {stageLabel[state.stage]}
      </p>
      <StepProgress
        steps={stageSteps}
        label={stageLabel.predire}
        caption={stageLabel[state.stage]}
      />
      <h2 className="av2-headline" lang="fr">
        {frenchSpacing(episode.title_fr || storyEpisodeLabel(episode))}
      </h2>

      {/* WP-103 T2: at every stage, the whole page's text is one tap away. */}
      <div className="wp44-radio__text">
        <Chip
          icon={<ShapeToken kind="story" size="sm" />}
          aria-pressed={text.all}
          data-radio-text-toggle=""
          onClick={() => dispatchText({ type: 'all' })}
        >
          {text.all ? copy.radio_text_hide : copy.radio_text_show}
        </Chip>
      </div>

      {state.stage === 'predire' && (
        <>
          <p className="av2-body av2-body--lg">
            {copy.radio_predire_body}
          </p>
          <ChoiceList
            options={guesses.map((guess) => ({ id: guess.id, textFr: guess.fr }))}
            selectedId={state.guess}
            label={copy.radio_guess_label}
            onSelect={(id) => dispatch({ type: 'guess', id: id as EpisodeGuessId })}
            statusLabels={{
              selected: copy.radio_guess_selected,
              // A prediction is never marked, so the two verdict words the
              // choice list can render are never reachable here. They are still
              // required by its contract; they are deliberately the neutral
              // ones rather than «juste»/«faux».
              correct: copy.radio_guess_selected,
              wrong: copy.radio_guess_selected,
            }}
          />
          {/* the one line in the learner's own language: what is about to
              happen, said once, as body copy and never as chrome */}
          <p className="av2-body">{copy.radio_predire_native}</p>
          {pageText}
          <div className="wp44-radio__foot av2-screen__foot">
            <Action
              tone="primary"
              disabled={!state.guess}
              onClick={() => dispatch({ type: 'listen' })}
            >
              {copy.radio_listen_action}
            </Action>
            <Action tone="quiet" onClick={onReadInstead}>
              {copy.radio_read_instead}
            </Action>
          </div>
        </>
      )}

      {state.stage === 'ecouter' && (
        <>
          {question}
          <p className="av2-body av2-body--lg">{copy.radio_ecouter_body}</p>

          {unavailable ? (
            <Notice tone="alert" live="alert" shape="action">
              {unavailableCopy[unavailable] ?? copy.radio_audio_failed}
            </Notice>
          ) : (
            <>
              {audioState.kind === 'preparing' && (
                <StateBlock tone="loading" title={copy.radio_preparing} />
              )}
              <ol className="av2-stack" data-radio-lines={text.all ? 'shown' : 'hidden'}>
                {lines.map((line, index) => {
                  const active = audioState.kind === 'playing' && audioState.index === index;
                  const shown = radioLineShown(text, line.key);
                  return (
                    <li key={line.key}>
                      <Surface tone={active ? 'blue' : 'paper'}>
                        <p className="av2-label">
                          {line.who || stageLabel.ecouter}
                          {!shown && (
                            <>
                              {' · '}
                              <span className="av2-body">{copy.radio_words_hidden}</span>
                            </>
                          )}
                        </p>
                        {shown && lineWords(line)}
                        <div className="wp44-radio__line-actions">
                          <Action
                            tone="quiet"
                            inline
                            disabled={audioState.kind !== 'ready' && audioState.kind !== 'played'}
                            onClick={() => playFrom(index)}
                          >
                            {copy.radio_replay}
                          </Action>
                          {lineToggle(line, index)}
                        </div>
                      </Surface>
                    </li>
                  );
                })}
              </ol>
              {audioState.kind === 'playing' ? (
                <Action tone="secondary" onClick={stop}>
                  {copy.radio_stop}
                </Action>
              ) : (
                <Action
                  tone="primary"
                  disabled={audioState.kind === 'preparing' || audioState.kind === 'idle'}
                  onClick={play}
                >
                  {heard ? copy.radio_replay : copy.radio_play}
                </Action>
              )}
            </>
          )}

          {/* With the words shown and no audio to wait for, the text is the way on. */}
          <Action
            tone={unavailable ? 'primary' : 'secondary'}
            disabled={!state.heard}
            onClick={() => dispatch({ type: 'verify' })}
          >
            {copy.radio_verify_action}
          </Action>
          <Action tone="quiet" onClick={onReadInstead}>
            {copy.radio_read_instead}
          </Action>
        </>
      )}

      {state.stage === 'verifier' && (
        <>
          {question}
          <Notice tone="quiet" shape="story">
            {verification.verdict === 'confirmed'
              ? copy.radio_guess_confirmed
              : verification.verdict === 'other'
                ? copy.radio_guess_other
                : copy.radio_guess_unresolved}
          </Notice>
          {verification.quoteFr && (
            <Surface>
              <p className="av2-label">{copy.radio_evidence_label}</p>
              <p className="av2-fr av2-headline av2-headline--rule" lang="fr">
                {frenchSpacing(verification.quoteFr)}
              </p>
            </Surface>
          )}

          <p className="av2-body av2-body--lg">{copy.radio_verifier_body}</p>
          <ol className="av2-stack">
            {lines.map((line, index) => (
              <li key={line.key}>
                <Surface>
                  {/* WP-77: the speaker's face with their name; narration has none. */}
                  {line.who && <Byline name={line.who} characterId={line.characterId} />}
                  {radioLineShown(text, line.key) ? lineWords(line) : null}
                  {lineToggle(line, index)}
                </Surface>
              </li>
            ))}
          </ol>
          <Action tone="primary" onClick={() => dispatch({ type: 'retain' })}>
            {stageLabel.retenir}
          </Action>
        </>
      )}

      {state.stage === 'retenir' && (
        <>
          <p className="av2-body av2-body--lg">{copy.radio_retenir_body}</p>
          <Surface tone="outline">
            {retain ? (
              <p className="av2-fr av2-headline av2-headline--rule" lang="fr">
                {frenchSpacing(retain)}
              </p>
            ) : (
              <p className="av2-body">{copy.radio_retain_none}</p>
            )}
          </Surface>
          {pageText}
          <Action
            tone="primary"
            pending={continuing}
            pendingLabel={copy.sending}
            onClick={onContinue}
          >
            {copy.scene_continue}
          </Action>
        </>
      )}
    </section>
  );
}

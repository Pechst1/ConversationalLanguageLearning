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
import {
  Action,
  Byline,
  ChoiceList,
  Notice,
  StateBlock,
  StepProgress,
  Surface,
} from '@/components/atelier-v2/ui';
import { frenchSpacing } from '@/lib/french-typography';
import { saveStoryReadingPosition } from '@/services/daily-journey';
import type { StoryEpisode } from '@/types/daily-journey';

import type { JourneyCopy } from './journey-copy';
import {
  RADIO_INITIAL,
  RADIO_STAGES,
  buildEpisodeGuesses,
  buildStoryStages,
  episodeListenLines,
  episodeRetainPhrase,
  panelReaderVariant,
  radioReduce,
  radioStageOrdinal,
  storyEpisodeLabel,
  storyStartIndex,
  storyUsesSettingArt,
  verifyEpisodeGuess,
  type EpisodeGuessId,
  type EpisodeVerification,
  type RadioStage,
} from './story-episode-model';
import type { UseEpisodeAudio } from './useEpisodeAudio';

export type StoryEpisodeReaderProps = {
  episode: StoryEpisode;
  /** `continue` hands the end of the panels to the daily journey; `replay` reads only. */
  mode: 'continue' | 'replay';
  onExit: () => void;
  onContinue?: () => void;
  continuing?: boolean;
  continueLabel?: string;
  /** Where a replay can go next, if anywhere. */
  nextHref?: string | null;
  nextLabel?: string;
  /** WP-44. A quiet link under the nav — «Écouter d'abord» in the journey. */
  footLink?: React.ReactNode;
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
}: StoryEpisodeReaderProps) {
  const stages = useMemo(() => buildStoryStages(episode), [episode]);
  const panelCount = episode.panels?.length ?? 0;
  const start = storyStartIndex(episode, stages.length);
  const [index, setIndex] = useState(start);
  const [furthest, setFurthest] = useState(start);
  const timer = useRef<number | null>(null);

  // A different episode is a different place.
  useEffect(() => {
    setIndex(start);
    setFurthest(start);
  }, [episode.id, start]);

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
      if (next < 0 || next >= panelCount) return;
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => {
        void saveStoryReadingPosition(episode.id, next).catch(() => {
          /* the place is still held locally; a failed save must not interrupt reading */
        });
      }, POSITION_DEBOUNCE_MS);
    },
    [episode.id, panelCount],
  );

  const noop = useCallback(() => {}, []);
  const replay = mode === 'replay' || episode.status !== 'available';

  if (!stages.length) return null;

  return (
    <>
      <FeuilletonReaderStyles />
      <FeuilletonReader
        episodeLabel={storyEpisodeLabel(episode)}
        title={episode.title_fr || 'Le feuilleton'}
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
 * The cycle's own chrome, in French (WP-44, Radio.dc.html).
 *
 * The artboards settle a question WP-32 left open: one chrome language per
 * screen, and on a screen whose entire content is French the chrome is French
 * too. The learner's own language does not disappear — it keeps the one line
 * that says what is about to happen (`radio_*_native`), as a line of body copy
 * rather than as furniture. Everything else the learner reads here is the
 * scene's own words.
 *
 * They are constants and not copy keys on purpose: a key implies a translation
 * that this screen must not have.
 */
const RADIO_FR: Record<RadioStage, string> = {
  predire: 'Prédire',
  ecouter: 'Écouter',
  verifier: 'Vérifier',
  retenir: 'Retenir',
};

const RADIO_FR_PREDIRE_BODY =
  'Avant d’écouter : comment ça finit ? Se tromper ne coûte rien — c’est la prédiction qui fait travailler l’oreille.';
const RADIO_FR_LISTEN = 'Écouter';
const RADIO_FR_READ_INSTEAD = 'Lire la scène';

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
  const guesses = useMemo(() => buildEpisodeGuesses(episode), [episode]);
  const lines = useMemo(() => episodeListenLines(episode), [episode]);
  const verification = useMemo(
    () => verifyEpisodeGuess(episode, state.guess),
    [episode, state.guess],
  );
  const retain = useMemo(() => episodeRetainPhrase(episode), [episode]);
  const recorded = useRef(false);

  const { state: audioState, prepare, play, playFrom, stop, heard } = audio;
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

  const stageSteps = RADIO_STAGES.map((stage) => ({
    id: stage,
    state:
      radioStageOrdinal(stage) < radioStageOrdinal(state.stage)
        ? ('done' as const)
        : stage === state.stage
          ? ('active' as const)
          : ('pending' as const),
  }));

  const stageLabel = RADIO_FR;

  const unavailableCopy: Record<string, string> = {
    disabled: copy.radio_audio_disabled,
    failed: copy.radio_audio_failed,
    offline: copy.radio_audio_offline,
    unsupported: copy.radio_audio_unsupported,
    empty: copy.radio_audio_empty,
  };

  return (
    <section className="av2-stack av2-step wp44-radio" data-radio-stage={state.stage}>
      <p className="av2-label av2-label--story" lang="fr">
        {[storyEpisodeLabel(episode), stageLabel[state.stage]].filter(Boolean).join(' · ')}
      </p>
      <StepProgress
        steps={stageSteps}
        label={RADIO_FR.predire}
        caption={stageLabel[state.stage]}
      />
      <h2 className="av2-headline" lang="fr">
        {frenchSpacing(episode.title_fr || storyEpisodeLabel(episode))}
      </h2>

      {state.stage === 'predire' && (
        <>
          <p className="av2-body av2-body--lg" lang="fr">
            {RADIO_FR_PREDIRE_BODY}
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
          <div className="wp44-radio__foot av2-screen__foot">
            <Action
              tone="primary"
              disabled={!state.guess}
              onClick={() => dispatch({ type: 'listen' })}
            >
              {RADIO_FR_LISTEN}
            </Action>
            <Action tone="quiet" onClick={onReadInstead}>
              {RADIO_FR_READ_INSTEAD}
            </Action>
          </div>
        </>
      )}

      {state.stage === 'ecouter' && (
        <>
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
              <ol className="av2-stack" data-radio-lines="hidden">
                {lines.map((line, index) => {
                  const active = audioState.kind === 'playing' && audioState.index === index;
                  return (
                    <li key={line.key}>
                      <Surface tone={active ? 'blue' : 'paper'}>
                        <p className="av2-label">
                          {line.who || RADIO_FR.ecouter}
                          {' · '}
                          <span className="av2-body">{copy.radio_words_hidden}</span>
                        </p>
                        <Action
                          tone="quiet"
                          inline
                          disabled={audioState.kind !== 'ready' && audioState.kind !== 'played'}
                          onClick={() => playFrom(index)}
                        >
                          {copy.radio_replay}
                        </Action>
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

          <Action
            tone={unavailable ? 'primary' : 'secondary'}
            disabled={!state.heard}
            onClick={() => dispatch({ type: 'verify' })}
          >
            {copy.radio_verify_action}
          </Action>
          <Action tone="quiet" onClick={onReadInstead}>
            {RADIO_FR_READ_INSTEAD}
          </Action>
        </>
      )}

      {state.stage === 'verifier' && (
        <>
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
                  {index < state.revealed ? (
                    <p className="av2-fr" lang="fr">
                      {frenchSpacing(line.fr)}
                    </p>
                  ) : (
                    <Action tone="quiet" inline onClick={() => dispatch({ type: 'reveal' })}>
                      {copy.radio_reveal}
                    </Action>
                  )}
                </Surface>
              </li>
            ))}
          </ol>
          {state.revealed < lines.length && (
            <Action
              tone="secondary"
              onClick={() => dispatch({ type: 'revealAll', count: lines.length })}
            >
              {copy.radio_reveal_all}
            </Action>
          )}
          <Action tone="primary" onClick={() => dispatch({ type: 'retain' })}>
            {RADIO_FR.retenir}
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

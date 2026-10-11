/**
 * The daily journey's scene step, read as story-engine panels when the engine
 * has published them (WP-14E), heard first when the learner has asked for that
 * (WP-32), and as the plain scene prompt otherwise.
 *
 * `getStoryEpisodeForJourney(journey.id)` is scoped to the learner; absent or
 * legacy content returns null and the existing `SceneStepView` renders, so a
 * journey never loses its scene because the projection is missing. The
 * lookup is a GET — it neither generates nor completes anything.
 *
 * WP-90: the lookup and the panel-art poll live in the journey controller
 * (`useDailyJourney` → `story-episode-store.ts`), so drawings that land after
 * the learner has moved on are still fetched, and a scene the controller has
 * already read opens at once. This step reads the cache, and asks for the
 * episode itself only when nobody has yet.
 *
 * WP-32's addition is deliberately narrow. «Écouter d'abord» is opt-in and
 * remembered per learner; with it off this file behaves exactly as it did, and
 * *nothing* about the audio path is reached — no manifest read, no synthesis,
 * no new request of any kind. That is the property the node suite pins, because
 * it is the one that decides whether an experiment can cost a learner their
 * ordinary scene.
 */

import React, { useCallback, useEffect, useState } from 'react';

import { Action, StateBlock } from '@/components/atelier-v2/ui';
import { Precedemment } from '@/components/feuilleton/archive/ArchiveMarks';
import { ArchiveStyles } from '@/components/feuilleton/archive/ArchiveStyles';
import { marginNotes as readMarginNotes } from '@/components/feuilleton/archive/archive-model';
import {
  precedemmentView,
  readPrecedemmentDismissed,
  writePrecedemmentDismissed,
} from '@/components/feuilleton/archive/precedemment-model';
import { scenePlace } from '@/lib/sound-bed';
import { getStoryEpisodeForJourney, recordEpisodePrediction } from '@/services/daily-journey';
import type { ControlLanguage, SceneStep, StoryEpisode } from '@/types/daily-journey';

import type { JourneyCopy } from './journey-copy';
import type { JourneySpeaker } from './journey-faces';
import { SceneStepView } from './JourneySteps';
import { EpisodeRadio, StoryEpisodeReader } from './StoryEpisodeReader';
import {
  authoredPageEpisode,
  listenFirstPlacement,
  readListenFirst,
  writeListenFirst,
  type EpisodeGuessId,
  type EpisodeVerification,
} from './story-episode-model';
import { getStoryEpisodeEntry, loadStoryEpisode, useStoryEpisodeEntry } from './story-episode-store';
import { useEpisodeAudio } from './useEpisodeAudio';
import { useSoundBed } from './useSoundBed';
import { listenLabel, useStepVoice } from './useStepVoice';

type Lookup = { kind: 'loading' } | { kind: 'none' } | { kind: 'episode'; episode: StoryEpisode };

export function StoryEpisodeStep({
  journeyId,
  step,
  copy,
  busy,
  onContinue,
  onExit,
  speaker = null,
  language = null,
  firstDay = false,
  locationId = null,
}: {
  journeyId: string;
  step: SceneStep;
  copy: JourneyCopy;
  busy: boolean;
  onContinue: () => void;
  onExit?: () => void;
  /** WP-77: who says the scene's line, so the plain scene shows their face. */
  speaker?: JourneySpeaker | null;
  /** WP-82: the screen's chrome language, so the reader's buttons match `copy`. */
  language?: ControlLanguage | null;
  /** WP-96: the learner's first day — there is no «Précédemment» yet. */
  firstDay?: boolean;
  /** WP-145: the place the scene is set in (the journey scenario's `location_id`), for its sound bed. */
  locationId?: string | null;
}) {
  // Server rendering (and the node test harness) has no effects and no cache:
  // render the scene prompt straight away rather than a loading state that
  // never ends.
  const entry = useStoryEpisodeEntry(journeyId);
  const lookup: Lookup =
    typeof window === 'undefined' ? { kind: 'none' } : entry ?? { kind: 'loading' };
  // WP-90/91: the face beside a caption is the play button — the scene step's
  // own server clips (the server refuses a text that is not a line of this
  // step), the device's French voice when there are none.
  const lineVoice = useStepVoice(journeyId, step.id);
  const speakLabel = useCallback((name: string) => listenLabel(copy, name), [copy]);
  // The remembered choice is read once, on the client. It defaults to off:
  // listening first is the harder way to meet a scene, and handing the hardest
  // condition to someone who never asked for it is how a good idea gets
  // measured as a bad one.
  const [listenFirst, setListenFirst] = useState(false);
  useEffect(() => {
    setListenFirst(readListenFirst());
  }, []);

  // WP-96 «Précédemment»: the chronicle's last lines before the first panel,
  // read once per scene. Before the client has read its memory the box is not
  // drawn — a reminder must never flash and vanish.
  const [previouslyRead, setPreviouslyRead] = useState<boolean | null>(null);
  useEffect(() => {
    setPreviouslyRead(readPrecedemmentDismissed(journeyId, step.id));
  }, [journeyId, step.id]);
  const previously = precedemmentView({
    lines: step.prompt.previously_fr,
    firstDay,
    dismissed: previouslyRead !== false,
  });
  const readOn = useCallback(() => {
    writePrecedemmentDismissed(journeyId, step.id);
    setPreviouslyRead(true);
  }, [journeyId, step.id]);
  // WP-97: the consequences this page pays back, in its margin.
  const margins = readMarginNotes(step.prompt.margin_notes);

  // The controller normally asked already (and polls the drawings). A step
  // mounted without it — or before it asked — reads the episode once itself.
  useEffect(() => {
    if (!journeyId || getStoryEpisodeEntry(journeyId)) return;
    void loadStoryEpisode(journeyId, getStoryEpisodeForJourney);
  }, [journeyId, step.id]);

  const sceneId = lookup.kind === 'episode' ? lookup.episode.id : null;
  // WP-49: the server says whether it can honour the listening-first cycle.
  // WP-66: the planner may have dealt this day as «jour d'écoute».
  // F-27: those two facts, plus the remembered choice, decide *where* the offer
  // goes — and the one place it may not go is after the scene has been read.
  const audioAvailable = Boolean(step.prompt.audio_available);
  const placement = listenFirstPlacement({
    audioAvailable,
    preferred: listenFirst,
    dealt: Boolean(step.prompt.listen_first),
  });
  const audio = useEpisodeAudio({
    sceneId,
    enabled: placement === 'cycle' && lookup.kind === 'episode',
  });

  // WP-145 «Ambiance»: the place's sound bed under the scene, ducked while a
  // line (or the listening-first recording) plays. Silent unless «Sons» and
  // «Ambiance» are on, and nothing starts before the learner's first gesture.
  const scenePanels = lookup.kind === 'episode' ? lookup.episode.panels : step.prompt.panels;
  const firstPlate = (scenePanels ?? []).find((panel) => panel?.plate_url)?.plate_url ?? null;
  useSoundBed({
    place: scenePlace(locationId, firstPlate),
    speaking: lineVoice.speakingKey !== null || audio.state.kind === 'playing',
  });

  const chooseMode = useCallback((enabled: boolean) => {
    setListenFirst(enabled);
    writeListenFirst(enabled);
  }, []);

  const recordPrediction = useCallback(
    (guess: EpisodeGuessId, verification: EpisodeVerification) => {
      if (!sceneId) return;
      // Fire and forget on purpose: this is measurement, and a learner must
      // never wait on — or be stopped by — the recording of a tap.
      void recordEpisodePrediction(sceneId, {
        guess,
        verdict: verification.verdict,
        supported: verification.supported,
      }).catch(() => {});
    },
    [sceneId],
  );

  if (lookup.kind === 'loading') {
    return <StateBlock tone="loading" title={copy.preparing_title} body={copy.preparing_body} />;
  }

  if (previously) {
    return (
      <>
        <ArchiveStyles />
        <Precedemment lines={previously} language={language} onRead={readOn} journeyId={journeyId} />
      </>
    );
  }

  if (lookup.kind === 'episode') {
    if (placement === 'cycle') {
      return (
        <EpisodeRadio
          episode={lookup.episode}
          copy={copy}
          audio={audio}
          continuing={busy}
          onContinue={onContinue}
          onReadInstead={() => chooseMode(false)}
          onPrediction={recordPrediction}
        />
      );
    }
    return (
      <>
        {/*
          F-27. WP-44 put the offer on the reader's foot — one quiet link under
          the nav — and the QA walk found what that costs: the learner meets it
          after reading the whole scene, and the cycle it opens starts by asking
          them to predict how that scene ends. So the same quiet link, with the
          same one-sentence title, now sits *before the first planche*, which is
          the only place where accepting it still means anything. It is still
          one tap and still nothing to dismiss; a learner who came to read
          scrolls past one line.
        */}
        {placement === 'before_first_panel' && (
          <p className="av2-body wp66-listen-offer" data-listen-offer="before-first-panel">
            <Action
              tone="quiet"
              inline
              title={copy.listen_first_hint}
              onClick={() => chooseMode(true)}
            >
              {copy.listen_first_on}
            </Action>
          </p>
        )}
        <StoryEpisodeReader
          episode={lookup.episode}
          mode="continue"
          onExit={onExit ?? (() => {})}
          onContinue={onContinue}
          continuing={busy}
          continueLabel={copy.scene_continue}
          language={language}
          lineVoice={lineVoice}
          listenLabel={speakLabel}
          marginNotes={margins}
          /* The foot keeps «Lire plutôt»'s counterpart nowhere: the offer is
             made once, above, and never a second time under the last panel. */
          footLink={null}
        />
      </>
    );
  }

  // An authored scene (the first day, the engine's stand-in) carries its own page.
  const page = authoredPageEpisode(journeyId, step.id, step.prompt.panels);
  if (page) {
    return (
      <StoryEpisodeReader
        episode={page}
        mode="continue"
        onExit={onExit ?? (() => {})}
        onContinue={onContinue}
        continuing={busy}
        continueLabel={copy.scene_continue}
        language={language}
        lineVoice={lineVoice}
        listenLabel={speakLabel}
        footLink={null}
        savePosition={false}
      />
    );
  }

  return (
    <SceneStepView step={step} copy={copy} busy={busy} onContinue={onContinue} speaker={speaker} />
  );
}

export default StoryEpisodeStep;

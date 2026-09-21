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
 * WP-32's addition is deliberately narrow. «Écouter d'abord» is opt-in and
 * remembered per learner; with it off this file behaves exactly as it did, and
 * *nothing* about the audio path is reached — no manifest read, no synthesis,
 * no new request of any kind. That is the property the node suite pins, because
 * it is the one that decides whether an experiment can cost a learner their
 * ordinary scene.
 */

import React, { useCallback, useEffect, useState } from 'react';

import { Action, StateBlock } from '@/components/atelier-v2/ui';
import { getStoryEpisodeForJourney, recordEpisodePrediction } from '@/services/daily-journey';
import type { SceneStep, StoryEpisode } from '@/types/daily-journey';

import type { JourneyCopy } from './journey-copy';
import { SceneStepView } from './JourneySteps';
import { EpisodeRadio, StoryEpisodeReader } from './StoryEpisodeReader';
import {
  listenFirstPlacement,
  readListenFirst,
  writeListenFirst,
  type EpisodeGuessId,
  type EpisodeVerification,
} from './story-episode-model';
import { useEpisodeAudio } from './useEpisodeAudio';

type Lookup = { kind: 'loading' } | { kind: 'none' } | { kind: 'episode'; episode: StoryEpisode };

export function StoryEpisodeStep({
  journeyId,
  step,
  copy,
  busy,
  onContinue,
  onExit,
}: {
  journeyId: string;
  step: SceneStep;
  copy: JourneyCopy;
  busy: boolean;
  onContinue: () => void;
  onExit?: () => void;
}) {
  // Server rendering (and the node test harness) has no effects: render the
  // scene prompt straight away rather than a loading state that never ends.
  const [lookup, setLookup] = useState<Lookup>(() =>
    typeof window === 'undefined' ? { kind: 'none' } : { kind: 'loading' },
  );
  // The remembered choice is read once, on the client. It defaults to off:
  // listening first is the harder way to meet a scene, and handing the hardest
  // condition to someone who never asked for it is how a good idea gets
  // measured as a bad one.
  const [listenFirst, setListenFirst] = useState(false);
  useEffect(() => {
    setListenFirst(readListenFirst());
  }, []);

  useEffect(() => {
    let alive = true;
    setLookup({ kind: 'loading' });
    getStoryEpisodeForJourney(journeyId)
      .then((episode) => {
        if (!alive) return;
        setLookup(episode && episode.panels?.length ? { kind: 'episode', episode } : { kind: 'none' });
      })
      .catch(() => {
        // The projection is optional. A failed lookup is not a failed scene.
        if (alive) setLookup({ kind: 'none' });
      });
    return () => {
      alive = false;
    };
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
          /* The foot keeps «Lire plutôt»'s counterpart nowhere: the offer is
             made once, above, and never a second time under the last panel. */
          footLink={null}
        />
      </>
    );
  }

  return <SceneStepView step={step} copy={copy} busy={busy} onContinue={onContinue} />;
}

export default StoryEpisodeStep;

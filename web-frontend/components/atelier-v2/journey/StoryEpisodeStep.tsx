/**
 * The daily journey's scene step, read as story-engine panels when the engine
 * has published them (WP-14E), and as the plain scene prompt otherwise.
 *
 * `getStoryEpisodeForJourney(journey.id)` is scoped to the learner; absent or
 * legacy content returns null and the existing `SceneStepView` renders, so a
 * journey never loses its scene because the projection is missing. The
 * lookup is a GET — it neither generates nor completes anything.
 */

import React, { useEffect, useState } from 'react';

import { StateBlock } from '@/components/atelier-v2/ui';
import { getStoryEpisodeForJourney } from '@/services/daily-journey';
import type { SceneStep, StoryEpisode } from '@/types/daily-journey';

import type { JourneyCopy } from './journey-copy';
import { SceneStepView } from './JourneySteps';
import { StoryEpisodeReader } from './StoryEpisodeReader';

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

  if (lookup.kind === 'loading') {
    return <StateBlock tone="loading" title={copy.preparing_title} body={copy.preparing_body} />;
  }

  if (lookup.kind === 'episode') {
    return (
      <StoryEpisodeReader
        episode={lookup.episode}
        mode="continue"
        onExit={onExit ?? (() => {})}
        onContinue={onContinue}
        continuing={busy}
        continueLabel={copy.scene_continue}
      />
    );
  }

  return <SceneStepView step={step} copy={copy} busy={busy} onContinue={onContinue} />;
}

export default StoryEpisodeStep;

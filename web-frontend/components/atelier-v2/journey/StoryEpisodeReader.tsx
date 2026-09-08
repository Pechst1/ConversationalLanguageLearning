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

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { FeuilletonReader, FeuilletonReaderStyles } from '@/components/feuilleton/reader';
import { saveStoryReadingPosition } from '@/services/daily-journey';
import type { StoryEpisode } from '@/types/daily-journey';

import {
  buildStoryStages,
  storyEpisodeLabel,
  storyStartIndex,
  storyUsesSettingArt,
} from './story-episode-model';

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
        banner={
          storyUsesSettingArt(episode) ? (
            <p className="fr-state" data-art="setting_reference">
              <span className="tok" aria-hidden="true" />
              Décor de référence : l’illustration montre le lieu, elle n’est pas une planche inédite.
            </p>
          ) : null
        }
      />
    </>
  );
}

export default StoryEpisodeReader;

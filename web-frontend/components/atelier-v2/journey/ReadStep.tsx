/**
 * WP-93 «Plus d'histoire, moins d'exercices» — the READ step.
 *
 * A page to read, advanced and never answered, and always optional:
 *
 *   relecture  yesterday's page again («Relecture · la page d'hier»);
 *   coulisses  the same evening from another cast member's point of view,
 *              written in the background («Coulisses · la soirée de Marin»).
 *
 * `ready` opens the page in the existing reader, read-only (`mode="reread"`:
 * no respond, no tasks, no reading position saved), fetched by its
 * `scene_id`; the faces speak their lines through the step's own voice, as
 * in the scene step. `writing` shows the cast member's face writing it, while
 * the controller re-reads the journey gently (`readPollTarget`). `unavailable`
 * is one quiet line. In every state «Continuer» is enabled: reading more is an
 * offer, never a gate.
 */

import React, { useCallback, useEffect, useState } from 'react';

import { Action, Notice, ShapeToken, StateBlock } from '@/components/atelier-v2/ui';
import { frenchSpacing } from '@/lib/french-typography';
import { getStoryEpisode } from '@/services/daily-journey';
import type { ControlLanguage, ReadStep, StoryEpisode } from '@/types/daily-journey';

import type { JourneyCopy } from './journey-copy';
import type { JourneySpeaker } from './journey-faces';
import { StoryWriting } from './ReplyStage';
import { StoryEpisodeReader } from './StoryEpisodeReader';
import {
  readStepEyebrow,
  readStepSpeaker,
  readStepView,
  readStepWantsEpisode,
  readStepWritingLine,
  type ReadLookup,
} from './read-step-model';
import { listenLabel, useStepVoice } from './useStepVoice';

export type ReadStepViewProps = {
  journeyId: string | null;
  step: ReadStep;
  copy: JourneyCopy;
  busy: boolean;
  onContinue: () => void;
  onExit?: (() => void) | null;
  /** The reader's chrome language — the journey screen's. */
  language?: ControlLanguage | null;
  /** The day's counterpart: the face of «Coulisses» when the prompt names nobody. */
  speaker?: JourneySpeaker | null;
  /** How the page is fetched; the gallery hands in its fixture. */
  loadEpisode?: (sceneId: string) => Promise<StoryEpisode | null>;
};

export function ReadStepView({
  journeyId,
  step,
  copy,
  busy,
  onContinue,
  onExit = null,
  language = null,
  speaker = null,
  loadEpisode = getStoryEpisode,
}: ReadStepViewProps) {
  const prompt = step.prompt;
  const sceneId = readStepWantsEpisode(prompt);
  const [lookup, setLookup] = useState<ReadLookup>({ kind: 'idle' });
  const lineVoice = useStepVoice(journeyId, step.id);
  const speakLabel = useCallback((name: string) => listenLabel(copy, name), [copy]);

  useEffect(() => {
    if (!sceneId) {
      setLookup({ kind: 'idle' });
      return undefined;
    }
    let live = true;
    setLookup({ kind: 'loading' });
    loadEpisode(sceneId)
      .then((episode) => {
        if (live) setLookup(episode ? { kind: 'episode', episode } : { kind: 'failed' });
      })
      .catch(() => {
        if (live) setLookup({ kind: 'failed' });
      });
    return () => {
      live = false;
    };
  }, [sceneId, loadEpisode]);

  const proceed = useCallback(() => {
    if (!busy) onContinue();
  }, [busy, onContinue]);

  const who = readStepSpeaker(prompt, speaker);
  const eyebrow = readStepEyebrow(prompt, copy, who?.name);
  const view = readStepView(prompt, lookup);

  if (view === 'reader' && lookup.kind === 'episode') {
    return (
      <StoryEpisodeReader
        episode={lookup.episode}
        mode="reread"
        eyebrow={eyebrow}
        title={prompt.title_fr || null}
        onExit={onExit}
        onContinue={proceed}
        continuing={busy}
        continueLabel={copy.scene_continue}
        language={language}
        lineVoice={lineVoice}
        listenLabel={speakLabel}
        savePosition={false}
        /* optional from the first panel: one quiet way on, under the nav */
        footLink={
          <Action tone="quiet" inline disabled={busy} onClick={proceed}>
            {copy.read_skip}
          </Action>
        }
      />
    );
  }

  return (
    <section
      className="av2-stack av2-step"
      data-step="read"
      data-read-variant={prompt.variant}
      data-read-state={view}
    >
      <p className="av2-label av2-label--story">
        <ShapeToken kind="story" size="sm" /> {eyebrow}
      </p>
      {prompt.title_fr && (
        <h2 className="av2-headline" lang="fr">
          {frenchSpacing(prompt.title_fr)}
        </h2>
      )}

      {view === 'writing' && (
        <>
          <StoryWriting speaker={who} line={readStepWritingLine(copy, who?.name)} />
          <p className="av2-body">{copy.read_optional}</p>
          {/* Waiting is the offer; going on is always one tap — never a dead primary. */}
          <Action tone="secondary" pending={busy} pendingLabel={copy.sending} onClick={proceed}>
            {copy.scene_continue}
          </Action>
        </>
      )}

      {view === 'loading' && (
        <>
          <StateBlock tone="loading" title={copy.preparing_title} />
          <Action tone="secondary" pending={busy} pendingLabel={copy.sending} onClick={proceed}>
            {copy.scene_continue}
          </Action>
        </>
      )}

      {view === 'unavailable' && (
        <>
          <Notice tone="quiet" shape="story">
            {copy.read_unavailable}
          </Notice>
          <Action tone="primary" pending={busy} pendingLabel={copy.sending} onClick={proceed}>
            {copy.scene_continue}
          </Action>
        </>
      )}
    </section>
  );
}

export default ReadStepView;

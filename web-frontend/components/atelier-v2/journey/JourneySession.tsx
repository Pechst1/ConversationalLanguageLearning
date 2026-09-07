/**
 * The one connected daily-journey shell — WP-07 **visual** milestone.
 *
 * Scene, recall, response, resolution and completion all render inside this
 * single component, so finishing the daily loop needs no tab switch and no
 * second screen. It receives the `useDailyJourney` controller and renders it —
 * it issues no request itself, and the controller is unchanged from the
 * functional milestone.
 *
 * ---------------------------------------------------------------------------
 * Design mapping — `Atelier App.dc.html`, the Séance screen
 * ---------------------------------------------------------------------------
 * Header: the round close control, then the blue progress rule, exactly as the
 * design draws them. Body: the step. Footer: the tinted feedback band above one
 * 3D-press primary.
 *
 * Two deliberate divergences, both recorded in FRONTEND-ENGINE-HANDOFF §4:
 *
 *  1. **No streak.** The design's header carries "12 jours de suite". Nothing
 *     in the contract exposes a real streak, and CONTRACTS forbids inventing
 *     one, so that slot is simply empty. It is not filled with a placeholder.
 *  2. **Progress is segmented, not a percentage of drills.** The design's bar
 *     is `exercise / 3`. Ours has one segment per real planned step, so it
 *     cannot claim a number the plan does not contain, and it renders nothing
 *     at all when there is no plan yet.
 *
 * Layout rules that are load-bearing rather than decorative:
 *   * one prompt, one answer area, one primary action, in that order;
 *   * the primary action sits in normal flow directly under the answer, so a
 *     software keyboard or the fixed bottom navigation can never cover it;
 *   * the shell reserves the bottom-navigation height, so nothing is hidden
 *     behind it at 320px or at large text.
 */

import React from 'react';

import {
  Action,
  AtelierV2Root,
  CrossIcon,
  IconAction,
  Notice,
  ShapeToken,
  StateBlock,
  StepProgress,
  Surface,
  type StepSegment,
} from '@/components/atelier-v2/ui';
import { atelierCopy, stepOfLabel, type AtelierCopy } from '@/lib/atelier-v2-copy';
import type { ConnectionView } from '@/lib/journey-recovery';
import type { PublicStep } from '@/types/daily-journey';

import { journeyCopy } from './journey-copy';
import { formatDuration, recapView, type JourneyPhase } from './journey-state';
import {
  JourneyFeedbackView,
  RecallStepView,
  RespondStepView,
  ResolutionStepView,
} from './JourneySteps';
import { StoryEpisodeStep } from './StoryEpisodeStep';
import type { DailyJourneyController } from './useDailyJourney';

export type JourneySessionProps = {
  controller: DailyJourneyController;
  /** Optional escape hatch back to the rest of the day. Never required to finish. */
  onExit?: () => void;
  /** Optional practice entry shown after a finished day. Must not reopen it. */
  morePractice?: { label: string; onSelect: () => void } | null;
};

/** One progress segment per real planned step — never a demo value. */
function segmentsOf(steps: PublicStep[], currentId: string | null): StepSegment[] {
  return steps.map((step) => ({
    id: step.id,
    state:
      step.status === 'completed'
        ? 'done'
        : step.status === 'skipped'
          ? 'skipped'
          : step.id === currentId
            ? 'active'
            : 'pending',
  }));
}

export function JourneySession({ controller, onExit, morePractice }: JourneySessionProps) {
  const { phase, feedback, step, progress, busy, help, voice, actions } = controller;
  const copy: AtelierCopy = {
    ...atelierCopy(controller.controlLanguage),
    ...journeyCopy(controller.controlLanguage),
  };
  const journey = controller.journey;
  const recovery = controller.recovery;

  const remaining = formatDuration(progress.remainingSeconds, controller.controlLanguage);

  // Draft persistence (WP-10). The accessors are stable callbacks, so the field
  // is not remounted and typing is not interrupted.
  const draftGet = recovery ? recovery.draftFor : null;
  const draftSet = recovery ? recovery.saveDraft : null;
  const draft = React.useMemo(
    () => (draftGet && draftSet ? { get: draftGet, set: draftSet } : undefined),
    [draftGet, draftSet],
  );

  const segments = journey ? segmentsOf(journey.steps, journey.current_step_id) : [];
  const caption =
    progress.total > 0
      ? `${stepOfLabel(copy, Math.min(progress.done + 1, progress.total), progress.total)}${
          remaining ? ` · ${remaining} ${copy.time_left}` : ''
        }`
      : undefined;

  return (
    <AtelierV2Root as="main" language={controller.controlLanguage} className="journey-shell">
      <div className="av2-screen">
        {/* The design's session header: close, then the progress rule. The
            streak slot the design puts on the right is deliberately empty. */}
        {journey && (
          <header className="av2-session__head">
            {onExit && (
              <IconAction label={copy.pause} onClick={onExit}>
                <CrossIcon size={16} />
              </IconAction>
            )}
            {segments.length > 0 ? (
              <StepProgress steps={segments} label={copy.progress_label} caption={caption} />
            ) : (
              <span className="av2-label">{copy.progress_none}</span>
            )}
          </header>
        )}

        <div className="av2-screen__body">
          <ConnectionNotice connection={recovery ? recovery.connection : null} copy={copy} />

          {journey && phase.kind === 'session' && (
            <p className="av2-label">
              {journey.scenario.location_name} · {journey.scenario.objective_native}
            </p>
          )}

          <JourneyPhaseView
            phase={phase}
            controller={controller}
            copy={copy}
            onExit={onExit}
            morePractice={morePractice}
          />

          {/* A paused journey shows its resume prompt alone, so the learner has
              exactly one action rather than a half-live step behind a notice. */}
          {phase.kind === 'session' && step && (
            <>
              {step.kind === 'scene' && (
                // Story-engine panels when the engine published them for this
                // journey; the plain scene prompt otherwise (WP-14E).
                <StoryEpisodeStep
                  journeyId={journey?.id ?? ''}
                  step={step}
                  copy={copy}
                  busy={busy}
                  onContinue={actions.continueJourney}
                  onExit={onExit}
                />
              )}
              {step.kind === 'recall' && (
                <RecallStepView
                  step={step}
                  copy={copy}
                  busy={busy}
                  feedback={feedback}
                  help={help}
                  onHelp={actions.requestHelp}
                  onSubmit={actions.submitAnswer}
                  onContinue={actions.continueJourney}
                  draft={draft}
                />
              )}
              {step.kind === 'respond' && (
                <RespondStepView
                  step={step}
                  copy={copy}
                  busy={busy}
                  feedback={feedback}
                  help={help}
                  voice={voice}
                  onHelp={actions.requestHelp}
                  onSubmit={actions.submitAnswer}
                  onContinue={actions.continueJourney}
                  onStartRecording={() => void actions.startRecording()}
                  onStopRecording={actions.stopRecording}
                  onResetVoice={actions.resetVoice}
                  draft={draft}
                />
              )}
              {step.kind === 'resolution' && (
                <ResolutionStepView
                  step={step}
                  copy={copy}
                  busy={busy}
                  onContinue={actions.continueJourney}
                />
              )}

              <JourneyFeedbackView
                feedback={feedback}
                copy={copy}
                onContinue={actions.continueJourney}
                onRetry={actions.retryLastAnswer}
                onDismiss={actions.clearFeedback}
              />

              {/* Third tier. Quiet by construction, so the step's own primary
                  stays the only primary in the composition. */}
              <div className="av2-session__secondary">
                <Action
                  tone="quiet"
                  inline
                  disabled={busy}
                  onClick={() => void actions.finish('early')}
                >
                  {copy.finish_early}
                </Action>
              </div>
            </>
          )}
        </div>
      </div>
    </AtelierV2Root>
  );
}

// ---------------------------------------------------------------------------
// Connection state — stated plainly, never dressed as a result
// ---------------------------------------------------------------------------

const CONNECTION_COPY: Record<ConnectionView['state'], keyof AtelierCopy | null> = {
  live: null,
  syncing: 'syncing',
  offline_cached: 'offline_cached',
  offline_empty: 'offline_empty',
  pending_sync: 'pending_sync',
};

/**
 * What the learner is actually looking at when it is not a live server answer.
 *
 * Deliberately a quiet `Notice` rather than the feedback band: it must never
 * read as a verdict or a finished day. It carries no tint, no tick and no
 * celebration — being offline is a fact about the connection, not about the
 * learner's work.
 */
export function ConnectionNotice({
  connection,
  copy,
}: {
  connection: ConnectionView | null;
  copy: AtelierCopy;
}) {
  if (!connection) return null;
  const key = CONNECTION_COPY[connection.state];
  // `live` and nothing stale is the ordinary case: say nothing at all.
  if (!key && !connection.stale) return null;

  return (
    <div className="journey-connection" data-state={connection.state}>
      <Notice tone="quiet" shape="story">
        <p>
          {key ? copy[key] : null}
          {connection.stale && (
            <>
              {key ? ' ' : null}
              {copy.stale_from_earlier_day}
            </>
          )}
        </p>
      </Notice>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Non-step phases
// ---------------------------------------------------------------------------

function JourneyPhaseView({
  phase,
  controller,
  copy,
  onExit,
  morePractice,
}: {
  phase: JourneyPhase;
  controller: DailyJourneyController;
  copy: AtelierCopy;
  onExit?: () => void;
  morePractice?: { label: string; onSelect: () => void } | null;
}) {
  const { actions, busy } = controller;

  switch (phase.kind) {
    case 'loading':
      return <StateBlock tone="loading" title={copy.loading} body={copy.preparing_body} />;

    case 'load_failed':
      return (
        <StateBlock
          tone="error"
          title={copy.error_title}
          body={copy.transport_error}
          action={{ label: copy.retry, onSelect: () => void actions.refresh() }}
        />
      );

    case 'preparing':
      return (
        <div data-state="preparing">
          <StateBlock
            tone="loading"
            title={copy.preparing_title}
            body={copy.preparing_body}
            action={{ label: copy.preparing_retry, onSelect: () => void actions.refresh() }}
          />
        </div>
      );

    case 'unavailable':
      return (
        <div data-state="unavailable">
          <StateBlock
            tone="error"
            title={copy.unavailable_title}
            body={copy.unavailable_body}
            action={
              phase.retryAllowed
                ? { label: copy.unavailable_retry, onSelect: () => void actions.retryGeneration() }
                : onExit
                  ? { label: copy.continue, onSelect: onExit }
                  : undefined
            }
          />
        </div>
      );

    /**
     * Every step is resolved and the server has not recorded the day as
     * finished — usually because the finishing request has not been made or was
     * refused. There is no step to render and no recap to read, so the screen
     * says exactly that and offers the one action that resolves it. It never
     * claims the day is done: only a `finished` journey may show the recap.
     */
    case 'awaiting_finish':
      return (
        <div data-state="awaiting_finish">
          <StateBlock
            tone="empty"
            title={copy.awaiting_finish_title}
            body={copy.awaiting_finish_body}
            action={{
              label: copy.awaiting_finish_action,
              tone: 'primary',
              onSelect: () => {
                if (!busy) void actions.finish('complete');
              },
            }}
          />
        </div>
      );

    case 'paused':
      return (
        <div data-state="paused">
          <StateBlock
            tone="empty"
            title={copy.paused_title}
            body={copy.paused_body}
            action={{
              label: copy.resume,
              tone: 'primary',
              onSelect: () => {
                if (!busy) void actions.resume();
              },
            }}
          />
        </div>
      );

    case 'finished':
      return (
        <JourneyRecapView
          phase={phase}
          controller={controller}
          onExit={onExit}
          morePractice={morePractice}
        />
      );

    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Completion recap — the server's evidence, and nothing invented
// ---------------------------------------------------------------------------

export function JourneyRecapView({
  phase,
  controller,
  onExit,
  morePractice,
}: {
  phase: Extract<JourneyPhase, { kind: 'finished' }>;
  controller: DailyJourneyController;
  onExit?: () => void;
  morePractice?: { label: string; onSelect: () => void } | null;
}) {
  const copy: AtelierCopy = {
    ...atelierCopy(controller.controlLanguage),
    ...journeyCopy(controller.controlLanguage),
  };
  const view = recapView(phase.recap);
  const partial = view?.partial ?? phase.journey.status === 'ended_early';
  const duration = formatDuration(view?.activeSeconds ?? null, controller.controlLanguage);

  return (
    <section className="journey-recap av2-stack" data-state={partial ? 'partial' : 'complete'}>
      <Surface tone={partial ? 'outline' : 'paper'} shape="hero" className="av2-recap__header">
        <p className="av2-label">{copy.today_eyebrow}</p>
        <h2 className="av2-headline">
          {partial ? copy.finished_partial_title : copy.finished_title}
        </h2>
        {partial && <p className="av2-body av2-body--lg">{copy.finished_partial_body}</p>}

        {/* `recap.active_seconds` is null by design until WP-11 measures it.
            Say so rather than printing an invented duration. */}
        <p className="av2-label" style={{ marginTop: 8 }}>
          {duration ? duration : copy.duration_not_measured}
        </p>
      </Surface>

      {view && view.practiced.length > 0 && (
        <Surface>
          <p className="av2-label">{copy.practiced}</p>
          <ul className="av2-recap__list">
            {view.practiced.map((item) => (
              <li key={`${item.target.kind}:${item.target.id}`}>
                <ShapeToken kind="reward" size="sm" />
                <span>
                  <span className="av2-fr" lang="fr">
                    {item.target.label_fr}
                  </span>
                  {item.target.label_native ? ` — ${item.target.label_native}` : ''}{' '}
                  <span className="av2-label" style={{ display: 'inline' }}>
                    · {copy[`evidence_${item.evidence_kind}` as const]}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </Surface>
      )}

      {/* Server-recorded capability evidence. Not a second headline: it is what
          the learner actually did, in the server's own words. */}
      {view && view.capabilities.length > 0 && (
        <Surface>
          <p className="av2-label">{copy.capability_shown}</p>
          <ul className="av2-recap__list">
            {view.capabilities.map((item, index) => (
              <li key={`${item.capability_key}-${index}`}>
                <ShapeToken kind="done" size="sm" />
                <span>
                  {item.context_native}{' '}
                  <span className="av2-label" style={{ display: 'inline' }}>
                    · {copy[`capability_state_${item.state}` as const]}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </Surface>
      )}

      {/* At most ONE headline. */}
      {view?.headline && (
        <Surface tone="blue">
          <p className="av2-label">{copy.next_focus}</p>
          <p className="av2-headline av2-headline--rule" lang="fr">
            {view.headline.labelFr}
          </p>
          <p className="av2-body av2-body--lg">{view.headline.reasonNative}</p>
        </Surface>
      )}

      {/* The callback is a character's line, so it is attributed rather than
          left as a bare French fragment with no speaker. */}
      {view?.storyCallbackFr && (
        <Surface>
          <p className="av2-label">{phase.journey.scenario.character_name}</p>
          <p className="av2-fr av2-headline av2-headline--rule" lang="fr">
            {view.storyCallbackFr}
          </p>
        </Surface>
      )}

      <div className="av2-recap__actions">
        {onExit && (
          <Action tone="primary" onClick={onExit}>
            {copy.continue}
          </Action>
        )}
        {morePractice && (
          <Action tone="secondary" onClick={morePractice.onSelect}>
            {morePractice.label || copy.more_practice}
          </Action>
        )}
      </div>
      {morePractice && <p className="av2-label">{copy.more_practice_note}</p>}
    </section>
  );
}

export default JourneySession;

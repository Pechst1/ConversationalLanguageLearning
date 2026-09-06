/**
 * The one connected daily-journey shell (WP-07 functional milestone).
 *
 * Scene, recall, response, resolution and completion all render inside this
 * single component, so finishing the daily loop needs no tab switch and no
 * second screen. It receives the `useDailyJourney` controller and renders it —
 * it issues no request itself.
 *
 * Layout rules that are load-bearing rather than decorative:
 *   * one prompt, one answer area, one primary action, in that order;
 *   * the primary action sits in normal flow directly under the answer, so a
 *     software keyboard or the fixed bottom navigation can never cover it;
 *   * the shell reserves the bottom-navigation height, so nothing is hidden
 *     behind it at 320px or at large text.
 */

import React from 'react';

import { Button } from '@/components/ui/Button';
import { ProgressBar } from '@/components/ui/ProgressBar';
import type { ConnectionView } from '@/lib/journey-recovery';

import { journeyCopy, type JourneyCopy } from './journey-copy';
import {
  formatDuration,
  recapView,
  type JourneyPhase,
} from './journey-state';
import {
  JourneyFeedbackView,
  RecallStepView,
  RespondStepView,
  ResolutionStepView,
  SceneStepView,
  StepStyles,
} from './JourneySteps';
import type { DailyJourneyController } from './useDailyJourney';

export type JourneySessionProps = {
  controller: DailyJourneyController;
  /** Optional escape hatch back to the rest of the day. Never required to finish. */
  onExit?: () => void;
  /** Optional practice entry shown after a finished day. Must not reopen it. */
  morePractice?: { label: string; onSelect: () => void } | null;
};

export function JourneySession({ controller, onExit, morePractice }: JourneySessionProps) {
  const { phase, feedback, step, progress, busy, help, voice, actions } = controller;
  const copy = journeyCopy(controller.controlLanguage);
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

  return (
    <main className="journey-shell">
      <ConnectionNotice connection={recovery ? recovery.connection : null} copy={copy} />

      {journey && (
        <header className="journey-head">
          <p className="journey-eyebrow">
            {copy.today_eyebrow} · {journey.scenario.location_name}
          </p>
          <h1 lang="fr">{journey.scenario.title_fr}</h1>
          <p className="journey-objective">
            <b>{copy.objective}:</b> {journey.scenario.objective_native}
          </p>
          {progress.total > 0 && (
            <div className="journey-progress">
              <ProgressBar
                value={progress.done}
                max={progress.total}
                label={copy.progress_label}
              />
              <p>
                {progress.done}/{progress.total}
                {remaining ? ` · ${remaining} ${copy.time_left}` : ''}
              </p>
            </div>
          )}
        </header>
      )}

      <div className="journey-body">
        <JourneyPhaseView
          phase={phase}
          controller={controller}
          onExit={onExit}
          morePractice={morePractice}
        />

        {/* A paused journey shows its resume prompt alone, so the learner has
            exactly one action rather than a half-live step behind a notice. */}
        {phase.kind === 'session' && step && (
          <>
            {step.kind === 'scene' && (
              <SceneStepView
                step={step}
                copy={copy}
                busy={busy}
                onContinue={actions.continueJourney}
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

            <div className="journey-secondary">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={busy}
                onClick={() => void actions.finish('early')}
              >
                {copy.finish_early}
              </Button>
              {onExit && (
                <Button type="button" variant="ghost" size="sm" onClick={onExit}>
                  {copy.pause}
                </Button>
              )}
            </div>
          </>
        )}
      </div>

      <StepStyles />
      <style jsx>{`
        .journey-shell {
          max-width: 720px;
          margin: 0 auto;
          padding: 16px 16px calc(24px + var(--phone-bottom-nav-space, 0px));
          display: grid;
          gap: 16px;
          min-width: 0;
        }
        .journey-head {
          display: grid;
          gap: 6px;
          min-width: 0;
        }
        .journey-eyebrow {
          margin: 0;
          font-size: 11px;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: var(--app-ink-3);
        }
        .journey-head h1 {
          margin: 0;
          font-size: 22px;
          line-height: 1.2;
          overflow-wrap: anywhere;
        }
        .journey-objective {
          margin: 0;
          font-size: 14px;
          line-height: 1.4;
          color: var(--app-ink-2);
        }
        .journey-progress {
          display: grid;
          gap: 4px;
          margin-top: 4px;
        }
        .journey-progress p {
          margin: 0;
          font-size: 12px;
          color: var(--app-ink-3);
        }
        .journey-body {
          display: grid;
          gap: 14px;
          min-width: 0;
        }
        .journey-secondary {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
      `}</style>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Connection state — stated plainly, never dressed as a result
// ---------------------------------------------------------------------------

const CONNECTION_COPY: Record<ConnectionView['state'], keyof JourneyCopy | null> = {
  live: null,
  syncing: 'syncing',
  offline_cached: 'offline_cached',
  offline_empty: 'offline_empty',
  pending_sync: 'pending_sync',
};

/**
 * What the learner is actually looking at when it is not a live server answer.
 *
 * Deliberately a plain line of text with `role="status"`: it must never read as
 * a verdict or a finished day. It carries no score, no tick, no celebration —
 * being offline is a fact about the connection, not about the learner's work.
 */
export function ConnectionNotice({
  connection,
  copy,
}: {
  connection: ConnectionView | null;
  copy: JourneyCopy;
}) {
  if (!connection) return null;
  const key = CONNECTION_COPY[connection.state];
  // `live` and nothing stale is the ordinary case: say nothing at all.
  if (!key && !connection.stale) return null;

  return (
    <p className="journey-connection" role="status" data-state={connection.state}>
      {key ? copy[key] : null}
      {connection.stale && (
        <>
          {key ? ' ' : null}
          {copy.stale_from_earlier_day}
        </>
      )}
      <style jsx>{`
        .journey-connection {
          margin: 0;
          padding: 8px 10px;
          border: 1px dashed var(--app-ink);
          background: var(--app-paper-2);
          color: var(--app-ink-2);
          font-size: 13px;
          line-height: 1.4;
        }
      `}</style>
    </p>
  );
}

// ---------------------------------------------------------------------------
// Non-step phases
// ---------------------------------------------------------------------------

function JourneyPhaseView({
  phase,
  controller,
  onExit,
  morePractice,
}: {
  phase: JourneyPhase;
  controller: DailyJourneyController;
  onExit?: () => void;
  morePractice?: { label: string; onSelect: () => void } | null;
}) {
  const copy = journeyCopy(controller.controlLanguage);
  const { actions, busy } = controller;

  switch (phase.kind) {
    case 'loading':
      return (
        <p className="journey-notice" role="status">
          {copy.preparing_body}
          <StepStyles />
        </p>
      );

    case 'load_failed':
      return (
        <div className="journey-notice" role="alert">
          <p>{copy.transport_error}</p>
          <Button type="button" size="sm" variant="outline" onClick={() => void actions.refresh()}>
            {copy.retry}
          </Button>
          <StepStyles />
        </div>
      );

    case 'preparing':
      return (
        <div className="journey-notice" role="status" data-state="preparing">
          <p>
            <b>{copy.preparing_title}</b>
          </p>
          <p>{copy.preparing_body}</p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => void actions.refresh()}
          >
            {copy.preparing_retry}
          </Button>
          <StepStyles />
        </div>
      );

    case 'unavailable':
      return (
        <div className="journey-notice" role="alert" data-state="unavailable">
          <p>
            <b>{copy.unavailable_title}</b>
          </p>
          <p>{copy.unavailable_body}</p>
          {phase.retryAllowed && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => void actions.retryGeneration()}
            >
              {copy.unavailable_retry}
            </Button>
          )}
          {onExit && (
            <Button type="button" size="sm" variant="ghost" onClick={onExit}>
              {copy.continue}
            </Button>
          )}
          <StepStyles />
        </div>
      );

    case 'paused':
      return (
        <div className="journey-notice" role="status" data-state="paused">
          <p>
            <b>{copy.paused_title}</b>
          </p>
          <p>{copy.paused_body}</p>
          <Button
            type="button"
            size="sm"
            disabled={busy}
            onClick={() => void actions.resume()}
          >
            {copy.resume}
          </Button>
          <StepStyles />
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
  const copy = journeyCopy(controller.controlLanguage);
  const view = recapView(phase.recap);
  const partial = view?.partial ?? phase.journey.status === 'ended_early';
  const duration = formatDuration(view?.activeSeconds ?? null, controller.controlLanguage);

  return (
    <section className="journey-recap" data-state={partial ? 'partial' : 'complete'}>
      <h2>{partial ? copy.finished_partial_title : copy.finished_title}</h2>
      {partial && <p className="journey-recap-note">{copy.finished_partial_body}</p>}

      {/* `recap.active_seconds` is null by design until WP-11 measures it. Say
          so rather than printing an invented duration. */}
      <p className="journey-recap-note">
        {duration ? `${duration}` : copy.duration_not_measured}
      </p>

      {view && view.practiced.length > 0 && (
        <div className="journey-recap-block">
          <h3>{copy.practiced}</h3>
          <ul>
            {view.practiced.map((item) => (
              <li key={`${item.target.kind}:${item.target.id}`}>
                <span lang="fr">{item.target.label_fr}</span>
                {item.target.label_native ? ` — ${item.target.label_native}` : ''}
                <small> · {copy[`evidence_${item.evidence_kind}` as const]}</small>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Server-recorded capability evidence. Not a second headline: it is what
          the learner actually did, in the server's own words. */}
      {view && view.capabilities.length > 0 && (
        <div className="journey-recap-block">
          <h3>{copy.capability_shown}</h3>
          <ul>
            {view.capabilities.map((item, index) => (
              <li key={`${item.capability_key}-${index}`}>
                {item.context_native}
                <small> · {copy[`capability_state_${item.state}` as const]}</small>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* At most ONE headline. */}
      {view?.headline && (
        <div className="journey-recap-block">
          <h3>{copy.next_focus}</h3>
          <p>
            <span lang="fr">{view.headline.labelFr}</span> — {view.headline.reasonNative}
          </p>
        </div>
      )}

      {/* The callback is a character's line, so it is attributed rather than
          left as a bare French fragment with no speaker. */}
      {view?.storyCallbackFr && (
        <p className="journey-recap-note">
          {phase.journey.scenario.character_name} ·{' '}
          <span lang="fr">{view.storyCallbackFr}</span>
        </p>
      )}

      <div className="journey-recap-actions">
        {onExit && (
          <Button type="button" onClick={onExit}>
            {copy.continue}
          </Button>
        )}
        {morePractice && (
          <Button type="button" variant="outline" onClick={morePractice.onSelect}>
            {morePractice.label || copy.more_practice}
          </Button>
        )}
      </div>
      {morePractice && <p className="journey-recap-note">{copy.more_practice_note}</p>}

      <style jsx>{`
        .journey-recap {
          border: 1px solid var(--app-ink);
          background: var(--app-sheet);
          padding: 16px;
          display: grid;
          gap: 10px;
          min-width: 0;
        }
        .journey-recap[data-state='partial'] {
          border-left-width: 5px;
          border-left-style: dashed;
        }
        .journey-recap h2 {
          margin: 0;
          font-size: 20px;
          line-height: 1.2;
        }
        .journey-recap h3 {
          margin: 0 0 4px;
          font-size: 11px;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--app-ink-3);
        }
        .journey-recap-note {
          margin: 0;
          font-size: 13px;
          line-height: 1.4;
          color: var(--app-ink-2);
        }
        .journey-recap-block ul {
          margin: 0;
          padding-left: 18px;
          display: grid;
          gap: 4px;
          font-size: 14px;
          line-height: 1.4;
        }
        .journey-recap-block p {
          margin: 0;
          font-size: 14px;
          line-height: 1.4;
        }
        .journey-recap-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
      `}</style>
    </section>
  );
}

export default JourneySession;

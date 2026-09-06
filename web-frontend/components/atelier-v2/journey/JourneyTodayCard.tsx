/**
 * The Today entry point for the daily journey (WP-07 functional milestone).
 *
 * One recommendation, one clear start/resume action, and — when the server says
 * one exists — a **separately labelled** resume for the old Atelier session.
 * The two are never merged: a V2 journey must not silently convert, replace or
 * complete a legacy session (CONTRACT-FREEZE, "Frontend recommendation
 * precedence").
 *
 * Presentation only. Every callback comes from the caller.
 */

import React from 'react';

import { Button } from '@/components/ui/Button';

import { journeyCopy } from './journey-copy';
import { formatDuration, type JourneyPhase } from './journey-state';
import type { DailyJourneyController } from './useDailyJourney';

export type JourneyTodayCardProps = {
  controller: DailyJourneyController;
  /** Open the connected session shell. */
  onOpen: () => void;
  /** Open the legacy Atelier session at its own href. */
  onOpenLegacy?: (href: string) => void;
};

export function JourneyTodayCard({
  controller,
  onOpen,
  onOpenLegacy,
}: JourneyTodayCardProps) {
  const copy = journeyCopy(controller.controlLanguage);
  const { phase, busy, actions, legacyResume } = controller;

  if (phase.kind === 'disabled' || phase.kind === 'loading') return null;

  return (
    <div className="journey-today">
      <JourneyTodayBody
        phase={phase}
        copy={copy}
        busy={busy}
        onOpen={onOpen}
        onStart={() => {
          void actions.start().then(onOpen);
        }}
        onResume={() => {
          void actions.resume().then(onOpen);
        }}
        onRefresh={() => void actions.refresh()}
        onRetryGeneration={() => void actions.retryGeneration()}
        controlLanguage={controller.controlLanguage}
      />

      {legacyResume && (
        <section className="journey-legacy" aria-label={copy.legacy_resume_title}>
          <p className="journey-today-eyebrow">{copy.legacy_resume_title}</p>
          <p className="journey-today-body">{copy.legacy_resume_body}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onOpenLegacy?.(legacyResume.href)}
          >
            {copy.legacy_resume_action}
          </Button>
        </section>
      )}

      <TodayStyles />
    </div>
  );
}

function JourneyTodayBody({
  phase,
  copy,
  busy,
  controlLanguage,
  onOpen,
  onStart,
  onResume,
  onRefresh,
  onRetryGeneration,
}: {
  phase: JourneyPhase;
  copy: ReturnType<typeof journeyCopy>;
  busy: boolean;
  controlLanguage: DailyJourneyController['controlLanguage'];
  onOpen: () => void;
  onStart: () => void;
  onResume: () => void;
  onRefresh: () => void;
  onRetryGeneration: () => void;
}) {
  switch (phase.kind) {
    case 'offer': {
      const scenario = phase.scenario;
      if (!scenario) {
        return (
          <Card eyebrow={copy.today_eyebrow} title={copy.nothing_offered}>
            <Button type="button" variant="outline" size="sm" onClick={onRefresh}>
              {copy.retry}
            </Button>
          </Card>
        );
      }
      const estimate = formatDuration(scenario.estimated_seconds, controlLanguage);
      return (
        <Card
          eyebrow={`${copy.today_eyebrow} · ${scenario.location_name}`}
          title={scenario.title_fr}
          lang="fr"
        >
          <p className="journey-today-body">{scenario.objective_native}</p>
          {estimate && <p className="journey-today-eyebrow">{estimate}</p>}
          <Button type="button" disabled={busy} loading={busy} onClick={onStart}>
            {copy.start}
          </Button>
        </Card>
      );
    }

    case 'session':
    case 'paused': {
      const scenario = phase.journey.scenario;
      return (
        <Card
          eyebrow={`${copy.today_eyebrow} · ${scenario.location_name}`}
          title={scenario.title_fr}
          lang="fr"
        >
          <p className="journey-today-body">{scenario.objective_native}</p>
          <Button
            type="button"
            disabled={busy}
            onClick={phase.kind === 'paused' ? onResume : onOpen}
          >
            {copy.resume}
          </Button>
        </Card>
      );
    }

    case 'preparing':
      return (
        <Card eyebrow={copy.today_eyebrow} title={copy.preparing_title}>
          <p className="journey-today-body">{copy.preparing_body}</p>
          <Button type="button" variant="outline" size="sm" disabled={busy} onClick={onRefresh}>
            {copy.preparing_retry}
          </Button>
        </Card>
      );

    case 'unavailable':
      return (
        <Card eyebrow={copy.today_eyebrow} title={copy.unavailable_title}>
          <p className="journey-today-body">{copy.unavailable_body}</p>
          {phase.retryAllowed && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={onRetryGeneration}
            >
              {copy.unavailable_retry}
            </Button>
          )}
        </Card>
      );

    case 'finished':
      // Re-entry is a READ. It must not restart the day or touch a streak.
      return (
        <Card eyebrow={copy.today_eyebrow} title={copy.done_today}>
          <Button type="button" variant="outline" size="sm" onClick={onOpen}>
            {copy.continue}
          </Button>
        </Card>
      );

    case 'load_failed':
      return (
        <Card eyebrow={copy.today_eyebrow} title={copy.transport_error}>
          <Button type="button" variant="outline" size="sm" onClick={onRefresh}>
            {copy.retry}
          </Button>
        </Card>
      );

    default:
      return null;
  }
}

function Card({
  eyebrow,
  title,
  lang,
  children,
}: {
  eyebrow: string;
  title: string;
  lang?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="journey-today-card">
      <p className="journey-today-eyebrow">{eyebrow}</p>
      <h2 lang={lang}>{title}</h2>
      {children}
    </section>
  );
}

/**
 * One namespaced style block for the whole card. Every selector is prefixed
 * `journey-`, so nothing here can reach a legacy page.
 */
function TodayStyles() {
  return (
    <style jsx global>{`
      .journey-today {
        display: grid;
        gap: 12px;
        min-width: 0;
      }
      .journey-legacy {
        border: 1px dashed var(--app-ink);
        background: var(--app-paper-2);
        padding: 12px 14px;
        display: grid;
        gap: 6px;
        justify-items: start;
      }
      .journey-today-card {
        border: 1px solid var(--app-ink);
        background: var(--app-sheet);
        padding: 14px 16px;
        display: grid;
        gap: 8px;
        justify-items: start;
        min-width: 0;
      }
      .journey-today-card h2 {
        margin: 0;
        font-size: 19px;
        line-height: 1.2;
        overflow-wrap: anywhere;
      }
      .journey-today-eyebrow {
        margin: 0;
        font-size: 11px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--app-ink-3);
      }
      .journey-today-body {
        margin: 0;
        font-size: 13px;
        line-height: 1.4;
        color: var(--app-ink-2);
      }
      /* An effective 44px touch target on every control of the day's entry,
         and a label that wraps instead of widening the card past the
         viewport at 320px with large text. */
      .journey-today button {
        height: auto;
        min-height: 44px;
        min-width: 0;
        max-width: 100%;
        white-space: normal;
        overflow-wrap: anywhere;
      }
    `}</style>
  );
}

export default JourneyTodayCard;

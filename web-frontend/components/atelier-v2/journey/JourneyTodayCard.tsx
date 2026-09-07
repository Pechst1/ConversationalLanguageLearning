/**
 * The Today entry point for the daily journey — WP-07 **visual** milestone.
 *
 * One recommendation, one clear start/resume action, and — when the server says
 * one exists — a **separately labelled** resume for the old Atelier session.
 * The two are never merged: a V2 journey must not silently convert, replace or
 * complete a legacy session (CONTRACT-FREEZE, "Frontend recommendation
 * precedence").
 *
 * ---------------------------------------------------------------------------
 * Design mapping — `Atelier App.dc.html`, home direction 1a "La Une, allégée"
 * ---------------------------------------------------------------------------
 * This is the design's episode card: a 22px-radius surface, 16:9 artwork above
 * a blue story label, a Garamond-italic headline, a character byline, and one
 * red 3D-press action. The design's card is followed by three tiles (Séance,
 * Lexique, Errata) and a masthead — those belong to the home composition the
 * frontend lead owns, not to this card.
 *
 * Deliberately NOT taken: the design's masthead carries "12 jours" and
 * "Édition Nº 12". Neither is in the contract, and CONTRACTS forbids inventing
 * a streak, so this card carries neither. Recorded in
 * FRONTEND-ENGINE-HANDOFF §4.
 *
 * Presentation only. Every callback comes from the caller.
 */

import React from 'react';

import {
  Action,
  Artwork,
  AtelierV2Root,
  Byline,
  ShapeToken,
  Surface,
} from '@/components/atelier-v2/ui';
import { atelierCopy, type AtelierCopy } from '@/lib/atelier-v2-copy';

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
  const copy: AtelierCopy = {
    ...atelierCopy(controller.controlLanguage),
    ...journeyCopy(controller.controlLanguage),
  };
  const { phase, busy, actions, legacyResume } = controller;

  if (phase.kind === 'disabled' || phase.kind === 'loading') return null;

  return (
    <AtelierV2Root language={controller.controlLanguage} className="journey-today">
      <div className="av2-stack">
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

        {/* The legacy session keeps its own outlined surface and its own
            second-tier action, so it can never be mistaken for today's scene. */}
        {legacyResume && (
          <Surface
            as="section"
            tone="outline"
            className="journey-legacy"
            aria-label={copy.legacy_resume_title}
          >
            <p className="av2-label">{copy.legacy_resume_title}</p>
            <p className="av2-body">{copy.legacy_resume_body}</p>
            <div className="av2-recap__actions">
              <Action
                tone="secondary"
                inline
                onClick={() => onOpenLegacy?.(legacyResume.href)}
              >
                {copy.legacy_resume_action}
              </Action>
            </div>
          </Surface>
        )}
      </div>
    </AtelierV2Root>
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
  copy: AtelierCopy;
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
          <Card copy={copy} eyebrow={copy.today_eyebrow} title={copy.nothing_offered}>
            <Action tone="secondary" inline onClick={onRefresh}>
              {copy.retry}
            </Action>
          </Card>
        );
      }
      const estimate = formatDuration(scenario.estimated_seconds, controlLanguage);
      return (
        <Card
          copy={copy}
          eyebrow={`${copy.today_eyebrow} · ${scenario.location_name}`}
          title={scenario.title_fr}
          lang="fr"
          imageUrl={scenario.image_url}
          imageAlt={scenario.objective_native}
          byline={
            scenario.character_name ? (
              <Byline
                name={scenario.character_name}
                meta={estimate ? estimate : undefined}
              />
            ) : null
          }
        >
          <p className="av2-body av2-body--lg">{scenario.objective_native}</p>
          {/* An estimate is not a countdown. It is the plan's own number, and
              it is absent rather than guessed when the plan has none. */}
          {estimate && !scenario.character_name && (
            <p className="av2-label">{estimate}</p>
          )}
          <Action tone="primary" pending={busy} pendingLabel={copy.sending} onClick={onStart}>
            {copy.start}
          </Action>
        </Card>
      );
    }

    case 'session':
    case 'paused': {
      const scenario = phase.journey.scenario;
      return (
        <Card
          copy={copy}
          eyebrow={`${copy.today_eyebrow} · ${scenario.location_name}`}
          title={scenario.title_fr}
          lang="fr"
          imageUrl={scenario.image_url}
          imageAlt={scenario.objective_native}
          byline={
            scenario.character_name ? <Byline name={scenario.character_name} /> : null
          }
        >
          <p className="av2-body av2-body--lg">{scenario.objective_native}</p>
          <Action
            tone="primary"
            disabled={busy}
            onClick={phase.kind === 'paused' ? onResume : onOpen}
          >
            {copy.resume}
          </Action>
        </Card>
      );
    }

    /**
     * Every step is done and the day is not recorded as finished. Offering
     * "Continue today" here would promise a scene that has nothing left to
     * answer, so the entry says what is actually left: finishing it. The card
     * opens the session, where the finishing action lives.
     */
    case 'awaiting_finish': {
      const scenario = phase.journey.scenario;
      return (
        <Card
          copy={copy}
          eyebrow={`${copy.today_eyebrow} · ${scenario.location_name}`}
          title={scenario.title_fr}
          lang="fr"
          imageUrl={scenario.image_url}
          imageAlt={scenario.objective_native}
          byline={scenario.character_name ? <Byline name={scenario.character_name} /> : null}
        >
          <p className="av2-body av2-body--lg">{copy.awaiting_finish_body}</p>
          <Action tone="primary" disabled={busy} onClick={onOpen}>
            {copy.awaiting_finish_action}
          </Action>
        </Card>
      );
    }

    case 'preparing':
      return (
        <Card copy={copy} eyebrow={copy.today_eyebrow} title={copy.preparing_title}>
          <p className="av2-body av2-body--lg">{copy.preparing_body}</p>
          <Action tone="secondary" inline disabled={busy} onClick={onRefresh}>
            {copy.preparing_retry}
          </Action>
        </Card>
      );

    case 'unavailable':
      return (
        <Card copy={copy} eyebrow={copy.today_eyebrow} title={copy.unavailable_title}>
          <p className="av2-body av2-body--lg">{copy.unavailable_body}</p>
          {phase.retryAllowed && (
            <Action tone="secondary" inline disabled={busy} onClick={onRetryGeneration}>
              {copy.unavailable_retry}
            </Action>
          )}
        </Card>
      );

    case 'finished':
      // Re-entry is a READ. It must not restart the day or touch a streak.
      return (
        <Card copy={copy} eyebrow={copy.today_eyebrow} title={copy.done_today} done>
          <Action tone="secondary" inline onClick={onOpen}>
            {copy.continue}
          </Action>
        </Card>
      );

    case 'load_failed':
      return (
        <Card copy={copy} eyebrow={copy.today_eyebrow} title={copy.transport_error}>
          <Action tone="secondary" inline onClick={onRefresh}>
            {copy.retry}
          </Action>
        </Card>
      );

    default:
      return null;
  }
}

function Card({
  copy,
  eyebrow,
  title,
  lang,
  imageUrl,
  imageAlt,
  byline,
  done,
  children,
}: {
  copy: AtelierCopy;
  eyebrow: string;
  title: string;
  lang?: string;
  imageUrl?: string | null;
  imageAlt?: string;
  byline?: React.ReactNode;
  done?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Surface as="section" shape="episode" className="journey-today-card">
      {imageUrl && (
        <Artwork
          url={imageUrl}
          alt={imageAlt ?? ''}
          fallbackLabel={copy.artwork_unavailable}
        />
      )}
      <div className="journey-today-card__body av2-stack">
        <p className="av2-label av2-label--story">
          {done && <ShapeToken kind="done" size="sm" />} {eyebrow}
        </p>
        <h2 className="av2-headline av2-headline--title" lang={lang}>
          {title}
        </h2>
        {byline}
        {children}
      </div>
    </Surface>
  );
}

export default JourneyTodayCard;

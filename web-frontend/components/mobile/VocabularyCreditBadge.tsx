import React from 'react';
import { cn } from '@/lib/utils';

type VocabularyCreditTone = 'positive' | 'repair' | 'seen';
type VocabularyCreditLabelMode = 'target' | 'word';

export interface VocabularyCreditBadgeProps extends React.HTMLAttributes<HTMLElement> {
  correction?: Record<string, any> | null;
  compact?: boolean;
  labelMode?: VocabularyCreditLabelMode;
  labelPrefix?: React.ReactNode;
}

function compactCreditText(value: unknown, maxLength = 44) {
  const text = String(value || '').trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1).trim()}...`;
}

function vocabularyEventsFromCorrection(correction?: Record<string, any> | null) {
  if (!correction) return [];
  const rawEvents = [
    ...(Array.isArray(correction.vocabulary_events) ? correction.vocabulary_events : []),
    ...(Array.isArray(correction.vocabulary_links) ? correction.vocabulary_links : []),
    ...(Array.isArray(correction.vocabulary_credit?.events) ? correction.vocabulary_credit.events : []),
  ].filter((event: any) => event && typeof event === 'object');
  const seen = new Set<string>();
  return rawEvents.filter((event: any) => {
    const key = `${event.word_id || event.target || event.learner_text || 'event'}:${event.event_type || 'credit'}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function vocabularyEventLabel(event: Record<string, any>) {
  return compactCreditText(
    event.word || event.target || event.learner_text || (event.word_id ? `word ${event.word_id}` : 'target word')
  );
}

function vocabularyCreditSummary(
  correction: Record<string, any> | null | undefined,
  labelMode: VocabularyCreditLabelMode
): { label: string; labels: string[]; tone: VocabularyCreditTone } | null {
  const events = vocabularyEventsFromCorrection(correction);
  const rawSummary = correction?.vocabulary_credit?.summary || correction?.vocabulary_credit || {};
  const produced = events.filter((event: any) => event.event_type === 'produced_correct').length
    || Number(rawSummary.produced_correct || rawSummary.used_correctly || 0);
  const missed = events.filter((event: any) => ['missed_target', 'produced_incorrect'].includes(String(event.event_type))).length
    || Number(rawSummary.missed_target || rawSummary.produced_incorrect || rawSummary.used_incorrectly || 0);
  const seen = events.filter((event: any) => event.event_type === 'seen_context').length
    || Number(rawSummary.seen_context || rawSummary.seen || 0);
  if (!events.length && !produced && !missed && !seen) return null;

  const count = produced || missed || seen || events.length;
  const plural = count === 1 ? '' : 's';
  const label = labelMode === 'word'
    ? produced
      ? `${produced} word${plural} used`
      : missed
        ? `${missed} word${plural} still missing`
        : `${count} word${plural} seen`
    : produced
      ? `${produced} vocabulary target${plural} used`
      : missed
        ? `${missed} vocabulary target${plural} missing`
        : `${count} word${plural} seen`;

  return {
    label,
    labels: events.map(vocabularyEventLabel).filter(Boolean).slice(0, 2),
    tone: missed ? 'repair' : produced ? 'positive' : 'seen',
  };
}

const VocabularyCreditBadge = React.forwardRef<HTMLElement, VocabularyCreditBadgeProps>(
  (
    {
      correction,
      compact = false,
      labelMode = 'target',
      labelPrefix,
      className,
      ...props
    },
    ref
  ) => {
    const summary = vocabularyCreditSummary(correction, labelMode);
    if (!summary) return null;

    return (
      <small
        ref={ref as React.Ref<HTMLElement>}
        className={cn('vocabulary-credit-badge', summary.tone, compact && 'compact', className)}
        {...props}
      >
        <strong>{labelPrefix}{summary.label}</strong>
        {summary.labels.length > 0 && <span>{summary.labels.join(' · ')}</span>}
        <style jsx>{`
          .vocabulary-credit-badge {
            --credit-paper: var(--app-paper, var(--paper, #f1ece1));
            --credit-paper-2: var(--app-paper-2, var(--paper-2, #e8e0cf));
            --credit-ink: var(--app-ink, var(--ink, #14110d));
            --credit-blue: var(--app-blue, var(--blue, #1d3a8a));
            --credit-red: var(--app-red, var(--red, #d8321a));
            --credit-yellow: var(--app-yellow, var(--yellow, #f3c318));
            --credit-green: var(--app-green, var(--green, #2e7d32));
            display: grid;
            gap: 3px;
            width: fit-content;
            max-width: 100%;
            margin-top: var(--credit-offset, 7px);
            border: 1px solid var(--credit-ink);
            border-left: 4px solid var(--credit-blue);
            background: var(--credit-paper-2);
            padding: 7px 9px;
            color: var(--credit-ink);
            font-size: 11px;
            font-style: normal;
            line-height: 1.2;
          }
          .vocabulary-credit-badge.compact {
            border-color: color-mix(in srgb, currentColor 45%, transparent);
            border-left-color: var(--credit-yellow);
            background: color-mix(in srgb, var(--credit-paper) 35%, transparent);
            color: inherit;
            font-size: 10px;
          }
          .vocabulary-credit-badge.positive {
            border-left-color: var(--credit-green);
          }
          .vocabulary-credit-badge.repair {
            border-left-color: var(--credit-red);
            background: color-mix(in srgb, var(--credit-red) 10%, var(--credit-paper));
          }
          .vocabulary-credit-badge strong {
            font-size: 11px;
            line-height: 1.15;
            text-transform: uppercase;
            letter-spacing: .04em;
          }
          .vocabulary-credit-badge span {
            overflow-wrap: anywhere;
            color: inherit;
            opacity: .78;
          }
        `}</style>
      </small>
    );
  }
);

VocabularyCreditBadge.displayName = 'VocabularyCreditBadge';

export { VocabularyCreditBadge };

/**
 * The repair card («Reprise de langue») on the Atelier V2 sheet.
 *
 * Opened from «Retravailler» on the journey summary and from «Plus de
 * pratique» → the errata queue (`/atelier?mode=practice&queue=errata`). Until
 * 2026-09-19 it was the last legacy overlay on the Séance route: uppercase
 * mono kickers, a 2px ink slab, a red uppercase button. It now uses the same
 * bottom sheet, field, verdict band and pill actions as every journey step.
 *
 * WP-82: the chrome follows the one language rule (`errata-copy.ts`) — the
 * learner's language up to A2, French from B1. The prompt and the learner's
 * own sentence are content and stay French; the stored erratum halves keep
 * whatever language the corrector filed them in.
 */

import React from 'react';

import {
  Action,
  AtelierV2Root,
  BottomSheet,
  CheckIcon,
  Correction,
  FeedbackBand,
  Notice,
  SendIcon,
  TextAnswer,
} from '@/components/atelier-v2/ui';
import { useChromeLanguage } from '@/lib/learner-language';
import type { AtelierErrataAttemptResult, AtelierErrataReviewTask } from '@/services/api';

import { errataCopy } from './errata-copy';

/** Backticks in a stored explanation become guillemets: the card prints it verbatim. */
export function printableWhy(text?: string | null): string {
  return String(text || '').replace(/`([^`]+)`/g, '« $1 »');
}

export type ErrataReviewSheetProps = {
  task: AtelierErrataReviewTask;
  answer: string;
  setAnswer: (value: string) => void;
  result: AtelierErrataAttemptResult | null;
  submitting: boolean;
  onSubmit: () => void;
  onClose: () => void;
};

export function ErrataReviewSheet({
  task,
  answer,
  setAnswer,
  result,
  submitting,
  onSubmit,
  onClose,
}: ErrataReviewSheetProps) {
  const language = useChromeLanguage();
  const COPY = errataCopy(language);
  const eyebrow = [task.source_label || 'Atelier', task.review_mode_label]
    .filter(Boolean)
    .join(' · ');
  const repaired = Boolean(result?.is_correct);
  const why = printableWhy(task.why_wrong);
  const hint = printableWhy(task.repair_hint);

  return (
    <AtelierV2Root as="div" language={language} className="errata-review-sheet">
      <BottomSheet open title={task.display_label} eyebrow={eyebrow} onClose={onClose}>
        <div className="av2-stack">
          <div>
            <p className="av2-label">{COPY.task}</p>
            <p className="av2-headline av2-headline--rule" lang="fr" style={{ margin: '4px 0 6px' }}>
              {task.prompt}
            </p>
            <p className="av2-body">{task.instruction}</p>
          </div>

          {task.learner_text && (
            <Notice tone="quiet" shape="action">
              <p className="av2-label" style={{ margin: 0 }}>{COPY.memorised}</p>
              <p className="av2-body av2-body--lg" lang="fr" style={{ margin: '4px 0 0' }}>
                <s>{task.learner_text}</s>
              </p>
            </Notice>
          )}

          {(why || hint) && (
            <div className="av2-body">
              {why && (
                <p style={{ margin: 0 }}>
                  <strong>{COPY.why}</strong> {why}
                </p>
              )}
              {hint && (
                <p style={{ margin: why ? '6px 0 0' : 0 }}>
                  <strong>{COPY.hint}</strong> {hint}
                </p>
              )}
            </div>
          )}

          <TextAnswer
            label={COPY.answer}
            value={answer}
            placeholder={task.placeholder}
            rows={3}
            disabled={submitting || repaired}
            onChange={setAnswer}
          />

          {result && (
            <FeedbackBand
              tone={result.is_correct ? 'correct' : 'wrong'}
              title={result.is_correct ? COPY.repaired : COPY.not_yet}
              detail={printableWhy(result.feedback)}
            >
              {!result.is_correct && result.target_answer && (
                <Correction
                  label={COPY.target}
                  spanFr={result.answer_text || answer}
                  correctedFr={result.target_answer}
                />
              )}
            </FeedbackBand>
          )}

          <div className="av2-stack" style={{ gap: 10 }}>
            {!repaired && (
              <Action
                tone="primary"
                pending={submitting}
                pendingLabel={COPY.sending}
                disabled={!answer.trim()}
                iconAfter={<SendIcon size={16} />}
                onClick={onSubmit}
              >
                {COPY.send}
              </Action>
            )}
            {repaired && (
              <Action tone="done" iconAfter={<CheckIcon size={16} />} onClick={onClose}>
                {COPY.done}
              </Action>
            )}
            <Action tone="quiet" onClick={onClose}>
              {COPY.close}
            </Action>
          </div>
        </div>
      </BottomSheet>
    </AtelierV2Root>
  );
}

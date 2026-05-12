import React from 'react';
import type { LearningMomentResult } from '@/hooks/useLearningSession';

type Props = {
  result?: LearningMomentResult | null;
  onDismiss?: () => void;
};

export default function MomentResultInline({ result, onDismiss }: Props) {
  if (!result) {
    return null;
  }

  const tone =
    result.isCorrect === true
      ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
      : result.isCorrect === false
        ? 'border-amber-200 bg-amber-50 text-amber-900'
        : 'border-stone-200 bg-stone-50 text-stone-800';

  return (
    <div className={`rounded-2xl border px-4 py-3 text-sm ${tone}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="font-medium">{result.feedbackSummary}</div>
          {result.nextStepHint ? (
            <div className="whitespace-pre-line text-xs text-stone-600">{result.nextStepHint}</div>
          ) : null}
        </div>
        {onDismiss ? (
          <button
            type="button"
            onClick={onDismiss}
            className="text-xs font-medium uppercase tracking-[0.14em] text-stone-400 transition-colors hover:text-stone-700"
          >
            Dismiss
          </button>
        ) : null}
      </div>
    </div>
  );
}

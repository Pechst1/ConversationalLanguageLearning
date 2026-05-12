import React from 'react';
import type {
  SessionErrorFeedback,
  SessionWordFeedback,
} from '@/hooks/useLearningSession';

type Props = {
  xpAwarded?: number | null;
  comboCount?: number | null;
  errorFeedback?: SessionErrorFeedback | null;
  wordFeedback?: SessionWordFeedback[] | null;
  onDismiss?: () => void;
};

const formatWordList = (items: SessionWordFeedback[]) => {
  return items.map((item) => item.word).join(', ');
};

export default function SessionTurnFeedback({
  xpAwarded,
  comboCount,
  errorFeedback,
  wordFeedback,
  onDismiss,
}: Props) {
  const hasXp = typeof xpAwarded === 'number' && xpAwarded > 0;
  const hasCombo = typeof comboCount === 'number' && comboCount > 1;
  const usedWords = (wordFeedback || []).filter((item) => item.wasUsed);
  const grammarFeedback =
    typeof errorFeedback?.metadata?.grammar_feedback === 'string'
      ? errorFeedback.metadata.grammar_feedback
      : null;
  const deckWordsUsed =
    typeof errorFeedback?.metadata?.deck_words_used === 'number'
      ? errorFeedback.metadata.deck_words_used
      : null;
  const correctionItems = (errorFeedback?.errors || []).filter(
    (item) => item.suggestion && item.suggestion !== item.span,
  );
  const hasFeedback =
    hasXp ||
    hasCombo ||
    usedWords.length > 0 ||
    Boolean(grammarFeedback) ||
    Boolean(deckWordsUsed) ||
    correctionItems.length > 0 ||
    Boolean(errorFeedback?.summary);

  if (!hasFeedback) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-stone-200 bg-stone-50/90 px-4 py-3 text-sm text-stone-700">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-medium uppercase tracking-[0.16em] text-stone-500">
            {hasXp ? (
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-emerald-700">
                +{xpAwarded} xp
              </span>
            ) : null}
            {hasCombo ? (
              <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-amber-700">
                {comboCount} word combo
              </span>
            ) : null}
            {usedWords.length > 0 ? (
              <span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-slate-600">
                {usedWords.length} focus word{usedWords.length === 1 ? '' : 's'} used
              </span>
            ) : null}
            {deckWordsUsed ? (
              <span className="rounded-full border border-sky-200 bg-sky-50 px-2 py-1 text-sky-700">
                {deckWordsUsed} words from Franzoesisch 5000 advanced
              </span>
            ) : null}
          </div>

          {errorFeedback?.summary ? (
            <p className="font-medium text-stone-900">{errorFeedback.summary}</p>
          ) : null}

          {grammarFeedback ? (
            <p className="text-stone-600">{grammarFeedback}</p>
          ) : null}

          {correctionItems.length > 0 ? (
            <div className="space-y-2">
              {correctionItems.slice(0, 2).map((item) => (
                <div
                  key={`${item.code}-${item.span}-${item.suggestion}`}
                  className="rounded-xl border border-rose-100 bg-white px-3 py-2"
                >
                  <div className="font-medium text-stone-900">
                    <span className="line-through text-stone-400">{item.span}</span>
                    {' -> '}
                    <span className="text-rose-700">{item.suggestion}</span>
                  </div>
                  <div className="mt-1 text-xs text-stone-500">{item.message}</div>
                </div>
              ))}
            </div>
          ) : usedWords.length > 0 ? (
            <p className="text-stone-600">Used this turn: {formatWordList(usedWords)}</p>
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

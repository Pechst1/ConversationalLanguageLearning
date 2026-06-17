import React from 'react';
import type { LearningFocusItem, LearningMoment } from '@/hooks/useLearningSession';

type Props = {
  items: LearningFocusItem[];
  className?: string;
  selectedWordIds?: number[];
  currentMoment?: LearningMoment | null;
  onInsertWord?: (word: string) => void;
  onToggleWord?: (
    word: {
      id: number;
      word: string;
      translation?: string;
      is_new?: boolean;
      familiarity?: 'new' | 'learning' | 'familiar';
    },
    selected: boolean,
  ) => void;
};

const LABELS: Record<LearningFocusItem['kind'], string> = {
  vocabulary: 'Use',
  grammar: 'Notice',
  error: 'Repair',
};

const TONES: Record<LearningFocusItem['kind'], string> = {
  vocabulary: 'border-slate-200 bg-slate-50 text-slate-700',
  grammar: 'border-amber-200 bg-amber-50 text-amber-800',
  error: 'border-rose-200 bg-rose-50 text-rose-800',
};

export default function LearningFocusPanel({
  items,
  className,
  selectedWordIds = [],
  currentMoment,
  onInsertWord,
  onToggleWord,
}: Props) {
  if (!items.length) {
    return null;
  }

  const vocabularyItems = items.filter((item) => item.kind === 'vocabulary');
  const contextualItems = items.filter((item) => item.kind !== 'vocabulary');
  const selectedSet = new Set(selectedWordIds);

  const selectedCount = vocabularyItems.filter((item) => {
    const wordId = typeof item.metadata?.word_id === 'number' ? item.metadata.word_id : null;
    return wordId !== null && selectedSet.has(wordId);
  }).length;
  const vocabularyExamples = vocabularyItems
    .map((item) => {
      const sentence =
        typeof item.metadata?.hint_sentence === 'string'
          ? item.metadata.hint_sentence
          : typeof item.metadata?.example_sentence === 'string'
            ? item.metadata.example_sentence
            : '';
      const translation =
        typeof item.metadata?.hint_translation === 'string'
          ? item.metadata.hint_translation
          : typeof item.metadata?.example_translation === 'string'
            ? item.metadata.example_translation
            : '';

      if (!sentence.trim()) {
        return null;
      }

      return {
        key: `${item.key}-context`,
        word: item.title,
        sentence,
        translation,
      };
    })
    .filter((item): item is { key: string; word: string; sentence: string; translation: string } => item !== null)
    .slice(0, 3);

  return (
    <div className={`${className ?? ''} overflow-hidden rounded-[28px] border border-stone-200 bg-white/85 px-5 py-4 shadow-sm`}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h3 className="text-base font-medium text-stone-900">
          Right now
        </h3>
        <span className="text-xs text-stone-400">
          {vocabularyItems.length > 0 ? `${selectedCount}/${vocabularyItems.length} ready` : `${items.length} cues`}
        </span>
      </div>

      <div className="space-y-3">
        {vocabularyItems.length > 0 ? (
          <div className="rounded-2xl border border-stone-200 bg-stone-50/70 px-4 py-4">
            <div className="mb-3 flex items-center gap-2">
              <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ${TONES.vocabulary}`}>
                {LABELS.vocabulary}
              </span>
              <span className="text-xs text-stone-400">
                Tap a word to place it into your next reply
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {vocabularyItems.map((item) => {
                const wordId = typeof item.metadata?.word_id === 'number' ? item.metadata.word_id : null;
                if (wordId === null) {
                  return null;
                }

                const isSelected = selectedSet.has(wordId);
                const translation = typeof item.metadata?.translation === 'string'
                  ? item.metadata.translation
                  : item.subtitle;
                const familiarity = typeof item.state === 'string'
                  ? item.state as 'new' | 'learning' | 'familiar'
                  : undefined;
                const isNew = Boolean(item.metadata?.is_new);

                return (
                  <button
                    key={item.key}
                    type="button"
                    className={`rounded-full border px-3 py-2 text-sm transition-colors ${
                      isSelected
                        ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                        : isNew
                          ? 'border-rose-200 bg-rose-50 text-rose-700 hover:border-rose-300'
                          : 'border-stone-200 bg-white text-stone-700 hover:border-stone-300 hover:bg-stone-50'
                    }`}
                    onClick={() => {
                      onToggleWord?.(
                        {
                          id: wordId,
                          word: item.title,
                          translation: translation || undefined,
                          is_new: isNew,
                          familiarity,
                        },
                        !isSelected,
                      );
                      if (onInsertWord) {
                        onInsertWord(item.title);
                      }
                    }}
                    title={translation || undefined}
                  >
                    <span className="font-medium">{item.title}</span>
                    {translation ? (
                      <span className="ml-2 text-xs opacity-70">{translation}</span>
                    ) : null}
                  </button>
                );
              })}
            </div>
            {vocabularyExamples.length > 0 ? (
              <div className="mt-3 rounded-2xl border border-stone-200 bg-white px-4 py-3">
                <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.16em] text-stone-400">
                  Context anchors
                </div>
                <div className="space-y-3">
                  {vocabularyExamples.map((example) => (
                    <div key={example.key} className="border-t border-stone-100 pt-3 first:border-t-0 first:pt-0">
                      <div className="mb-1 text-xs font-medium text-stone-500">{example.word}</div>
                      <p className="font-serif text-base italic leading-6 text-stone-800">
                        {example.sentence}
                      </p>
                      {example.translation ? (
                        <p className="mt-1 text-xs leading-5 text-stone-500">
                          {example.translation}
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        {contextualItems.map((item) => (
          <div
            key={item.key}
            className="rounded-2xl border border-stone-200 bg-white px-4 py-4"
          >
            <div className="mb-2 flex items-center gap-2">
              <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ${TONES[item.kind]}`}>
                {LABELS[item.kind]}
              </span>
              {item.state ? (
                <span className="text-xs text-stone-400">{item.state.replace(/_/g, ' ')}</span>
              ) : null}
              {currentMoment && currentMoment.sourceType === item.kind ? (
                <span className="text-xs text-stone-400">exercise below</span>
              ) : null}
            </div>
            <div className="text-sm font-medium text-stone-900">{item.title}</div>
            {item.subtitle ? (
              <div className="mt-1 text-sm text-stone-500">{item.subtitle}</div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

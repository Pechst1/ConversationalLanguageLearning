import React from 'react';
import type { LearningMoment } from '@/hooks/useLearningSession';

type SubmitPayload = {
  answerText?: string;
  selectedChoice?: string;
};

type Props = {
  moment: LearningMoment;
  loading?: boolean;
  onSubmit: (payload: SubmitPayload) => Promise<void> | void;
  onSkip: () => Promise<void> | void;
};

export default function VocabMomentCard({
  moment,
  loading = false,
  onSubmit,
  onSkip,
}: Props) {
  const [value, setValue] = React.useState(moment.prefillText ?? '');
  const [isAnswerRevealed, setIsAnswerRevealed] = React.useState(false);

  React.useEffect(() => {
    setValue(moment.prefillText ?? '');
    setIsAnswerRevealed(false);
  }, [moment.id, moment.prefillText]);

  const primaryWord =
    typeof moment.metadata?.word === 'string' ? moment.metadata.word : null;
  const deckName =
    typeof moment.metadata?.deck_name === 'string' ? moment.metadata.deck_name : null;
  const exampleSentence =
    typeof moment.metadata?.example_sentence === 'string' ? moment.metadata.example_sentence : null;
  const exampleTranslation =
    typeof moment.metadata?.example_translation === 'string' ? moment.metadata.example_translation : null;
  const correctAnswer =
    typeof moment.metadata?.correct_answer === 'string'
      ? moment.metadata.correct_answer
      : typeof moment.metadata?.translation === 'string'
        ? moment.metadata.translation
        : Array.isArray(moment.metadata?.accepted_answers)
          ? moment.metadata.accepted_answers.find((answer): answer is string => typeof answer === 'string')
          : null;
  const shouldUseAnkiReview =
    moment.kind === 'vocab_check' ||
    (moment.sourceType === 'vocabulary' && moment.inputMode === 'single_choice');

  const ankiRatings = [
    {
      key: 'again',
      label: 'Again',
      hint: 'Did not remember',
      className: 'border-rose-200 bg-rose-50 text-rose-700 hover:border-rose-300 hover:bg-rose-100',
      answerText: undefined,
    },
    {
      key: 'hard',
      label: 'Hard',
      hint: 'Remembered with effort',
      className: 'border-amber-200 bg-amber-50 text-amber-800 hover:border-amber-300 hover:bg-amber-100',
      answerText: correctAnswer ?? undefined,
    },
    {
      key: 'good',
      label: 'Good',
      hint: 'Remembered',
      className: 'border-sky-200 bg-sky-50 text-sky-800 hover:border-sky-300 hover:bg-sky-100',
      answerText: correctAnswer ?? undefined,
    },
    {
      key: 'easy',
      label: 'Easy',
      hint: 'Instant recall',
      className: 'border-stone-800 bg-stone-900 text-stone-50 hover:bg-stone-800',
      answerText: correctAnswer ?? undefined,
    },
  ];

  const handleSubmit = async () => {
    if (moment.inputMode === 'free_text') {
      if (!value.trim()) {
        return;
      }
      await onSubmit({ answerText: value.trim() });
      return;
    }
  };

  return (
    <div className="rounded-[28px] border border-stone-200 bg-white px-5 py-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium uppercase tracking-[0.16em] text-slate-700">
            Vocabulary
          </span>
          {deckName ? (
            <span className="text-xs text-stone-400">{deckName}</span>
          ) : null}
        </div>
        {primaryWord ? (
          <span className="rounded-full border border-stone-200 bg-stone-50 px-3 py-1 text-sm font-medium text-stone-700">
            {primaryWord}
          </span>
        ) : null}
      </div>

      <div className="space-y-3">
        <div>
          <h3 className="text-base font-medium text-stone-900">{moment.title}</h3>
          <p className="mt-1 whitespace-pre-line text-sm leading-6 text-stone-600">{moment.body}</p>
        </div>

        {exampleSentence ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div className="mb-1 text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">
              Context sentence
            </div>
            <p className="font-serif text-lg italic leading-6 text-stone-900">{exampleSentence}</p>
            {exampleTranslation ? (
              <p className="mt-2 text-sm leading-5 text-stone-500">{exampleTranslation}</p>
            ) : null}
          </div>
        ) : null}

        {shouldUseAnkiReview ? (
          <div className="space-y-3">
            {isAnswerRevealed ? (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 px-4 py-3">
                <div className="mb-1 text-[11px] font-medium uppercase tracking-[0.16em] text-emerald-700">
                  Answer
                </div>
                <p className="text-lg font-medium text-emerald-950">
                  {correctAnswer || 'Use your recall, then rate it.'}
                </p>
              </div>
            ) : (
              <button
                type="button"
                disabled={loading}
                onClick={() => setIsAnswerRevealed(true)}
                className="w-full rounded-2xl border border-stone-900 bg-stone-900 px-4 py-3 text-center text-sm font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Reveal answer
              </button>
            )}

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {ankiRatings.map((rating) => (
                <button
                  key={rating.key}
                  type="button"
                  disabled={loading || !isAnswerRevealed}
                  onClick={() => onSubmit({
                    answerText: rating.answerText,
                    selectedChoice: `anki:${rating.key}`,
                  })}
                  className={`min-h-[76px] rounded-2xl border px-3 py-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${rating.className}`}
                >
                  <span className="block text-sm font-semibold">{rating.label}</span>
                  <span className="mt-1 block text-xs opacity-75">{rating.hint}</span>
                </button>
              ))}
            </div>

            <div className="flex justify-end">
              <button
                type="button"
                onClick={onSkip}
                disabled={loading}
                className="rounded-full border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-stone-600 transition-colors hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Skip
              </button>
            </div>
          </div>
        ) : null}

        {!shouldUseAnkiReview && moment.inputMode === 'single_choice' ? (
          <div className="space-y-2">
            {moment.choices.map((choice) => (
              <button
                key={choice.key}
                type="button"
                disabled={loading}
                onClick={() => onSubmit({ selectedChoice: choice.key })}
                className="w-full rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-left text-sm text-stone-700 transition-colors hover:border-stone-300 hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
              >
                {choice.label}
              </button>
            ))}
          </div>
        ) : null}

        {!shouldUseAnkiReview && moment.inputMode === 'free_text' ? (
          <div className="space-y-3">
            <textarea
              value={value}
              onChange={(event) => setValue(event.target.value)}
              rows={3}
              placeholder="Type the answer here..."
              className="w-full rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-900 placeholder:text-stone-400 focus:border-stone-300 focus:outline-none"
            />
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={onSkip}
                disabled={loading}
                className="rounded-full border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-stone-600 transition-colors hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Skip
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={loading || !value.trim()}
                className="rounded-full bg-stone-900 px-4 py-2 text-sm font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:cursor-not-allowed disabled:bg-stone-300"
              >
                Check
              </button>
            </div>
          </div>
        ) : null}

        {moment.inputMode === 'chips' ? (
          <div className="flex items-center justify-between gap-3 rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3">
            <div className="text-sm text-stone-600">
              This is a light prompt. Use it naturally in the reply composer below.
            </div>
            <button
              type="button"
              onClick={onSkip}
              disabled={loading}
              className="rounded-full border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-stone-600 transition-colors hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Skip hint
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

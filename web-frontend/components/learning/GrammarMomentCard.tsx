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

export default function GrammarMomentCard({
  moment,
  loading = false,
  onSubmit,
  onSkip,
}: Props) {
  const [value, setValue] = React.useState(moment.prefillText ?? '');

  React.useEffect(() => {
    setValue(moment.prefillText ?? '');
  }, [moment.id, moment.prefillText]);

  const conceptName =
    typeof moment.metadata?.concept_name === 'string'
      ? moment.metadata.concept_name
      : typeof moment.metadata?.exercise_type === 'string'
        ? moment.metadata.exercise_type
        : null;
  const instruction =
    typeof moment.metadata?.instruction === 'string'
      ? moment.metadata.instruction
      : null;
  const exampleFormat =
    typeof moment.metadata?.example_format === 'string'
      ? moment.metadata.example_format
      : typeof moment.metadata?.correct_answer === 'string'
        ? moment.metadata.correct_answer
        : null;
  const hint =
    typeof moment.metadata?.hint === 'string'
      ? moment.metadata.hint
      : null;

  const label = moment.sourceType === 'error' ? 'Repair' : 'Grammar';

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
          <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-medium uppercase tracking-[0.16em] text-amber-800">
            {label}
          </span>
          {conceptName ? (
            <span className="text-xs text-stone-400">{conceptName}</span>
          ) : null}
        </div>
      </div>

      <div className="space-y-3">
        <div>
          {instruction ? (
            <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.16em] text-stone-400">
              {instruction}
            </div>
          ) : null}
          <h3 className="text-base font-medium text-stone-900">{moment.title}</h3>
          <p className="mt-1 text-sm leading-6 text-stone-600">{moment.body}</p>
        </div>

        {exampleFormat ? (
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 px-4 py-3">
            <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-emerald-700">
              Example format
            </div>
            <div className="mt-1 text-sm text-emerald-900">{exampleFormat}</div>
          </div>
        ) : null}

        {hint ? (
          <div className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-600">
            {hint}
          </div>
        ) : null}

        {moment.inputMode === 'single_choice' ? (
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

        {moment.inputMode === 'free_text' ? (
          <div className="space-y-3">
            <textarea
              value={value}
              onChange={(event) => setValue(event.target.value)}
              rows={3}
              placeholder="Write one corrected answer..."
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
                Submit
              </button>
            </div>
          </div>
        ) : null}

        {moment.inputMode === 'chips' ? (
          <div className="flex items-center justify-between gap-3 rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3">
            <div className="text-sm text-stone-600">
              This prompt shapes the next reply. Continue in the composer below.
            </div>
            <button
              type="button"
              onClick={onSkip}
              disabled={loading}
              className="rounded-full border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-stone-600 transition-colors hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Skip
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

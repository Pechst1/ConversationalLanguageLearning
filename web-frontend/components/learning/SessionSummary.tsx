import React from 'react';

type SuccessExample = {
  word: string;
  translation?: string;
  sentence?: string;
};

type ErrorExample = {
  word: string;
  issue?: string;
  correction?: string;
  category?: string;
};

type Summary = {
  xp_earned: number;
  words_practiced: number;
  accuracy_rate: number;
  new_words_introduced: number;
  words_reviewed: number;
  correct_responses: number;
  incorrect_responses: number;
  status: string;
  success_examples?: SuccessExample[];
  error_examples?: ErrorExample[];
  flashcard_words?: Array<any>;
  practice_items?: Array<{
    word: string;
    translation?: string;
    issue?: string;
    correction?: string;
    category?: string;
    sentence?: string;
  }>;
};

type SessionSummaryProps = {
  summary: Summary;
};

const StatItem = ({ label, value }: { label: string; value: React.ReactNode }) => (
  <div className="rounded-lg border-2 border-[#0b3954] bg-[#f5f1e8] p-4 shadow-sm">
    <p className="text-xs uppercase tracking-wide text-[#0b3954]/70">{label}</p>
    <p className="text-2xl font-semibold text-[#0b3954]">{value}</p>
  </div>
);

export default function SessionSummary({ summary }: SessionSummaryProps) {
  const stats = [
    { label: 'XP earned', value: summary.xp_earned },
    { label: 'Words practiced', value: summary.words_practiced },
    { label: 'Accuracy rate', value: `${Math.round((summary.accuracy_rate || 0) * 100)}%` },
    { label: 'New words introduced', value: summary.new_words_introduced },
    { label: 'Words reviewed', value: summary.words_reviewed },
  ];

  const flashcards = (summary.flashcard_words ?? []).map((word: any) => ({
    id: word.id ?? word.word_id,
    word: word.word,
    translation: word.translation,
    hintSentence: word.hint_sentence ?? word.hintSentence,
  }));

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-gray-900">Session Highlights</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {stats.map((stat) => (
            <StatItem key={stat.label} label={stat.label} value={stat.value} />
          ))}
        </div>
      </section>

      {summary.success_examples && summary.success_examples.length > 0 && (
        <section className="space-y-3">
          <h3 className="text-lg font-semibold text-[#0b3954]">What went well</h3>
          <div className="space-y-3">
            {summary.success_examples.map((item, index) => (
              <div key={index} className="rounded-lg border-2 border-[#4caf50] bg-[#edf7ed] p-4">
                <p className="text-sm font-semibold text-[#245b2a]">
                  {item.word}
                  {item.translation ? ` – ${item.translation}` : ''}
                </p>
                {item.sentence && (
                  <p className="mt-1 text-sm text-[#1f5124]">“{item.sentence}”</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {summary.error_examples && summary.error_examples.length > 0 && (
        <section className="space-y-3">
          <h3 className="text-lg font-semibold text-[#931621]">Next steps</h3>
          <div className="space-y-3">
            {summary.error_examples.map((item, index) => (
              <div key={index} className="rounded-lg border-2 border-[#f25c54] bg-[#ffe8e5] p-4">
                <p className="text-sm font-semibold text-[#aa2f2f]">{item.word}</p>
                {item.issue && <p className="mt-1 text-sm text-[#8c1d1d]">{item.issue}</p>}
                {item.correction && (
                  <p className="mt-1 text-sm text-[#8c1d1d]">
                    Suggested: <span className="font-medium">{item.correction}</span>
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {summary.practice_items && summary.practice_items.length > 0 && (
        <section className="space-y-3">
          <h3 className="text-lg font-semibold text-[#0b3954]">What needs practice</h3>
          <div className="space-y-3">
            {summary.practice_items.map((item, index) => (
              <div key={index} className="rounded-lg border-2 border-[#0b3954] bg-[#f0efeb] p-4">
                <p className="text-sm font-semibold text-[#0b3954]">
                  {item.word}
                  {item.translation ? ` – ${item.translation}` : ''}
                </p>
                {item.issue && (
                  <p className="mt-1 text-sm text-[#0b3954]">
                    Issue: <span className="font-medium">{item.issue}</span>
                  </p>
                )}
                {item.correction && (
                  <p className="mt-1 text-sm text-[#0b3954]">
                    Correction: <span className="font-medium">{item.correction}</span>
                  </p>
                )}
                {item.sentence && (
                  <p className="mt-1 text-sm italic text-[#0b3954]/80">“{item.sentence}”</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {flashcards.length > 0 && (
        <section className="space-y-3">
          <h3 className="text-lg font-semibold text-[#0b3954]">Words to review</h3>
          <div className="flex flex-wrap gap-2">
            {flashcards.map((word) => (
              <div
                key={word.id}
                className="rounded-md border-2 border-[#0b3954] bg-[#ffd60a] px-3 py-2 text-sm text-[#0b3954]"
              >
                <p className="font-semibold">{word.word}</p>
                {word.translation && <p>{word.translation}</p>}
                {word.hintSentence && (
                  <p className="text-xs text-[#0b3954]">Hint: {word.hintSentence}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

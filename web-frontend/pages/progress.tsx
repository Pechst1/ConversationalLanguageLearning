import React, { useMemo, useState, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import api from '@/services/api';
import { Card, CardContent } from '@/components/ui/Card';
import { AnkiSync } from '@/components/AnkiSync';
import { CollapsibleSection } from '@/components/ui/CollapsibleSection';
import { AlertCircle, BookOpen, Languages, Target } from 'lucide-react';

// Error Analytics Types
type ErrorStageCounts = {
  new: number;
  learning: number;
  review: number;
  relearning: number;
  mastered: number;
};

type ErrorCategoryCount = {
  category: string;
  count: number;
};

type ErrorSummary = {
  total_errors: number;
  due_today: number;
  stage_counts: ErrorStageCounts;
  categories: ErrorCategoryCount[];
};

type StageCounts = Record<string, number>;

type AnkiDirectionSummary = {
  direction: string;
  total: number;
  due_today: number;
  stage_counts: StageCounts;
};

type AnkiProgressSummary = {
  total_cards: number;
  due_today: number;
  stage_totals: StageCounts;
  chart: { stage: string; value: number }[];
  directions: Record<string, AnkiDirectionSummary>;
};

type AnkiWordProgress = {
  word_id: number;
  word: string;
  language: string;
  direction?: string | null;
  french_translation?: string | null;
  german_translation?: string | null;
  english_translation?: string | null;
  deck_name?: string | null;
  difficulty_level?: number | null;
  learning_stage: string;
  state: string;
  progress_difficulty?: number | null;
  ease_factor?: number | null;
  interval_days?: number | null;
  due_at?: string | null;
  next_review?: string | null;
  last_review?: string | null;
  reps: number;
  lapses: number;
  proficiency_score: number;
  scheduler?: string | null;
};

type GrammarSummary = {
  total: number;
  mastered: number;
  in_progress: number;
  not_started: number;
  due_count: number;
};

type ErrorDetailItem = {
  id: number;
  original_text: string;  // The erroneous text the user wrote
  subcategory: string;    // Fine-grained category (e.g., "gender_agreement")
  category: string;       // Main category (e.g., "grammar")
  explanation: string | null;
  correction: string | null;
  occurrences: number;
  lapses: number;
  learning_stage: string;
  next_review: string | null;
  last_seen: string | null;
};

// Subcategory display names
const subcategoryLabels: Record<string, string> = {
  // Grammar
  gender_agreement: 'Gender Agreement',
  verb_tenses: 'Verb Tenses',
  subjonctif: 'Subjonctif',
  conditional: 'Conditional',
  negation: 'Negation',
  prepositions: 'Prepositions',
  articles: 'Articles',
  pronouns: 'Pronouns',
  word_order: 'Word Order',
  subject_verb_agreement: 'Subject-Verb Agreement',
  // Spelling
  accents: 'Accents',
  common_misspellings: 'Spelling',
  // Vocabulary
  false_friends: 'False Friends',
  word_choice: 'Word Choice',
  // Punctuation
  quotation_marks: 'Quotation Marks',
  capitalization: 'Capitalization',
  // Fallback
  other: 'Other',
  grammar: 'Grammar',
  spelling: 'Spelling',
  vocabulary: 'Vocabulary',
  punctuation: 'Punctuation',
  style: 'Style',
};

type ErrorListResponse = {
  total: number;
  items: ErrorDetailItem[];
};

type ProgressPageProps = {
  /** Rendered inside the Cahier, which supplies its own masthead. */
  embedded?: boolean;
  summary?: AnkiProgressSummary;
  initialProgress?: AnkiWordProgress[];
  errorSummary?: ErrorSummary;
  errorList?: ErrorListResponse;
  grammarSummary?: GrammarSummary;
};

const directionLabels: Record<string, string> = {
  all: 'All Directions',
  fr_to_de: 'French → German',
  de_to_fr: 'German → French',
};

const stageOrder = ['new', 'learning', 'review', 'relearn', 'other'] as const;
const stageDisplay: Record<string, string> = {
  new: 'New',
  learning: 'In Progress',
  review: 'Review',
  relearn: 'Re-learning',
  other: 'Other',
};

const EMPTY_STAGE_COUNTS: StageCounts = {
  new: 0,
  learning: 0,
  review: 0,
  relearn: 0,
  relearning: 0,
  mastered: 0,
  other: 0,
};

const EMPTY_ANKI_SUMMARY: AnkiProgressSummary = {
  total_cards: 0,
  due_today: 0,
  stage_totals: EMPTY_STAGE_COUNTS,
  chart: [],
  directions: {},
};

const EMPTY_ERROR_SUMMARY: ErrorSummary = {
  total_errors: 0,
  due_today: 0,
  stage_counts: {
    new: 0,
    learning: 0,
    review: 0,
    relearning: 0,
    mastered: 0,
  },
  categories: [],
};

const EMPTY_ERROR_LIST: ErrorListResponse = {
  total: 0,
  items: [],
};

const EMPTY_GRAMMAR_SUMMARY: GrammarSummary = {
  total: 0,
  mastered: 0,
  in_progress: 0,
  not_started: 0,
  due_count: 0,
};

function preferredDirectionFor(summary: AnkiProgressSummary): 'fr_to_de' | 'de_to_fr' | 'all' {
  if (summary.directions?.fr_to_de?.total) return 'fr_to_de';
  if (summary.directions?.de_to_fr?.total) return 'de_to_fr';
  return 'all';
}

const formatNumber = (value: number | null | undefined) => {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString();
};

const formatDate = (value: string | null | undefined) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    dateStyle: 'short',
    timeStyle: 'short',
  });
};

const AnkiStagePie = dynamic(() => import('@/components/learning/AnkiStagePie'), { ssr: false });
const ErrorCategoryPie = dynamic(() => import('@/components/learning/ErrorCategoryPie'), { ssr: false });

export default function ProgressPage({
  embedded = false,
  summary: initialSummary = EMPTY_ANKI_SUMMARY,
  initialProgress = [],
  errorSummary: initialErrorSummary = EMPTY_ERROR_SUMMARY,
  errorList: initialErrorList = EMPTY_ERROR_LIST,
  grammarSummary: initialGrammarSummary = EMPTY_GRAMMAR_SUMMARY,
}: ProgressPageProps) {
  const [summary, setSummary] = useState<AnkiProgressSummary>(initialSummary);
  const [errorSummary, setErrorSummary] = useState<ErrorSummary>(initialErrorSummary);
  const [errorList, setErrorList] = useState<ErrorListResponse>(initialErrorList);
  const [grammarSummary, setGrammarSummary] = useState<GrammarSummary>(initialGrammarSummary);
  const defaultDirection = preferredDirectionFor(initialSummary);

  const [direction, setDirection] = useState<'fr_to_de' | 'de_to_fr' | 'all'>(defaultDirection);
  const [entries, setEntries] = useState<AnkiWordProgress[]>(
    defaultDirection === 'fr_to_de' ? initialProgress : []
  );
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const loadOverview = async () => {
      setLoading(true);
      try {
        const [
          nextSummary,
          nextProgress,
          nextErrorSummary,
          nextErrorList,
          nextGrammarSummary,
        ] = await Promise.all([
          api.getAnkiSummary().catch(() => EMPTY_ANKI_SUMMARY),
          api.getAnkiProgress({ direction: 'fr_to_de' }).catch(() => []),
          api.getErrorSummary().catch(() => EMPTY_ERROR_SUMMARY),
          api.get<ErrorListResponse>('/analytics/errors/list').catch(() => EMPTY_ERROR_LIST),
          api.getGrammarSummary().catch(() => EMPTY_GRAMMAR_SUMMARY),
        ]);

        if (cancelled) return;

        const normalizedSummary = nextSummary as AnkiProgressSummary;
        setSummary(normalizedSummary);
        setEntries(Array.isArray(nextProgress) ? nextProgress as AnkiWordProgress[] : []);
        setErrorSummary(nextErrorSummary as ErrorSummary);
        setErrorList(nextErrorList as ErrorListResponse);
        setGrammarSummary(nextGrammarSummary as GrammarSummary);
        setDirection((prev) => (prev === 'all' ? preferredDirectionFor(normalizedSummary) : prev));
      } catch (error) {
        console.debug('Failed to load progress overview', error);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadOverview();

    return () => {
      cancelled = true;
    };
  }, []);

  const directionSummary = useMemo(() => {
    if (direction === 'all') {
      return {
        total: summary.total_cards,
        due_today: summary.due_today,
        stage_counts: summary.stage_totals,
      };
    }
    const data = summary.directions?.[direction];
    return (
      data ?? {
        total: 0,
        due_today: 0,
        stage_counts: { new: 0, learning: 0, review: 0, relearn: 0, other: 0 },
      }
    );
  }, [direction, summary]);

  const chartData = useMemo(() => {
    if (direction === 'all') {
      return summary.chart ?? [];
    }
    const counts = directionSummary.stage_counts;
    return stageOrder
      .filter((stage) => counts[stage] > 0)
      .map((stage) => ({ stage, value: counts[stage] }));
  }, [direction, directionSummary.stage_counts, summary.chart]);

  useEffect(() => {
    const fetchData = async () => {
      if (direction === 'all') {
        setEntries([]);
        return;
      }
      setLoading(true);
      try {
        const payload = await api.getAnkiProgress({ direction });
        setEntries(Array.isArray(payload) ? payload : []);
      } catch (error) {
        console.debug('Failed to load progress list', error);
        setEntries([]);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [direction]);

  const handleSyncComplete = useCallback(() => {
    // Refresh the progress data after sync
    window.location.reload();
  }, []);

  return (
    <div className={embedded ? 'space-y-8' : 'space-y-8 p-4'}>
      <div className={embedded ? 'mb-6' : 'mb-8 border-b border-[var(--app-ink)] pb-5'}>
        {!embedded && (
          <div className="text-xs font-black uppercase tracking-[0.16em] text-[var(--app-ink-3)]">
            Learning Progress
          </div>
        )}
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mt-1">
          <h1 className="font-serif text-5xl italic leading-none text-[var(--app-ink)]">
            Progress
          </h1>
          <div className="flex gap-4 flex-wrap items-center">
            <div className="mr-2">
              <AnkiSync onSyncComplete={handleSyncComplete} />
            </div>
            {(['fr_to_de', 'de_to_fr', 'all'] as const).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setDirection(option)}
                className={`border border-[var(--app-ink)] px-4 py-2 text-xs font-black uppercase tracking-[0.13em] transition-all hover:bg-[var(--app-paper-2)] ${
                  direction === option
                    ? 'bg-[var(--app-ink)] text-[var(--app-paper)]'
                    : 'bg-[var(--app-sheet)] text-[var(--app-ink)]'
                }`}
              >
                {directionLabels[option]}
              </button>
            ))}
          </div>
        </div>
        <p className="mt-3 max-w-2xl text-[var(--app-ink-2)]">
          Overview of all imported Anki cards. Choose your learning direction to review vocabulary details.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
        <StatCard label="Total" value={formatNumber(directionSummary.total)} color="bg-[var(--app-sheet)]" />
        <StatCard label="New" value={formatNumber(directionSummary.stage_counts.new)} color="bg-[var(--app-blue)]" textColor="text-[var(--app-sheet)]" />
        <StatCard label="In Progress" value={formatNumber(directionSummary.stage_counts.learning)} color="bg-[var(--app-yellow)]" />
        <StatCard label="Review" value={formatNumber(directionSummary.stage_counts.review)} color="bg-[var(--app-red)]" textColor="text-[var(--app-sheet)]" />
        <StatCard label="Due Today" value={formatNumber(directionSummary.due_today)} color="bg-[var(--app-ink)]" textColor="text-[var(--app-sheet)]" />
      </div>

      {directionSummary.total === 0 ? (
        <div className="bg-[var(--app-sheet)] border border-[var(--app-ink)] p-8 text-center">
          <p className="text-xl font-bold">
            No cards available for the currently selected direction.
          </p>
          <p className="mt-2 text-[var(--app-ink-2)]">Import Anki cards or select a different direction.</p>
        </div>
      ) : (
        <>
          <div className="bg-[var(--app-sheet)] border border-[var(--app-ink)]">
            <div className="border-b-4 border-[var(--app-ink)] p-4 bg-[var(--app-paper-2)]">
              <h2 className="text-xl font-black uppercase">Stage Distribution ({directionLabels[direction]})</h2>
            </div>
            <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
              <div className="h-64 border border-[var(--app-ink)] p-4 bg-[var(--app-sheet)] rounded-none">
                <AnkiStagePie data={chartData} />
              </div>
              <div className="space-y-4">
                {stageOrder.map((stage) => (
                  <div key={stage} className="flex items-center justify-between text-base border-b-2 border-[var(--app-ink)]/10 pb-2 last:border-0 hover:pl-2 transition-all">
                    <span className="font-bold uppercase tracking-wide">{stageDisplay[stage]}</span>
                    <span className="font-black text-xl tabular-nums bg-[var(--app-yellow)] px-2 border border-[var(--app-ink)]">
                      {formatNumber(directionSummary.stage_counts[stage])}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {direction === 'all' ? (
            <div className="bg-[var(--app-yellow)] border border-[var(--app-ink)] p-6 text-center">
              <p className="font-bold text-lg">
                Select a specific direction above to view individual cards and their progress.
              </p>
            </div>
          ) : (
            <CollapsibleSection
              title="Vocabulary"
              icon={<Languages className="w-6 h-6 text-[var(--app-sheet)]" />}
              iconBgColor="bg-[var(--app-blue)]"
              defaultOpen={true}
              badge={entries.length}
            >
              <ProgressTable
                direction={direction}
                entries={entries}
                loading={loading}
              />
            </CollapsibleSection>
          )}
        </>
      )}

      {/* Error Analytics Section */}
      <div className="mt-12 pt-8 border-t-8 border-[var(--app-ink)]">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-black uppercase tracking-tight flex items-center gap-3">
              <div className="bg-[var(--app-red)] border border-[var(--app-ink)] p-1">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 text-[var(--app-sheet)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              </div>
              Error Analysis
            </h2>
            <p className="text-lg font-bold text-[var(--app-ink-2)] mt-2">
              Overview of your errors with spaced repetition tracking.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-6 mb-8">
          <StatCard label="Total" value={formatNumber(errorSummary.total_errors)} color="bg-[var(--app-sheet)]" />
          <StatCard label="New" value={formatNumber(errorSummary.stage_counts.new)} color="bg-[var(--app-red)]" textColor="text-[var(--app-sheet)]" />
          <StatCard label="In Progress" value={formatNumber(errorSummary.stage_counts.learning + errorSummary.stage_counts.relearning)} color="bg-[var(--app-yellow)]" />
          <StatCard label="Review" value={formatNumber(errorSummary.stage_counts.review)} color="bg-[var(--app-blue)]" textColor="text-[var(--app-sheet)]" />
          <StatCard label="Due Today" value={formatNumber(errorSummary.due_today)} color="bg-[var(--app-ink)]" textColor="text-[var(--app-sheet)]" />
        </div>

        {errorSummary.total_errors === 0 ? (
          <div className="bg-[var(--app-paper-2)] border border-[var(--app-ink)] p-6">
            <div className="flex items-center gap-4">
              <div className="bg-[var(--app-green)] border border-[var(--app-ink)] p-2">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-8 h-8 text-[var(--app-sheet)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
              </div>
              <p className="text-lg font-bold text-[var(--app-ink)]">
                Excellent! You don&apos;t have any errors tracked yet. Keep it up!
              </p>
            </div>
          </div>
        ) : (
          <div className="bg-[var(--app-sheet)] border border-[var(--app-ink)]">
            <div className="border-b-4 border-[var(--app-ink)] p-4 bg-[var(--app-paper-2)]">
              <h3 className="text-xl font-black uppercase">Error Distribution by Category</h3>
            </div>
            <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
              <div className="h-64 border border-[var(--app-ink)] p-4 bg-[var(--app-sheet)]">
                <ErrorCategoryPie data={errorSummary.categories.map(c => ({ category: c.category, value: c.count }))} />
              </div>
              <div className="space-y-4">
                {errorSummary.categories.length > 0 ? (
                  errorSummary.categories.map((cat) => (
                    <div key={cat.category} className="flex items-center justify-between text-base border-b-2 border-[var(--app-ink)]/10 pb-2 last:border-0">
                      <span className="font-bold flex items-center gap-3">
                        <span className={`w-4 h-4 border border-[var(--app-ink)] ${cat.category === 'grammar' ? 'bg-[var(--app-red)]' :
                          cat.category === 'spelling' ? 'bg-[var(--app-alert)]' :
                            cat.category === 'vocabulary' ? 'bg-[var(--app-blue)]' :
                              cat.category === 'style' ? 'bg-[var(--app-blue)]' :
                                'bg-[var(--app-paper-2)]0'
                          }`} />
                        <span className="uppercase tracking-wide">
                          {cat.category === 'grammar' ? 'Grammar' :
                            cat.category === 'spelling' ? 'Spelling' :
                              cat.category === 'vocabulary' ? 'Vocabulary' :
                                cat.category === 'style' ? 'Style' :
                                  cat.category}
                        </span>
                      </span>
                      <span className="font-black text-xl tabular-nums">{formatNumber(cat.count)}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-sm font-bold text-[var(--app-ink-3)] italic">No categories available.</p>
                )}
                <div className="pt-4 mt-4 border-t-4 border-[var(--app-ink)] bg-[var(--app-paper-2)] p-4 -mx-2">
                  <div className="flex items-center justify-between text-lg">
                    <span className="font-black uppercase">Mastered</span>
                    <span className="tabular-nums text-[var(--app-green)] font-black text-2xl">{formatNumber(errorSummary.stage_counts.mastered)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Error Details List */}
        {errorList.items.length > 0 && (
          <div className="mt-8">
            <CollapsibleSection
              title="Saved Errors"
              icon={<AlertCircle className="w-6 h-6 text-[var(--app-sheet)]" />}
              iconBgColor="bg-[var(--app-alert)]"
              defaultOpen={false}
              badge={errorList.total}
            >
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-[var(--app-ink)] text-[var(--app-sheet)] font-bold uppercase tracking-wider text-xs border-b-4 border-[var(--app-ink)]">
                    <tr>
                      <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Error</th>
                      <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Type</th>
                      <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Correction</th>
                      <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Occurrences</th>
                      <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Lapses</th>
                      <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Stage</th>
                      <th className="px-4 py-3">Next Review</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y-2 divide-black">
                    {errorList.items.map((item) => (
                      <tr key={item.id} className="hover:bg-[var(--app-yellow)]/20 transition-colors font-medium">
                        <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)] font-bold text-[var(--app-red)] max-w-[200px] truncate" title={item.original_text}>
                          {item.original_text}
                        </td>
                        <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)]">
                          <span className={`px-2 py-0.5 border border-[var(--app-ink)] text-xs uppercase font-bold ${item.category === 'grammar' ? 'bg-[var(--app-paper-2)] text-[var(--app-ink)]' :
                            item.category === 'spelling' ? 'bg-[var(--app-paper-2)] text-[var(--app-ink)]' :
                              item.category === 'vocabulary' ? 'bg-[var(--app-paper-2)] text-[var(--app-ink)]' :
                                'bg-[var(--app-paper-2)]'
                            }`}>
                            {subcategoryLabels[item.subcategory] || subcategoryLabels[item.category] || item.subcategory}
                          </span>
                        </td>
                        <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)] text-[var(--app-green)] font-medium max-w-[200px] truncate" title={item.correction || ''}>
                          {item.correction || '—'}
                        </td>
                        <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)] tabular-nums text-center">{item.occurrences}</td>
                        <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)] tabular-nums text-[var(--app-red)] font-bold text-center">{item.lapses}</td>
                        <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)]">
                          <span className={`px-2 py-0.5 border border-[var(--app-ink)] text-xs uppercase font-bold ${item.learning_stage === 'new' ? 'bg-[var(--app-paper-2)] text-[var(--app-ink)]' :
                            item.learning_stage === 'learning' ? 'bg-[var(--app-paper-2)] text-[var(--app-ink)]' :
                              item.learning_stage === 'review' ? 'bg-[var(--app-paper-2)] text-[var(--app-ink)]' :
                                item.learning_stage === 'mastered' ? 'bg-[var(--app-green)] text-[var(--app-sheet)]' :
                                  'bg-[var(--app-paper-2)]'
                            }`}>
                            {item.learning_stage === 'new' ? 'New' :
                              item.learning_stage === 'learning' ? 'Learn' :
                                item.learning_stage === 'review' ? 'Review' :
                                  item.learning_stage === 'mastered' ? 'Mastered' : item.learning_stage}
                          </span>
                        </td>
                        <td className="px-4 py-3 tabular-nums font-mono text-xs">{formatDate(item.next_review)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CollapsibleSection>
          </div>
        )}
      </div>

      {/* Grammar Overview Section */}
      <div className="mt-12 pt-8 border-t-8 border-[var(--app-ink)]">
        <div className="mb-8">
          <h2 className="text-3xl font-black uppercase tracking-tight flex items-center gap-3">
            <div className="bg-[var(--app-blue)] border border-[var(--app-ink)] p-1">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 text-[var(--app-sheet)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            Grammar
          </h2>
          <p className="text-lg font-bold text-[var(--app-ink-2)] mt-2">
            Your progress with grammar concepts.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-6 mb-8">
          <StatCard label="Total" value={formatNumber(grammarSummary.total)} color="bg-[var(--app-sheet)]" />
          <StatCard label="Not Started" value={formatNumber(grammarSummary.not_started)} color="bg-[var(--app-paper-3)]" />
          <StatCard label="In Progress" value={formatNumber(grammarSummary.in_progress)} color="bg-[var(--app-yellow)]" />
          <StatCard label="Mastered" value={formatNumber(grammarSummary.mastered)} color="bg-[var(--app-green)]" />
          <StatCard label="Due Today" value={formatNumber(grammarSummary.due_count)} color="bg-[var(--app-ink)]" textColor="text-[var(--app-sheet)]" />
        </div>

        {grammarSummary.total === 0 ? (
          <div className="bg-[var(--app-sheet)] border border-[var(--app-ink)] p-8 text-center">
            <p className="text-xl font-bold">
              No grammar concepts in the system yet.
            </p>
            <p className="mt-2 text-[var(--app-ink-2)] font-bold">Start your grammar training!</p>
          </div>
        ) : (
          <div className="bg-[var(--app-sheet)] border border-[var(--app-ink)] p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-black uppercase">Progress Overview</h3>
              <Link href="/grammar" className="inline-block bg-[var(--app-blue)] text-[var(--app-sheet)] font-bold py-2 px-4 border border-[var(--app-ink)] hover:translate-x-1 hover:translate-y-1 hover:shadow-none transition-all">
                To Grammar Training →
              </Link>
            </div>
            <div className="w-full bg-[var(--app-paper-2)] border border-[var(--app-ink)] h-8 overflow-hidden relative">
              <div className="h-full flex">
                <div
                  className="bg-[var(--app-green)] border-r-2 border-[var(--app-ink)] h-full"
                  style={{ width: `${grammarSummary.total > 0 ? (grammarSummary.mastered / grammarSummary.total) * 100 : 0}%` }}
                  title="Mastered"
                />
                <div
                  className="bg-[var(--app-yellow)] border-r-2 border-[var(--app-ink)] h-full"
                  style={{ width: `${grammarSummary.total > 0 ? (grammarSummary.in_progress / grammarSummary.total) * 100 : 0}%` }}
                  title="In Progress"
                />
              </div>
            </div>
            <div className="flex justify-between text-xs font-bold uppercase mt-2 text-[var(--app-ink-2)] tracking-wider">
              <span>0%</span>
              <span>{grammarSummary.total > 0 ? Math.round((grammarSummary.mastered / grammarSummary.total) * 100) : 0}% mastered</span>
              <span>100%</span>
            </div>
          </div>
        )}
      </div>

      {/* Grammar↔Error Synergy Section */}
      {errorSummary.total_errors > 0 && (
        <div className="mt-12 pt-8 border-t-8 border-[var(--app-ink)]">
          <div className="mb-8">
            <h2 className="text-3xl font-black uppercase tracking-tight flex items-center gap-3">
              <div className="bg-[var(--app-alert)] border border-[var(--app-ink)] p-1">
                <Target className="w-6 h-6 text-[var(--app-sheet)]" />
              </div>
              Recommended Grammar Review
            </h2>
            <p className="text-lg font-bold text-[var(--app-ink-2)] mt-2">
              Based on your most frequent errors, we recommend these grammar topics.
            </p>
          </div>

          <CollapsibleSection
            title="Grammar for your Errors"
            icon={<BookOpen className="w-6 h-6 text-[var(--app-sheet)]" />}
            iconBgColor="bg-[var(--app-blue)]"
            defaultOpen={true}
          >
            <GrammarForErrors />
          </CollapsibleSection>
        </div>
      )}
    </div>
  );
}

// Component to fetch and display grammar concepts for errors
function GrammarForErrors() {
  const [concepts, setConcepts] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    const fetchConcepts = async () => {
      try {
        const data = await api.get('/grammar/for-errors?limit=5');
        setConcepts(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error('Failed to load grammar concepts for errors:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchConcepts();
  }, []);

  if (loading) {
    return (
      <div className="p-8 text-center">
        <p className="text-lg font-bold animate-pulse">Loading recommendations...</p>
      </div>
    );
  }

  if (concepts.length === 0) {
    return (
      <div className="p-8 text-center bg-[var(--app-paper-2)] border border-[var(--app-ink)]">
        <p className="text-lg font-bold">Great! No specific grammar topics need review.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {concepts.map((item: any) => (
        <div
          key={item.concept.id}
          className="bg-[var(--app-sheet)] border border-[var(--app-ink)] p-6 hover:-translate-y-1 transition-all"
        >
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <h3 className="text-xl font-black uppercase mb-2">{item.concept.name}</h3>
              <p className="text-sm text-[var(--app-ink-2)] font-medium">{item.concept.description}</p>
            </div>
            <span className="ml-4 px-3 py-1 bg-[var(--app-blue)] text-[var(--app-sheet)] font-bold text-sm border border-[var(--app-ink)]">
              {item.concept.level}
            </span>
          </div>

          <div className="mb-4">
            <p className="text-xs font-bold uppercase text-[var(--app-ink-3)] mb-2">Your errors in this area:</p>
            <div className="flex flex-wrap gap-2">
              {item.error_patterns.map((pattern: string, idx: number) => (
                <span
                  key={idx}
                  className="px-2 py-1 bg-[var(--app-paper-2)] text-[var(--app-ink)] text-xs font-bold border border-[var(--app-ink)]"
                >
                  {subcategoryLabels[pattern] || pattern}
                </span>
              ))}
            </div>
          </div>

          <Link
            href={`/grammar`}
            className="inline-block bg-[var(--app-blue)] text-[var(--app-sheet)] font-bold py-2 px-4 border border-[var(--app-ink)] hover:translate-x-1 hover:translate-y-1 hover:shadow-none transition-all uppercase text-sm"
          >
            Practice now →
          </Link>
        </div>
      ))}
    </div>
  );
}

type ProgressTableProps = {
  direction: 'fr_to_de' | 'de_to_fr';
  entries: AnkiWordProgress[];
  loading: boolean;
};

function ProgressTable({ direction, entries, loading }: ProgressTableProps) {
  const translationFor = (entry: AnkiWordProgress) => {
    if (entry.direction === 'fr_to_de') return entry.german_translation || entry.english_translation || '—';
    if (entry.direction === 'de_to_fr') return entry.french_translation || entry.english_translation || '—';
    return entry.english_translation || entry.german_translation || entry.french_translation || '—';
  };

  return (
    <div className="bg-[var(--app-sheet)] border border-[var(--app-ink)] overflow-hidden">
      <div className="flex items-center justify-between p-4 border-b-4 border-[var(--app-ink)] bg-[var(--app-paper-2)]">
        <h2 className="text-xl font-black uppercase">{directionLabels[direction]}</h2>
        {loading && <span className="text-sm font-bold bg-[var(--app-yellow)] px-2 border border-[var(--app-ink)] animate-pulse">UPDATING...</span>}
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-[var(--app-ink)] text-[var(--app-sheet)] font-bold uppercase tracking-wider text-xs border-b-4 border-[var(--app-ink)]">
            <tr>
              <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Word</th>
              <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Translation</th>
              <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Stage</th>
              <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Level</th>
              <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Ease</th>
              <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Interval</th>
              <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Due</th>
              <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Reps</th>
              <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Lapses</th>
              <th className="px-4 py-3 border-r border-[var(--app-paper-3)]">Skill</th>
              <th className="px-4 py-3">Deck</th>
            </tr>
          </thead>
          <tbody className="divide-y-2 divide-black">
            {entries.length === 0 ? (
              <tr>
                <td colSpan={11} className="px-4 py-8 text-center text-lg font-bold text-[var(--app-ink-3)]">
                  No cards available for this direction.
                </td>
              </tr>
            ) : (
              entries.map((item) => (
                <tr key={item.word_id} className="hover:bg-[var(--app-yellow)]/20 transition-colors font-medium text-[var(--app-ink)]">
                  <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)] font-bold">{item.word}</td>
                  <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)] text-[var(--app-ink-2)]">{translationFor(item)}</td>
                  <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)]">
                    <span className={`px-2 py-0.5 border border-[var(--app-ink)] text-xs uppercase font-bold ${item.learning_stage === 'new' ? 'bg-[var(--app-paper-2)] text-[var(--app-ink)]' :
                      item.learning_stage === 'learning' ? 'bg-[var(--app-paper-2)] text-[var(--app-ink)]' :
                        item.learning_stage === 'review' ? 'bg-[var(--app-paper-2)] text-[var(--app-ink)]' :
                          'bg-[var(--app-paper-2)]'
                      }`}>
                      {stageDisplay[item.learning_stage?.toLowerCase()] || item.learning_stage}
                    </span>
                  </td>
                  <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)] tabular-nums">{formatNumber(item.progress_difficulty)}</td>
                  <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)] tabular-nums">{formatNumber(item.ease_factor)}</td>
                  <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)] tabular-nums">{formatNumber(item.interval_days)}</td>
                  <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)] tabular-nums font-mono text-xs">{formatDate(item.due_at || item.next_review)}</td>
                  <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)] tabular-nums">{item.reps ?? 0}</td>
                  <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)] tabular-nums text-[var(--app-red)] font-bold">{item.lapses ?? 0}</td>
                  <td className="px-4 py-3 border-r-2 border-[var(--app-paper-3)] tabular-nums">{item.proficiency_score ?? 0}</td>
                  <td className="px-4 py-3 text-[var(--app-ink-3)] italic truncate max-w-[150px]">{item.deck_name || '—'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

type StatCardProps = {
  label: string;
  value: string;
  color?: string;
  textColor?: string;
};

function StatCard({ label, value, color = 'bg-[var(--app-sheet)]', textColor = 'text-[var(--app-ink)]' }: StatCardProps) {
  return (
    <div className={`${color} ${textColor} border border-[var(--app-ink)] p-4 hover:-translate-y-2 transition-all duration-200`}>
      <p className={`text-xs uppercase font-black tracking-widest opacity-80 mb-2`}>{label}</p>
      <p className="text-3xl font-black">{value}</p>
    </div>
  );
}

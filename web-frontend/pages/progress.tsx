import React, { useMemo, useState, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { getSession } from 'next-auth/react';
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
  gender_agreement: 'Genus',
  verb_tenses: 'Zeitformen',
  subjonctif: 'Subjonctif',
  conditional: 'Konditional',
  negation: 'Verneinung',
  prepositions: 'Präpositionen',
  articles: 'Artikel',
  pronouns: 'Pronomen',
  word_order: 'Wortstellung',
  subject_verb_agreement: 'Subjekt-Verb',
  // Spelling
  accents: 'Akzente',
  common_misspellings: 'Rechtschreibung',
  // Vocabulary
  false_friends: 'Faux Amis',
  word_choice: 'Wortwahl',
  // Punctuation
  quotation_marks: 'Anführungszeichen',
  capitalization: 'Großschreibung',
  // Fallback
  other: 'Sonstige',
  grammar: 'Grammatik',
  spelling: 'Rechtschreibung',
  vocabulary: 'Wortschatz',
  punctuation: 'Interpunktion',
  style: 'Stil',
};

type ErrorListResponse = {
  total: number;
  items: ErrorDetailItem[];
};

type ProgressPageProps = {
  summary: AnkiProgressSummary;
  initialProgress: AnkiWordProgress[];
  errorSummary: ErrorSummary;
  errorList: ErrorListResponse;
  grammarSummary: GrammarSummary;
};

const directionLabels: Record<string, string> = {
  all: 'Alle Richtungen',
  fr_to_de: 'Französisch → Deutsch',
  de_to_fr: 'Deutsch → Französisch',
};

const stageOrder = ['new', 'learning', 'review', 'relearn', 'other'] as const;
const stageDisplay: Record<string, string> = {
  new: 'Neu',
  learning: 'In Bearbeitung',
  review: 'Review',
  relearn: 'Re-Learning',
  other: 'Sonstige',
};

const formatNumber = (value: number | null | undefined) => {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString('de-DE');
};

const formatDate = (value: string | null | undefined) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('de-DE', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
};

const AnkiStagePie = dynamic(() => import('@/components/learning/AnkiStagePie'), { ssr: false });
const ErrorCategoryPie = dynamic(() => import('@/components/learning/ErrorCategoryPie'), { ssr: false });

export default function ProgressPage({ summary, initialProgress, errorSummary, errorList, grammarSummary }: ProgressPageProps) {
  const defaultDirection: 'fr_to_de' | 'de_to_fr' | 'all' =
    summary.directions?.fr_to_de?.total
      ? 'fr_to_de'
      : summary.directions?.de_to_fr?.total
        ? 'de_to_fr'
        : 'all';

  const [direction, setDirection] = useState<'fr_to_de' | 'de_to_fr' | 'all'>(defaultDirection);
  const [entries, setEntries] = useState<AnkiWordProgress[]>(
    defaultDirection === 'fr_to_de' ? initialProgress : []
  );
  const [loading, setLoading] = useState(false);

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
    <div className="space-y-8 p-4">
      {/* Anki Sync Section */}
      <div className="mb-6">
        <AnkiSync onSyncComplete={handleSyncComplete} />
      </div>

      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6 bg-white border-4 border-black p-6 shadow-[8px_8px_0px_0px_#000]">
        <div>
          <h1 className="text-4xl font-black uppercase tracking-tighter mb-2">Dein Lernfortschritt</h1>
          <p className="text-lg font-medium text-gray-800">
            Übersicht aller importierten Anki-Karten. Wähle die gewünschte Richtung aus.
          </p>
        </div>
        <div className="flex gap-4">
          {(['fr_to_de', 'de_to_fr', 'all'] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setDirection(option)}
              className={`border-2 border-black px-4 py-2 text-sm font-bold uppercase tracking-wider transition-all shadow-[4px_4px_0px_0px_#000] hover:-translate-y-1 hover:shadow-[6px_6px_0px_0px_#000] active:translate-y-0 active:shadow-[2px_2px_0px_0px_#000] ${direction === option
                ? 'bg-bauhaus-blue text-white'
                : 'bg-white text-black hover:bg-bauhaus-yellow'
                }`}
            >
              {directionLabels[option]}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
        <StatCard label="Gesamt" value={formatNumber(directionSummary.total)} color="bg-white" />
        <StatCard label="Neu" value={formatNumber(directionSummary.stage_counts.new)} color="bg-bauhaus-blue" textColor="text-white" />
        <StatCard label="In Bearbeitung" value={formatNumber(directionSummary.stage_counts.learning)} color="bg-bauhaus-yellow" />
        <StatCard label="Review" value={formatNumber(directionSummary.stage_counts.review)} color="bg-bauhaus-red" textColor="text-white" />
        <StatCard label="Heute fällig" value={formatNumber(directionSummary.due_today)} color="bg-black" textColor="text-white" />
      </div>

      {directionSummary.total === 0 ? (
        <div className="bg-white border-4 border-black p-8 shadow-[8px_8px_0px_0px_#000] text-center">
          <p className="text-xl font-bold">
            Für die aktuell gewählte Richtung liegen noch keine Karten vor.
          </p>
          <p className="mt-2 text-gray-600">Importiere Anki-Karten oder wähle eine andere Richtung aus.</p>
        </div>
      ) : (
        <>
          <div className="bg-white border-4 border-black shadow-[8px_8px_0px_0px_#000]">
            <div className="border-b-4 border-black p-4 bg-gray-50">
              <h2 className="text-xl font-black uppercase">Verteilung nach Lernphasen ({directionLabels[direction]})</h2>
            </div>
            <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
              <div className="h-64 border-2 border-black p-4 shadow-[4px_4px_0px_0px_#000] bg-white rounded-none">
                <AnkiStagePie data={chartData} />
              </div>
              <div className="space-y-4">
                {stageOrder.map((stage) => (
                  <div key={stage} className="flex items-center justify-between text-base border-b-2 border-black/10 pb-2 last:border-0 hover:pl-2 transition-all">
                    <span className="font-bold uppercase tracking-wide">{stageDisplay[stage]}</span>
                    <span className="font-black text-xl tabular-nums bg-bauhaus-yellow px-2 border border-black shadow-[2px_2px_0px_0px_#000]">
                      {formatNumber(directionSummary.stage_counts[stage])}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {direction === 'all' ? (
            <div className="bg-bauhaus-yellow border-4 border-black p-6 shadow-[8px_8px_0px_0px_#000] text-center">
              <p className="font-bold text-lg">
                Wähle oben eine konkrete Richtung aus, um die einzelnen Karten inklusive Fortschritt anzuzeigen.
              </p>
            </div>
          ) : (
            <CollapsibleSection
              title="Vokabeln"
              icon={<Languages className="w-6 h-6 text-white" />}
              iconBgColor="bg-bauhaus-blue"
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
      <div className="mt-12 pt-8 border-t-8 border-black">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-black uppercase tracking-tight flex items-center gap-3">
              <div className="bg-bauhaus-red border-2 border-black p-1 shadow-[4px_4px_0px_0px_#000]">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              </div>
              Fehleranalyse
            </h2>
            <p className="text-lg font-bold text-gray-600 mt-2">
              Übersicht deiner Fehler mit Spaced Repetition Tracking.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-6 mb-8">
          <StatCard label="Gesamt" value={formatNumber(errorSummary.total_errors)} color="bg-white" />
          <StatCard label="Neu" value={formatNumber(errorSummary.stage_counts.new)} color="bg-bauhaus-red" textColor="text-white" />
          <StatCard label="In Bearbeitung" value={formatNumber(errorSummary.stage_counts.learning + errorSummary.stage_counts.relearning)} color="bg-bauhaus-yellow" />
          <StatCard label="Review" value={formatNumber(errorSummary.stage_counts.review)} color="bg-bauhaus-blue" textColor="text-white" />
          <StatCard label="Heute fällig" value={formatNumber(errorSummary.due_today)} color="bg-black" textColor="text-white" />
        </div>

        {errorSummary.total_errors === 0 ? (
          <div className="bg-green-100 border-4 border-black p-6 shadow-[8px_8px_0px_0px_#000]">
            <div className="flex items-center gap-4">
              <div className="bg-green-500 border-2 border-black p-2 shadow-[4px_4px_0px_0px_#000]">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-8 h-8 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
              </div>
              <p className="text-lg font-bold text-black">
                Ausgezeichnet! Du hast noch keine Fehler im System. Mach weiter so!
              </p>
            </div>
          </div>
        ) : (
          <div className="bg-white border-4 border-black shadow-[8px_8px_0px_0px_#000]">
            <div className="border-b-4 border-black p-4 bg-gray-50">
              <h3 className="text-xl font-black uppercase">Fehlerverteilung nach Kategorie</h3>
            </div>
            <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
              <div className="h-64 border-2 border-black p-4 shadow-[4px_4px_0px_0px_#000] bg-white">
                <ErrorCategoryPie data={errorSummary.categories.map(c => ({ category: c.category, value: c.count }))} />
              </div>
              <div className="space-y-4">
                {errorSummary.categories.length > 0 ? (
                  errorSummary.categories.map((cat) => (
                    <div key={cat.category} className="flex items-center justify-between text-base border-b-2 border-black/10 pb-2 last:border-0">
                      <span className="font-bold flex items-center gap-3">
                        <span className={`w-4 h-4 border-2 border-black shadow-[2px_2px_0px_0px_#000] ${cat.category === 'grammar' ? 'bg-bauhaus-red' :
                          cat.category === 'spelling' ? 'bg-orange-500' :
                            cat.category === 'vocabulary' ? 'bg-bauhaus-blue' :
                              cat.category === 'style' ? 'bg-purple-500' :
                                'bg-gray-500'
                          }`} />
                        <span className="uppercase tracking-wide">
                          {cat.category === 'grammar' ? 'Grammatik' :
                            cat.category === 'spelling' ? 'Rechtschreibung' :
                              cat.category === 'vocabulary' ? 'Wortschatz' :
                                cat.category === 'style' ? 'Stil' :
                                  cat.category}
                        </span>
                      </span>
                      <span className="font-black text-xl tabular-nums">{formatNumber(cat.count)}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-sm font-bold text-gray-500 italic">Keine Kategorien vorhanden.</p>
                )}
                <div className="pt-4 mt-4 border-t-4 border-black bg-green-50 p-4 -mx-2 shadow-[4px_4px_0px_0px_#000]">
                  <div className="flex items-center justify-between text-lg">
                    <span className="font-black uppercase">Gemeistert</span>
                    <span className="tabular-nums text-green-700 font-black text-2xl">{formatNumber(errorSummary.stage_counts.mastered)}</span>
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
              title="Gespeicherte Fehler"
              icon={<AlertCircle className="w-6 h-6 text-white" />}
              iconBgColor="bg-orange-500"
              defaultOpen={false}
              badge={errorList.total}
            >
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-black text-white font-bold uppercase tracking-wider text-xs border-b-4 border-black">
                    <tr>
                      <th className="px-4 py-3 border-r border-gray-700">Fehler</th>
                      <th className="px-4 py-3 border-r border-gray-700">Typ</th>
                      <th className="px-4 py-3 border-r border-gray-700">Korrektur</th>
                      <th className="px-4 py-3 border-r border-gray-700">Vorkommen</th>
                      <th className="px-4 py-3 border-r border-gray-700">Lapses</th>
                      <th className="px-4 py-3 border-r border-gray-700">Phase</th>
                      <th className="px-4 py-3">Nächste Review</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y-2 divide-black">
                    {errorList.items.map((item) => (
                      <tr key={item.id} className="hover:bg-bauhaus-yellow/20 transition-colors font-medium">
                        <td className="px-4 py-3 border-r-2 border-gray-200 font-bold text-red-700 max-w-[200px] truncate" title={item.original_text}>
                          {item.original_text}
                        </td>
                        <td className="px-4 py-3 border-r-2 border-gray-200">
                          <span className={`px-2 py-0.5 border border-black text-xs uppercase font-bold ${item.category === 'grammar' ? 'bg-red-100 text-red-800' :
                            item.category === 'spelling' ? 'bg-orange-100 text-orange-800' :
                              item.category === 'vocabulary' ? 'bg-blue-100 text-blue-800' :
                                'bg-gray-100'
                            }`}>
                            {subcategoryLabels[item.subcategory] || subcategoryLabels[item.category] || item.subcategory}
                          </span>
                        </td>
                        <td className="px-4 py-3 border-r-2 border-gray-200 text-green-700 font-medium max-w-[200px] truncate" title={item.correction || ''}>
                          {item.correction || '—'}
                        </td>
                        <td className="px-4 py-3 border-r-2 border-gray-200 tabular-nums text-center">{item.occurrences}</td>
                        <td className="px-4 py-3 border-r-2 border-gray-200 tabular-nums text-red-600 font-bold text-center">{item.lapses}</td>
                        <td className="px-4 py-3 border-r-2 border-gray-200">
                          <span className={`px-2 py-0.5 border border-black text-xs uppercase font-bold ${item.learning_stage === 'new' ? 'bg-blue-100 text-blue-800' :
                            item.learning_stage === 'learning' ? 'bg-yellow-100 text-yellow-800' :
                              item.learning_stage === 'review' ? 'bg-green-100 text-green-800' :
                                item.learning_stage === 'mastered' ? 'bg-green-500 text-white' :
                                  'bg-gray-100'
                            }`}>
                            {item.learning_stage === 'new' ? 'Neu' :
                              item.learning_stage === 'learning' ? 'Lernen' :
                                item.learning_stage === 'review' ? 'Review' :
                                  item.learning_stage === 'mastered' ? 'Gemeistert' : item.learning_stage}
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
      <div className="mt-12 pt-8 border-t-8 border-black">
        <div className="mb-8">
          <h2 className="text-3xl font-black uppercase tracking-tight flex items-center gap-3">
            <div className="bg-purple-500 border-2 border-black p-1 shadow-[4px_4px_0px_0px_#000]">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            Grammatik
          </h2>
          <p className="text-lg font-bold text-gray-600 mt-2">
            Dein Fortschritt bei den Grammatikkonzepten.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-6 mb-8">
          <StatCard label="Gesamt" value={formatNumber(grammarSummary.total)} color="bg-white" />
          <StatCard label="Nicht gestartet" value={formatNumber(grammarSummary.not_started)} color="bg-gray-200" />
          <StatCard label="In Bearbeitung" value={formatNumber(grammarSummary.in_progress)} color="bg-bauhaus-yellow" />
          <StatCard label="Gemeistert" value={formatNumber(grammarSummary.mastered)} color="bg-bauhaus-green" />
          <StatCard label="Heute fällig" value={formatNumber(grammarSummary.due_count)} color="bg-black" textColor="text-white" />
        </div>

        {grammarSummary.total === 0 ? (
          <div className="bg-white border-4 border-black p-8 shadow-[8px_8px_0px_0px_#000] text-center">
            <p className="text-xl font-bold">
              Noch keine Grammatikkonzepte im System.
            </p>
            <p className="mt-2 text-gray-600 font-bold">Beginne mit dem Grammatik-Training!</p>
          </div>
        ) : (
          <div className="bg-white border-4 border-black shadow-[8px_8px_0px_0px_#000] p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-black uppercase">Fortschrittsübersicht</h3>
              <Link href="/grammar" className="inline-block bg-bauhaus-blue text-white font-bold py-2 px-4 border-2 border-black shadow-[4px_4px_0px_0px_#000] hover:translate-x-1 hover:translate-y-1 hover:shadow-none transition-all">
                Zum Grammatik-Training →
              </Link>
            </div>
            <div className="w-full bg-gray-100 border-4 border-black h-8 overflow-hidden relative">
              <div className="h-full flex">
                <div
                  className="bg-green-500 border-r-2 border-black h-full"
                  style={{ width: `${grammarSummary.total > 0 ? (grammarSummary.mastered / grammarSummary.total) * 100 : 0}%` }}
                  title="Gemeistert"
                />
                <div
                  className="bg-bauhaus-yellow border-r-2 border-black h-full"
                  style={{ width: `${grammarSummary.total > 0 ? (grammarSummary.in_progress / grammarSummary.total) * 100 : 0}%` }}
                  title="In Bearbeitung"
                />
              </div>
            </div>
            <div className="flex justify-between text-xs font-bold uppercase mt-2 text-gray-600 tracking-wider">
              <span>0%</span>
              <span>{grammarSummary.total > 0 ? Math.round((grammarSummary.mastered / grammarSummary.total) * 100) : 0}% gemeistert</span>
              <span>100%</span>
            </div>
          </div>
        )}
      </div>

      {/* Grammar↔Error Synergy Section */}
      {errorSummary.total_errors > 0 && (
        <div className="mt-12 pt-8 border-t-8 border-black">
          <div className="mb-8">
            <h2 className="text-3xl font-black uppercase tracking-tight flex items-center gap-3">
              <div className="bg-orange-500 border-2 border-black p-1 shadow-[4px_4px_0px_0px_#000]">
                <Target className="w-6 h-6 text-white" />
              </div>
              Empfohlene Grammatik-Wiederholung
            </h2>
            <p className="text-lg font-bold text-gray-600 mt-2">
              Basierend auf deinen häufigsten Fehlern empfehlen wir diese Grammatikthemen.
            </p>
          </div>

          <CollapsibleSection
            title="Grammatik für deine Fehler"
            icon={<BookOpen className="w-6 h-6 text-white" />}
            iconBgColor="bg-purple-500"
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
        <p className="text-lg font-bold animate-pulse">Lade Empfehlungen...</p>
      </div>
    );
  }

  if (concepts.length === 0) {
    return (
      <div className="p-8 text-center bg-green-100 border-2 border-black">
        <p className="text-lg font-bold">Großartig! Keine spezifischen Grammatikthemen nötig.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {concepts.map((item: any) => (
        <div
          key={item.concept.id}
          className="bg-white border-4 border-black p-6 shadow-[6px_6px_0px_0px_#000] hover:-translate-y-1 hover:shadow-[8px_8px_0px_0px_#000] transition-all"
        >
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <h3 className="text-xl font-black uppercase mb-2">{item.concept.name}</h3>
              <p className="text-sm text-gray-600 font-medium">{item.concept.description}</p>
            </div>
            <span className="ml-4 px-3 py-1 bg-bauhaus-blue text-white font-bold text-sm border-2 border-black shadow-[3px_3px_0px_0px_#000]">
              {item.concept.level}
            </span>
          </div>

          <div className="mb-4">
            <p className="text-xs font-bold uppercase text-gray-500 mb-2">Deine Fehler in diesem Bereich:</p>
            <div className="flex flex-wrap gap-2">
              {item.error_patterns.map((pattern: string, idx: number) => (
                <span
                  key={idx}
                  className="px-2 py-1 bg-red-100 text-red-800 text-xs font-bold border border-black"
                >
                  {subcategoryLabels[pattern] || pattern}
                </span>
              ))}
            </div>
          </div>

          <Link
            href={`/grammar`}
            className="inline-block bg-purple-500 text-white font-bold py-2 px-4 border-2 border-black shadow-[4px_4px_0px_0px_#000] hover:translate-x-1 hover:translate-y-1 hover:shadow-none transition-all uppercase text-sm"
          >
            Jetzt üben →
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
    <div className="bg-white border-4 border-black shadow-[8px_8px_0px_0px_#000] overflow-hidden">
      <div className="flex items-center justify-between p-4 border-b-4 border-black bg-gray-50">
        <h2 className="text-xl font-black uppercase">{directionLabels[direction]}</h2>
        {loading && <span className="text-sm font-bold bg-bauhaus-yellow px-2 border border-black animate-pulse">AKTUALISIERE...</span>}
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-black text-white font-bold uppercase tracking-wider text-xs border-b-4 border-black">
            <tr>
              <th className="px-4 py-3 border-r border-gray-700">Wort</th>
              <th className="px-4 py-3 border-r border-gray-700">Übersetzung</th>
              <th className="px-4 py-3 border-r border-gray-700">Phase</th>
              <th className="px-4 py-3 border-r border-gray-700">Level</th>
              <th className="px-4 py-3 border-r border-gray-700">Ease</th>
              <th className="px-4 py-3 border-r border-gray-700">Intervall</th>
              <th className="px-4 py-3 border-r border-gray-700">Fällig</th>
              <th className="px-4 py-3 border-r border-gray-700">Reps</th>
              <th className="px-4 py-3 border-r border-gray-700">Fehler</th>
              <th className="px-4 py-3 border-r border-gray-700">Skill</th>
              <th className="px-4 py-3">Deck</th>
            </tr>
          </thead>
          <tbody className="divide-y-2 divide-black">
            {entries.length === 0 ? (
              <tr>
                <td colSpan={11} className="px-4 py-8 text-center text-lg font-bold text-gray-500">
                  Keine Karten für diese Richtung vorhanden.
                </td>
              </tr>
            ) : (
              entries.map((item) => (
                <tr key={item.word_id} className="hover:bg-bauhaus-yellow/20 transition-colors font-medium text-black">
                  <td className="px-4 py-3 border-r-2 border-gray-200 font-bold">{item.word}</td>
                  <td className="px-4 py-3 border-r-2 border-gray-200 text-gray-700">{translationFor(item)}</td>
                  <td className="px-4 py-3 border-r-2 border-gray-200">
                    <span className={`px-2 py-0.5 border border-black text-xs uppercase font-bold ${item.learning_stage === 'new' ? 'bg-blue-100 text-blue-800' :
                      item.learning_stage === 'learning' ? 'bg-yellow-100 text-yellow-800' :
                        item.learning_stage === 'review' ? 'bg-green-100 text-green-800' :
                          'bg-gray-100'
                      }`}>
                      {stageDisplay[item.learning_stage?.toLowerCase()] || item.learning_stage}
                    </span>
                  </td>
                  <td className="px-4 py-3 border-r-2 border-gray-200 tabular-nums">{formatNumber(item.progress_difficulty)}</td>
                  <td className="px-4 py-3 border-r-2 border-gray-200 tabular-nums">{formatNumber(item.ease_factor)}</td>
                  <td className="px-4 py-3 border-r-2 border-gray-200 tabular-nums">{formatNumber(item.interval_days)}</td>
                  <td className="px-4 py-3 border-r-2 border-gray-200 tabular-nums font-mono text-xs">{formatDate(item.due_at || item.next_review)}</td>
                  <td className="px-4 py-3 border-r-2 border-gray-200 tabular-nums">{item.reps ?? 0}</td>
                  <td className="px-4 py-3 border-r-2 border-gray-200 tabular-nums text-red-600 font-bold">{item.lapses ?? 0}</td>
                  <td className="px-4 py-3 border-r-2 border-gray-200 tabular-nums">{item.proficiency_score ?? 0}</td>
                  <td className="px-4 py-3 text-gray-500 italic truncate max-w-[150px]">{item.deck_name || '—'}</td>
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

function StatCard({ label, value, color = 'bg-white', textColor = 'text-black' }: StatCardProps) {
  return (
    <div className={`${color} ${textColor} border-4 border-black p-4 shadow-[8px_8px_0px_0px_#000] hover:-translate-y-2 hover:shadow-[12px_12px_0px_0px_#000] transition-all duration-200`}>
      <p className={`text-xs uppercase font-black tracking-widest opacity-80 mb-2`}>{label}</p>
      <p className="text-3xl font-black">{value}</p>
    </div>
  );
}

export async function getServerSideProps(ctx: any) {
  const session = await getSession(ctx);
  if (!session) return { redirect: { destination: '/auth/signin', permanent: false } };

  const headers = { Authorization: `Bearer ${session.accessToken}` } as any;
  const rawBase =
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.API_URL ||
    'http://localhost:8000/api/v1';
  const normalizedBase = rawBase.replace(/\/+$/, '');
  const baseUrl = normalizedBase.endsWith('/api/v1')
    ? normalizedBase
    : `${normalizedBase}/api/v1`;

  const [summaryRes, progressRes, errorSummaryRes, errorListRes, grammarSummaryRes] = await Promise.all([
    fetch(`${baseUrl}/progress/anki/summary`, { headers }),
    fetch(`${baseUrl}/progress/anki?direction=fr_to_de`, { headers }),
    fetch(`${baseUrl}/analytics/errors/summary`, { headers }),
    fetch(`${baseUrl}/analytics/errors/list`, { headers }),
    fetch(`${baseUrl}/grammar/summary`, { headers }),
  ]);

  const summary = summaryRes.ok ? await summaryRes.json() : { total_cards: 0, due_today: 0, stage_totals: {}, chart: [], directions: {} };
  const initialProgress = progressRes.ok ? await progressRes.json() : [];
  const errorSummary = errorSummaryRes.ok ? await errorSummaryRes.json() : { total_errors: 0, due_today: 0, stage_counts: { new: 0, learning: 0, review: 0, relearning: 0, mastered: 0 }, categories: [] };
  const errorList = errorListRes.ok ? await errorListRes.json() : { total: 0, items: [] };
  const grammarSummary = grammarSummaryRes.ok ? await grammarSummaryRes.json() : { total: 0, mastered: 0, in_progress: 0, not_started: 0, due_count: 0 };

  return { props: { summary, initialProgress, errorSummary, errorList, grammarSummary } };
}



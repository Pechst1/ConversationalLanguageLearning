import React, { useMemo, useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { getSession } from 'next-auth/react';
import api from '@/services/api';

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

type ProgressPageProps = {
  summary: AnkiProgressSummary;
  initialProgress: AnkiWordProgress[];
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

export default function ProgressPage({ summary, initialProgress }: ProgressPageProps) {
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

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Dein Lernfortschritt</h1>
          <p className="text-sm text-gray-600">
            Übersicht aller importierten Anki-Karten. Wähle die gewünschte Richtung aus, um Details zu sehen.
          </p>
        </div>
        <div className="flex gap-2">
          {(['fr_to_de', 'de_to_fr', 'all'] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setDirection(option)}
              className={`rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
                direction === option
                  ? 'border-blue-600 bg-blue-50 text-blue-700'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300 hover:text-gray-900'
              }`}
            >
              {directionLabels[option]}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <StatCard label="Gesamt" value={formatNumber(directionSummary.total)} />
        <StatCard label="Neu" value={formatNumber(directionSummary.stage_counts.new)} />
        <StatCard label="In Bearbeitung" value={formatNumber(directionSummary.stage_counts.learning)} />
        <StatCard label="Review" value={formatNumber(directionSummary.stage_counts.review)} />
        <StatCard label="Heute fällig" value={formatNumber(directionSummary.due_today)} />
      </div>

      {directionSummary.total === 0 ? (
        <div className="learning-card">
          <p className="text-sm text-gray-600">
            Für die aktuell gewählte Richtung liegen noch keine Karten vor. Importiere Anki-Karten oder wähle eine andere
            Richtung aus.
          </p>
        </div>
      ) : (
        <>
          <div className="learning-card">
            <h2 className="text-lg font-semibold mb-3">Verteilung nach Lernphasen ({directionLabels[direction]})</h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="h-64">
                <AnkiStagePie data={chartData} />
              </div>
              <div className="space-y-3">
                {stageOrder.map((stage) => (
                  <div key={stage} className="flex items-center justify-between text-sm text-gray-700">
                    <span className="font-medium">{stageDisplay[stage]}</span>
                    <span className="tabular-nums">{formatNumber(directionSummary.stage_counts[stage])}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {direction === 'all' ? (
            <div className="learning-card">
              <p className="text-sm text-gray-600">
                Wähle oben eine konkrete Richtung aus, um die einzelnen Karten inklusive Fortschritt anzuzeigen.
              </p>
            </div>
          ) : (
            <ProgressTable
              direction={direction}
              entries={entries}
              loading={loading}
            />
          )}
        </>
      )}
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
    <div className="learning-card overflow-auto">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold">{directionLabels[direction]}</h2>
        {loading && <span className="text-xs text-gray-500">Aktualisiere…</span>}
      </div>
      <table className="min-w-full text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-gray-500">
          <tr>
            <th className="px-3 py-2">Wort</th>
            <th className="px-3 py-2">Übersetzung</th>
            <th className="px-3 py-2">Phase</th>
            <th className="px-3 py-2">Schwierigkeit</th>
            <th className="px-3 py-2">Ease</th>
            <th className="px-3 py-2">Intervall (Tage)</th>
            <th className="px-3 py-2">Fälligkeit</th>
            <th className="px-3 py-2">Reps</th>
            <th className="px-3 py-2">Fehler</th>
            <th className="px-3 py-2">Skill</th>
            <th className="px-3 py-2">Deck</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {entries.length === 0 ? (
            <tr>
              <td colSpan={11} className="px-3 py-6 text-center text-sm text-gray-500">
                Keine Karten für diese Richtung vorhanden.
              </td>
            </tr>
          ) : (
            entries.map((item) => (
              <tr key={item.word_id} className="hover:bg-gray-50">
                <td className="px-3 py-2 font-medium text-gray-900">{item.word}</td>
                <td className="px-3 py-2 text-gray-700">{translationFor(item)}</td>
                <td className="px-3 py-2">{stageDisplay[item.learning_stage?.toLowerCase()] || item.learning_stage}</td>
                <td className="px-3 py-2">{formatNumber(item.progress_difficulty)}</td>
                <td className="px-3 py-2">{formatNumber(item.ease_factor)}</td>
                <td className="px-3 py-2">{formatNumber(item.interval_days)}</td>
                <td className="px-3 py-2">{formatDate(item.due_at || item.next_review)}</td>
                <td className="px-3 py-2">{item.reps ?? 0}</td>
                <td className="px-3 py-2">{item.lapses ?? 0}</td>
                <td className="px-3 py-2">{item.proficiency_score ?? 0}</td>
                <td className="px-3 py-2 text-gray-500">{item.deck_name || '—'}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

type StatCardProps = {
  label: string;
  value: string;
};

function StatCard({ label, value }: StatCardProps) {
  return (
    <div className="learning-card text-center">
      <p className="text-xs uppercase text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
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

  const [summaryRes, progressRes] = await Promise.all([
    fetch(`${baseUrl}/progress/anki/summary`, { headers }),
    fetch(`${baseUrl}/progress/anki?direction=fr_to_de`, { headers }),
  ]);

  const summary = summaryRes.ok ? await summaryRes.json() : { total_cards: 0, due_today: 0, stage_totals: {}, chart: [], directions: {} };
  const initialProgress = progressRes.ok ? await progressRes.json() : [];

  return { props: { summary, initialProgress } };
}

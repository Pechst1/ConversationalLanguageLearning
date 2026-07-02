import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { ArrowLeft, Check, Loader2, RotateCcw } from 'lucide-react';
import toast from 'react-hot-toast';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import apiService, { ConjugationReviewItem } from '@/services/api';

const ratingOptions = [
  { rating: 0, label: 'Again', hint: 'Soon', tone: 'red' },
  { rating: 1, label: 'Hard', hint: 'Keep close', tone: 'yellow' },
  { rating: 2, label: 'Good', hint: 'Schedule', tone: 'blue' },
  { rating: 3, label: 'Easy', hint: 'Stretch', tone: 'black' },
] as const;

function normalizeAnswer(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^A-Za-z0-9À-ÿ]+/g, ' ')
    .trim()
    .toLowerCase();
}

function nextReviewLabel(value?: string | null) {
  if (!value) return 'Review saved';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Review saved';
  return `Next touch ${date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`;
}

export default function ConjugationReviewPage() {
  const [items, setItems] = useState<ConjugationReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [typed, setTyped] = useState('');
  const [revealed, setRevealed] = useState(false);
  const [completed, setCompleted] = useState(0);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const queue = await apiService.getConjugationReview({ limit: 18 });
      setItems(queue.items || []);
      setTyped('');
      setRevealed(false);
      setCompleted(0);
    } catch (nextError) {
      console.error(nextError);
      setError('Conjugation drill is unavailable right now.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const current = items[0] || null;
  const typedMatches = current ? normalizeAnswer(typed) === normalizeAnswer(current.answer) : false;
  const progress = useMemo(() => {
    const total = completed + items.length;
    return total ? Math.round((completed / total) * 100) : 0;
  }, [completed, items.length]);

  const submitRating = async (rating: number) => {
    if (!current || saving) return;
    setSaving(true);
    try {
      const result = await apiService.submitConjugationReview({
        lemma: current.lemma,
        tense: current.tense,
        rating,
      });
      toast.success(nextReviewLabel(result.next_review));
      setItems((previous) => previous.slice(1));
      setCompleted((value) => value + 1);
      setTyped('');
      setRevealed(false);
    } catch (nextError) {
      console.error(nextError);
      toast.error('Could not save conjugation review.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Head>
        <title>Conjugation Drill</title>
      </Head>
      <EditorialMasthead active="notebook" mobileAction={<Link className="conj-mobile-action" href="/vocabulary">Map</Link>} />
      <main className="conj-page">
        <header className="conj-hero">
          <Link href="/vocabulary" className="conj-back"><ArrowLeft size={15} /> Coverage map</Link>
          <span>Verbs & conjugation</span>
          <h1>Irregular forms</h1>
          <div className="conj-progress">
            <strong>{completed} reviewed</strong>
            <div aria-label={`${progress}% complete`}><i style={{ width: `${progress}%` }} /></div>
            <em>{items.length} waiting</em>
          </div>
        </header>

        {loading && (
          <section className="conj-state">
            <Loader2 className="spin" size={20} />
            <strong>Loading conjugation drill.</strong>
          </section>
        )}

        {!loading && error && (
          <section className="conj-state error">
            <strong>{error}</strong>
            <button type="button" onClick={loadQueue}><RotateCcw size={14} /> Retry</button>
          </section>
        )}

        {!loading && !error && !current && (
          <section className="conj-state done">
            <Check size={24} />
            <strong>No irregular forms waiting.</strong>
            <Link href="/vocabulary/review">Review vocabulary</Link>
          </section>
        )}

        {!loading && !error && current && (
          <section className="conj-card">
            <div className="conj-card-head">
              <span>{current.cefr_band} · {current.tense_label}</span>
              <em>{current.state}</em>
            </div>
            <div className="conj-prompt">
              <span>Prompt</span>
              <h2>{current.lemma} · {current.tense_label} · {current.person}</h2>
              <input
                value={typed}
                onChange={(event) => setTyped(event.target.value)}
                placeholder="Type the form"
                aria-label="Type the conjugated form"
              />
              <button type="button" onClick={() => setRevealed(true)} disabled={!typed.trim()}>
                Reveal table
              </button>
            </div>

            {revealed && (
              <div className="conj-answer">
                <div className={typedMatches ? 'conj-verdict match' : 'conj-verdict miss'}>
                  <strong>{current.answer}</strong>
                  <span>{typedMatches ? 'Matched' : `You typed: ${typed}`}</span>
                </div>
                <table>
                  <tbody>
                    {current.table.map((row) => (
                      <tr key={`${row.person}-${row.form}`} className={row.person === current.person ? 'target' : ''}>
                        <th>{row.person}</th>
                        <td>{row.form}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="conj-ratings" aria-label="Conjugation rating">
              {ratingOptions.map((option) => (
                <button
                  key={option.rating}
                  type="button"
                  className={option.tone}
                  disabled={saving || !revealed}
                  onClick={() => submitRating(option.rating)}
                >
                  <strong>{option.label}</strong>
                  <span>{option.hint}</span>
                </button>
              ))}
            </div>
          </section>
        )}
      </main>
      <style jsx>{`
        .conj-page {
          --paper: #f1ece1;
          --paper-2: #e8e0cf;
          --sheet: #f8f3e8;
          --ink: #14110d;
          --ink-2: #4a4538;
          --ink-3: #8a826f;
          --red: #d8321a;
          --blue: #1d3a8a;
          --yellow: #f3c318;
          --disabled-bg: #98958c;
          --disabled-ink: #f8f3e8;
          min-height: 100vh;
          background: var(--paper);
          color: var(--ink);
          padding: 24px clamp(18px, 4vw, 48px) 96px;
        }
        .conj-back,
        .conj-mobile-action,
        .conj-hero > span,
        .conj-card-head,
        .conj-prompt > span,
        .conj-verdict span,
        .conj-ratings span {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: .1em;
          text-transform: uppercase;
        }
        .conj-back,
        .conj-mobile-action {
          display: inline-flex;
          min-height: 30px;
          align-items: center;
          gap: 7px;
          color: var(--ink);
          text-decoration: none;
        }
        .conj-hero {
          display: grid;
          gap: 10px;
          border-bottom: 1px solid var(--ink);
          padding-bottom: 18px;
        }
        .conj-hero h1 {
          margin: 0;
          color: var(--ink);
          font-family: "EB Garamond", Garamond, serif;
          font-size: clamp(44px, 9vw, 82px);
          font-style: italic;
          line-height: .95;
          letter-spacing: 0;
        }
        .conj-progress {
          display: grid;
          grid-template-columns: auto minmax(120px, 320px) auto;
          align-items: center;
          gap: 12px;
          color: var(--ink);
        }
        .conj-progress div {
          height: 8px;
          border: 1px solid var(--ink);
          background: var(--paper-2);
        }
        .conj-progress i {
          display: block;
          height: 100%;
          background: var(--red);
        }
        .conj-card,
        .conj-state {
          max-width: 760px;
          margin: 22px auto 0;
          border: 1px solid var(--ink);
          background: var(--sheet);
          padding: 16px;
        }
        .conj-state {
          display: grid;
          min-height: 180px;
          place-items: center;
          text-align: center;
        }
        .conj-state button,
        .conj-state a,
        .conj-prompt button {
          display: inline-flex;
          min-height: 42px;
          align-items: center;
          justify-content: center;
          gap: 8px;
          border: 1px solid var(--ink);
          background: var(--ink);
          color: var(--sheet);
          padding: 0 14px;
          font-weight: 900;
          text-decoration: none;
        }
        .conj-card-head {
          display: flex;
          justify-content: space-between;
          color: var(--ink-2);
        }
        .conj-hero > span,
        .conj-prompt > span,
        .conj-verdict span,
        .conj-ratings span {
          color: var(--ink-2);
        }
        .conj-ratings .black span {
          color: var(--sheet);
        }
        .conj-prompt {
          display: grid;
          gap: 12px;
          margin-top: 18px;
          border-top: 1px solid var(--ink);
          padding-top: 18px;
          text-align: center;
        }
        .conj-prompt h2 {
          margin: 0;
          color: var(--ink);
          font-size: clamp(30px, 7vw, 56px);
          font-weight: 950;
          line-height: 1;
          letter-spacing: 0;
          overflow-wrap: anywhere;
        }
        .conj-prompt input {
          width: min(100%, 420px);
          min-height: 52px;
          margin: 0 auto;
          border: 2px solid var(--ink);
          background: var(--paper);
          padding: 0 14px;
          color: var(--ink);
          font-size: 20px;
          font-weight: 900;
          text-align: center;
        }
        .conj-prompt input::placeholder {
          color: var(--ink-2);
          opacity: 1;
        }
        .conj-prompt button {
          width: min(100%, 240px);
          margin: 0 auto;
        }
        .conj-prompt button:disabled {
          background: var(--disabled-bg);
          color: var(--disabled-ink);
          cursor: not-allowed;
          opacity: 1;
        }
        .conj-answer {
          display: grid;
          gap: 12px;
          margin-top: 16px;
        }
        .conj-verdict {
          border: 1px solid var(--ink);
          background: var(--paper);
          padding: 12px;
          text-align: center;
        }
        .conj-verdict.match {
          border-color: var(--blue);
        }
        .conj-verdict.miss {
          border-color: var(--red);
        }
        .conj-verdict strong {
          display: block;
          font-size: 28px;
        }
        table {
          width: 100%;
          border-collapse: collapse;
          background: var(--paper);
        }
        th,
        td {
          border: 1px solid var(--ink);
          padding: 10px 12px;
          text-align: left;
        }
        th {
          width: 34%;
          color: var(--ink-3);
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 11px;
          text-transform: uppercase;
        }
        tr.target th,
        tr.target td {
          background: var(--yellow);
        }
        .conj-ratings {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 8px;
          margin-top: 16px;
        }
        .conj-ratings button {
          min-height: 58px;
          border: 1px solid var(--ink);
          background: var(--paper);
          color: var(--ink);
          text-align: left;
          padding: 8px;
        }
        .conj-ratings strong,
        .conj-ratings span {
          display: block;
        }
        .conj-ratings .red { box-shadow: inset 4px 0 0 var(--red); }
        .conj-ratings .yellow { box-shadow: inset 4px 0 0 var(--yellow); }
        .conj-ratings .blue { box-shadow: inset 4px 0 0 var(--blue); }
        .conj-ratings .black {
          background: var(--ink);
          color: var(--sheet);
        }
        .conj-ratings button:disabled {
          background: var(--paper);
          color: var(--ink-2);
          cursor: not-allowed;
          opacity: 1;
        }
        .conj-ratings button:disabled.black {
          background: var(--disabled-bg);
          color: var(--disabled-ink);
        }
        .conj-ratings button:disabled.black span {
          color: var(--disabled-ink);
        }
        .spin {
          animation: spin .7s linear infinite;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @media (max-width: 640px) {
          .conj-page {
            padding: 16px 16px 96px;
          }
          .conj-progress,
          .conj-ratings {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
          .conj-progress div {
            grid-column: 1 / -1;
          }
          .conj-card,
          .conj-state {
            margin-top: 16px;
          }
        }
      `}</style>
    </>
  );
}

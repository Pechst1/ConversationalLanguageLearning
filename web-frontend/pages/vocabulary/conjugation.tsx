import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import toast from 'react-hot-toast';

import {
  Action,
  AtelierV2Root,
  CrossIcon,
  FeedbackBand,
  IconAction,
  ProgressRule,
  ShapeToken,
  StateBlock,
  Surface,
} from '@/components/atelier-v2/ui';
import apiService, { ConjugationReviewItem } from '@/services/api';

/* "Les formes irrégulières" — the conjugation drill, on the Claude design
 * system (Atelier V2).
 *
 * The design has no artboard for this screen. It is extended from the Séance
 * artboard: the same session chrome (round close control, blue progress rule),
 * one Garamond-italic headline (the form being asked), one answer field, one
 * 3D-press primary ("Voir le tableau"), the tinted feedback band for the
 * verdict, and the conjugation table drawn as the Séance's choice cards with
 * the asked person carried in blue. The four FSRS grades keep their exact
 * ratings (0–3) and their French labels; they are secondary presses so the
 * screen has one primary. Tabs are hidden as on every drill screen; the close
 * control returns to the registre. Recorded as an extension in the report. */

const ratingOptions = [
  { rating: 0, label: 'À revoir', hint: 'Très bientôt', shape: 'action' },
  { rating: 1, label: 'Difficile', hint: 'Garder près', shape: 'reward' },
  { rating: 2, label: 'Correct', hint: 'Rythme normal', shape: 'story' },
  { rating: 3, label: 'Facile', hint: 'Espacer', shape: 'done' },
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
  if (!value) return 'Reprise classée';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Reprise classée';
  return `Reprise le ${date.toLocaleDateString('fr-FR', { month: 'long', day: 'numeric' })}`;
}

export default function ConjugationReviewPage() {
  const router = useRouter();
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
      setError('L’exercice de conjugaison ne répond pas pour l’instant.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const current = items[0] || null;
  const typedMatches = current ? normalizeAnswer(typed) === normalizeAnswer(current.answer) : false;
  const total = completed + items.length;
  const progress = useMemo(() => (total ? Math.round((completed / total) * 100) : 0), [completed, total]);

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
      toast.error('La reprise n’a pas pu être classée.');
    } finally {
      setSaving(false);
    }
  };

  const caption = total ? `${completed}/${total}` : undefined;

  return (
    <>
      <Head>
        <title>Le Cahier · Conjugaison · L’Atelier</title>
      </Head>
      <AtelierV2Root as="main" className="lx-conj" aria-label="Les formes irrégulières">
        <div className="av2-screen">
          <header className="av2-session__head">
            <IconAction label="Revenir au registre" onClick={() => void router.push('/vocabulary')}>
              <CrossIcon size={16} />
            </IconAction>
            <ProgressRule value={completed} max={total} label={`${progress}% du tour`} caption={caption} />
          </header>

          <div className="av2-screen__body">
            <p className="av2-label">
              Les formes irrégulières
              {current ? ` · ${current.cefr_band} · ${current.tense_label}` : ''}
            </p>

            {loading && <StateBlock tone="loading" title="L’exercice se prépare." />}

            {!loading && error && (
              <StateBlock
                tone="error"
                title={error}
                action={{ label: 'Réessayer', onSelect: () => void loadQueue() }}
              />
            )}

            {!loading && !error && !current && (
              <>
                <StateBlock
                  tone="empty"
                  title="Aucune forme irrégulière en attente."
                  body={completed ? `${completed} ${completed === 1 ? 'forme reprise' : 'formes reprises'} ce tour.` : undefined}
                />
                <Link className="av2-btn av2-btn--primary" href="/vocabulary/review">
                  <ShapeToken kind="action" size="sm" /> Reprendre le vocabulaire
                </Link>
              </>
            )}

            {!loading && !error && current && (
              <>
                {/* the one Garamond-italic headline on this screen */}
                <h1 className="av2-headline lx-conj__prompt">
                  {current.lemma} · {current.tense_label} · {current.person}
                </h1>

                <label className="av2-field">
                  <span className="av2-field__label">La forme conjuguée</span>
                  <input
                    className="av2-field__control lx-input"
                    lang="fr"
                    value={typed}
                    onChange={(event) => setTyped(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && typed.trim() && !revealed) {
                        event.preventDefault();
                        setRevealed(true);
                      }
                    }}
                    placeholder="Écrivez la forme"
                    aria-label="Écrivez la forme conjuguée"
                    autoComplete="off"
                    autoCapitalize="off"
                  />
                </label>

                {!revealed && (
                  /* the one tactile 3D press on this screen */
                  <Action tone="primary" disabled={!typed.trim()} onClick={() => setRevealed(true)}>
                    Voir le tableau
                  </Action>
                )}

                {revealed && (
                  <>
                    <Surface shape="hero" className="av2-graded" data-state={typedMatches ? 'correct' : 'wrong'}>
                      <FeedbackBand
                        tone={typedMatches ? 'correct' : 'wrong'}
                        title={current.answer}
                        detail={typedMatches ? 'Juste' : `Vous avez écrit : ${typed}`}
                      />
                    </Surface>

                    <ul className="av2-choices lx-conj__table" aria-label={`${current.lemma} · ${current.tense_label}`}>
                      {current.table.map((row) => {
                        const target = row.person === current.person;
                        return (
                          <li
                            key={`${row.person}-${row.form}`}
                            className="av2-choice lx-conj__row"
                            data-state={target ? 'selected' : undefined}
                            aria-current={target ? 'true' : undefined}
                          >
                            <span className="lx-conj__person">{row.person}</span>
                            <span className="lx-conj__form">{row.form}</span>
                            <span className="av2-choice__dot" aria-hidden="true" />
                          </li>
                        );
                      })}
                    </ul>

                    <div className="lx-conj__ratings" role="group" aria-label="Classement de la forme">
                      {ratingOptions.map((option) => (
                        <Action
                          key={option.rating}
                          tone="secondary"
                          pending={saving}
                          pendingLabel={option.label}
                          icon={<ShapeToken kind={option.shape} size="sm" />}
                          onClick={() => submitRating(option.rating)}
                          title={option.hint}
                        >
                          {option.label}
                          <span className="av2-sr"> · {option.hint}</span>
                        </Action>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      </AtelierV2Root>
      <style jsx global>{`
        body { background: var(--app-paper); }
        .av2.lx-conj {
          display: block;
          min-height: 100vh;
          max-width: 720px;
          margin: 0 auto;
          padding: 0 0 calc(24px + var(--av2-safe-bottom));
        }
        .av2 .lx-conj__prompt { font-size: var(--av2-t-head); }
        /* globals.css puts an !important 1px ruled border on every input; the
           design's field is a paper well with a 2px focus edge. */
        .av2 .lx-input {
          border: 2px solid transparent !important;
          border-radius: var(--av2-r-card) !important;
          box-shadow: none !important;
          background-color: var(--av2-card);
          min-height: max(var(--av2-tap), 3rem);
        }
        .av2 .lx-input:focus { border-color: var(--av2-blue) !important; box-shadow: none !important; outline: 0; }
        .av2 .lx-conj__table { gap: 6px; }
        .av2 .lx-conj__row { cursor: default; min-height: var(--av2-tap); padding: 0.5rem 1.125rem; }
        .av2 .lx-conj__row[data-state='selected'] { --av2-choice-face: var(--av2-card); }
        .av2 .lx-conj__person {
          flex: 0 0 34%;
          font-family: var(--av2-sans);
          font-style: normal;
          font-size: var(--av2-t-label);
          font-weight: 700;
          color: var(--av2-muted);
        }
        .av2 .lx-conj__row[data-state='selected'] .lx-conj__person { color: var(--av2-blue); }
        .av2 .lx-conj__form { flex: 1 1 auto; min-width: 0; }
        .av2 .lx-conj__ratings { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; min-width: 0; }
        .av2 .lx-conj__ratings .av2-btn { width: auto; }
        @media (max-width: 360px) {
          .av2 .lx-conj__ratings { grid-template-columns: minmax(0, 1fr); }
        }
      `}</style>
    </>
  );
}

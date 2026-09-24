import React, { useCallback, useEffect, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import {
  Action,
  ArrowRightIcon,
  AtelierV2Root,
  ShapeToken,
  Skeleton,
  StateBlock,
  Surface,
} from '@/components/atelier-v2/ui';
import {
  CahierHead,
  CahierStyles,
  NbSectionHead,
  NotebookModeTabs,
  cahierModeLabel,
  type CahierMode,
} from '@/components/cahiers/CahierV2';
import { cahierCopy, countLabel, fill, useCahierCopy, type CahierCopy } from '@/components/cahiers/cahier-copy';
import JournalTab from '@/components/cahiers/JournalTab';
import { NOTEBOOK_MODE_STORAGE_KEY } from '@/components/mobile';
import Releve from '@/components/releve/Releve';
import { Button } from '@/components/ui/Button';
import { ExerciseShell } from '@/components/ui/ExerciseShell';
import { FeedbackSheet } from '@/components/ui/FeedbackSheet';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { pulseAppHaptic } from '@/lib/haptics';
import { STORY_FEATURE_VISIBLE } from '@/lib/launch-flags';
import { useChromeLanguage } from '@/lib/learner-language';
import api, {
  type CEFRProgress,
  type GrammarProgressSummary,
  type GraphicNovelToday,
  type LibraryBook,
  type LibraryEpisode,
} from '@/services/api';

import { GrammarNotebookSurface } from './grammar';
import VocabularyPage from './vocabulary';

type NotebookQuery = Record<string, string | string[] | undefined>;
/* The Cahier's own tab set. `NotebookMode` in components/mobile still describes
   the retired mobile switch; Le Relevé is a Cahier tab, so the shell keeps its
   own union rather than widening the legacy one. */
type NotebookMode = CahierMode;
type LibraryExerciseKind = 'comprehension' | 'vocabulary' | 'grammar' | 'production';
type LibraryExerciseStep = {
  id: string;
  kind: LibraryExerciseKind;
  eyebrow: string;
  title: string;
  prompt: string;
  target?: string;
  evidence?: string;
  explanation?: string;
  criteria?: string[];
  inputMode: 'line' | 'paragraph';
};
type LibraryExerciseFeedback = {
  status: 'correct' | 'wrong';
  title: string;
  explanation: string;
  repair?: string;
  rule?: string;
};

function firstQueryValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

function storedNotebookMode(): NotebookMode {
  if (typeof window === 'undefined') return 'grammar';
  try {
    const stored = window.localStorage.getItem(NOTEBOOK_MODE_STORAGE_KEY);
    if (stored === 'vocabulary') return 'vocabulary';
    if (stored === 'journal') return 'journal';
    if (stored === 'releve') return 'releve';
    if (STORY_FEATURE_VISIBLE && stored === 'library') return 'library';
    return 'grammar';
  } catch {
    return 'grammar';
  }
}

function rememberNotebookMode(mode: NotebookMode) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(NOTEBOOK_MODE_STORAGE_KEY, mode);
  } catch {
    // Persisting the mode is a convenience; the notebook still works without it.
  }
}

function notebookModeFromQuery(query: NotebookQuery): NotebookMode | null {
  const explicitMode = firstQueryValue(query.mode);
  if (
    explicitMode === 'grammar'
    || explicitMode === 'vocabulary'
    || explicitMode === 'journal'
    || explicitMode === 'releve'
  ) return explicitMode;
  if (STORY_FEATURE_VISIBLE && explicitMode === 'library') return 'library';
  if (STORY_FEATURE_VISIBLE && firstQueryValue(query.book)) return 'library';
  if (firstQueryValue(query.word)) return 'vocabulary';
  if (firstQueryValue(query.concept) || firstQueryValue(query.review)) return 'grammar';
  return null;
}

function queryForMode(query: NotebookQuery, requestedMode: NotebookMode): NotebookQuery {
  const mode = !STORY_FEATURE_VISIBLE && requestedMode === 'library' ? 'grammar' : requestedMode;
  const nextQuery: NotebookQuery = { mode };
  const locale = firstQueryValue(query.locale);
  if (locale) nextQuery.locale = locale;

  if (mode === 'grammar') {
    const concept = firstQueryValue(query.concept) || firstQueryValue(query.review);
    if (concept) nextQuery.concept = concept;
  } else if (mode === 'releve' || mode === 'journal') {
    // Le Relevé is a read-only ledger and Le journal de bord is the learner's
    // own writing; neither carries deep-link parameters.
    return nextQuery;
  } else {
    if (mode === 'library') {
      const book = firstQueryValue(query.book);
      const episode = firstQueryValue(query.episode);
      if (book) nextQuery.book = book;
      if (episode) nextQuery.episode = episode;
      return nextQuery;
    }
    const word = firstQueryValue(query.word);
    if (word) nextQuery.word = word;
  }

  return nextQuery;
}

/* WP-82 — the document title is chrome: read from the Cahier copy table. */
const MODE_TITLE_KEYS: Record<NotebookMode, keyof CahierCopy['notebook']> = {
  grammar: 'title_grammar',
  vocabulary: 'title_vocabulary',
  journal: 'title_journal',
  releve: 'title_releve',
  library: 'title_library',
};

export default function NotebookEntryPage() {
  const router = useRouter();
  // WP-82: the Cahier's chrome is the learner's language up to A2, French from
  // B1; the root hands it to every Cahier primitive below.
  const language = useChromeLanguage();
  const t = cahierCopy(language);
  const [mode, setMode] = useState<NotebookMode>('grammar');
  const [cefr, setCefr] = useState<CEFRProgress | null>(null);
  const [grammarSummary, setGrammarSummary] = useState<GrammarProgressSummary | null>(null);
  const [feuilletonToday, setFeuilletonToday] = useState<GraphicNovelToday | null>(null);
  const queryConcept = router.query.concept;
  const queryMode = router.query.mode;
  const queryReview = router.query.review;
  const queryWord = router.query.word;
  const queryBook = router.query.book;
  const queryEpisode = router.query.episode;

  useEffect(() => {
    if (!router.isReady) return;
    const nextMode = notebookModeFromQuery({
      book: queryBook,
      concept: queryConcept,
      episode: queryEpisode,
      mode: queryMode,
      review: queryReview,
      word: queryWord,
    }) || storedNotebookMode();
    setMode(nextMode);
    rememberNotebookMode(nextMode);
  }, [queryBook, queryConcept, queryEpisode, queryMode, queryReview, queryWord, router.isReady]);

  useEffect(() => {
    let cancelled = false;
    api.getCefrProgress()
      .then((payload) => {
        if (!cancelled) setCefr(payload);
      })
      .catch(() => {
        if (!cancelled) setCefr(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // The design's kicker — "54 concepts · 12 vus" — is the learner's own
  // concept count from /grammar/summary, or nothing.
  useEffect(() => {
    let cancelled = false;
    (api.getGrammarSummary() as Promise<GrammarProgressSummary>)
      .then((payload) => {
        if (!cancelled) setGrammarSummary(payload);
      })
      .catch(() => {
        if (!cancelled) setGrammarSummary(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    api.getGraphicNovelToday()
      .then((payload) => {
        if (!cancelled) setFeuilletonToday(payload);
      })
      .catch(() => {
        if (!cancelled) setFeuilletonToday(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const switchMode = useCallback(
    (nextMode: NotebookMode) => {
      const resolvedMode = !STORY_FEATURE_VISIBLE && nextMode === 'library' ? 'grammar' : nextMode;
      if (resolvedMode !== mode) pulseAppHaptic('selection');
      setMode(resolvedMode);
      rememberNotebookMode(resolvedMode);
      if (!router.isReady) return;
      void router.push(
        { pathname: '/notebook', query: queryForMode(router.query, resolvedMode) },
        undefined,
        { shallow: true, scroll: false }
      );
    },
    [mode, router]
  );

  const visibleMode = !STORY_FEATURE_VISIBLE && mode === 'library' ? 'grammar' : mode;

  // The bound serial clipping at the top of the carnet — one line, or absent.
  const notebookFeuilleton = React.useMemo(() => {
    const scene = feuilletonToday?.active_scene
      || feuilletonToday?.available_scene
      || feuilletonToday?.recent_completed?.[0]
      || null;
    if (!scene) return null;
    const ep = typeof scene.episode_index === 'number' ? scene.episode_index + 1 : undefined;
    return {
      ep,
      title: scene.title || t.notebook.feuilleton_fallback,
      href: `/graphic-novel?scene=${encodeURIComponent(scene.id)}`,
    };
  }, [feuilletonToday, t]);

  // Kicker: real counts in the rules register, the CEFR line elsewhere.
  const cefrLine = cefr?.estimate ? fill(t.notebook.cefr_line, { level: cefr.estimate }) : null;
  const total = Number(grammarSummary?.total_concepts || 0);
  const started = Number(grammarSummary?.started || 0);
  const countsLine = total > 0
    ? `${countLabel(t.cahier, 'concepts', total)} · ${countLabel(t.cahier, 'seen', started)}`
    : null;
  const kicker = visibleMode === 'grammar' && countsLine
    ? [countsLine, cefrLine].filter(Boolean).join(' · ')
    : [cahierModeLabel(t, visibleMode), cefrLine].filter(Boolean).join(' · ');

  return (
    <>
      <Head>
        <title>{`${t.notebook[MODE_TITLE_KEYS[visibleMode]]} · L’Atelier`}</title>
      </Head>
      <CahierStyles />
      <AtelierV2Root as="main" language={language} className="nb-page" aria-label="Le cahier">
        <CahierHead kicker={kicker}>
          <NotebookModeTabs
            active={visibleMode}
            library={STORY_FEATURE_VISIBLE}
            onSelect={switchMode}
          />
        </CahierHead>
        <div className="nb-body">
          {notebookFeuilleton && (
            <Link className="av2-row nb-feuille" href={notebookFeuilleton.href}>
              <ShapeToken kind="story" size="lg" />
              <span className="av2-row__main">
                <span className="av2-label av2-label--story">{t.cahier.feuilleton_filed}</span>
                <span className="nb-feuille__title" lang="fr">
                  {notebookFeuilleton.ep != null ? fill(t.cahier.episode_prefix, { n: notebookFeuilleton.ep }) : ''}{notebookFeuilleton.title}
                </span>
              </span>
              <ArrowRightIcon size={18} />
            </Link>
          )}
          <section key={visibleMode} className="nb-embed" data-mode={visibleMode}>
            {visibleMode === 'grammar' ? (
              <GrammarNotebookSurface embedded />
            ) : visibleMode === 'vocabulary' ? (
              <VocabularyPage embedded />
            ) : visibleMode === 'journal' ? (
              <JournalTab />
            ) : visibleMode === 'releve' ? (
              <Releve />
            ) : (
              <LibraryNotebookSurface
                bookId={firstQueryValue(queryBook)}
                episodeIndex={firstQueryValue(queryEpisode)}
              />
            )}
          </section>
        </div>
      </AtelierV2Root>
      <PhoneProductNav active="notebook" placement="embedded" />
    </>
  );
}

function normalizeLibraryAnswer(value: unknown) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[’`]/g, "'")
    .replace(/[.!?;:,«»]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function libraryWordCount(value: string) {
  return value.trim().split(/\s+/).filter(Boolean).length;
}

function excerpt(value: unknown, maxLength = 180) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1).trim()}...`;
}

function libraryExerciseSteps(payload: Record<string, any> | null | undefined, t: CahierCopy['library']): LibraryExerciseStep[] {
  const comprehension = Array.isArray(payload?.comprehension) ? payload.comprehension : [];
  const vocabulary = Array.isArray(payload?.vocabulary) ? payload.vocabulary : [];
  const grammar = Array.isArray(payload?.grammar) ? payload.grammar : [];
  const production = payload?.production && typeof payload.production === 'object' ? payload.production : null;
  return [
    ...comprehension.slice(0, 2).map((item: any, index: number): LibraryExerciseStep => ({
      id: `comprehension-${index}`,
      kind: 'comprehension',
      eyebrow: t.comprehension,
      title: fill(t.comprehension_title, { n: index + 1 }),
      prompt: String(item.question || t.comprehension_prompt),
      target: String(item.answer || ''),
      evidence: String(item.evidence || ''),
      inputMode: 'paragraph',
    })),
    ...vocabulary.slice(0, 2).map((item: any, index: number): LibraryExerciseStep => ({
      id: `vocabulary-${index}`,
      kind: 'vocabulary',
      eyebrow: t.lexique,
      title: String(item.word || fill(t.word_title, { n: index + 1 })),
      prompt: fill(t.vocabulary_prompt, { hint: item.gloss_hint || t.vocabulary_hint }),
      target: String(item.word || ''),
      evidence: String(item.context_sentence || ''),
      inputMode: 'line',
    })),
    ...grammar.slice(0, 1).map((item: any, index: number): LibraryExerciseStep => ({
      id: `grammar-${index}`,
      kind: 'grammar',
      eyebrow: t.grammar,
      title: String(item.pattern || t.grammar_title),
      prompt: String(item.prompt || t.grammar_prompt),
      target: String(item.answer || ''),
      explanation: String(item.explanation || ''),
      inputMode: 'paragraph',
    })),
    ...(production ? [{
      id: 'production-0',
      kind: 'production' as const,
      eyebrow: t.production,
      title: t.production_title,
      prompt: String(production.prompt || t.production_prompt),
      target: String(production.example_answer || ''),
      criteria: Array.isArray(production.success_criteria) ? production.success_criteria.map((item: any) => String(item || '').trim()).filter(Boolean) : [],
      inputMode: 'paragraph' as const,
    }] : []),
  ];
}

function libraryExerciseFeedback(step: LibraryExerciseStep, answer: string, t: CahierCopy['library']): LibraryExerciseFeedback {
  const normalizedAnswer = normalizeLibraryAnswer(answer);
  const normalizedTarget = normalizeLibraryAnswer(step.target);
  const targetTokens = normalizedTarget.split(' ').filter((token) => token.length > 3);
  const overlap = targetTokens.filter((token) => normalizedAnswer.includes(token)).length;
  const enoughWriting = step.kind === 'production' ? libraryWordCount(answer) >= 8 : libraryWordCount(answer) >= 2;
  const exact = Boolean(normalizedTarget) && normalizedAnswer === normalizedTarget;
  const close = step.kind === 'vocabulary'
    ? exact
    : exact || (enoughWriting && overlap >= Math.min(2, Math.max(1, targetTokens.length)));
  if (close || (step.kind === 'production' && enoughWriting)) {
    return {
      status: 'correct',
      title: step.kind === 'production' ? t.ready : t.verified,
      explanation: step.kind === 'production' ? t.ready_body : t.verified_body,
      rule: step.evidence ? fill(t.evidence, { text: excerpt(step.evidence) }) : undefined,
    };
  }
  return {
    status: 'wrong',
    title: t.wrong_title,
    explanation: step.kind === 'vocabulary' ? t.wrong_vocabulary : t.wrong_other,
    repair: step.target ? fill(t.target, { text: excerpt(step.target) }) : undefined,
    rule: step.evidence ? fill(t.evidence, { text: excerpt(step.evidence) }) : step.explanation || undefined,
  };
}

/* La Bibliothèque has no artboard in the design; it is extended from the
   concept-row primitive (a book is a row with a level glyph and a completion
   figure) and the reading surface. Flag-gated behind STORY_FEATURE_VISIBLE. */
function LibraryNotebookSurface({
  bookId,
  episodeIndex,
}: {
  bookId?: string;
  episodeIndex?: string;
}) {
  const [books, setBooks] = useState<LibraryBook[]>([]);
  const [selectedBook, setSelectedBook] = useState<LibraryBook | null>(null);
  const [episode, setEpisode] = useState<LibraryEpisode | null>(null);
  const [loading, setLoading] = useState(true);
  const [episodeLoading, setEpisodeLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const t = useCahierCopy().library;

  async function markEpisodeComplete() {
    if (!selectedBook || !episode) return;
    const updated = await api.completeLibraryEpisode(selectedBook.id, episode.order_index);
    setSelectedBook(updated);
    setBooks((prev) => prev.map((item) => item.id === updated.id ? updated : item));
    setEpisode((prev) => prev ? { ...prev, is_completed: true } : prev);
    pulseAppHaptic('complete');
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.getLibraryBooks()
      .then((rows) => {
        if (cancelled) return;
        setBooks(rows || []);
      })
      .catch(() => {
        if (!cancelled) setError(t.load_failed);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const fallback = books.find((book) => book.status === 'ready') || books[0] || null;
    const targetId = bookId || fallback?.id;
    if (!targetId) {
      setSelectedBook(null);
      setEpisode(null);
      return;
    }
    setEpisodeLoading(true);
    api.getLibraryBook(targetId)
      .then((book) => {
        if (cancelled) return;
        setSelectedBook(book);
        const requested = Number(episodeIndex);
        const index = Number.isFinite(requested)
          ? requested
          : Number(book.current_episode_index || 0);
        return api.getLibraryEpisode(book.id, Math.max(0, index));
      })
      .then((payload) => {
        if (!cancelled && payload) setEpisode(payload);
      })
      .catch(() => {
        if (!cancelled) setEpisode(null);
      })
      .finally(() => {
        if (!cancelled) setEpisodeLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [bookId, books, episodeIndex]);

  return (
    <div className="nb-lib">
      {error && <StateBlock tone="error" title={error} />}
      {loading && (
        <div className="nb-list" aria-busy="true">
          <Skeleton height={68} radius={16} />
          <Skeleton height={68} radius={16} />
          <span className="av2-sr" role="status">{t.loading}</span>
        </div>
      )}

      {!loading && !books.length && (
        <StateBlock
          tone="empty"
          title="Bibliothèque"
          body={(
            <>
              {t.empty_body}{' '}
              <Link href="/bibliotheque">{t.open_imports}</Link>
            </>
          )}
        />
      )}

      {!!books.length && (
        <div className="nb-lib__grid">
          <section className="nb-list" aria-label={t.books_label}>
            {books.map((book) => {
              const active = selectedBook?.id === book.id;
              const pct = Number(book.completion_percentage || 0);
              const tone = pct >= 100 ? 'done' : active ? 'progress' : 'new';
              return (
                <Link
                  key={book.id}
                  className="nb-row"
                  data-tone={tone}
                  aria-current={active ? 'true' : undefined}
                  href={`/notebook?mode=library&book=${book.id}&episode=${book.current_episode_index || 0}`}
                  onClick={() => pulseAppHaptic('selection')}
                >
                  <span className="nb-row__glyph" aria-hidden="true">{book.target_level}</span>
                  <span className="nb-row__main">
                    <span className="nb-row__title">{book.title}</span>
                    <span className="nb-row__meta">
                      {book.target_level} · {book.author || book.source_filename || t.imported_text}{active ? ` · ${t.open_marker}` : ''}
                    </span>
                  </span>
                  <span className="nb-row__pct">{pct}%</span>
                </Link>
              );
            })}
          </section>

          <section className="nb-lib__reader" aria-label={t.reader_label}>
            {episodeLoading && (
              <div className="nb-list" aria-busy="true">
                <Skeleton height={120} radius={16} />
                <span className="av2-sr" role="status">{t.episode_loading}</span>
              </div>
            )}
            {!episodeLoading && selectedBook && episode && (
              <>
                <header>
                  <p className="av2-label av2-label--story">{selectedBook.title}</p>
                  <h2 className="av2-headline av2-headline--title" lang="fr">{episode.title}</h2>
                  <p className="av2-label" style={{ fontWeight: 400, marginTop: 4 }}>
                    {fill(t.episode_meta, {
                      n: episode.order_index + 1,
                      total: selectedBook.total_episodes || 1,
                      minutes: episode.est_reading_minutes,
                      words: episode.word_count,
                    })}
                  </p>
                </header>
                <Surface as="article" className="nb-lib__passage" lang="fr">
                  {(episode.passage_text || '').split(/\n{2,}/).filter(Boolean).slice(0, 8).map((paragraph, index) => (
                    <p key={`${episode.id}-${index}`}>{paragraph}</p>
                  ))}
                </Surface>
                <LibraryExercisePreview payload={episode.exercise_payload} />
                <LibraryEpisodeExerciseRunner
                  episode={episode}
                  completed={episode.is_completed}
                  onComplete={markEpisodeComplete}
                />
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function LibraryEpisodeExerciseRunner({
  episode,
  completed,
  onComplete,
}: {
  episode: LibraryEpisode;
  completed: boolean;
  onComplete: () => Promise<void>;
}) {
  const t = useCahierCopy().library;
  const steps = libraryExerciseSteps(episode.exercise_payload, t);
  const [stepIndex, setStepIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState<LibraryExerciseFeedback | null>(null);
  const [finishing, setFinishing] = useState(false);
  const activeStep = steps[Math.min(stepIndex, Math.max(0, steps.length - 1))];
  const answer = activeStep ? answers[activeStep.id] || '' : '';
  const allChecked = stepIndex >= steps.length;

  useEffect(() => {
    setStepIndex(0);
    setAnswers({});
    setFeedback(null);
  }, [episode.id]);

  if (!steps.length) return null;
  if (!activeStep) return null;

  async function finishEpisode() {
    setFinishing(true);
    try {
      await onComplete();
    } finally {
      setFinishing(false);
    }
  }

  if (completed) {
    return (
      <Surface as="section" className="nb-sec" aria-label={t.done_label}>
        <p className="av2-label"><ShapeToken kind="done" size="sm" /> {t.done_kicker}</p>
        <h3 className="av2-headline av2-headline--rule">{fill(t.done_title, { n: episode.order_index + 1 })}</h3>
        <p className="av2-body">{t.done_body}</p>
      </Surface>
    );
  }

  if (allChecked) {
    return (
      <Surface as="section" className="nb-sec" aria-label={t.ready_label}>
        <p className="av2-label av2-label--action">{t.ready_kicker}</p>
        <h3 className="av2-headline av2-headline--rule">{fill(t.ready_title, { title: episode.title })}</h3>
        <p className="av2-body">{t.ready_summary}</p>
        <Action tone="primary" pending={finishing} pendingLabel={t.finishing} iconAfter={<ArrowRightIcon size={18} />} onClick={finishEpisode}>
          {t.finish}
        </Action>
      </Surface>
    );
  }

  function checkAnswer() {
    if (!activeStep || !answer.trim()) return;
    const nextFeedback = libraryExerciseFeedback(activeStep, answer, t);
    setFeedback(nextFeedback);
    pulseAppHaptic(nextFeedback.status === 'correct' ? 'correct' : 'repair');
  }

  function nextStep() {
    pulseAppHaptic('selection');
    setFeedback(null);
    setStepIndex((current) => current + 1);
  }

  return (
    <ExerciseShell
      className="nb-lib__runner"
      eyebrow={fill(t.exercise_n, { n: stepIndex + 1, total: steps.length })}
      title={activeStep.title}
      action={<ProgressBar value={stepIndex} max={steps.length} label={t.progress_label} />}
    >
      <div className="nb-lib__stage">
        <p className="av2-label">{activeStep.eyebrow}</p>
        <p className="nb-lib__prompt">{activeStep.prompt}</p>
        {activeStep.evidence && <blockquote className="nb-lib__evidence" lang="fr">{excerpt(activeStep.evidence, 260)}</blockquote>}
        {!!activeStep.criteria?.length && (
          <ul className="nb-lib__criteria">
            {activeStep.criteria.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
          </ul>
        )}
      </div>
      {activeStep.inputMode === 'line' ? (
        <input
          className="nb-field nb-field--sans nb-field--line"
          value={answer}
          onChange={(event) => {
            setAnswers((current) => ({ ...current, [activeStep.id]: event.target.value }));
            setFeedback(null);
          }}
          placeholder={t.line_placeholder}
        />
      ) : (
        <textarea
          className="nb-field"
          value={answer}
          onChange={(event) => {
            setAnswers((current) => ({ ...current, [activeStep.id]: event.target.value }));
            setFeedback(null);
          }}
          placeholder={t.paragraph_placeholder}
        />
      )}
      {feedback && (
        <FeedbackSheet
          status={feedback.status}
          title={feedback.title}
          explanation={feedback.explanation}
          repair={feedback.repair}
          rule={feedback.rule}
          onTryAgain={feedback.status === 'wrong' ? () => setFeedback(null) : undefined}
          onNext={nextStep}
        />
      )}
      {!feedback && (
        <div className="nb-lib__actions">
          <Button disabled={!answer.trim()} onClick={checkAnswer}>
            {t.check}
          </Button>
        </div>
      )}
    </ExerciseShell>
  );
}

function LibraryExercisePreview({ payload }: { payload: Record<string, any> }) {
  const comprehension = Array.isArray(payload?.comprehension) ? payload.comprehension.slice(0, 2) : [];
  const vocabulary = Array.isArray(payload?.vocabulary) ? payload.vocabulary.slice(0, 5) : [];
  const production = payload?.production || null;
  const t = useCahierCopy().library;
  return (
    <section className="nb-sec" aria-label={t.preview_label}>
      <NbSectionHead t={t.preview_title} />
      <div className="nb-lib__consignes">
        {comprehension.map((item: any, index: number) => (
          <Surface as="article" key={`comp-${index}`} shape="tile">
            <p className="av2-label">{t.comprehension}</p>
            <p className="av2-body">{item.question}</p>
          </Surface>
        ))}
        {!!vocabulary.length && (
          <Surface as="article" shape="tile">
            <p className="av2-label">{t.lexique}</p>
            <p className="av2-body">{vocabulary.map((item: any) => item.word).filter(Boolean).join(', ')}</p>
          </Surface>
        )}
        {production?.prompt && (
          <Surface as="article" shape="tile">
            <p className="av2-label">{t.production}</p>
            <p className="av2-body">{production.prompt}</p>
          </Surface>
        )}
      </div>
    </section>
  );
}

import React, { useEffect, useMemo, useRef, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { ArrowRight, Check, Loader2, MapPinned, Mic, RotateCcw, Send, Square } from 'lucide-react';
import toast from 'react-hot-toast';

import apiService, {
  AtelierAttemptRead,
  AtelierAttemptResult,
  AtelierConcept,
  AtelierErrataAttemptResult,
  AtelierErrataReviewTask,
  AtelierErratum,
  AtelierSessionStart,
  AtelierToday,
} from '@/services/api';
import { ConceptMotif } from '@/components/grammar/ConceptMotif';
import EditorialMasthead from '@/components/layout/EditorialMasthead';

type RoundName = 'recognize' | 'transform' | 'sentence' | 'produce' | 'speak' | 'conversation';
type RecognizeMode = 'fill' | 'word_bank' | 'classify';

const recognizeModes: Array<{ id: RecognizeMode; label: string; short: string }> = [
  { id: 'fill', label: 'Fill', short: 'A' },
  { id: 'word_bank', label: 'Word-bank', short: 'B' },
  { id: 'classify', label: 'Classify', short: 'C' },
];

const roundLabels: Array<{ id: RoundName; label: string; roman: string }> = [
  { id: 'recognize', label: 'Recognize', roman: 'I' },
  { id: 'transform', label: 'Transform', roman: 'II' },
  { id: 'sentence', label: 'Sentence', roman: 'III' },
  { id: 'produce', label: 'Paragraph', roman: 'IV' },
  { id: 'speak', label: 'Spoken', roman: 'V' },
  { id: 'conversation', label: 'Conversation', roman: 'VI' },
];

function answerKey(round: RoundName, mode: string, conceptId?: number | null) {
  return `${round}:${mode}:${conceptId || 'session'}`;
}

function roundUsesSessionScope(round: RoundName) {
  return round === 'produce';
}

function roundMode(round: RoundName, mode: RecognizeMode) {
  return round === 'recognize' ? mode : round;
}

function totalDrills(session: AtelierSessionStart | null) {
  if (!session) return 0;
  return session.concepts.length * (recognizeModes.length + 4) + 1;
}

type AtelierExerciseSet = AtelierSessionStart['exercise_sets'][number];

function asPositiveCount(value: any, fallback = 1) {
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric > 0 ? Math.min(Math.round(numeric), 3) : fallback;
}

function conceptRequirement(concept: AtelierConcept, exerciseSets: AtelierExerciseSet[] = []) {
  const exerciseSet = exerciseSets.find((set) => set.concept_id === concept.id);
  const requirements = Array.isArray(exerciseSet?.payload?.produce?.requirements)
    ? exerciseSet?.payload?.produce?.requirements
    : [];
  const requirement = requirements.find((item: any) => Number(item?.concept_id) === concept.id) || requirements[0] || {};
  const recipeCount = concept.atelier_blueprint?.exercise_recipe?.output_ladder?.paragraph?.target_count;
  return {
    count: asPositiveCount(requirement.target_count, asPositiveCount(recipeCount)),
    label: String(requirement.label || concept.atelier_blueprint?.display_title || concept.name || 'grammar target'),
  };
}

function wordCount(text: string) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function normalizeClient(value: any) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[’`]/g, "'")
    .replace(/[.!?;:,«»]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

export default function AtelierPage() {
  const router = useRouter();
  const [today, setToday] = useState<AtelierToday | null>(null);
  const [session, setSession] = useState<AtelierSessionStart | null>(null);
  const [activeConceptIndex, setActiveConceptIndex] = useState(0);
  const [round, setRound] = useState<RoundName>('recognize');
  const [mode, setMode] = useState<RecognizeMode>('fill');
  const [answers, setAnswers] = useState<Record<string, Record<string, any>>>({});
  const [submitted, setSubmitted] = useState<Record<string, boolean>>({});
  const [correctionsByKey, setCorrectionsByKey] = useState<Record<string, Record<string, any>>>({});
  const [errata, setErrata] = useState<AtelierErratum[]>([]);
  const [recentCorrection, setRecentCorrection] = useState<Record<string, any> | null>(null);
  const [recap, setRecap] = useState<Record<string, any> | null>(null);
  const [reviewTask, setReviewTask] = useState<AtelierErrataReviewTask | null>(null);
  const [reviewAnswer, setReviewAnswer] = useState('');
  const [reviewResult, setReviewResult] = useState<AtelierErrataAttemptResult | null>(null);
  const [view, setView] = useState<'today' | 'session'>('today');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [reviewSubmitting, setReviewSubmitting] = useState(false);

  const hydrateSession = (next: AtelierSessionStart) => {
    const restoredAnswers: Record<string, Record<string, any>> = {};
    const restoredSubmitted: Record<string, boolean> = { ...(next.submitted_map || {}) };
    const restoredCorrections: Record<string, Record<string, any>> = {};
    const restoredErrata: AtelierErratum[] = [];

    (next.attempts || []).forEach((attempt: AtelierAttemptRead) => {
      const key = attempt.submitted_key || answerKey(attempt.round, attempt.round === 'recognize' ? attempt.mode : attempt.round, attempt.concept_id);
      restoredSubmitted[key] = true;
      restoredCorrections[key] = attempt.correction || {};
      if (['sentence', 'produce', 'speak', 'conversation'].includes(attempt.round)) {
        restoredAnswers[key] = { text: attempt.answer_payload?.text || '' };
      } else {
        restoredAnswers[key] = { ...(attempt.answer_payload?.answers || {}) };
      }
      (attempt.correction?.errata || []).forEach((item: AtelierErratum) => {
        restoredErrata.unshift({ ...item, source_attempt_id: attempt.attempt_id });
      });
    });

    const position = next.current_position || {};
    const nextRound = position.round && position.round !== 'complete' ? position.round : 'produce';
    const conceptIndex = typeof position.concept_index === 'number'
      ? position.concept_index
      : Math.max(0, next.concepts.findIndex((concept) => concept.id === position.concept_id));

    setSession(next);
    setAnswers(restoredAnswers);
    setSubmitted(restoredSubmitted);
    setCorrectionsByKey(restoredCorrections);
    setErrata(restoredErrata);
    setRecentCorrection((next.attempts || []).slice(-1)[0]?.correction || null);
    setRecap(next.status === 'completed' && next.recap ? next.recap : null);
    setActiveConceptIndex(Math.max(0, Math.min(conceptIndex, next.concepts.length - 1)));
    setRound(nextRound as RoundName);
    setMode(recognizeModes.some((item) => item.id === position.mode) ? position.mode as RecognizeMode : 'fill');
    setView('session');
  };

  useEffect(() => {
    let alive = true;
    Promise.all([apiService.getAtelierToday(), apiService.getActiveAtelierSession()])
      .then(([todayData, active]) => {
        if (!alive) return;
        setToday(todayData);
        if (active.session) {
          hydrateSession(active.session);
        }
      })
      .catch((error) => {
        console.error(error);
        toast.error('Could not load Atelier practice state.');
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const activeConcept = session?.concepts[activeConceptIndex] || today?.concepts[activeConceptIndex] || null;
  const activeSet = useMemo(() => {
    if (!session || !activeConcept) return null;
    return session.exercise_sets.find((set) => set.concept_id === activeConcept.id)?.payload || null;
  }, [session, activeConcept]);
  const scopedMode = roundMode(round, mode);
  const scopedKey = answerKey(round, scopedMode, roundUsesSessionScope(round) ? null : activeConcept?.id);
  const currentAnswers = answers[scopedKey] || {};

  const updateAnswer = (
    key: string,
    value: any,
    scopedRound: RoundName = round,
    scopedModeValue: string = roundMode(round, mode),
    conceptId: number | null | undefined = roundUsesSessionScope(round) ? null : activeConcept?.id
  ) => {
    const keyScope = answerKey(scopedRound, scopedModeValue, conceptId);
    setAnswers((prev) => ({
      ...prev,
      [keyScope]: {
        ...(prev[keyScope] || {}),
        [key]: value,
      },
    }));
  };

  const startSession = async () => {
    setSubmitting(true);
    try {
      const conceptId = Number(router.query.concept_id);
      const next = await apiService.startAtelierSession(
        Number.isFinite(conceptId) ? { preferred_concept_id: conceptId } : undefined
      );
      hydrateSession(next);
    } catch (error) {
      console.error(error);
      toast.error('Could not start the Atelier session.');
    } finally {
      setSubmitting(false);
    }
  };

  const submitAttempt = async () => {
    if (!session) return;
    if (submitted[scopedKey]) {
      toast('This drill is already submitted.');
      return;
    }
    setSubmitting(true);
    try {
      let result: AtelierAttemptResult;
      if (round === 'recognize') {
        result = await apiService.submitAtelierAttempt(session.session_id, {
          concept_id: activeConcept?.id,
          round,
          mode,
          exercise_id: `${activeConcept?.external_id || activeConcept?.id}:${mode}`,
          answer_payload: { answers: currentAnswers },
        });
      } else if (round === 'transform') {
        result = await apiService.submitAtelierAttempt(session.session_id, {
          concept_id: activeConcept?.id,
          round,
          mode: 'rewrite',
          exercise_id: `${activeConcept?.external_id || activeConcept?.id}:transform`,
          answer_payload: { answers: currentAnswers },
        });
      } else if (round === 'sentence' || round === 'speak' || round === 'conversation') {
        result = await apiService.submitAtelierAttempt(session.session_id, {
          concept_id: activeConcept?.id,
          round,
          mode: round,
          exercise_id: `${activeConcept?.external_id || activeConcept?.id}:${round}`,
          answer_payload: { text: currentAnswers.text || '' },
        });
      } else {
        const produceKey = answerKey('produce', 'produce', null);
        result = await apiService.submitAtelierAttempt(session.session_id, {
          concept_id: null,
          round,
          mode: 'integrated_writing',
          exercise_id: 'integrated-writing',
          answer_payload: { text: answers[produceKey]?.text || '' },
        });
      }
      setSubmitted((prev) => ({ ...prev, [scopedKey]: true }));
      setCorrectionsByKey((prev) => ({ ...prev, [scopedKey]: result.correction }));
      setRecentCorrection(result.correction);
      setErrata((prev) => [...(result.correction.errata || []), ...prev]);
      toast.success(result.verdict === 'correct' ? 'Correct' : 'Submitted');
    } catch (error) {
      console.error(error);
      toast.error('The correction could not be submitted.');
    } finally {
      setSubmitting(false);
    }
  };

  const completeSession = async () => {
    if (!session) return;
    setSubmitting(true);
    try {
      const result = await apiService.completeAtelierSession(session.session_id);
      const recapPayload = { ...result.recap, session_id: result.session_id };
      setRecap(recapPayload);
      setSession((prev) => prev ? { ...prev, status: 'completed', recap: recapPayload } : prev);
    } catch (error) {
      console.error(error);
      toast.error('Could not complete the session.');
    } finally {
      setSubmitting(false);
    }
  };

  const removeErratumFromToday = (errorId: string) => {
    setToday((prev) => {
      if (!prev) return prev;
      const strip = (items?: AtelierErratum[]) => (items || []).filter((item) => item.id !== errorId);
      return {
        ...prev,
        due_errata: strip(prev.due_errata),
        concepts: prev.concepts.map((concept) => ({ ...concept, due_errata: strip(concept.due_errata) })),
        summary: {
          ...prev.summary,
          due_errata: Math.max(0, Number(prev.summary?.due_errata || 0) - 1),
        },
      };
    });
  };

  const openErratumReview = async (errorId?: string) => {
    if (!errorId) return;
    setReviewSubmitting(true);
    try {
      const result = await apiService.getAtelierErratumTask(errorId);
      setReviewTask(result.task);
      setReviewAnswer('');
      setReviewResult(null);
    } catch (error) {
      console.error(error);
      toast.error('Could not open this repair.');
    } finally {
      setReviewSubmitting(false);
    }
  };

  const submitErratumReview = async () => {
    if (!reviewTask?.error_id) return;
    setReviewSubmitting(true);
    try {
      const result = await apiService.submitAtelierErratumAttempt(reviewTask.error_id, { answer_text: reviewAnswer });
      setReviewResult(result);
      setReviewTask(result.task);
      removeErratumFromToday(reviewTask.error_id);
      if (result.is_correct) {
        toast.success('Erratum repaired');
      } else {
        toast('Reviewed. It will return soon for another repair.');
      }
    } catch (error) {
      console.error(error);
      toast.error('Could not submit this repair.');
    } finally {
      setReviewSubmitting(false);
    }
  };

  const goNext = () => {
    if (!session) return;
    if (round === 'recognize') {
      const modeIndex = recognizeModes.findIndex((item) => item.id === mode);
      if (modeIndex < recognizeModes.length - 1) {
        setMode(recognizeModes[modeIndex + 1].id);
        return;
      }
      if (activeConceptIndex < session.concepts.length - 1) {
        setActiveConceptIndex(activeConceptIndex + 1);
        setMode('fill');
        return;
      }
      setRound('transform');
      setActiveConceptIndex(0);
      return;
    }
    if (round === 'transform') {
      if (activeConceptIndex < session.concepts.length - 1) {
        setActiveConceptIndex(activeConceptIndex + 1);
        return;
      }
      setRound('sentence');
      setActiveConceptIndex(0);
      return;
    }
    if (round === 'sentence') {
      if (activeConceptIndex < session.concepts.length - 1) {
        setActiveConceptIndex(activeConceptIndex + 1);
        return;
      }
      setRound('produce');
      setActiveConceptIndex(0);
      return;
    }
    if (round === 'produce') {
      setRound('speak');
      setActiveConceptIndex(0);
      return;
    }
    if (round === 'speak') {
      if (activeConceptIndex < session.concepts.length - 1) {
        setActiveConceptIndex(activeConceptIndex + 1);
        return;
      }
      setRound('conversation');
      setActiveConceptIndex(0);
      return;
    }
    if (round === 'conversation' && activeConceptIndex < session.concepts.length - 1) {
      setActiveConceptIndex(activeConceptIndex + 1);
    }
  };

  const completedDrills = Object.values(submitted).filter(Boolean).length;

  return (
    <>
      <Head>
        <title>Atelier</title>
      </Head>
      <AtelierStyles />
      <div className="atelier-page">
        <Masthead
          view={view}
          setView={setView}
          hasSession={!!session}
          streak={today?.summary?.streak || 0}
        />
        {loading ? (
          <div className="spread loading">LOADING ATELIER</div>
        ) : view === 'today' || !session ? (
          <TodayView today={today} onStart={startSession} loading={submitting} onReviewErratum={openErratumReview} />
        ) : (
          <SessionView
            session={session}
            activeConceptIndex={activeConceptIndex}
            setActiveConceptIndex={setActiveConceptIndex}
            round={round}
            setRound={setRound}
            mode={mode}
            setMode={setMode}
            activeSet={activeSet}
            activeConcept={activeConcept}
            currentAnswers={currentAnswers}
            allAnswers={answers}
            updateAnswer={updateAnswer}
            submitAttempt={submitAttempt}
            completeSession={completeSession}
            submitting={submitting}
            submitted={submitted}
            correctionsByKey={correctionsByKey}
            goNext={goNext}
            recentCorrection={recentCorrection}
            errata={errata}
            completedDrills={completedDrills}
            onBack={() => setView('today')}
            produceAnswer={answers[answerKey('produce', 'produce', null)]?.text || ''}
          />
        )}
        {recap && <RecapModal recap={recap} concepts={session?.concepts || []} onClose={() => setRecap(null)} />}
        {reviewTask && (
          <ErrataReviewOverlay
            task={reviewTask}
            answer={reviewAnswer}
            setAnswer={setReviewAnswer}
            result={reviewResult}
            submitting={reviewSubmitting}
            onSubmit={submitErratumReview}
            onClose={() => {
              setReviewTask(null);
              setReviewAnswer('');
              setReviewResult(null);
            }}
          />
        )}
      </div>
    </>
  );
}

function Masthead({
  view,
  setView,
  hasSession,
  streak,
}: {
  view: 'today' | 'session';
  setView: (view: 'today' | 'session') => void;
  hasSession: boolean;
  streak: number;
}) {
  return (
    <EditorialMasthead
      active="studio"
      studioControl={(
        <button className={`app-nav-button ${view === 'today' ? 'active' : ''}`} onClick={() => setView('today')}>
          Atelier
        </button>
      )}
      sessionControl={(
        <button
          className={`app-nav-button ${view === 'session' ? 'active' : ''}`}
          disabled={!hasSession}
          onClick={() => setView('session')}
        >
          Session
        </button>
      )}
      trailing={<span>Vincent · {streak || 0}d streak</span>}
    />
  );
}

function TodayView({
  today,
  onStart,
  loading,
  onReviewErratum,
}: {
  today: AtelierToday | null;
  onStart: () => void;
  loading: boolean;
  onReviewErratum: (errorId?: string) => void;
}) {
  const concepts = today?.concepts || [];
  const atlas = today?.atlas || [];
  const due = today?.summary?.due || 0;
  const fragile = today?.summary?.fragile || 0;
  const dueErrata = today?.summary?.due_errata || today?.due_errata?.length || 0;
  const quote = today?.quote || {};

  return (
    <main className="spread today-spread">
      <header className="atelier-title">
        <div>
          <div className="t-mono">DAILY LEARNING LOOP</div>
          <h1>Atelier</h1>
        </div>
        <button className="btn red lg" onClick={onStart} disabled={loading || concepts.length === 0}>
          {loading ? 'STARTING' : 'BEGIN SESSION'} <ArrowRight size={14} />
        </button>
      </header>

      <section className="paper-frame atelier-passport">
        <CropMarks />
        <div className="passport-grid">
          <div className="practice-summary">
            <div className="atelier-kicker">
              <span>{due} due</span>
              <span>{dueErrata} errata</span>
              <span>{fragile} fragile</span>
            </div>
            <h2>Today&apos;s practice</h2>
            <p>9 recognition drills, 9 rewrites, and one writing task. Start with the useful repair, then carry it into Missions or Feuilleton.</p>
          </div>
          <div className="quote-card">
            <span className="t-mono-low">Desk note</span>
            <p className="fr">« {quote.text || 'On ne voit bien qu’avec le coeur.'} »</p>
            <p className="quote-author">— {quote.source || 'Antoine de Saint-Exupéry'}</p>
            {quote.source_detail && <p className="quote-source">Source: {quote.source_detail}</p>}
          </div>
        </div>
        <div className="atelier-loop" aria-label="Atelier loop">
          <span>Recognize</span>
          <ArrowRight size={13} />
          <span>Transform</span>
          <ArrowRight size={13} />
          <span>Write</span>
          <ArrowRight size={13} />
          <span>Use</span>
        </div>
      </section>

      <section className="today-set-head">
        <span className="t-mono">TODAY&apos;S SET</span>
      </section>
      <section className="grid-12 concept-grid">
        {concepts.map((concept, index) => (
          <div key={concept.id} className="grid-span-4">
            <ConceptCover concept={concept} index={index} />
          </div>
        ))}
      </section>

      <section className="stat-row">
        <Stat num={due} label="DUE" sub={due ? 'concepts ready' : 'clear today'} />
        <Stat num={dueErrata} label="ERRATA" sub={dueErrata ? 'mistakes due' : 'no slips due'} accent="var(--red)" />
        <Stat num={fragile} label="FRAGILE" sub={fragile ? 'low mastery' : 'no weak spots'} />
        <Stat num={today?.summary?.streak || 0} label="STREAK" sub="grammar days" />
      </section>

      <section className="grid-12 lower-board">
        <div className="grid-span-8">
          <Atlas items={atlas} />
        </div>
        <div className="grid-span-4 side-stack">
          {Boolean(today?.due_errata?.length) && (
            <DueErrataList items={today?.due_errata || []} onReview={onReviewErratum} />
          )}
          <NotebookBridge concepts={concepts} dueErrata={dueErrata} />
          <MissionBridge concepts={concepts} />
          <PriorityList items={atlas} selectedIds={concepts.map((concept) => concept.id)} />
        </div>
      </section>

      <footer className="atelier-footer">
        <span>Atelier · Today&apos;s Set</span>
        <span>local curated quote list · cached exercise sets</span>
      </footer>
    </main>
  );
}

function NotebookBridge({ concepts, dueErrata }: { concepts: AtelierConcept[]; dueErrata: number }) {
  return (
    <section className="paper-2 notebook-bridge">
      <header>
        <div>
          <span className="t-mono">NOTEBOOK</span>
          <p>Deep reference for today&apos;s rules and recurring slips.</p>
        </div>
        <Link className="notebook-link" href="/grammar">OPEN ALL ↗</Link>
      </header>
      <div className="notebook-rows">
        {concepts.slice(0, 3).map((concept, index) => (
          <Link key={concept.id} className="notebook-row" href={`/grammar?concept=${concept.id}`}>
            <span className="t-mono-low">{String(index + 1).padStart(2, '0')}</span>
            <ConceptMotif concept={concept} size={36} />
            <strong>{concept.atelier_blueprint?.display_title || concept.name}</strong>
            <span className="cefr">{concept.level}</span>
          </Link>
        ))}
      </div>
      <p className="notebook-foot">
        {dueErrata > 0
          ? `${dueErrata} due errata can be repaired from their rule notes.`
          : 'No errata due; use this to preview or review today’s concepts.'}
      </p>
    </section>
  );
}

function MissionBridge({ concepts }: { concepts: AtelierConcept[] }) {
  const conceptIds = concepts.map((concept) => `concept_id=${concept.id}`).join('&');
  return (
    <section className="paper-2 mission-bridge">
      <header>
        <div>
          <span className="t-mono">MISSION</span>
          <p>Use today&apos;s repairs in a message, conversation, or visual Feuilleton.</p>
        </div>
        <MapPinned size={18} />
      </header>
      <Link className="btn solid" href={`/missions${conceptIds ? `?${conceptIds}` : ''}`}>
        OPEN MISSIONS <ArrowRight size={14} />
      </Link>
      <Link className="btn ghost" href={`/graphic-novel${conceptIds ? `?${conceptIds}` : ''}`}>
        OPEN FEUILLETON <ArrowRight size={14} />
      </Link>
    </section>
  );
}

function DueErrataList({ items, onReview }: { items: AtelierErratum[]; onReview: (errorId?: string) => void }) {
  return (
    <section className="paper-2 due-errata-list">
      <header>
        <span className="t-mono">ERRATA DUE · {items.length}</span>
        <span className="t-mono-low">drives today</span>
      </header>
      {items.slice(0, 4).map((item) => (
        <article key={item.id || `${item.display_label}-${item.concept_id}`}>
          <div>
            <strong>{item.display_label}</strong>
            <p>{item.reason || (item.learner_text && item.corrected_target ? `${item.learner_text} → ${item.corrected_target}` : item.repair_hint)}</p>
            <p className="memory-meta">{item.source_label || 'Practice'} · {item.review_mode || 'grammar'} · {item.occurrences || 1}x</p>
          </div>
          <div className="due-errata-actions">
            {item.concept_id && <Link className="notebook-link" href={`/grammar?concept=${item.concept_id}`}>RULE</Link>}
            <button className="btn ghost" onClick={() => onReview(item.id)}>REPAIR</button>
          </div>
        </article>
      ))}
    </section>
  );
}

function ErrataReviewOverlay({
  task,
  answer,
  setAnswer,
  result,
  submitting,
  onSubmit,
  onClose,
}: {
  task: AtelierErrataReviewTask;
  answer: string;
  setAnswer: (value: string) => void;
  result: AtelierErrataAttemptResult | null;
  submitting: boolean;
  onSubmit: () => void;
  onClose: () => void;
}) {
  return (
    <div className="recap-overlay errata-review-overlay">
      <section className="errata-review-modal">
        <CropMarks />
        <header>
          <div>
            <div className="t-mono-low">{task.source_label || 'Atelier'} · {task.review_mode}</div>
            <h2>{task.display_label}</h2>
          </div>
          <button className="btn ghost" onClick={onClose}>CLOSE ×</button>
        </header>
        <div className="errata-review-body">
          <div className="errata-review-copy">
            <div className="t-mono yellow">REPAIR TASK</div>
            <p className="review-prompt">{task.prompt}</p>
            <p>{task.instruction}</p>
            {task.learner_text && (
              <div className="review-memory">
                <div className="t-mono-low">REMEMBERED SLIP</div>
                <p className="wrong">{task.learner_text}</p>
              </div>
            )}
            {task.why_wrong && <p><strong>Why:</strong> {task.why_wrong}</p>}
            {task.repair_hint && <p><strong>Repair:</strong> {task.repair_hint}</p>}
          </div>
          <div className="errata-review-answer">
            <label className="t-mono" htmlFor="errata-review-answer">YOUR REPAIR</label>
            <textarea
              id="errata-review-answer"
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
              placeholder={task.placeholder}
              autoFocus
            />
            {result && (
              <div className={`review-result ${result.is_correct ? 'correct' : ''}`}>
                <div className="t-mono">{result.is_correct ? 'REPAIRED' : 'NOT YET'}</div>
                <p>{result.feedback}</p>
                {!result.is_correct && (
                  <p><strong>Target:</strong> <span className="right">{result.target_answer}</span></p>
                )}
              </div>
            )}
            <div className="action-row">
              <button className="btn red lg" disabled={submitting || !answer.trim()} onClick={onSubmit}>
                SUBMIT REPAIR <Send size={15} />
              </button>
              {result?.is_correct && <button className="btn solid lg" onClick={onClose}>DONE <Check size={15} /></button>}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function SessionView({
  session,
  activeConceptIndex,
  setActiveConceptIndex,
  round,
  setRound,
  mode,
  setMode,
  activeSet,
  activeConcept,
  currentAnswers,
  allAnswers,
  updateAnswer,
  submitAttempt,
  completeSession,
  submitting,
  submitted,
  correctionsByKey,
  goNext,
  recentCorrection,
  errata,
  completedDrills,
  onBack,
  produceAnswer,
}: {
  session: AtelierSessionStart;
  activeConceptIndex: number;
  setActiveConceptIndex: (index: number) => void;
  round: RoundName;
  setRound: (round: RoundName) => void;
  mode: RecognizeMode;
  setMode: (mode: RecognizeMode) => void;
  activeSet: Record<string, any> | null;
  activeConcept: AtelierConcept | null;
  currentAnswers: Record<string, any>;
  allAnswers: Record<string, Record<string, any>>;
  updateAnswer: (key: string, value: any, scopedRound?: RoundName, scopedMode?: string, conceptId?: number | null) => void;
  submitAttempt: () => void;
  completeSession: () => void;
  submitting: boolean;
  submitted: Record<string, boolean>;
  correctionsByKey: Record<string, Record<string, any>>;
  goNext: () => void;
  recentCorrection: Record<string, any> | null;
  errata: any[];
  completedDrills: number;
  onBack: () => void;
  produceAnswer: string;
}) {
  const currentMode = roundMode(round, mode);
  const currentKey = answerKey(round, currentMode, roundUsesSessionScope(round) ? null : activeConcept?.id);
  const currentCorrection = correctionsByKey[currentKey] || null;
  const currentSubmitted = !!submitted[currentKey];
  const total = totalDrills(session);

  return (
    <main className="spread session-spread">
      <section className="session-title-row">
        <div>
          <button className="btn ghost" onClick={onBack}>← BACK</button>
          <span className="session-title">Session</span>
        </div>
        <span className="t-mono-low">{errata.length} corrections · {completedDrills}/{total} submitted</span>
      </section>
      <div className="rule thick" />

      <ConceptBench concepts={session.concepts} activeIndex={activeConceptIndex} setActiveIndex={setActiveConceptIndex} />
      <RoundStrip round={round} setRound={setRound} />

      {activeSet && activeConcept && (
        <>
          <section className="xray-title"><span className="t-mono">SENTENCE X-RAY</span></section>
          <section className="xray-board">
            <CropMarks />
            <SentenceXRay xray={activeSet.xray} />
            <ConceptRulePanel payload={activeSet} concept={activeConcept} />
          </section>

          <section className="grid-12 work-grid">
            <div className="grid-span-8">
              {round === 'recognize' && (
                <>
                  <div className="exercise-toolbar">
                    <ModeMarkers
                      mode={mode}
                      setMode={setMode}
                      activeConcept={activeConcept}
                      submitted={submitted}
                      answers={currentAnswers}
                      allAnswers={allAnswers}
                      activeSet={activeSet}
                    />
                    <p>{recognizeModeSummary(activeSet, mode, currentAnswers, currentSubmitted)}</p>
                  </div>
                  <div className="paper-frame exercise-frame">
                    <CropMarks />
                    <RecognizePanel
                      payload={activeSet}
                      mode={mode}
                      answers={currentAnswers}
                      updateAnswer={updateAnswer}
                      correction={currentCorrection}
                      submitted={currentSubmitted}
                    />
                    <ActionRow submitting={submitting} submitted={currentSubmitted} submitAttempt={submitAttempt} goNext={goNext} />
                  </div>
                </>
              )}
              {round === 'transform' && (
                <div className="paper-frame exercise-frame">
                  <CropMarks />
                  <TransformPanel
                    payload={activeSet}
                    answers={currentAnswers}
                    updateAnswer={updateAnswer}
                    correction={currentCorrection}
                    submitted={currentSubmitted}
                  />
                  <ActionRow submitting={submitting} submitted={currentSubmitted} submitAttempt={submitAttempt} goNext={goNext} />
                </div>
              )}
              {(round === 'sentence' || round === 'speak' || round === 'conversation') && (
                <div className="paper-frame exercise-frame">
                  <CropMarks />
                  <OutputLadderPanel
                    payload={activeSet}
                    round={round}
                    answer={currentAnswers.text || ''}
                    updateAnswer={(value) => updateAnswer('text', value, round, round, activeConcept?.id)}
                    correction={currentCorrection}
                    submitted={currentSubmitted}
                  />
                  <ActionRow
                    submitting={submitting}
                    submitted={currentSubmitted}
                    submitAttempt={submitAttempt}
                    goNext={goNext}
                    nextLabel="NEXT STEP"
                    nextDisabled={round === 'conversation' && activeConceptIndex >= session.concepts.length - 1}
                  />
                </div>
              )}
              {round === 'produce' && (
                <div className="paper-frame exercise-frame">
                  <CropMarks />
                  <ProducePanel
                    concepts={session.concepts}
                    exerciseSets={session.exercise_sets}
                    payload={activeSet}
                    answer={produceAnswer}
                    updateAnswer={(value) => updateAnswer('text', value, 'produce', 'produce', null)}
                  />
                  <div className="action-row">
                    <button className="btn red" disabled={submitting || currentSubmitted} onClick={submitAttempt}>
                      {currentSubmitted ? 'REVIEW SUBMITTED' : 'SUBMIT FOR REVIEW'} <Send size={14} />
                    </button>
                    <button className="btn solid" disabled={submitting || !currentSubmitted} onClick={goNext}>
                      NEXT STEP <ArrowRight size={14} />
                    </button>
                  </div>
                </div>
              )}
              {round === 'conversation' && currentSubmitted && activeConceptIndex >= session.concepts.length - 1 && (
                <div className="action-row final-action">
                  <button className="btn solid lg" disabled={submitting} onClick={completeSession}>
                    COMPLETE SESSION <Check size={14} />
                  </button>
                </div>
              )}
            </div>
            <aside className="grid-span-4 margin-stack">
              <TutorNote concept={activeConcept} correction={recentCorrection} round={round} />
              <ErrataStack errata={errata} />
            </aside>
          </section>
        </>
      )}
    </main>
  );
}

function ActionRow({
  submitting,
  submitted,
  submitAttempt,
  goNext,
  nextLabel = 'NEXT DRILL',
  nextDisabled = false,
}: {
  submitting: boolean;
  submitted: boolean;
  submitAttempt: () => void;
  goNext: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
}) {
  return (
    <div className="action-row">
      <button className="btn solid" disabled={submitting || submitted} onClick={submitAttempt}>
        {submitted ? 'SUBMITTED' : 'SUBMIT'} <Send size={14} />
      </button>
      <button className="btn ghost" disabled={submitting || !submitted || nextDisabled} onClick={goNext}>{nextLabel} →</button>
    </div>
  );
}

function Stat({ num, label, sub, accent = 'var(--ink)' }: { num: any; label: string; sub?: string; accent?: string }) {
  return (
    <div className="stat">
      <div className="t-num" style={{ color: accent }}>{num}</div>
      <div className="t-mono">{label}</div>
      {sub && <p>{sub}</p>}
    </div>
  );
}

function ConceptCover({ concept, index, compact = false, active = false }: { concept: AtelierConcept; index: number; compact?: boolean; active?: boolean }) {
  const accent = index === 2 || concept.role === 'contrast' ? 'var(--blue)' : 'var(--red)';
  const displayTitle = concept.atelier_blueprint?.display_title || concept.name;
  const dueErratum = concept.due_errata?.[0];
  const statusText = dueErratum
    ? dueErratum.reason || `${dueErratum.display_label}${dueErratum.learner_text && dueErratum.corrected_target ? `: ${dueErratum.learner_text} → ${dueErratum.corrected_target}` : ''}`
    : concept.role === 'contrast' ? 'Different rule' : 'Weak spot';
  return (
    <article className={`concept-cover ${compact ? 'compact' : ''} ${active ? 'active' : ''}`}>
      <div className="cover-band" style={{ background: accent }}>
        <span>{String(index + 1).padStart(2, '0')}</span>
        <span>{concept.level} · {(concept.category || 'Grammar').toUpperCase()}</span>
      </div>
      <div className="cover-symbol">
        <ConceptMotif concept={concept} />
      </div>
      <div className="cover-title">
        <h3>{displayTitle}</h3>
      </div>
      {!compact && (
        <div className="cover-foot">
          <span className="status-dot" style={{ background: accent }} />
          <span title={statusText}>{statusText}</span>
          <Link className="cover-ref" href={`/grammar?concept=${concept.id}`}>Notebook ↗</Link>
        </div>
      )}
    </article>
  );
}

function Atlas({ items }: { items: any[] }) {
  return (
    <section className="paper-2 atlas">
      <div className="atlas-head">
        <span className="t-mono">FRAGILITY ATLAS</span>
        <span className="t-mono-low"><span className="red-dot" /> FRAGILE · <span className="black-square" /> STABLE</span>
      </div>
      <div className="atlas-plot">
        <span className="danger-zone">DANGER ZONE</span>
        <span className="axis-y">↑ PRIORITY</span>
        <span className="axis-x">MASTERY →</span>
        {items.slice(0, 16).map((item, index) => {
          const mastery = Math.max(0, Math.min(100, Number(item.mastery || 0)));
          const left = Math.max(1, Math.min(96, mastery));
          const top = Math.max(4, Math.min(88, 10 + index * 5));
          return (
            <span
              key={`${item.concept_id}-${index}`}
              className={`atlas-dot ${item.is_foundation ? 'foundation' : ''}`}
              style={{ left: `${left}%`, top: `${top}%` }}
              title={item.name}
            />
          );
        })}
      </div>
    </section>
  );
}

function PriorityList({ items, selectedIds }: { items: any[]; selectedIds: number[] }) {
  const nextItems = items.filter((item) => !selectedIds.includes(item.concept_id));
  return (
    <section className="paper-2 priority-list">
      <header>
        <span className="t-mono">NEXT AFTER TODAY · {nextItems.length}</span>
        <span className="t-mono-low">reference only</span>
      </header>
      {nextItems.length === 0 && (
        <div className="empty-priority">
          <strong>Queue is clear after today</strong>
          <span className="t-mono-low">new weak spots will appear here after corrections</span>
        </div>
      )}
      {nextItems.slice(0, 8).map((item, index) => (
        item.concept_id ? (
          <Link
            key={`${item.concept_id}-${index}`}
            href={`/grammar?concept=${item.concept_id}`}
            className={selectedIds.includes(item.concept_id) ? 'selected' : ''}
          >
            <span className="t-mono-low">{String(index + 1).padStart(2, '0')}</span>
            <strong>{item.display_title || item.name}</strong>
            <span className="cefr">{item.level}</span>
            <span className="status-ring" />
          </Link>
        ) : (
          <div key={`${item.concept_id}-${index}`} className={selectedIds.includes(item.concept_id) ? 'selected' : ''}>
            <span className="t-mono-low">{String(index + 1).padStart(2, '0')}</span>
            <strong>{item.display_title || item.name}</strong>
            <span className="cefr">{item.level}</span>
            <span className="status-ring" />
          </div>
        )
      ))}
    </section>
  );
}

function ConceptBench({ concepts, activeIndex, setActiveIndex }: { concepts: AtelierConcept[]; activeIndex: number; setActiveIndex: (index: number) => void }) {
  return (
    <section className="concept-bench">
      {concepts.map((concept, index) => (
        <button key={concept.id} onClick={() => setActiveIndex(index)}>
          <ConceptCover concept={concept} index={index} compact active={activeIndex === index} />
        </button>
      ))}
    </section>
  );
}

function RoundStrip({ round, setRound }: { round: RoundName; setRound: (round: RoundName) => void }) {
  return (
    <section className="round-strip">
      {roundLabels.map((item) => (
        <button key={item.id} className={round === item.id ? 'active' : ''} onClick={() => setRound(item.id)}>
          <span>{item.roman}</span> {item.label}
        </button>
      ))}
    </section>
  );
}

function SentenceXRay({ xray }: { xray: Record<string, any> }) {
  const sentence = xray?.sentence || 'Si je finis tôt, je t’appellerai.';
  const marks = xray?.marks || [];
  const tokens = sentence.split(/(\s+|[.,!?;:])/).filter(Boolean);
  return (
    <div className="sentence-xray">
      <p>
        {tokens.map((token: string, index: number) => {
          const clean = token.toLowerCase().replace(/[.,!?;:]/g, '');
          const markIndex = marks.findIndex((mark: any) => clean === String(mark.text || '').toLowerCase().replace(/[.,!?;:]/g, ''));
          if (markIndex < 0) return <React.Fragment key={`${token}-${index}`}>{token}</React.Fragment>;
          return (
            <span key={`${token}-${index}`} className={`marked mark-${markIndex % 3}`}>
              {token}
              <em>{marks[markIndex].label}</em>
            </span>
          );
        })}
      </p>
      <div className="xray-legend">
        {marks.map((mark: any, index: number) => (
          <span key={`${mark.text}-${index}`}>
            <i className={`legend-box mark-${index % 3}`} />
            <b>{mark.label}</b>
            <small>{mark.text}</small>
          </span>
        ))}
      </div>
    </div>
  );
}

function ConceptRulePanel({ payload, concept }: { payload: Record<string, any>; concept: AtelierConcept }) {
  const rule = payload.rule_panel || {};
  return (
    <aside className="grammar-block rule-panel">
      <div className="between">
        <div className="t-mono blue">RULE</div>
        <Link className="notebook-link" href={`/grammar?concept=${concept.id}`}>Notebook ↗</Link>
      </div>
      <h3>{rule.title}</h3>
      <p>{rule.rule}</p>
      <p><strong>When:</strong> {rule.when}</p>
      <p><strong>Pattern:</strong> {rule.pattern}</p>
      <p><strong>Check:</strong> {rule.check}</p>
      <div className="examples">
        {(rule.examples || []).slice(0, 3).map((example: string) => <p key={example}>{example}</p>)}
      </div>
    </aside>
  );
}

function recognizeModeSummary(
  activeSet: Record<string, any> | null,
  mode: RecognizeMode,
  answers: Record<string, any>,
  submitted: boolean,
) {
  const items = activeSet?.recognize?.[mode]?.items || [];
  const answered = submitted ? items.length : items.filter((item: any) => String(answers[item.id] || '').trim()).length;
  const label = recognizeModes.find((item) => item.id === mode)?.label || mode;
  return `${label} ${answered}/${items.length || 3}`;
}

function ModeMarkers({
  mode,
  setMode,
  activeConcept,
  submitted,
  answers,
  allAnswers,
  activeSet,
}: {
  mode: RecognizeMode;
  setMode: (mode: RecognizeMode) => void;
  activeConcept: AtelierConcept | null;
  submitted: Record<string, boolean>;
  answers: Record<string, any>;
  allAnswers: Record<string, Record<string, any>>;
  activeSet: Record<string, any> | null;
}) {
  return (
    <div className="mode-markers">
      {recognizeModes.map((item) => {
        const key = answerKey('recognize', item.id, activeConcept?.id);
        const items = activeSet?.recognize?.[item.id]?.items || [];
        const modeAnswers = item.id === mode ? answers : allAnswers[key] || {};
        const answered = submitted[key]
          ? items.length
          : items.filter((entry: any) => String(modeAnswers[entry.id] || '').trim()).length;
        return (
          <button key={item.id} className={mode === item.id ? 'active' : ''} onClick={() => setMode(item.id)}>
            <span>{item.short} ·</span> {item.label} <small>{answered}/{items.length || 3}</small>
          </button>
        );
      })}
    </div>
  );
}

function RecognizePanel({
  payload,
  mode,
  answers,
  updateAnswer,
  correction,
  submitted,
}: {
  payload: Record<string, any>;
  mode: RecognizeMode;
  answers: Record<string, any>;
  updateAnswer: (key: string, value: any) => void;
  correction: Record<string, any> | null;
  submitted: boolean;
}) {
  const items = payload.recognize?.[mode]?.items || [];
  return (
    <div className="recognize-set">
      {items.map((item: any, index: number) => {
        const feedback = itemFeedback(item, answers[item.id], correction);
        return (
          <article key={item.id} className="sub-exercise">
            <div className="t-mono-low">EXERCISE {index + 1}</div>
            <p className="exercise-prompt">{item.prompt}</p>
            {mode === 'fill' && (
              <div className="choice-row">
                {item.choices.map((choice: string) => (
                  <button key={choice} className={answers[item.id] === choice ? 'selected' : ''} onClick={() => updateAnswer(item.id, choice)}>{choice}</button>
                ))}
              </div>
            )}
            {mode === 'word_bank' && (
              <>
                <div className="type-case">
                  {item.tokens.map((token: string, tokenIndex: number) => <span key={`${token}-${tokenIndex}`}>{token}</span>)}
                </div>
                <input value={answers[item.id] || ''} onChange={(event) => updateAnswer(item.id, event.target.value)} placeholder="Type the sentence built from the chips" />
              </>
            )}
            {mode === 'classify' && (
              <div className="choice-row compact">
                {item.labels.map((label: string) => (
                  <button key={label} className={answers[item.id] === label ? 'selected' : ''} onClick={() => updateAnswer(item.id, label)}>{label}</button>
                ))}
              </div>
            )}
            {submitted && <InlineFeedback feedback={feedback} />}
          </article>
        );
      })}
    </div>
  );
}

function TransformPanel({
  payload,
  answers,
  updateAnswer,
  correction,
  submitted,
}: {
  payload: Record<string, any>;
  answers: Record<string, any>;
  updateAnswer: (key: string, value: any) => void;
  correction: Record<string, any> | null;
  submitted: boolean;
}) {
  const items = payload.transform?.items || [];
  return (
    <div className="transform-set">
      {items.map((item: any, index: number) => {
        const feedback = itemFeedback(item, answers[item.id], correction);
        return (
          <article key={item.id} className="sub-exercise">
            <div className="t-mono-low"><RotateCcw size={13} /> REWRITE {index + 1} · {String(item.type || '').replace('_', ' ')}</div>
            <p className="instruction">{item.instruction}</p>
            <p className="source-sentence">{item.source}</p>
            <textarea value={answers[item.id] || ''} onChange={(event) => updateAnswer(item.id, event.target.value)} placeholder="Rewrite here" />
            {submitted && <InlineFeedback feedback={feedback} />}
          </article>
        );
      })}
    </div>
  );
}

function itemFeedback(item: any, learner: any, correction: Record<string, any> | null) {
  if (!correction) return null;
  const corrected = correction.corrected_answer || {};
  const target = typeof corrected === 'object' ? corrected[item.id] : item.correct_answer || item.expected_answer;
  const learnerText = Array.isArray(learner) ? learner.join(' ') : String(learner || '');
  const targetText = String(target || item.correct_answer || item.expected_answer || item.correct_label || '');
  const matchingErratum = (correction.errata || []).find((erratum: AtelierErratum) => {
    const errTarget = normalizeClient(erratum.corrected_target);
    const errLearner = normalizeClient(erratum.learner_text);
    return errTarget === normalizeClient(targetText) || (!!learnerText && errLearner === normalizeClient(learnerText));
  });
  const correct = normalizeClient(learnerText) === normalizeClient(targetText);
  return {
    correct,
    target: targetText,
    why: matchingErratum?.why_wrong,
    repair: matchingErratum?.repair_hint,
  };
}

function InlineFeedback({ feedback }: { feedback: ReturnType<typeof itemFeedback> }) {
  if (!feedback) return null;
  if (feedback.correct) {
    return <div className="inline-feedback correct"><Check size={14} /> Correct</div>;
  }
  return (
    <div className="inline-feedback">
      <div><strong>Target:</strong> {feedback.target}</div>
      {feedback.why && <div><strong>Why:</strong> {feedback.why}</div>}
      {feedback.repair && <div><strong>Repair:</strong> {feedback.repair}</div>}
    </div>
  );
}

function OutputLadderPanel({
  payload,
  round,
  answer,
  updateAnswer,
  correction,
  submitted,
}: {
  payload: Record<string, any>;
  round: 'sentence' | 'speak' | 'conversation';
  answer: string;
  updateAnswer: (value: string) => void;
  correction: Record<string, any> | null;
  submitted: boolean;
}) {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const item = payload.output_ladder?.[round]?.items?.[0] || {};
  const roundCopy = {
    sentence: {
      eyebrow: 'SHORT SENTENCE',
      title: 'Use it once, cleanly.',
      hint: 'This is the first active-output step: one original sentence is enough.',
    },
    speak: {
      eyebrow: 'SPOKEN RESPONSE',
      title: 'Say it before you type it.',
      hint: 'Speak the answer aloud, then type the transcript so Atelier can review the grammar.',
    },
    conversation: {
      eyebrow: 'CONVERSATION TURN',
      title: 'Use it in a reply.',
      hint: 'Answer the prompt as one natural turn. The reply can be short if it carries the target grammar.',
    },
  }[round];
  const target = correction?.corrected_answer || item.example_answer || '';
  const feedback = submitted
    ? {
        correct: !correction?.errata?.length,
        target: String(target || ''),
        why: correction?.errata?.[0]?.why_wrong,
        repair: correction?.errata?.[0]?.repair_hint,
      }
    : null;

  const transcribeAudio = async (blob: Blob) => {
    setIsTranscribing(true);
    try {
      const transcript = await apiService.transcribeAudio(blob);
      if (transcript.trim()) {
        updateAnswer(transcript.trim());
      } else {
        toast('No speech detected.');
      }
    } catch (error) {
      console.error(error);
      toast.error('Could not transcribe the recording.');
    } finally {
      setIsTranscribing(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' });
        stream.getTracks().forEach((track) => track.stop());
        void transcribeAudio(audioBlob);
      };
      recorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error(error);
      toast.error('Microphone access failed.');
    }
  };

  const stopRecording = () => {
    if (!mediaRecorderRef.current || !isRecording) return;
    mediaRecorderRef.current.stop();
    setIsRecording(false);
  };

  const toggleRecording = () => {
    if (submitted || isTranscribing) return;
    if (isRecording) {
      stopRecording();
    } else {
      void startRecording();
    }
  };

  return (
    <div className={`output-ladder-panel output-${round}`}>
      <div className="ladder-stage">
        <div>
          <div className="t-mono yellow">{roundCopy.eyebrow}</div>
          <h3>{roundCopy.title}</h3>
          <p>{roundCopy.hint}</p>
        </div>
        <div className="stage-meter">
          {roundLabels.map((entry) => (
            <span key={entry.id} className={entry.id === round ? 'active' : ''}>{entry.roman}</span>
          ))}
        </div>
      </div>
      <div className="live-block">
        <div className="t-mono-low">TASK</div>
        <p className="instruction">{item.instruction}</p>
        <p className="exercise-prompt">{item.prompt}</p>
        {item.example_answer && <p className="example-answer">Example frame: {item.example_answer}</p>}
      </div>
      {round === 'speak' && (
        <div className="voice-capture">
          <button type="button" className={`voice-button ${isRecording ? 'recording' : ''}`} disabled={submitted || isTranscribing} onClick={toggleRecording}>
            {isTranscribing ? <Loader2 size={18} className="spin" /> : isRecording ? <Square size={18} /> : <Mic size={18} />}
            {isTranscribing ? 'TRANSCRIBING' : isRecording ? 'STOP' : 'RECORD'}
          </button>
          <span>{isRecording ? 'Speak your answer now.' : 'Record to fill the transcript, or type manually.'}</span>
        </div>
      )}
      <textarea
        value={answer}
        onChange={(event) => updateAnswer(event.target.value)}
        placeholder={round === 'speak' ? 'Type the sentence you just said aloud.' : 'Write your answer here.'}
      />
      <div className="word-count">
        {wordCount(answer)} / {item.min_words || 5}-{item.max_words || 28} words
      </div>
      {submitted && <InlineFeedback feedback={feedback} />}
    </div>
  );
}

function ProducePanel({
  concepts,
  exerciseSets,
  payload,
  answer,
  updateAnswer,
}: {
  concepts: AtelierConcept[];
  exerciseSets: AtelierExerciseSet[];
  payload: Record<string, any>;
  answer: string;
  updateAnswer: (value: string) => void;
}) {
  const requirements = concepts.map((concept) => conceptRequirement(concept, exerciseSets));
  const produce = payload.produce || {};
  return (
    <div className="produce-panel">
      <div className="live-block">
        <div className="t-mono yellow">WRITING TASK</div>
        <p className="fr">« {produce.source_fragment || 'Le Tour de France 2026 partira de Barcelone le 4 juillet.'} »</p>
        <p>
          Write a compact scene around this fragment. Use exactly enough grammar pressure to make the review useful:
          {' '}
          {requirements.map((req) => `${req.count} ${req.label}`).join(', ')}. Submission stays open even if a target is missing.
        </p>
      </div>
      <div className="target-chips">
        {requirements.map((req) => <span key={req.label}>{req.count} × {req.label}</span>)}
      </div>
      <textarea value={answer} onChange={(event) => updateAnswer(event.target.value)} placeholder="Write your paragraph here. The targets guide the review; they do not lock submission." />
      <div className="word-count">{wordCount(answer)} / {produce.min_words || 70}-{produce.max_words || 140} words</div>
    </div>
  );
}

function TutorNote({ concept, correction, round }: { concept: AtelierConcept | null; correction: Record<string, any> | null; round: RoundName }) {
  const title = correction ? 'RECENT CORRECTION' : 'ATELIER NOTE';
  const erratum = correction?.errata?.[0];
  return (
    <section className="tutor-note">
      <div className="between">
        <span className="t-mono">{title}</span>
        <span className="t-mono-low">{round}</span>
      </div>
      {erratum ? (
        <>
          <h3>{erratum.display_label}</h3>
          <p><strong>Why:</strong> {erratum.why_wrong}</p>
          <p><strong>Repair:</strong> {erratum.repair_hint}</p>
        </>
      ) : (
        <>
          <h3>{concept?.name}</h3>
          <p>{concept?.core_rule || 'Use the x-ray and the rule panel as the proofing reference while you answer.'}</p>
        </>
      )}
    </section>
  );
}

function ErrataStack({ errata }: { errata: any[] }) {
  return (
    <section className="errata-column">
      <div className="between">
        <span className="t-mono">CORRECTIONS</span>
        <span className="t-mono-low">{errata.length}</span>
      </div>
      {errata.length === 0 && (
        <div className="empty-slip">
          <div className="t-mono-low">No corrections yet</div>
          <p>Wrong answers appear here as proofreader slips.</p>
        </div>
      )}
      {errata.slice(0, 6).map((item, index) => (
        <article key={`${item.display_label}-${index}`} className="errata-slip">
          <span className="slip-label">{item.display_label}</span>
          <span className="slip-num">Nº {String(index + 1).padStart(2, '0')}</span>
          <div className="t-mono-low">YOU WROTE</div>
          <p className="wrong">{item.learner_text || 'missing'}</p>
          <div className="t-mono-low red">CORRECTED</div>
          <p className="right">{item.corrected_target}</p>
          <div className="why">
            <p><strong>Why.</strong> {item.why_wrong}</p>
            <p><strong>Repair.</strong> {item.repair_hint}</p>
          </div>
          {(item.review_mode || item.source_label || item.next_review_date) && (
            <div className="slip-memory">
              {[item.source_label, item.review_mode, item.next_review_date ? 'scheduled' : null].filter(Boolean).join(' · ')}
            </div>
          )}
          {item.concept_id && <Link className="notebook-link slip-link" href={`/grammar?concept=${item.concept_id}`}>Review in notebook ↗</Link>}
          {item.id && (
            <Link
              className="notebook-link slip-link"
              href={`/missions?erratum_id=${item.id}${item.concept_id ? `&concept_id=${item.concept_id}` : ''}`}
            >
              Repair in mission ↗
            </Link>
          )}
        </article>
      ))}
    </section>
  );
}

function RecapModal({ recap, concepts, onClose }: { recap: Record<string, any>; concepts: AtelierConcept[]; onClose: () => void }) {
  return (
    <div className="recap-overlay">
      <section className="recap-modal">
        <CropMarks />
        <header>
          <div>
            <div className="t-mono-low">Session recap</div>
            <h2>Session Recap</h2>
          </div>
          <button className="btn ghost" onClick={onClose}>CLOSE ×</button>
        </header>
        <div className="recap-stats">
          <Stat num={recap.concepts_repaired || 0} label="REPAIRED" sub="concepts" />
          <Stat num={errataLabel(recap.errata_logged || 0)} label="ERRATA" sub="logged" accent="var(--red)" />
          <Stat num={recap.strengthened || 0} label="STRENGTHENED" sub="concepts" />
          <Stat num={`${recap.streak_before || 0}→${recap.streak_after || 0}`} label="STREAK" sub="days" />
        </div>
        <div className="recap-lines">
          <div className="t-mono">CONCEPTS · NEW STATE</div>
          {(recap.concepts || []).map((item: any, index: number) => {
            const concept = concepts.find((entry) => entry.id === item.concept_id);
            return (
              <div key={item.concept_id}>
                {concept && <ConceptMotif concept={concept} />}
                <strong>
                  {concept ? (
                    <Link href={`/grammar?concept=${concept.id}`}>{concept.atelier_blueprint?.display_title || concept.name}</Link>
                  ) : (
                    `Concept ${item.concept_id}`
                  )}
                </strong>
                <span>{item.score}/10</span>
                <span>{item.state}</span>
              </div>
            );
          })}
        </div>
        <footer>
          <span className="t-mono-low">Atelier · Today&apos;s Set</span>
          <div className="recap-actions">
            {recap.session_id && (
              <Link className="btn red" href={`/missions?atelier_session_id=${recap.session_id}`}>
                USE IN MISSION <ArrowRight size={14} />
              </Link>
            )}
            <button className="btn solid" onClick={onClose}>RETURN TO TODAY</button>
          </div>
        </footer>
      </section>
    </div>
  );
}

function errataLabel(count: number) {
  return count;
}

function CropMarks() {
  return (
    <>
      <span className="crop-mark tl" />
      <span className="crop-mark tr" />
      <span className="crop-mark bl" />
      <span className="crop-mark br" />
    </>
  );
}

function AtelierStyles() {
  return (
    <style jsx global>{`
      .atelier-page {
        --paper: #f1ece1;
        --paper-2: #e8e0cf;
        --paper-3: #d8cdb6;
        --paper-deep: #1a1814;
        --ink: #14110d;
        --ink-2: #4a4538;
        --ink-3: #8a826f;
        --red: #d8321a;
        --blue: #1d3a8a;
        --yellow: #f3c318;
        --grotesk: "Inter", "Helvetica Neue", Arial, sans-serif;
        --display: "Inter", "Helvetica Neue", Arial, sans-serif;
        --serif: "EB Garamond", Garamond, "Times New Roman", serif;
        --mono: "Inter", "Helvetica Neue", Arial, sans-serif;
        min-height: 100vh;
        background: var(--paper);
        color: var(--ink);
        font-family: var(--grotesk);
        background-image:
          radial-gradient(circle at 18% 22%, rgba(20,17,13,0.025) 0, transparent 0.7px),
          radial-gradient(circle at 71% 56%, rgba(20,17,13,0.025) 0, transparent 0.7px);
        background-size: 7px 7px, 11px 11px;
      }
      .atelier-page * { box-sizing: border-box; }
      .atelier-page button, .atelier-page input, .atelier-page textarea { font: inherit; color: inherit; }
      .atelier-page button { border: 0; background: transparent; cursor: pointer; }
      .spread { width: min(1280px, 100%); margin: 0 auto; padding-left: clamp(22px, 4vw, 48px); padding-right: clamp(22px, 4vw, 48px); }
      .grid-12 { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 24px; }
      .grid-span-4 { grid-column: span 4; }
      .grid-span-8 { grid-column: span 8; }
      .t-display, .brand-name, .session-title { font-family: var(--display); font-weight: 900; letter-spacing: -0.035em; line-height: .95; }
      .t-mono, .atelier-nav button, .atelier-nav a, .btn { font-family: var(--mono); font-size: 10px; letter-spacing: .13em; text-transform: uppercase; font-weight: 800; }
      .t-mono-low { font-family: var(--mono); font-size: 10px; letter-spacing: .06em; color: var(--ink-2); }
      .t-num { font-family: var(--display); font-weight: 900; letter-spacing: -.04em; font-variant-numeric: tabular-nums; }
      .fr { font-family: var(--serif); font-style: italic; font-size: 23px; line-height: 1.28; }
      .blue { color: var(--blue); }
      .yellow { color: #8a6800; }
      .red { color: var(--red); }
      .between { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
      .rule { height: 1px; background: var(--ink); width: 100%; }
      .rule.thick { height: 4px; }
      .btn { display: inline-flex; align-items: center; justify-content: center; gap: 9px; min-height: 40px; padding: 0 18px; border: 1px solid var(--ink); background: var(--paper); transition: .12s ease; }
      .btn:hover:not(:disabled) { background: var(--ink); color: var(--paper); }
      .btn:disabled { opacity: .45; cursor: not-allowed; }
      .btn.red { background: var(--red); border-color: var(--red); color: var(--paper); }
      .btn.solid { background: var(--ink); color: var(--paper); }
      .btn.ghost { border-color: transparent; padding-inline: 10px; }
      .btn.lg { min-height: 56px; padding-inline: 28px; font-size: 11px; }
      .paper-2, .paper-frame { background: var(--paper-2); border: 1px solid var(--ink); position: relative; }
      .paper-frame { border-width: 2px; background: var(--paper); }
      .crop-mark { position: absolute; width: 12px; height: 12px; pointer-events: none; }
      .crop-mark.tl { top: -1px; left: -1px; border-top: 1px solid var(--ink); border-left: 1px solid var(--ink); }
      .crop-mark.tr { top: -1px; right: -1px; border-top: 1px solid var(--ink); border-right: 1px solid var(--ink); }
      .crop-mark.bl { bottom: -1px; left: -1px; border-bottom: 1px solid var(--ink); border-left: 1px solid var(--ink); }
      .crop-mark.br { bottom: -1px; right: -1px; border-bottom: 1px solid var(--ink); border-right: 1px solid var(--ink); }
      .atelier-masthead { border-bottom: 1px solid var(--ink); background: var(--paper); }
      .masthead-inner { min-height: 58px; display: flex; align-items: center; justify-content: space-between; gap: 24px; }
      .brand-lockup { display: flex; align-items: center; gap: 12px; color: var(--ink); text-decoration: none; }
      .brand-name { font-size: 22px; }
      .atelier-nav { display: flex; align-items: center; gap: 18px; }
      .atelier-nav button, .atelier-nav a { color: var(--ink-3); padding-bottom: 3px; border-bottom: 2px solid transparent; text-decoration: none; }
      .atelier-nav button.active { color: var(--ink); border-bottom-color: var(--ink); }
      .atelier-nav a:hover { color: var(--ink); border-bottom-color: var(--ink); }
      .atelier-nav button:disabled { opacity: .35; cursor: not-allowed; }
      .nav-rule { width: 1px; height: 20px; background: var(--ink); }
      .loading { min-height: 60vh; display: grid; place-items: center; font-family: var(--mono); letter-spacing: .14em; color: var(--ink-2); }
      .today-spread { padding-top: 32px; padding-bottom: 80px; }
      .atelier-title {
        display: flex;
        align-items: end;
        justify-content: space-between;
        gap: 24px;
        border-bottom: 4px solid var(--ink);
        padding-bottom: 20px;
        margin-bottom: 24px;
      }
      .atelier-title h1 {
        margin: 8px 0 0;
        font-family: var(--serif);
        font-size: clamp(36px, 5vw, 58px);
        line-height: .95;
        letter-spacing: 0;
        font-style: italic;
        font-weight: 700;
      }
      .atelier-passport {
        padding: 28px 32px;
        background: var(--paper);
      }
      .passport-grid {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 340px;
        gap: 28px;
        align-items: start;
      }
      .atelier-kicker {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 18px;
      }
      .atelier-kicker span {
        border: 1px solid var(--ink);
        background: var(--paper-2);
        padding: 5px 8px;
        font-size: 10px;
        letter-spacing: .12em;
        text-transform: uppercase;
        font-weight: 900;
      }
      .practice-summary h2 {
        margin: 0;
        font-family: var(--serif);
        font-size: clamp(30px, 4vw, 48px);
        line-height: 1;
        letter-spacing: 0;
        font-style: italic;
        font-weight: 700;
      }
      .practice-summary p {
        max-width: 780px;
        color: var(--ink-2);
        line-height: 1.5;
        font-size: 17px;
      }
      .quote-card {
        border-left: 4px solid var(--blue);
        background: var(--paper-2);
        padding: 16px 18px;
      }
      .quote-card .fr {
        margin: 12px 0 0;
      }
      .atelier-loop {
        margin-top: 20px;
        border-top: 2px solid var(--ink);
        padding-top: 14px;
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
      }
      .atelier-loop span {
        background: var(--ink);
        color: var(--paper);
        padding: 7px 10px;
        font-size: 10px;
        letter-spacing: .1em;
        text-transform: uppercase;
        font-weight: 900;
      }
      .today-opening { align-items: end; margin-bottom: 24px; }
      .practice-plate { grid-column: span 5; border-top: 2px solid var(--ink); padding-top: 14px; }
      .practice-time { font-size: 48px; line-height: .95; font-family: var(--display); font-weight: 900; letter-spacing: -.04em; margin-top: 10px; }
      .practice-plate p, .stat p, .quote-source, .quote-author, .exercise-toolbar p, .empty-slip p { color: var(--ink-2); font-size: 13px; }
      .quote-plate { grid-column: 8 / span 5; padding: 16px 0; border-top: 1px solid var(--ink); border-bottom: 1px solid var(--ink); }
      .quote-author { margin-top: 8px; }
      .quote-source { margin-top: 2px; color: var(--ink-3); }
      .today-set-head { margin: 28px 0 14px; }
      .concept-cover { min-height: 292px; border: 1px solid var(--ink); background: var(--paper); display: flex; flex-direction: column; color: var(--ink); }
      .concept-cover.active { background: var(--paper-deep); color: var(--paper); }
      .concept-cover.compact { min-height: 140px; height: 100%; }
      .cover-band { min-height: 36px; color: var(--paper); display: flex; align-items: center; justify-content: space-between; padding: 0 14px; border-bottom: 1px solid currentColor; font-family: var(--mono); font-size: 10px; font-weight: 800; letter-spacing: .08em; }
      .cover-symbol { flex: 1; min-height: 120px; display: flex; align-items: center; justify-content: center; padding: 26px; }
      .compact .cover-symbol { min-height: 58px; padding: 10px; }
      .cover-title { border-top: 1px solid currentColor; padding: 14px; }
      .cover-title h3 { margin: 0; font-family: var(--display); font-size: 24px; line-height: 1.03; letter-spacing: -.035em; font-weight: 900; }
      .compact .cover-title h3 { font-size: 15px; }
      .cover-foot { border-top: 1px solid var(--ink); padding: 10px 14px; color: var(--ink-2); font-size: 13px; display: flex; align-items: center; gap: 8px; }
      .cover-foot span:nth-child(2) { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .cover-ref, .notebook-link { margin-left: auto; font-family: var(--mono); font-size: 10px; text-transform: uppercase; letter-spacing: .08em; color: var(--blue); text-decoration: none; white-space: nowrap; }
      .status-dot, .red-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
      .red-dot { background: var(--red); }
      .black-square { width: 7px; height: 7px; background: var(--ink); display: inline-block; }
      .stat-row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 24px; margin-top: 30px; }
      .stat { border-top: 2px solid var(--ink); padding-top: 10px; min-height: 108px; }
      .stat .t-num { font-size: 54px; line-height: .9; }
      .stat p { margin: 4px 0 0; }
      .lower-board { margin-top: 48px; }
      .side-stack { display: grid; gap: 24px; align-content: start; }
      .atlas-head { min-height: 44px; padding: 0 14px; border-bottom: 1px solid var(--ink); display: flex; align-items: center; justify-content: space-between; }
      .atlas-plot { height: 420px; margin: 36px 48px 48px; border-left: 2px solid var(--ink); border-bottom: 2px solid var(--ink); position: relative; background-image: linear-gradient(var(--paper-3) 1px, transparent 1px), linear-gradient(90deg, var(--paper-3) 1px, transparent 1px); background-size: 100% 33.33%, 25% 100%; }
      .danger-zone { position: absolute; left: 12px; top: 10px; width: 38%; height: 44%; background: rgba(216,50,26,.08); color: var(--red); padding: 10px; font-family: var(--mono); font-size: 10px; letter-spacing: .2em; }
      .axis-y, .axis-x { position: absolute; font-family: var(--mono); font-size: 10px; letter-spacing: .12em; color: var(--ink-2); }
      .axis-y { left: -34px; top: 0; }
      .axis-x { right: 0; bottom: -28px; }
      .atlas-dot { position: absolute; width: 18px; height: 18px; border: 2px solid var(--ink); border-radius: 50%; background: var(--red); transform: translate(-50%, -50%); box-shadow: 0 0 0 4px var(--paper); }
      .atlas-dot.foundation { background: var(--blue); }
      .notebook-bridge header { padding: 14px; border-bottom: 1px solid var(--ink); display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; }
      .notebook-bridge header p { margin: 6px 0 0; color: var(--ink-2); font-size: 12px; line-height: 1.35; }
      .notebook-rows { display: grid; }
      .notebook-row { display: grid; grid-template-columns: 24px 42px 1fr 42px; align-items: center; gap: 10px; min-height: 66px; padding: 10px 14px; border-top: 1px solid var(--paper-3); color: var(--ink); text-decoration: none; }
      .notebook-row:hover { background: var(--paper); }
      .notebook-row strong { min-width: 0; font-size: 13px; line-height: 1.18; }
      .notebook-foot { margin: 0; padding: 12px 14px; border-top: 1px solid var(--ink); color: var(--ink-2); font-size: 12px; line-height: 1.35; }
      .mission-bridge { padding: 14px; display: grid; gap: 14px; }
      .mission-bridge header { display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; }
      .mission-bridge header p { margin: 6px 0 0; color: var(--ink-2); font-size: 12px; line-height: 1.35; }
      .mission-bridge .btn { width: 100%; }
      .priority-list header { padding: 12px 14px; border-bottom: 1px solid var(--ink); display: flex; justify-content: space-between; }
      .priority-list > a, .priority-list > div { display: grid; grid-template-columns: 32px 1fr 56px 20px; gap: 10px; align-items: center; min-height: 54px; padding: 8px 14px; border-top: 1px solid var(--paper-3); color: var(--ink); text-decoration: none; }
      .priority-list > a:hover { background: var(--paper); }
      .priority-list .empty-priority { grid-template-columns: 1fr; align-items: start; }
      .priority-list strong { font-size: 13px; line-height: 1.25; }
      .priority-list .selected { background: var(--paper); }
      .cefr { border: 1px solid var(--ink); height: 20px; display: inline-flex; align-items: center; justify-content: center; font-family: var(--mono); font-size: 10px; font-weight: 800; }
      .status-ring { width: 11px; height: 11px; border: 2px solid var(--ink-3); border-radius: 50%; }
      .due-errata-list header { padding: 12px 14px; border-bottom: 1px solid var(--ink); display: flex; justify-content: space-between; }
      .due-errata-list article { display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: center; padding: 12px 14px; border-top: 1px solid var(--paper-3); }
      .due-errata-list strong { font-size: 13px; }
      .due-errata-list p { margin: 4px 0 0; color: var(--ink-2); font-size: 12px; line-height: 1.35; }
      .due-errata-list .memory-meta { font-family: var(--mono); text-transform: uppercase; letter-spacing: 0; font-size: 10px; color: var(--muted); }
      .due-errata-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
      .due-errata-actions .notebook-link { margin-left: 0; }
      .atelier-footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--ink); display: flex; justify-content: space-between; color: var(--ink-2); font-size: 12px; }
      .session-spread { padding-top: 24px; padding-bottom: 80px; }
      .session-title-row { display: flex; align-items: center; justify-content: space-between; padding-bottom: 14px; }
      .session-title { font-size: 24px; margin-left: 14px; }
      .concept-bench { margin-top: 24px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; }
      .concept-bench button { text-align: left; }
      .round-strip { margin-top: 28px; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); border: 1px solid var(--ink); }
      .round-strip button { min-height: 50px; border-right: 1px solid var(--ink); text-align: left; padding: 0 18px; font-family: var(--mono); font-size: 10px; letter-spacing: .13em; text-transform: uppercase; font-weight: 900; }
      .round-strip button:last-child { border-right: 0; }
      .round-strip button.active { background: var(--ink); color: var(--paper); }
      .round-strip span { font-size: 24px; vertical-align: middle; margin-right: 10px; }
      .xray-title { margin: 36px 0 14px; }
      .xray-board { background: var(--paper-2); border: 1px solid var(--ink); padding: 28px 32px 24px; position: relative; display: grid; grid-template-columns: 1.25fr .75fr; gap: 30px; }
      .sentence-xray { padding-top: 12px; padding-bottom: 34px; }
      .sentence-xray > p { margin: 0; font-family: var(--serif); font-style: italic; font-size: 39px; line-height: 1.45; }
      .marked { position: relative; display: inline-block; padding-bottom: 3px; border-bottom: 3px solid var(--ink); }
      .marked em { position: absolute; left: 50%; top: 100%; transform: translateX(-50%); margin-top: 11px; font-family: var(--mono); font-style: normal; font-size: 9px; font-weight: 900; letter-spacing: .12em; white-space: nowrap; color: inherit; }
      .mark-0 { color: var(--blue); border-color: var(--blue); }
      .mark-1 { color: var(--ink); border-color: var(--ink); }
      .mark-2 { color: var(--red); border-color: var(--red); }
      .xray-legend { margin-top: 54px; display: flex; flex-wrap: wrap; gap: 14px; border-top: 1px solid var(--paper-3); padding-top: 16px; }
      .xray-legend span { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-2); font-size: 12px; }
      .legend-box { width: 10px; height: 10px; display: inline-block; background: var(--ink); }
      .legend-box.mark-0 { background: var(--blue); }
      .legend-box.mark-2 { background: var(--red); }
      .grammar-block { background: var(--paper); border-left: 4px solid var(--blue); padding: 16px 18px; }
      .rule-panel h3 { margin: 8px 0 10px; font-size: 17px; }
      .rule-panel p { margin: 8px 0; font-size: 13px; line-height: 1.45; color: var(--ink-2); }
      .rule-panel > p:first-of-type { color: var(--ink); font-weight: 700; }
      .examples { border-top: 1px solid var(--paper-3); margin-top: 13px; padding-top: 10px; font-family: var(--serif); font-style: italic; font-size: 17px; }
      .work-grid { margin-top: 40px; align-items: start; }
      .exercise-toolbar { display: flex; justify-content: space-between; gap: 24px; align-items: flex-end; margin-bottom: 14px; }
      .mode-markers { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border: 1px solid var(--ink); min-width: 520px; }
      .mode-markers button { min-height: 44px; border-right: 1px solid var(--ink); font-family: var(--mono); font-size: 10px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; }
      .mode-markers button small { display: block; margin-top: 3px; letter-spacing: .08em; opacity: .72; }
      .mode-markers button:last-child { border-right: 0; }
      .mode-markers button.active { background: var(--ink); color: var(--paper); }
      .exercise-frame { min-height: 520px; padding: 28px 32px; }
      .recognize-set, .transform-set { display: grid; gap: 18px; }
      .sub-exercise { border-bottom: 1px solid var(--paper-3); padding-bottom: 18px; }
      .sub-exercise:last-child { border-bottom: 0; }
      .sub-exercise .t-mono-low { display: inline-flex; align-items: center; gap: 6px; }
      .exercise-prompt, .source-sentence { font-family: var(--serif); font-style: italic; font-size: 29px; line-height: 1.45; margin: 12px 0 20px; }
      .source-sentence { background: var(--paper-2); border: 1px solid var(--ink); padding: 14px 16px; }
      .instruction { margin: 10px 0 0; font-weight: 700; color: var(--ink-2); }
      .choice-row, .type-case, .target-chips { display: flex; flex-wrap: wrap; gap: 10px; }
      .choice-row button, .type-case span, .target-chips span { border: 1px solid var(--ink); background: var(--paper); padding: 8px 15px; font-family: var(--serif); font-style: italic; font-size: 19px; }
      .choice-row.compact button, .target-chips span { font-family: var(--mono); font-style: normal; font-size: 10px; letter-spacing: .1em; text-transform: uppercase; font-weight: 900; }
      .choice-row button.selected { background: var(--blue); color: var(--paper); }
      .type-case { margin-bottom: 12px; padding: 14px; background: var(--paper-2); border: 1px solid var(--ink); }
      .sub-exercise input, .sub-exercise textarea, .produce-panel textarea, .output-ladder-panel textarea { width: 100%; border: 1px solid var(--ink); background: var(--paper); outline: none; padding: 13px 15px; font-family: var(--serif); font-style: italic; font-size: 19px; }
      .sub-exercise textarea { min-height: 86px; resize: vertical; }
      .inline-feedback { margin-top: 12px; border-left: 4px solid var(--blue); background: rgba(29,58,138,.06); padding: 10px 12px; font-size: 13px; line-height: 1.42; color: var(--ink-2); }
      .inline-feedback.correct { display: inline-flex; align-items: center; gap: 8px; border-left-color: var(--ink); background: rgba(20,17,13,.06); color: var(--ink); font-family: var(--mono); font-size: 10px; letter-spacing: .12em; text-transform: uppercase; font-weight: 900; }
      .output-ladder-panel { display: grid; gap: 18px; }
      .ladder-stage { display: grid; grid-template-columns: 1fr auto; gap: 24px; align-items: start; border-bottom: 2px solid var(--ink); padding-bottom: 18px; }
      .ladder-stage h3 { margin: 8px 0 6px; font-family: var(--display); font-size: 31px; letter-spacing: -.04em; line-height: .96; }
      .ladder-stage p, .example-answer { margin: 0; color: var(--ink-2); line-height: 1.45; }
      .stage-meter { display: grid; grid-template-columns: repeat(6, 26px); border: 1px solid var(--ink); }
      .stage-meter span { height: 26px; display: grid; place-items: center; border-right: 1px solid var(--ink); font-family: var(--mono); font-size: 10px; font-weight: 900; }
      .stage-meter span:last-child { border-right: 0; }
      .stage-meter .active { background: var(--ink); color: var(--paper); }
      .output-ladder-panel .live-block { border-left: 4px solid var(--yellow); padding: 14px 18px; background: var(--paper); }
      .voice-capture { display: flex; align-items: center; gap: 14px; border: 1px solid var(--ink); background: var(--paper-2); padding: 12px 14px; }
      .voice-capture span { color: var(--ink-2); font-size: 13px; line-height: 1.35; }
      .voice-button { height: 42px; min-width: 132px; display: inline-flex; align-items: center; justify-content: center; gap: 8px; background: var(--ink); color: var(--paper); border: 1px solid var(--ink); font-family: var(--mono); font-size: 11px; letter-spacing: .18em; font-weight: 900; }
      .voice-button.recording { background: var(--red); border-color: var(--red); }
      .voice-button:disabled { opacity: .45; cursor: not-allowed; }
      .spin { animation: spin .7s linear infinite; }
      .output-ladder-panel textarea { min-height: 150px; resize: vertical; box-shadow: 5px 5px 0 var(--ink); }
      .output-speak textarea { min-height: 118px; }
      .output-conversation .live-block { border-left-color: var(--blue); }
      .produce-panel .live-block { border-left: 4px solid var(--yellow); padding: 14px 18px; background: var(--paper); }
      .produce-panel .live-block p:not(.fr) { color: var(--ink-2); max-width: 680px; }
      .produce-panel textarea { margin-top: 18px; min-height: 250px; resize: vertical; }
      .target-chips { margin-top: 16px; }
      .word-count { text-align: right; margin-top: 10px; font-family: var(--mono); font-size: 10px; letter-spacing: .1em; text-transform: uppercase; color: var(--ink-2); }
      .action-row { margin-top: 24px; display: flex; gap: 12px; align-items: center; }
      .margin-stack { display: grid; gap: 26px; }
      .tutor-note { border-top: 2px solid var(--ink); padding-top: 16px; }
      .tutor-note h3 { font-size: 18px; margin: 14px 0 8px; }
      .tutor-note p { font-size: 13px; line-height: 1.5; color: var(--ink-2); }
      .errata-column { display: grid; gap: 14px; }
      .empty-slip { border: 1px dashed var(--ink-3); padding: 20px 16px; }
      .errata-slip { position: relative; background: var(--paper); border: 2px solid var(--ink); padding: 38px 18px 18px; box-shadow: 5px 5px 0 var(--ink); transform: rotate(-1deg); animation: slip-in .24s both; }
      .slip-label { position: absolute; top: -12px; left: 16px; background: var(--red); color: var(--paper); padding: 5px 12px; font-family: var(--mono); font-size: 10px; letter-spacing: .1em; text-transform: uppercase; font-weight: 900; }
      .slip-num { position: absolute; right: 0; top: 0; background: var(--ink); color: var(--paper); padding: 4px 8px; font-family: var(--mono); font-size: 10px; }
      .errata-slip .wrong, .errata-slip .right { font-family: var(--serif); font-style: italic; font-size: 19px; line-height: 1.35; }
      .errata-slip .wrong { color: var(--red); text-decoration: line-through; text-decoration-thickness: 2px; }
      .errata-slip .right { background: linear-gradient(transparent 62%, rgba(243,195,24,.45) 62%); display: inline; }
      .why { margin-top: 14px; border-left: 4px solid var(--blue); padding-left: 12px; color: var(--ink-2); font-size: 13px; line-height: 1.45; }
      .slip-memory { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--paper-3); font-family: var(--mono); text-transform: uppercase; font-size: 10px; color: var(--muted); }
      .slip-link { display: inline-block; margin: 10px 0 0; }
      .recap-overlay { position: fixed; inset: 0; background: rgba(20,17,13,.84); z-index: 1000; display: grid; place-items: center; padding: 28px; }
      .errata-review-overlay { z-index: 1010; }
      .errata-review-modal { width: min(900px, 96vw); max-height: 90vh; overflow: auto; background: var(--paper); border: 2px solid var(--ink); position: relative; box-shadow: 8px 8px 0 var(--ink); }
      .errata-review-modal header { padding: 28px 36px 20px; border-bottom: 2px solid var(--ink); display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; }
      .errata-review-modal h2 { margin: 8px 0 0; font-family: var(--display); font-size: 42px; line-height: .95; letter-spacing: -.04em; }
      .errata-review-body { display: grid; grid-template-columns: .9fr 1.1fr; gap: 28px; padding: 28px 36px 34px; }
      .errata-review-copy { border-left: 4px solid var(--yellow); padding-left: 18px; }
      .errata-review-copy p { color: var(--ink-2); line-height: 1.48; margin: 10px 0 0; }
      .review-prompt { font-family: var(--serif); font-style: italic; font-size: 25px; line-height: 1.3; color: var(--ink) !important; }
      .review-memory { margin-top: 18px; border: 1px solid var(--ink); background: var(--paper-2); padding: 12px 14px; }
      .review-memory .wrong { margin-top: 6px; font-family: var(--serif); font-style: italic; color: var(--red); text-decoration: line-through; text-decoration-thickness: 2px; }
      .errata-review-answer textarea { width: 100%; min-height: 150px; margin-top: 10px; border: 2px solid var(--ink); background: var(--paper); padding: 14px 16px; outline: none; resize: vertical; font-family: var(--serif); font-size: 22px; font-style: italic; box-shadow: 5px 5px 0 var(--ink); }
      .review-result { margin-top: 18px; border-left: 4px solid var(--red); background: rgba(216,50,26,.06); padding: 12px 14px; color: var(--ink-2); line-height: 1.45; }
      .review-result.correct { border-left-color: var(--blue); background: rgba(29,58,138,.06); }
      .review-result p { margin: 6px 0 0; }
      .review-result .right { font-family: var(--serif); font-style: italic; background: linear-gradient(transparent 62%, rgba(243,195,24,.45) 62%); }
      .recap-modal { width: min(960px, 96vw); max-height: 90vh; overflow: auto; background: var(--paper); border: 2px solid var(--ink); position: relative; }
      .recap-modal header { padding: 28px 36px 20px; border-bottom: 2px solid var(--ink); display: flex; justify-content: space-between; align-items: flex-end; }
      .recap-modal h2 { margin: 8px 0 0; font-family: var(--display); font-size: 54px; line-height: .95; letter-spacing: -.04em; }
      .recap-stats { padding: 20px 36px; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 24px; border-bottom: 1px solid var(--ink); }
      .recap-lines { padding: 20px 36px; }
      .recap-lines > div:not(.t-mono) { display: grid; grid-template-columns: 42px 1fr 80px 120px; align-items: center; gap: 14px; padding: 12px 0; border-top: 1px solid var(--paper-3); }
      .recap-lines svg { width: 32px; height: 32px; }
      .recap-modal footer { padding: 16px 36px; border-top: 1px solid var(--ink); display: flex; justify-content: space-between; align-items: center; }
      .recap-actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
      @keyframes spin { to { transform: rotate(360deg); } }
      @keyframes slip-in { from { opacity: 0; transform: translate(18px, -8px) rotate(2deg); } to { opacity: 1; transform: translate(0, 0) rotate(-1deg); } }
      @media (max-width: 960px) {
        .grid-12, .today-opening, .passport-grid, .lower-board, .work-grid, .xray-board { grid-template-columns: 1fr; }
        .grid-span-4, .grid-span-8, .practice-plate, .quote-plate { grid-column: auto; }
        .concept-grid, .concept-bench, .stat-row, .recap-stats { grid-template-columns: 1fr; }
        .errata-review-body { grid-template-columns: 1fr; }
        .masthead-inner, .atelier-title, .atelier-nav, .exercise-toolbar, .atelier-footer { align-items: flex-start; flex-direction: column; }
        .atelier-passport { padding: 22px 18px; }
        .mode-markers { min-width: 0; width: 100%; }
        .sentence-xray > p { font-size: 31px; }
      }
    `}</style>
  );
}

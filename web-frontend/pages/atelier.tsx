import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
  VocabularyRecommendationItem,
} from '@/services/api';
import { ConceptMotif } from '@/components/grammar/ConceptMotif';
import EditorialMasthead from '@/components/layout/EditorialMasthead';
import {
  buildDayProgress,
  resolveRecommendedNext,
  serialActionFromToday,
  type DayProgress,
  type RecommendedAction,
} from '@/lib/atelier-next';

type RoundName = 'recognize' | 'transform' | 'sentence' | 'produce' | 'speak' | 'conversation';
type RecognizeMode = 'fill' | 'word_bank' | 'classify';
type RoadmapTarget = RoundName | 'review' | 'mission' | 'feuilleton' | 'rest';
type RoadmapAction = {
  label: string;
  onClick: () => void;
};
type RoadmapNode = {
  id: string;
  label: string;
  target: RoadmapTarget;
  href?: string;
};

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

function isRoundName(value: unknown): value is RoundName {
  return roundLabels.some((item) => item.id === value);
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
    label: String(requirement.label || concept.atelier_blueprint?.display_title || concept.name || 'Target'),
  };
}

function wordCount(text: string) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function wordRangeLabel(count: number, minWords?: unknown, maxWords?: unknown) {
  const min = Number(minWords);
  const max = Number(maxWords);
  if (Number.isFinite(min) && Number.isFinite(max) && min > 0 && max >= min) {
    return `${count} / ${Math.round(min)}-${Math.round(max)} words`;
  }
  return `${count} words`;
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

function joinWordBankTokens(tokens: any[]) {
  return tokens
    .map((token) => String(token || '').trim())
    .filter(Boolean)
    .join(' ')
    .replace(/\s+([,.;:!?])/g, '$1')
    .replace(/([cdjlmnst])'\s+/gi, "$1'")
    .replace(/\s+/g, ' ')
    .trim();
}

function wordBankTokensFromAnswer(answer: any) {
  if (Array.isArray(answer)) {
    return answer.map((token) => String(token || '').trim()).filter(Boolean);
  }
  return String(answer || '').trim().split(/\s+/).filter(Boolean);
}

function wordBankTokenIsUsed(answerTokens: string[], sourceTokens: string[], token: string, tokenIndex: number) {
  const sameToken = (value: string) => value === token;
  const previousCopies = sourceTokens.slice(0, tokenIndex).filter(sameToken).length;
  const usedCopies = answerTokens.filter(sameToken).length;
  return usedCopies > previousCopies;
}

function correctionWithAiReview(result: AtelierAttemptResult | AtelierAttemptRead) {
  const correction = { ...(result.correction || {}) };
  const aiReview = correction.ai_review || (result as AtelierAttemptResult).ai_review || {};
  correction.ai_review = aiReview;
  return correction;
}

function aiReviewStatus(correction: Record<string, any> | null | undefined) {
  return String(correction?.ai_review?.status || '');
}

function errataForAttempt(correction: Record<string, any>, attemptId?: string) {
  return (correction.errata || []).map((item: AtelierErratum) => ({ ...item, source_attempt_id: attemptId || item.source_attempt_id }));
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
  const [attemptIdsByKey, setAttemptIdsByKey] = useState<Record<string, string>>({});
  const [aiReviewSubmitting, setAiReviewSubmitting] = useState<Record<string, boolean>>({});
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
  const [vocabularyDue, setVocabularyDue] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const aiPollTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const scheduleAiReviewPollingRef = useRef<(attemptId: string, key: string, remaining?: number) => void>(() => {});

  const hydrateSession = useCallback((next: AtelierSessionStart, openSession = false) => {
    const restoredAnswers: Record<string, Record<string, any>> = {};
    const restoredSubmitted: Record<string, boolean> = { ...(next.submitted_map || {}) };
    const restoredCorrections: Record<string, Record<string, any>> = {};
    const restoredAttemptIds: Record<string, string> = {};
    const restoredErrata: AtelierErratum[] = [];

    (next.attempts || []).forEach((attempt: AtelierAttemptRead) => {
      const key = attempt.submitted_key || answerKey(attempt.round, attempt.round === 'recognize' ? attempt.mode : attempt.round, attempt.concept_id);
      const correction = correctionWithAiReview(attempt);
      restoredSubmitted[key] = true;
      restoredCorrections[key] = correction;
      restoredAttemptIds[key] = attempt.attempt_id;
      if (['sentence', 'produce', 'speak', 'conversation'].includes(attempt.round)) {
        restoredAnswers[key] = { text: attempt.answer_payload?.text || '' };
      } else {
        restoredAnswers[key] = { ...(attempt.answer_payload?.answers || {}) };
      }
      errataForAttempt(correction, attempt.attempt_id).forEach((item: AtelierErratum) => restoredErrata.unshift(item));
      if (aiReviewStatus(correction) === 'pending') {
        scheduleAiReviewPollingRef.current(attempt.attempt_id, key);
      }
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
    setAttemptIdsByKey(restoredAttemptIds);
    setErrata(restoredErrata);
    setRecentCorrection((next.attempts || []).slice(-1)[0] ? correctionWithAiReview((next.attempts || []).slice(-1)[0]) : null);
    setRecap(next.status === 'completed' && next.recap ? next.recap : null);
    setActiveConceptIndex(Math.max(0, Math.min(conceptIndex, next.concepts.length - 1)));
    setRound(nextRound as RoundName);
    setMode(recognizeModes.some((item) => item.id === position.mode) ? position.mode as RecognizeMode : 'fill');
    if (openSession) {
      setView('session');
    }
  }, []);

  useEffect(() => {
    scheduleAiReviewPollingRef.current = scheduleAiReviewPolling;
  });

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setLoadError(null);
    Promise.all([
      apiService.getAtelierToday(),
      apiService.getActiveAtelierSession(),
      apiService.getVocabularyDueContext({
        limit: 1,
        due_limit: 1,
        fragile_limit: 0,
        new_limit: 0,
        topic_limit: 0,
        linked_limit: 0,
        direction: 'fr_to_de',
      }).catch(() => null),
    ])
      .then(([todayData, active, vocabularyContext]) => {
        if (!alive) return;
        setToday(todayData);
        setVocabularyDue(Number(vocabularyContext?.summary?.due || 0));
        if (active.session) {
          hydrateSession(active.session);
        } else {
          setSession(null);
        }
      })
      .catch((error) => {
        console.error(error);
        if (!alive) return;
        setLoadError('Atelier is unavailable right now. Keep the phone flow calm: retry, or come back after the connection is restored.');
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [hydrateSession, reloadKey]);

  useEffect(() => {
    return () => {
      Object.values(aiPollTimers.current).forEach((timer) => clearTimeout(timer));
      aiPollTimers.current = {};
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
  const dayProgress = useMemo(
    () => buildDayProgress({
      today,
      session,
      vocabularyDue,
    }),
    [today, session, vocabularyDue],
  );
  const recommendation = useMemo(
    () => resolveRecommendedNext(today, session, dayProgress),
    [today, session, dayProgress],
  );

  function applyAttemptResult(key: string, result: AtelierAttemptResult, replaceErrata = false, schedulePending = true) {
    const correction = correctionWithAiReview(result);
    setAttemptIdsByKey((prev) => ({ ...prev, [key]: result.attempt_id }));
    setCorrectionsByKey((prev) => ({ ...prev, [key]: correction }));
    setRecentCorrection(correction);
    const nextErrata = errataForAttempt(correction, result.attempt_id);
    if (replaceErrata) {
      setErrata((prev) => [
        ...nextErrata,
        ...prev.filter((item) => item.source_attempt_id !== result.attempt_id),
      ]);
    } else if (nextErrata.length) {
      setErrata((prev) => [...nextErrata, ...prev]);
    }
    if (schedulePending && aiReviewStatus(correction) === 'pending') {
      scheduleAiReviewPolling(result.attempt_id, key);
    }
    return correction;
  }

  function scheduleAiReviewPolling(attemptId: string, key: string, remaining = 10) {
    if (!attemptId || remaining <= 0) return;
    const existing = aiPollTimers.current[attemptId];
    if (existing) {
      clearTimeout(existing);
    }
    aiPollTimers.current[attemptId] = setTimeout(async () => {
      try {
        const result = await apiService.getAtelierAttempt(attemptId);
        const correction = applyAttemptResult(key, result, true, false);
        if (aiReviewStatus(correction) === 'pending' && remaining > 1) {
          scheduleAiReviewPolling(attemptId, key, remaining - 1);
        } else {
          delete aiPollTimers.current[attemptId];
        }
      } catch (error) {
        console.error(error);
        if (remaining > 1) {
          scheduleAiReviewPolling(attemptId, key, remaining - 1);
        } else {
          delete aiPollTimers.current[attemptId];
        }
      }
    }, 2000);
  }

  const requestAiReview = async () => {
    const attemptId = attemptIdsByKey[scopedKey];
    if (!attemptId || aiReviewSubmitting[scopedKey]) return;
    setAiReviewSubmitting((prev) => ({ ...prev, [scopedKey]: true }));
    try {
      const result = await apiService.requestAtelierAttemptAiReview(attemptId);
      applyAttemptResult(scopedKey, result, true);
      toast('AI correction started.');
    } catch (error) {
      console.error(error);
      toast.error('AI correction is unavailable.');
    } finally {
      setAiReviewSubmitting((prev) => ({ ...prev, [scopedKey]: false }));
    }
  };

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
      hydrateSession(next, true);
    } catch (error) {
      console.error(error);
      setLoadError('Could not start today’s session. Check the connection and retry from this screen.');
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
      const attemptKey = scopedKey;
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
      applyAttemptResult(attemptKey, result);
      setSubmitted((prev) => ({ ...prev, [attemptKey]: true }));
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

  const openRecommendedReview = (action?: Extract<RecommendedAction, { kind: 'review' }>) => {
    const errataDue = action?.errataDue ?? dayProgress.errataDue;
    const vocabDue = action?.vocabularyDue ?? dayProgress.vocabularyDue;
    if (errataDue > 0) {
      const dueErratum = firstDueErratum(today, session);
      if (dueErratum?.id) {
        void openErratumReview(dueErratum.id);
        return;
      }
    }
    if (vocabDue > 0 || errataDue === 0) {
      void router.push('/vocabulary/review');
      return;
    }
    toast('Review queue is clear.');
  };

  const handleRecommendedAction = (action: RecommendedAction = recommendation) => {
    if (action.kind === 'resume_session') {
      if (session) {
        const nextRound = isRoundName(action.round) ? action.round : 'recognize';
        const nextConceptIndex = Math.max(0, Math.min(action.conceptIndex || 0, session.concepts.length - 1));
        setRound(nextRound);
        setActiveConceptIndex(nextConceptIndex);
        if (nextRound === 'recognize' && recognizeModes.some((item) => item.id === action.mode)) {
          setMode(action.mode as RecognizeMode);
        }
      }
      setView('session');
      return;
    }
    if (action.kind === 'start_session') {
      void startSession();
      return;
    }
    if (action.kind === 'review') {
      openRecommendedReview(action);
      return;
    }
    if (action.kind === 'mission') {
      void router.push(`/missions${action.query}`);
      return;
    }
    if (action.kind === 'feuilleton') {
      void router.push(`/graphic-novel${action.query}`);
      return;
    }
    if (action.kind === 'serial') {
      void router.push(`/${action.episodeKind === 'mission' ? 'missions' : 'graphic-novel'}${action.query}`);
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
        <Masthead view={view} />
        {loading ? (
          <div className="spread loading">LOADING ATELIER</div>
        ) : view === 'today' || !session ? (
          <TodayView
            today={today}
            activeSession={session}
            onContinue={() => setView('session')}
            onStart={startSession}
            dayProgress={dayProgress}
            recommendation={recommendation}
            onRecommendedAction={handleRecommendedAction}
            onOpenReview={() => openRecommendedReview()}
            loading={submitting}
            loadError={loadError}
            onRetry={() => setReloadKey((key) => key + 1)}
          />
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
            requestAiReview={requestAiReview}
            aiReviewSubmitting={!!aiReviewSubmitting[scopedKey]}
            completedDrills={completedDrills}
            onBack={() => setView('today')}
            produceAnswer={answers[answerKey('produce', 'produce', null)]?.text || ''}
          />
        )}
        {recap && (
          <RecapModal
            recap={recap}
            concepts={session?.concepts || []}
            recommendation={recommendation}
            onRecommendedAction={() => {
              setRecap(null);
              setView('today');
              handleRecommendedAction(recommendation);
            }}
            onClose={() => {
              setRecap(null);
              setView('today');
            }}
          />
        )}
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

function Masthead({ view }: { view: 'today' | 'session' }) {
  if (view === 'today') return null;

  return (
    <EditorialMasthead
      active="studio"
      hideMobileHeader={view === 'session'}
      hideMobileNav={view === 'session'}
      hideMobileTitle={false}
    />
  );
}

function TodayView({
  today,
  activeSession,
  onContinue,
  onStart,
  dayProgress,
  recommendation,
  onRecommendedAction,
  onOpenReview,
  loading,
  loadError,
  onRetry,
}: {
  today: AtelierToday | null;
  activeSession: AtelierSessionStart | null;
  onContinue: () => void;
  onStart: () => void;
  dayProgress: DayProgress;
  recommendation: RecommendedAction;
  onRecommendedAction: (action?: RecommendedAction) => void;
  onOpenReview: () => void;
  loading: boolean;
  loadError: string | null;
  onRetry: () => void;
}) {
  const hasActiveSession = dayProgress.sessionStatus === 'active';
  const concepts = activeSession?.concepts?.length ? activeSession.concepts : today?.concepts || [];
  const dueErrata = dayProgress.errataDue || roadmapErrataCount(today, activeSession);
  const grammarTopics = concepts.slice(0, 3).map(displayConceptTitle);
  const canStart = hasActiveSession || concepts.length > 0;
  const recommendedTarget = recommendedRoadmapTarget(recommendation);
  const primaryAction = roadmapPrimaryAction(recommendation, loading, canStart, () => onRecommendedAction(recommendation));
  const reviewTotal = recommendation.kind === 'review'
    ? recommendation.errataDue + recommendation.vocabularyDue
    : dayProgress.errataDue + dayProgress.vocabularyDue;
  const reviewKindCount = [dayProgress.errataDue, dayProgress.vocabularyDue].filter((count) => count > 0).length;
  const serialAction = serialActionFromToday(today, activeSession);
  const serialEpisode = (today as any)?.serial_episode || (today as any)?.serial || null;
  const serialKind = serialAction?.episodeKind
    || (recommendation.kind === 'serial' ? recommendation.episodeKind : recommendedTarget === 'feuilleton' ? 'feuilleton' : 'mission');
  const serialHref = serialAction
    ? `/${serialAction.episodeKind === 'mission' ? 'missions' : 'graphic-novel'}${serialAction.query}`
    : recommendation.kind === 'serial'
      ? `/${recommendation.episodeKind === 'mission' ? 'missions' : 'graphic-novel'}${recommendation.query}`
    : serialKind === 'mission'
      ? '/atelier'
      : '/atelier';
  const serialDone = serialKind === 'mission' ? dayProgress.missionDone : dayProgress.feuilletonDone;
  const sessionComplete = dayProgress.sessionStatus === 'completed';
  const positionRound = activeSession?.current_position?.round;
  const activeRound = recommendation.kind === 'resume_session' && isRoundName(recommendation.round)
    ? recommendation.round
    : isRoundName(positionRound)
      ? positionRound
      : 'recognize';
  const activeRoundIndex = Math.max(0, roundLabels.findIndex((item) => item.id === activeRound));
  const editionDate = formatAtelierEditionDate();
  const streak = atelierEditionStreak(today, activeSession);
  const submittedCount = sessionSubmittedCount(activeSession);
  const completedSignatureCount = sessionComplete ? roundLabels.length : Math.min(activeRoundIndex, roundLabels.length);
  const signatureSub = hasActiveSession
    ? `${Math.max(completedSignatureCount, Math.min(submittedCount, roundLabels.length))} of ${roundLabels.length} signatures set`
    : `${grammarFocusCountLabel(concepts.length || grammarTopics.length)} · ${plannedAtelierDrills(concepts, activeSession)} drills`;
  const currentPanelLabel = hasActiveSession ? 'Resume · in progress' : 'Today · grammar';
  const currentPanelFoci = canStart
    ? hasActiveSession
      ? [currentRoundFocus(activeSession, activeRound, grammarTopics)]
      : grammarTopics.length
        ? grammarTopics
        : ['Session not ready']
    : ['Session not ready'];
  const nodes: RoadmapNode[] = [
    { id: 'grammar', label: currentPanelLabel, target: activeRound },
    { id: 'review', label: 'Review', target: 'review' },
    { id: 'living-thread', label: 'Living thread', target: serialKind, href: serialHref },
  ];

  if (loadError && !today && !hasActiveSession) {
    return (
      <main className="atelier-edition-stage">
        <AtelierRoadmapEmpty onRetry={onRetry} />
      </main>
    );
  }

  return (
    <main className="atelier-edition-stage">
      <section className={`ph ${recommendation.kind === 'rest' ? 'is-rest' : ''}`} aria-label="Atelier roadmap">
        <AtelierEditionHead title="Atelier" />
        <div className={`ph-body ${recommendation.kind === 'rest' ? 'center' : ''}`}>
          {loadError && <AtelierLoadNotice message={loadError} onRetry={onRetry} />}

          {recommendation.kind === 'rest' ? (
            <>
              <AtelierEditionHeader
                rubric="Edition closed"
                rubricMuted
                date={editionDate}
                sub={`Day ${streak} · unbroken`}
                streak={streak}
              />
              <AtelierEditionClosed
                reviewTotal={reviewTotal}
                datestamp={formatAtelierDatestamp()}
              />
            </>
          ) : (
            <>
              <AtelierEditionHeader
                rubric={hasActiveSession ? "Today's edition · in press" : "Today's edition"}
                date={editionDate}
                sub={signatureSub}
                streak={streak}
              />
              <div className="spine" data-node-count={nodes.length}>
                {roundLabels.map((item, index) => {
                  const state = sessionComplete
                    ? 'done'
                    : index < activeRoundIndex && dayProgress.sessionStatus !== 'none'
                      ? 'done'
                      : index === activeRoundIndex
                        ? 'current'
                        : 'up';
                  return (
                    <AtelierEditionStep
                      key={item.id}
                      roman={item.roman}
                      name={item.label}
                      meta={roundMetaLabel(state, dayProgress.sessionStatus)}
                      state={state}
                      first={index === 0}
                    >
                      {state === 'current' && (
                        <AtelierCurrentPanel
                          label={currentPanelLabel}
                          foci={currentPanelFoci}
                          errataCount={dueErrata}
                          cta={primaryAction}
                          disabled={loading || (recommendation.kind === 'start_session' && !canStart)}
                        />
                      )}
                    </AtelierEditionStep>
                  );
                })}
                <AtelierEditionStep
                  roman="R"
                  name="Review"
                  meta={reviewTotal > 0
                    ? `${reviewTotal} to review${recommendedTarget === 'review' && reviewKindCount > 1 ? ` · ${reviewKindCount} kinds` : ''}`
                    : 'Queue clear'}
                  state={recommendedTarget === 'review' ? 'current' : reviewTotal > 0 ? 'up' : 'done'}
                  review
                  badge={recommendedTarget !== 'review' && reviewTotal > 0 ? String(reviewTotal) : undefined}
                  metaGo={recommendedTarget === 'review'}
                  last
                >
                  {recommendedTarget === 'review' && (
                    <AtelierReviewOpen
                      errataDue={dayProgress.errataDue}
                      vocabularyDue={dayProgress.vocabularyDue}
                      onOpenReview={onOpenReview}
                    />
                  )}
                </AtelierEditionStep>
              </div>

              <div className="branch">
                <div className="branch-head"><span className="t">Living thread</span></div>
                <SerialThreadCard
                  kind={serialKind}
                  href={serialHref}
                  episodeLabel={serialEpisodeLabel(serialAction || recommendation)}
                  status={serialEpisode?.status}
                  hookText={serialEpisode?.hook?.teaser || serialEpisode?.hook?.text || serialEpisode?.previously}
                  invited={recommendation.kind !== 'serial' && !serialDone}
                  recommended={recommendedTarget === serialKind}
                  done={serialDone}
                />
              </div>
            </>
          )}
        </div>
        <AtelierEditionNav active="atelier" />
      </section>
    </main>
  );
}

function recommendedRoadmapTarget(action: RecommendedAction): RoadmapTarget {
  if (action.kind === 'start_session') return 'recognize';
  if (action.kind === 'resume_session') return isRoundName(action.round) ? action.round : 'recognize';
  if (action.kind === 'serial') return action.episodeKind;
  return action.kind;
}

function roadmapPrimaryAction(
  action: RecommendedAction,
  loading: boolean,
  canStart: boolean,
  onClick: () => void,
): RoadmapAction | null {
  if (action.kind === 'rest') return null;
  if (action.kind === 'start_session') {
    return { label: loading ? 'Starting' : canStart ? 'Begin session' : 'Retry setup', onClick };
  }
  if (action.kind === 'resume_session') {
    const roundLabel = isRoundName(action.round)
      ? roundLabels.find((item) => item.id === action.round)?.label
      : null;
    return { label: roundLabel ? `Continue · ${roundLabel}` : 'Continue session', onClick };
  }
  if (action.kind === 'review') {
    const total = action.errataDue + action.vocabularyDue;
    return { label: `Review ${total} item${total === 1 ? '' : 's'}`, onClick };
  }
  if (action.kind === 'mission') return { label: 'Use in mission', onClick };
  if (action.kind === 'serial') return { label: action.episodeKind === 'mission' ? 'Reply in story' : 'Continue story', onClick };
  return { label: 'Read Feuilleton', onClick };
}

function formatAtelierEditionDate(date = new Date()) {
  const formatted = new Intl.DateTimeFormat('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(date);
  return formatted.charAt(0).toUpperCase() + formatted.slice(1);
}

function formatAtelierDatestamp(date = new Date()) {
  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const year = String(date.getFullYear()).slice(-2);
  return `Closed · ${day} · ${month} · ${year}`;
}

function atelierEditionStreak(today: AtelierToday | null, activeSession: AtelierSessionStart | null) {
  const value = Number(
    today?.summary?.streak_days
      ?? today?.summary?.streak
      ?? activeSession?.recap?.streak_after
      ?? activeSession?.recap?.streak_before
      ?? 12,
  );
  return Number.isFinite(value) && value > 0 ? Math.round(value) : 12;
}

function grammarFocusCountLabel(count: number) {
  if (count <= 0) return 'No grammar foci';
  if (count === 1) return 'One grammar focus';
  const words: Record<number, string> = {
    2: 'Two',
    3: 'Three',
    4: 'Four',
    5: 'Five',
    6: 'Six',
  };
  return `${words[count] || String(count)} grammar foci`;
}

function plannedAtelierDrills(concepts: AtelierConcept[], activeSession: AtelierSessionStart | null) {
  const sessionTotal = totalDrills(activeSession);
  if (sessionTotal > 0) return sessionTotal;
  if (concepts.length > 0) return concepts.length * (recognizeModes.length + 4) + 1;
  return 0;
}

function currentRoundFocus(
  session: AtelierSessionStart | null,
  activeRound: RoundName,
  grammarTopics: string[],
) {
  const conceptIndex = Math.max(0, Math.min(session?.current_position?.concept_index || 0, Math.max(grammarTopics.length - 1, 0)));
  const topic = grammarTopics[conceptIndex] || grammarTopics[0] || 'Today’s grammar';
  return `${topic} — ${roundFocusInstruction(activeRound)}`;
}

function roundFocusInstruction(round: RoundName) {
  if (round === 'recognize') return 'recognize the pattern';
  if (round === 'transform') return 'rewrite with precision';
  if (round === 'sentence') return 'write one full sentence';
  if (round === 'produce') return 'shape a short paragraph';
  if (round === 'speak') return 'say it aloud';
  return 'use it in a reply';
}

function roundMetaLabel(state: 'done' | 'current' | 'up', sessionStatus: DayProgress['sessionStatus']) {
  if (state === 'done') return 'done';
  if (state === 'current') return sessionStatus === 'none' ? 'Start here' : 'Continue here';
  return 'up next';
}

type AtelierEditionStepState = 'done' | 'current' | 'up';

function AtelierEditionHead({ title }: { title: string }) {
  return (
    <header className="ph-head">
      <span className="mark"><AtelierEditionMark size={26} /></span>
      <span className="ttl">{title}</span>
      <Link className="gear" href="/settings" aria-label="Settings"><AtelierEditionGear /></Link>
    </header>
  );
}

function AtelierEditionHeader({
  rubric,
  rubricMuted,
  date,
  sub,
  streak,
}: {
  rubric: string;
  rubricMuted?: boolean;
  date: string;
  sub?: string;
  streak?: number;
}) {
  return (
    <div className="edition">
      <div>
        <div className={`rubric ${rubricMuted ? 'muted' : ''}`}>{rubric}</div>
        <h1>{date}</h1>
        {sub && <div className="sub">{sub}</div>}
      </div>
      {streak != null && (
        <div className="stamp">
          <div className="cap">DAY</div>
          <div className="n">{streak}</div>
          <div className="rules">
            {[0, 1, 2, 3, 4, 5].map((item) => <i key={item} className={item < 5 ? 'on' : ''} />)}
          </div>
        </div>
      )}
    </div>
  );
}

function AtelierEditionStep({
  roman,
  name,
  meta,
  state,
  first,
  last,
  review,
  badge,
  metaGo,
  children,
}: {
  roman: string;
  name: string;
  meta: string;
  state: AtelierEditionStepState;
  first?: boolean;
  last?: boolean;
  review?: boolean;
  badge?: string;
  metaGo?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <div className={`step ${state} ${first ? 'is-first' : ''} ${last ? 'is-last' : ''}`}>
      <span className={`plate ${state} ${review ? 'review' : ''} ${review && state !== 'up' && badge ? 'live' : ''}`}>
        {state === 'done' ? <AtelierEditionCheck /> : roman}
        {badge != null && <span className="badge">{badge}</span>}
      </span>
      <div className="node">
        <div className="name">{name}</div>
        <div className={`meta ${metaGo || state === 'current' ? 'go' : ''}`}>{meta}</div>
        {children}
      </div>
    </div>
  );
}

function AtelierCurrentPanel({
  label,
  foci,
  errataCount,
  cta,
  disabled,
}: {
  label: string;
  foci: string[];
  errataCount?: number;
  cta?: RoadmapAction | null;
  disabled?: boolean;
}) {
  return (
    <div className="current-panel">
      <div className="label">{label}</div>
      <div className="foci">
        {foci.slice(0, 3).map((focus) => <div className="f" key={focus}>{focus}</div>)}
        {errataCount && errataCount > 0 ? <div className="f errata">Errata · {errataCount} repair{errataCount === 1 ? '' : 's'}</div> : null}
      </div>
      {cta && (
        <button className="cta" onClick={cta.onClick} disabled={disabled}>
          {cta.label} <AtelierEditionArrow />
        </button>
      )}
    </div>
  );
}

function AtelierReviewOpen({
  errataDue,
  vocabularyDue,
  onOpenReview,
}: {
  errataDue: number;
  vocabularyDue: number;
  onOpenReview: () => void;
}) {
  const total = errataDue + vocabularyDue;
  const kindCount = [vocabularyDue, errataDue].filter((count) => count > 0).length;
  return (
    <div className="review-open-wrap">
      <div className="review-open">
        <div className="r">
          <span className="dot vocab" />
          <span className="lab"><b>Vocabulary cards</b><em>French 5000 · spaced</em></span>
          <span className="ct">{vocabularyDue}</span>
        </div>
        <div className="r">
          <span className="dot errata" />
          <span className="lab"><b>Grammar errata</b><em>Repairs from past slips</em></span>
          <span className="ct">{errataDue}</span>
        </div>
      </div>
      <button className="cta" onClick={onOpenReview}>
        Review {total} item{total === 1 ? '' : 's'} <AtelierEditionArrow />
      </button>
      {kindCount > 1 && <div className="review-kind-note">{kindCount} kinds</div>}
    </div>
  );
}

function AtelierQuest({
  kind,
  title,
  href,
  copy,
  recommended,
  done,
}: {
  kind: 'mission' | 'feuilleton';
  title: string;
  href: string;
  copy: string;
  recommended?: boolean;
  done?: boolean;
}) {
  const tag = done
    ? 'Thread beat done'
    : recommended
      ? '● Next beat'
      : "Thread beat · with today's French";
  return (
    <Link className={`quest ${recommended ? 'recommended' : ''} ${done ? 'done' : ''}`} href={href}>
      {kind === 'mission' ? (
        <svg className="shape triangle" viewBox="0 0 92 82" aria-hidden="true">
          <path d="M46 5L87 77H5L46 5Z" />
        </svg>
      ) : (
        <svg className="shape circle" viewBox="0 0 86 86" aria-hidden="true">
          <circle cx="43" cy="43" r="36" />
        </svg>
      )}
      <span>
        <span className="tag">{tag}</span>
        <h3>{title}</h3>
        <p>{copy}</p>
      </span>
    </Link>
  );
}

function SerialThreadCard({
  kind,
  href,
  episodeLabel,
  status,
  hookText,
  invited,
  recommended,
  done,
}: {
  kind: 'mission' | 'feuilleton';
  href: string;
  episodeLabel: string;
  status?: string;
  hookText?: string;
  invited: boolean;
  recommended?: boolean;
  done?: boolean;
}) {
  const variant = status === 'delayed' ? 'rest' : done ? 'rest' : invited ? 'invite' : kind === 'mission' ? 'act' : 'see';
  const who = done ? 'romy' : invited ? 'margaux' : kind === 'mission' ? 'marchand' : 'marin';
  const copy = serialThreadCopy({ kind, invited, done, episodeLabel, status, hookText });
  return (
    <Link className={`s-thread ${variant} ${recommended ? 'recommended' : ''}`} href={href} data-char={who}>
      <div className="ttop">
        <AtelierEditionMark size={18} />
        <span className="ser">The serial</span>
        <span className="ep">{copy.episode}</span>
      </div>
      {copy.previously && <div className="prev"><b>Previously —</b> {copy.previously}</div>}
      <div className="tmain" data-char={who}>
        <SerialAvatar who={who} mood={kind === 'mission' ? 'confused' : 'warm'} />
        <div>
          <div className="beat">{copy.beat}</div>
          <h2>{copy.title}</h2>
          <div className="sub">{copy.sub}</div>
        </div>
      </div>
      {!done && (
        <div className={`tcta ${kind === 'feuilleton' || invited ? 'ink' : ''}`}>
          {copy.cta} <SerialArrowIcon />
        </div>
      )}
    </Link>
  );
}

function serialEpisodeLabel(action: RecommendedAction) {
  if (action.kind !== 'serial') return 'Episode 1';
  const params = new URLSearchParams(action.query.replace(/^\?/, ''));
  const index = Number(params.get('episode_index'));
  if (!Number.isFinite(index)) return 'Episode';
  return `Episode ${index + 1}`;
}

function serialThreadCopy({
  kind,
  invited,
  done,
  episodeLabel,
  status,
  hookText,
}: {
  kind: 'mission' | 'feuilleton';
  invited: boolean;
  done?: boolean;
  episodeLabel: string;
  status?: string;
  hookText?: string;
}) {
  if (status === 'delayed') {
    return {
      episode: `${episodeLabel} · delayed`,
      previously: '',
      beat: "L'édition de demain est retardée",
      title: 'The presses are paused.',
      sub: 'The story writer is unavailable, so the serial waits instead of replaying the opener.',
      cta: 'Retry edition',
    };
  }
  if (status === 'generating') {
    return {
      episode: `${episodeLabel} · printing`,
      previously: '',
      beat: "Tomorrow's edition is at the printer's",
      title: 'The script is ready.',
      sub: 'Panels will appear as the image desk finishes them.',
      cta: 'Open edition',
    };
  }
  if (done) {
    return {
      episode: `${episodeLabel} · settled`,
      previously: 'you sent the story forward.',
      beat: '— Fin de l’épisode —',
      title: 'You’re caught up.',
      sub: 'The next installment is still being typeset. Let the cliffhanger sit overnight.',
      cta: '',
    };
  }
  if (invited) {
    return {
      episode: `${episodeLabel} · begins`,
      previously: '',
      beat: 'A new serial',
      title: '“L’arrivée”',
      sub: 'A café in the 11th, a key that will not turn, and people who will remember you. Your French moves the story.',
      cta: 'Begin episode 1',
    };
  }
  if (kind === 'mission') {
    return {
      episode: `${episodeLabel} · Act`,
      previously: 'the last panel left someone waiting for your answer.',
      beat: 'Le monde attend ta réponse',
      title: 'The world is waiting for your reply',
      sub: 'Write the next message and let the town answer in fiction.',
      cta: 'Reply in story',
    };
  }
  return {
    episode: `${episodeLabel} · See`,
    previously: hookText || 'the reply you wrote becomes the scene.',
    beat: 'New episode ready',
    title: 'Continue the story',
    sub: 'See what your last message changed, then leave on the next hook.',
    cta: 'Read episode',
  };
}

function SerialAvatar({ who, mood }: { who: string; mood?: 'warm' | 'confused' | 'cool' }) {
  const initials: Record<string, string> = {
    marin: 'M',
    lila: 'L',
    gus: 'G',
    romy: 'R',
    margaux: 'Mx',
    marchand: 'M·',
    toi: 'T',
  };
  return (
    <span className="s-ava lg" data-char={who} style={(initials[who] || 'T').length > 1 ? { fontSize: 19 } : undefined}>
      {initials[who] || 'T'}
      {mood && <span className={`mood-pip ${mood}`}><i /></span>}
    </span>
  );
}

function SerialArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square" aria-hidden="true">
      <path d="M4 12h15M13 6l6 6-6 6" />
    </svg>
  );
}

function AtelierEditionClosed({ reviewTotal, datestamp }: { reviewTotal: number; datestamp: string }) {
  return (
    <div className="closed">
      <div className="rubric">— Fin —</div>
      <div className="endmark" />
      <h2>Edition complete.</h2>
      <p className="lead">Session, review, mission and Feuilleton are all settled. You&apos;re done for today &mdash; let the spacing do its quiet work.</p>
      <div className="ledger">
        <div className="row"><span>Session · I–VI</span><b><AtelierEditionCheck />Printed</b></div>
        <div className="row"><span>{reviewTotal > 0 ? `Review · ${reviewTotal} items` : 'Review'}</span><b><AtelierEditionCheck />Cleared</b></div>
        <div className="row"><span>Mission</span><b><AtelierEditionCheck />Filed</b></div>
        <div className="row"><span>Feuilleton</span><b><AtelierEditionCheck />Read</b></div>
      </div>
      <Link className="free" href="/practice">Free practice, if you like <AtelierEditionArrow /></Link>
      <div className="datestamp">{datestamp}</div>
    </div>
  );
}

function AtelierEditionNav({
  active = 'atelier',
  variant = 'two',
}: {
  active?: 'atelier' | 'notebook';
  variant?: 'two' | 'three';
}) {
  if (variant === 'three') {
    return (
      <nav className="ph-nav three" aria-label="Primary">
        <Link className={active === 'atelier' ? 'active' : ''} href="/atelier">
          <AtelierEditionMarkTab /><span>Today</span>
        </Link>
        <Link className="center-act" href="/practice">
          <AtelierEditionPenNib /><span className="lbl">Practise</span>
        </Link>
        <Link className={active === 'notebook' ? 'active' : ''} href="/notebook">
          <AtelierEditionBookTab /><span>Notebook</span>
        </Link>
      </nav>
    );
  }

  return (
    <nav className="ph-nav" aria-label="Primary">
      <Link className={active === 'atelier' ? 'active' : ''} href="/atelier">
        <AtelierEditionMarkTab /><span>Today</span>
      </Link>
      <Link className={active === 'notebook' ? 'active' : ''} href="/notebook">
        <AtelierEditionBookTab /><span>Notebook</span>
      </Link>
    </nav>
  );
}

function AtelierEditionPenNib() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square" aria-hidden="true">
      <path d="M5 19l3-9 9-5-5 9-7 5z" />
      <path d="M8 16l4-4" />
      <circle cx="13" cy="11" r="1.4" fill="currentColor" stroke="none" />
    </svg>
  );
}

function AtelierEditionMark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden="true">
      <rect x="0" y="0" width="11" height="11" fill="var(--ink)" />
      <circle cx="22" cy="6" r="6" fill="var(--blue)" />
      <rect x="0" y="17" width="11" height="11" fill="var(--yellow)" />
      <path d="M17 28L23 16L28 28H17Z" fill="var(--red)" />
    </svg>
  );
}

function AtelierEditionGear() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.2 5.2l2.1 2.1M16.7 16.7l2.1 2.1M18.8 5.2l-2.1 2.1M7.3 16.7l-2.1 2.1" />
    </svg>
  );
}

function AtelierEditionArrow() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square" aria-hidden="true">
      <path d="M4 12h15M13 6l6 6-6 6" />
    </svg>
  );
}

function AtelierEditionCheck() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="square" aria-hidden="true">
      <path d="M4 12.5l5 5 11-12" />
    </svg>
  );
}

function AtelierEditionMarkTab() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <rect x="0" y="0" width="8" height="8" fill="currentColor" />
      <path d="M20 0 A 12 12 0 0 0 8 12 L 20 12 Z" fill="currentColor" />
      <rect x="0" y="12" width="8" height="8" fill="currentColor" />
    </svg>
  );
}

function AtelierEditionBookTab() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <rect x="3" y="2" width="13" height="16" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3 4h13M3 6h13" stroke="currentColor" strokeWidth="1" />
      <path d="M11 2v8l-2-2-2 2V2" fill="currentColor" />
    </svg>
  );
}

function displayConceptTitle(concept: AtelierConcept) {
  return String(concept.atelier_blueprint?.display_title || concept.name || 'Grammar focus');
}

function roadmapErrataCount(today: AtelierToday | null, activeSession: AtelierSessionStart | null) {
  const sessionCount = activeSession?.due_errata?.length || 0;
  const summaryCount = Number(today?.summary?.due_errata ?? today?.due_errata?.length ?? 0);
  return Math.max(sessionCount, Number.isFinite(summaryCount) ? summaryCount : 0);
}

function firstDueErratum(today: AtelierToday | null, activeSession: AtelierSessionStart | null) {
  return activeSession?.due_errata?.find((item) => item.id)
    || today?.due_errata?.find((item) => item.id)
    || today?.concepts?.flatMap((concept) => concept.due_errata || []).find((item) => item.id)
    || null;
}

function AtelierRoadmapEmpty({ onRetry }: { onRetry: () => void }) {
  return (
    <section className="ph" aria-label="Atelier roadmap">
      <AtelierEditionHead title="Atelier" />
      <div className="ph-body">
        <AtelierEditionHeader
          rubric="Today's edition"
          date={formatAtelierEditionDate()}
          sub="Session not ready"
          streak={atelierEditionStreak(null, null)}
        />
        <div className="spine">
          <AtelierEditionStep roman="I" name="Recognize" meta="Start here" state="current" first last>
            <AtelierCurrentPanel
              label="Today · grammar"
              foci={['Session not ready']}
              cta={{ label: 'Retry setup', onClick: onRetry }}
            />
          </AtelierEditionStep>
        </div>
      </div>
      <AtelierEditionNav active="atelier" />
    </section>
  );
}

function sessionSubmittedCount(session: AtelierSessionStart | null) {
  if (!session) return 0;
  return Object.values(session.submitted_map || {}).filter(Boolean).length;
}

function activeSessionLabel(session: AtelierSessionStart) {
  const position = session.current_position || {};
  const roundId = position.round && position.round !== 'complete' ? position.round : 'produce';
  const roundLabel = roundLabels.find((item) => item.id === roundId)?.label || 'Writing';
  const conceptIndex = typeof position.concept_index === 'number'
    ? position.concept_index
    : Math.max(0, session.concepts.findIndex((concept) => concept.id === position.concept_id));
  const concept = session.concepts[Math.max(0, Math.min(conceptIndex, session.concepts.length - 1))];
  return `${roundLabel}${concept ? ` · ${concept.atelier_blueprint?.display_title || concept.name}` : ''}`;
}

function vocabularyTranslation(item: VocabularyRecommendationItem) {
  return item.translation || item.translations?.de || item.translations?.en || item.translations?.fr || 'target word';
}

function AtelierLoadNotice({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <section className="atelier-load-notice">
      <div>
        <span className="t-mono red">OFFLINE</span>
        <p>{message}</p>
      </div>
      <button className="btn solid" onClick={onRetry}>Retry</button>
    </section>
  );
}

function AtelierContinueCard({
  session,
  completed,
  total,
  onContinue,
}: {
  session: AtelierSessionStart;
  completed: number;
  total: number;
  onContinue: () => void;
}) {
  const progress = total ? Math.min(100, Math.round((completed / total) * 100)) : 0;
  return (
    <section className="paper-frame continue-card">
      <CropMarks />
      <div>
        <div className="t-mono red">IN PROGRESS</div>
        <h2>Continue today</h2>
        <p>{activeSessionLabel(session)}</p>
        <div className="session-progress-bar" aria-label={`${completed} of ${total} drills complete`}>
          <span style={{ width: `${progress}%` }} />
        </div>
        <div className="continue-meta">
          <span>{completed}/{total || '–'} submitted</span>
          <span>{session.target_vocabulary?.length || 0} words inside session</span>
        </div>
      </div>
      <button className="btn red lg" onClick={onContinue}>
        Continue <ArrowRight size={15} />
      </button>
      {Boolean(session.target_vocabulary?.length) && (
        <VocabularyFocus words={session.target_vocabulary} compact className="continue-vocab" />
      )}
    </section>
  );
}

function VocabularyFocus({
  words,
  compact = false,
  className = '',
}: {
  words?: VocabularyRecommendationItem[];
  compact?: boolean;
  className?: string;
}) {
  const items = (words || []).slice(0, compact ? 3 : 5);
  if (!items.length) return null;
  return (
    <section className={`vocab-focus ${compact ? 'compact' : ''} ${className}`}>
      <header>
        <span className="t-mono">TODAY&apos;S WORDS</span>
      </header>
      <div className="vocab-focus-list">
        {items.map((item) => (
          <span key={`${item.word_id}-${item.bucket}`}>
            <strong>{item.word}</strong>
            <em>{vocabularyTranslation(item)}</em>
          </span>
        ))}
      </div>
    </section>
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
  const query = conceptQueryString(concepts);
  const conceptIds = concepts.map((concept) => `concept_id=${concept.id}`).join('&');
  return (
    <section className="paper-2 mission-bridge" data-context-query={query}>
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

function conceptQueryString(concepts: AtelierConcept[]) {
  const conceptIds = concepts.map((concept) => `concept_id=${concept.id}`).join('&');
  return conceptIds ? `?${conceptIds}` : '';
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
  requestAiReview,
  aiReviewSubmitting,
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
  requestAiReview: () => void;
  aiReviewSubmitting: boolean;
  completedDrills: number;
  onBack: () => void;
  produceAnswer: string;
}) {
  const currentMode = roundMode(round, mode);
  const currentKey = answerKey(round, currentMode, roundUsesSessionScope(round) ? null : activeConcept?.id);
  const currentCorrection = correctionsByKey[currentKey] || null;
  const currentSubmitted = !!submitted[currentKey];
  const total = totalDrills(session);
  const progress = total ? Math.min(100, Math.round((completedDrills / total) * 100)) : 0;
  const activeRoundLabel = roundLabels.find((item) => item.id === round)?.label || 'Practice';
  const activeRecognizeLabel = recognizeModes.find((item) => item.id === mode)?.label || 'Recognize';
  const activeConceptTitle = activeConcept?.atelier_blueprint?.display_title || activeConcept?.name || 'Daily session';

  return (
    <main className="spread session-spread">
      <section className="mobile-session-topbar">
        <button className="mobile-back-button" onClick={onBack}>Back</button>
        <div>
          <span className="t-mono-low">ATELIER</span>
          <strong>{completedDrills}/{total || '–'}</strong>
        </div>
        <button className="mobile-quiet-button" onClick={completeSession} disabled={submitting || completedDrills < total}>Finish</button>
      </section>
      <section className="mobile-session-brief">
        <div className="session-progress-bar" aria-label={`${completedDrills} of ${total} drills complete`}>
          <span style={{ width: `${progress}%` }} />
        </div>
        <div className="mobile-session-heading">
          <span className="t-mono red">{activeRoundLabel}</span>
          <h1>{activeConceptTitle}</h1>
          {round === 'recognize' && <p>{activeRecognizeLabel}</p>}
        </div>
        <VocabularyFocus words={session.target_vocabulary} compact className="mobile-vocab-focus" />
        {activeSet && activeConcept && (
          <details className="mobile-context-details">
            <summary>Rule card</summary>
            <ConceptRulePanel payload={activeSet} concept={activeConcept} />
          </details>
        )}
      </section>
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

          <VocabularyFocus words={session.target_vocabulary} className="desktop-vocab-focus" />

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
                    onRequestAiReview={requestAiReview}
                    aiReviewSubmitting={aiReviewSubmitting}
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
                    onRequestAiReview={requestAiReview}
                    aiReviewSubmitting={aiReviewSubmitting}
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
                    targetVocabulary={session.target_vocabulary}
                    answer={produceAnswer}
                    updateAnswer={(value) => updateAnswer('text', value, 'produce', 'produce', null)}
                    correction={currentCorrection}
                    submitted={currentSubmitted}
                    onRequestAiReview={requestAiReview}
                    aiReviewSubmitting={aiReviewSubmitting}
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
              <TutorNote
                concept={activeConcept}
                correction={currentCorrection || recentCorrection}
                round={round}
                onRequestAiReview={requestAiReview}
                aiReviewSubmitting={aiReviewSubmitting}
              />
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
  const sentence = String(xray?.sentence || '').trim();
  const marks = xray?.marks || [];
  if (!sentence) {
    return (
      <div className="sentence-xray missing-panel">
        <p>Session content unavailable.</p>
      </div>
    );
  }
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
        const wordBankTokens = mode === 'word_bank' ? wordBankTokensFromAnswer(answers[item.id]) : [];
        const sourceTokens = Array.isArray(item.tokens) ? item.tokens.map((token: string) => String(token)) : [];
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
                  {sourceTokens.map((token: string, tokenIndex: number) => {
                    const used = wordBankTokenIsUsed(wordBankTokens, sourceTokens, token, tokenIndex);
                    return (
                      <button
                        key={`${token}-${tokenIndex}`}
                        type="button"
                        className={used ? 'used' : ''}
                        disabled={submitted || used}
                        onClick={() => updateAnswer(item.id, [...wordBankTokens, token])}
                      >
                        {token}
                      </button>
                    );
                  })}
                </div>
                <div className="word-bank-builder">
                  <input
                    value={Array.isArray(answers[item.id]) ? joinWordBankTokens(answers[item.id]) : answers[item.id] || ''}
                    onChange={(event) => updateAnswer(item.id, event.target.value)}
                    placeholder="Built sentence"
                  />
                  {wordBankTokens.length > 0 && (
                    <div className="word-bank-answer">
                      {wordBankTokens.map((token, selectedIndex) => (
                        <button
                          key={`${token}-${selectedIndex}`}
                          type="button"
                          disabled={submitted}
                          onClick={() => updateAnswer(item.id, wordBankTokens.filter((_, index) => index !== selectedIndex))}
                        >
                          {token}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
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
  onRequestAiReview,
  aiReviewSubmitting,
}: {
  payload: Record<string, any>;
  answers: Record<string, any>;
  updateAnswer: (key: string, value: any) => void;
  correction: Record<string, any> | null;
  submitted: boolean;
  onRequestAiReview: () => void;
  aiReviewSubmitting: boolean;
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
      {submitted && (
        <CorrectionAiReview
          correction={correction}
          onRequestAiReview={onRequestAiReview}
          submitting={aiReviewSubmitting}
        />
      )}
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

function CorrectionAiReview({
  correction,
  onRequestAiReview,
  submitting,
}: {
  correction: Record<string, any> | null;
  onRequestAiReview: () => void;
  submitting: boolean;
}) {
  const status = aiReviewStatus(correction);
  if (!status || status === 'not_applicable') return null;
  if (status === 'available') {
    return (
      <div className="ai-review-line">
        <button type="button" className="ai-review-button" disabled={submitting} onClick={onRequestAiReview}>
          {submitting ? 'Starting AI' : 'AI correction'}
        </button>
      </div>
    );
  }
  const label = status === 'pending'
    ? 'AI reviewing'
    : status === 'complete'
      ? 'AI correction ready'
      : 'AI unavailable';
  return <div className={`ai-review-line ${status}`}>{label}</div>;
}

function OutputLadderPanel({
  payload,
  round,
  answer,
  updateAnswer,
  correction,
  submitted,
  onRequestAiReview,
  aiReviewSubmitting,
}: {
  payload: Record<string, any>;
  round: 'sentence' | 'speak' | 'conversation';
  answer: string;
  updateAnswer: (value: string) => void;
  correction: Record<string, any> | null;
  submitted: boolean;
  onRequestAiReview: () => void;
  aiReviewSubmitting: boolean;
}) {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const item = payload.output_ladder?.[round]?.items?.[0] || {};
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
      <div className="live-block">
        <p className="exercise-prompt">{item.prompt}</p>
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
        {wordRangeLabel(wordCount(answer), item.min_words, item.max_words)}
      </div>
      {submitted && <InlineFeedback feedback={feedback} />}
      {submitted && (
        <CorrectionAiReview
          correction={correction}
          onRequestAiReview={onRequestAiReview}
          submitting={aiReviewSubmitting}
        />
      )}
    </div>
  );
}

function ProducePanel({
  concepts,
  exerciseSets,
  payload,
  targetVocabulary,
  answer,
  updateAnswer,
  correction,
  submitted,
  onRequestAiReview,
  aiReviewSubmitting,
}: {
  concepts: AtelierConcept[];
  exerciseSets: AtelierExerciseSet[];
  payload: Record<string, any>;
  targetVocabulary?: VocabularyRecommendationItem[];
  answer: string;
  updateAnswer: (value: string) => void;
  correction: Record<string, any> | null;
  submitted: boolean;
  onRequestAiReview: () => void;
  aiReviewSubmitting: boolean;
}) {
  const requirements = concepts.map((concept) => conceptRequirement(concept, exerciseSets));
  const produce = payload.produce || {};
  const sourceFragment = String(produce.source_fragment || '').trim();
  return (
    <div className="produce-panel">
      <div className="live-block">
        <div className="t-mono yellow">WRITING TASK</div>
        {sourceFragment ? <p className="fr">« {sourceFragment} »</p> : <p>Writing prompt unavailable.</p>}
      </div>
      <div className="target-chips">
        {requirements.map((req) => <span key={req.label}>{req.count} × {req.label}</span>)}
      </div>
      {Boolean(targetVocabulary?.length) && (
        <div className="target-word-strip" aria-label="Vocabulary targets for this paragraph">
          {(targetVocabulary || []).slice(0, 5).map((item) => (
            <span key={`${item.word_id}-${item.word}`}>
              {item.word}
              <em>{vocabularyTranslation(item)}</em>
            </span>
          ))}
        </div>
      )}
      <textarea value={answer} onChange={(event) => updateAnswer(event.target.value)} placeholder="Write your paragraph here. The targets guide the review; they do not lock submission." />
      <div className="word-count">{wordRangeLabel(wordCount(answer), produce.min_words, produce.max_words)}</div>
      {submitted && (
        <CorrectionAiReview
          correction={correction}
          onRequestAiReview={onRequestAiReview}
          submitting={aiReviewSubmitting}
        />
      )}
    </div>
  );
}

function TutorNote({
  concept,
  correction,
  round,
  onRequestAiReview,
  aiReviewSubmitting,
}: {
  concept: AtelierConcept | null;
  correction: Record<string, any> | null;
  round: RoundName;
  onRequestAiReview: () => void;
  aiReviewSubmitting: boolean;
}) {
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
          <CorrectionAiReview correction={correction} onRequestAiReview={onRequestAiReview} submitting={aiReviewSubmitting} />
        </>
      ) : (
        <>
          <h3>{concept?.name}</h3>
          {concept?.core_rule && <p>{concept.core_rule}</p>}
          <CorrectionAiReview correction={correction} onRequestAiReview={onRequestAiReview} submitting={aiReviewSubmitting} />
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

function RecapModal({
  recap,
  concepts,
  recommendation,
  onRecommendedAction,
  onClose,
}: {
  recap: Record<string, any>;
  concepts: AtelierConcept[];
  recommendation: RecommendedAction;
  onRecommendedAction: () => void;
  onClose: () => void;
}) {
  const reviewTotal = recommendation.kind === 'review' ? recommendation.errataDue + recommendation.vocabularyDue : 0;
  const nextLabel = recapActionLabel(recommendation, reviewTotal);
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
        {nextLabel && (
          <section className="recap-next">
            <div>
              <span className="t-mono red">NEXT ON TODAY&apos;S PATH</span>
              <h3>{nextLabel.title}</h3>
              <p>{nextLabel.copy}</p>
            </div>
            <button className="btn red lg" onClick={onRecommendedAction}>
              {nextLabel.action} <ArrowRight size={14} />
            </button>
          </section>
        )}
        <footer>
          <span className="t-mono-low">Atelier · Today&apos;s Set</span>
          <div className="recap-actions">
            {recap.session_id && (
              <Link className="btn red" href={`/missions?atelier_session_id=${recap.session_id}`}>
                USE IN MISSION
              </Link>
            )}
            <button className="btn solid" onClick={onClose}>RETURN TO TODAY</button>
          </div>
        </footer>
      </section>
    </div>
  );
}

function recapActionLabel(action: RecommendedAction, reviewTotal: number) {
  if (action.kind === 'review') {
    return {
      title: `${reviewTotal} review item${reviewTotal === 1 ? '' : 's'} waiting`,
      copy: 'Clear the repair queue before the optional branches so today’s grammar stays fresh.',
      action: 'Review now',
    };
  }
  if (action.kind === 'mission') {
    return {
      title: 'Use it in a Mission',
      copy: 'The loud on-ramp is here: take the completed session into a real-world prompt.',
      action: 'Open mission',
    };
  }
  if (action.kind === 'serial') {
    return {
      title: action.episodeKind === 'mission' ? 'The world is waiting for your reply' : 'Continue the story',
      copy: action.episodeKind === 'mission'
        ? 'Your next French message moves the shared thread forward.'
        : 'See the consequence of what you wrote, then catch the next hook.',
      action: action.episodeKind === 'mission' ? 'Reply now' : 'Open story',
    };
  }
  if (action.kind === 'feuilleton') {
    return {
      title: 'Read the Feuilleton branch',
      copy: 'Carry the same grammar into the story scene while it is still warm.',
      action: 'Open Feuilleton',
    };
  }
  if (action.kind === 'rest') {
    return {
      title: 'Done for today',
      copy: 'Everything on the path is complete. Return to the road map and rest.',
      action: 'Back to today',
    };
  }
  return null;
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
        --paper: var(--app-paper);
        --paper-2: var(--app-paper-2);
        --paper-3: var(--app-paper-3);
        --paper-deep: #1a1814;
        --ink: var(--app-ink);
        --ink-2: var(--app-ink-2);
        --ink-3: var(--app-ink-3);
        --red: var(--app-red);
        --blue: var(--app-blue);
        --yellow: var(--app-yellow);
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
      .atelier-mobile-streak {
        display: inline-flex;
        min-width: 42px;
        min-height: 30px;
        align-items: center;
        justify-content: center;
        border: 1px solid var(--ink);
        background: var(--paper);
        font-family: var(--mono);
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .08em;
        text-transform: uppercase;
      }
      .atelier-load-notice {
        margin: 18px 0 20px;
        border: 1px solid var(--ink);
        background: var(--paper-2);
        padding: 14px 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
      }
      .atelier-load-notice p {
        margin: 5px 0 0;
        color: var(--ink-2);
        line-height: 1.4;
      }
      .atelier-edition-stage {
        min-height: 100svh;
        display: grid;
        justify-items: center;
        align-items: start;
        background: #f1ece1;
      }
      .ph {
        --paper: #f1ece1;
        --paper-2: #e8e0cf;
        --paper-3: #d8cdb6;
        --sheet: #f8f3e8;
        --ink: #14110d;
        --ink-2: #4a4538;
        --ink-3: #8a826f;
        --blue: #1d3a8a;
        --red: #d8321a;
        --yellow: #f3c318;
        --serif: "EB Garamond", Garamond, "Times New Roman", serif;
        --grotesk: "Inter", "Helvetica Neue", Arial, sans-serif;
        position: relative;
        width: min(100vw, 380px);
        min-height: 100svh;
        background: var(--paper);
        color: var(--ink);
        font-family: var(--grotesk);
        -webkit-font-smoothing: antialiased;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }
      .ph * { box-sizing: border-box; }
      .ph-head {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 54px;
        padding: 8px 16px 10px;
        border-bottom: 1px solid var(--ink);
        background: var(--paper);
        flex: 0 0 auto;
      }
      .ph-head .mark {
        position: absolute;
        left: 16px;
        top: 50%;
        transform: translateY(-50%);
      }
      .ph-head .ttl {
        font-family: var(--serif);
        font-style: italic;
        font-weight: 500;
        font-size: 23px;
        line-height: 1;
        letter-spacing: 0;
      }
      .ph-head .gear {
        position: absolute;
        right: 16px;
        top: 50%;
        transform: translateY(-50%);
        width: 36px;
        height: 36px;
        border: 1px solid var(--ink);
        background: var(--sheet);
        color: var(--ink);
        display: grid;
        place-items: center;
        text-decoration: none;
      }
      .ph-head .gear svg {
        width: 18px;
        height: 18px;
      }
      .ph-body {
        flex: 1 1 auto;
        padding: 16px 22px 22px;
      }
      .ph-body.center {
        display: flex;
        flex-direction: column;
      }
      .ph-nav {
        flex: 0 0 auto;
        display: grid;
        grid-template-columns: 1fr 1fr;
        min-height: 62px;
        border-top: 1px solid var(--ink);
        background: var(--paper);
      }
      .ph-nav a {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 5px;
        text-decoration: none;
        color: var(--ink-3);
        font-size: 10px;
        font-weight: 800;
        letter-spacing: .14em;
        text-transform: uppercase;
        border-top: 2px solid transparent;
        margin-top: -1px;
      }
      .ph-nav a svg {
        width: 22px;
        height: 22px;
      }
      .ph-nav a.active {
        color: var(--ink);
        background: var(--sheet);
        border-top-color: var(--ink);
      }
      .ph-nav.three {
        grid-template-columns: 1fr auto 1fr;
        min-height: 64px;
        align-items: stretch;
      }
      .ph-nav .center-act {
        align-self: center;
        margin: 0 6px;
        transform: translateY(-14px);
        width: 70px;
        height: 70px;
        background: var(--red);
        color: #fff;
        border: 1.5px solid var(--ink);
        box-shadow: 4px 4px 0 var(--ink);
        display: grid;
        place-items: center;
        gap: 0;
        text-decoration: none;
      }
      .ph-nav .center-act .lbl {
        font-size: 8.5px;
        font-weight: 900;
        letter-spacing: .12em;
        margin-top: 2px;
      }
      .ph-nav .center-act svg {
        width: 22px;
        height: 22px;
      }
      .edition {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 16px;
        padding-bottom: 13px;
        border-bottom: 1px solid var(--ink);
      }
      .edition .rubric {
        font-size: 9.5px;
        font-weight: 900;
        letter-spacing: .16em;
        text-transform: uppercase;
        color: var(--red);
      }
      .edition .rubric.muted {
        color: var(--ink-3);
      }
      .edition h1 {
        margin: 4px 0 0;
        font-family: var(--serif);
        font-style: italic;
        font-weight: 600;
        font-size: 30px;
        line-height: .92;
        letter-spacing: 0;
        color: var(--ink);
      }
      .edition .sub {
        margin-top: 5px;
        font-size: 11px;
        color: var(--ink-3);
        font-weight: 500;
      }
      .stamp {
        flex: 0 0 auto;
        border: 1px solid var(--ink);
        background: var(--sheet);
        padding: 7px 9px 6px;
        text-align: center;
      }
      .stamp .cap {
        font-size: 8px;
        font-weight: 900;
        letter-spacing: .14em;
        color: var(--ink-3);
      }
      .stamp .n {
        font-family: var(--serif);
        font-style: italic;
        font-weight: 700;
        font-size: 24px;
        line-height: .85;
        margin: 1px 0 4px;
      }
      .stamp .rules {
        display: flex;
        gap: 2px;
        justify-content: center;
      }
      .stamp .rules i {
        width: 2px;
        height: 11px;
        background: var(--paper-3);
      }
      .stamp .rules i.on {
        background: var(--ink);
      }
      .spine {
        position: relative;
        margin-top: 18px;
      }
      .step {
        position: relative;
        display: grid;
        grid-template-columns: 52px minmax(0, 1fr);
        column-gap: 16px;
        align-items: start;
        min-height: 66px;
        padding-bottom: 4px;
      }
      .step::before {
        content: "";
        position: absolute;
        left: 25px;
        top: 0;
        bottom: 0;
        border-left: 2px solid var(--ink);
        z-index: 0;
      }
      .step.up::before {
        border-left: 1.5px dashed var(--ink-3);
      }
      .step.is-first::before {
        top: 26px;
      }
      .step.is-last::before {
        bottom: calc(100% - 26px);
      }
      .plate {
        position: relative;
        z-index: 1;
        width: 52px;
        height: 52px;
        border: 1.5px solid var(--ink);
        background: var(--paper);
        display: grid;
        place-items: center;
        font-family: var(--grotesk);
        font-weight: 900;
        font-size: 14px;
        letter-spacing: .04em;
        color: var(--ink);
      }
      .plate.done {
        background: var(--ink);
        color: var(--paper);
      }
      .plate.up {
        border-color: var(--ink-3);
        color: var(--ink-3);
        background: var(--paper);
      }
      .plate.current {
        background: var(--yellow);
        color: var(--ink);
        box-shadow: 6px 6px 0 var(--red);
      }
      .plate.review.live {
        background: var(--red);
        color: #fff;
      }
      .plate svg {
        width: 20px;
        height: 20px;
      }
      .plate .badge {
        position: absolute;
        top: -8px;
        right: -8px;
        min-width: 22px;
        height: 22px;
        padding: 0 5px;
        background: var(--red);
        color: #fff;
        border: 1.5px solid var(--ink);
        display: grid;
        place-items: center;
        font-size: 11px;
        font-weight: 900;
        z-index: 2;
      }
      .node {
        padding-top: 5px;
        min-width: 0;
      }
      .node .name {
        font-size: 16px;
        font-weight: 800;
        line-height: 1.04;
        letter-spacing: -.01em;
        color: var(--ink);
      }
      .step.done .node .name {
        color: var(--ink-2);
      }
      .step.up .node .name {
        color: var(--ink-3);
        font-weight: 700;
      }
      .node .meta {
        margin-top: 4px;
        font-size: 9.5px;
        font-weight: 900;
        letter-spacing: .14em;
        text-transform: uppercase;
        color: var(--ink-3);
      }
      .node .meta.go {
        color: var(--red);
      }
      .current-panel {
        margin-top: 12px;
      }
      .current-panel .label {
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .16em;
        text-transform: uppercase;
        color: var(--ink-3);
      }
      .foci {
        margin: 7px 0 14px;
        display: grid;
        gap: 4px;
      }
      .foci .f {
        font-family: var(--serif);
        font-style: italic;
        font-size: 17px;
        line-height: 1.12;
        color: var(--ink);
        padding-left: 11px;
        border-left: 2px solid var(--blue);
      }
      .foci .f.errata {
        color: var(--ink-2);
        border-left-color: var(--red);
      }
      .ph .cta {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
        width: 100%;
        min-height: 58px;
        padding: 0 20px;
        background: var(--red);
        color: #fff;
        border: 1.5px solid var(--ink);
        box-shadow: 6px 6px 0 var(--ink);
        text-decoration: none;
        font-size: 14px;
        font-weight: 900;
        letter-spacing: .14em;
        text-transform: uppercase;
      }
      .ph .cta svg {
        width: 18px;
        height: 18px;
      }
      .ph .cta:disabled {
        opacity: .55;
        cursor: wait;
      }
      .review-open-wrap {
        margin-top: 12px;
        display: grid;
        gap: 12px;
      }
      .review-open {
        border: 1px solid var(--ink);
        background: var(--sheet);
      }
      .review-open .r {
        display: grid;
        grid-template-columns: 18px 1fr auto;
        align-items: center;
        gap: 12px;
        padding: 13px 15px;
        border-bottom: 1px solid var(--paper-3);
      }
      .review-open .r:last-child {
        border-bottom: 0;
      }
      .review-open .r .dot {
        width: 12px;
        height: 12px;
      }
      .review-open .r .dot.vocab {
        background: var(--blue);
      }
      .review-open .r .dot.errata {
        width: 0;
        height: 0;
        background: none;
        border-style: solid;
        border-width: 0 7px 12px 7px;
        border-color: transparent transparent var(--red) transparent;
      }
      .review-open .r .lab {
        min-width: 0;
      }
      .review-open .r .lab b {
        display: block;
        font-size: 13px;
        font-weight: 800;
      }
      .review-open .r .lab em {
        display: block;
        margin-top: 1px;
        font-style: normal;
        font-size: 10px;
        font-weight: 800;
        letter-spacing: .1em;
        text-transform: uppercase;
        color: var(--ink-3);
      }
      .review-open .r .ct {
        font-family: var(--serif);
        font-style: italic;
        font-weight: 700;
        font-size: 22px;
      }
      .review-kind-note {
        justify-self: end;
        margin-top: -4px;
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .15em;
        text-transform: uppercase;
        color: var(--ink-3);
      }
      .branch {
        position: relative;
        margin-top: 4px;
        padding-top: 18px;
      }
      .branch::before {
        content: "";
        position: absolute;
        left: 25px;
        top: 0;
        height: 26px;
        border-left: 2px solid var(--ink);
      }
      .branch::after {
        content: "";
        position: absolute;
        left: 25px;
        top: 26px;
        width: 22px;
        border-top: 2px solid var(--ink);
      }
      .branch-head {
        margin: 0 0 12px 0;
        padding-left: 60px;
      }
      .branch-head .t {
        font-size: 9.5px;
        font-weight: 900;
        letter-spacing: .16em;
        text-transform: uppercase;
        color: var(--ink-3);
      }
      .quest {
        position: relative;
        display: grid;
        grid-template-columns: 56px minmax(0, 1fr);
        column-gap: 15px;
        align-items: center;
        border: 1px solid var(--ink);
        background: var(--sheet);
        padding: 14px 16px;
        margin-bottom: 13px;
        text-decoration: none;
        color: var(--ink);
      }
      .quest.recommended {
        background: var(--paper);
        box-shadow: 5px 5px 0 var(--ink);
      }
      .quest.recommended::after {
        content: "";
        position: absolute;
        top: -1px;
        right: -1px;
        border-width: 0 18px 18px 0;
        border-style: solid;
        border-color: transparent var(--red) transparent transparent;
      }
      .quest .shape {
        width: 50px;
        height: 50px;
        overflow: visible;
      }
      .quest .shape path,
      .quest .shape circle {
        stroke: var(--ink);
        stroke-width: 3;
      }
      .quest .shape.triangle path {
        fill: var(--red);
      }
      .quest .shape.circle circle {
        fill: var(--blue);
      }
      .quest .tag {
        font-size: 8.5px;
        font-weight: 900;
        letter-spacing: .15em;
        text-transform: uppercase;
        color: var(--ink-3);
      }
      .quest.recommended .tag {
        color: var(--red);
      }
      .quest.done .tag {
        color: var(--ink-3);
      }
      .quest h3 {
        margin: 2px 0 4px;
        font-family: var(--serif);
        font-style: italic;
        font-weight: 600;
        font-size: 21px;
        line-height: 1;
      }
      .quest p {
        margin: 0;
        font-size: 11.5px;
        line-height: 1.32;
        color: var(--ink-2);
      }
      .closed {
        display: block;
        text-align: center;
        padding: 46px 8px 30px;
      }
      .closed .rubric {
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .18em;
        text-transform: uppercase;
        color: var(--ink-3);
      }
      .closed .endmark {
        width: 16px;
        height: 16px;
        background: var(--ink);
        margin: 18px auto 16px;
      }
      .closed h2 {
        margin: 0 auto;
        max-width: 280px;
        font-family: var(--serif);
        font-style: italic;
        font-weight: 600;
        font-size: 37px;
        line-height: 1.02;
        color: var(--ink);
      }
      .closed .lead {
        margin: 18px auto 0;
        max-width: 248px;
        font-size: 12.5px;
        line-height: 1.5;
        color: var(--ink-2);
      }
      .closed .ledger {
        margin: 28px auto 0;
        width: 100%;
        max-width: 280px;
        border-top: 1px solid var(--ink);
      }
      .closed .ledger .row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 9px 2px;
        border-bottom: 1px solid var(--paper-3);
      }
      .closed .ledger .row span {
        font-size: 11px;
        font-weight: 800;
        letter-spacing: .1em;
        text-transform: uppercase;
        color: var(--ink-3);
      }
      .closed .ledger .row b {
        font-family: var(--serif);
        font-style: italic;
        font-weight: 600;
        font-size: 16px;
        color: var(--ink);
        display: inline-flex;
        align-items: center;
        gap: 7px;
      }
      .closed .ledger .row b svg {
        width: 15px;
        height: 15px;
      }
      .closed .free {
        margin-top: 30px;
        white-space: nowrap;
        font-size: 11px;
        font-weight: 900;
        letter-spacing: .14em;
        text-transform: uppercase;
        color: var(--ink);
        display: inline-flex;
        align-items: center;
        gap: 9px;
        text-decoration: none;
        border-bottom: 1.5px solid var(--ink);
        padding-bottom: 4px;
      }
      .closed .free svg {
        width: 14px;
        height: 14px;
      }
      .closed .datestamp {
        display: inline-block;
        margin-top: 22px;
        border: 1px solid var(--ink-3);
        color: var(--ink-3);
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .16em;
        text-transform: uppercase;
        padding: 5px 10px;
        transform: rotate(-3deg);
      }
      @media (max-width: 420px) {
        .ph {
          width: 100vw;
        }
      }
      .today-spread {
        display: grid;
        align-items: start;
        min-height: calc(100vh - 58px);
        padding-top: clamp(22px, 5vw, 54px);
        padding-bottom: 80px;
      }
      .roadmap-shell {
        width: min(1120px, 100%);
        margin: 0 auto;
      }
      .roadmap-stage {
        position: relative;
        display: grid;
        grid-template-columns: minmax(300px, 430px) minmax(0, 1fr);
        gap: clamp(28px, 5vw, 68px);
        align-items: start;
        padding: 22px 0 70px;
      }
      .roadmap-today-card {
        position: relative;
        z-index: 2;
        width: 100%;
        min-height: 520px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        border: 2px solid var(--ink);
        background: var(--yellow);
        padding: clamp(20px, 4vw, 30px);
        box-shadow: 10px 10px 0 var(--ink);
        overflow: hidden;
      }
      .roadmap-today-card.empty {
        background: var(--paper-2);
      }
      .roadmap-today-card.rest {
        background: var(--paper-2);
      }
      .roadmap-today-card.solo {
        margin: 0 auto;
      }
      .roadmap-today-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 18px;
        color: var(--ink);
        font-family: var(--mono);
        font-size: 11px;
        font-weight: 900;
        letter-spacing: .14em;
        text-transform: uppercase;
      }
      .roadmap-mini-mark {
        width: 34px;
        height: 34px;
        flex: 0 0 auto;
      }
      .roadmap-mini-mark rect:first-of-type {
        fill: var(--ink);
      }
      .roadmap-mini-mark circle {
        fill: var(--blue);
      }
      .roadmap-mini-mark rect:nth-of-type(2) {
        fill: var(--yellow);
        stroke: var(--ink);
        stroke-width: 1;
      }
      .roadmap-mini-mark path {
        fill: var(--red);
      }
      .roadmap-focus {
        display: grid;
        gap: 16px;
        min-width: 0;
      }
      .roadmap-focus > div {
        display: grid;
        gap: 8px;
        min-width: 0;
      }
      .roadmap-focus span,
      .roadmap-recommendation span,
      .roadmap-rest-state span,
      .roadmap-node-copy em {
        color: var(--ink-2);
        font-family: var(--mono);
        font-size: 10px;
        font-style: normal;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .roadmap-topic-list {
        display: grid;
        gap: 8px;
        min-width: 0;
      }
      .roadmap-focus strong {
        color: var(--ink);
        font-family: var(--display);
        font-size: clamp(18px, 3vw, 25px);
        line-height: 1.02;
        letter-spacing: -.02em;
        font-weight: 900;
        overflow-wrap: anywhere;
      }
      .roadmap-recommendation {
        display: grid;
        gap: 8px;
        border-top: 2px solid var(--ink);
        padding-top: 16px;
      }
      .roadmap-recommendation strong,
      .roadmap-rest-state strong {
        color: var(--ink);
        font-family: var(--display);
        font-size: clamp(30px, 5vw, 46px);
        line-height: .94;
        letter-spacing: -.03em;
        font-weight: 900;
      }
      .roadmap-recommendation p,
      .roadmap-rest-state p,
      .roadmap-node-copy span {
        margin: 0;
        color: var(--ink-2);
        font-size: 13px;
        line-height: 1.42;
      }
      .roadmap-rest-state {
        display: grid;
        gap: 12px;
        align-content: center;
        min-height: 320px;
      }
      .roadmap-secondary-link {
        justify-self: start;
        color: var(--ink);
        font-family: var(--mono);
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
        text-decoration: none;
        border-bottom: 2px solid var(--ink);
      }
      .roadmap-action-cluster {
        display: grid;
        gap: 10px;
      }
      button.roadmap-primary-button,
      button.roadmap-retry-button {
        display: inline-flex;
        min-height: 58px;
        width: 100%;
        align-items: center;
        justify-content: center;
        gap: 10px;
        border: 2px solid var(--ink);
        background: var(--red);
        color: var(--paper);
        box-shadow: 5px 5px 0 var(--ink);
        font-family: var(--mono);
        font-size: 12px;
        font-weight: 900;
        letter-spacing: .13em;
        text-transform: uppercase;
        transition: transform .15s ease, box-shadow .15s ease, background .15s ease;
      }
      button.roadmap-primary-button:hover:not(:disabled),
      button.roadmap-retry-button:hover:not(:disabled) {
        transform: translate(-2px, -2px);
        box-shadow: 7px 7px 0 var(--ink);
      }
      button.roadmap-primary-button:active:not(:disabled),
      button.roadmap-retry-button:active:not(:disabled) {
        transform: translate(2px, 2px);
        box-shadow: 2px 2px 0 var(--ink);
      }
      button.roadmap-primary-button:disabled {
        background: var(--ink-3);
        cursor: not-allowed;
      }
      button.roadmap-retry-button {
        min-height: 44px;
        background: var(--ink);
      }
      .roadmap-path-board {
        position: relative;
        display: grid;
        grid-template-columns: minmax(230px, 290px) minmax(220px, 1fr);
        gap: clamp(22px, 4vw, 38px);
        align-items: center;
        min-height: 560px;
      }
      .roadmap-session-spine {
        position: relative;
        display: grid;
        gap: 12px;
        padding: 10px 0;
      }
      .roadmap-spine-rail {
        position: absolute;
        left: 29px;
        top: 28px;
        bottom: 28px;
        width: 0;
        border-left: 3px solid var(--ink);
        z-index: 0;
      }
      .roadmap-spine-rail::after {
        content: "";
        position: absolute;
        left: -3px;
        top: 0;
        bottom: 0;
        border-left: 3px dashed var(--paper);
        opacity: .42;
      }
      .roadmap-spine-node {
        position: relative;
        z-index: 1;
        display: grid;
        grid-template-columns: 62px minmax(0, 1fr);
        align-items: center;
        gap: 12px;
        min-height: 62px;
        padding: 0;
        color: var(--ink);
        text-align: left;
        text-decoration: none;
        transition: opacity .15s ease, transform .15s ease;
      }
      .roadmap-spine-node.dimmed {
        opacity: .48;
      }
      .roadmap-spine-node.recommended {
        opacity: 1;
        transform: translateX(3px);
      }
      .roadmap-spine-node:hover {
        opacity: 1;
      }
      .roadmap-step-mark {
        display: inline-flex;
        width: 58px;
        height: 58px;
        align-items: center;
        justify-content: center;
        border: 2px solid var(--ink);
        background: var(--paper);
        color: var(--ink);
        box-shadow: 4px 4px 0 var(--ink);
        font-family: var(--mono);
        font-size: 12px;
        font-weight: 900;
        letter-spacing: .08em;
        transition: transform .15s ease, background .15s ease, box-shadow .15s ease;
      }
      .roadmap-step-mark.done {
        background: var(--ink);
        color: var(--paper);
      }
      .roadmap-step-mark.current,
      .roadmap-spine-node.recommended .roadmap-step-mark {
        background: var(--yellow);
      }
      .roadmap-spine-node.recommended .roadmap-step-mark {
        box-shadow: 7px 7px 0 var(--red);
      }
      .roadmap-spine-node.review.recommended .roadmap-step-mark {
        background: var(--red);
        color: var(--paper);
      }
      .roadmap-spine-node.rest.recommended .roadmap-step-mark {
        background: var(--blue);
        color: var(--paper);
      }
      .roadmap-spine-node:hover .roadmap-step-mark,
      .roadmap-branch-card:hover .roadmap-shape {
        transform: translate(-2px, -2px);
      }
      .roadmap-branch-stack {
        position: relative;
        display: grid;
        gap: 20px;
        align-content: center;
      }
      .roadmap-branch-stack::before {
        content: "";
        position: absolute;
        left: -38px;
        top: 50%;
        width: 38px;
        border-top: 3px solid var(--ink);
      }
      .roadmap-branch-card {
        position: relative;
        display: grid;
        grid-template-columns: 78px minmax(0, 1fr);
        align-items: center;
        gap: 16px;
        min-height: 136px;
        border: 2px solid var(--ink);
        background: var(--paper);
        color: var(--ink);
        padding: 16px;
        text-decoration: none;
        box-shadow: 6px 6px 0 var(--ink);
        transition: opacity .15s ease, transform .15s ease, box-shadow .15s ease;
      }
      .roadmap-branch-card::before {
        content: "";
        position: absolute;
        left: -25px;
        top: 50%;
        width: 25px;
        border-top: 2px solid var(--ink);
      }
      .roadmap-branch-card.dimmed {
        opacity: .55;
      }
      .roadmap-branch-card.recommended {
        opacity: 1;
        background: var(--yellow);
        box-shadow: 9px 9px 0 var(--red);
      }
      .roadmap-branch-card:hover {
        opacity: 1;
        transform: translate(-2px, -2px);
        box-shadow: 8px 8px 0 var(--ink);
      }
      .roadmap-shape {
        width: 68px;
        height: 68px;
        overflow: visible;
        filter: drop-shadow(3px 3px 0 var(--ink));
        transition: transform .15s ease, filter .15s ease;
      }
      .roadmap-shape path,
      .roadmap-shape circle {
        stroke: var(--ink);
        stroke-width: 3;
      }
      .roadmap-shape.triangle path {
        fill: var(--red);
      }
      .roadmap-shape.circle circle {
        fill: var(--blue);
      }
      .roadmap-node-copy {
        display: grid;
        gap: 4px;
        min-width: 0;
      }
      .roadmap-node-copy strong {
        color: var(--ink);
        font-family: var(--display);
        font-size: 16px;
        line-height: 1;
        letter-spacing: -.02em;
        font-weight: 900;
        overflow-wrap: anywhere;
      }
      .roadmap-spine-node.recommended .roadmap-node-copy strong,
      .roadmap-branch-card.recommended .roadmap-node-copy strong {
        background: linear-gradient(transparent 58%, rgba(216,50,26,.28) 58%);
      }
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
      .continue-card {
        margin-top: 18px;
        padding: 18px 20px;
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 18px;
        align-items: center;
        background: var(--paper);
      }
      .continue-card h2 {
        margin: 6px 0 4px;
        font-family: var(--display);
        font-size: 27px;
        line-height: 1;
        letter-spacing: -.03em;
      }
      .continue-card p {
        margin: 0;
        color: var(--ink-2);
        line-height: 1.38;
      }
      .session-progress-bar {
        overflow: hidden;
        width: 100%;
        height: 8px;
        margin-top: 12px;
        border: 1px solid var(--ink);
        background: var(--paper-2);
      }
      .session-progress-bar span {
        display: block;
        height: 100%;
        background: var(--red);
        transition: width .18s ease;
      }
      .continue-meta {
        margin-top: 8px;
        display: flex;
        flex-wrap: wrap;
        gap: 8px 14px;
        color: var(--ink-2);
        font-family: var(--mono);
        font-size: 10px;
        letter-spacing: .08em;
        text-transform: uppercase;
        font-weight: 800;
      }
      .continue-vocab {
        grid-column: 1 / -1;
      }
      .atelier-empty-state {
        margin-bottom: 18px;
        padding: 18px;
      }
      .atelier-empty-state p {
        margin: 6px 0 14px;
        color: var(--ink-2);
      }
      .vocab-focus {
        border: 1px solid var(--ink);
        background: var(--paper-2);
      }
      .vocab-focus header {
        min-height: 38px;
        padding: 0 12px;
        border-bottom: 1px solid var(--ink);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }
      .vocab-focus-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 12px;
      }
      .vocab-focus-list span,
      .target-word-strip span {
        border: 1px solid var(--ink);
        background: var(--paper);
        padding: 8px 10px;
        display: inline-flex;
        align-items: baseline;
        gap: 8px;
      }
      .vocab-focus-list strong,
      .target-word-strip span {
        font-family: var(--serif);
        font-style: italic;
        font-size: 18px;
      }
      .vocab-focus-list em,
      .target-word-strip em {
        color: var(--ink-2);
        font-family: var(--grotesk);
        font-size: 12px;
        font-style: normal;
      }
      .vocab-focus.compact header {
        min-height: 32px;
      }
      .vocab-focus.compact .vocab-focus-list {
        padding: 10px;
      }
      .vocab-focus.compact .vocab-focus-list span {
        padding: 6px 8px;
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
      .mobile-session-topbar,
      .mobile-session-brief {
        display: none;
      }
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
      .desktop-vocab-focus { margin-top: 18px; }
      .sentence-xray { padding-top: 12px; padding-bottom: 34px; }
      .sentence-xray > p { margin: 0; font-family: var(--serif); font-style: italic; font-size: 39px; line-height: 1.45; }
      .sentence-xray.missing-panel > p { font-family: var(--mono); font-style: normal; font-size: 13px; color: var(--ink-2); text-transform: uppercase; letter-spacing: .12em; }
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
      .choice-row button, .type-case button, .target-chips span { border: 1px solid var(--ink); background: var(--paper); padding: 8px 15px; font-family: var(--serif); font-style: italic; font-size: 19px; }
      .choice-row.compact button, .target-chips span { font-family: var(--mono); font-style: normal; font-size: 10px; letter-spacing: .1em; text-transform: uppercase; font-weight: 900; }
      .choice-row button.selected { background: var(--blue); color: var(--paper); }
      .type-case { margin-bottom: 12px; padding: 14px; background: var(--paper-2); border: 1px solid var(--ink); }
      .type-case button.used { opacity: .35; text-decoration: line-through; cursor: default; }
      .word-bank-builder { display: grid; gap: 10px; }
      .word-bank-answer { display: flex; flex-wrap: wrap; gap: 8px; min-height: 34px; }
      .word-bank-answer button { border: 1px solid var(--ink); background: var(--yellow); padding: 6px 10px; font-family: var(--serif); font-size: 18px; font-style: italic; }
      .sub-exercise input, .sub-exercise textarea, .produce-panel textarea, .output-ladder-panel textarea { width: 100%; border: 1px solid var(--ink); background: var(--paper); outline: none; padding: 13px 15px; font-family: var(--serif); font-style: italic; font-size: 19px; }
      .sub-exercise textarea { min-height: 86px; resize: vertical; }
      .inline-feedback { margin-top: 12px; border-left: 4px solid var(--blue); background: rgba(29,58,138,.06); padding: 10px 12px; font-size: 13px; line-height: 1.42; color: var(--ink-2); }
      .inline-feedback.correct { display: inline-flex; align-items: center; gap: 8px; border-left-color: var(--ink); background: rgba(20,17,13,.06); color: var(--ink); font-family: var(--mono); font-size: 10px; letter-spacing: .12em; text-transform: uppercase; font-weight: 900; }
      .ai-review-line { margin-top: 12px; display: inline-flex; align-items: center; min-height: 28px; font-family: var(--mono); font-size: 10px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: var(--blue); }
      .ai-review-line.complete { color: var(--ink); }
      .ai-review-line.failed { color: var(--muted); }
      .ai-review-button { min-height: 34px; border: 1px solid var(--blue); background: transparent; color: var(--blue); padding: 0 12px; font-family: var(--mono); font-size: 10px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; }
      .ai-review-button:disabled { opacity: .45; cursor: wait; }
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
      .target-word-strip {
        margin-top: 12px;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .target-word-strip span {
        background: var(--paper-2);
      }
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
      .recap-next {
        margin: 0 36px 20px;
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 22px;
        align-items: center;
        border: 2px solid var(--ink);
        background: var(--yellow);
        padding: 18px 20px;
        box-shadow: 6px 6px 0 var(--ink);
      }
      .recap-next h3 {
        margin: 8px 0 6px;
        font-family: var(--display);
        font-size: 32px;
        line-height: .96;
        letter-spacing: -.03em;
      }
      .recap-next p {
        margin: 0;
        color: var(--ink-2);
        line-height: 1.45;
      }
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
      @media (max-width: 760px) {
        .atelier-page {
          background-image: none;
          overflow-x: hidden;
        }
        .spread {
          padding-left: 16px;
          padding-right: 16px;
        }
        .today-spread {
          padding-top: 16px;
          padding-bottom: calc(92px + env(safe-area-inset-bottom));
        }
        .roadmap-shell {
          width: 100%;
        }
        .roadmap-stage {
          min-height: auto;
          display: grid;
          grid-template-columns: 1fr;
          gap: 24px;
          padding: 4px 0 34px;
        }
        .roadmap-today-card {
          width: min(100%, 420px);
          min-height: 430px;
          margin: 0 auto;
          padding: 20px;
          box-shadow: 7px 7px 0 var(--ink);
        }
        .roadmap-today-top {
          font-size: 10px;
        }
        .roadmap-focus {
          gap: 14px;
        }
        .roadmap-focus strong {
          font-size: clamp(17px, 5.4vw, 23px);
          line-height: 1.04;
        }
        .roadmap-primary-button {
          min-height: 56px;
          font-size: 11px;
        }
        .roadmap-path-board {
          grid-template-columns: 1fr;
          gap: 20px;
          min-height: auto;
        }
        .roadmap-session-spine {
          width: min(100%, 420px);
          margin: 0 auto;
          gap: 10px;
        }
        .roadmap-spine-node {
          min-height: 58px;
          grid-template-columns: 58px minmax(0, 1fr);
          gap: 10px;
        }
        .roadmap-step-mark {
          width: 54px;
          height: 54px;
          box-shadow: 3px 3px 0 var(--ink);
        }
        .roadmap-spine-rail {
          left: 27px;
        }
        .roadmap-branch-stack {
          width: min(100%, 420px);
          margin: 0 auto;
          gap: 14px;
        }
        .roadmap-branch-stack::before,
        .roadmap-branch-card::before {
          display: none;
        }
        .roadmap-branch-card {
          grid-template-columns: 58px minmax(0, 1fr);
          min-height: 112px;
          padding: 14px;
          box-shadow: 4px 4px 0 var(--ink);
        }
        .roadmap-shape {
          width: 52px;
          height: 52px;
          filter: drop-shadow(3px 3px 0 var(--ink));
        }
        .atelier-load-notice,
        .atelier-title {
          align-items: stretch;
          flex-direction: column;
        }
        .atelier-load-notice .btn,
        .atelier-title .btn {
          width: 100%;
        }
        .atelier-title {
          gap: 14px;
          padding-bottom: 16px;
          margin-bottom: 16px;
          border-bottom-width: 2px;
        }
        .atelier-title h1 {
          font-size: 40px;
        }
        .atelier-passport {
          padding: 18px 16px;
          border-width: 1px;
        }
        .practice-summary p {
          margin-bottom: 0;
          font-size: 15px;
        }
        .quote-card,
        .atelier-loop,
        .atlas,
        .priority-list,
        .atelier-footer {
          display: none;
        }
        .continue-card {
          grid-template-columns: 1fr;
          padding: 16px;
          gap: 14px;
        }
        .continue-card .btn {
          width: 100%;
        }
        .continue-card h2 {
          font-size: 24px;
        }
        .continue-meta {
          gap: 6px;
        }
        .continue-vocab .vocab-focus-list {
          display: grid;
          grid-template-columns: 1fr;
        }
        .today-set-head {
          margin: 22px 0 10px;
        }
        .concept-grid {
          gap: 12px;
        }
        .concept-cover {
          min-height: auto;
        }
        .cover-band {
          min-height: 30px;
          padding-inline: 10px;
        }
        .cover-symbol {
          display: none;
        }
        .cover-title {
          padding: 12px;
        }
        .cover-title h3 {
          font-size: 20px;
          line-height: 1.08;
        }
        .cover-foot {
          align-items: flex-start;
          padding: 10px 12px;
          font-size: 12px;
        }
        .stat-row {
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 14px;
          margin-top: 20px;
        }
        .stat {
          min-height: 84px;
        }
        .stat .t-num {
          font-size: 38px;
        }
        .lower-board {
          margin-top: 22px;
        }
        .side-stack {
          gap: 14px;
        }
        .notebook-bridge,
        .mission-bridge,
        .due-errata-list {
          border-width: 1px;
        }
        .notebook-row {
          grid-template-columns: 24px 38px 1fr;
        }
        .notebook-row .cefr {
          display: none;
        }
        .due-errata-list article {
          grid-template-columns: 1fr;
          align-items: start;
        }
        .due-errata-actions {
          justify-content: flex-start;
        }
        .session-spread {
          width: 100%;
          min-height: 100vh;
          padding-top: 0;
          padding-bottom: 28px;
        }
        .session-title-row,
        .session-spread > .rule,
        .concept-bench,
        .round-strip,
        .xray-title,
        .xray-board,
        .desktop-vocab-focus,
        .margin-stack {
          display: none;
        }
        .mobile-session-topbar {
          position: sticky;
          top: 0;
          z-index: 35;
          display: grid;
          grid-template-columns: 74px minmax(0, 1fr) 74px;
          align-items: center;
          min-height: 54px;
          margin-left: -16px;
          margin-right: -16px;
          padding: 0 16px;
          border-bottom: 1px solid var(--ink);
          background: var(--paper);
        }
        .mobile-session-topbar div {
          min-width: 0;
          text-align: center;
        }
        .mobile-session-topbar strong {
          display: block;
          margin-top: 2px;
          font-family: var(--mono);
          font-size: 11px;
          letter-spacing: .08em;
          text-transform: uppercase;
        }
        .mobile-back-button,
        .mobile-quiet-button {
          min-height: 40px;
          font-family: var(--mono);
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .08em;
          text-transform: uppercase;
        }
        .mobile-back-button {
          text-align: left;
        }
        .mobile-quiet-button {
          text-align: right;
          color: var(--blue);
        }
        .mobile-quiet-button:disabled {
          color: var(--ink-3);
          opacity: .5;
        }
        .mobile-session-brief {
          display: grid;
          gap: 14px;
          padding: 16px 0 10px;
          border-bottom: 1px solid var(--ink);
        }
        .mobile-session-heading {
          min-width: 0;
          max-width: 100%;
        }
        .mobile-session-heading h1 {
          max-width: 100%;
          margin: 7px 0 2px;
          font-family: var(--display);
          font-size: clamp(27px, 7.4vw, 36px);
          font-style: normal;
          font-weight: 900;
          line-height: 1;
          letter-spacing: 0;
          overflow-wrap: break-word;
          white-space: normal;
        }
        .mobile-session-heading p {
          margin: 0;
          color: var(--ink-2);
          font-size: 13px;
          line-height: 1.35;
        }
        .mobile-vocab-focus header {
          display: none;
        }
        .mobile-vocab-focus .vocab-focus-list {
          display: flex;
          flex-wrap: nowrap;
          gap: 12px;
          overflow-x: auto;
          padding: 0 0 2px;
          scrollbar-width: none;
        }
        .mobile-vocab-focus .vocab-focus-list::-webkit-scrollbar {
          display: none;
        }
        .mobile-vocab-focus.vocab-focus {
          min-width: 0;
          max-width: 100%;
          border: 0;
          background: transparent;
        }
        .mobile-vocab-focus .vocab-focus-list span {
          flex: 0 0 auto;
          border: 0;
          border-left: 3px solid var(--blue);
          background: transparent;
          padding: 0 10px;
        }
        .mobile-vocab-focus .vocab-focus-list strong {
          font-size: 20px;
        }
        .mobile-vocab-focus .vocab-focus-list em {
          display: none;
        }
        .mobile-context-details {
          border: 0;
          border-top: 1px solid var(--ink);
          background: transparent;
        }
        .mobile-context-details summary {
          min-height: 36px;
          padding: 10px 0;
          font-family: var(--mono);
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .12em;
          text-transform: uppercase;
          cursor: pointer;
        }
        .mobile-context-details .rule-panel {
          border-left: 0;
          border-top: 1px solid var(--ink);
          padding: 14px 0;
        }
        .work-grid {
          margin-top: 14px;
        }
        .exercise-toolbar {
          gap: 10px;
          margin-bottom: 12px;
        }
        .mode-markers {
          grid-template-columns: repeat(3, minmax(0, 1fr));
          border: 0;
          gap: 8px;
        }
        .mode-markers button {
          min-height: 44px;
          border: 0;
          border-bottom: 2px solid var(--ink-3);
          padding: 4px 2px;
          font-size: 9px;
          letter-spacing: .06em;
        }
        .mode-markers button.active {
          border-bottom-color: var(--red);
          background: transparent;
          color: var(--red);
        }
        .exercise-frame {
          min-height: auto;
          padding: 12px 0 0;
          border: 0;
          background: transparent;
        }
        .exercise-frame > .crop-mark {
          display: none;
        }
        .recognize-set,
        .transform-set,
        .output-ladder-panel {
          gap: 16px;
        }
        .sub-exercise {
          padding-bottom: 16px;
        }
        .exercise-prompt,
        .source-sentence {
          font-size: 23px;
          line-height: 1.33;
          margin: 10px 0 14px;
        }
        .source-sentence {
          padding: 12px;
        }
        .choice-row button,
        .type-case button {
          flex: 1 1 calc(50% - 8px);
          min-height: 44px;
          padding: 8px 10px;
          font-size: 17px;
        }
        .choice-row.compact button {
          flex-basis: 100%;
          font-size: 10px;
        }
        .type-case {
          padding: 0;
          border: 0;
          background: transparent;
        }
        .sub-exercise input,
        .sub-exercise textarea,
        .produce-panel textarea,
        .output-ladder-panel textarea,
        .errata-review-answer textarea {
          border: 0;
          border-bottom: 1px solid var(--ink);
          background: transparent;
          font-size: 18px;
          box-shadow: none;
        }
        .word-bank-answer button {
          border: 0;
          border-bottom: 2px solid var(--ink);
          background: transparent;
          padding: 5px 2px;
        }
        .ladder-stage {
          grid-template-columns: 1fr;
          gap: 12px;
        }
        .ladder-stage h3 {
          font-size: 26px;
        }
        .stage-meter {
          width: max-content;
        }
        .voice-capture {
          align-items: flex-start;
          flex-direction: column;
        }
        .voice-button {
          width: 100%;
        }
        .produce-panel textarea {
          min-height: 190px;
        }
        .output-ladder-panel textarea {
          min-height: 150px;
        }
        .target-chips,
        .target-word-strip {
          display: grid;
          grid-template-columns: 1fr;
        }
        .session-spread .action-row {
          position: sticky;
          bottom: 0;
          z-index: 28;
          margin: 18px -16px -18px;
          padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
          border-top: 1px solid var(--ink);
          background: var(--paper);
        }
        .session-spread .action-row .btn {
          flex: 1 1 0;
          min-height: 48px;
          padding-inline: 10px;
        }
        .recap-overlay {
          align-items: end;
          padding: 12px;
        }
        .recap-modal,
        .errata-review-modal {
          width: 100%;
          max-height: calc(100vh - 24px);
          box-shadow: none;
        }
        .recap-modal header,
        .errata-review-modal header {
          padding: 20px 18px 16px;
          align-items: flex-start;
          flex-direction: column;
          gap: 12px;
        }
        .recap-modal h2,
        .errata-review-modal h2 {
          font-size: 34px;
        }
        .recap-stats {
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 14px;
          padding: 16px 18px;
        }
        .recap-lines,
        .errata-review-body {
          padding: 18px;
        }
        .recap-lines > div:not(.t-mono) {
          grid-template-columns: 32px 1fr;
          gap: 10px;
        }
        .recap-lines > div:not(.t-mono) span {
          grid-column: 2;
        }
        .recap-next {
          margin: 0 18px 16px;
          grid-template-columns: 1fr;
          gap: 14px;
          padding: 16px;
          box-shadow: 4px 4px 0 var(--ink);
        }
        .recap-next h3 {
          font-size: 26px;
        }
        .recap-next .btn {
          width: 100%;
        }
        .recap-modal footer {
          align-items: stretch;
          flex-direction: column;
          padding: 16px 18px;
          gap: 12px;
        }
        .recap-actions,
        .recap-actions .btn {
          width: 100%;
        }
        .errata-review-answer .action-row {
          align-items: stretch;
          flex-direction: column;
        }
      }
    `}</style>
  );
}

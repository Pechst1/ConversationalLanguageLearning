import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import axios from 'axios';
import { ArrowRight, BookOpen, Check, HelpCircle, Loader2, MapPinned, Mic, RotateCcw, Send, Square, Volume2, X } from 'lucide-react';
import toast from 'react-hot-toast';

import { createAudioMediaRecorder, recordedAudioBlob } from '@/lib/audio-recording';
import { seanceAssessment } from '@/lib/seance-feedback';
import apiService, {
  AtelierCollectible,
  AtelierAttemptRead,
  AtelierAttemptResult,
  AtelierConcept,
  AtelierErrataAttemptResult,
  AtelierErrataReviewTask,
  AtelierErratum,
  AtelierSessionStart,
  AtelierToday,
  DailyWordSlate,
  VocabularyRecommendationItem,
} from '@/services/api';
import { ConceptMotif } from '@/components/grammar/ConceptMotif';
import { nativePushIsAvailable, registerNativePushToken } from '@/lib/native-push';
import {
  cacheAtelierEdition,
  clearResumeActivity,
  readCachedAtelierEdition,
  saveResumeActivity,
} from '@/lib/pilot-resilience';
import { type LuAskKind } from '@/components/laune/LaUne';
import { HomeScreen, HomeSkeleton, type HomeTile } from '@/components/atelier-v2/home/HomeScreen';
import {
  LEpreuveStyles,
  EpShell,
  EpTopbar,
  EpEyebrow,
  EpProvenance,
  EpConcept,
  EpMotif,
  EpRule,
  EpPrompt,
  Blank,
  EpOpts,
  EpOpt,
  EpSlug,
  EpSetLine,
  EpCases,
  EpConfidence,
  EpVerdict,
  EpBar,
  EpFoot,
  EpFix,
  EpIns,
  EpLabelFix,
  EpLineFix,
  EpGalley,
  EpRelecture,
  EpCorrect,
  EpRepair,
  EpListen,
  EpRecord,
  EpLock,
  EpBatStage,
  EpRecapHead,
  EpTally,
  EpProof,
  EpSeal,
  EpStreak,
  EpMint,
  EpPhrase,
  EpHandoff,
  EpNotice,
  type MotifPrim,
} from '@/components/epreuve/Epreuve';
import EditorialMasthead from '@/components/layout/EditorialMasthead';
import PhoneProductNav from '@/components/layout/PhoneProductNav';
// Atelier V2 daily journey (WP-07 functional milestone). The V2 branch below is
// entirely additive: with the capability off nothing here renders and every
// legacy route, deep link and in-progress session behaves exactly as before.
import {
  JourneySession,
  JourneyTodayCard,
  useDailyJourney,
} from '@/components/atelier-v2/journey';
import { ExerciseShell } from '@/components/ui/ExerciseShell';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { Confetti, LogoToken, Seal, sealForEdition, type SealVariant } from '@/components/ui/Seal';
import {
  buildDayProgress,
  dayQueryString,
  resolveLegacyRecommendedNext,
  resolveRecommendedNext,
  resolvePracticeEntry,
  PRACTICE_LABEL,
  serialActionFromToday,
  type DayProgress,
  type RecommendedAction,
} from '@/lib/atelier-next';
import { learnerGloss } from '@/lib/glosses';
import { pulseAppHaptic } from '@/lib/haptics';
import { STORY_FEATURE_VISIBLE } from '@/lib/launch-flags';
import { cn } from '@/lib/utils';
import { resolveMediaUrl } from '@/lib/media-url';

type RoundName = 'recognize' | 'transform' | 'sentence' | 'produce' | 'speak' | 'conversation';
type RecognizeMode = 'fill' | 'word_bank' | 'classify';
type RoadmapTarget = RoundName | 'vocabulary' | 'review' | 'mission' | 'studio' | 'library' | 'feuilleton' | 'rest';
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
type RewardMoment = {
  id: string;
  kind: 'logo_token' | 'gilt_seal';
  collectible?: AtelierCollectible;
};
type RepairRetest = {
  id: string;
  status: 'queued' | 'completed';
  sourceAttemptId: string;
  conceptId: number | null;
  round: RoundName;
  mode: string;
  exerciseId: string;
  dueAfterCompleted: number;
  promptPayload: Record<string, any>;
};

const recognizeModes: Array<{ id: RecognizeMode; label: string; short: string }> = [
  { id: 'fill', label: 'Compléter', short: 'A' },
  { id: 'classify', label: 'Classer', short: 'B' },
  { id: 'word_bank', label: 'Banque de mots', short: 'C' },
];

// Mirrors the backend's enforced exercise-set shape (ATELIER_DRILLS_PER_CONCEPT
// in app/services/atelier.py): nine recognition items, three transforms, then
// one written line, one spoken line and one conversation turn per concept, plus
// a single integrated paragraph for the session.
const DRILLS_PER_CONCEPT = 15;
const SESSION_LEVEL_DRILLS = 1;

// A concept's earned skips, granted by the backend once the learner has proved
// the rung (see _maybe_apply_adaptive_lock). Locked drills are removed from the
// ladder entirely -- both the work and the denominator.
type AdaptiveLock = {
  concept_id?: number;
  title?: string;
  skipped_modes?: string[];
  skipped_rounds?: string[];
};

function sessionAdaptiveLocks(session: AtelierSessionStart | null): Record<string, AdaptiveLock> {
  const raw = (session?.learning_moments as Record<string, any> | undefined)?.adaptive_locks;
  return raw && typeof raw === 'object' ? (raw as Record<string, AdaptiveLock>) : {};
}

function lockedRecognizeModes(locks: Record<string, AdaptiveLock>, conceptId?: number | null): Set<string> {
  const lock = conceptId == null ? null : locks[String(conceptId)];
  return new Set(lock?.skipped_modes || []);
}

function roundIsLocked(locks: Record<string, AdaptiveLock>, conceptId: number | null | undefined, round: RoundName) {
  const lock = conceptId == null ? null : locks[String(conceptId)];
  return Boolean(lock?.skipped_rounds?.includes(round));
}

const roundLabels: Array<{ id: RoundName; label: string; roman: string }> = [
  { id: 'recognize', label: 'Reconnaître', roman: 'I' },
  { id: 'transform', label: 'Transformer', roman: 'II' },
  { id: 'sentence', label: 'Phrase', roman: 'III' },
  { id: 'produce', label: 'Paragraphe', roman: 'IV' },
  { id: 'speak', label: 'À l’oral', roman: 'V' },
  { id: 'conversation', label: 'Conversation', roman: 'VI' },
];

// The eyebrow half of this table was never rendered (EpPrompt dropped its label
// prop); the round is already named by the sheet's eyebrow above the prompt.
const OUTPUT_LADDER_META: Record<'sentence' | 'speak' | 'conversation', { instruction: string }> = {
  sentence: {
    instruction: 'Réagissez à la situation ci-dessous avec une phrase française complète.',
  },
  speak: {
    instruction: 'Enregistrez votre réponse : nous la transcrivons et relisons la grammaire.',
  },
  conversation: {
    instruction: 'Répondez naturellement au message avec la grammaire que vous venez de travailler.',
  },
};

function answerKey(round: RoundName, mode: string, conceptId?: number | null, itemId?: string | null) {
  const base = `${round}:${mode}:${conceptId || 'session'}`;
  return itemId ? `${base}:${itemId}` : base;
}

// The word-bank meaning cue often arrives as "Express: I was reading…". The task
// is already stated once at the top of the screen, so each subtask shows only the
// bare English sentence to translate.
function stripExpressPrefix(value: unknown): string {
  return String(value || '').replace(/^\s*express\s*:\s*/i, '').trim();
}

function isVagueOutputPrompt(value: unknown): boolean {
  const normalized = String(value || '').trim().toLowerCase().replace(/\s+/g, ' ');
  if (!normalized) return true;
  return [
    'target grammar',
    'target concept',
    'use the grammar',
    'using the grammar',
    'one sentence using',
    'say one natural response',
    'answer in one conversational turn',
    'write one real future condition',
    'describe a background interrupted by an event',
    'answer with one background and one completed event',
  ].some((marker) => normalized.includes(marker));
}

function fallbackOutputPrompt(payload: Record<string, any>, item: Record<string, any>, round: 'sentence' | 'speak' | 'conversation'): string {
  const conceptTitle = String(payload?.concept?.name || payload?.rule_panel?.title || '').toLowerCase();
  const anchorSentence = String(item?.context_anchor?.sentence || '').trim();
  if (conceptTitle.includes('imparfait') || conceptTitle.includes('passé composé') || conceptTitle.includes('passe compose')) {
    return round === 'conversation'
      ? 'Message reçu : « Pourquoi tu n’as pas répondu hier soir ? » Dites ce qui était en cours et ce qui s’est produit.'
      : round === 'speak'
        ? 'Un collègue demande ce que vous faisiez quand le téléphone a sonné. Dites une phrase avec le contexte et l’événement.'
        : 'Un ami demande pourquoi vous êtes arrivé en retard hier. Expliquez en une phrase française ce qui se passait et ce qui s’est produit.';
  }
  if (conceptTitle.includes('si type') || conceptTitle.includes('si +') || conceptTitle.includes('condition')) {
    return round === 'conversation'
      ? 'Message reçu : « S’il pleut demain, on fait quoi ? » Répondez avec une condition réelle et sa conséquence.'
      : round === 'speak'
        ? 'Un ami demande ce que vous ferez s’il pleut demain. Donnez une réponse naturelle avec si + présent.'
        : 'Un collègue demande : « Tu termines tôt aujourd’hui ? » Répondez en disant ce que vous ferez dans ce cas.';
  }
  if (conceptTitle.includes('negation') || conceptTitle.includes('négation') || conceptTitle.includes('pas de')) {
    return round === 'conversation'
      ? 'Message reçu : « Tu as encore du café ? » Répondez avec une quantité niée.'
      : round === 'speak'
        ? 'Au café, on demande ce qui est disponible. Citez un élément manquant avec ne…pas de/d’.'
        : 'Un ami demande ce qu’il reste à boire ou à manger. Dites une chose que vous n’avez pas.';
  }
  if (anchorSentence) return `Réagissez à cette situation : ${anchorSentence}`;
  return round === 'conversation'
    ? 'Message reçu : « Qu’est-ce qui se passe ? » Répondez naturellement en français.'
    : 'Un ami demande une nouvelle concrète de votre journée. Répondez en français avec une phrase complète.';
}

function outputLadderPrompt(payload: Record<string, any>, item: Record<string, any>, round: 'sentence' | 'speak' | 'conversation'): string {
  const prompt = String(item?.prompt || '').trim();
  return isVagueOutputPrompt(prompt) ? fallbackOutputPrompt(payload, item, round) : prompt;
}

function roundUsesSessionScope(round: RoundName) {
  return round === 'produce';
}

function roundUsesItemScope(round: RoundName) {
  return round === 'recognize' || round === 'transform';
}

function roundMode(round: RoundName, mode: RecognizeMode) {
  return round === 'recognize' ? mode : round;
}

function isRoundName(value: unknown): value is RoundName {
  return roundLabels.some((item) => item.id === value);
}

type AtelierExerciseSet = AtelierSessionStart['exercise_sets'][number];

function drillItems(payload: Record<string, any> | null, round: RoundName, mode: RecognizeMode): any[] {
  if (!payload) return [];
  if (round === 'recognize') return payload.recognize?.[mode]?.items || [];
  if (round === 'transform') return payload.transform?.items || [];
  if (round === 'sentence' || round === 'speak' || round === 'conversation') {
    return payload.output_ladder?.[round]?.items || [{}];
  }
  if (round === 'produce') return [payload.produce || {}];
  return [];
}

function exerciseSetForRetest(retest: RepairRetest): Record<string, any> {
  const prompt = retest.promptPayload || {};
  const rulePanel = prompt.rule_panel || {};
  if (retest.round === 'recognize') {
    return { rule_panel: rulePanel, recognize: { [retest.mode]: { items: prompt.items || [] } } };
  }
  if (retest.round === 'transform') {
    return { rule_panel: rulePanel, transform: { items: prompt.items || [] } };
  }
  if (retest.round === 'produce') {
    return { rule_panel: rulePanel, produce: prompt };
  }
  return { rule_panel: rulePanel, output_ladder: { [retest.round]: { items: prompt.items || [] } } };
}

function scopedPromptPayload(
  payload: Record<string, any> | null,
  round: RoundName,
  mode: string,
  item: Record<string, any> | null,
): Record<string, any> {
  const rule_panel = payload?.rule_panel || {};
  if (round === 'recognize' || round === 'transform') {
    return { round, mode, rule_panel, items: item ? [item] : [] };
  }
  if (round === 'produce') return { round, mode, rule_panel, ...(payload?.produce || {}) };
  return { round, mode, rule_panel, items: item ? [item] : [] };
}

function repairRetestFromAttempt(attempt: AtelierAttemptRead, correction: Record<string, any>): RepairRetest | null {
  const raw = correction?.retest;
  if (!raw || !raw.id || !attempt.attempt_id || !attempt.round) return null;
  if (!['recognize', 'transform', 'sentence', 'produce', 'speak', 'conversation'].includes(attempt.round)) return null;
  return {
    id: String(raw.id),
    status: raw.status === 'completed' ? 'completed' : 'queued',
    sourceAttemptId: attempt.attempt_id,
    conceptId: attempt.concept_id ?? null,
    round: attempt.round,
    mode: String(attempt.mode || attempt.round),
    exerciseId: String(attempt.exercise_id || ''),
    dueAfterCompleted: Math.max(1, Number(raw.due_after_completed || 1)),
    promptPayload: attempt.prompt_payload || {},
  };
}

const PROVENANCE_SOURCE_LABELS: Record<string, string> = {
  pilot_capture: 'Capture pilote',
  conversation: 'Conversation',
  atelier: 'Atelier',
  mission: 'Courrier',
  feuilleton: 'Feuilleton',
};

function provenanceLine(erratum?: AtelierErratum | null): string | null {
  if (!erratum) return null;
  const rawSource = String(erratum.source_label || '').trim();
  // Machine keys (snake_case) must never reach the page; map them or prettify.
  const source = rawSource.includes('_')
    ? PROVENANCE_SOURCE_LABELS[rawSource.toLowerCase()] || rawSource.replace(/_/g, ' ')
    : rawSource;
  const reason = String(erratum.reason || erratum.display_label || '').trim();
  // A "learner text -> target" mapping would print the answer of the coming
  // repair; fall back to the short label instead of spoiling it.
  const safeReason = /->|→/.test(reason)
    ? String(erratum.display_label || '').trim() || reason.split(/:|->|→/)[0].trim()
    : reason;
  if (!source && !safeReason) return null;
  return [source ? `Manqué · ${source}` : '', safeReason].filter(Boolean).join(' · ');
}

/* LLM explanations arrive with markdown backticks (`fera`); print them as
   French guillemets instead of leaking raw markup onto the page. */
function printableWhy(text?: string | null): string {
  return String(text || '').replace(/`([^`]+)`/g, '« $1 »');
}

function safeDrillItemIndex(index: number, items: any[]) {
  if (!items.length) return 0;
  return Math.max(0, Math.min(index, items.length - 1));
}

function itemIdForKey(item: any, index: number) {
  return String(item?.id || index || '').trim();
}

function answerValueHasContent(value: unknown): boolean {
  if (Array.isArray(value)) return value.some((item) => String(item || '').trim());
  if (typeof value === 'string') return value.trim().length > 0;
  if (value == null) return false;
  if (typeof value === 'object') return Object.values(value as Record<string, unknown>).some(answerValueHasContent);
  return true;
}

function drillAnswerIsReady(
  payload: Record<string, any> | null,
  round: RoundName,
  mode: RecognizeMode,
  activeItemIndex: number,
  currentAnswers: Record<string, any>,
  produceAnswer = '',
) {
  if (round === 'produce') {
    // A non-empty scrap of text is not "the paragraph" the assignment asks
    // for — gate the check button on the stated minimum, same as the server
    // now does defensively in _apply_produce_length_gate.
    const minWords = Number(payload?.produce?.min_words) || 0;
    return minWords > 0 ? wordCount(produceAnswer) >= minWords : produceAnswer.trim().length > 0;
  }
  if (!payload) return false;
  if (round === 'recognize') {
    const items = payload.recognize?.[mode]?.items || [];
    const item = items[safeDrillItemIndex(activeItemIndex, items)] || {};
    return answerValueHasContent(currentAnswers[item.id]);
  }
  if (round === 'transform') {
    const items = payload.transform?.items || [];
    const item = items[safeDrillItemIndex(activeItemIndex, items)] || {};
    return answerValueHasContent(currentAnswers[item.id]);
  }
  if (round === 'sentence' || round === 'speak' || round === 'conversation') {
    return answerValueHasContent(currentAnswers.text);
  }
  return false;
}

function scopedExerciseId(concept: AtelierConcept | null, round: RoundName, mode: RecognizeMode, itemId?: string | null) {
  const base = round === 'produce'
    ? 'integrated-writing'
    : `${concept?.external_id || concept?.id || 'session'}:${round === 'recognize' ? mode : round}`;
  return itemId && roundUsesItemScope(round) ? `${base}:${itemId}` : base;
}

// A lock retires the rungs the learner has NOT reached yet -- never the drills
// they already classed. Dropping a whole rung from the ladder took the finished
// items out of the numerator too, so the stick ran backwards mid-session (24
// drills done, "18/25" on the cap) and EpLock announced "1 exercice retiré"
// while three disappeared. `submitted` is what separates the two: banked items
// stay, unreached ones go, and the count matches `retired_now` again.
function sessionDrillEntries(
  session: AtelierSessionStart | null,
  locks: Record<string, AdaptiveLock> = {},
  submitted: Record<string, boolean> = {},
) {
  if (!session) return [];
  const entries: Array<{ key: string; legacyKey?: string }> = [];
  const exerciseSetByConcept = new Map(session.exercise_sets.map((set) => [set.concept_id, set.payload]));
  const keepLockedItem = (key: string) => Boolean(submitted[key]);
  session.concepts.forEach((concept) => {
    const payload = exerciseSetByConcept.get(concept.id) || null;
    const skippedModes = lockedRecognizeModes(locks, concept.id);
    recognizeModes.forEach((recognizeMode) => {
      const modeIsLocked = skippedModes.has(recognizeMode.id);
      const legacyKey = answerKey('recognize', recognizeMode.id, concept.id);
      const items = drillItems(payload, 'recognize', recognizeMode.id);
      if (!items.length) {
        if (!modeIsLocked) entries.push({ key: legacyKey });
        return;
      }
      items.forEach((item, index) => {
        const key = answerKey('recognize', recognizeMode.id, concept.id, itemIdForKey(item, index));
        if (modeIsLocked && !keepLockedItem(key)) return;
        entries.push({ key, legacyKey });
      });
    });
  });
  session.concepts.forEach((concept) => {
    const transformIsLocked = roundIsLocked(locks, concept.id, 'transform');
    const payload = exerciseSetByConcept.get(concept.id) || null;
    const legacyKey = answerKey('transform', 'transform', concept.id);
    const items = drillItems(payload, 'transform', 'fill');
    if (!items.length) {
      if (!transformIsLocked) entries.push({ key: legacyKey });
      return;
    }
    items.forEach((item, index) => {
      const key = answerKey('transform', 'transform', concept.id, itemIdForKey(item, index));
      if (transformIsLocked && !keepLockedItem(key)) return;
      entries.push({ key, legacyKey });
    });
  });
  session.concepts.forEach((concept) => entries.push({ key: answerKey('sentence', 'sentence', concept.id) }));
  entries.push({ key: answerKey('produce', 'produce', null) });
  session.concepts.forEach((concept) => entries.push({ key: answerKey('speak', 'speak', concept.id) }));
  session.concepts.forEach((concept) => entries.push({ key: answerKey('conversation', 'conversation', concept.id) }));
  return entries;
}

function totalDrills(
  session: AtelierSessionStart | null,
  locks: Record<string, AdaptiveLock> = {},
  submitted: Record<string, boolean> = {},
) {
  return sessionDrillEntries(session, locks, submitted).length;
}

function submittedDrills(
  session: AtelierSessionStart | null,
  submitted: Record<string, boolean>,
  locks: Record<string, AdaptiveLock> = {},
) {
  return sessionDrillEntries(session, locks, submitted)
    .filter((entry) => submitted[entry.key] || Boolean(entry.legacyKey && submitted[entry.legacyKey]))
    .length;
}

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
    label: String(requirement.label || concept.atelier_blueprint?.display_title || concept.name || 'Objectif'),
  };
}

function wordCount(text: string) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function wordRangeLabel(count: number, minWords?: unknown, maxWords?: unknown) {
  const min = Number(minWords);
  const max = Number(maxWords);
  if (Number.isFinite(min) && Number.isFinite(max) && min > 0 && max >= min) {
    const remaining = Math.max(0, Math.round(min) - count);
    const suffix = remaining > 0 ? ` · ${remaining} de plus` : '';
    return `${count} / ${Math.round(min)}-${Math.round(max)} mots${suffix}`;
  }
  return `${count} mots`;
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

function pulseAtelierHaptic(kind: 'correct' | 'repair' | 'complete' | 'token') {
  pulseAppHaptic(kind);
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

function firstMintedCollectible(collectibles: AtelierCollectible[] | undefined, kind: string) {
  return (collectibles || []).find((item) => item.kind === kind);
}

type AtelierErrorNotice = { label: string; message: string };

const ATELIER_CONFIRM_NEEDED_NOTICE: AtelierErrorNotice = {
  label: 'À REPRENDRE',
  message: 'L’Atelier n’a pas pu confirmer la séance en cours. Réessayez avant d’en commencer une autre afin de conserver votre travail.',
};

function describeAtelierError(error: unknown, context: 'load' | 'session'): AtelierErrorNotice {
  const isAxiosError = axios.isAxiosError(error);
  const status = isAxiosError ? error.response?.status : undefined;
  const timedOut = isAxiosError && (error.code === 'ECONNABORTED' || /timeout/i.test(error.message || ''));
  const noResponse = isAxiosError && !error.response;

  if (noResponse && !timedOut) {
    return { label: 'HORS LIGNE', message: 'Vous semblez hors ligne. Vérifiez la connexion puis réessayez.' };
  }
  if (timedOut) {
    return context === 'session'
      ? { label: 'TOUJOURS SOUS PRESSE', message: 'La séance du jour demande plus de temps que prévu. Réessayez : elle est peut-être déjà prête.' }
      : { label: 'CHARGEMENT EN COURS', message: 'L’Atelier répond plus lentement que d’habitude. Réessayez dans un instant.' };
  }
  if (typeof status === 'number' && status >= 500) {
    return context === 'session'
      ? { label: 'PAS ENCORE PRÊTE', message: 'La séance du jour n’a pas pu être préparée. Réessayez dans un instant.' }
      : { label: 'PAS ENCORE PRÊTE', message: 'L’Atelier n’a pas pu charger l’édition du jour. Réessayez dans un instant.' };
  }
  return context === 'session'
    ? { label: 'À REPRENDRE', message: 'La séance du jour n’a pas démarré. Réessayez depuis cet écran.' }
    : { label: 'À REPRENDRE', message: 'L’Atelier est indisponible pour le moment. Réessayez ou revenez dans un instant.' };
}

export default function AtelierPage() {
  const router = useRouter();
  const [today, setToday] = useState<AtelierToday | null>(null);
  const [session, setSession] = useState<AtelierSessionStart | null>(null);
  const [activeConceptIndex, setActiveConceptIndex] = useState(0);
  const [activeItemIndex, setActiveItemIndex] = useState(0);
  const [round, setRound] = useState<RoundName>('recognize');
  const [mode, setMode] = useState<RecognizeMode>('fill');
  const [answers, setAnswers] = useState<Record<string, Record<string, any>>>({});
  const [confidenceByKey, setConfidenceByKey] = useState<Record<string, 'sure' | 'unsure'>>({});
  const [submitted, setSubmitted] = useState<Record<string, boolean>>({});
  const [resubmitKeys, setResubmitKeys] = useState<Record<string, boolean>>({});
  const [correctionsByKey, setCorrectionsByKey] = useState<Record<string, Record<string, any>>>({});
  const [attemptIdsByKey, setAttemptIdsByKey] = useState<Record<string, string>>({});
  const [aiReviewSubmitting, setAiReviewSubmitting] = useState<Record<string, boolean>>({});
  const [repairDrafts, setRepairDrafts] = useState<Record<string, string>>({});
  const [repairSubmitting, setRepairSubmitting] = useState<Record<string, boolean>>({});
  const [repairRetests, setRepairRetests] = useState<Record<string, RepairRetest>>({});
  const [activeRetestId, setActiveRetestId] = useState<string | null>(null);
  const [errata, setErrata] = useState<AtelierErratum[]>([]);
  const [recentCorrection, setRecentCorrection] = useState<Record<string, any> | null>(null);
  const [recap, setRecap] = useState<Record<string, any> | null>(null);
  const [reviewTask, setReviewTask] = useState<AtelierErrataReviewTask | null>(null);
  const [reviewAnswer, setReviewAnswer] = useState('');
  const [reviewResult, setReviewResult] = useState<AtelierErrataAttemptResult | null>(null);
  // 'journey' is the V2 daily-journey shell. It is only ever reachable when the
  // server says the capability is enabled; 'today' and 'session' are unchanged.
  const [view, setView] = useState<'today' | 'session' | 'journey'>('today');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [vocabularyDue, setVocabularyDue] = useState(0);
  const [loadError, setLoadError] = useState<AtelierErrorNotice | null>(null);
  const [activeSessionReady, setActiveSessionReady] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [serialWelcomeDismissed, setSerialWelcomeDismissed] = useState(false);
  const [rewardMoment, setRewardMoment] = useState<RewardMoment | null>(null);
  const [cachedEditionAt, setCachedEditionAt] = useState<string | null>(null);
  const aiPollTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const scheduleAiReviewPollingRef = useRef<(attemptId: string, key: string, remaining?: number) => void>(() => {});

  const hydrateSession = useCallback((next: AtelierSessionStart, openSession = false) => {
    const restoredAnswers: Record<string, Record<string, any>> = {};
    const restoredSubmitted: Record<string, boolean> = { ...(next.submitted_map || {}) };
    const restoredCorrections: Record<string, Record<string, any>> = {};
    const restoredAttemptIds: Record<string, string> = {};
    const restoredConfidence: Record<string, 'sure' | 'unsure'> = {};
    const restoredRetests: Record<string, RepairRetest> = {};
    const restoredErrata: AtelierErratum[] = [];

    (next.attempts || []).forEach((attempt: AtelierAttemptRead) => {
      const fallbackKey = attempt.submitted_key || answerKey(attempt.round, attempt.round === 'recognize' ? attempt.mode : attempt.round, attempt.concept_id);
      const keys = Array.isArray(attempt.submitted_keys) && attempt.submitted_keys.length ? attempt.submitted_keys : [fallbackKey];
      const correction = correctionWithAiReview(attempt);
      keys.forEach((key) => {
        restoredSubmitted[key] = true;
        restoredCorrections[key] = correction;
        restoredAttemptIds[key] = attempt.attempt_id;
        if (['sentence', 'produce', 'speak', 'conversation'].includes(attempt.round)) {
          restoredAnswers[key] = { text: attempt.answer_payload?.text || '' };
        } else {
          restoredAnswers[key] = { ...(attempt.answer_payload?.answers || {}) };
        }
        const confidence = attempt.answer_payload?.confidence || correction?.confidence;
        if (confidence === 'sure' || confidence === 'unsure') {
          restoredConfidence[key] = confidence;
        }
      });
      const retest = repairRetestFromAttempt(attempt, correction);
      if (retest) restoredRetests[retest.id] = retest;
      errataForAttempt(correction, attempt.attempt_id).forEach((item: AtelierErratum) => restoredErrata.unshift(item));
      if (aiReviewStatus(correction) === 'pending') {
        scheduleAiReviewPollingRef.current(attempt.attempt_id, keys[0]);
      }
    });

    const position = next.current_position || {};
    const nextRound = position.round && position.round !== 'complete' ? position.round : 'produce';
    const conceptIndex = typeof position.concept_index === 'number'
      ? position.concept_index
      : Math.max(0, next.concepts.findIndex((concept) => concept.id === position.concept_id));

    setSession(next);
    setAnswers(restoredAnswers);
    setConfidenceByKey(restoredConfidence);
    setSubmitted(restoredSubmitted);
    setCorrectionsByKey(restoredCorrections);
    setAttemptIdsByKey(restoredAttemptIds);
    setRepairDrafts({});
    setRepairRetests(restoredRetests);
    setActiveRetestId(null);
    setErrata(restoredErrata);
    setRecentCorrection((next.attempts || []).slice(-1)[0] ? correctionWithAiReview((next.attempts || []).slice(-1)[0]) : null);
    setRecap(next.status === 'completed' && next.recap ? next.recap : null);
    setActiveConceptIndex(Math.max(0, Math.min(conceptIndex, next.concepts.length - 1)));
    setActiveItemIndex(Math.max(0, Number(position.item_index || 0)));
    setRound(nextRound as RoundName);
    setMode(recognizeModes.some((item) => item.id === position.mode) ? position.mode as RecognizeMode : 'fill');
    if (openSession) {
      setView('session');
    }
  }, []);

  useEffect(() => {
    scheduleAiReviewPollingRef.current = scheduleAiReviewPolling;
  });

  const loadActiveSession = useCallback(async (alive: () => boolean) => {
    try {
      const active = await apiService.getActiveAtelierSession();
      if (!alive()) return;
      if (active.session) {
        hydrateSession(active.session);
      } else {
        setSession(null);
      }
      setActiveSessionReady(true);
      return true;
    } catch (error) {
      console.error(error);
      if (alive()) {
        setActiveSessionReady(false);
        setLoadError(describeAtelierError(error, 'load'));
      }
      return false;
    }
  }, [hydrateSession]);

  useEffect(() => {
    let alive = true;
    const cached = readCachedAtelierEdition<AtelierToday>();
    if (cached) {
      setToday(cached.today);
      setVocabularyDue(cached.vocabularyDue);
      setCachedEditionAt(cached.cachedAt);
      setLoading(false);
    } else {
      setLoading(true);
    }
    setLoadError(null);
    setActiveSessionReady(false);
    Promise.all([
      apiService.getAtelierToday(),
      apiService.getVocabularyDueContext({
        limit: 1,
        due_limit: 1,
        fragile_limit: 0,
        new_limit: 0,
        topic_limit: 0,
        linked_limit: 0,
      }).catch(() => null),
      loadActiveSession(() => alive),
    ])
      .then(([todayData, vocabularyContext]) => {
        if (!alive) return;
        setToday(todayData);
        const due = Number(vocabularyContext?.summary?.due_total ?? vocabularyContext?.summary?.due ?? 0);
        setVocabularyDue(due);
        cacheAtelierEdition(todayData, due);
        setCachedEditionAt(null);
      })
      .catch((error) => {
        console.error(error);
        if (!alive) return;
        setLoadError(describeAtelierError(error, 'load'));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [loadActiveSession, reloadKey]);

  useEffect(() => {
    if (!session || session.status === 'completed') return;
    saveResumeActivity({
      href: `/atelier?resume=${session.session_id}`,
      kind: 'atelier',
      entityId: session.session_id,
    });
    if (router.isReady && router.query.resume) setView('session');
  }, [router.isReady, router.query.resume, session]);

  useEffect(() => {
    return () => {
      Object.values(aiPollTimers.current).forEach((timer) => clearTimeout(timer));
      aiPollTimers.current = {};
    };
  }, []);

  useEffect(() => {
    if (!rewardMoment) return;
    const timer = window.setTimeout(() => setRewardMoment(null), 2600);
    return () => window.clearTimeout(timer);
  }, [rewardMoment]);

  const activeRetest = activeRetestId ? repairRetests[activeRetestId] || null : null;
  const exerciseRound = activeRetest?.round || round;
  const exerciseMode = exerciseRound === 'recognize'
    ? (activeRetest?.mode as RecognizeMode || mode)
    : mode;
  const baseActiveConcept = session?.concepts[exerciseRound === 'produce' ? 0 : activeConceptIndex] || today?.concepts[activeConceptIndex] || null;
  const activeConcept = activeRetest && session
    ? session.concepts.find((concept) => concept.id === activeRetest.conceptId) || baseActiveConcept
    : baseActiveConcept;
  const sessionActiveSet = useMemo(() => {
    if (!session || !activeConcept) return null;
    return session.exercise_sets.find((set) => set.concept_id === activeConcept.id)?.payload || null;
  }, [session, activeConcept]);
  const baseActiveItems = useMemo(() => drillItems(sessionActiveSet, round, mode), [sessionActiveSet, round, mode]);
  const baseActiveItemIndexSafe = safeDrillItemIndex(activeItemIndex, baseActiveItems);
  const activeSet = activeRetest ? exerciseSetForRetest(activeRetest) : sessionActiveSet;
  const activeItems = useMemo(() => drillItems(activeSet, exerciseRound, exerciseMode), [activeSet, exerciseRound, exerciseMode]);
  const activeItemIndexSafe = activeRetest ? 0 : baseActiveItemIndexSafe;
  const activeItem = activeItems[activeItemIndexSafe] || null;
  const activeAnswerItemId = roundUsesItemScope(exerciseRound) ? itemIdForKey(activeItem, activeItemIndexSafe) || null : null;
  const activeItemId = activeRetest
    ? `retest:${activeRetest.id}`
    : activeAnswerItemId;
  const scopedMode = roundMode(exerciseRound, exerciseMode);
  const scopedKey = answerKey(exerciseRound, scopedMode, roundUsesSessionScope(exerciseRound) ? null : activeConcept?.id, activeItemId);
  const currentAnswers = answers[scopedKey] || {};
  const produceAnswer = exerciseRound === 'produce'
    ? currentAnswers.text || ''
    : answers[answerKey('produce', 'produce', null)]?.text || '';
  const currentAttemptReady = drillAnswerIsReady(activeSet, exerciseRound, exerciseMode, activeItemIndexSafe, currentAnswers, produceAnswer);
  const adaptiveLocks = useMemo(() => sessionAdaptiveLocks(session), [session]);
  const dayProgress = useMemo(
    () => buildDayProgress({
      today,
      session,
      vocabularyDue,
    }),
    [today, session, vocabularyDue],
  );
  // --- Atelier V2 daily journey -------------------------------------------
  // The controller owns every journey request, idempotency key and contract
  // state; this page only renders it. It stays idle until the legacy edition
  // has loaded, so an unauthenticated visit never fires a journey request.
  const journey = useDailyJourney({ enabled: !loading && !loadError });
  // The server response is the only authority. A failed or absent `/today`
  // read is NOT an enabled capability, so the legacy page is untouched when the
  // flag is off, when the request fails, and before the first read returns.
  const journeyEnabled =
    journey.envelope?.enabled === true && journey.phase.kind !== 'disabled';

  // The frozen precedence: the journey branch sits in front of the legacy chain.
  const recommendation = useMemo(
    () => resolveRecommendedNext(today, session, dayProgress, journey.envelope),
    [today, session, dayProgress, journey.envelope],
  );
  // The legacy surfaces (La Une, the session recap) keep receiving the legacy
  // chain verbatim. The journey has its own entry above them, so nothing here is
  // reorganized during the functional milestone and no legacy copy has to learn
  // a new action kind. Whichever the learner picks, the other stays available.
  const legacyRecommendation = useMemo(
    () => resolveLegacyRecommendedNext(today, session, dayProgress),
    [today, session, dayProgress],
  );
  // --- WP-16 / decision D-0: «Plus de pratique» ---------------------------
  // The legacy exercise Séance is no longer "today". It is the drill loop, and
  // a drill loop is entered by a grammar concept or by the errata queue:
  // `/atelier?mode=practice&concept=<id>` (or `&queue=errata`). The historical
  // `?concept_id=` deep link from the Cahier fiche keeps working unchanged.
  const practiceMode = router.isReady && String(router.query.mode || '') === 'practice';
  const practiceQueue = String(router.query.queue || '');
  const practiceConceptId = (() => {
    const raw = router.query.concept ?? router.query.concept_id;
    const value = Number(Array.isArray(raw) ? raw[0] : raw);
    return Number.isFinite(value) && value > 0 ? value : null;
  })();
  // The concept's own title, for the practice header. Read from the server's
  // payload only — an unknown id prints no title rather than an invented one.
  const practiceConceptTitle = (() => {
    if (!practiceConceptId) return null;
    const pool = [...(session?.concepts || []), ...(today?.concepts || [])];
    const found = pool.find((concept) => Number(concept.id) === practiceConceptId);
    return found ? displayConceptTitle(found) : null;
  })();
  // The secondary line Home shows under the Séance tile. `null` with the
  // capability off, so a flag-off Home is untouched.
  const practiceEntry = useMemo(() => resolvePracticeEntry(journey.envelope), [journey.envelope]);

  const journeyRecommended = recommendation.kind.startsWith('journey_');
  // The Today entry for the journey is on screen exactly when the frozen
  // precedence puts it in front of the legacy chain, plus the finished case.
  // Nothing may be rendered on top of it: it carries the day's primary action.
  const journeyEntryVisible =
    journeyEnabled && (journeyRecommended || journey.phase.kind === 'finished');

  useEffect(() => {
    if (!activeRetest && activeItemIndex !== activeItemIndexSafe) {
      setActiveItemIndex(activeItemIndexSafe);
    }
  }, [activeItemIndex, activeItemIndexSafe, activeRetest]);

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
      toast('Relecture automatique lancée.');
    } catch (error) {
      console.error(error);
      toast.error('La relecture automatique est indisponible.');
    } finally {
      setAiReviewSubmitting((prev) => ({ ...prev, [scopedKey]: false }));
    }
  };

  const reportCurrentExercise = async () => {
    if (!session) return;
    const reportMode = round === 'recognize' ? mode : round === 'transform' ? 'transform' : round;
    const exerciseId = scopedExerciseId(activeConcept, round, mode, activeItemId);
    const exerciseSet = activeConcept
      ? session.exercise_sets.find((set) => set.concept_id === activeConcept.id)
      : null;
    try {
      await apiService.reportAtelierExercise({
        session_id: session.session_id,
        concept_id: round === 'produce' ? null : activeConcept?.id,
        exercise_set_id: exerciseSet?.id || null,
        round,
        mode: reportMode,
        exercise_id: exerciseId,
        item_id: activeItemId,
        reason: 'Exercice signalé depuis la feuille de correction.',
      });
      toast.success('Exercice signalé.');
    } catch (error) {
      console.error(error);
      toast.error('L’exercice n’a pas pu être signalé.');
    }
  };

  const updateAnswer = (
    key: string,
    value: any,
    scopedRound: RoundName = round,
    scopedModeValue: string = roundMode(round, mode),
    conceptId: number | null | undefined = roundUsesSessionScope(round) ? null : activeConcept?.id,
    itemId: string | null | undefined = roundUsesItemScope(scopedRound) ? activeItemId : null,
  ) => {
    const keyScope = answerKey(scopedRound, scopedModeValue, conceptId, itemId);
    setAnswers((prev) => ({
      ...prev,
      [keyScope]: {
        ...(prev[keyScope] || {}),
        [key]: value,
      },
    }));
  };

  const startSession = async () => {
    if (!activeSessionReady) {
      setLoadError(ATELIER_CONFIRM_NEEDED_NOTICE);
      return;
    }
    setSubmitting(true);
    setLoadError(null);
    try {
      // WP-16: `?concept=` is the practice-mode spelling; `?concept_id=` is the
      // Cahier fiche's historical one. Both seat the same concept.
      const rawConcept = router.query.concept ?? router.query.concept_id;
      const conceptId = Number(Array.isArray(rawConcept) ? rawConcept[0] : rawConcept);
      const next = await apiService.startAtelierSession(
        Number.isFinite(conceptId) && conceptId > 0 ? { preferred_concept_id: conceptId } : undefined
      );
      setActiveSessionReady(true);
      hydrateSession(next, true);
    } catch (error) {
      console.error(error);
      setLoadError(describeAtelierError(error, 'session'));
    } finally {
      setSubmitting(false);
    }
  };

  const submitAttempt = async () => {
    if (!session) return;
    if (submitted[scopedKey]) {
      toast('Cet exercice est déjà classé.');
      return;
    }
    if (!currentAttemptReady) {
      toast('Ajoutez une réponse avant de vérifier.');
      return;
    }
    setSubmitting(true);
    try {
      let result: AtelierAttemptResult;
      const attemptKey = scopedKey;
      const resubmit = !!resubmitKeys[attemptKey];
      const confidence = confidenceByKey[attemptKey];
      const retestSourceAttemptId = activeRetest?.sourceAttemptId || null;
      if (exerciseRound === 'recognize') {
        const itemAnswers = activeAnswerItemId ? { [activeAnswerItemId]: currentAnswers[activeAnswerItemId] ?? '' } : currentAnswers;
        result = await apiService.submitAtelierAttempt(session.session_id, {
          concept_id: activeConcept?.id,
          round: exerciseRound,
          mode: exerciseMode,
          exercise_id: activeRetest
            ? `${activeRetest.exerciseId}:retest:${activeRetest.id}`
            : scopedExerciseId(activeConcept, exerciseRound, exerciseMode, activeAnswerItemId),
          answer_payload: { answers: itemAnswers },
          confidence,
          retest_source_attempt_id: retestSourceAttemptId,
          resubmit,
        });
      } else if (exerciseRound === 'transform') {
        const itemAnswers = activeAnswerItemId ? { [activeAnswerItemId]: currentAnswers[activeAnswerItemId] ?? '' } : currentAnswers;
        result = await apiService.submitAtelierAttempt(session.session_id, {
          concept_id: activeConcept?.id,
          round: exerciseRound,
          mode: 'rewrite',
          exercise_id: activeRetest
            ? `${activeRetest.exerciseId}:retest:${activeRetest.id}`
            : scopedExerciseId(activeConcept, exerciseRound, exerciseMode, activeAnswerItemId),
          answer_payload: { answers: itemAnswers },
          confidence,
          retest_source_attempt_id: retestSourceAttemptId,
          resubmit,
        });
      } else if (exerciseRound === 'sentence' || exerciseRound === 'speak' || exerciseRound === 'conversation') {
        result = await apiService.submitAtelierAttempt(session.session_id, {
          concept_id: activeConcept?.id,
          round: exerciseRound,
          mode: exerciseRound,
          exercise_id: activeRetest
            ? `${activeRetest.exerciseId}:retest:${activeRetest.id}`
            : `${activeConcept?.external_id || activeConcept?.id}:${exerciseRound}`,
          answer_payload: { text: currentAnswers.text || '' },
          confidence,
          retest_source_attempt_id: retestSourceAttemptId,
          resubmit,
        });
      } else {
        result = await apiService.submitAtelierAttempt(session.session_id, {
          concept_id: null,
          round: exerciseRound,
          mode: 'integrated_writing',
          exercise_id: activeRetest ? `${activeRetest.exerciseId}:retest:${activeRetest.id}` : 'integrated-writing',
          answer_payload: { text: currentAnswers.text || '' },
          confidence,
          retest_source_attempt_id: retestSourceAttemptId,
          resubmit,
        });
      }
      applyAttemptResult(attemptKey, result);
      setSubmitted((prev) => ({ ...prev, [attemptKey]: true }));
      setResubmitKeys((prev) => ({ ...prev, [attemptKey]: false }));
      const adaptiveLock = result.correction?.adaptive_lock;
      if (adaptiveLock?.concept_id) {
        const lockedConceptId = Number(adaptiveLock.concept_id);
        const skippedModes: string[] = Array.isArray(adaptiveLock.skipped_modes) ? adaptiveLock.skipped_modes : [];
        const skippedRounds: string[] = Array.isArray(adaptiveLock.skipped_rounds) ? adaptiveLock.skipped_rounds : [];
        setSubmitted((prev) => ({
          ...prev,
          ...Object.fromEntries(skippedModes.map((skippedMode) => [
            answerKey('recognize', skippedMode, lockedConceptId),
            true,
          ])),
          ...Object.fromEntries(skippedRounds.map((skippedRound) => [
            answerKey(skippedRound as RoundName, skippedRound, lockedConceptId),
            true,
          ])),
        }));
        setSession((prev) => prev ? {
          ...prev,
          learning_moments: {
            ...(prev.learning_moments || {}),
            adaptive_locks: {
              ...(prev.learning_moments?.adaptive_locks || {}),
              [String(adaptiveLock.concept_id)]: adaptiveLock,
            },
          },
        } : prev);
      }
      if (activeRetest) {
        setRepairRetests((prev) => ({ ...prev, [activeRetest.id]: { ...activeRetest, status: 'completed' } }));
      }
      const mintedLogoToken = firstMintedCollectible(result.minted_collectibles, 'logo_token');
      if (mintedLogoToken) {
        setRewardMoment({ id: `${mintedLogoToken.id}:${Date.now()}`, kind: 'logo_token', collectible: mintedLogoToken });
        pulseAtelierHaptic('token');
        toast.success('Jeton du logo gagné.');
      } else {
        pulseAtelierHaptic(result.verdict === 'correct' ? 'correct' : 'repair');
      }
    } catch (error) {
      console.error(error);
      toast.error('La correction n’a pas pu être transmise.');
    } finally {
      setSubmitting(false);
    }
  };

  const retryCurrentAttempt = () => {
    setSubmitted((prev) => ({ ...prev, [scopedKey]: false }));
    setResubmitKeys((prev) => ({ ...prev, [scopedKey]: true }));
    setRecentCorrection(null);
  };

  const submitMicroRepair = async (erratumIndex: number) => {
    const attemptId = attemptIdsByKey[scopedKey];
    const draftKey = `${scopedKey}:${erratumIndex}`;
    const text = repairDrafts[draftKey] || '';
    if (!attemptId || !text.trim() || repairSubmitting[draftKey]) return;
    setRepairSubmitting((prev) => ({ ...prev, [draftKey]: true }));
    try {
      const result = await apiService.repairAtelierAttempt(attemptId, { text, erratum_index: erratumIndex });
      const correction = applyAttemptResult(scopedKey, result, true, false);
      const rawRetest = correction?.retest;
      if (rawRetest?.id) {
        const retest: RepairRetest = {
          id: String(rawRetest.id),
          status: rawRetest.status === 'completed' ? 'completed' : 'queued',
          sourceAttemptId: attemptId,
          conceptId: activeConcept?.id ?? null,
          round: exerciseRound,
          mode: exerciseRound === 'recognize' ? exerciseMode : exerciseRound === 'transform' ? 'rewrite' : exerciseRound,
          exerciseId: activeRetest?.exerciseId || scopedExerciseId(activeConcept, exerciseRound, exerciseMode, activeAnswerItemId),
          dueAfterCompleted: Math.max(1, Number(rawRetest.due_after_completed || 1)),
          promptPayload: scopedPromptPayload(activeSet, exerciseRound, exerciseMode, activeItem),
        };
        setRepairRetests((prev) => ({ ...prev, [retest.id]: retest }));
      }
      pulseAtelierHaptic(correction?.micro_repairs?.[String(erratumIndex)]?.status === 'ok' ? 'correct' : 'repair');
    } catch (error) {
      console.error(error);
      toast.error('La correction n’a pas pu être vérifiée.');
    } finally {
      setRepairSubmitting((prev) => ({ ...prev, [draftKey]: false }));
    }
  };

  const completeSession = async () => {
    if (!session) return;
    setSubmitting(true);
    try {
      const result = await apiService.completeAtelierSession(session.session_id);
      const recapPayload = { ...result.recap, session_id: result.session_id, minted_collectibles: result.minted_collectibles || [] };
      setRecap(recapPayload);
      setSession((prev) => prev ? { ...prev, status: 'completed', recap: recapPayload } : prev);
      clearResumeActivity('atelier');
      try {
        const [todayData, vocabularyContext] = await Promise.all([
          apiService.getAtelierToday(),
          apiService.getVocabularyDueContext({
            limit: 1,
            due_limit: 1,
            fragile_limit: 0,
            new_limit: 0,
            topic_limit: 0,
            linked_limit: 0,
          }).catch(() => null),
        ]);
        setToday(todayData);
        setVocabularyDue(Number(vocabularyContext?.summary?.due_total ?? vocabularyContext?.summary?.due ?? 0));
      } catch (refreshError) {
        console.error(refreshError);
      }
      const mintedGiltSeal = firstMintedCollectible(result.minted_collectibles, 'gilt_seal');
      if (mintedGiltSeal) {
        setRewardMoment({ id: `${mintedGiltSeal.id}:${Date.now()}`, kind: 'gilt_seal', collectible: mintedGiltSeal });
      }
      pulseAtelierHaptic('complete');
      if (
        nativePushIsAvailable()
        && window.localStorage.getItem('pilot:native-push-prompted:v1') !== 'true'
      ) {
        window.localStorage.setItem('pilot:native-push-prompted:v1', 'true');
        try {
          const token = await registerNativePushToken();
          await apiService.subscribeToNativeNotifications(token);
          toast.success("L’édition de demain pourra vous prévenir.");
        } catch (pushError) {
          console.info('Native push was not enabled after the first session.', pushError);
        }
      }
    } catch (error) {
      console.error(error);
      toast.error('La séance n’a pas pu être terminée.');
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
      toast.error('Cette correction n’a pas pu être ouverte.');
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
        toast.success('Erratum repris');
      } else {
        toast('Relue. Elle reviendra bientôt pour une nouvelle reprise.');
      }
    } catch (error) {
      console.error(error);
      toast.error('La correction n’a pas pu être envoyée.');
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
    toast('La file de révision est vide.');
  };

  // --- WP-20 (WP-19 defect D-1): land inside the journey, not on Home -------
  // `/atelier?view=journey` is the destination `lib/journey-resume.ts` hands to
  // the cold-start redirect in `_app.tsx` while a journey for today is still
  // open. It is a *view* switch, never a start: if the flag is off, or the
  // server sent no open journey, the parameter does nothing and Home renders
  // exactly as it did before.
  const journeyViewEnteredRef = useRef(false);
  useEffect(() => {
    if (!router.isReady || journeyViewEnteredRef.current) return;
    if (String(router.query.view || '') !== 'journey') return;
    if (!journeyEnabled) return;
    journeyViewEnteredRef.current = true;
    setView('journey');
  }, [router.isReady, router.query.view, journeyEnabled]);

  // --- WP-16 / D-0: enter the drill loop from a concept or the errata queue --
  // `/atelier?mode=practice&concept=<id>` starts the legacy exercise Séance on
  // that concept; `&queue=errata` opens the errata review instead. Neither is
  // ever the day's primary action: this only runs when the learner followed a
  // «Plus de pratique» link. The guard fires once per landing, so a re-render
  // (or a failed start) cannot loop on the paid start endpoint.
  const practiceEnteredRef = useRef(false);
  useEffect(() => {
    if (!practiceMode || loading) return;
    if (practiceEnteredRef.current) return;
    if (practiceQueue === 'errata') {
      practiceEnteredRef.current = true;
      openRecommendedReview();
      return;
    }
    if (session && session.status !== 'completed') {
      practiceEnteredRef.current = true;
      setView('session');
      return;
    }
    if (!session && activeSessionReady) {
      practiceEnteredRef.current = true;
      void startSession();
    }
    // `startSession` and `openRecommendedReview` are re-created every render;
    // listing them would re-run this effect continuously. The `practiceEnteredRef`
    // guard is what makes the entry happen exactly once, not the dependency list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [practiceMode, practiceQueue, loading, session, activeSessionReady]);

  const handleRecommendedAction = (action: RecommendedAction = recommendation) => {
    // --- Atelier V2 branches, in the frozen precedence order ----------------
    if (action.kind === 'journey_resume') {
      // Resume, never restart. `resume` is an accepted no-op on an already
      // active journey, so this is safe to tap twice.
      if (action.status === 'paused') void journey.actions.resume();
      setView('journey');
      return;
    }
    if (action.kind === 'journey_start') {
      void journey.actions.start().then(() => setView('journey'));
      return;
    }
    if (action.kind === 'journey_preparing') {
      // Never start a second journey: re-read the one the server is preparing.
      void journey.actions.refresh();
      setView('journey');
      return;
    }
    if (action.kind === 'journey_unavailable') {
      // Offer the retry, then let the rest of the day carry on underneath.
      if (action.retryAllowed) void journey.actions.retryGeneration();
      else handleRecommendedAction(action.fallback);
      return;
    }

    if (action.kind === 'resume_session') {
      if (session) {
        const nextRound = isRoundName(action.round) ? action.round : 'recognize';
        const nextConceptIndex = Math.max(0, Math.min(action.conceptIndex || 0, session.concepts.length - 1));
        setRound(nextRound);
        setActiveConceptIndex(nextConceptIndex);
        if (nextRound === 'recognize' && recognizeModes.some((item) => item.id === action.mode)) {
          setMode(action.mode as RecognizeMode);
        }
        setActiveItemIndex(Math.max(0, Number(action.itemIndex ?? 0)));
      }
      setView('session');
      return;
    }
    if (action.kind === 'start_session') {
      if (!activeSessionReady) {
        setLoadError(ATELIER_CONFIRM_NEEDED_NOTICE);
        return;
      }
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
    if (action.kind === 'studio') {
      void router.push('/audio-session');
      return;
    }
    if (action.kind === 'library') {
      if (!STORY_FEATURE_VISIBLE) return;
      void router.push(action.href);
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

  // Where the recognition rung resumes for a concept, skipping every mode the
  // learner has already earned out of. Returns null when the whole rung is done.
  const firstOpenRecognizeMode = (conceptId?: number | null): RecognizeMode | null => {
    const skipped = lockedRecognizeModes(adaptiveLocks, conceptId);
    return recognizeModes.find((item) => !skipped.has(item.id))?.id || null;
  };

  const enterTransformRung = (fromIndex: number) => {
    if (!session) return;
    const nextIndex = session.concepts
      .findIndex((concept, index) => index >= fromIndex && !roundIsLocked(adaptiveLocks, concept.id, 'transform'));
    if (nextIndex >= 0) {
      setRound('transform');
      setActiveConceptIndex(nextIndex);
      setActiveItemIndex(0);
      return;
    }
    setRound('sentence');
    setActiveConceptIndex(0);
    setActiveItemIndex(0);
  };

  const advanceBaseDrill = () => {
    if (!session) return;
    if (roundUsesItemScope(round) && baseActiveItemIndexSafe < Math.max(baseActiveItems.length - 1, 0)) {
      // An item-level lock earned on this very answer (e.g. two clean
      // transforms) retires the rest of the rung instead of marching on.
      if (!roundIsLocked(adaptiveLocks, activeConcept?.id, round)) {
        setActiveItemIndex(baseActiveItemIndexSafe + 1);
        return;
      }
    }
    if (round === 'recognize') {
      const modeIndex = recognizeModes.findIndex((item) => item.id === mode);
      const skipped = lockedRecognizeModes(adaptiveLocks, activeConcept?.id);
      const nextMode = recognizeModes.slice(modeIndex + 1).find((item) => !skipped.has(item.id));
      if (nextMode) {
        setMode(nextMode.id);
        setActiveItemIndex(0);
        return;
      }
      for (let index = activeConceptIndex + 1; index < session.concepts.length; index += 1) {
        const openMode = firstOpenRecognizeMode(session.concepts[index].id);
        if (openMode) {
          setActiveConceptIndex(index);
          setMode(openMode);
          setActiveItemIndex(0);
          return;
        }
      }
      enterTransformRung(0);
      return;
    }
    if (round === 'transform') {
      const nextIndex = session.concepts.findIndex((concept, index) => (
        index > activeConceptIndex && !roundIsLocked(adaptiveLocks, concept.id, 'transform')
      ));
      if (nextIndex >= 0) {
        setActiveConceptIndex(nextIndex);
        setActiveItemIndex(0);
        return;
      }
      setRound('sentence');
      setActiveConceptIndex(0);
      setActiveItemIndex(0);
      return;
    }
    if (round === 'sentence') {
      if (activeConceptIndex < session.concepts.length - 1) {
        setActiveConceptIndex(activeConceptIndex + 1);
        setActiveItemIndex(0);
        return;
      }
      setRound('produce');
      setActiveConceptIndex(0);
      setActiveItemIndex(0);
      return;
    }
    if (round === 'produce') {
      setRound('speak');
      setActiveConceptIndex(0);
      setActiveItemIndex(0);
      return;
    }
    if (round === 'speak') {
      if (activeConceptIndex < session.concepts.length - 1) {
        setActiveConceptIndex(activeConceptIndex + 1);
        setActiveItemIndex(0);
        return;
      }
      setRound('conversation');
      setActiveConceptIndex(0);
      setActiveItemIndex(0);
      return;
    }
    if (round === 'conversation' && activeConceptIndex < session.concepts.length - 1) {
      setActiveConceptIndex(activeConceptIndex + 1);
      setActiveItemIndex(0);
    }
  };

  const goNext = () => {
    if (!session) return;
    if (activeRetest) {
      setActiveRetestId(null);
      advanceBaseDrill();
      return;
    }
    const baselineCompleted = submittedDrills(session, submitted, adaptiveLocks);
    // The server schedules a retest a couple of drills out; clamp it to the end
    // of the ladder so one that was booked past the last drill still gets asked
    // instead of sitting queued forever (and padding the denominator, which then
    // filed a finished edition as "close en avance").
    const dueRetest = Object.values(repairRetests).find((retest) => (
      retest.status === 'queued'
      && baselineCompleted >= Math.min(retest.dueAfterCompleted, totalDrills(session, adaptiveLocks, submitted))
    ));
    if (dueRetest) {
      setActiveRetestId(dueRetest.id);
      return;
    }
    advanceBaseDrill();
  };

  const completedRetests = Object.values(repairRetests).filter((retest) => retest.status === 'completed').length;
  const totalRetests = Object.keys(repairRetests).length;
  const completedDrills = submittedDrills(session, submitted, adaptiveLocks) + completedRetests;
  const baseDrills = totalDrills(session, adaptiveLocks, submitted);
  const plannedDrills = baseDrills + totalRetests;
  // The feuilleton welcome is onboarding for the serial, and its call to action
  // starts a legacy grammar session. When the daily journey owns Today it must
  // not render at all: a fixed overlay in front of the day's recommended action
  // makes that action unclickable, and its one button leads somewhere else.
  const showSerialWelcome = !loading
    && !serialWelcomeDismissed
    && today?.onboarding?.serial_seen === false
    && !session
    && !journeyEntryVisible
    // The capability read decides who owns Today. Until it settles, showing the
    // welcome would flash a full-screen overlay in front of an action that is
    // about to appear underneath it.
    && journey.phase.kind !== 'loading'
    && dayProgress.sessionStatus === 'none';
  const dismissSerialWelcome = async () => {
    setSerialWelcomeDismissed(true);
    try {
      await apiService.markSerialOnboardingSeen();
      setToday((current) => current ? {
        ...current,
        onboarding: {
          ...(current.onboarding || {}),
          serial_seen: true,
        },
      } : current);
    } catch (error) {
      console.error(error);
    }
  };
  // The modal's own button reads "Start today" -- it should be the one true
  // start action, not a first tap that only dismisses a modal in front of a
  // second, identically-labelled button underneath.
  const beginFromSerialWelcome = async () => {
    await dismissSerialWelcome();
    void startSession();
  };

  return (
    <>
      <Head>
        <title>L’Atelier</title>
      </Head>
      <AtelierStyles />
      <div className="atelier-page">
        <Masthead view={view === 'today' ? 'today' : 'session'} />
        {cachedEditionAt && (
          <div className="atelier-cache-note" role="status">
            Édition précédente · mise à jour en cours…
          </div>
        )}
        {loading ? (
          <HomeSkeleton>
            <AtelierEditionNav active="atelier" />
          </HomeSkeleton>
        ) : view === 'journey' && journeyEnabled ? (
          // One connected shell: scene, recall, response, resolution and the
          // recap all live here, so finishing the day needs no second screen.
          <JourneySession
            controller={journey}
            onExit={() => {
              setView('today');
              void journey.actions.refresh();
            }}
            // WP-16 / D-0: the recap points into the drill loop for what this
            // scene practised. It navigates to the server's own practice href;
            // it never reopens the finished journey.
            morePractice={practiceEntry ? {
              label: PRACTICE_LABEL,
              onSelect: () => { void router.push(practiceEntry.href); },
            } : null}
            onPractice={(href) => { void router.push(href); }}
          />
        ) : /* A capability that turns off mid-session falls back to Today, never
               into the legacy exercise view the learner did not ask for. */
        view === 'today' || view === 'journey' || !session ? (
          <>
            {/* The journey entry appears exactly when the frozen precedence puts
                it in front of the legacy chain (branches 1–3 and 5), plus the
                finished case, where branch 4 makes re-entry a read. */}
            {journeyEntryVisible && (
              <div
                className="atelier-journey-entry"
                style={{ maxWidth: 720, margin: '0 auto', padding: '16px 16px 0', width: '100%' }}
              >
                <JourneyTodayCard
                  controller={journey}
                  onOpen={() => setView('journey')}
                  onOpenLegacy={(href) => {
                    // The old Atelier session is resumed on its own terms: the
                    // journey never converts, replaces or completes it.
                    void router.push(href);
                  }}
                />
              </div>
            )}
            <TodayView
              today={today}
              activeSession={session}
              dayProgress={dayProgress}
              recommendation={legacyRecommendation}
              onRecommendedAction={handleRecommendedAction}
              onOpenReview={() => openRecommendedReview()}
              loading={submitting}
              loadError={loadError}
              activeSessionReady={activeSessionReady}
              onRetry={() => setReloadKey((key) => key + 1)}
              // WP-16 / D-0: `null` unless the daily journey owns the day, so a
              // flag-off Home renders byte-for-byte what it rendered before.
              practiceEntry={practiceEntry}
            />
          </>
        ) : (
          <>
            {/* WP-16 / D-0: the drill loop says what it is. The legacy Séance
                is «Plus de pratique» now, keyed by the concept the learner
                chose; the strip sits above SessionView rather than inside it,
                so no SessionView internal changes. */}
            {practiceMode && (
              <div className="atelier-practice-strip av2" role="status">
                <p className="av2-label">{PRACTICE_LABEL}</p>
                {practiceConceptTitle && (
                  <p className="av2-headline av2-headline--rule" lang="fr">
                    {practiceConceptTitle}
                  </p>
                )}
              </div>
            )}
          <SessionView
            session={session}
            activeConceptIndex={activeConceptIndex}
            activeItemIndex={activeItemIndexSafe}
            activeItemCount={Math.max(activeItems.length, 1)}
            round={exerciseRound}
            mode={exerciseMode}
            activeSet={activeSet}
            activeConcept={activeConcept}
            activeItemId={activeItemId}
            currentAnswers={currentAnswers}
            updateAnswer={(key, value) => updateAnswer(
              key,
              value,
              exerciseRound,
              scopedMode,
              roundUsesSessionScope(exerciseRound) ? null : activeConcept?.id,
              activeItemId,
            )}
            submitAttempt={submitAttempt}
            completeSession={completeSession}
            submitting={submitting}
            submitted={submitted}
            correctionsByKey={correctionsByKey}
            goNext={goNext}
            retryAttempt={retryCurrentAttempt}
            requestAiReview={requestAiReview}
            reportExercise={reportCurrentExercise}
            aiReviewSubmitting={!!aiReviewSubmitting[scopedKey]}
            completedDrills={completedDrills}
            totalDrills={plannedDrills}
            confidence={confidenceByKey[scopedKey]}
            onPickConfidence={(confidence) => setConfidenceByKey((prev) => ({ ...prev, [scopedKey]: confidence }))}
            repairDrafts={repairDrafts}
            onSetRepairDraft={(key, value) => setRepairDrafts((prev) => ({ ...prev, [key]: value }))}
            onSubmitRepair={submitMicroRepair}
            repairSubmitting={repairSubmitting}
            isRetest={Boolean(activeRetest)}
            onBack={() => setView('today')}
            produceAnswer={produceAnswer}
          />
          </>
        )}
        {recap && (
          <RecapModal
            recap={recap}
            concepts={session?.concepts || []}
            filedEarly={completedDrills < plannedDrills}
            recommendation={legacyRecommendation}
            onRecommendedAction={() => {
              setRecap(null);
              setView('today');
              handleRecommendedAction(legacyRecommendation);
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
        {rewardMoment && (
          <RewardMomentOverlay
            moment={rewardMoment}
            onClose={() => setRewardMoment(null)}
          />
        )}
        {showSerialWelcome && (
          <SerialWelcomeModal
            onBegin={beginFromSerialWelcome}
            onDismiss={() => { void dismissSerialWelcome(); }}
          />
        )}
      </div>
    </>
  );
}

function RewardMomentOverlay({
  moment,
  onClose,
}: {
  moment: RewardMoment;
  onClose: () => void;
}) {
  const isLogoToken = moment.kind === 'logo_token';
  const isDrafting = isLogoToken && moment.collectible?.metadata?.effort === 'drafting';
  const credit = Number(moment.collectible?.metadata?.credit || 0);
  const eyebrow = isLogoToken
    ? (isDrafting ? 'Composé de toutes pièces' : 'Écran parfait')
    : 'Édition sans faute';
  const title = isLogoToken
    ? (isDrafting ? 'Jeton bonus gagné' : 'Jeton du logo gagné')
    : 'Sceau doré gagné';
  const body = isLogoToken
    ? (isDrafting
        ? 'Vous avez produit la forme visée avec vos propres mots : ce travail plus exigeant reçoit un crédit supplémentaire.'
        : 'Les trois formes ont rejoint la marque de la maison. Elles sont classées dans votre Almanach.')
    : 'Aucune coquille sur ce tirage. Le sceau du jour a été frappé en doré.';
  return (
    <div className="reward-moment-layer" role="status" aria-live="polite">
      <Confetti count={isLogoToken ? (isDrafting ? 30 : 24) : 30} />
      <section className={cn('reward-moment-card', isDrafting && 'drafting')} aria-label={title}>
        {isLogoToken ? (
          <LogoToken pop />
        ) : (
          <Seal
            stamp
            tone="gilt"
            variant={(moment.collectible?.metadata?.seal_variant as SealVariant) || 'row'}
            date={String(moment.collectible?.metadata?.date || '')}
          />
        )}
        <div>
          <span>{eyebrow}</span>
          <h2>{title}</h2>
          {isDrafting && credit > 0 && <p className="reward-credit-line">+{credit} crédit</p>}
          <p>{body}</p>
        </div>
        <button type="button" onClick={onClose}>
          Continuer <ArrowRight size={14} />
        </button>
      </section>
    </div>
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

/**
 * The feuilleton welcome. It is a real modal dialog, so it has to behave like
 * one: it must be dismissible without committing the learner to anything, it
 * must move focus in and hand it back, and Tab must not walk out of it into the
 * page it is covering.
 *
 * It never renders while the daily journey owns Today (see `journeyEntryVisible`),
 * because a fixed overlay in front of the day's recommended action makes that
 * action unclickable.
 */
function SerialWelcomeModal({
  onBegin,
  onDismiss,
}: {
  /** Accept the invitation: dismiss and start today's legacy session. */
  onBegin: () => void;
  /** Close without starting anything. */
  onDismiss: () => void;
}) {
  const dialogRef = useRef<HTMLElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  // The dismiss handler is read through a ref so the focus/keyboard effect
  // never re-runs (and never steals focus back) when the parent re-renders.
  const dismissRef = useRef(onDismiss);
  dismissRef.current = onDismiss;

  const focusable = () => {
    const root = dialogRef.current;
    if (!root) return [] as HTMLElement[];
    return Array.from(
      root.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])'),
    ).filter((el) => el.offsetParent !== null || el === document.activeElement);
  };

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    // Focus the close control first: the escape from the dialog is the first
    // thing the learner can reach, not the commitment.
    closeRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        dismissRef.current();
        return;
      }
      if (event.key !== 'Tab') return;
      const items = focusable();
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (event.shiftKey && (active === first || !dialogRef.current?.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown, true);
    return () => {
      document.removeEventListener('keydown', onKeyDown, true);
      // Hand focus back where it was, so closing the dialog does not dump the
      // learner at the top of the document.
      if (previouslyFocused && document.contains(previouslyFocused)) previouslyFocused.focus();
    };
  }, []);

  return (
    <div
      className="serial-welcome-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        // Only a press that both starts and ends on the backdrop closes it, so
        // a drag that finishes outside the card never dismisses by accident.
        if (event.target === event.currentTarget) onDismiss();
      }}
    >
      <section
        className="serial-welcome"
        role="dialog"
        aria-modal="true"
        aria-labelledby="serial-welcome-title"
        ref={(node) => { dialogRef.current = node; }}
      >
        <div className="serial-welcome-head">
          <div className="t-mono red">Le Feuilleton</div>
          <button
            type="button"
            className="serial-welcome-close"
            aria-label="Fermer"
            ref={closeRef}
            onClick={onDismiss}
          >
            <X size={18} />
          </button>
        </div>
        <h2 id="serial-welcome-title">Votre feuilleton français quotidien commence ici.</h2>
        <p>Chaque jour porte un acte : parfois vous écrivez le message qui change la scène, parfois vous lisez sa conséquence illustrée.</p>
        <div className="serial-welcome-steps">
          <span><b>1</b> Agir en français</span>
          <span><b>2</b> Lire l’édition</span>
          <span><b>3</b> Revenir demain</span>
        </div>
        <button type="button" onClick={onBegin}>
          Commencer aujourd’hui <ArrowRight size={16} />
        </button>
        <button type="button" className="serial-welcome-later" onClick={onDismiss}>
          Plus tard
        </button>
      </section>
    </div>
  );
}

function TodayView({
  today,
  activeSession,
  dayProgress,
  recommendation,
  onRecommendedAction,
  onOpenReview,
  loading,
  loadError,
  activeSessionReady,
  onRetry,
  practiceEntry,
}: {
  today: AtelierToday | null;
  activeSession: AtelierSessionStart | null;
  dayProgress: DayProgress;
  recommendation: RecommendedAction;
  onRecommendedAction: (action?: RecommendedAction) => void;
  onOpenReview: () => void;
  loading: boolean;
  loadError: AtelierErrorNotice | null;
  activeSessionReady: boolean;
  onRetry: () => void;
  /**
   * WP-16 / decision D-0. Non-null only when the daily journey is enabled and
   * owns the day: the Séance tile then carries «Plus de pratique» as a quiet
   * secondary line instead of being the day's primary action.
   */
  practiceEntry?: { label: string; href: string; conceptId: string | null } | null;
}) {
  const router = useRouter();
  const hasActiveSession = dayProgress.sessionStatus === 'active';
  const concepts = activeSession?.concepts?.length ? activeSession.concepts : today?.concepts || [];
  const canStart = activeSessionReady && (hasActiveSession || concepts.length > 0);
  const [wordSlate, setWordSlate] = useState<DailyWordSlate | null>(null);
  useEffect(() => {
    let alive = true;
    apiService.getWordsOfTheDay()
      .then((slate) => { if (alive) setWordSlate(slate); })
      .catch(() => { /* the slate is an enrichment — La Une renders without it */ });
    return () => { alive = false; };
  }, [dayProgress.vocabularyDue, dayProgress.missionDone, dayProgress.feuilletonDone]);
  const vocabularyReviewDue = Math.max(0, Number(dayProgress.vocabularyDue || 0));
  const repairDue = Math.max(0, Number(dayProgress.errataDue || 0));
  const serialAction = serialActionFromToday(today, activeSession);
  const serialEpisode = (today as any)?.serial_episode || (today as any)?.serial || null;
  const libraryEpisode = STORY_FEATURE_VISIBLE ? (today as any)?.library_episode || null : null;
  const libraryHref = STORY_FEATURE_VISIBLE
    ? recommendation.kind === 'library'
      ? recommendation.href
      : libraryEpisode?.href || (libraryEpisode?.book_id ? `/notebook?mode=library&book=${libraryEpisode.book_id}&episode=${libraryEpisode.episode_index ?? libraryEpisode.order_index ?? 0}` : '/notebook?mode=library')
    : '/notebook';
  const serialKind = serialAction?.episodeKind
    || (recommendation.kind === 'serial' ? recommendation.episodeKind : 'feuilleton');
  const storyHref = parcoursStoryHref(serialAction, recommendation, serialEpisode);
  const serialDone = serialKind === 'mission' ? dayProgress.missionDone : dayProgress.feuilletonDone;
  const serialInvited = !serialAction && recommendation.kind !== 'serial' && !serialDone;
  const serialCopy = serialThreadCopy({
    kind: serialKind,
    invited: serialInvited,
    done: serialDone,
    episodeLabel: serialEpisodeLabel(serialAction || recommendation),
    status: serialEpisode?.status,
    hookText: serialEpisode?.hook?.teaser || serialEpisode?.hook?.text || serialEpisode?.previously,
  });
  const sessionComplete = dayProgress.sessionStatus === 'completed';
  const streak = atelierEditionStreak(today, activeSession);
  const submittedCount = sessionSubmittedCount(activeSession);
  const cefr = today?.cefr || null;
  const remainingMinutes = Math.max(0, Number(dayProgress.estimatedRemainingMinutes ?? dayProgress.estimatedTotalMinutes ?? 20));
  const storyReady = Boolean(storyHref);
  const upcomingFocus = parcoursUpcomingFocus(today);

  // ---- La Une (front page) mapping: every field below maps onto real API data. ----
  const isRest = recommendation.kind === 'rest';
  const episodeNumber = (() => {
    const idx = Number(serialEpisode?.episode_index);
    return Number.isFinite(idx) ? idx + 1 : 1;
  })();
  const isMissionBeat = serialKind === 'mission';
  const leadArtUrl = resolveMediaUrl(serialLeadImageUrl(serialEpisode));
  const leadArtMode: 'art' | 'press' | 'late' | 'none' =
    serialEpisode?.status === 'generating' ? 'press'
      : serialEpisode?.status === 'delayed' ? 'late'
        : leadArtUrl ? 'art'
          : 'none';
  const leadHeadline = storyReady
    ? parcoursStoryTeaser(serialEpisode, serialCopy.title)
    : isMissionBeat
      ? 'Une lettre attend ta réponse.'
      : `Épisode ${episodeNumber} — ta première scène t’attend.`;
  const leadByline = parcoursStoryCharacter(serialEpisode, serialKind).name;
  const activeCastMember = serialEpisode?.active_cast_member as Record<string, any> | undefined;
  const leadPortraitUrl = typeof activeCastMember?.model_sheet_url === 'string'
    ? activeCastMember.model_sheet_url
    : null;
  const leadAccentColour = typeof activeCastMember?.accent_colour === 'string'
    ? activeCastMember.accent_colour
    : null;
  const openStory = storyHref ? () => { void router.push(storyHref); } : null;

  const sessionNode = (dayProgress.nodes || []).find((node) => node.id === 'session');
  const sessionMins = Math.max(1, Number(sessionNode?.estimatedMinutes ?? remainingMinutes ?? 8));
  const timeBudget = Math.max(0, Number(dayProgress.timeBudgetMinutes || 0));
  const seanceStatus: 'fresh' | 'resume' | 'done' = sessionComplete ? 'done' : hasActiveSession ? 'resume' : 'fresh';
  const seanceConcepts: Array<{ t: string; cefr: string; role: 'new' | 'fragile' | 'contrast' }> = concepts.slice(0, 3).map((concept, index) => ({
    t: displayConceptTitle(concept),
    cefr: String(concept.level || 'A1'),
    role: concept.role === 'new' || concept.role === 'fragile' || concept.role === 'contrast'
      ? concept.role
      : index === 2 ? 'contrast' : 'fragile',
  }));
  const totalDrillsCount = plannedAtelierDrills(concepts, activeSession, sessionNode?.plannedDrills);
  const seanceProgress: [number, number] | null = hasActiveSession
    ? [Math.min(submittedCount, totalDrillsCount), Math.max(1, totalDrillsCount)]
    : null;
  const seanceAction: RecommendedAction = hasActiveSession
    ? {
        kind: 'resume_session',
        conceptIndex: activeSession?.current_position?.concept_index ?? 0,
        round: (activeSession?.current_position?.round as string) || 'recognize',
        mode: activeSession?.current_position?.mode,
        itemIndex: activeSession?.current_position?.item_index ?? 0,
      }
    : { kind: 'start_session' };
  const seanceDisabled = loading || (!hasActiveSession && !canStart);
  const prescribedConcept = seanceConcepts.find((concept) => concept.role === 'fragile') || seanceConcepts[0];
  // The headline minutes are what the edition will really cost at this
  // learner's measured pace (server-side estimate), never the daily-goal
  // setting echoed back at them. When the honest number overruns the budget the
  // prescription says so rather than quietly printing the nicer figure.
  const prescribedMinutes = Math.max(1, Number(remainingMinutes || sessionMins || 8));
  const overBudgetMinutes = timeBudget > 0 && prescribedMinutes > timeBudget ? timeBudget : null;
  // On the days the written mission is not prescribed, the day's third element is
  // the voice studio, so the prescription has to name speaking rather than a
  // written reply that is not being asked for.
  const studioIsPrescribed = Boolean(dayProgress.studioSuggested) && !dayProgress.studioDone;
  const onboardingMotivation = String(today?.summary?.learning_motivation || '').trim();
  const onboardingMotivationLabel = (
    {
      travel: 'voyager et vous débrouiller',
      work: 'travailler en français',
      relationships: 'parler avec vos proches',
      culture: 'lire, regarder et écouter',
    } as Record<string, string>
  )[onboardingMotivation] || onboardingMotivation;
  /* One quiet explaining clause on the first edition only — the onboarding
     motivation earns it. */
  const prescriptionBecause = today?.summary?.first_session && onboardingMotivation
    ? `parce que votre objectif « ${onboardingMotivationLabel} » commence par une seule règle bien posée.`
    : null;
  const phraseOfDay = today?.phrase_of_day || null;
  const nextEpisodeNumber = episodeNumber + 1;
  const rawEpisodeTease = firstNonEmptyString(serialEpisode?.hook?.teaser, serialEpisode?.hook?.text) || null;
  // A hook that merely repeats tonight's headline is no tease — let LuDemain
  // fall back to its "en composition" line instead of promising a rerun.
  const nextEpisodeTease = rawEpisodeTease && rawEpisodeTease.trim() !== String(leadHeadline || '').trim()
    ? rawEpisodeTease
    : null;
  /* The manchette's ask follows the recommendation; the because-line is kept
     only for the first edition, where the onboarding motivation earns it. */
  const askKind: LuAskKind = isRest
    ? 'rest'
    : recommendation.kind === 'mission' || (recommendation.kind === 'serial' && recommendation.episodeKind === 'mission') || recommendation.kind === 'studio'
      ? 'mission'
      : recommendation.kind === 'review'
        ? 'review'
        : recommendation.kind === 'feuilleton' || recommendation.kind === 'serial'
          ? 'read'
          : 'session';
  const ruleCount = seanceConcepts.length;
  const slateCount = wordSlate?.words?.length || 0;
  const lexiqueParts = [
    vocabularyReviewDue > 0 ? `${vocabularyReviewDue} mot${vocabularyReviewDue === 1 ? '' : 's'} à revoir` : null,
    slateCount > 0 ? `${slateCount} mot${slateCount === 1 ? '' : 's'} du jour` : null,
    repairDue > 0 ? `${repairDue} correction${repairDue === 1 ? '' : 's'}` : null,
  ].filter(Boolean) as string[];
  const errorOnlyPage = loadError && !today && !hasActiveSession;

  // ---- Home (design direction 1a): one story, one action, three tiles. ----
  const levelLabel = cefr?.estimate ? ` · ${cefr.estimate}` : '';
  const editionLabel = `Édition Nº ${episodeNumber}${levelLabel}`;
  // For engine-managed learners `/serial/today` answers `journey_required`
  // with no scene: the story is today's journey (its card is above), so the
  // page does not draw an episode it cannot open.
  const storyIsJourney = String(serialEpisode?.status || '') === 'journey_required';
  const homeEpisode = errorOnlyPage || storyIsJourney
    ? null
    : {
        kicker: isMissionBeat ? `Courrier · Épisode ${episodeNumber}` : `Feuilleton · Épisode ${episodeNumber}`,
        headline: leadHeadline,
        artUrl: leadArtUrl,
        artState: leadArtMode,
        byline: leadByline,
        bylineMeta: dayProgress.missionDone
          ? `${leadByline} a lu votre lettre`
          : [prescribedConcept?.t, `~${prescribedMinutes} min`].filter(Boolean).join(' · '),
        read: serialDone,
        onOpen: openStory,
        ariaLabel: (isMissionBeat ? 'Répondre à la mission — ' : 'Lire l’épisode — ') + leadHeadline,
      };
  // WP-16 / D-0: with the daily journey on screen above, the journey card
  // carries the day's one 3D-press action. La Une must not draw a second one —
  // and certainly not one that starts the legacy exercise Séance, which is now
  // «Plus de pratique». `practiceEntry` is non-null exactly in that case.
  const journeyOwnsPrimary = Boolean(practiceEntry);
  const homeAction = errorOnlyPage || isRest || journeyOwnsPrimary
    ? null
    : {
        label: askKind === 'mission'
          ? (studioIsPrescribed ? 'Parler' : 'Répondre')
          : askKind === 'review'
            ? 'Réviser'
            : askKind === 'read'
              ? 'Lire'
              : 'Continuer',
        onSelect: () => onRecommendedAction(recommendation),
        disabled: loading || (recommendation.kind === 'start_session' && !canStart),
        pending: loading,
      };
  const seanceBarsOn = seanceStatus === 'done'
    ? 3
    : seanceProgress
      ? Math.min(3, Math.round((seanceProgress[0] / seanceProgress[1]) * 3))
      : 0;
  const lexiqueDone = lexiqueParts.length === 0;
  const homeTiles: HomeTile[] = errorOnlyPage
    ? []
    : [
        {
          id: 'seance',
          title: 'Séance',
          // WP-16 / D-0: with the journey on, the tile stops advertising a
          // number of minutes for "today" — the day's minutes belong to the
          // journey — and names the exercises it really opens.
          meta: practiceEntry
            ? seanceStatus === 'resume' && seanceProgress
              ? `${seanceProgress[0]}/${seanceProgress[1]} · reprendre`
              : `${ruleCount} règle${ruleCount === 1 ? '' : 's'} · exercices`
            : seanceStatus === 'done'
              ? 'Bouclée'
              : seanceStatus === 'resume' && seanceProgress
                ? `${seanceProgress[0]}/${seanceProgress[1]} · reprendre`
                : `${ruleCount} règle${ruleCount === 1 ? '' : 's'} · ~${Math.max(1, Number(remainingMinutes || sessionMins || 8))} min`,
          mark: seanceStatus === 'done' && !practiceEntry ? 'done' : 'story',
          bars: [0, 1, 2].map((index) => (index < seanceBarsOn ? (seanceStatus === 'done' ? 'done' : 'story') : null)),
          // The tile and its secondary line lead to the same place: the drill
          // loop, entered by concept. Never `start_session` as "today".
          href: practiceEntry ? practiceEntry.href : undefined,
          onSelect: practiceEntry ? undefined : () => onRecommendedAction(seanceAction),
          disabled: practiceEntry ? false : seanceDisabled,
          done: seanceStatus === 'done' && !practiceEntry,
          // WP-16 / D-0: with the journey on, the drill loop is reachable here
          // and from a Cahier concept — never as the day's one action.
          secondary: practiceEntry
            ? {
                label: practiceEntry.label,
                href: practiceEntry.href,
                ariaLabel: `${practiceEntry.label} — la séance d’exercices`,
              }
            : null,
        },
        {
          id: 'lexique',
          title: 'Lexique',
          meta: lexiqueDone ? 'Rien à revoir' : lexiqueParts.slice(0, 2).join(' · '),
          mark: lexiqueDone ? 'done' : 'reward',
          bars: lexiqueDone ? ['done', 'done', 'done'] : [null, null, null],
          href: '/vocabulary/review',
          done: lexiqueDone,
        },
        {
          id: 'errata',
          title: 'Errata',
          meta: repairDue > 0 ? `${repairDue} à reprendre` : 'Rien à reprendre',
          mark: repairDue > 0 ? 'action' : 'done',
          bars: repairDue > 0 ? [null, null, null] : ['done', 'done', 'done'],
          // With repairs due the tile opens the review; otherwise it reads Le Relevé.
          onSelect: repairDue > 0 ? onOpenReview : undefined,
          href: '/notebook?mode=releve',
          done: repairDue === 0,
        },
      ];

  return (
    <HomeScreen
      dateLabel={formatAtelierEditionDate()}
      editionLabel={editionLabel}
      streak={streak}
      settingsHref="/settings"
      notice={loadError ? { label: loadError.label, message: loadError.message, onRetry: onRetry } : null}
      episode={homeEpisode}
      action={homeAction}
      filedLabel={isRest && !errorOnlyPage && !journeyOwnsPrimary ? 'Édition bouclée — à demain.' : null}
      note={journeyOwnsPrimary ? null : prescriptionBecause}
      overrunMinutes={journeyOwnsPrimary ? null : overBudgetMinutes}
      adjustHref={errorOnlyPage || isRest || journeyOwnsPrimary ? null : '/settings?section=practice'}
      phrase={phraseOfDay ? { text: phraseOfDay.text, byline: phraseOfDay.byline } : null}
      library={
        STORY_FEATURE_VISIBLE && libraryEpisode && (
          {
            title: libraryEpisode.book_title || libraryEpisode.title || 'La Bibliothèque',
            chapter: Number(libraryEpisode.episode_index ?? libraryEpisode.order_index ?? 0) + 1,
            href: libraryHref,
          }
        )
      }
      tiles={homeTiles}
      colophon={errorOnlyPage ? null : {
        lead: 'Demain — ',
        focus: upcomingFocus.topic,
        focusHref: upcomingFocus.href,
        tail: nextEpisodeTease ? `, épisode ${nextEpisodeNumber} · ${nextEpisodeTease}.` : `, épisode ${nextEpisodeNumber}.`,
      }}
    >
      <AtelierEditionNav active="atelier" />
    </HomeScreen>
  );
}

function firstNonEmptyString(...values: unknown[]) {
  for (const value of values) {
    const text = String(value || '').trim();
    if (text) return text;
  }
  return '';
}

// Resolve the front-page lead image ("head picture of the journal").
// Prefers a composed panel URL if the payload ever carries one, then falls back
// to the episode location's establishing illustration from the serial world
// bible (served by Next from /public/assets/serial/...). Returns null when no
// real image resolves, so the lead stays text-first instead of showing a
// broken frame.
function serialLeadImageUrl(serialEpisode: Record<string, any> | null): string | null {
  if (!serialEpisode) return null;
  const toUrl = (raw: unknown): string | null => {
    const value = String(raw || '').trim();
    if (!value) return null;
    if (/^https?:\/\//.test(value) || value.startsWith('/')) return value;
    return `/${value.replace(/^\.?\/+/, '')}`;
  };
  const composed = toUrl(
    firstNonEmptyString(
      // The episode's own printed art comes first; plates and hooks are fallbacks.
      serialEpisode?.lead_image_url,
      serialEpisode?.hero_image,
      serialEpisode?.image_url,
      serialEpisode?.hook?.image_url,
      serialEpisode?.panels?.[0]?.image_url,
    ),
  );
  if (composed) return composed;
  const locationId = serialEpisode?.location_id;
  const locations = serialEpisode?.thread?.world_bible?.visual_design?.locations;
  const refs = locationId && locations && locations[locationId]
    ? locations[locationId].reference_images
    : null;
  return Array.isArray(refs) && refs.length ? toUrl(refs[0]) : null;
}

function stripDisplayQuotes(value: string) {
  return value
    .replace(/^\s*[«"“]+/, '')
    .replace(/[»"”]+\s*$/, '')
    .trim();
}

function parcoursStoryTeaser(serialEpisode: Record<string, any> | null, fallback: string) {
  // `beat` (e.g. "act") is an internal state-machine field, never narrative
  // copy — never include it here. When there's no real hook yet, fall back to
  // the honest, human-authored serialCopy.title rather than inventing a plot
  // beat (e.g. a name-dropped cliffhanger) that may not be true this episode.
  const raw = firstNonEmptyString(
    serialEpisode?.hook?.teaser,
    serialEpisode?.hook?.text,
    serialEpisode?.previously,
  );
  return stripDisplayQuotes(raw || fallback);
}

function parcoursStoryCharacter(serialEpisode: Record<string, any> | null, kind: 'mission' | 'feuilleton') {
  const name = firstNonEmptyString(
    serialEpisode?.character?.name,
    serialEpisode?.character_name,
    serialEpisode?.npc_name,
    serialEpisode?.speaker_name,
    serialEpisode?.speaker,
    kind === 'mission' ? 'Monsieur Marchand' : 'Romy Tremblay',
  );
  return {
    name,
    initial: name.replace(/^monsieur\s+/i, '').trim().charAt(0).toUpperCase() || 'R',
  };
}

function isRecordValue(value: unknown): value is Record<string, any> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

function queryHasAnyParam(query: string, names: string[]) {
  const params = new URLSearchParams(query.replace(/^\?/, ''));
  return names.some((name) => Boolean(params.get(name)));
}

function parcoursStoryHref(
  serialAction: Extract<RecommendedAction, { kind: 'serial' }> | null,
  recommendation: RecommendedAction,
  serialEpisode: Record<string, any> | null,
) {
  const episodeKind = serialAction?.episodeKind || (recommendation.kind === 'serial' ? recommendation.episodeKind : null);
  const query = serialAction?.query || (recommendation.kind === 'serial' ? recommendation.query : '');
  if (!episodeKind || !query) return null;

  if (episodeKind === 'mission') {
    return queryHasAnyParam(query, ['mission', 'mission_id']) || serialEpisode?.mission_id
      ? `/missions${query}`
      : null;
  }

  return queryHasAnyParam(query, ['scene', 'scene_id']) || serialEpisode?.scene_id
    ? `/graphic-novel${query}`
    : null;
}

function parcoursSummaryFocus(today: AtelierToday | null, key: 'previous' | 'today' | 'next') {
  const summary = today?.summary || {};
  const parcours = isRecordValue(summary.parcours) ? summary.parcours : {};
  if (key === 'previous') {
    return parcours.previous || summary.previous_focus || summary.previous_concept || summary.last_focus || null;
  }
  if (key === 'next') {
    return summary.tomorrow_focus || parcours.next || summary.next_focus || summary.next_concept || null;
  }
  return parcours.today || summary.today_focus || null;
}

function focusLabel(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map(focusLabel).find(Boolean) || '';
  }
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value).trim();
  }
  if (!isRecordValue(value)) return '';
  return [
    value.label,
    value.display_title,
    value.title,
    value.name,
    value.concept,
    value.concepts,
  ].map(focusLabel).find(Boolean) || '';
}

function focusDateValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map(focusDateValue).find(Boolean) || '';
  }
  if (!isRecordValue(value)) return '';
  return firstNonEmptyString(
    value.completed_at,
    value.scheduled_at,
    value.next_review,
    value.date,
    value.concept?.next_review,
    value.concepts?.[0]?.next_review,
  );
}

function focusConceptId(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map(focusConceptId).find(Boolean) || '';
  }
  if (!isRecordValue(value)) return '';
  return firstNonEmptyString(
    value.id,
    value.concept_id,
    value.concept?.id,
    value.concept?.concept_id,
    value.concepts?.[0]?.id,
    value.concepts?.[0]?.concept_id,
  );
}

function localDateKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function shiftDateKey(offsetDays: number) {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  return localDateKey(date);
}

function focusDayLabel(value: unknown, fallback: string, direction: 'previous' | 'next') {
  const rawDate = focusDateValue(value);
  if (!rawDate) return fallback;
  const date = new Date(rawDate);
  if (Number.isNaN(date.getTime())) return fallback;
  const key = localDateKey(date);
  if (direction === 'previous' && key === shiftDateKey(-1)) return 'Hier';
  if (direction === 'next' && key === shiftDateKey(1)) return 'Demain';
  return new Intl.DateTimeFormat('fr-FR', { weekday: 'long' }).format(date);
}

function parcoursUpcomingFocus(today: AtelierToday | null) {
  const focus = parcoursSummaryFocus(today, 'next');
  const label = focusLabel(focus);
  const conceptId = focusConceptId(focus);
  return {
    dayLabel: focusDayLabel(focus, label ? 'À suivre' : 'Après', 'next'),
    topic: label ? parcoursTopicShort(label) : 'après la séance',
    href: conceptId ? `/notebook?mode=grammar&concept=${encodeURIComponent(conceptId)}` : '/notebook',
  };
}

function parcoursTopicShort(value: string) {
  const normalized = value.trim();
  const lower = normalized.toLowerCase();
  if (lower.includes('imparfait')) return 'l’imparfait';
  if (lower.includes('relatif')) return 'pronoms relatifs';
  if (lower.includes('si ') || lower.includes('condition')) return 'si + présent';
  if (lower.includes('négation') || lower.includes('negation')) return 'la négation';
  return normalized.length > 26 ? `${normalized.slice(0, 23).trim()}…` : normalized;
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
  return `Classée · ${day} · ${month} · ${year}`;
}

function atelierEditionStreak(today: AtelierToday | null, activeSession: AtelierSessionStart | null) {
  const value = Number(
    today?.summary?.streak
      ?? activeSession?.recap?.streak_after
      ?? activeSession?.recap?.streak_before
      ?? 0,
  );
  return Number.isFinite(value) && value > 0 ? Math.round(value) : 0;
}

// Once a session exists its own payload is the truth (and shrinks as the learner
// earns skips). Before that, the server's planned count for today's concepts is —
// never a number invented on the client.
function plannedAtelierDrills(
  concepts: AtelierConcept[],
  activeSession: AtelierSessionStart | null,
  plannedFromServer?: number,
) {
  const sessionTotal = totalDrills(activeSession, sessionAdaptiveLocks(activeSession), activeSession?.submitted_map || {});
  if (sessionTotal > 0) return sessionTotal;
  const planned = Number(plannedFromServer || 0);
  if (planned > 0) return planned;
  return concepts.length > 0 ? concepts.length * DRILLS_PER_CONCEPT + SESSION_LEVEL_DRILLS : 0;
}

type AtelierEditionStepState = 'done' | 'current' | 'up';

type SerialOnRampVariant = 'act' | 'see' | 'invite' | 'rest';

function serialEpisodeLabel(action: RecommendedAction) {
  if (action.kind !== 'serial') return 'Épisode 1';
  const params = new URLSearchParams(action.query.replace(/^\?/, ''));
  const index = Number(params.get('episode_index'));
  if (!Number.isFinite(index)) return 'Épisode';
  return `Épisode ${index + 1}`;
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
      episode: `${episodeLabel} · retardé`,
      previously: '',
      beat: "L'édition de demain est retardée",
      title: 'Les presses sont à l’arrêt.',
      sub: 'La rédaction du feuilleton est indisponible : l’édition attend sans rejouer l’ouverture.',
      cta: 'Réessayer l’édition',
    };
  }
  if (status === 'generating') {
    return {
      episode: `${episodeLabel} · sous presse`,
      previously: '',
      beat: 'L’édition de demain est à l’imprimerie',
      title: 'Le récit est prêt.',
      sub: hookText ? `À suivre : ${hookText}` : 'Les planches paraîtront à mesure que le service image les termine.',
      cta: 'Ouvrir l’édition',
    };
  }
  if (done) {
    return {
      episode: `${episodeLabel} · classé`,
      previously: 'vous avez fait avancer le feuilleton.',
      beat: '— Fin de l’épisode —',
      title: 'Vous êtes à jour.',
      sub: hookText ? `Demain : ${hookText}` : 'Le prochain acte est encore en composition. Laissez le suspense reposer jusqu’à demain.',
      cta: '',
    };
  }
  if (invited) {
    return {
      episode: `${episodeLabel} · ouverture`,
      previously: '',
      beat: 'Un nouveau feuilleton',
      title: '“L’arrivée”',
      sub: 'Un café du 11e, une clé qui refuse de tourner et des gens qui se souviendront de vous. Votre français fait avancer le récit.',
      cta: 'Commencer l’épisode 1',
    };
  }
  if (kind === 'mission') {
    return {
      episode: `${episodeLabel} · agir`,
      previously: 'la dernière planche a laissé quelqu’un attendre votre réponse.',
      beat: 'Le monde attend ta réponse',
      title: 'Le monde attend votre réponse',
      sub: 'Écrivez le prochain message et laissez le feuilleton vous répondre.',
      cta: 'Répondre dans le feuilleton',
    };
  }
  return {
    episode: `${episodeLabel} · lire`,
    previously: hookText || 'la réponse que vous avez écrite devient la scène.',
    beat: 'Nouvel épisode prêt',
    title: 'Continuer le feuilleton',
    sub: 'Voyez ce que votre dernier message a changé, puis repartez avec le prochain suspense.',
    cta: 'Lire l’épisode',
  };
}

function AtelierEditionNav({
  active = 'atelier',
}: {
  active?: 'atelier' | 'missions' | 'feuilleton' | 'notebook';
}) {
  return <PhoneProductNav active={active} placement="embedded" />;
}

function displayConceptTitle(concept: AtelierConcept) {
  // Publication surfaces speak French first; catalog names stay the native-
  // language fallback until every concept carries its fr localization.
  return String(concept.title_fr || concept.atelier_blueprint?.display_title || concept.name || 'Règle du jour');
}

function firstDueErratum(today: AtelierToday | null, activeSession: AtelierSessionStart | null) {
  return activeSession?.due_errata?.find((item) => item.id)
    || today?.due_errata?.find((item) => item.id)
    || today?.concepts?.flatMap((concept) => concept.due_errata || []).find((item) => item.id)
    || null;
}

function sessionSubmittedCount(session: AtelierSessionStart | null) {
  if (!session) return 0;
  return submittedDrills(session, session.submitted_map || {}, sessionAdaptiveLocks(session));
}

function vocabularyTranslation(item: VocabularyRecommendationItem) {
  return learnerGloss(item, 'mot visé');
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
            {/* review_mode is a machine key ("word_bank", "grammar"); the server
                now sends the French label beside it. */}
            <div className="t-mono-low">{task.source_label || 'Atelier'}{task.review_mode_label ? ` · ${task.review_mode_label}` : ''}</div>
            <h2>{task.display_label}</h2>
          </div>
          <button className="btn ghost" onClick={onClose}>FERMER ×</button>
        </header>
        <div className="errata-review-body">
          <div className="errata-review-copy">
            <div className="t-mono yellow">TÂCHE DE REPRISE</div>
            <p className="review-prompt">{task.prompt}</p>
            <p>{task.instruction}</p>
            {task.learner_text && (
              <div className="review-memory">
                <div className="t-mono-low">ERREUR MÉMORISÉE</div>
                <p className="wrong">{task.learner_text}</p>
              </div>
            )}
            {task.why_wrong && <p><strong>Pourquoi :</strong> {printableWhy(task.why_wrong)}</p>}
            {task.repair_hint && <p><strong>À reprendre :</strong> {printableWhy(task.repair_hint)}</p>}
          </div>
          <div className="errata-review-answer">
            <label className="t-mono" htmlFor="errata-review-answer">VOTRE REPRISE</label>
            <textarea
              id="errata-review-answer"
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
              placeholder={task.placeholder}
              autoFocus
            />
            {result && (
              <div className={`review-result ${result.is_correct ? 'correct' : ''}`}>
                <div className="t-mono">{result.is_correct ? 'REPRIS' : 'PAS ENCORE'}</div>
                <p>{printableWhy(result.feedback)}</p>
                {!result.is_correct && (
                  <p><strong>Réponse visée :</strong> <span className="right">{result.target_answer}</span></p>
                )}
              </div>
            )}
            <div className="action-row">
              <button className="btn red lg" disabled={submitting || !answer.trim()} onClick={onSubmit}>
                ENVOYER LA REPRISE <Send size={15} />
              </button>
              {result?.is_correct && <button className="btn solid lg" onClick={onClose}>TERMINÉ <Check size={15} /></button>}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function hasConceptRecognizeSubmission(submitted: Record<string, boolean>, conceptId?: number | null) {
  if (!conceptId) return false;
  return recognizeModes.some((item) => {
    const legacyKey = answerKey('recognize', item.id, conceptId);
    const itemPrefix = `${legacyKey}:`;
    return submitted[legacyKey] || Object.keys(submitted).some((key) => key.startsWith(itemPrefix) && submitted[key]);
  });
}

// Maps a concept's Bauhaus blueprint visual_motif into L'Épreuve house-form
// primitives, scaled to the 46-unit motif canvas, printing one more piece per
// round advanced through the concept (the motif assembles as you set the type).
function epMotifPrimsFrom(concept: AtelierConcept | null, roundOrdinal: number): MotifPrim[] {
  const vm = concept?.atelier_blueprint?.visual_motif as Record<string, any> | undefined;
  const raw = Array.isArray(vm?.primitives) ? vm!.primitives : [];
  const canvas = Number(vm?.canvas?.width) || 84;
  const k = 46 / canvas;
  const houses = raw.filter((p: any) => p && (p.type === 'rect' || p.type === 'circle' || p.type === 'triangle'));
  return houses.map((p: any, i: number): MotifPrim => {
    if (p.type === 'circle') {
      const r = Number(p.r) || 6;
      return { shape: 'circle', cx: (Number(p.cx) || 0) * k, cy: (Number(p.cy) || 0) * k, s: r * 2 * k, printed: i < roundOrdinal, printing: i === roundOrdinal - 1 };
    }
    const w = Number(p.w) || 12;
    const h = Number(p.h) || 12;
    const cx = ((Number(p.x) || 0) + w / 2) * k;
    const cy = ((Number(p.y) || 0) + h / 2) * k;
    return { shape: p.type === 'triangle' ? 'triangle' : 'square', cx, cy, s: Math.max(w, h) * k, printed: i < roundOrdinal, printing: i === roundOrdinal - 1 };
  });
}

function SessionView({
  session,
  activeConceptIndex,
  activeItemIndex,
  activeItemCount,
  round,
  mode,
  activeSet,
  activeConcept,
  activeItemId,
  currentAnswers,
  updateAnswer,
  submitAttempt,
  completeSession,
  submitting,
  submitted,
  correctionsByKey,
  goNext,
  retryAttempt,
  requestAiReview,
  reportExercise,
  aiReviewSubmitting,
  completedDrills,
  totalDrills: totalDrillsForSession,
  confidence,
  onPickConfidence,
  repairDrafts,
  onSetRepairDraft,
  onSubmitRepair,
  repairSubmitting,
  isRetest,
  onBack,
  produceAnswer,
}: {
  session: AtelierSessionStart;
  activeConceptIndex: number;
  activeItemIndex: number;
  activeItemCount: number;
  round: RoundName;
  mode: RecognizeMode;
  activeSet: Record<string, any> | null;
  activeConcept: AtelierConcept | null;
  activeItemId: string | null;
  currentAnswers: Record<string, any>;
  updateAnswer: (key: string, value: any, scopedRound?: RoundName, scopedMode?: string, conceptId?: number | null, itemId?: string | null) => void;
  submitAttempt: () => void;
  completeSession: () => void;
  submitting: boolean;
  submitted: Record<string, boolean>;
  correctionsByKey: Record<string, Record<string, any>>;
  goNext: () => void;
  retryAttempt: () => void;
  requestAiReview: () => void;
  reportExercise: () => void;
  aiReviewSubmitting: boolean;
  completedDrills: number;
  totalDrills: number;
  confidence?: 'sure' | 'unsure';
  onPickConfidence: (confidence: 'sure' | 'unsure') => void;
  repairDrafts: Record<string, string>;
  onSetRepairDraft: (key: string, value: string) => void;
  onSubmitRepair: (erratumIndex: number) => void;
  repairSubmitting: Record<string, boolean>;
  isRetest: boolean;
  onBack: () => void;
  produceAnswer: string;
}) {
  const currentMode = roundMode(round, mode);
  const currentKey = answerKey(round, currentMode, roundUsesSessionScope(round) ? null : activeConcept?.id, activeItemId);
  const currentCorrection = correctionsByKey[currentKey] || null;
  const currentSubmitted = !!submitted[currentKey];
  const total = totalDrillsForSession;
  const activeRoundLabel = roundLabels.find((item) => item.id === round)?.label || 'Pratique';
  const activeRecognizeLabel = recognizeModes.find((item) => item.id === mode)?.label || 'Reconnaître';
  const activeConceptTitle = activeConcept ? displayConceptTitle(activeConcept) : 'Séance du jour';
  const focusedItemLabel = activeItemCount > 1 ? `${activeItemIndex + 1}/${activeItemCount}` : '';
  const [ruleOpenByConcept, setRuleOpenByConcept] = useState<Record<string, boolean>>({});
  const conceptRuleKey = `${session.session_id}:${activeConcept?.id || 'session'}`;
  const firstConceptDrill = Boolean(
    activeConcept
      && round === 'recognize'
      && mode === 'fill'
      && !hasConceptRecognizeSubmission(submitted, activeConcept.id),
  );
  const rulePreference = ruleOpenByConcept[conceptRuleKey];
  const ruleExpanded = firstConceptDrill ? rulePreference !== false : rulePreference === true;
  const isFinalConversation = !isRetest && round === 'conversation' && activeConceptIndex >= session.concepts.length - 1;
  const currentFeedback = currentSubmitted
    ? feedbackForExercise(round, mode, activeSet, activeItemIndex, currentAnswers, currentCorrection)
    : null;
  // The design's primary cycles Vérifier → Continuer → Terminer.
  const feedbackNextLabel = isFinalConversation ? 'Terminer' : 'Continuer';
  const feedbackRule = currentFeedback && !currentFeedback.correct
    ? feedbackRuleLine(activeSet, activeConcept)
    : undefined;
  const feedbackNext = isFinalConversation ? completeSession : goNext;
  const nextDisabled = !drillAnswerIsReady(activeSet, round, mode, activeItemIndex, currentAnswers, produceAnswer);
  const toggleRule = () => {
    setRuleOpenByConcept((prev) => ({ ...prev, [conceptRuleKey]: !ruleExpanded }));
  };

  // ---- L'Épreuve frame mapping (composing stick + assembling motif). ----
  const sessionComplete = String(session.status) === 'completed' || (total > 0 && completedDrills >= total);
  const roundOrdinal = Math.max(1, roundLabels.findIndex((item) => item.id === round) + 1);
  const epMotifPrims = epMotifPrimsFrom(activeConcept, roundOrdinal);
  const epGroups = [{ total: Math.max(1, total), set: completedDrills, current: !sessionComplete }];
  const epCap: [string, string] = [`${completedDrills}/${total || '–'}`, ''];
  // The "Manqué · …" note explains why this concept was seated; said once, on
  // arrival, it is context — repeated above all 15 drills it was clutter.
  const provenance = roundOrdinal === 1 && activeItemIndex === 0 && !isRetest
    ? provenanceLine(activeConcept?.due_errata?.[0])
    : null;
  const activeLock = currentCorrection?.adaptive_lock;
  // The header's red "● n" is the session's own run of consecutive correct
  // answers, read from the real corrections in submission order; it is never
  // a placeholder. A correction with no substantive erratum is a correct line.
  const correctRun = (() => {
    let run = 0;
    const corrections = Object.values(correctionsByKey);
    for (let index = corrections.length - 1; index >= 0; index -= 1) {
      const errata = Array.isArray(corrections[index]?.errata) ? corrections[index].errata : [];
      const substantive = errata.filter((item: any) => String(item?.task_error_type || '') !== 'task_compliance');
      if (substantive.length > 0) break;
      run += 1;
    }
    return run;
  })();

  return (
    <EpShell className="atelier-do-mode">
      <LEpreuveStyles />
      <EpTopbar
        groups={epGroups}
        cap={epCap}
        onClose={onBack}
        onFinish={completeSession}
        // Every classed drill is already banked server-side, so stopping early
        // files a real (shorter) edition -- streak, recap and errata included.
        // Only a session with nothing in it has nothing to file.
        finishDisabled={submitting || completedDrills < 1}
        partial={completedDrills < total}
        run={correctRun}
      />
      <div className="ep-body av2-screen__body">
      {activeSet && activeConcept && (
        <section className="ep-sheet">
          <EpEyebrow
            round={activeRoundLabel}
            mode={round === 'recognize' ? activeRecognizeLabel : undefined}
            i={activeItemCount > 1 ? activeItemIndex + 1 : 1}
            n={activeItemCount > 1 ? activeItemCount : 1}
            retour={isRetest}
          />
          {provenance && <EpProvenance>{provenance}</EpProvenance>}
          <EpConcept
            title={activeConceptTitle}
            motif={<EpMotif prims={epMotifPrims} canvas={46} done={sessionComplete} />}
            askOn={ruleExpanded}
            onAsk={toggleRule}
          />
          {ruleExpanded && (
            <EpRule
              lede={<ConceptRulePanel payload={activeSet} concept={activeConcept} />}
              examples={firstConceptDrill ? ['Essayez maintenant avec l’élément le plus simple.'] : []}
              onClose={toggleRule}
            />
          )}
              {round === 'recognize' && (
                <div className="ep-frame">
                    <RecognizePanel
                      payload={activeSet}
                      mode={mode}
                      activeItemIndex={activeItemIndex}
                      answers={currentAnswers}
                      updateAnswer={updateAnswer}
                      correction={currentCorrection}
                      submitted={currentSubmitted}
                    />
                    <ActionRow
                      submitting={submitting}
                      submitted={currentSubmitted}
                      nextDisabled={nextDisabled}
                      submitAttempt={submitAttempt}
                      confidence={confidence}
                      onPickConfidence={onPickConfidence}
                    />
                </div>
              )}
              {round === 'transform' && (
                <div className="ep-frame">
                  <TransformPanel
                    payload={activeSet}
                    activeItemIndex={activeItemIndex}
                    answers={currentAnswers}
                    updateAnswer={updateAnswer}
                    correction={currentCorrection}
                    submitted={currentSubmitted}
                  />
                  <ActionRow
                    submitting={submitting}
                    submitted={currentSubmitted}
                    nextDisabled={nextDisabled}
                    submitAttempt={submitAttempt}
                    confidence={confidence}
                    onPickConfidence={onPickConfidence}
                  />
                </div>
              )}
              {(round === 'sentence' || round === 'speak' || round === 'conversation') && (
                <div className="ep-frame">
                  <OutputLadderPanel
                    payload={activeSet}
                    round={round}
                    answer={currentAnswers.text || ''}
                    updateAnswer={(value) => updateAnswer('text', value)}
                    correction={currentCorrection}
                    submitted={currentSubmitted}
                  />
                  <ActionRow
                    submitting={submitting}
                    submitted={currentSubmitted}
                    nextDisabled={nextDisabled}
                    submitAttempt={submitAttempt}
                    confidence={confidence}
                    onPickConfidence={onPickConfidence}
                  />
                </div>
              )}
              {round === 'produce' && (
                <div className="ep-frame">
                  <ProducePanel
                    concepts={session.concepts}
                    exerciseSets={session.exercise_sets}
                    payload={activeSet}
                    targetVocabulary={session.target_vocabulary}
                    answer={produceAnswer}
                    updateAnswer={(value) => updateAnswer('text', value)}
                    correction={currentCorrection}
                    submitted={currentSubmitted}
                  />
                  <ActionRow
                    submitting={submitting}
                    submitted={currentSubmitted}
                    nextDisabled={nextDisabled}
                    submitAttempt={submitAttempt}
                    confidence={confidence}
                    onPickConfidence={onPickConfidence}
                  />
                </div>
              )}
              {activeLock && currentSubmitted && (
                <EpLock
                  title={activeConceptTitle}
                  retired={Number(activeLock.retired_now ?? activeLock.retired_drills ?? 0)}
                  motif={<EpMotif prims={epMotifPrims} canvas={76} done />}
                />
              )}
              <ExerciseFeedbackMoment
                feedback={currentFeedback}
                submitted={currentSubmitted}
                rule={feedbackRule}
                onNext={feedbackNext}
                nextLabel={feedbackNextLabel}
                onTryAgain={currentFeedback && !currentFeedback.correct ? retryAttempt : undefined}
                onReport={currentFeedback && !currentFeedback.correct ? reportExercise : undefined}
                correction={currentCorrection}
                repairDrafts={repairDrafts}
                onSetRepairDraft={onSetRepairDraft}
                onSubmitRepair={onSubmitRepair}
                repairSubmitting={repairSubmitting}
                feedbackKey={currentKey}
                isLabelCompare={round === 'recognize' && mode === 'classify'}
                onRetryAiReview={requestAiReview}
                aiReviewSubmitting={aiReviewSubmitting}
              />
        </section>
      )}
      {(!activeSet || !activeConcept) && (
        // A concept whose exercise set failed to compose used to render the
        // topbar over an empty page: no copy, no way forward. The press notice
        // is the designed state for it.
        <section className="ep-sheet">
          <EpNotice
            msg="La feuille de cette règle n’a pas pu être composée. Ce qui est déjà classé est enregistré ; revenez à La Une, la rédaction recompose l’édition."
            onRetry={onBack}
          />
        </section>
      )}
      </div>
    </EpShell>
  );
}

function ActionRow({
  submitting,
  submitted,
  nextDisabled,
  submitAttempt,
  confidence,
  onPickConfidence,
}: {
  submitting: boolean;
  submitted: boolean;
  nextDisabled: boolean;
  submitAttempt: () => void;
  confidence?: 'sure' | 'unsure';
  onPickConfidence: (confidence: 'sure' | 'unsure') => void;
}) {
  if (submitted) return null;
  return (
    <>
      <EpConfidence value={confidence} onPick={onPickConfidence} />
      {/* The one 3D press of the screen, in the footer band: grey face until an
          answer is chosen, spent (spinner + word) while the line is checked. */}
      <EpFoot tone="neutral">
        <EpBar tone="go" icon="check" disabled={submitting || nextDisabled} pending={submitting} onClick={submitAttempt}>
          {submitting ? 'Vérification…' : 'Vérifier'}
        </EpBar>
      </EpFoot>
    </>
  );
}

function ExerciseFeedbackMoment({
  feedback,
  submitted,
  rule,
  onTryAgain,
  onNext,
  nextLabel,
  onReport,
  correction,
  repairDrafts,
  onSetRepairDraft,
  onSubmitRepair,
  repairSubmitting,
  feedbackKey,
  isLabelCompare,
  onRetryAiReview,
  aiReviewSubmitting,
}: {
  feedback: InlineFeedbackModel;
  submitted: boolean;
  rule?: string;
  onTryAgain?: () => void;
  onNext: () => void;
  nextLabel: string;
  onReport?: () => void;
  correction: Record<string, any> | null;
  repairDrafts: Record<string, string>;
  onSetRepairDraft: (key: string, value: string) => void;
  onSubmitRepair: (erratumIndex: number) => void;
  repairSubmitting: Record<string, boolean>;
  feedbackKey: string;
  isLabelCompare?: boolean;
  onRetryAiReview?: () => void;
  aiReviewSubmitting?: boolean;
}) {
  if (!submitted || !feedback) return null;
  if (feedback.unscored) {
    return (
      <div className="ep-feedback" data-verdict="unscored" role="status">
        <p className="av2-body">Votre réponse est enregistrée, mais elle n’a pas encore pu être vérifiée. Aucun résultat ni progrès de maîtrise n’est attribué.</p>
        <EpRelecture status="failed" onRetry={onRetryAiReview} retrying={aiReviewSubmitting} />
        <EpFoot tone="neutral">
          <EpBar tone="ghost" onClick={onNext}>Passer sans évaluation</EpBar>
        </EpFoot>
      </div>
    );
  }
  const issues = feedback.issues?.length
    ? feedback.issues
    : feedback.target
      ? [{ display_label: 'Ligne corrigée', learner_text: feedback.learner, corrected_target: feedback.target, why_wrong: feedback.why } as AtelierErratum]
      : [];
  const repairs = correction?.micro_repairs || {};
  // The typed retype only gates Next for corrections that are real lines;
  // one-word fixes are settled by the galley marks alone.
  const needsNewAnswer = issues.some((issue) => issue.task_error_type === 'task_compliance' || !issue.corrected_target);
  const repairsComplete = !needsNewAnswer && (isLabelCompare || issues.every((issue, index) => {
    const target = String(issue.corrected_target || '').trim();
    if (!isRepairableLine(target)) return true;
    return repairs[String(index)]?.status === 'ok';
  }));
  const aiStatus = aiReviewStatus(correction);
  const relecture = aiStatus === 'pending' || aiStatus === 'reviewing' || aiStatus === 'queued'
    ? <EpRelecture status="pending" />
    : aiStatus === 'complete'
      ? <EpRelecture status="done">Relecture terminée</EpRelecture>
      // A failed second look used to render nothing at all, so the note simply
      // never resolved and the retry endpoint was unreachable from the sheet.
      : (aiStatus === 'error' || aiStatus === 'failed')
        ? <EpRelecture status="failed" onRetry={onRetryAiReview} retrying={aiReviewSubmitting} />
        : null;
  // French words the learner fell back to L1 for — the backend added each to the
  // vocabulary notebook, so we confirm it inline under the correction.
  const vocabularyGaps: Array<{ french: string; gloss?: string }> = Array.isArray(correction?.vocabulary_gaps?.added)
    ? correction.vocabulary_gaps.added
        .map((gap: any) => ({ french: String(gap?.french || '').trim(), gloss: String(gap?.gloss || '').trim() }))
        .filter((gap: { french: string }) => gap.french)
    : [];

  if (feedback.correct) {
    return (
      <div className="ep-feedback" data-verdict="correct">
        <EpCorrect said={feedback.target || feedback.learner || 'Ligne réglée.'} struck />
        {/* The design's mint footer: badge + Garamond verdict, then the primary. */}
        <EpFoot tone="correct">
          <EpVerdict tone="go" sub={rule}>Bien joué !</EpVerdict>
          <EpBar icon="check" onClick={onNext}>{nextLabel}</EpBar>
        </EpFoot>
      </div>
    );
  }

  return (
    <div className="ep-feedback" data-verdict="wrong">
      {issues.map((issue, index) => {
        const learner = String(issue.learner_text || feedback.learner || '').trim();
        const target = String(issue.corrected_target || feedback.target || '').trim();
        const repairKey = `${feedbackKey}:${index}`;
        const repair = repairs[String(index)] || null;
        if (issue.task_error_type === 'task_compliance' || !target) {
          return <div className="av2-surface" key={`task-${index}`} role="status">
            <p className="av2-label">La consigne</p>
            <p className="av2-body">{issue.why_wrong || feedback.why}</p>
            {issue.repair_hint && <p className="av2-body">{issue.repair_hint}</p>}
          </div>;
        }
        return (
          <React.Fragment key={`${issue.display_label || 'repair'}-${index}`}>
            <EpGalley
              anchor={issue.display_label || `Correction ${index + 1}`}
              why={printableWhy(issue.why_wrong || feedback.why)}
              repair={printableWhy(issue.repair_hint || (index === 0 ? feedback.repair : '')) || undefined}
              // One second-look note per correction sheet, not one per erratum.
              relecture={index === 0 ? relecture : undefined}
            >
              {isLabelCompare && learner
                ? <EpLabelFix old={learner} fix={target || 'corrigé'} />
                : isRepairableLine(target) || isRepairableLine(learner)
                  ? <EpLineFix old={learner} fix={target || 'corrigé'} />
                  : learner ? <EpFix old={learner} fix={target || 'corrigé'} /> : <EpIns fix={target || 'corrigé'} />}
            </EpGalley>
            {!isLabelCompare && target && isRepairableLine(target) && (
              <EpRepair
                target={target}
                typed={repair?.typed || repairDrafts[repairKey] || ''}
                status={repair?.status || null}
                onChange={(value) => onSetRepairDraft(repairKey, value)}
                onSubmit={() => onSubmitRepair(index)}
                submitting={!!repairSubmitting[repairKey]}
              />
            )}
          </React.Fragment>
        );
      })}
      {vocabularyGaps.length > 0 && (
        <div className="ep-notebook-add">
          <span className="nh">Ajouté au carnet</span>
          <ul>
            {vocabularyGaps.map((gap, index) => (
              <li key={`${gap.french}-${index}`}>
                <b>{gap.french}</b>
                {gap.gloss ? <em> — {gap.gloss}</em> : null}
              </li>
            ))}
          </ul>
        </div>
      )}
      {/* The design's blush footer: badge + "Presque." with the rule as its
          13px line, then the primary — Continuer once the line is recopied,
          otherwise the retry. The quiet links stay third-tier underneath. */}
      <EpFoot tone="wrong">
        <EpVerdict tone="no" sub={rule}>À reprendre</EpVerdict>
        {repairsComplete
          ? <EpBar icon="check" onClick={onNext}>{nextLabel}</EpBar>
          : onTryAgain && <EpBar tone="ghost" icon="retry" onClick={onTryAgain}>Réessayer la ligne</EpBar>}
        <div className="ep-fb-links">
          {repairsComplete && onTryAgain && (
            <button type="button" onClick={onTryAgain}>Réessayer</button>
          )}
          {needsNewAnswer && <button type="button" onClick={onNext}>Passer cet exercice</button>}
          {onReport && (
            <button type="button" onClick={onReport}>Signaler cet exercice</button>
          )}
        </div>
      </EpFoot>
    </div>
  );
}

function ConceptRulePanel({ payload, concept }: { payload: Record<string, any>; concept: AtelierConcept }) {
  const rule = payload.rule_panel || {};
  return (
    <aside className="grammar-block rule-panel">
      <div className="between">
        {/* Furniture (kickers + link label) is publication French; the rule text below
            stays in the learner's own language. */}
        <div className="t-mono blue">La règle</div>
        <Link className="notebook-link" href={`/grammar?concept=${concept.id}`}>Cahier ↗</Link>
      </div>
      {/* The concept title is already set as the sheet's h1 two rows above; a
          second copy here only repeated it (and, before the server localized
          rule_panel.title, repeated it in English). */}
      <p>{rule.rule}</p>
      {rule.when && <p><strong>Quand :</strong> {rule.when}</p>}
      {rule.pattern && <p><strong>Le schéma :</strong> {rule.pattern}</p>}
      {rule.check && <p><strong>Le contrôle :</strong> {rule.check}</p>}
      <div className="examples">
        {(rule.examples || []).slice(0, 3).map((example: string) => <p key={example}>{example}</p>)}
      </div>
    </aside>
  );
}

function EpreuveBlankPrompt({ prompt, answer }: { prompt: string; answer?: string }) {
  const parts = String(prompt || '').split(/_{2,}/);
  if (parts.length < 2) return <>{prompt}</>;
  return (
    <>
      {parts.map((part, index) => (
        <React.Fragment key={`${part}-${index}`}>
          {part}
          {index < parts.length - 1 && <Blank set={Boolean(answer)}>{answer}</Blank>}
        </React.Fragment>
      ))}
    </>
  );
}

function RecognizePanel({
  payload,
  mode,
  activeItemIndex,
  answers,
  updateAnswer,
  correction,
  submitted,
}: {
  payload: Record<string, any>;
  mode: RecognizeMode;
  activeItemIndex: number;
  answers: Record<string, any>;
  updateAnswer: (key: string, value: any) => void;
  correction: Record<string, any> | null;
  submitted: boolean;
}) {
  const items = payload.recognize?.[mode]?.items || [];
  const itemIndex = safeDrillItemIndex(activeItemIndex, items);
  const item = items[itemIndex] || {};
  const feedback = itemFeedback(item, answers[item.id], correction);
  const wordBankTokens = mode === 'word_bank' ? wordBankTokensFromAnswer(answers[item.id]) : [];
  const sourceTokens = Array.isArray(item.tokens) ? item.tokens.map((token: string) => String(token)) : [];
  return (
    <div className="ep-exercise ep-recognize">
      {mode === 'fill' && (
        <>
          <EpPrompt>
            <EpreuveBlankPrompt prompt={String(item.prompt || '')} answer={answers[item.id]} />
          </EpPrompt>
          <EpOpts>
            {(item.choices || []).map((choice: string) => (
              <EpOpt
                key={choice}
                chosen={answers[item.id] === choice}
                right={submitted && normalizeClient(choice) === normalizeClient(feedback?.target)}
                wrong={submitted && answers[item.id] === choice && !feedback?.correct}
                disabled={submitted}
                onClick={() => updateAnswer(item.id, choice)}
              >{choice}</EpOpt>
            ))}
          </EpOpts>
        </>
      )}
      {mode === 'word_bank' && (
        <>
          <EpPrompt cue={stripExpressPrefix(item.meaning_cue) || item.prompt}>
            <EpSetLine empty={wordBankTokens.length === 0}>
              {wordBankTokens.map((token, selectedIndex) => (
                <EpSlug
                  key={`${token}-${selectedIndex}`}
                  set
                  disabled={submitted}
                  onClick={() => updateAnswer(item.id, wordBankTokens.filter((_, tokenIndex) => tokenIndex !== selectedIndex))}
                >{token}</EpSlug>
              ))}
            </EpSetLine>
          </EpPrompt>
          <div className="ep-typecase" aria-label="Caractères disponibles">
            {sourceTokens.map((token: string, tokenIndex: number) => {
              const used = wordBankTokenIsUsed(wordBankTokens, sourceTokens, token, tokenIndex);
              return (
                <EpSlug
                  key={`${token}-${tokenIndex}`}
                  spent={used}
                  disabled={submitted || used}
                  onClick={() => updateAnswer(item.id, [...wordBankTokens, token])}
                >{token}</EpSlug>
              );
            })}
          </div>
        </>
      )}
      {mode === 'classify' && (
        <>
          <EpPrompt>{item.prompt}</EpPrompt>
          <EpCases boxes={(item.labels || []).map((label: string) => ({
            label,
            slugs: [
              <EpOpt
                key={label}
                chosen={answers[item.id] === label}
                right={submitted && normalizeClient(label) === normalizeClient(feedback?.target)}
                wrong={submitted && answers[item.id] === label && !feedback?.correct}
                disabled={submitted}
                onClick={() => updateAnswer(item.id, label)}
              >Placer ici</EpOpt>,
            ],
          }))} />
        </>
      )}
    </div>
  );
}

function TransformPanel({
  payload,
  activeItemIndex,
  answers,
  updateAnswer,
  correction,
  submitted,
}: {
  payload: Record<string, any>;
  activeItemIndex: number;
  answers: Record<string, any>;
  updateAnswer: (key: string, value: any) => void;
  correction: Record<string, any> | null;
  submitted: boolean;
}) {
  const items = payload.transform?.items || [];
  const itemIndex = safeDrillItemIndex(activeItemIndex, items);
  const item = items[itemIndex] || {};
  return (
    <div className="ep-exercise ep-transform">
      <EpPrompt cue={item.instruction}>
        {item.source}
      </EpPrompt>
      <textarea
        className="ep-composed-input"
        value={answers[item.id] || ''}
        onChange={(event) => updateAnswer(item.id, event.target.value)}
        placeholder="Composez la nouvelle ligne…"
        readOnly={submitted}
      />
      {submitted && (() => {
        const corrected = correction?.corrected_answer;
        const correctedForItem = corrected && typeof corrected === 'object' ? corrected[item.id] : undefined;
        const modelText = String(correctedForItem || item.expected_answer || answers[item.id] || '').trim();
        return modelText ? <EpreuveModelAudio text={modelText} /> : null;
      })()}
    </div>
  );
}

function itemFeedback(item: any, learner: any, correction: Record<string, any> | null) {
  if (!correction) return null;
  const corrected = correction.corrected_answer || {};
  const target = typeof corrected === 'object' ? corrected[item.id] : item.correct_answer || item.expected_answer;
  const learnerText = Array.isArray(learner) ? learner.join(' ') : String(learner || '');
  const targetText = String(target || item.correct_answer || item.expected_answer || item.correct_label || '');
  const errata: AtelierErratum[] = Array.isArray(correction.errata) ? correction.errata : [];
  const hasItemScopedErrata = errata.some((erratum) => Boolean(String(erratum.item_id || '').trim()));
  const targetNorm = normalizeClient(targetText);
  const learnerNorm = normalizeClient(learnerText);
  const matchingErrata = errata.filter((erratum: AtelierErratum) => {
    const erratumItemId = String(erratum.item_id || '').trim();
    if (erratumItemId) return erratumItemId === item.id;
    if (hasItemScopedErrata) return false;
    const errTarget = normalizeClient(erratum.corrected_target);
    const errLearner = normalizeClient(erratum.learner_text);
    // When the erratum names the submitted form, it must match THIS card's answer.
    // Otherwise an erratum from a sibling item that happens to share the same target
    // (e.g. two fill blanks both corrected to "de") would leak onto this card and
    // show as a confusing extra "fix".
    if (errLearner && errTarget) {
      return Boolean(learnerNorm) && errLearner === learnerNorm && errTarget === targetNorm;
    }
    if (errLearner) {
      return Boolean(learnerNorm) && errLearner === learnerNorm && (!errTarget || errTarget === targetNorm);
    }
    return Boolean(errTarget && errTarget === targetNorm);
  });
  // Trust the server's per-item errata rather than re-deriving correctness from
  // a naive client join/compare: word-bank tokens join with plain spaces (e.g.
  // "J' ai" for "J'" + "ai"), which normalizeClient doesn't collapse the way the
  // backend's French-elision-aware normalizer does — a correct answer with an
  // elidable apostrophe (j', c', l', ...) would otherwise show as wrong.
  const assessment = seanceAssessment(correction);
  const correct = matchingErrata.length === 0 && (assessment === 'correct' || (
    assessment === 'needs_work' && correction.errata?.some((error: AtelierErratum) => error.item_id && error.item_id !== item.id) && typeof corrected === 'object' && !!targetText &&
    normalizeClient(learnerText).replace(/['’]\s+/g, "'") === normalizeClient(targetText).replace(/['’]\s+/g, "'")
  ));
  return {
    correct,
    learner: learnerText,
    target: targetText,
    why: printableWhy(matchingErrata[0]?.why_wrong) || undefined,
    repair: matchingErrata[0]?.repair_hint ?? undefined,
    issues: matchingErrata,
    unscored: assessment === 'pending' || assessment === 'unavailable',
  };
}

type InlineFeedbackModel = {
  correct: boolean;
  unscored?: boolean;
  learner?: string;
  target?: string;
  why?: string;
  repair?: string;
  issues?: AtelierErratum[];
} | null;

function correctionTargetText(value: unknown): string {
  if (!value) return '';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(correctionTargetText).filter(Boolean).join(' ');
  if (typeof value === 'object') {
    return Object.values(value as Record<string, unknown>).map(correctionTargetText).filter(Boolean).join(' ');
  }
  return String(value);
}

function feedbackFromFreeformCorrection(correction: Record<string, any> | null, fallbackTarget = '', learner = ''): InlineFeedbackModel {
  if (!correction) return null;
  const allErrata: AtelierErratum[] = Array.isArray(correction?.errata) ? correction.errata : [];
  // Task compliance is part of the assessment and must remain visible.
  const errata = allErrata;
  // Show the learner's whole line rewritten cleanly. The full rewrite lives in
  // corrected_answer (reliable); a per-erratum corrected_target is sometimes a
  // rule pattern or a hedge like "c'était/ce serait? depending on…", so only use
  // it when corrected_answer is unavailable or unchanged.
  const cleanRewrite = correctionTargetText(correction?.corrected_answer);
  const rewriteDiffers = !!cleanRewrite && normalizeClient(cleanRewrite) !== normalizeClient(learner);
  const shownTarget = rewriteDiffers ? cleanRewrite : (errata[0]?.corrected_target || cleanRewrite || fallbackTarget);
  const whyLines = errata.map((item) => String(item?.why_wrong || '').trim()).filter(Boolean);
  const assessment = seanceAssessment(correction);
  const correct = assessment === 'correct';
  const taskOnly = !rewriteDiffers && (errata.length === 0 || errata.every((item) => item.task_error_type === 'task_compliance'));
  // One clean before/after for the whole line, with each error explained in the
  // note — instead of one messy before/after per erratum.
  const issues: AtelierErratum[] = correct ? [] : [{
    display_label: errata.length > 1 ? `${errata.length} corrections` : (errata[0]?.display_label || 'Ligne corrigée'),
    learner_text: learner,
    corrected_target: taskOnly ? '' : (rewriteDiffers ? shownTarget : (errata[0]?.corrected_target || '')),
    why_wrong: whyLines.join(' ') || 'La réponse ne remplit pas encore la consigne. Relisez la situation et réessayez avec la règle indiquée.',
    task_error_type: taskOnly ? 'task_compliance' : undefined,
  } as AtelierErratum];
  if (!correct && !taskOnly) {
    issues.push(...errata.filter((item) => item.task_error_type === 'task_compliance').map((item) => ({ ...item, corrected_target: '' })));
  }
  return {
    correct,
    unscored: assessment === 'unavailable' || assessment === 'pending',
    learner,
    target: shownTarget,
    why: whyLines.join(' ') || undefined,
    repair: errata[0]?.repair_hint || undefined,
    issues,
  };
}

function feedbackForExercise(
  round: RoundName,
  mode: RecognizeMode,
  activeSet: Record<string, any> | null,
  activeItemIndex: number,
  currentAnswers: Record<string, any>,
  correction: Record<string, any> | null,
): InlineFeedbackModel {
  if (!activeSet || !correction) return null;
  if (round === 'recognize') {
    const items = activeSet.recognize?.[mode]?.items || [];
    const item = items[safeDrillItemIndex(activeItemIndex, items)] || {};
    return itemFeedback(item, currentAnswers[item.id], correction);
  }
  if (round === 'transform') {
    const items = activeSet.transform?.items || [];
    const item = items[safeDrillItemIndex(activeItemIndex, items)] || {};
    return itemFeedback(item, currentAnswers[item.id], correction);
  }
  if (round === 'sentence' || round === 'speak' || round === 'conversation') {
    const item = activeSet.output_ladder?.[round]?.items?.[0] || {};
    return feedbackFromFreeformCorrection(correction, item.example_answer || '', String(currentAnswers.text || ''));
  }
  return feedbackFromFreeformCorrection(correction, '', String(currentAnswers.text || ''));
}

function feedbackRuleLine(activeSet: Record<string, any> | null, activeConcept: AtelierConcept | null) {
  // Publication furniture is French, and the title is the French one: the server
  // now localizes rule_panel.title, and title_fr is the concept-level fallback.
  // This used to print "Rule: Si type 1: present condition, future result".
  const title = String(
    activeSet?.rule_panel?.title
    || activeConcept?.title_fr
    || activeConcept?.atelier_blueprint?.display_title
    || activeConcept?.name
    || '',
  ).trim();
  return title ? `La règle · ${title}` : undefined;
}

// "Recopie la correction" is a line-level exercise: retyping a one-word fill
// option or a classify label teaches nothing, so the typed repair only appears
// when the corrected target is an actual sentence.
function isRepairableLine(target: string): boolean {
  const trimmed = target.trim();
  if (!trimmed) return false;
  const words = trimmed.split(/\s+/).length;
  return words >= 3 || (words >= 2 && /[.!?…]$/.test(trimmed));
}

function browserSpeak(text: string, onDone: () => void) {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
    onDone();
    return;
  }
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'fr-FR';
  utterance.onend = onDone;
  utterance.onerror = onDone;
  window.speechSynthesis.speak(utterance);
}

function EpreuveModelAudio({ text }: { text: string }) {
  const [playing, setPlaying] = useState(false);
  const value = String(text || '').trim();
  if (!value) return null;
  const play = async () => {
    if (playing) return;
    setPlaying(true);
    try {
      const audio = await apiService.synthesizeSpeech(value);
      const blob = new Blob([audio], { type: 'audio/mpeg' });
      const url = URL.createObjectURL(blob);
      const player = new Audio(url);
      player.onended = () => { URL.revokeObjectURL(url); setPlaying(false); };
      player.onerror = () => { URL.revokeObjectURL(url); browserSpeak(value, () => setPlaying(false)); };
      await player.play();
    } catch (error) {
      console.error(error);
      browserSpeak(value, () => setPlaying(false));
    }
  };
  return <EpListen fr={value} playing={playing} onPlay={play} />;
}

function EpreuveWiringStyles() {
  return (
    <style jsx global>{`
      .ep .ep-exercise { display: grid; gap: 14px; padding: 4px 0 2px; }
      .ep .ep-typecase { display: flex; flex-wrap: wrap; gap: 8px; padding: 12px; border: 1px solid var(--app-ink); background: var(--app-sheet); }
      .ep .ep-composed-input { width: 100%; min-height: 122px; resize: vertical; border: 1px solid var(--app-ink); background: var(--app-paper); color: var(--app-ink); padding: 13px 14px; font: 400 17px/1.45 var(--app-serif); outline: none; box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ep-channel) 35%, transparent); }
      .ep .ep-composed-input:focus { border-color: var(--app-blue); box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--app-blue) 30%, transparent); }
      .ep .ep-composed-input::placeholder { color: var(--app-ink-3); font-style: italic; }
      .ep .ep-output .word-count, .ep .ep-produce-panel .word-count { margin-top: -5px; font: 800 8px/1 var(--app-grotesk); letter-spacing: .12em; text-transform: uppercase; color: var(--app-ink-3); }
      .ep .ep-character-byline { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; border-top: 1px solid var(--app-ink); border-bottom: 1px solid var(--app-ink); padding: 8px 0; }
      .ep .ep-character-byline span { font: 700 18px/1.1 var(--app-serif); font-style: italic; color: var(--app-ink); }
      .ep .ep-character-byline em, .ep .ep-world-reply > span { font: 900 8px/1 var(--app-grotesk); letter-spacing: .12em; text-transform: uppercase; color: var(--app-blue); }
      .ep .ep-world-reply { margin: 10px 0 0; border-left: 3px solid var(--app-blue); background: var(--app-sheet); padding: 12px 14px; color: var(--app-ink); }
      .ep .ep-world-reply p { margin: 6px 0 0; font: 500 17px/1.35 var(--app-serif); }
      .ep .ep-feedback { margin-top: 20px; }
      .ep .ep-feedback .ep-foot { padding: 0; margin-top: 16px; }
      .ep .ep-feedback .ep-correct { margin-top: 4px; }
      .ep .ep-rulenote { margin-top: 12px; font-family: var(--ep-mono); font-size: 9px; letter-spacing: .06em; text-transform: uppercase; color: var(--app-ink-3); }
      .ep .ep-notebook-add { margin-top: 14px; border: 1px solid var(--app-ink); background: var(--app-sheet); padding: 11px 13px; }
      .ep .ep-notebook-add .nh { display: block; font-family: var(--ep-mono); font-size: 8.5px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--ep-bon); margin-bottom: 7px; }
      .ep .ep-notebook-add ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 4px; }
      .ep .ep-notebook-add li { font-family: var(--app-serif); font-size: 15px; line-height: 1.3; color: var(--app-ink); }
      .ep .ep-notebook-add li b { font-weight: 700; }
      .ep .ep-notebook-add li em { font-style: italic; color: var(--app-ink-3); }
      .ep .ep-fb-links { display: flex; justify-content: center; gap: 20px; margin-top: 11px; }
      .ep .ep-fb-links button { border: 0; background: none; padding: 4px 2px; color: var(--app-ink-3); font: 700 9px/1 var(--app-grotesk); letter-spacing: .12em; text-transform: uppercase; cursor: pointer; }
      .ep .ep-fb-links button:hover { color: var(--app-ink); }
      .ep .ep-lock { margin: 15px 0 0; border: 1px solid var(--app-ink); background: var(--app-sheet); }
      .ep-recap { position: relative; width: min(100%, 510px); max-height: min(90dvh, 780px); overflow: auto; border: 1px solid var(--app-ink); border-radius: 0; box-shadow: 0 16px 38px color-mix(in srgb, var(--app-ink) 20%, transparent); }
      .ep-recap-close { position: absolute; z-index: 2; right: 10px; top: 10px; width: 30px; height: 30px; border: 1px solid var(--app-ink); background: var(--app-paper); color: var(--app-ink); font-size: 20px; line-height: 1; }
      .ep-recap .ep-bat-stage { padding-top: 26px; }
      .ep-recap-rewards { display: flex; align-items: center; gap: 18px; margin-top: 18px; padding: 15px 0; border-top: 1px solid var(--app-paper-3); border-bottom: 1px solid var(--app-paper-3); }
      .ep-recap-rewards .ep-mint { flex: 1; }
      @media (max-width: 480px) { .ep-recap { width: calc(100vw - 28px); } .ep .ep-composed-input { min-height: 110px; } }
    `}</style>
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
  const promptText = outputLadderPrompt(payload, item, round);
  const character = item.character || {};
  const worldReply = correction?.world_reply || {};

  const transcribeAudio = async (blob: Blob) => {
    setIsTranscribing(true);
    try {
      const transcript = await apiService.transcribeAudio(blob);
      if (transcript.trim()) {
        updateAnswer(transcript.trim());
      } else {
        toast('Aucune parole détectée.');
      }
    } catch (error) {
      console.error(error);
      toast.error('L’enregistrement n’a pas pu être transcrit.');
    } finally {
      setIsTranscribing(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = createAudioMediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        const audioBlob = recordedAudioBlob(chunksRef.current, recorder);
        stream.getTracks().forEach((track) => track.stop());
        void transcribeAudio(audioBlob);
      };
      recorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error(error);
      toast.error('L’accès au micro a échoué.');
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

  const meta = OUTPUT_LADDER_META[round];
  return (
    <div className={`ep-exercise ep-output ep-output-${round}`}>
      {round === 'conversation' && character.name && (
        <div className="ep-character-byline" aria-label={`Conversation avec ${character.name}`}>
          <span>{character.name}</span>
          <em>{String(character.register || 'vous').toUpperCase()}</em>
        </div>
      )}
      <EpPrompt cue={item.instruction || meta.instruction}>
        {promptText}
      </EpPrompt>
      {round === 'speak' && (
        <EpRecord
          status={isTranscribing ? 'transcribing' : isRecording ? 'recording' : 'idle'}
          disabled={submitted}
          onToggle={toggleRecording}
        />
      )}
      <textarea
        value={answer}
        onChange={(event) => updateAnswer(event.target.value)}
        readOnly={submitted}
        className="ep-composed-input"
        placeholder={
          round === 'speak'
            ? 'Vos mots apparaissent ici, ou composez-les.'
            : round === 'conversation'
              ? 'Composez votre réponse…'
              : 'Composez votre ligne…'
        }
      />
      <div className="word-count">
        {wordRangeLabel(wordCount(answer), item.min_words, item.max_words)}
      </div>
      {submitted && (() => {
        const modelText = String(seanceAssessment(correction) === 'correct' ? correction?.corrected_answer || item.example_answer || '' : '').trim();
        return modelText ? <EpreuveModelAudio text={modelText} /> : null;
      })()}
      {round === 'conversation' && submitted && worldReply.text && (
        <blockquote className="ep-world-reply">
          <span>{worldReply.character?.name || character.name}</span>
          <p>{worldReply.text}</p>
        </blockquote>
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
}: {
  concepts: AtelierConcept[];
  exerciseSets: AtelierExerciseSet[];
  payload: Record<string, any>;
  targetVocabulary?: VocabularyRecommendationItem[];
  answer: string;
  updateAnswer: (value: string) => void;
  correction: Record<string, any> | null;
  submitted: boolean;
}) {
  const produce = payload.produce || {};
  const requirements = (produce.requirements || []).map((req: any) => ({
    label: concepts.find((concept) => concept.id === req.concept_id)?.title_fr || req.label,
    count: req.target_count || 1,
  }));
  const sourceFragment = String(produce.source_fragment || '').trim();
  const promptText = String(produce.prompt || '').trim();
  return (
    <div className="ep-exercise ep-produce-panel">
      <EpPrompt cue={sourceFragment ? `« ${sourceFragment} »` : undefined}>
        {promptText || 'La consigne de composition est indisponible.'}
      </EpPrompt>
      <div className="target-chips">
        {requirements.map((req: { label: string; count: number }) => <span key={req.label}>{req.count} × {req.label}</span>)}
      </div>
      {Boolean(targetVocabulary?.length) && (
        <div className="target-word-strip" aria-label="Lexique visé pour ce paragraphe">
          {(targetVocabulary || []).slice(0, 5).map((item) => (
            <span key={`${item.word_id}-${item.word}`}>
              {item.word}
              <em>{vocabularyTranslation(item)}</em>
            </span>
          ))}
        </div>
      )}
      <textarea className="ep-composed-input" value={answer} onChange={(event) => updateAnswer(event.target.value)} placeholder="Composez votre paragraphe ici…" readOnly={submitted} />
      <div className="word-count">{wordRangeLabel(wordCount(answer), produce.min_words, produce.max_words)}</div>
    </div>
  );
}

function RecapModal({
  recap,
  concepts,
  filedEarly = false,
  recommendation,
  onRecommendedAction,
  onClose,
}: {
  recap: Record<string, any>;
  concepts: AtelierConcept[];
  /** The learner closed the edition before the last drill; say so plainly. */
  filedEarly?: boolean;
  recommendation: RecommendedAction;
  onRecommendedAction: () => void;
  onClose: () => void;
}) {
  const reviewTotal = recommendation.kind === 'review' ? recommendation.errataDue + recommendation.vocabularyDue : 0;
  const nextLabel = recapActionLabel(recommendation, reviewTotal);
  const practiced = concepts.slice(0, 3).map((concept) => displayConceptTitle(concept));
  const minted = Array.isArray(recap.minted_collectibles) ? recap.minted_collectibles as AtelierCollectible[] : [];
  const logoTokens = minted.filter((item) => item.kind === 'logo_token');
  const giltSeal = minted.find((item) => item.kind === 'gilt_seal');
  const attempts = Math.max(0, Number(recap.attempts || 0));
  const strengthened = Math.max(0, Number(recap.strengthened || concepts.length || 0));
  const errataLogged = Math.max(0, Number(recap.errata_logged || 0));
  const phrase = recap.phrase_of_day || null;
  const recapErrata = Array.isArray(recap.errata) ? recap.errata : [];
  const proofLines: Array<{ fr: React.ReactNode; tag: string; re: boolean }> = recapErrata.slice(0, 4).map((item: Record<string, any>, index: number) => ({
    fr: <><del>{item.learner_text || '—'}</del> <ins>{item.corrected_target || 'corrigé'}</ins></>,
    tag: item.display_label || `Correction ${index + 1}`,
    re: true,
  }));
  if (!proofLines.length) {
    proofLines.push(...(practiced.length ? practiced : ['La séance']).map((item) => ({ fr: item, tag: 'ligne réglée', re: false })));
  }
  return (
    <div className="recap-overlay">
      <section className="ep ep-recap av2" aria-label="L’épreuve de la séance">
        <LEpreuveStyles />
        <EpreuveWiringStyles />
        <button type="button" className="ep-recap-close" onClick={onClose} aria-label="Fermer l’épreuve">×</button>
        <EpBatStage
          sub={giltSeal
            ? 'Séance sans faute, frappée en doré.'
            : filedEarly
              ? 'Édition close en avance — tout ce qui est classé ci-dessous compte.'
              : 'Les lignes sont prêtes pour l’édition de demain.'}
        />
        <EpRecapHead date={formatAtelierDatestamp().replace('Classée · ', '')} />
        <div className="ep-recap-body">
          <EpTally items={[
            { n: attempts, l: 'lignes réglées' },
            { n: strengthened, l: 'concepts affermis' },
            { n: errataLogged, l: 'errata classés' },
          ]} />
          <EpProof lines={proofLines} />
          {phrase?.text && <EpPhrase quote={phrase.text} by={phrase.byline || 'L’élève de l’Atelier'} />}
          <div className="ep-recap-rewards">
            <EpSeal gilt={Boolean(giltSeal)} stamp />
            {(logoTokens.length > 0 || giltSeal) && (
              <EpMint
                tokens={Math.max(1, logoTokens.length)}
                note={giltSeal ? 'Sceau doré frappé pour une séance sans faute.' : `${logoTokens.length} jeton${logoTokens.length > 1 ? 's' : ''} ajouté${logoTokens.length > 1 ? 's' : ''} à l’atelier.`}
              />
            )}
          </div>
          <EpStreak was={recap.streak_before || 0} now={recap.streak_after || 1} on={Math.min(5, Number(recap.streak_after || 1))} />
          <EpHandoff
            // recapActionLabel returns a verb phrase ("Réviser maintenant",
            // "Ouvrir la mission"), so it IS the button; the old prop prefixed
            // it with "Lire" and printed "Lire Réviser maintenant".
            label={nextLabel?.action}
            onRead={nextLabel ? onRecommendedAction : onClose}
            onHome={onClose}
          />
        </div>
      </section>
    </div>
  );
}

function recapActionLabel(action: RecommendedAction, reviewTotal: number) {
  if (action.kind === 'review') {
    return {
      title: `${reviewTotal} élément${reviewTotal === 1 ? '' : 's'} à réviser`,
      copy: 'Videz la file des reprises avant les branches facultatives pour garder la grammaire du jour fraîche.',
      action: 'Réviser maintenant',
    };
  }
  if (action.kind === 'mission') {
    return {
      title: 'L’utiliser dans une mission',
      copy: 'Le passage vers le réel est ici : réemployez la séance terminée dans une situation concrète.',
      action: 'Ouvrir la mission',
    };
  }
  if (action.kind === 'studio') {
    return {
      title: 'Le dire à voix haute',
      copy: 'La règle que vous venez de poser tient-elle dans une vraie conversation ? Cinq minutes au studio.',
      action: 'Ouvrir le studio',
    };
  }
  if (action.kind === 'library') {
    if (!STORY_FEATURE_VISIBLE) return null;
    return {
      title: action.bookTitle ? `Continuer ${action.bookTitle}` : 'Continuer le livre de la bibliothèque',
      copy: action.title
        ? `Épisode ${action.episodeIndex + 1} : ${action.title}`
        : 'Lire le passage suivant et répondre aux questions qui en découlent.',
      action: 'Continuer le livre',
    };
  }
  if (action.kind === 'serial') {
    return {
      title: action.episodeKind === 'mission' ? 'Le monde attend votre réponse' : 'Continuer le feuilleton',
      copy: action.episodeKind === 'mission'
        ? 'Votre prochain message en français fait avancer le fil commun.'
        : 'Voyez la conséquence de votre texte, puis attrapez le prochain suspense.',
      action: action.episodeKind === 'mission' ? 'Répondre' : 'Ouvrir le feuilleton',
    };
  }
  if (action.kind === 'feuilleton') {
    return {
      title: 'Lire la branche du Feuilleton',
      copy: 'Portez la même grammaire dans la scène du Feuilleton pendant qu’elle est encore fraîche.',
      action: 'Ouvrir le Feuilleton',
    };
  }
  if (action.kind === 'rest') {
    return {
      title: 'Édition terminée',
      copy: 'Tout le parcours est terminé. Revenez à la carte du jour et laissez reposer.',
      action: 'Retour au jour',
    };
  }
  return null;
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
        --sheet: var(--app-sheet);
        --muted: var(--app-ink-3);
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
      .serial-welcome-backdrop {
        position: fixed;
        inset: 0;
        z-index: 80;
        display: grid;
        place-items: center;
        padding: 18px;
        background: rgba(20, 17, 13, 0.68);
      }
      .serial-welcome {
        width: min(520px, 100%);
        border: 2px solid var(--ink);
        background: var(--paper);
        box-shadow: 0 18px 42px color-mix(in srgb, var(--ink) 22%, transparent);
        padding: 24px;
      }
      .serial-welcome h2 {
        margin: 8px 0 10px;
        font-family: var(--serif);
        font-size: 38px;
        font-style: italic;
        line-height: .98;
        letter-spacing: 0;
      }
      .serial-welcome p {
        margin: 0;
        color: var(--ink-2);
        line-height: 1.45;
      }
      .serial-welcome-steps {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;
        margin: 18px 0;
      }
      .serial-welcome-steps span {
        display: grid;
        gap: 6px;
        border: 1.5px solid var(--ink);
        background: var(--paper-2);
        padding: 10px;
        font-size: 12px;
        font-weight: 900;
      }
      .serial-welcome-steps b {
        display: grid;
        place-items: center;
        width: 24px;
        height: 24px;
        background: var(--yellow);
        border: 1.5px solid var(--ink);
      }
      .serial-welcome button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        width: 100%;
        border: 2px solid var(--ink);
        background: var(--red);
        color: #fff;
        min-height: 52px;
        font-weight: 900;
        letter-spacing: .13em;
        text-transform: uppercase;
      }
      .serial-welcome-head {
        display: flex;
        align-items: start;
        justify-content: space-between;
        gap: 12px;
      }
      /* The close control and the "later" control are escapes, not calls to
         action: they must be reachable at 44px without shouting. */
      .serial-welcome button.serial-welcome-close {
        flex: none;
        width: 44px;
        min-height: 44px;
        margin: -10px -10px 0 0;
        border: 0;
        background: transparent;
        color: var(--ink);
      }
      .serial-welcome button.serial-welcome-later {
        margin-top: 10px;
        border: 0;
        background: transparent;
        color: var(--ink-2);
        min-height: 44px;
        font-weight: 700;
        letter-spacing: .1em;
      }
      .serial-welcome button:focus-visible {
        outline: 2px solid var(--ink);
        outline-offset: 2px;
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
      .atelier-cache-note { max-width: 430px; margin: 6px auto -2px; padding: 0 18px; color: var(--app-ink-3); font: italic 12px/1.35 var(--app-serif); }
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
      .week-ribbon {
        position: absolute;
        top: 4.5%;
        left: 32%;
        border: 1px dashed var(--ink-3);
        padding: 5px 8px;
        color: var(--ink-3);
        background: color-mix(in srgb, var(--paper) 88%, transparent);
        font-size: 10px;
        font-weight: 500;
        letter-spacing: .16em;
        text-transform: uppercase;
        white-space: nowrap;
      }
      .node-check {
        width: 46px;
        height: 46px;
        display: grid;
        place-items: center;
        margin: 0 auto 8px;
        border: 1px solid var(--ink);
      }
      .node-check.dark {
        background: var(--ink);
        color: var(--paper);
      }
      .node-check.blue {
        border-radius: 999px;
        background: var(--blue);
        color: #fff;
      }
      .node-check.blue.hollow {
        background: var(--paper);
        border-color: var(--ink-3);
        color: transparent;
      }
      .node-check svg {
        width: 20px;
        height: 20px;
      }
      .monday-node {
        top: 10%;
        left: 16%;
        transform: translate(-50%, 0);
      }
      .tuesday-node {
        top: 31%;
        left: 75%;
        transform: translate(-50%, 0);
      }
      .today-square {
        position: relative;
        width: 58px;
        height: 58px;
        display: grid;
        place-items: center;
        margin: 0 auto 9px;
        border: 1.5px solid var(--ink);
        background: var(--yellow);
      }
      .today-square::after {
        content: "";
        position: absolute;
        z-index: -1;
        right: -8px;
        bottom: -8px;
        width: 100%;
        height: 100%;
        background: var(--red);
      }
      .today-square i {
        width: 17px;
        height: 17px;
        background: var(--ink);
      }
      .story-rubric {
        display: block;
        color: var(--blue);
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .1em;
        text-transform: uppercase;
      }
      .story-byline {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 12px;
        min-width: 0;
      }
      .story-avatar {
        width: 32px;
        height: 32px;
        display: grid;
        place-items: center;
        background: var(--blue);
        color: #fff;
        border: 1px solid var(--ink);
        font-family: var(--serif);
        font-size: 18px;
        font-style: italic;
        font-weight: 700;
        flex: 0 0 auto;
      }
      .story-byline i {
        width: 9px;
        height: 9px;
        background: var(--blue);
        border: 1px solid var(--ink);
        flex: 0 0 auto;
      }
      .story-byline b {
        min-width: 0;
        overflow: hidden;
        color: var(--ink);
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .12em;
        text-overflow: ellipsis;
        text-transform: uppercase;
        white-space: nowrap;
      }
      .story-status {
        display: block;
        margin-top: 9px;
        color: var(--ink-3);
        font-size: 8px;
        font-weight: 900;
        letter-spacing: .1em;
        text-transform: uppercase;
      }
      .review-node {
        top: 74%;
        left: 74%;
        transform: translate(-50%, 0);
        border: 0;
        background: transparent;
        padding: 0;
        cursor: pointer;
      }
      .review-node span {
        display: block;
        width: 48px;
        height: 44px;
        margin: 0 auto 7px;
        clip-path: polygon(50% 0, 100% 100%, 0 100%);
        background: var(--ink-3);
        position: relative;
      }
      .review-node span::after {
        content: "";
        position: absolute;
        inset: 3px 3px 4px;
        clip-path: inherit;
        background: var(--paper);
      }
      .review-node.due span::after {
        background: var(--sheet);
      }
      .tomorrow-node {
        top: 83%;
        left: 35%;
        transform: translate(-50%, 0);
      }
      .tomorrow-node span {
        display: block;
        width: 44px;
        height: 44px;
        margin: 0 auto 8px;
        border: 1.5px solid var(--ink-3);
        border-radius: 999px;
        background: var(--paper);
      }
      .caught-mark {
        width: 68px;
        height: 68px;
        display: grid;
        place-items: center;
        margin: 72px auto 18px;
        border: 1.5px solid var(--ink);
        border-radius: 999px;
        background: var(--blue);
        color: #fff;
      }
      .caught-mark svg {
        width: 28px;
        height: 28px;
      }
      .caught-ledger {
        margin: 28px 10px 0;
        border-top: 1px solid var(--ink);
      }
      .caught-ledger div {
        min-height: 52px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        border-bottom: 1px solid var(--paper-3);
      }
      .caught-ledger span {
        color: var(--ink-3);
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .caught-ledger b {
        font-size: 12px;
        font-weight: 900;
        letter-spacing: .08em;
        text-transform: uppercase;
      }
      .caught-doors {
        display: grid;
        gap: 10px;
        margin: auto 10px 0;
      }
      .caught-doors a {
        min-height: 56px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border: 1px solid var(--ink);
        background: var(--sheet);
        color: var(--ink);
        padding: 0 14px;
        text-decoration: none;
        font-size: 12px;
        font-weight: 900;
        letter-spacing: .08em;
        text-transform: uppercase;
      }
      .caught-doors svg {
        width: 17px;
        height: 17px;
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
      .cefr-bars {
        display: grid;
        gap: 7px;
      }
      .cefr-mini div {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        font-family: var(--mono);
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .1em;
        text-transform: uppercase;
        color: var(--ink-2);
      }
      .cefr-mini i {
        display: block;
        height: 8px;
        margin-top: 4px;
        border: 1px solid var(--ink);
        background: var(--paper);
      }
      .cefr-mini em {
        display: block;
        height: 100%;
        background: var(--blue);
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
        box-shadow: inset 0 -3px 0 color-mix(in srgb, var(--red) 48%, transparent);
      }
      .plate.review.live {
        background: var(--red);
        color: #fff;
      }
      .plate.vocabulary .badge {
        background: var(--blue);
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
      .vocab-open-wrap {
        margin-top: 12px;
        display: grid;
        gap: 12px;
      }
      .vocab-open {
        min-height: 64px;
        display: grid;
        grid-template-columns: 18px minmax(0, 1fr);
        align-items: center;
        gap: 12px;
        border: 1px solid var(--ink);
        background: var(--sheet);
        padding: 13px 15px;
      }
      .vocab-open .dot.vocab {
        width: 14px;
        height: 14px;
        background: var(--blue);
        border: 1px solid var(--ink);
      }
      .vocab-open .lab {
        min-width: 0;
      }
      .vocab-open .lab b {
        display: block;
        font-size: 13px;
        font-weight: 800;
      }
      .vocab-open .lab em {
        display: block;
        margin-top: 1px;
        font-style: normal;
        font-size: 10px;
        font-weight: 800;
        letter-spacing: .1em;
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
        box-shadow: inset 4px 0 0 var(--red);
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
        .story-rubric {
          font-size: 8px;
          letter-spacing: .09em;
        }
        .story-byline {
          gap: 7px;
          margin-top: 10px;
        }
        .story-avatar {
          width: 28px;
          height: 28px;
          font-size: 16px;
        }
        .story-byline b {
          font-size: 9px;
          letter-spacing: .08em;
        }
        .review-node {
          top: 76%;
          left: 72%;
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
        box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 24%, transparent);
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
        box-shadow: inset 0 -3px 0 color-mix(in srgb, var(--ink) 28%, transparent);
      }
      button.roadmap-primary-button:active:not(:disabled),
      button.roadmap-retry-button:active:not(:disabled) {
        transform: translate(2px, 2px);
        box-shadow: inset 0 -1px 0 color-mix(in srgb, var(--ink) 20%, transparent);
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
        box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 22%, transparent);
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
        box-shadow: inset 0 -3px 0 color-mix(in srgb, var(--red) 48%, transparent);
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
        box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 22%, transparent);
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
        box-shadow: inset 5px 0 0 var(--red);
      }
      .roadmap-branch-card:hover {
        opacity: 1;
        transform: translate(-2px, -2px);
        box-shadow: inset 0 -3px 0 color-mix(in srgb, var(--ink) 28%, transparent);
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
      .edition-serial {
        margin-top: var(--phone-section-gap);
      }
      .edition-today {
        display: grid;
        gap: 16px;
        margin-top: var(--phone-section-gap);
      }
      .edition-progress { display: grid; gap: 6px; }
      .edition-progress-label {
        font-family: var(--mono); font-size: 10px; font-weight: 900;
        letter-spacing: .14em; text-transform: uppercase; color: var(--ink-3);
      }
      .edition-progress-bar { height: 5px; background: var(--paper-2); }
      .edition-progress-bar i { display: block; height: 100%; background: var(--ink); }
      .edition-hero {
        display: grid; gap: 4px; width: 100%; text-align: left;
        border: 1px solid var(--ink); background: var(--paper);
        box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 22%, transparent); padding: 16px; cursor: pointer;
      }
      .edition-hero:disabled { opacity: .5; cursor: not-allowed; box-shadow: none; }
      .edition-hero-kicker {
        font-family: var(--mono); font-size: 9px; font-weight: 900;
        letter-spacing: .14em; text-transform: uppercase; color: var(--red);
      }
      .edition-hero-title {
        font-family: var(--serif); font-style: italic; font-size: 23px; line-height: 1.1;
      }
      .edition-hero-meta { font-size: 13px; color: var(--ink-2); }
      .edition-hero-go {
        margin-top: 10px; display: inline-flex; align-items: center; gap: 8px;
        font-family: var(--mono); font-size: 11px; font-weight: 900;
        letter-spacing: .14em; text-transform: uppercase; color: var(--ink);
      }
      .edition-then { display: grid; border: 1px solid var(--paper-2); }
      .edition-then-label {
        padding: 10px 12px 4px; font-family: var(--mono); font-size: 9px; font-weight: 900;
        letter-spacing: .14em; text-transform: uppercase; color: var(--ink-3);
      }
      .edition-row {
        display: flex; align-items: baseline; justify-content: space-between;
        width: 100%; text-align: left; padding: 11px 12px; border-top: 1px solid var(--paper-2);
        background: var(--paper); color: var(--ink); text-decoration: none; cursor: pointer;
      }
      .edition-row-name { font-family: var(--serif); font-style: italic; font-size: 16px; }
      .edition-row-meta {
        font-family: var(--mono); font-size: 10px; font-weight: 900; color: var(--ink-3); font-style: normal;
      }
      .edition-row-meta.accent { color: var(--blue); }
      .also-today {
        display: grid;
        gap: 9px;
        margin-top: 18px;
      }
      .also-label {
        color: var(--ink-3);
        font-family: var(--mono);
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .16em;
        text-transform: uppercase;
      }
      .also-card {
        width: 100%;
        min-height: 68px;
        display: flex;
        align-items: center;
        gap: 12px;
        border: 1px solid var(--ink);
        background: var(--sheet);
        padding: 12px 14px;
        color: var(--ink);
        text-align: left;
        text-decoration: none;
      }
      .also-card:hover:not(:disabled) {
        background: var(--paper);
        box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 22%, transparent);
        transform: translate(-1px, -1px);
      }
      .also-card:disabled {
        cursor: wait;
        opacity: .55;
      }
      .also-card.review {
        background: var(--paper);
      }
      .also-card.vocabulary {
        background: var(--sheet);
      }
      .also-mark {
        background: var(--paper);
        color: var(--ink);
      }
      .also-copy {
        min-width: 0;
        display: grid;
        gap: 4px;
      }
      .also-title {
        display: block;
        min-width: 0;
        font-family: var(--serif);
        font-size: 19px;
        font-style: italic;
        font-weight: 600;
        line-height: 1;
      }
      .also-meta {
        display: block;
        min-width: 0;
        color: var(--ink-3);
        font-family: var(--mono);
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .12em;
        line-height: 1.25;
        text-transform: uppercase;
      }
      .also-arrow {
        width: 18px;
        height: 18px;
        display: grid;
        place-items: center;
        flex: 0 0 auto;
        margin-left: auto;
      }
      .also-arrow svg {
        width: 18px;
        height: 18px;
      }
      .review-dot {
        width: 0;
        height: 0;
        border-style: solid;
        border-width: 0 13px 23px 13px;
        border-color: transparent transparent var(--red) transparent;
        flex: 0 0 auto;
      }
      .vocab-dot {
        width: 18px;
        height: 18px;
        background: var(--blue);
        border: 1px solid var(--ink);
        box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 22%, transparent);
        flex: 0 0 auto;
      }
      .today-plan {
        margin-top: 22px;
        border-top: 1px solid var(--ink);
        border-bottom: 1px solid var(--ink);
      }
      .today-plan summary {
        min-height: 48px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        cursor: pointer;
        font-family: var(--mono);
        font-size: 10px;
        font-weight: 500;
        letter-spacing: .12em;
        text-transform: uppercase;
        list-style: none;
      }
      .today-plan summary::-webkit-details-marker {
        display: none;
      }
      .today-plan summary::after {
        content: "+";
        font-size: 18px;
        line-height: 1;
      }
      .today-plan[open] summary::after {
        content: "−";
      }
      .today-plan-body {
        display: grid;
        gap: 18px;
        padding: 4px 0 22px;
      }
      .plan-note {
        display: flex;
        flex-wrap: wrap;
        gap: 8px 14px;
        color: var(--ink-2);
        font-size: 13px;
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
      /* The séance shell (EpShell → .av2.ep-shell) sizes itself in
         components/epreuve/Epreuve.tsx; the class only names the mode. */
      .atelier-do-mode { max-width: 100%; }
      .do-topbar {
        position: sticky;
        top: 0;
        z-index: 35;
        display: grid;
        grid-template-columns: 44px minmax(0, 1fr) 78px;
        align-items: center;
        gap: 14px;
        min-height: 62px;
        margin: 0 calc(0px - var(--phone-gutter));
        padding: var(--phone-safe-top) var(--phone-gutter) 0;
        border-bottom: 1px solid var(--ink);
        background: color-mix(in srgb, var(--paper) 94%, transparent);
        backdrop-filter: blur(10px);
      }
      .do-close,
      .do-finish,
      .rule-toggle {
        border: 1px solid var(--ink);
        background: var(--paper);
        color: var(--ink);
        display: inline-grid;
        place-items: center;
        font-family: var(--mono);
        font-weight: 500;
        transition: background var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard);
      }
      .do-close {
        width: 38px;
        height: 38px;
        font-size: 26px;
        line-height: 1;
      }
      .do-progress {
        min-width: 0;
        display: grid;
        gap: 6px;
      }
      .do-progress .atelier-progress-bar {
        height: 6px;
      }
      .do-progress span {
        color: var(--ink-3);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-family: var(--mono);
        font-size: 10px;
        font-weight: 500;
        letter-spacing: .08em;
        text-transform: uppercase;
      }
      .do-finish {
        min-height: 38px;
        padding: 0 12px;
        font-size: 10px;
        letter-spacing: .08em;
        text-transform: uppercase;
      }
      .do-finish:disabled {
        opacity: .45;
      }
      .do-close:hover,
      .do-finish:hover:not(:disabled),
      .rule-toggle:hover {
        background: var(--ink);
        color: var(--paper);
      }
      .do-stage {
        min-height: calc(var(--app-viewport-height) - var(--phone-topbar-height));
        display: grid;
        align-content: center;
        padding: var(--phone-section-gap) 0 calc(var(--phone-bottom-nav-space) + 36px);
      }
      .rule-toggle {
        width: 40px;
        height: 40px;
        font-size: 16px;
      }
      .rule-toggle svg {
        width: 18px;
        height: 18px;
      }
      .do-rule-sheet {
        margin-bottom: 18px;
        border-top: 1px solid var(--ink);
        border-bottom: 1px solid var(--ink);
        background: var(--paper-2);
        padding: 14px 0;
      }
      .do-rule-sheet .rule-panel {
        border-left: 0;
        background: transparent;
        padding: 0 16px;
      }
      .rule-bridge {
        margin: 12px 16px 0;
        padding: 10px 0 0;
        border-top: 1px solid var(--paper-3);
        color: var(--ink-2);
        font-size: 13px;
        font-weight: 500;
      }
      .atelier-do-mode .exercise-frame {
        min-height: 0;
        padding: 0;
        border: 0;
        background: transparent;
      }
      .atelier-do-mode .recognize-set,
      .atelier-do-mode .transform-set,
      .atelier-do-mode .output-ladder-panel {
        gap: 22px;
      }
      .atelier-do-mode .sub-exercise {
        border-bottom-color: var(--paper-3);
        padding-bottom: 22px;
      }
      .atelier-do-mode .sub-exercise:last-child {
        padding-bottom: 0;
      }
      .focused-exercise-meter {
        margin: 0 0 18px;
        display: grid;
        grid-template-columns: auto minmax(72px, 1fr) auto;
        align-items: center;
        gap: 12px;
        color: var(--ink-3);
        font-family: var(--mono);
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .focused-exercise-meter div {
        display: flex;
        gap: 5px;
      }
      .focused-exercise-meter i {
        display: block;
        flex: 1 1 0;
        min-width: 18px;
        height: 5px;
        background: var(--paper-3);
      }
      .focused-exercise-meter i.done {
        background: var(--ink-3);
      }
      .focused-exercise-meter i.active {
        background: var(--red);
      }
      .focused-exercise-meter b {
        color: var(--ink);
      }
      .atelier-do-mode .exercise-prompt,
      .atelier-do-mode .source-sentence {
        margin: 10px 0 22px;
        font-size: var(--phone-type-serif-lg);
        line-height: 1.14;
      }
      .atelier-do-mode .source-sentence {
        background: transparent;
        border: 0;
        border-left: 3px solid var(--ink);
        padding: 4px 0 4px 16px;
      }
      .atelier-do-mode .instruction {
        max-width: 54ch;
        font-weight: 500;
      }
      .atelier-do-mode .choice-row button,
      .atelier-do-mode .type-case button {
        min-height: 48px;
        font-size: var(--phone-type-serif-md);
      }
      .atelier-do-mode .choice-row button.selected {
        background: var(--ink);
        color: var(--paper);
      }
      .atelier-do-mode .type-case {
        border: 0;
        background: transparent;
        padding: 0;
      }
      .atelier-do-mode .inline-feedback {
        margin-top: 14px;
      }
      .atelier-do-mode .action-row {
        justify-content: center;
        margin-top: 28px;
      }
      .atelier-do-mode .action-row .btn {
        width: min(100%, 320px);
        min-height: 56px;
      }
      .atelier-do-mode .final-action {
        margin-top: 18px;
      }
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
      .mode-markers { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border: 1px solid var(--ink); min-width: 0; }
      .mode-markers button { min-height: 44px; border-right: 1px solid var(--ink); font-family: var(--mono); font-size: 10px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; }
      .mode-markers button small { display: block; margin-top: 3px; letter-spacing: .08em; opacity: .72; }
      .mode-markers button:last-child { border-right: 0; }
      .mode-markers button.active { background: var(--ink); color: var(--paper); }
      .exercise-frame { min-height: 520px; padding: 28px 32px; }
      .recognize-set, .transform-set { display: grid; gap: 18px; }
      .sub-exercise { border-bottom: 1px solid var(--paper-3); padding-bottom: 18px; }
      .sub-exercise:last-child { border-bottom: 0; }
      .recognize-card {
        display: grid;
        grid-template-columns: 46px minmax(0, 1fr);
        gap: 16px;
        align-items: start;
      }
      .recognize-form-slot {
        position: sticky;
        top: calc(var(--phone-safe-top) + 84px);
        min-height: 48px;
        display: grid;
        place-items: start center;
        padding-top: 8px;
      }
      .recognize-form-slot .rf {
        width: 42px;
        height: 42px;
      }
      .recognize-card-body {
        min-width: 0;
      }
      .sub-exercise .t-mono-low { display: inline-flex; align-items: center; gap: 6px; }
      .exercise-prompt, .source-sentence { font-family: var(--serif); font-style: italic; font-size: 29px; line-height: 1.45; margin: 12px 0 20px; }
      .source-sentence { background: var(--paper-2); border: 1px solid var(--ink); padding: 14px 16px; }
      .meaning-cue { margin: -8px 0 16px; border-left: 3px solid var(--yellow); padding: 8px 0 8px 12px; color: var(--ink-2); font-size: 13px; line-height: 1.4; }
      .recognize-task-note { margin: 0 0 22px; color: var(--ink-2); font-size: 14px; line-height: 1.45; max-width: 640px; }
      .wb-cue { margin: 6px 0 16px; font-family: var(--serif); font-style: italic; font-size: 22px; line-height: 1.4; color: var(--ink); }
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
      .inline-feedback.wrong { border-left-color: var(--red); background: rgba(216,50,26,.06); }
      .inline-feedback p { margin: 6px 0 0; }
      .inline-feedback p:first-child { margin-top: 0; }
      .feedback-issue { padding-top: 10px; margin-top: 10px; border-top: 1px solid rgba(20,17,13,.14); }
      .feedback-issue:first-of-type { border-top: 0; }
      .feedback-issue > b { display: block; color: var(--ink); font-family: var(--mono); font-size: 10px; letter-spacing: .11em; text-transform: uppercase; }
      .inline-feedback.correct { display: inline-flex; align-items: center; gap: 8px; border-left-color: var(--ink); background: rgba(20,17,13,.06); color: var(--ink); font-family: var(--mono); font-size: 10px; letter-spacing: .12em; text-transform: uppercase; font-weight: 900; }
      .ai-review-line { margin-top: 12px; display: inline-flex; align-items: center; min-height: 28px; font-family: var(--mono); font-size: 10px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: var(--blue); }
      .ai-review-line.complete { color: var(--ink); }
      .ai-review-line.failed { color: var(--muted); }
      .ai-review-button { min-height: 34px; border: 1px solid var(--blue); background: transparent; color: var(--blue); padding: 0 12px; font-family: var(--mono); font-size: 10px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; }
      .ai-review-button:disabled { opacity: .45; cursor: wait; }
      .reward-credit-line { margin: 2px 0 0; font-family: var(--mono); font-size: 11px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; color: var(--blue); }
      .reward-moment-card.drafting { border-color: var(--blue); }
      .output-ladder-panel { display: grid; gap: 18px; }
      .ladder-head { display: grid; gap: 4px; }
      .ladder-eyebrow { font-family: var(--mono); font-size: 10px; font-weight: 900; letter-spacing: .16em; text-transform: uppercase; color: var(--blue); }
      .ladder-instruction { margin: 0; color: var(--ink-2); font-size: 14px; line-height: 1.45; }
      .chat-thread { display: grid; gap: 12px; }
      .chat-bubble { border: 1px solid var(--ink); padding: 12px 15px; max-width: 86%; }
      .chat-bubble.incoming { justify-self: start; background: var(--paper-2); border-left: 4px solid var(--blue); }
      .chat-bubble .chat-who { display: block; font-family: var(--mono); font-size: 9px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); margin-bottom: 5px; }
      .chat-bubble p { margin: 0; font-family: var(--serif); font-style: italic; font-size: 22px; line-height: 1.4; }
      .output-ladder-panel textarea.chat-reply { min-height: 100px; box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--blue) 30%, transparent); }
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
      .model-audio-row { margin-top: 12px; }
      .model-audio-button { display: inline-flex; align-items: center; gap: 8px; min-height: 40px; padding: 0 14px; border: 1px solid var(--ink); background: var(--sheet); color: var(--ink); font-family: var(--mono); font-size: 10px; letter-spacing: .13em; font-weight: 800; text-transform: uppercase; cursor: pointer; }
      .model-audio-button:hover { background: var(--paper-2); }
      .model-audio-button:disabled { opacity: .55; cursor: progress; }
      .spin { animation: spin .7s linear infinite; }
      .output-ladder-panel textarea { min-height: 150px; resize: vertical; box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 20%, transparent); }
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
      .errata-slip { position: relative; background: var(--paper); border: 2px solid var(--ink); padding: 38px 18px 18px; box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 20%, transparent); transform: rotate(-1deg); animation: slip-in .24s both; }
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
      .errata-review-modal { width: min(900px, 96vw); max-height: 90vh; overflow: auto; background: var(--paper); border: 2px solid var(--ink); position: relative; box-shadow: 0 18px 42px color-mix(in srgb, var(--ink) 24%, transparent); }
      .errata-review-modal header { padding: 28px 36px 20px; border-bottom: 2px solid var(--ink); display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; }
      .errata-review-modal h2 { margin: 8px 0 0; font-family: var(--display); font-size: 42px; line-height: .95; letter-spacing: -.04em; }
      .errata-review-body { display: grid; grid-template-columns: .9fr 1.1fr; gap: 28px; padding: 28px 36px 34px; }
      .errata-review-copy { border-left: 4px solid var(--yellow); padding-left: 18px; }
      .errata-review-copy p { color: var(--ink-2); line-height: 1.48; margin: 10px 0 0; }
      .review-prompt { font-family: var(--serif); font-style: italic; font-size: 25px; line-height: 1.3; color: var(--ink) !important; }
      .review-memory { margin-top: 18px; border: 1px solid var(--ink); background: var(--paper-2); padding: 12px 14px; }
      .review-memory .wrong { margin-top: 6px; font-family: var(--serif); font-style: italic; color: var(--red); text-decoration: line-through; text-decoration-thickness: 2px; }
      .errata-review-answer textarea { width: 100%; min-height: 150px; margin-top: 10px; border: 2px solid var(--ink); background: var(--paper); padding: 14px 16px; outline: none; resize: vertical; font-family: var(--serif); font-size: 22px; font-style: italic; box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 20%, transparent); }
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
        box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 22%, transparent);
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
      .recap-modal.printed {
        width: min(680px, 96vw);
        box-shadow: var(--ink-block-shadow);
      }
      .recap-modal.printed header {
        align-items: flex-start;
        gap: 24px;
      }
      .recap-modal.printed header .btn {
        width: 42px;
        height: 42px;
        padding: 0;
        font-size: 20px;
      }
      .edition-seal {
        width: 104px;
        height: 104px;
        display: grid;
        place-items: center;
        border: 2px solid var(--red);
        color: var(--red);
        border-radius: 50%;
        transform: rotate(-9deg);
        font-family: var(--mono);
        font-size: 12px;
        font-weight: 500;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .printed-body {
        display: grid;
        gap: 0;
        padding: 0 36px;
      }
      .printed-body section {
        display: grid;
        gap: 8px;
        padding: 20px 0;
        border-top: 1px solid var(--paper-3);
      }
      .printed-body section:first-child {
        border-top: 0;
      }
      .printed-body p {
        margin: 0;
        font-family: var(--serif);
        font-size: 26px;
        font-style: italic;
        line-height: 1.1;
      }
      .printed-seal-stage {
        grid-template-columns: auto minmax(0, 1fr);
        align-items: center;
        gap: 20px;
      }
      .printed-seal-stage .seal {
        transform: rotate(-4deg);
      }
      .printed-stats {
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
      }
      .printed-stats div {
        border: 1px solid var(--ink);
        background: var(--paper-2);
        padding: 12px 10px;
      }
      .printed-stats b {
        display: block;
        font-family: var(--serif);
        font-size: 30px;
        font-style: italic;
        line-height: 1;
      }
      .printed-stats span {
        display: block;
        margin-top: 5px;
        color: var(--ink-2);
        font-family: var(--mono);
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .1em;
        text-transform: uppercase;
      }
      .printed-minted .minted-row {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
      }
      .printed-minted .seal {
        margin-right: 6px;
      }
      .printed-minted p {
        font-size: 22px;
      }
      .printed-hook p {
        color: var(--ink);
      }
      .recap-modal.printed footer {
        justify-content: flex-end;
      }
      .reward-moment-layer {
        position: fixed;
        inset: 0;
        z-index: 1100;
        display: grid;
        place-items: center;
        padding: 22px;
        background: rgba(20, 17, 13, .58);
      }
      .reward-moment-card {
        position: relative;
        z-index: 2;
        width: min(420px, 100%);
        display: grid;
        justify-items: center;
        gap: 16px;
        border: 2px solid var(--ink);
        background: var(--paper);
        box-shadow: var(--ink-block-shadow);
        padding: 26px 24px 22px;
        text-align: center;
      }
      .reward-moment-card span {
        color: var(--red);
        font-family: var(--mono);
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .16em;
        text-transform: uppercase;
      }
      .reward-moment-card h2 {
        margin: 6px 0 0;
        font-family: var(--serif);
        font-size: 38px;
        font-style: italic;
        font-weight: 600;
        line-height: .96;
        letter-spacing: 0;
      }
      .reward-moment-card p {
        margin: 8px auto 0;
        max-width: 28ch;
        color: var(--ink-2);
        font-size: 13px;
        line-height: 1.45;
      }
      .reward-moment-card button {
        min-height: 48px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 9px;
        border: 1.5px solid var(--ink);
        background: var(--red);
        color: #fff;
        padding: 0 18px;
        font-family: var(--mono);
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .13em;
        text-transform: uppercase;
      }
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
          box-shadow: inset 0 -3px 0 color-mix(in srgb, var(--ink) 28%, transparent);
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
          box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 22%, transparent);
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
          box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 22%, transparent);
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
          min-height: var(--app-viewport-height);
          padding-top: 0;
          padding-bottom: 28px;
        }
        .atelier-do-mode .do-topbar {
          grid-template-columns: 42px minmax(0, 1fr) 68px;
          gap: 10px;
          margin-left: calc(0px - var(--phone-gutter));
          margin-right: calc(0px - var(--phone-gutter));
          padding-left: var(--phone-gutter);
          padding-right: var(--phone-gutter);
        }
        .atelier-do-mode .do-finish {
          padding: 0 8px;
          font-size: 9px;
        }
        .atelier-do-mode .do-stage {
          min-height: calc(var(--app-viewport-height) - var(--phone-topbar-height));
          align-content: start;
          padding-top: var(--phone-section-gap);
          padding-bottom: calc(var(--phone-bottom-nav-space) + 44px);
        }
        .atelier-do-mode .atelier-exercise-shell > header {
          align-items: flex-start;
          gap: 12px;
        }
        .atelier-do-mode .atelier-exercise-shell > header h2 {
          font-size: var(--phone-type-title);
        }
        .atelier-do-mode .atelier-exercise-shell-body {
          padding: var(--phone-gutter);
        }
        .atelier-do-mode .exercise-prompt,
        .atelier-do-mode .source-sentence {
          font-size: var(--phone-type-serif-lg);
          line-height: 1.16;
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
          min-height: var(--phone-topbar-height);
          margin-left: calc(0px - var(--phone-gutter));
          margin-right: calc(0px - var(--phone-gutter));
          /* Clear the status bar / Dynamic Island so BACK/FINISH stay tappable. */
          padding: var(--phone-safe-top) var(--phone-gutter) 0;
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
          gap: var(--phone-card-gap);
          padding: var(--phone-section-gap) 0 10px;
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
          font-size: var(--phone-type-display);
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
          margin-top: var(--phone-section-gap);
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
          gap: var(--phone-card-gap);
        }
        .sub-exercise {
          padding-bottom: var(--phone-card-gap);
        }
        .recognize-card {
          grid-template-columns: 40px minmax(0, 1fr);
          gap: 12px;
        }
        .recognize-form-slot {
          position: static;
          min-height: 40px;
          padding-top: 4px;
        }
        .recognize-form-slot .rf {
          width: 36px;
          height: 36px;
        }
        .exercise-prompt,
        .source-sentence {
          font-size: var(--phone-type-serif-lg);
          line-height: 1.33;
          margin: 10px 0 var(--phone-card-gap);
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
          margin: 18px calc(0px - var(--phone-gutter)) calc(0px - var(--phone-safe-bottom-space));
          padding: 12px var(--phone-gutter) calc(12px + var(--phone-safe-bottom-space));
          border-top: 1px solid var(--ink);
          background: var(--paper);
        }
        .session-spread .action-row .btn {
          flex: 1 1 0;
          min-height: var(--phone-action-height);
          padding-inline: 10px;
        }
        .atelier-do-mode .action-row .btn {
          width: 100%;
          min-height: var(--phone-action-height);
        }
        .atelier-do-mode .final-action {
          margin-bottom: 18px;
        }
        .recap-overlay {
          align-items: end;
          padding: 12px;
        }
        .recap-modal,
        .errata-review-modal {
          width: 100%;
          max-height: calc(var(--app-viewport-height) - 24px);
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
          box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 22%, transparent);
        }
        .recap-next h3 {
          font-size: 26px;
        }
        .recap-next .btn {
          width: 100%;
        }
        .recap-modal.printed {
          box-shadow: none;
        }
        .printed-body {
          padding: 0 18px;
        }
        .printed-seal-stage {
          grid-template-columns: 1fr;
          justify-items: center;
          text-align: center;
        }
        .printed-stats {
          grid-template-columns: 1fr;
        }
        .printed-body p {
          font-size: 22px;
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

import React, { useEffect, useMemo, useRef, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  ArrowRight,
  Check,
  ClipboardList,
  Clock3,
  Eye,
  FileText,
  Loader2,
  Mail,
  MapPinned,
  Menu,
  Mic,
  Play,
  Send,
  Sparkles,
  Square,
  Upload,
  Volume2,
} from 'lucide-react';
import toast from 'react-hot-toast';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import { ContinuationCard, RedInkRepairSlip, VocabularyCreditBadge } from '@/components/mobile';
import { writeLocalDayProgressFlag } from '@/lib/atelier-next';
import api, {
  DueGrammarConcept,
  GrammarNotebookItem,
  MissionToday,
  RealWorldMission,
  UnifiedSRSItem,
  VocabularyRecommendationItem,
} from '@/services/api';

type MissionMessenger = {
  channel_label: string;
  contact_name: string;
  contact_role: string;
  contact_initials: string;
  presence: string;
  time_label: string;
  thread_title: string;
  scene_anchor: string;
  dispatch_note: string;
  inbox_context: string;
  opening_message: string;
  ambient_cues: string[];
  quick_replies: string[];
  success_signal: string;
  realism_rules: string[];
};

type CreateMissionOptions = {
  mission_type?: string;
  cadence?: string;
  atelier_session_id?: string;
  serial_thread_id?: string;
  episode_index?: number;
  preferred_concept_ids?: number[];
  preferred_errata_ids?: string[];
  preferred_vocabulary_ids?: number[];
  use_news?: boolean;
  custom_scenario?: string;
  desired_outcome?: string;
  relationship?: string;
  register?: string;
  stakes_level?: number;
};

type FailedTurn = { text: string; mode: 'chat' | 'voice' };
type MobileComposerState = 'default' | 'typing' | 'voice' | 'sent' | 'failed';
type MissionQueueItem = {
  label: string;
  mission: RealWorldMission;
  section: 'active' | 'inactive';
};
type ThreadSeedContext = {
  atelierSessionId?: string | null;
  conceptIds: number[];
  vocabularyIds: number[];
  erratumIds: string[];
};
type TargetConceptSource = 'srs' | 'due' | 'notebook';
type TargetConcept = GrammarNotebookItem & {
  recommendation_source: TargetConceptSource;
  recommendation_label: string;
  due_since_days?: number | null;
  srs_score?: number | null;
  reps?: number | null;
};
type TargetVocabulary = VocabularyRecommendationItem & {
  recommendation_label: string;
};
type DayProgressFlag = Parameters<typeof writeLocalDayProgressFlag>[0];
type ServerDayProgressCandidate = {
  progress?: Partial<Record<DayProgressFlag, boolean>> | null;
};

function queryList(value: string | string[] | undefined) {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function queryNumberList(value: string | string[] | undefined) {
  return queryList(value)
    .map((item) => Number(item))
    .filter((item) => Number.isFinite(item));
}

function queryStringList(value: string | string[] | undefined) {
  return queryList(value)
    .map((item) => item.trim())
    .filter(Boolean);
}

function hasThreadSeedContext(context: ThreadSeedContext | null | undefined) {
  return Boolean(
    context
    && (context.atelierSessionId || context.conceptIds.length || context.vocabularyIds.length || context.erratumIds.length),
  );
}

function missionThreadSeedContext(mission: RealWorldMission | null): ThreadSeedContext | null {
  if (!mission?.atelier_session_id) return null;
  const conceptIds = Array.isArray(mission.selected_concept_ids) ? mission.selected_concept_ids : [];
  const vocabularyIds = Array.isArray(mission.target_vocabulary_ids) ? mission.target_vocabulary_ids : [];
  const erratumIds = Array.isArray(mission.target_errata_ids) ? mission.target_errata_ids : [];
  return {
    atelierSessionId: mission.atelier_session_id,
    conceptIds,
    vocabularyIds,
    erratumIds,
  };
}

const missionTypes = [
  { id: 'message', label: 'Inbox message' },
  { id: 'explain_plan', label: 'Plan handoff' },
  { id: 'news_summary', label: 'News brief' },
  { id: 'travel_work', label: 'Desk problem' },
  { id: 'conversation', label: 'Live roleplay' },
];

function wordCount(text: string) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item || '').trim()).filter(Boolean) : [];
}

function compactText(value: unknown, maxLength = 96) {
  const text = String(value || '').trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1).trim()}...`;
}

function latestCorrection(mission: RealWorldMission | null): Record<string, any> | null {
  if (!mission) return null;
  const attempt = (mission.attempts || []).slice(-1)[0];
  const userTurn = (mission.turns || []).filter((turn) => turn.role === 'user').slice(-1)[0];
  return userTurn?.correction || attempt?.correction || null;
}

function correctionFeedback(correction: Record<string, any>) {
  const rawVerdict = String(correction.verdict || 'reviewed').replace(/_/g, ' ');
  const score = Number(correction.score_0_4);
  const hasScore = Number.isFinite(score);
  const scoreLabel = hasScore ? `${Math.round(score * 10) / 10}/4 clarity` : 'clarity pending';
  const errata = Array.isArray(correction.errata) ? correction.errata : [];
  const missingTargets = Array.isArray(correction.missing_targets) ? correction.missing_targets : [];
  const needsWork = rawVerdict !== 'accepted' || (hasScore && score < 3) || errata.length > 0 || missingTargets.length > 0;
  const firstRepair = errata.find((item: any) => item?.repair_hint || item?.why_wrong);
  const support = missingTargets.length
    ? `${missingTargets.length} target${missingTargets.length === 1 ? '' : 's'} still missing`
    : firstRepair?.repair_hint
      ? `Repair: ${compactText(firstRepair.repair_hint)}`
      : firstRepair?.why_wrong
        ? compactText(firstRepair.why_wrong)
        : needsWork && rawVerdict !== 'accepted'
          ? rawVerdict
          : '';
  return {
    label: needsWork ? (rawVerdict === 'partial' ? 'Partial' : 'Needs work') : 'Accepted',
    scoreLabel,
    support,
    tone: needsWork ? 'needs-work' : 'accepted',
  };
}

function targetConceptFromNotebook(concept: GrammarNotebookItem): TargetConcept {
  return {
    ...concept,
    recommendation_source: 'notebook',
    recommendation_label: concept.due_errata_count > 0
      ? `${concept.due_errata_count} due repair${concept.due_errata_count === 1 ? '' : 's'}`
      : concept.state_label || 'Notebook',
  };
}

function targetConceptFromDue(concept: DueGrammarConcept): TargetConcept {
  const state = concept.current_state || 'due';
  return {
    id: concept.id,
    external_id: null,
    language: 'fr',
    name: concept.name,
    display_title: concept.name,
    localized_title: null,
    localized_category: concept.category || null,
    localized_subskill: null,
    level: concept.level,
    category: concept.category || null,
    subskill: null,
    catalog_version: null,
    source_refs: undefined,
    is_foundation: false,
    active: true,
    mastery: concept.current_score || 0,
    state,
    state_label: state === 'new' ? 'New SRS target' : 'Due SRS target',
    next_review: null,
    due_errata_count: 0,
    recent_errata_count: 0,
    recommendation_source: 'due',
    recommendation_label: concept.current_score == null ? 'Due SRS' : `Due SRS · ${Math.round(concept.current_score)}/100`,
    srs_score: concept.current_score ?? null,
    reps: concept.reps,
  };
}

function targetConceptFromUnified(item: UnifiedSRSItem): TargetConcept | null {
  const conceptId = Number(item.metadata?.concept_id ?? item.original_id);
  if (!Number.isFinite(conceptId)) return null;
  const category = String(item.metadata?.category || item.display_subtitle || 'Grammar');
  const state = String(item.metadata?.state || 'due');
  const score = Number(item.metadata?.score);
  const dueLabel = item.due_since_days > 0 ? `Due ${item.due_since_days}d` : 'Due now';
  return {
    id: conceptId,
    external_id: typeof item.metadata?.external_id === 'string' ? item.metadata.external_id : null,
    language: 'fr',
    name: item.display_title,
    display_title: item.display_title,
    localized_title: null,
    localized_category: category,
    localized_subskill: typeof item.metadata?.subskill === 'string' ? item.metadata.subskill : null,
    level: item.level,
    category,
    subskill: typeof item.metadata?.subskill === 'string' ? item.metadata.subskill : null,
    catalog_version: null,
    source_refs: undefined,
    is_foundation: false,
    active: true,
    mastery: Number.isFinite(score) ? score : 0,
    state,
    state_label: 'Due SRS target',
    next_review: typeof item.metadata?.next_review === 'string' ? item.metadata.next_review : null,
    due_errata_count: 0,
    recent_errata_count: 0,
    recommendation_source: 'srs',
    recommendation_label: `${dueLabel} · SRS priority`,
    due_since_days: item.due_since_days,
    srs_score: Number.isFinite(score) ? score : null,
    reps: typeof item.metadata?.reps === 'number' ? item.metadata.reps : null,
  };
}

function mergeTargetConcepts(groups: TargetConcept[][], limit = 18) {
  const seen = new Set<number>();
  const merged: TargetConcept[] = [];
  groups.flat().forEach((concept) => {
    if (seen.has(concept.id) || merged.length >= limit) return;
    seen.add(concept.id);
    merged.push(concept);
  });
  return merged;
}

function vocabularyTranslation(item: Pick<VocabularyRecommendationItem, 'translations'> & { translation?: string | null }) {
  return item.translation || item.translations?.de || item.translations?.en || item.translations?.fr || '';
}

function targetVocabularyFromRecommendation(item: VocabularyRecommendationItem): TargetVocabulary {
  const dueLabel = item.bucket === 'due'
    ? 'Due vocabulary'
    : item.bucket === 'fragile'
      ? 'Fragile vocabulary'
      : 'Vocabulary';
  const score = Number.isFinite(item.priority_score) ? ` · ${Math.round(item.priority_score)}` : '';
  return {
    ...item,
    recommendation_label: `${dueLabel}${score}`,
  };
}

function mergeTargetVocabulary(groups: VocabularyRecommendationItem[][], limit = 18) {
  const seen = new Set<number>();
  const merged: TargetVocabulary[] = [];
  groups.flat().forEach((item) => {
    if (seen.has(item.word_id) || merged.length >= limit) return;
    seen.add(item.word_id);
    merged.push(targetVocabularyFromRecommendation(item));
  });
  return merged;
}

function getMessenger(mission: RealWorldMission | null): MissionMessenger {
  const prompt = mission?.prompt_payload || {};
  const raw = prompt.messenger && typeof prompt.messenger === 'object' ? prompt.messenger as Record<string, any> : {};
  const opening = String(raw.opening_message || prompt.conversation_opening || 'Reponds naturellement en francais, et je continue la situation.');
  return {
    channel_label: String(raw.channel_label || 'Reality messages'),
    contact_name: String(raw.contact_name || 'Camille'),
    contact_role: String(raw.contact_role || 'Local contact'),
    contact_initials: String(raw.contact_initials || 'CA').slice(0, 3).toUpperCase(),
    presence: String(raw.presence || 'available now'),
    time_label: String(raw.time_label || '17:42'),
    thread_title: String(raw.thread_title || 'Camille · arrival logistics'),
    scene_anchor: String(raw.scene_anchor || 'A real-world moment in France'),
    dispatch_note: String(raw.dispatch_note || missionDisplayBrief(mission)),
    inbox_context: String(raw.inbox_context || 'The other person needs useful information, not a classroom answer.'),
    opening_message: opening,
    ambient_cues: asStringList(raw.ambient_cues).length ? asStringList(raw.ambient_cues) : ['one practical constraint', 'a real person waiting', 'short message rhythm'],
    quick_replies: asStringList(raw.quick_replies).length ? asStringList(raw.quick_replies) : ['D abord, je vais...', 'Est-ce que je peux...', 'Si cela change...'],
    success_signal: String(raw.success_signal || 'The other person knows what to do next.'),
    realism_rules: asStringList(raw.realism_rules).length ? asStringList(raw.realism_rules) : ['Make it short enough to send.', 'Add one concrete detail.', 'Ask one natural follow-up question.'],
  };
}

function missionDisplayTitle(mission: RealWorldMission | null) {
  if (!mission) return 'Reality Mission';
  if (mission.prompt_payload?.display_title) return String(mission.prompt_payload.display_title);
  if (mission.title && mission.title !== 'Write a Useful Message') return mission.title;
  return {
    message: 'Message Before Arrival',
    explain_plan: "Explain Tomorrow's Plan",
    news_summary: 'Turn One French Headline Into a Brief',
    travel_work: 'Solve a Desk Problem',
    conversation: 'Back-and-Forth Scenario',
  }[mission.mission_type] || mission.title;
}

function missionDisplayBrief(mission: RealWorldMission | null) {
  if (!mission) return 'Complete a realistic French exchange with a concrete outcome.';
  if (mission.brief && !mission.brief.startsWith('Write a realistic French message connected to this')) {
    return mission.brief;
  }
  return {
    message: 'Write a short French message you could actually send before meeting someone in France. Say when you arrive, mention one practical need, and ask one polite question.',
    explain_plan: 'Explain the first step, the backup plan, and one condition that would change your decision.',
    news_summary: 'Use the source card to summarize what happened, why it matters, and one practical consequence.',
    travel_work: 'You are at a station, hotel, or office desk in France. Explain the problem, ask for a solution, and confirm the next step politely.',
    conversation: 'Answer the assistant as if the situation were real. Keep the exchange moving for several turns.',
  }[mission.mission_type] || mission.brief;
}

function missionTypeLabel(type: string) {
  return {
    message: 'Message',
    explain_plan: 'Plan',
    news_summary: 'News brief',
    travel_work: 'Desk scenario',
    conversation: 'Conversation',
  }[type] || type.replace('_', ' ');
}

function missionFormatLabel(mission: RealWorldMission) {
  return {
    chat_message: 'Message',
    voicemail_reply: 'Voicemail',
    email_formal: 'Formal email',
    admin_form: 'Admin form',
    phone_call: 'Phone call',
  }[mission.mission_format || ''] || missionTypeLabel(mission.mission_type);
}

function missionStatusLabel(status?: string) {
  if (!status) return 'ready';
  return status.replace('_', ' ');
}

function sourceCard(mission: RealWorldMission | null): Record<string, any> {
  return mission?.prompt_payload?.source_context_card || {};
}

function missionObjectives(mission: RealWorldMission | null) {
  return (mission?.objectives || []).filter(
    (objective) => mission?.mission_type === 'news_summary' || objective.kind !== 'source',
  );
}

function missionObjectiveProgress(mission: RealWorldMission | null) {
  const objectives = missionObjectives(mission);
  const total = Math.max(objectives.length, 1);
  if (!mission) return { completed: 0, total, text: `0 of ${total} mission goals met` };
  if (mission.status === 'completed') return { completed: total, total, text: `${total} of ${total} mission goals met` };
  const progress = latestCorrection(mission)?.objective_progress || [];
  const completed = Array.isArray(progress)
    ? Math.min(total, progress.filter((item: any) => item?.met).length)
    : 0;
  return { completed, total, text: `${completed} of ${total} mission goals met` };
}

function missionCadenceLabel(cadence?: string, mission?: RealWorldMission | null) {
  if (mission?.serial_thread_id || typeof mission?.episode_index === 'number') return 'Serial';
  if (cadence === 'post_session') return 'Post-session';
  if (cadence === 'ad_hoc') return 'Ad hoc';
  if (!cadence) return 'Mission';
  return cadence.replace('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function weekdayLabel(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(undefined, { weekday: 'short' }).format(date);
}

function missionDeadlineLabel(mission: RealWorldMission | null) {
  if (!mission) return 'open today';
  const prompt = mission.prompt_payload || {};
  const explicit = prompt.deadline_label || prompt.ends_label || prompt.due_label;
  if (typeof explicit === 'string' && explicit.trim()) return explicit.trim();
  if (mission.status === 'completed') {
    const completed = weekdayLabel(mission.completed_at);
    return completed ? `completed ${completed}` : 'completed';
  }
  if (mission.cadence === 'weekly') return 'ends Friday';
  if (mission.cadence === 'post_session') return 'after Atelier';
  if (mission.cadence === 'ad_hoc') return 'open today';
  return missionStatusLabel(mission.status);
}

function missionQueue(today: MissionToday | null): MissionQueueItem[] {
  const raw = [
    today?.active_mission && { label: 'Active', mission: today.active_mission, section: 'active' as const },
    today?.post_session_recommendation && { label: 'Post-session', mission: today.post_session_recommendation, section: 'active' as const },
    today?.weekly_mission && { label: 'Weekly', mission: today.weekly_mission, section: 'active' as const },
    ...(today?.recent_completed || []).map((mission) => ({ label: 'Done', mission, section: 'inactive' as const })),
  ].filter(Boolean) as MissionQueueItem[];
  const seen = new Set<string>();
  return raw.filter((item) => {
    if (seen.has(item.mission.id)) return false;
    seen.add(item.mission.id);
    return true;
  });
}

function uniqueMissionItems(items: MissionQueueItem[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.mission.id)) return false;
    seen.add(item.mission.id);
    return true;
  });
}

function missionActiveSlot(next: RealWorldMission, current: RealWorldMission | null) {
  if (next.status === 'in_progress') return next;
  if (current?.id === next.id) return next;
  if (!current && next.status === 'available' && next.cadence === 'ad_hoc') return next;
  return current;
}

function routeWithQuery(path: string, pairs: Array<[string, string | number | null | undefined]>) {
  const params = new URLSearchParams();
  pairs.forEach(([key, value]) => {
    if (value === null || value === undefined) return;
    const text = String(value).trim();
    if (!text) return;
    params.append(key, text);
  });
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

function hasServerDayProgressFlag(candidate: unknown, flag: DayProgressFlag) {
  const progress = (candidate as ServerDayProgressCandidate | null)?.progress;
  return Boolean(progress && typeof progress[flag] === 'boolean');
}

async function writeSideQuestProgressFlag(flag: DayProgressFlag) {
  try {
    const atelierToday = await api.getAtelierToday();
    if (hasServerDayProgressFlag(atelierToday, flag)) return;
  } catch (error) {
    console.error(error);
  }
  writeLocalDayProgressFlag(flag);
}

function uniqueText(items: string[], limit = 4) {
  const seen = new Set<string>();
  const output: string[] = [];
  items.forEach((item) => {
    const text = item.trim();
    const key = text.toLowerCase();
    if (!text || seen.has(key) || output.length >= limit) return;
    seen.add(key);
    output.push(text);
  });
  return output;
}

function missionTargetVocabulary(mission: RealWorldMission | null): Record<string, any>[] {
  if (!mission) return [];
  const direct = Array.isArray(mission.target_vocabulary) ? mission.target_vocabulary : [];
  const prompt = Array.isArray(mission.prompt_payload?.target_vocabulary) ? mission.prompt_payload.target_vocabulary : [];
  return direct.length ? direct : prompt;
}

function missionTargetConceptIds(mission: RealWorldMission | null) {
  const fromMission = Array.isArray(mission?.selected_concept_ids) ? mission?.selected_concept_ids || [] : [];
  const fromObjectives = missionObjectives(mission)
    .map((objective) => Number(objective.concept_id))
    .filter((item) => Number.isFinite(item));
  return Array.from(new Set([...fromMission, ...fromObjectives])).slice(0, 4);
}

function cleanTargetLabel(value: unknown) {
  return String(value || '')
    .replace(/^Use\s+\d+\s+clear instance of\s+/i, '')
    .replace(/^Use\s+/i, '')
    .replace(/\s+naturally$/i, '')
    .replace(/^Repair:\s*/i, 'Repair: ')
    .trim();
}

function correctionErrata(correction: Record<string, any> | null | undefined): Record<string, any>[] {
  return Array.isArray(correction?.errata) ? correction?.errata || [] : [];
}

function missionFeuilletonHref(mission: RealWorldMission, correction?: Record<string, any> | null) {
  const conceptIds = missionTargetConceptIds(mission);
  const vocabularyIds = missionTargetVocabulary(mission)
    .map((item) => Number(item.word_id))
    .filter((item) => Number.isFinite(item));
  const errata = correctionErrata(correction);
  const feuilletonPairs: Array<[string, string | number | null | undefined]> = [
    ['mission_id', mission.id],
    ['atelier_session_id', mission.atelier_session_id || undefined],
    ['serial_thread_id', mission.serial_thread_id || undefined],
    ['episode_index', typeof mission.episode_index === 'number' ? mission.episode_index + 1 : undefined],
    ...conceptIds.slice(0, 4).map((id): [string, number] => ['concept_id', id]),
    ...vocabularyIds.slice(0, 4).map((id): [string, number] => ['vocabulary_id', id]),
    ...errata.slice(0, 2).map((item): [string, string | number | null | undefined] => ['erratum_id', item.id]),
  ];
  return routeWithQuery('/graphic-novel', feuilletonPairs);
}

function missionRouteQuery(mission: RealWorldMission): Record<string, string | number> {
  const query: Record<string, string | number> = { mission: mission.id };
  if (mission.serial_thread_id) query.serial_thread_id = mission.serial_thread_id;
  if (typeof mission.episode_index === 'number') query.episode_index = mission.episode_index;
  return query;
}

function erratumText(item: Record<string, any>, keys: string[], fallback = '') {
  const value = keys.map((key) => item[key]).find((candidate) => String(candidate || '').trim());
  return String(value || fallback).trim();
}

function missionAnalysisTargets(mission: RealWorldMission | null, correction?: Record<string, any> | null) {
  const objectives = missionObjectives(mission);
  const grammar = uniqueText(
    objectives
      .filter((objective) => {
        const kind = String(objective.kind || '').toLowerCase();
        const id = String(objective.id || '').toLowerCase();
        return kind.includes('grammar') || id.startsWith('concept_') || id.startsWith('erratum_') || Boolean(objective.concept_id);
      })
      .map((objective) => cleanTargetLabel(objective.label)),
  );
  const vocabulary = uniqueText(
    missionTargetVocabulary(mission)
      .map((item) => [item.word, item.translation].filter(Boolean).join(' - ')),
  );
  const repairs = uniqueText(
    correctionErrata(correction)
      .map((item) => cleanTargetLabel(item.display_label || item.error_category || item.review_mode)),
  );
  const fallback = uniqueText(
    objectives
      .filter((objective) => objective.required)
      .map((objective) => cleanTargetLabel(objective.label || 'Real-world task')),
    2,
  );
  return { grammar, vocabulary, repairs, fallback };
}

export default function MissionsPage() {
  const router = useRouter();
  const [today, setToday] = useState<MissionToday | null>(null);
  const [mission, setMission] = useState<RealWorldMission | null>(null);
  const [missionType, setMissionType] = useState('message');
  const [customScenario, setCustomScenario] = useState('');
  const [customOutcome, setCustomOutcome] = useState('');
  const [customRelationship, setCustomRelationship] = useState('');
  const [customRegister, setCustomRegister] = useState('polite neutral');
  const [customMissionName, setCustomMissionName] = useState('');
  const [customConceptIds, setCustomConceptIds] = useState<number[]>([]);
  const [customConcepts, setCustomConcepts] = useState<TargetConcept[]>([]);
  const [customConceptsLoading, setCustomConceptsLoading] = useState(false);
  const [customVocabularyIds, setCustomVocabularyIds] = useState<number[]>([]);
  const [customVocabulary, setCustomVocabulary] = useState<TargetVocabulary[]>([]);
  const [customVocabularyLoading, setCustomVocabularyLoading] = useState(false);
  const [showCustomMissionSheet, setShowCustomMissionSheet] = useState(false);
  const [customMissionStep, setCustomMissionStep] = useState(0);
  const [writingText, setWritingText] = useState('');
  const [turnText, setTurnText] = useState('');
  const [turnMode, setTurnMode] = useState<'chat' | 'voice'>('chat');
  const [turnOutcome, setTurnOutcome] = useState<Record<string, any> | null>(null);
  const [failedTurn, setFailedTurn] = useState<FailedTurn | null>(null);
  const [composerSent, setComposerSent] = useState(false);
  const [showMissionSwitcher, setShowMissionSwitcher] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [submittingWriting, setSubmittingWriting] = useState(false);
  const [submittingTurn, setSubmittingTurn] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const [threadSeedContext, setThreadSeedContext] = useState<ThreadSeedContext | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const queryHandledRef = useRef(false);

  const correction = useMemo(() => latestCorrection(mission), [mission]);
  const messenger = useMemo(() => getMessenger(mission), [mission]);
  const visibleThreadContext = useMemo(() => {
    if (hasThreadSeedContext(threadSeedContext)) return threadSeedContext;
    return missionThreadSeedContext(mission);
  }, [mission, threadSeedContext]);
  const mobileComposerState: MobileComposerState = failedTurn
    ? 'failed'
    : recording || transcribing || turnMode === 'voice'
      ? 'voice'
      : turnText.trim()
        ? 'typing'
        : composerSent
          ? 'sent'
          : 'default';
  const customMissionDraftActive = Boolean(
    customScenario.trim()
    || customOutcome.trim()
    || customRelationship.trim()
    || customMissionName.trim()
    || customConceptIds.length
    || customVocabularyIds.length,
  );

  function openMissionSwitcher() {
    setShowCustomMissionSheet(false);
    setShowMissionSwitcher(true);
  }

  function openCustomMissionSheet(step = customMissionStep) {
    setShowMissionSwitcher(false);
    setCustomMissionStep(Math.max(0, Math.min(2, step)));
    setShowCustomMissionSheet(true);
  }

  useEffect(() => {
    if (!showMissionSwitcher && !showCustomMissionSheet && !recording && !transcribing) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setShowMissionSwitcher(false);
      if (event.key === 'Escape') setShowCustomMissionSheet(false);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [recording, showMissionSwitcher, showCustomMissionSheet, transcribing]);

  useEffect(() => {
    if (!showCustomMissionSheet || customConcepts.length || customConceptsLoading) return;
    let cancelled = false;
    setCustomConceptsLoading(true);
    async function loadTargetConcepts() {
      const srsConcepts = await api.getUnifiedSRSQueue({ limit: 60, interleaving_mode: 'priority' })
        .then((queue) => (queue.queue || [])
          .filter((item) => item.item_type === 'grammar')
          .map(targetConceptFromUnified)
          .filter((item): item is TargetConcept => Boolean(item)))
        .catch((error) => {
          console.error(error);
          return [];
        });
      const dueConcepts = srsConcepts.length >= 18 ? [] : await api.getDueGrammarConcepts({ limit: 18 })
        .then((items) => (items || []).map(targetConceptFromDue))
        .catch((error) => {
          console.error(error);
          return [];
        });
      const notebookConcepts = srsConcepts.length + dueConcepts.length >= 18 ? [] : await api.getGrammarNotebook({ limit: 18 })
        .then((items) => (items || []).map(targetConceptFromNotebook))
        .catch((error) => {
          console.error(error);
          return [];
        });
      const next = mergeTargetConcepts([srsConcepts, dueConcepts, notebookConcepts]);
      if (!cancelled) {
        setCustomConcepts(next);
      }
    }
    loadTargetConcepts()
      .finally(() => {
        if (!cancelled) setCustomConceptsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [customConcepts.length, customConceptsLoading, showCustomMissionSheet]);

  useEffect(() => {
    if (!showCustomMissionSheet || customVocabulary.length || customVocabularyLoading) return;
    let cancelled = false;
    setCustomVocabularyLoading(true);
    async function loadTargetVocabulary() {
      const data = await api.getVocabularyDueContext({
        limit: 24,
        due_limit: 14,
        fragile_limit: 8,
        new_limit: 8,
        topic_limit: 4,
      }).catch((error) => {
        console.error(error);
        return null;
      });
      const next = data
        ? mergeTargetVocabulary([
          data.due_words || [],
          data.fragile_words || [],
          data.topic_compatible_words || [],
        ])
        : [];
      if (!cancelled) {
        setCustomVocabulary(next);
      }
    }
    loadTargetVocabulary()
      .finally(() => {
        if (!cancelled) setCustomVocabularyLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [customVocabulary.length, customVocabularyLoading, showCustomMissionSheet]);

  function syncTodayMission(next: RealWorldMission) {
    setToday((current) => {
      if (!current) return current;
      const replace = (item: RealWorldMission | null) => item?.id === next.id ? next : item;
      return {
        ...current,
        weekly_mission: replace(current.weekly_mission),
        post_session_recommendation: replace(current.post_session_recommendation),
        active_mission: missionActiveSlot(next, replace(current.active_mission)),
        recent_completed: (current.recent_completed || []).map((item) => item.id === next.id ? next : item),
      };
    });
  }

  async function loadToday() {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await api.getMissionsToday();
      setToday(data);
      const queryMissionId = typeof router.query.mission === 'string' ? router.query.mission : null;
      if (queryMissionId) {
        const selected = await api.getMission(queryMissionId);
        setMission(selected);
      } else {
        setMission(data.active_mission || data.post_session_recommendation || data.weekly_mission);
      }
    } catch (error) {
      console.error(error);
      setToday(null);
      setMission(null);
      setLoadError('Missions are offline right now. Retry the sync, or create a custom mission from the mobile sheet.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!router.isReady) return;
    void loadToday();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.isReady]);

  useEffect(() => {
    if (!router.isReady || queryHandledRef.current) return;
    const queryMissionId = typeof router.query.mission === 'string' ? router.query.mission : null;
    if (queryMissionId) return;
    const atelierSessionId = typeof router.query.atelier_session_id === 'string' ? router.query.atelier_session_id : null;
    const conceptIds = queryNumberList(router.query.concept_id);
    const vocabularyIds = queryNumberList(router.query.vocabulary_id);
    const erratumIds = queryStringList(router.query.erratum_id);
    const serialThreadId = typeof router.query.serial_thread_id === 'string' ? router.query.serial_thread_id : null;
    const episodeIndex = Number(router.query.episode_index);
    if (!atelierSessionId && !serialThreadId && !conceptIds.length && !erratumIds.length && !vocabularyIds.length) return;
    const requestedEpisodeIndex = Number.isFinite(episodeIndex) ? episodeIndex : undefined;
    if (serialThreadId) {
      queryHandledRef.current = true;
      void openSerialMissionFromQuery({
        serialThreadId,
        episodeIndex: requestedEpisodeIndex,
        atelierSessionId,
        conceptIds,
        vocabularyIds,
        erratumIds,
      });
      return;
    }
    const nextThreadSeed = {
      atelierSessionId,
      conceptIds,
      vocabularyIds,
      erratumIds,
    };
    setThreadSeedContext(nextThreadSeed);
    queryHandledRef.current = true;
    void createMission({
      cadence: atelierSessionId ? 'post_session' : 'ad_hoc',
      atelier_session_id: atelierSessionId || undefined,
      preferred_concept_ids: conceptIds.length ? conceptIds : undefined,
      preferred_errata_ids: erratumIds.length ? erratumIds : undefined,
      preferred_vocabulary_ids: vocabularyIds.length ? vocabularyIds : undefined,
      use_news: false,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.isReady, router.query.atelier_session_id, router.query.concept_id, router.query.episode_index, router.query.erratum_id, router.query.mission, router.query.serial_thread_id, router.query.vocabulary_id]);

  async function openSerialMissionFromQuery({
    serialThreadId,
    episodeIndex,
    atelierSessionId,
    conceptIds,
    vocabularyIds,
    erratumIds,
  }: {
    serialThreadId: string;
    episodeIndex?: number;
    atelierSessionId?: string | null;
    conceptIds: number[];
    vocabularyIds: number[];
    erratumIds: string[];
  }) {
    const nextThreadSeed = {
      atelierSessionId,
      conceptIds,
      vocabularyIds,
      erratumIds,
    };
    setThreadSeedContext(nextThreadSeed);

    try {
      const serial = await api.getSerialToday();
      const sameThread = serial?.thread_id === serialThreadId;
      const sameEpisode = episodeIndex === undefined || serial?.episode_index === episodeIndex;
      if (sameThread && sameEpisode && serial.kind === 'mission' && serial.mission_id) {
        const selected = await api.getMission(serial.mission_id);
        setMission(selected);
        syncTodayMission(selected);
        await router.replace({ pathname: '/missions', query: missionRouteQuery(selected) }, undefined, { shallow: true });
        return;
      }
      if (sameThread && sameEpisode && serial.kind === 'feuilleton' && serial.scene_id) {
        const query: Record<string, string | number> = {
          serial_thread_id: serial.thread_id,
          episode_index: serial.episode_index,
          scene: serial.scene_id,
        };
        await router.replace({ pathname: '/graphic-novel', query }, undefined, { shallow: false });
        return;
      }
    } catch (error) {
      console.error(error);
    }

    void createMission({
      cadence: 'ad_hoc',
      atelier_session_id: atelierSessionId || undefined,
      serial_thread_id: serialThreadId,
      episode_index: episodeIndex,
      preferred_concept_ids: conceptIds.length ? conceptIds : undefined,
      preferred_errata_ids: erratumIds.length ? erratumIds : undefined,
      preferred_vocabulary_ids: vocabularyIds.length ? vocabularyIds : undefined,
      use_news: false,
    });
  }

  async function createMission(extra?: CreateMissionOptions) {
    setCreating(true);
    try {
      const nextType = extra?.mission_type || missionType;
      const next = await api.createMission({
        mission_type: nextType,
        cadence: extra?.cadence || 'ad_hoc',
        use_news: extra?.use_news ?? nextType === 'news_summary',
        atelier_session_id: extra?.atelier_session_id,
        serial_thread_id: extra?.serial_thread_id,
        episode_index: extra?.episode_index,
        preferred_concept_ids: extra?.preferred_concept_ids,
        preferred_errata_ids: extra?.preferred_errata_ids,
        preferred_vocabulary_ids: extra?.preferred_vocabulary_ids,
        custom_scenario: extra?.custom_scenario,
        desired_outcome: extra?.desired_outcome,
        relationship: extra?.relationship,
        register: extra?.register,
        stakes_level: extra?.stakes_level,
      });
      setMission(next);
      syncTodayMission(next);
      setWritingText('');
      setTurnText('');
      setTurnMode('chat');
      setFailedTurn(null);
      setComposerSent(false);
      setMicError(null);
      if (extra?.custom_scenario) {
        setCustomScenario('');
        setCustomOutcome('');
        setCustomRelationship('');
        setCustomRegister('polite neutral');
        setCustomMissionName('');
        setCustomConceptIds([]);
        setCustomVocabularyIds([]);
        setCustomMissionStep(0);
        setShowCustomMissionSheet(false);
      }
      router.replace({ pathname: '/missions', query: missionRouteQuery(next) }, undefined, { shallow: true });
    } catch (error) {
      console.error(error);
      toast.error('Could not create this mission.');
    } finally {
      setCreating(false);
    }
  }

  function selectMission(next: RealWorldMission) {
    setMission(next);
    setWritingText('');
    setTurnText('');
    setTurnMode('chat');
    setTurnOutcome(null);
    setFailedTurn(null);
    setComposerSent(false);
    setMicError(null);
    router.replace({ pathname: '/missions', query: { mission: next.id } }, undefined, { shallow: true });
  }

  async function submitWriting() {
    if (!mission) return;
    setSubmittingWriting(true);
    try {
      const result = await api.submitMission(mission.id, { text: writingText, mode: 'writing' });
      setMission(result.mission);
      syncTodayMission(result.mission);
      toast.success(result.correction?.verdict === 'accepted' ? 'Dispatch accepted' : 'Dispatch reviewed');
    } catch (error) {
      console.error(error);
      toast.error('Could not review this dispatch.');
    } finally {
      setSubmittingWriting(false);
    }
  }

  async function submitTurn(mode: 'chat' | 'voice' = 'chat', retryText?: string) {
    if (!mission) return;
    const text = (retryText ?? turnText).trim();
    if (!text) return;
    setSubmittingTurn(true);
    try {
      const result = await api.submitMissionTurn(mission.id, { text, mode });
      setMission(result.mission);
      syncTodayMission(result.mission);
      setTurnOutcome(result.outcome && Object.keys(result.outcome).length ? result.outcome : null);
      setTurnText('');
      setTurnMode('chat');
      setFailedTurn(null);
      setComposerSent(true);
    } catch (error) {
      console.error(error);
      setComposerSent(false);
      setFailedTurn({ text, mode });
      toast.error('Could not send this message.');
    } finally {
      setSubmittingTurn(false);
    }
  }

  async function completeMission() {
    if (!mission) return;
    setCompleting(true);
    try {
      const result = await api.completeMission(mission.id);
      setMission(result.mission);
      syncTodayMission(result.mission);
      try {
        const nextToday = await api.getMissionsToday();
        setToday(nextToday);
      } catch (error) {
        console.error(error);
      }
      await writeSideQuestProgressFlag('missionDone');
      toast.success('Mission completed.');
      void router.push('/atelier');
    } catch (error) {
      console.error(error);
      toast.error('Could not complete the mission.');
    } finally {
      setCompleting(false);
    }
  }

  async function transcribeAudio(blob: Blob) {
    setTranscribing(true);
    try {
      const transcript = await api.transcribeMissionAudio(blob);
      if (transcript.trim()) {
        setTurnText(transcript.trim());
        setTurnMode('voice');
        setFailedTurn(null);
        setComposerSent(false);
        setMicError(null);
        toast.success('Transcript ready to edit.');
      } else {
        setMicError('No speech was detected. Try one more recording, upload clearer audio, or type the message.');
        toast('No speech detected.');
      }
    } catch (error) {
      console.error(error);
      setMicError('Could not transcribe this audio. Try again, upload another file, or type the message.');
      toast.error('Could not transcribe this recording.');
    } finally {
      setTranscribing(false);
    }
  }

  async function startRecording() {
    setComposerSent(false);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setMicError('Voice recording is not available in this browser. Type the message, or upload an audio file.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];
      setMicError(null);
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' });
        stream.getTracks().forEach((track) => track.stop());
        void transcribeAudio(audioBlob);
      };
      recorder.start();
      setRecording(true);
    } catch (error) {
      console.error(error);
      const name = error instanceof DOMException ? error.name : '';
      const message = name === 'NotAllowedError'
        ? 'Microphone is blocked. Allow microphone access in the browser toolbar, or type the message.'
        : name === 'NotFoundError'
          ? 'No microphone was found. Type the message, or upload an audio file.'
          : 'Microphone access failed. Type the message, or upload an audio file.';
      setMicError(message);
      toast.error(message);
    }
  }

  function stopRecording() {
    if (!mediaRecorderRef.current || !recording) return;
    mediaRecorderRef.current.stop();
    setRecording(false);
  }

  function uploadAudioFile(file?: File | null) {
    if (!file) return;
    setComposerSent(false);
    setMicError(null);
    void transcribeAudio(file);
  }

  async function playLastAssistant() {
    const text = (mission?.turns || []).filter((turn) => turn.role === 'assistant').slice(-1)[0]?.text;
    if (!text) return;
    setPlaying(true);
    try {
      const audio = await api.synthesizeSpeech(text);
      const blob = new Blob([audio], { type: 'audio/mpeg' });
      const url = URL.createObjectURL(blob);
      const player = new Audio(url);
      player.onended = () => {
        URL.revokeObjectURL(url);
        setPlaying(false);
      };
      player.onerror = () => setPlaying(false);
      await player.play();
    } catch (error) {
      console.error(error);
      setPlaying(false);
      toast.error('Could not play the response.');
    }
  }

  return (
    <>
      <Head>
        <title>Missions · Atelier</title>
      </Head>
      <MissionStyles />
      <main className="missions-page">
        <EditorialMasthead
          active="studio"
          mobileAction={(
            <div className="missions-mobile-actions">
              <Link className="mobile-masthead-action" href="/atelier" aria-label="Back to today">
                Today
              </Link>
              <button
                className={`mobile-masthead-action ${customMissionDraftActive ? 'custom-draft' : ''}`}
                type="button"
                aria-label={customMissionDraftActive ? 'Continue custom mission setup' : 'Open mission switcher'}
                onClick={() => customMissionDraftActive ? openCustomMissionSheet(customMissionStep) : openMissionSwitcher()}
              >
                {customMissionDraftActive ? <Sparkles size={19} /> : <Menu size={20} />}
              </button>
            </div>
          )}
        />

        <div className="mission-spread page-grid">
          <section className="mission-main">
            <div className="mission-title">
              <div>
                <div className="t-mono">ATELIER DETOUR</div>
                <h1>Missions</h1>
              </div>
              <div className="mission-builder">
                <Link className="btn atelier-return" href="/atelier">
                  BACK TO TODAY <ArrowRight size={14} />
                </Link>
                <select value={missionType} onChange={(event) => setMissionType(event.target.value)} aria-label="Mission type">
                  {missionTypes.map((type) => <option key={type.id} value={type.id}>{type.label}</option>)}
                </select>
                <button className="btn red" disabled={creating} onClick={() => createMission({ cadence: 'ad_hoc' })}>
                  {creating ? <Loader2 className="spin" size={14} /> : <Sparkles size={14} />}
                  {creating ? 'CREATING' : 'NEW MISSION'} <ArrowRight size={14} />
                </button>
              </div>
            </div>
            {mission && (
              <MobileMissionSwitcher
                mission={mission}
                onOpen={openMissionSwitcher}
                expanded={showMissionSwitcher}
              />
            )}
            {visibleThreadContext && (
              <ThreadContextBanner
                context={visibleThreadContext}
                creating={creating}
              />
            )}

            <CustomMissionComposer
              scenario={customScenario}
              setScenario={setCustomScenario}
              outcome={customOutcome}
              setOutcome={setCustomOutcome}
              relationship={customRelationship}
              setRelationship={setCustomRelationship}
              register={customRegister}
              setRegister={setCustomRegister}
              creating={creating}
              onCreate={() => createMission({
                mission_type: missionType,
                cadence: 'ad_hoc',
                custom_scenario: customScenario,
                desired_outcome: customOutcome,
                relationship: customRelationship,
                register: customRegister,
                use_news: missionType === 'news_summary',
              })}
            />

            {loading ? (
              <MissionLoadingState />
            ) : loadError ? (
              <MissionErrorState message={loadError} creating={creating} onRetry={loadToday} onCreate={() => openCustomMissionSheet(0)} />
            ) : mission ? (
              <>
                <ColdOpen mission={mission} />
                <EpisodeBanner mission={mission} />
                <MissionPassport mission={mission} messenger={messenger} />
                <MissionFormatBrief mission={mission} />
                <RealityMessenger
                  mission={mission}
                  messenger={messenger}
                  turnText={turnText}
                  turnMode={turnMode}
                  setTurnText={(value) => {
                    setTurnText(value);
                    setTurnMode('chat');
                    setFailedTurn(null);
                    setComposerSent(false);
                  }}
                  composerState={mobileComposerState}
                  failedTurn={failedTurn}
                  submitting={submittingTurn}
                  recording={recording}
                  transcribing={transcribing}
                  playing={playing}
                  micError={micError}
                  onSubmitTurn={() => submitTurn(turnMode)}
                  onRetryTurn={() => failedTurn && submitTurn(failedTurn.mode, failedTurn.text)}
                  onEditFailedTurn={() => {
                    if (!failedTurn) return;
                    setTurnText(failedTurn.text);
                    setTurnMode(failedTurn.mode);
                    setFailedTurn(null);
                    setComposerSent(false);
                  }}
                  onRecord={() => recording ? stopRecording() : void startRecording()}
                  onUploadAudio={uploadAudioFile}
                  onPlay={playLastAssistant}
                />
                <TurnAdvanceCTA mission={mission} outcome={turnOutcome} />
                {!(mission.serial_thread_id || typeof mission.episode_index === 'number') && (
                  <MissionBridgePanel mission={mission} correction={correction} />
                )}
                <MobileMissionFinishCard
                  mission={mission}
                  completing={completing}
                  onComplete={completeMission}
                />
                <button className="mobile-custom-mission-entry" type="button" onClick={() => openCustomMissionSheet(customMissionDraftActive ? customMissionStep : 0)}>
                  <Sparkles size={14} />
                  {customMissionDraftActive ? 'Continue custom mission' : 'Custom mission'}
                  <ArrowRight size={13} />
                </button>
                <DispatchDraft
                  mission={mission}
                  messenger={messenger}
                  text={writingText}
                  setText={setWritingText}
                  submitting={submittingWriting}
                  onSubmit={submitWriting}
                />
                <MissionDebrief mission={mission} />
                <div className="complete-row">
                  <Link className="btn" href={missionFeuilletonHref(mission, correction)}>
                    MAKE FEUILLETON <ArrowRight size={14} />
                  </Link>
                  <button className="btn solid lg" disabled={completing || mission.status === 'completed'} onClick={completeMission}>
                    {mission.status === 'completed' ? 'MISSION COMPLETE' : 'COMPLETE MISSION'} <Check size={15} />
                  </button>
                </div>
              </>
            ) : (
              <MissionEmptyState creating={creating} onCreate={() => createMission({ cadence: 'ad_hoc' })} />
            )}
          </section>

          <aside className="mission-side">
            <MissionChooser today={today} selectedId={mission?.id} onSelect={selectMission} />
            <SceneLens mission={mission} messenger={messenger} />
            <Objectives mission={mission} correction={correction} />
            <CorrectionStack correction={correction} />
          </aside>
        </div>
        {showMissionSwitcher && (
          <MissionSwitcherSheet
            today={today}
            selectedId={mission?.id}
            selectedMission={mission}
            creating={creating}
            customDraftActive={customMissionDraftActive}
            onClose={() => setShowMissionSwitcher(false)}
            onCreate={() => {
              openCustomMissionSheet(customMissionDraftActive ? customMissionStep : 0);
            }}
            onSelect={(next) => {
              selectMission(next);
              setShowMissionSwitcher(false);
            }}
          />
        )}
        {showCustomMissionSheet && (
          <MobileCustomMissionSheet
            step={customMissionStep}
            setStep={setCustomMissionStep}
            scenario={customScenario}
            setScenario={setCustomScenario}
            outcome={customOutcome}
            setOutcome={setCustomOutcome}
            relationship={customRelationship}
            setRelationship={setCustomRelationship}
            register={customRegister}
            setRegister={setCustomRegister}
            name={customMissionName}
            setName={setCustomMissionName}
            concepts={customConcepts}
            selectedConceptIds={customConceptIds}
            setSelectedConceptIds={setCustomConceptIds}
            loadingConcepts={customConceptsLoading}
            vocabulary={customVocabulary}
            selectedVocabularyIds={customVocabularyIds}
            setSelectedVocabularyIds={setCustomVocabularyIds}
            loadingVocabulary={customVocabularyLoading}
            creating={creating}
            onClose={() => setShowCustomMissionSheet(false)}
            onCreate={() => createMission({
              mission_type: missionType,
              cadence: 'ad_hoc',
              custom_scenario: customMissionName.trim()
                ? `${customMissionName.trim()}: ${customScenario}`
                : customScenario,
              desired_outcome: customOutcome,
              relationship: customRelationship,
              register: customRegister,
              preferred_concept_ids: customConceptIds.length ? customConceptIds : undefined,
              preferred_vocabulary_ids: customVocabularyIds.length ? customVocabularyIds : undefined,
              use_news: missionType === 'news_summary',
            })}
          />
        )}
      </main>
    </>
  );
}

function MobileMissionSwitcher({
  mission,
  onOpen,
  expanded,
}: {
  mission: RealWorldMission;
  onOpen: () => void;
  expanded: boolean;
}) {
  const progress = missionObjectiveProgress(mission);
  return (
    <button
      className="mobile-mission-switcher"
      data-testid="mobile-mission-switcher"
      data-mission-id={mission.id}
      type="button"
      aria-label="Switch mission"
      aria-expanded={expanded}
      onClick={onOpen}
    >
      <span className="switcher-dot" aria-hidden="true" />
      <div>
        <div className="mobile-meta">Mission · {missionCadenceLabel(mission.cadence, mission)}</div>
        <strong>{missionDisplayTitle(mission)}</strong>
        <p>{progress.text} · {missionDeadlineLabel(mission)}</p>
      </div>
      <ArrowRight size={16} aria-hidden="true" />
    </button>
  );
}

function countLabel(count: number, singular: string, plural: string) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function shortThreadId(value: string) {
  const text = value.trim();
  if (text.length <= 12) return text;
  return `${text.slice(0, 5)}...${text.slice(-4)}`;
}

function ThreadContextBanner({
  context,
  creating,
}: {
  context: ThreadSeedContext;
  creating: boolean;
}) {
  const chips = [
    context.conceptIds.length && {
      tone: 'grammar',
      label: 'Grammar',
      value: countLabel(context.conceptIds.length, 'rule', 'rules'),
    },
    context.vocabularyIds.length && {
      tone: 'vocabulary',
      label: 'Vocabulary',
      value: countLabel(context.vocabularyIds.length, 'word', 'words'),
    },
    context.erratumIds.length && {
      tone: 'errata',
      label: 'Errata',
      value: countLabel(context.erratumIds.length, 'erratum', 'errata'),
    },
    context.atelierSessionId && {
      tone: 'session',
      label: 'Atelier Session',
      value: shortThreadId(context.atelierSessionId),
    },
  ].filter(Boolean) as Array<{ tone: string; label: string; value: string }>;

  return (
    <section className="paper thread-context-banner" aria-label="Today's Thread context">
      <div className="thread-context-copy">
        <div className="t-mono">TODAY&apos;S THREAD</div>
        <h2>Mission seeded from Atelier</h2>
        <p>
          This field loop is carrying context from today&apos;s thread into the mission:
          use the linked grammar, vocabulary, and repairs in a message that could actually be sent.
        </p>
      </div>
      <div className="thread-context-side">
        <span className="thread-context-status">{creating ? 'Building mission' : 'Thread context active'}</span>
        <div className="thread-context-chips" aria-label="Seeded mission context">
          {chips.map((chip) => (
            <span key={chip.label} className={`thread-chip ${chip.tone}`}>
              <strong>{chip.label}</strong>
              <em>{chip.value}</em>
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function MissionSwitcherSheet({
  today,
  selectedId,
  selectedMission,
  creating,
  customDraftActive,
  onClose,
  onSelect,
  onCreate,
}: {
  today: MissionToday | null;
  selectedId?: string;
  selectedMission: RealWorldMission | null;
  creating: boolean;
  customDraftActive: boolean;
  onClose: () => void;
  onSelect: (mission: RealWorldMission) => void;
  onCreate: () => void;
}) {
  const queued = missionQueue(today);
  const selectedItem: MissionQueueItem[] = selectedMission && !queued.some((item) => item.mission.id === selectedMission.id)
    ? [{
      label: selectedMission.status === 'completed' ? 'Selected' : 'Current',
      mission: selectedMission,
      section: selectedMission.status === 'completed' ? 'inactive' : 'active',
    }]
    : [];
  const active = uniqueMissionItems([...selectedItem, ...queued])
    .filter((item) => item.section === 'active')
    .slice(0, 4);
  const inactive = uniqueMissionItems([...queued, ...selectedItem])
    .filter((item) => item.section === 'inactive' && !active.some((activeItem) => activeItem.mission.id === item.mission.id))
    .slice(0, 4);
  return (
    <div className="mobile-mission-sheet-layer" role="presentation">
      <button className="mobile-sheet-backdrop" type="button" aria-label="Close mission switcher" onClick={onClose} />
      <section className="mobile-mission-sheet" data-testid="mission-switcher-sheet" role="dialog" aria-modal="true" aria-labelledby="mission-switcher-title">
        <div className="sheet-handle" aria-hidden="true" />
        <header>
          <div>
            <div className="mobile-meta">Ready + recent</div>
            <h2 id="mission-switcher-title">Switch mission</h2>
          </div>
          <button className="sheet-close" type="button" onClick={onClose}>Close</button>
        </header>
        <p className="sheet-count">{active.length} ready · {inactive.length} recent completed</p>
        <MissionSheetGroup title="Ready missions" items={active} selectedId={selectedId} onSelect={onSelect} empty="No ready mission yet." />
        <MissionSheetGroup title="Recent completed" items={inactive} selectedId={selectedId} onSelect={onSelect} empty="No completed missions yet." />
        <button className="btn solid mobile-sheet-create" data-testid="mission-switcher-create-custom" type="button" disabled={creating} onClick={onCreate}>
          {creating ? <Loader2 className="spin" size={14} /> : <Sparkles size={14} />}
          {creating ? 'Creating' : customDraftActive ? 'Continue custom setup' : 'New custom mission'}
        </button>
      </section>
    </div>
  );
}

function MissionSheetGroup({
  title,
  items,
  selectedId,
  onSelect,
  empty = 'No missions queued.',
}: {
  title: string;
  items: MissionQueueItem[];
  selectedId?: string;
  onSelect: (mission: RealWorldMission) => void;
  empty?: string;
}) {
  return (
    <div className="mission-sheet-group">
      <span className="mobile-meta">{title}</span>
      {items.map(({ label, mission }) => {
        const progress = missionObjectiveProgress(mission);
        const active = selectedId === mission.id;
        return (
          <button
            key={`${label}-${mission.id}`}
            className={active ? 'active' : ''}
            type="button"
            onClick={() => onSelect(mission)}
          >
            <span className="mission-row-dot" aria-hidden="true" />
            <span>
              <strong>{missionDisplayTitle(mission)}</strong>
              <small>{missionCadenceLabel(mission.cadence, mission)} · {missionTypeLabel(mission.mission_type)}</small>
            </span>
            <em>{progress.text} · {missionDeadlineLabel(mission)}</em>
            <ArrowRight className="mission-row-chevron" size={14} aria-hidden="true" />
          </button>
        );
      })}
      {!items.length && <p>{empty}</p>}
    </div>
  );
}

function MobileCustomMissionSheet({
  step,
  setStep,
  scenario,
  setScenario,
  outcome,
  setOutcome,
  relationship,
  setRelationship,
  register,
  setRegister,
  name,
  setName,
  concepts,
  selectedConceptIds,
  setSelectedConceptIds,
  loadingConcepts,
  vocabulary,
  selectedVocabularyIds,
  setSelectedVocabularyIds,
  loadingVocabulary,
  creating,
  onClose,
  onCreate,
}: {
  step: number;
  setStep: (step: number) => void;
  scenario: string;
  setScenario: (value: string) => void;
  outcome: string;
  setOutcome: (value: string) => void;
  relationship: string;
  setRelationship: (value: string) => void;
  register: string;
  setRegister: (value: string) => void;
  name: string;
  setName: (value: string) => void;
  concepts: TargetConcept[];
  selectedConceptIds: number[];
  setSelectedConceptIds: (ids: number[]) => void;
  loadingConcepts: boolean;
  vocabulary: TargetVocabulary[];
  selectedVocabularyIds: number[];
  setSelectedVocabularyIds: (ids: number[]) => void;
  loadingVocabulary: boolean;
  creating: boolean;
  onClose: () => void;
  onCreate: () => void;
}) {
  const canLeaveTopic = scenario.trim().length >= 12;
  const targetsLoading = loadingConcepts || loadingVocabulary;
  const hasTargetOptions = concepts.length > 0 || vocabulary.length > 0;
  const selectedTargetCount = selectedConceptIds.length + selectedVocabularyIds.length;
  const canLeaveTargets = targetsLoading || !hasTargetOptions || selectedTargetCount > 0;
  const canCreate = canLeaveTopic && (name.trim().length >= 3 || outcome.trim().length >= 3);
  const topicValidation = scenario.trim() && !canLeaveTopic ? 'Add a little more context so the mission has something real to work with.' : '';
  const targetValidation = !targetsLoading && hasTargetOptions && !selectedTargetCount ? 'Pick at least one grammar or vocabulary target before continuing.' : '';
  const confirmValidation = step === 2 && !canCreate ? 'Name the mission or describe the outcome before creating it.' : '';
  const selectedVocabulary = vocabulary.filter((item) => selectedVocabularyIds.includes(item.word_id));
  const toggleConcept = (id: number) => {
    setSelectedConceptIds(
      selectedConceptIds.includes(id)
        ? selectedConceptIds.filter((item) => item !== id)
        : [...selectedConceptIds, id].slice(0, 4),
    );
  };
  const toggleVocabulary = (id: number) => {
    setSelectedVocabularyIds(
      selectedVocabularyIds.includes(id)
        ? selectedVocabularyIds.filter((item) => item !== id)
        : [...selectedVocabularyIds, id].slice(0, 4),
    );
  };
  return (
    <div className="mobile-mission-sheet-layer custom-flow-layer" role="presentation">
      <button className="mobile-sheet-backdrop" type="button" aria-label="Close custom mission flow" onClick={onClose} />
      <section className="mobile-mission-sheet custom-mission-sheet" data-testid="custom-mission-sheet" role="dialog" aria-modal="true" aria-labelledby="custom-mission-title">
        <div className="sheet-handle" aria-hidden="true" />
        <header>
          <div>
            <div className="mobile-meta">Step {step + 1} of 3</div>
            <h2 id="custom-mission-title">{['Topic/context', 'Target concepts', 'Confirm/name'][step]}</h2>
          </div>
          <button className="sheet-close" type="button" onClick={onClose}>Close</button>
        </header>
        <div className="custom-step-dots" aria-hidden="true">
          {[0, 1, 2].map((item) => <span key={item} className={item <= step ? 'active' : ''} />)}
        </div>
        {step === 0 && (
          <div className="custom-step-panel">
            <label>
              <span>Topic/context</span>
              <textarea
                data-testid="custom-mission-scenario"
                value={scenario}
                onChange={(event) => setScenario(event.target.value)}
                placeholder="I need to text my landlord about the heating, explain a late train, or ask a pharmacy for advice..."
              />
              {topicValidation && <small className="field-validation">{topicValidation}</small>}
            </label>
            <label>
              <span>Outcome</span>
              <input data-testid="custom-mission-outcome" value={outcome} onChange={(event) => setOutcome(event.target.value)} placeholder="What should the other person know or do?" />
            </label>
            <div className="custom-two">
              <label>
                <span>Relationship</span>
                <input data-testid="custom-mission-relationship" value={relationship} onChange={(event) => setRelationship(event.target.value)} placeholder="landlord, colleague, friend..." />
              </label>
              <label>
                <span>Tone</span>
                <select data-testid="custom-mission-register" value={register} onChange={(event) => setRegister(event.target.value)}>
                  <option value="polite neutral">Polite neutral</option>
                  <option value="polite formal">Polite formal</option>
                  <option value="warm informal">Warm informal</option>
                  <option value="firm but calm">Firm but calm</option>
                </select>
              </label>
            </div>
          </div>
        )}
        {step === 1 && (
          <div className="custom-step-panel">
            <p className="custom-help">Pick grammar and up to four vocabulary targets. Due SRS items are shown first, with examples when available.</p>
            {targetValidation && <p className="field-validation sheet-validation">{targetValidation}</p>}
            <div className="target-section-head">
              <span>Grammar</span>
              <small>{selectedConceptIds.length}/4 selected</small>
            </div>
            <div className="target-concept-grid">
              {loadingConcepts && <span className="concept-loading">Loading concepts...</span>}
              {!loadingConcepts && concepts.slice(0, 18).map((concept) => (
                <button
                  key={concept.id}
                  className={[
                    selectedConceptIds.includes(concept.id) ? 'selected' : '',
                    concept.recommendation_source === 'notebook' ? 'notebook' : 'due',
                  ].filter(Boolean).join(' ')}
                  type="button"
                  data-testid="custom-concept-option"
                  onClick={() => toggleConcept(concept.id)}
                >
                  <span>{concept.recommendation_label}</span>
                  <strong>{concept.display_title || concept.name}</strong>
                  <small>{concept.level} · {concept.localized_category || concept.category || 'Grammar'}</small>
                </button>
              ))}
            </div>
            <div className="target-section-head">
              <span>Vocabulary</span>
              <small>{selectedVocabularyIds.length}/4 selected</small>
            </div>
            <div className="target-vocabulary-grid">
              {loadingVocabulary && <span className="concept-loading">Loading vocabulary...</span>}
              {!loadingVocabulary && !vocabulary.length && <span className="concept-loading">No due vocabulary found right now.</span>}
              {!loadingVocabulary && vocabulary.slice(0, 18).map((item) => {
                const translation = vocabularyTranslation(item);
                const example = item.example_sentence || (item as any).example_translation;
                return (
                  <button
                    key={item.word_id}
                    className={selectedVocabularyIds.includes(item.word_id) ? 'selected' : ''}
                    type="button"
                    data-testid="custom-vocabulary-option"
                    onClick={() => toggleVocabulary(item.word_id)}
                  >
                    <span>{item.recommendation_label}</span>
                    <strong>{item.word}</strong>
                    {translation && <small>{translation}</small>}
                    {example && <em>{compactText(example, 84)}</em>}
                  </button>
                );
              })}
            </div>
          </div>
        )}
        {step === 2 && (
          <div className="custom-step-panel">
            <label>
              <span>Mission name</span>
              <input data-testid="custom-mission-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Landlord heating message" />
            </label>
            <div className="custom-confirm-card">
              <span className="mobile-meta">Ready to create</span>
              <strong>{name || 'Custom French mission'}</strong>
              <p>{scenario || 'No context yet.'}</p>
              <small>
                {selectedConceptIds.length || 'Suggested'} grammar · {selectedVocabularyIds.length} vocabulary · {register}
              </small>
              {selectedVocabulary.length > 0 && (
                <div className="confirm-vocabulary">
                  {selectedVocabulary.map((item) => (
                    <span key={item.word_id}>{item.word}</span>
                  ))}
                </div>
              )}
            </div>
            {confirmValidation && <p className="field-validation sheet-validation">{confirmValidation}</p>}
          </div>
        )}
        <footer className="custom-flow-actions">
          <button type="button" data-testid="custom-mission-back" disabled={step === 0} onClick={() => setStep(Math.max(0, step - 1))}>Back</button>
          {step < 2 ? (
            <button
              type="button"
              data-testid="custom-mission-next"
              disabled={step === 0 ? !canLeaveTopic : !canLeaveTargets}
              onClick={() => setStep(Math.min(2, step + 1))}
            >
              Next
            </button>
          ) : (
            <button type="button" data-testid="custom-mission-create" disabled={creating || !canCreate} onClick={onCreate}>
              {creating ? 'Creating' : 'Create mission'}
            </button>
          )}
        </footer>
      </section>
    </div>
  );
}

function MissionLoadingState() {
  return (
    <div className="paper loading mission-loading" role="status" aria-live="polite">
      <div className="loading-line">
        <Loader2 className="spin" />
        <span>LOADING MISSIONS</span>
      </div>
      <div className="mobile-loading-stack" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}

function MissionErrorState({
  message,
  creating,
  onRetry,
  onCreate,
}: {
  message: string;
  creating: boolean;
  onRetry: () => void;
  onCreate: () => void;
}) {
  return (
    <div className="paper empty-state mission-empty mission-error" role="alert">
      <span>Could not load missions.</span>
      <p className="mobile-empty-copy">{message}</p>
      <div className="mobile-state-actions">
        <button className="btn red mobile-empty-cta" type="button" onClick={onRetry}>
          <ArrowRight size={14} />
          RETRY SYNC
        </button>
        <button className="btn mobile-empty-cta" type="button" disabled={creating} onClick={onCreate}>
          {creating ? <Loader2 className="spin" size={14} /> : <Sparkles size={14} />}
          CUSTOM MISSION
        </button>
      </div>
    </div>
  );
}

function MissionEmptyState({ creating, onCreate }: { creating: boolean; onCreate: () => void }) {
  return (
    <div className="paper empty-state mission-empty">
      <span>No mission is available yet.</span>
      <p className="mobile-empty-copy">Start a quick field loop, then answer it like a real message thread.</p>
      <div className="mobile-state-actions">
        <button className="btn red mobile-empty-cta" type="button" disabled={creating} onClick={onCreate}>
          {creating ? <Loader2 className="spin" size={14} /> : <Sparkles size={14} />}
          {creating ? 'CREATING' : 'START A MISSION'}
        </button>
      </div>
    </div>
  );
}

function ColdOpen({ mission }: { mission: RealWorldMission }) {
  const coldOpen = ((mission.source_snapshot || {}).cold_open || null) as Record<string, any> | null;
  const storageKey = `serial:coldopen:${mission.serial_thread_id || 'thread'}`;
  const [mounted, setMounted] = useState(false);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    setMounted(true);
    try {
      setSeen(window.localStorage.getItem(storageKey) === 'seen');
    } catch {
      setSeen(false);
    }
  }, [storageKey]);

  const isEpisodeZero = mission.episode_index === 0;
  const started = (mission.turns || []).length > 0 || (mission.attempts || []).length > 0 || mission.status !== 'available';
  const paragraphs = Array.isArray(coldOpen?.paragraphs) ? (coldOpen?.paragraphs as string[]) : [];
  if (!mounted || seen || !isEpisodeZero || started || paragraphs.length === 0) return null;

  function begin() {
    try {
      window.localStorage.setItem(storageKey, 'seen');
    } catch {
      /* ignore */
    }
    setSeen(true);
  }

  return (
    <section className="cold-open" aria-label="Story prologue" data-testid="serial-cold-open">
      <div className="cold-open-sheet">
        <span className="cold-open-eyebrow">{coldOpen?.eyebrow || 'A new serial'}</span>
        <h1 className="cold-open-title">{coldOpen?.title || 'Bienvenue à Paris'}</h1>
        <span className="cold-open-dateline">{coldOpen?.dateline || 'Paris · tonight'}</span>
        <div className="cold-open-body">
          {paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)}
        </div>
        <button className="btn solid lg" type="button" onClick={begin} data-testid="serial-cold-open-begin">
          {coldOpen?.cta || 'Begin Episode 1'} <ArrowRight size={15} />
        </button>
        {coldOpen?.footer && <p className="cold-open-footer">{coldOpen.footer}</p>}
      </div>
      <style jsx>{`
        .cold-open { display: grid; place-items: center; padding: 8px 0 4px; }
        .cold-open-sheet { width: 100%; display: grid; gap: 11px; padding: 26px 20px 22px; background: var(--ink); color: var(--paper, #f1ece1); border: 1px solid var(--ink); }
        .cold-open-eyebrow { font-size: 11px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; color: var(--char-romy, #7da0e8); }
        .cold-open-title { margin: 0; font-size: 30px; line-height: 1.04; font-style: italic; }
        .cold-open-dateline { font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; opacity: .6; }
        .cold-open-body { display: grid; gap: 11px; margin-top: 4px; }
        .cold-open-body p { margin: 0; line-height: 1.55; font-size: 16px; opacity: .94; }
        .cold-open :global(.btn.solid.lg) { justify-self: start; margin-top: 8px; background: var(--red, #d8321a); color: white; border-color: var(--red, #d8321a); }
        .cold-open-footer { margin: 6px 0 0; font-size: 12px; font-style: italic; opacity: .62; }
      `}</style>
    </section>
  );
}

function EpisodeBanner({ mission }: { mission: RealWorldMission }) {
  const episodeIndex = typeof mission.episode_index === 'number' ? mission.episode_index : null;
  const isSerial = Boolean(mission.serial_thread_id) || episodeIndex !== null;
  if (!isSerial) return null;
  const messenger = getMessenger(mission);
  const snapshot = (mission.source_snapshot || {}) as Record<string, any>;
  const previously = typeof snapshot.previously === 'string'
    ? snapshot.previously
    : (mission.prompt_payload as any)?.hook_from_previous?.text || null;
  const location = typeof snapshot.location_name === 'string' ? snapshot.location_name : 'Paris';
  return (
    <section className="paper episode-banner" aria-label="Story episode">
      <div className="episode-dateline">
        <span className="t-mono">Episode {(episodeIndex ?? 0) + 1}</span>
        <span className="episode-loc">{location}</span>
      </div>
      <h2 className="episode-title">{missionDisplayTitle(mission)}</h2>
      {previously && (
        <p className="episode-previously"><span className="t-mono-low">Previously</span> {previously}</p>
      )}
      <p className="episode-scene">{missionDisplayBrief(mission)}</p>
      <div className="episode-addressee">
        <span className="episode-avatar" aria-hidden="true">{messenger.contact_initials}</span>
        <div>
          <strong>To: {messenger.contact_name}</strong>
          <span>{messenger.contact_role}</span>
        </div>
      </div>
      <style jsx>{`
        .episode-banner { display: grid; gap: 9px; padding: 15px 16px 14px; border-left: 5px solid var(--char-marchand, var(--ink-3)); }
        .episode-dateline { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
        .episode-dateline .episode-loc { font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; color: var(--ink-3); }
        .episode-title { margin: 0; font-size: 22px; line-height: 1.08; font-style: italic; }
        .episode-previously { margin: 0; font-size: 13px; line-height: 1.4; color: var(--ink-2); }
        .episode-previously .t-mono-low { margin-right: 6px; color: var(--char-romy, var(--blue)); }
        .episode-scene { margin: 0; line-height: 1.45; color: var(--ink); }
        .episode-addressee { display: flex; align-items: center; gap: 10px; margin-top: 3px; padding-top: 11px; border-top: 1px solid rgba(20,17,13,.12); }
        .episode-avatar { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; background: var(--char-marchand, var(--ink-3)); color: white; font-size: 12px; font-weight: 800; flex: none; }
        .episode-addressee strong { display: block; font-size: 14px; }
        .episode-addressee span { font-size: 11px; color: var(--ink-3); }
      `}</style>
    </section>
  );
}

function TurnAdvanceCTA({ mission, outcome }: { mission: RealWorldMission; outcome: Record<string, any> | null }) {
  if (!outcome) return null;
  const hook = (outcome.hook && typeof outcome.hook === 'object' ? outcome.hook : null) as Record<string, any> | null;
  const ready = Boolean(outcome.ready_to_advance) || Boolean(hook?.text);
  if (!ready) return null;
  return (
    <div className="turn-advance" data-testid="mission-turn-advance">
      <span className="t-mono-low">The reply landed in the serial</span>
      <p className="turn-advance-hook">{hook?.text || 'You got what you needed. See what it changes.'}</p>
      <Link className="btn solid" href={missionFeuilletonHref(mission, null)}>
        See what happens <ArrowRight size={14} />
      </Link>
      <style jsx>{`
        .turn-advance { display: grid; gap: 7px; padding: 13px 15px; background: var(--paper-2, #f8f3e8); border: 1px solid rgba(20,17,13,.16); border-left: 5px solid var(--char-romy, var(--blue)); }
        .turn-advance .turn-advance-hook { margin: 0; line-height: 1.42; font-style: italic; color: var(--ink); }
        .turn-advance :global(.btn.solid) { justify-self: start; margin-top: 3px; }
      `}</style>
    </div>
  );
}

function MissionPassport({ mission, messenger }: { mission: RealWorldMission; messenger: MissionMessenger }) {
  return (
    <section className="paper mission-passport">
      <CropMarks />
      <div className="passport-grid">
        <div>
          <div className="mission-kicker">
            <span>{missionFormatLabel(mission)}</span>
            <span>{mission.cadence === 'post_session' ? 'After Atelier' : mission.cadence}</span>
            <span>{missionStatusLabel(mission.status)}</span>
          </div>
          <h2>{missionDisplayTitle(mission)}</h2>
          <p>{missionDisplayBrief(mission)}</p>
        </div>
        <div className="signal-card">
          <span className="t-mono">SUCCESS SIGNAL</span>
          <strong>{messenger.success_signal}</strong>
          <small>{messenger.dispatch_note}</small>
        </div>
      </div>
      <div className="mission-loop" aria-label="Mission loop">
        <span>Scene</span>
        <ArrowRight size={13} />
        <span>Reply</span>
        <ArrowRight size={13} />
        <span>Repair</span>
        <ArrowRight size={13} />
        <span>Send</span>
      </div>
    </section>
  );
}

function MissionFormatBrief({ mission }: { mission: RealWorldMission }) {
  const prompt = mission.prompt_payload || {};
  const payload = (prompt.mission_format_payload && typeof prompt.mission_format_payload === 'object')
    ? prompt.mission_format_payload as Record<string, any>
    : {};
  const format = mission.mission_format || prompt.mission_format || payload.kind || 'chat_message';
  const [showTranscript, setShowTranscript] = useState(false);
  if (format === 'chat_message' || !payload.kind) return null;
  if (format === 'voicemail_reply') {
    const transcript = String(payload.transcript || '');
    return (
      <section className="paper format-brief voicemail">
        <div className="format-icon"><Volume2 size={18} /></div>
        <div className="format-copy">
          <span className="t-mono">VOICE NOTE</span>
          <h3>{payload.caller || 'The contact'} left a voicemail.</h3>
          <p>Reply by text or voice; the same correction engine grades the transcript.</p>
          {payload.audio_payload?.url && (
            <audio className="format-audio" controls src={String(payload.audio_payload.url)}>
              Voice note audio
            </audio>
          )}
          {transcript && (
            <button type="button" className="format-toggle" onClick={() => setShowTranscript((value) => !value)}>
              {showTranscript ? 'Hide transcript' : 'Show transcript'}
            </button>
          )}
          {showTranscript && <blockquote>{transcript}</blockquote>}
        </div>
      </section>
    );
  }
  if (format === 'email_formal') {
    const required = asStringList(payload.required_parts);
    return (
      <section className="paper format-brief email">
        <div className="format-icon"><Mail size={18} /></div>
        <div className="format-copy">
          <span className="t-mono">FORMAL EMAIL</span>
          <h3>{payload.subject || 'Subject required'}</h3>
          <p>{payload.salutation || 'Bonjour,'} · {payload.closing || 'Cordialement,'}</p>
          {!!required.length && (
            <div className="format-chips">
              {required.map((item) => <span key={item}>{item}</span>)}
            </div>
          )}
        </div>
      </section>
    );
  }
  if (format === 'admin_form') {
    const fields = Array.isArray(payload.fields) ? payload.fields : [];
    return (
      <section className="paper format-brief admin-form">
        <div className="format-icon"><FileText size={18} /></div>
        <div className="format-copy">
          <span className="t-mono">ADMIN FORM</span>
          <h3>{payload.agency || 'French office form'}</h3>
          <div className="format-fields">
            {fields.map((field: any) => (
              <span key={String(field.id || field.label)}>
                {String(field.label || field.id)}{field.required ? ' *' : ''}
              </span>
            ))}
          </div>
        </div>
      </section>
    );
  }
  return null;
}

function CustomMissionComposer({
  scenario,
  setScenario,
  outcome,
  setOutcome,
  relationship,
  setRelationship,
  register,
  setRegister,
  creating,
  onCreate,
}: {
  scenario: string;
  setScenario: (value: string) => void;
  outcome: string;
  setOutcome: (value: string) => void;
  relationship: string;
  setRelationship: (value: string) => void;
  register: string;
  setRegister: (value: string) => void;
  creating: boolean;
  onCreate: () => void;
}) {
  const canCreate = scenario.trim().length >= 12;
  const hasDraft = Boolean(scenario.trim() || outcome.trim() || relationship.trim());
  const [expanded, setExpanded] = useState(false);
  return (
    <section className={`paper custom-composer ${expanded ? 'expanded' : ''}`}>
      <div className="composer-copy">
        <div className="composer-topline">
          <div className="t-mono">CUSTOM REALITY MISSION</div>
          <span>{canCreate ? 'ready' : hasDraft ? 'draft' : 'optional'}</span>
        </div>
        <h2>Bring the thing you actually need to say.</h2>
        <p>Use the exact situation, person, outcome, and tone you need outside the app.</p>
        <button
          className="btn ghost composer-toggle"
          type="button"
          aria-expanded={expanded}
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? 'HIDE CUSTOM FORM' : hasDraft ? 'CONTINUE CUSTOM DRAFT' : 'CUSTOM MISSION'} <ArrowRight size={13} />
        </button>
      </div>
      <div className="composer-form">
        <textarea
          value={scenario}
          onChange={(event) => setScenario(event.target.value)}
          placeholder="I need to text my landlord about the heating, explain a delay to a colleague, ask a pharmacy for advice..."
        />
        <div className="composer-row">
          <input
            value={outcome}
            onChange={(event) => setOutcome(event.target.value)}
            placeholder="Desired outcome"
          />
          <input
            value={relationship}
            onChange={(event) => setRelationship(event.target.value)}
            placeholder="Relationship"
          />
          <select value={register} onChange={(event) => setRegister(event.target.value)} aria-label="Custom mission register">
            <option value="polite neutral">Polite neutral</option>
            <option value="polite formal">Polite formal</option>
            <option value="warm informal">Warm informal</option>
            <option value="firm but calm">Firm but calm</option>
          </select>
        </div>
        <button className="btn solid" disabled={creating || !canCreate} onClick={onCreate}>
          {creating ? <Loader2 className="spin" size={14} /> : <Sparkles size={14} />}
          MAKE IT A MISSION
        </button>
      </div>
    </section>
  );
}

function RealityMessenger({
  mission,
  messenger,
  turnText,
  turnMode,
  setTurnText,
  failedTurn,
  composerState,
  submitting,
  recording,
  transcribing,
  playing,
  micError,
  onSubmitTurn,
  onRetryTurn,
  onEditFailedTurn,
  onRecord,
  onUploadAudio,
  onPlay,
}: {
  mission: RealWorldMission;
  messenger: MissionMessenger;
  turnText: string;
  turnMode: 'chat' | 'voice';
  setTurnText: (value: string) => void;
  failedTurn: FailedTurn | null;
  composerState: MobileComposerState;
  submitting: boolean;
  recording: boolean;
  transcribing: boolean;
  playing: boolean;
  micError: string | null;
  onSubmitTurn: () => void;
  onRetryTurn: () => void;
  onEditFailedTurn: () => void;
  onRecord: () => void;
  onUploadAudio: (file?: File | null) => void;
  onPlay: () => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messageListRef = useRef<HTMLDivElement>(null);
  const turns = mission.turns || [];
  const visibleTurns = turns.length ? turns : [{
    id: 'opening',
    role: 'assistant',
    mode: 'chat',
    text: messenger.opening_message,
    turn_index: 0,
    correction: {},
  }];
  const canPlay = turns.some((turn) => turn.role === 'assistant');
  const isClosed = mission.status === 'completed';
  const voiceStatus = transcribing
    ? {
      title: 'Preparing your transcript',
      detail: 'Keep this screen open while the audio is turned into a draft.',
    }
    : recording
      ? {
        title: 'Recording now',
        detail: 'Stop when the message is complete; the transcript will appear in the composer.',
      }
      : turnMode === 'voice' && turnText.trim()
        ? {
          title: 'Voice transcript ready',
          detail: 'Give it one quick read, then send it into the thread.',
        }
        : {
          title: 'Speak or upload audio',
          detail: 'Use voice when typing slows the exchange down.',
        };
  const composerCopy = {
    default: { label: 'Resting composer', text: 'Write or record the next useful French reply.' },
    typing: { label: 'Keyboard ready', text: 'Keep it short enough to send naturally.' },
    voice: { label: recording ? 'Recording now' : transcribing ? 'Transcribing audio' : 'Voice draft', text: voiceStatus.detail },
    sent: { label: 'Message sent', text: 'The thread has advanced. Continue or polish the final dispatch.' },
    failed: { label: 'Send failed', text: 'Retry the exact message or edit it before sending again.' },
  }[composerState];

  useEffect(() => {
    const list = messageListRef.current;
    if (!list) return;
    list.scrollTop = list.scrollHeight;
  }, [mission.id, visibleTurns.length, submitting, failedTurn?.text]);

  return (
    <section className="paper messenger-workspace" data-testid="mission-messenger" data-mission-id={mission.id}>
      <div className="workspace-head">
        <div>
          <div className="t-mono">REALITY MESSENGER</div>
          <h3>{messenger.thread_title}</h3>
        </div>
        <button className="btn ghost" disabled={!canPlay || playing} onClick={onPlay}>
          {playing ? 'PLAYING' : 'PLAY LAST'} <Play size={13} />
        </button>
      </div>

      <div className="mobile-thread-summary" aria-label="Mission snapshot">
        <span>{missionFormatLabel(mission)}</span>
        <span>{missionStatusLabel(mission.status)}</span>
        <span>{messenger.success_signal}</span>
      </div>

      <div className="messenger-grid">
        <div className="phone-shell" aria-label="Realistic mission message thread">
          <div className="phone-screen">
            <div className="phone-status">
              <span>{messenger.time_label}</span>
              <span>{messenger.channel_label}</span>
            </div>
            <div className="thread-contact">
              <div className="avatar">{messenger.contact_initials}</div>
              <div>
                <strong>{messenger.contact_name}</strong>
                <span>{messenger.contact_role} · {messenger.presence}</span>
              </div>
            </div>
            <div className="message-list" data-testid="mission-message-list" ref={messageListRef}>
              {visibleTurns.map((turn, index) => (
                <MessageBubble key={turn.id || `${turn.role}-${index}`} turn={turn} />
              ))}
              {submitting && <AnalysisInterstitial mission={mission} mode="turn" />}
            </div>
            {failedTurn && (
              <div className="retry-send-bar" role="status" aria-live="polite">
                <div>
                  <strong>{failedTurn.mode === 'voice' ? 'Voice transcript did not send.' : 'Message did not send.'}</strong>
                  <span className="failed-snippet">{failedTurn.text}</span>
                </div>
                <div className="retry-actions">
                  <button type="button" disabled={submitting} onClick={onEditFailedTurn}>
                    Edit
                  </button>
                  <button type="button" disabled={submitting} onClick={onRetryTurn}>
                    {submitting ? 'Retrying' : 'Retry'}
                  </button>
                </div>
              </div>
            )}
            <div className={`phone-composer state-${composerState}`}>
              <div className="mobile-composer-status" role={composerState === 'failed' ? 'alert' : composerState === 'sent' ? 'status' : undefined}>
                <span>{composerCopy.label}</span>
                <strong>{composerCopy.text}</strong>
              </div>
              <div className="composer-input-row">
                <button className="composer-mic" type="button" disabled={submitting || transcribing || isClosed} onClick={onRecord} aria-label={recording ? 'Stop recording' : 'Record voice message'}>
                  {transcribing ? <Loader2 className="spin" size={16} /> : recording ? <Square size={16} /> : <Mic size={16} />}
                </button>
                <textarea
                  data-testid="mission-turn-textarea"
                  value={turnText}
                  onChange={(event) => setTurnText(event.target.value)}
                  disabled={isClosed}
                  placeholder="Write the next French message..."
                />
                <button className="send-dot" data-testid="mission-send-turn" disabled={submitting || transcribing || recording || !turnText.trim() || isClosed} onClick={onSubmitTurn} aria-label="Send message">
                  {submitting ? <Loader2 className="spin" size={15} /> : <Send size={15} />}
                </button>
              </div>
              <div className="mobile-composer-tools">
                <button type="button" disabled={submitting || transcribing || isClosed} onClick={onRecord}>
                  {transcribing ? <Loader2 className="spin" size={13} /> : recording ? <Square size={13} /> : <Mic size={13} />}
                  {transcribing ? 'Transcribing' : recording ? 'Stop' : 'Voice'}
                </button>
                <button type="button" disabled={submitting || transcribing || recording || isClosed} onClick={() => fileInputRef.current?.click()}>
                  <Upload size={13} /> Audio
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="thread-tools">
          <div className={`voice-affordance ${recording ? 'recording' : ''} ${transcribing ? 'transcribing' : ''}`} role={recording || transcribing ? 'status' : undefined}>
            <span><Mic size={15} /></span>
            <div>
              <strong>{voiceStatus.title}</strong>
              <small>{voiceStatus.detail}</small>
            </div>
          </div>
          <div className="scene-strip">
            <MapPinned size={15} />
            <span>{messenger.scene_anchor}</span>
          </div>
          <p>{messenger.inbox_context}</p>
          <div className="quick-replies">
            <span className="t-mono-low">QUICK STARTS</span>
            {messenger.quick_replies.map((reply) => (
              <button key={reply} type="button" onClick={() => setTurnText(reply)} disabled={isClosed}>
                {reply}
              </button>
            ))}
          </div>
          <div className="action-row">
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*"
              className="sr-file"
              onChange={(event) => {
                onUploadAudio(event.target.files?.[0]);
                event.currentTarget.value = '';
              }}
            />
            <button className={`btn solid ${recording ? 'recording' : ''}`} disabled={submitting || transcribing || isClosed} onClick={onRecord}>
              {transcribing ? <Loader2 className="spin" size={14} /> : recording ? <Square size={14} /> : <Mic size={14} />}
              {transcribing ? 'TRANSCRIBING' : recording ? 'STOP' : 'RECORD'}
            </button>
            <button className="btn" disabled={submitting || transcribing || recording || isClosed} onClick={() => fileInputRef.current?.click()}>
              <Upload size={14} /> AUDIO
            </button>
          </div>
          {micError && <p className="voice-warning">{micError}</p>}
        </div>
      </div>
      {(recording || transcribing) && (
        <MobileVoiceTakeover
          recording={recording}
          transcribing={transcribing}
          onStop={onRecord}
          onUpload={() => fileInputRef.current?.click()}
        />
      )}
    </section>
  );
}

function AnalysisInterstitial({
  mission,
  mode,
}: {
  mission: RealWorldMission;
  mode: 'turn' | 'dispatch';
}) {
  const targets = missionAnalysisTargets(mission, latestCorrection(mission));
  const focusItems = [
    ...targets.grammar.map((label) => ({ label, tone: 'grammar' })),
    ...targets.vocabulary.map((label) => ({ label, tone: 'vocabulary' })),
    ...targets.repairs.map((label) => ({ label, tone: 'repair' })),
    ...(!targets.grammar.length && !targets.vocabulary.length && !targets.repairs.length
      ? targets.fallback.map((label) => ({ label, tone: 'fallback' }))
      : []),
  ].slice(0, 6);
  const title = mode === 'dispatch' ? 'Reviewing the final dispatch' : 'Checking the next turn';
  const detail = focusItems.length
    ? 'Target grammar, vocabulary, and repair memories are being checked now.'
    : 'Clarity, register, and the mission outcome are being checked now.';

  return (
    <div className="analysis-interstitial" role="status" aria-live="polite">
      <Loader2 className="spin" size={16} />
      <div>
        <span className="t-mono-low">ANALYSIS IN PROGRESS</span>
        <strong>{title}</strong>
        <p>{detail}</p>
        {focusItems.length > 0 && (
          <div className="analysis-targets">
            {focusItems.map((item) => (
              <em key={`${item.tone}-${item.label}`} className={item.tone}>{item.label}</em>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MobileVoiceTakeover({
  recording,
  transcribing,
  onStop,
  onUpload,
}: {
  recording: boolean;
  transcribing: boolean;
  onStop: () => void;
  onUpload: () => void;
}) {
  const bars = [8, 18, 28, 14, 34, 22, 12, 26, 32, 16, 10, 24, 30, 18];
  return (
    <div className="mobile-voice-layer" role="presentation">
      <div className="mobile-voice-scrim" aria-hidden="true" />
      <section className="mobile-voice-sheet" role="dialog" aria-modal="true" aria-labelledby="voice-sheet-title">
        <div className="sheet-handle" aria-hidden="true" />
        <div className="voice-sheet-head">
          <span className="voice-live-dot" aria-hidden="true" />
          <div>
            <div className="mobile-meta">{transcribing ? 'Transcript handoff' : 'Voice recording'}</div>
            <h2 id="voice-sheet-title">{transcribing ? 'Preparing transcript' : 'Recording in French'}</h2>
          </div>
        </div>
        <div className={`voice-waveform ${recording ? 'recording' : ''}`} aria-hidden="true">
          {bars.map((height, index) => <span key={index} style={{ height }} />)}
        </div>
        <p>{transcribing ? 'Keep this open while your audio becomes an editable composer draft.' : 'Stop when the message is complete. The transcript will land in the composer before you send.'}</p>
        <div className="voice-sheet-actions">
          <button className="voice-stop" type="button" disabled={transcribing} onClick={onStop}>
            {transcribing ? <Loader2 className="spin" size={15} /> : <Square size={15} />}
            {transcribing ? 'Transcribing' : 'Stop'}
          </button>
          <button type="button" disabled={recording || transcribing} onClick={onUpload}>
            <Upload size={15} />
            Upload audio
          </button>
        </div>
      </section>
    </div>
  );
}

function MessageBubble({ turn }: { turn: Record<string, any> }) {
  const isUser = turn.role === 'user';
  const correction = turn.correction || {};
  const feedback = correction.verdict ? correctionFeedback(correction) : null;
  const branch = turn.audio_payload?.branch;
  const errata = correctionErrata(correction);
  const hasNotes = Boolean(feedback) || errata.length > 0 || hasVocabularyCredit(correction);
  return (
    <div className={`message-row ${isUser ? 'user' : 'assistant'}`}>
      <div className="message-bubble-real">
        <p>{turn.text}</p>
        <span>{isUser ? 'sent' : 'received'} · {turn.mode || 'chat'}</span>
        {!isUser && branch?.label && (
          <small className={`branch-chip ${branch.state || ''}`}>
            {branch.label}
          </small>
        )}
        {isUser && hasNotes && (
          <details className={`turn-notes ${feedback?.tone || ''}`}>
            <summary>
              <span className="turn-notes-dot" aria-hidden="true" />
              <span className="turn-notes-label">Writing notes</span>
              {feedback && <span className="turn-notes-hint">{feedback.scoreLabel}</span>}
            </summary>
            <div className="turn-notes-body">
              {feedback && (
                <small className={`turn-verdict ${feedback.tone}`}>
                  <strong>{feedback.label}</strong>
                  <span>{feedback.scoreLabel}</span>
                  {feedback.support && <em>{feedback.support}</em>}
                </small>
              )}
              <VocabularyCreditBadge correction={correction} compact />
              {errata.length > 0 && <TurnRepairMarkup errata={errata} />}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}

function hasVocabularyCredit(correction: Record<string, any>): boolean {
  const events = correction?.vocabulary_events;
  if (Array.isArray(events) && events.length > 0) return true;
  const credit = correction?.vocabulary_credit;
  return Boolean(credit && typeof credit === 'object' && Object.keys(credit).length > 0);
}

function TurnRepairMarkup({ errata }: { errata: Record<string, any>[] }) {
  return (
    <div className="turn-repair-card" aria-label="Repair notes">
      <span className="t-mono-low">RED INK REPAIR</span>
      {errata.slice(0, 2).map((item, index) => {
        return (
          <RedInkRepairSlip
            key={`${item.id || item.display_label || 'repair'}-${index}`}
            compact
            className="turn-repair-slip"
            label={item.display_label || item.error_category || 'Repair'}
            learnerText={erratumText(item, ['learner_text', 'original_text', 'wrong_text'], 'Missing target')}
            correctedText={erratumText(item, ['corrected_target', 'correction', 'target'], 'Use the target form')}
            why={erratumText(item, ['why_wrong', 'reason'])}
            repair={erratumText(item, ['repair_hint', 'hint'])}
            meta={[item.source_label, item.review_mode].filter(Boolean).join(' · ')}
          />
        );
      })}
    </div>
  );
}

function MissionBridgePanel({
  mission,
  correction,
}: {
  mission: RealWorldMission;
  correction: Record<string, any> | null;
}) {
  const hasUserTurn = (mission.turns || []).some((turn) => turn.role === 'user');
  const isComplete = mission.status === 'completed';
  const vocabulary = missionTargetVocabulary(mission);
  const conceptIds = missionTargetConceptIds(mission);
  const errata = correctionErrata(correction);
  const firstConceptId = Number(errata.find((item) => Number.isFinite(Number(item.concept_id)))?.concept_id || conceptIds[0]);
  const firstVocabularyId = Number(vocabulary.find((item) => Number.isFinite(Number(item.word_id)))?.word_id);
  const hasTargets = conceptIds.length > 0 || vocabulary.length > 0 || errata.length > 0;
  if (!hasTargets || (!hasUserTurn && !isComplete)) return null;

  const reviewWordsHref = Number.isFinite(firstVocabularyId)
    ? routeWithQuery('/vocabulary', [['word', firstVocabularyId]])
    : '/vocabulary/review';
  const quickRepairHref = Number.isFinite(firstConceptId)
    ? routeWithQuery('/atelier', [['concept_id', firstConceptId]])
    : reviewWordsHref;
  const repairsHref = Number.isFinite(firstConceptId)
    ? routeWithQuery('/grammar', [['concept', firstConceptId]])
    : '/atelier';
  const feuilletonHref = missionFeuilletonHref(mission, correction);
  const focus = missionAnalysisTargets(mission, correction);
  const focusItems = [
    ...focus.grammar.map((label) => ({ label, tone: 'grammar' as const })),
    ...focus.vocabulary.map((label) => ({ label, tone: 'vocabulary' as const })),
    ...errata.slice(0, 2).map((item) => ({ label: item.display_label || 'Erratum', tone: 'errata' as const })),
  ].slice(0, 4);

  return (
    <ContinuationCard
      className="mission-bridge-panel"
      tone={errata.length ? 'errata' : 'mission'}
      eyebrow="Next repair bridge"
      title={isComplete ? 'Carry the mission into practice' : 'Keep the repair warm'}
      description={isComplete ? 'The targets are ready to leave the mission loop.' : 'Use the same targets again before they cool off.'}
      focus={focusItems}
      actions={[
        { label: 'Quick repair session', href: quickRepairHref, tone: 'primary' },
        { label: 'Review words', href: reviewWordsHref },
        { label: 'Read in Feuilleton', href: feuilletonHref },
        { label: 'File to repairs', href: repairsHref, tone: 'quiet' },
      ]}
    />
  );
}

function MissionDebrief({ mission }: { mission: RealWorldMission }) {
  const recap = mission.recap || {};
  const readiness = recap.readiness || null;
  const saved = recap.saved_to_srs?.phrase_bank || [];
  const branch = recap.branch_outcome || null;
  const outcome = mission.outcome || recap.outcome || null;
  const hook = outcome?.hook || null;
  const messenger = getMessenger(mission);
  if (mission.status !== 'completed' || !readiness) return null;
  return (
    <section className="paper debrief-panel">
      <div className="workspace-head">
        <div>
          <div className="t-mono">{outcome?.reply_text ? 'WORLD REPLY' : 'MISSION DEBRIEF'}</div>
          <h3>{outcome?.reply_text ? 'The reply landed in the serial' : branch?.label || 'Real-world readiness'}</h3>
        </div>
        <div className="readiness-score">
          <span>{readiness.overall}</span>
          <small>ready</small>
        </div>
      </div>
      {outcome?.reply_text && (
        <MissionWorldReplyCard
          mission={mission}
          messenger={messenger}
          replyText={outcome.reply_text}
          readiness={readiness}
        />
      )}
      {hook?.text && (
        <MissionOutcomeHook mission={mission} hook={hook} />
      )}
      <div className="readiness-grid">
        {[
          ['Clarity', readiness.clarity],
          ['Task fit', readiness.task_fit],
          ['Register', readiness.register],
          ['Repair stability', readiness.repair_stability],
          ['Naturalness', readiness.naturalness],
        ].map(([label, value]) => (
          <div key={label as string}>
            <span>{label}</span>
            <strong>{value as number}</strong>
          </div>
        ))}
      </div>
      {branch?.next_best_move && <p className="debrief-next">{branch.next_best_move}</p>}
      <div className="srs-bank">
        <div className="between">
          <span className="t-mono">SRS PHRASE BANK</span>
          <span className="t-mono-low">{saved.length}</span>
        </div>
        {saved.length ? saved.map((item: any) => (
          <article key={`${item.progress_id}-${item.phrase}`}>
            <strong>{item.phrase}</strong>
            <span>{item.translation} · queued for daily practice</span>
          </article>
        )) : (
          <p>No phrases were saved yet. Send or review a dispatch before completing.</p>
        )}
      </div>
      {recap.next_mission_seed?.custom_scenario && (
        <div className="next-seed">
          <span className="t-mono-low">NEXT MISSION SEED</span>
          <p>{recap.next_mission_seed.custom_scenario}</p>
        </div>
      )}
    </section>
  );
}

function MissionWorldReplyCard({
  mission,
  messenger,
  replyText,
  readiness,
}: {
  mission: RealWorldMission;
  messenger: MissionMessenger;
  replyText: string;
  readiness: Record<string, any>;
}) {
  const who = missionCharacterKey(mission, messenger);
  const mood = missionReplyMood(readiness);
  const needs = missionWorldNeeds(mission);
  const score = missionReadinessPips(readiness?.overall);
  return (
    <div className="s-reply mission-world-reply" data-char={who}>
      <div className="rhead">
        <SerialAvatar who={who} initials={messenger.contact_initials} mood={mood} />
        <div>
          <div className="nm">{messenger.contact_name}</div>
          <div className="mood">{mood === 'warm' ? 'Radouci · warm' : mood === 'confused' ? 'Perdu · confused' : 'Réservé · guarded'}</div>
        </div>
        <div className="loc">{messenger.scene_anchor}</div>
      </div>
      <div className="rbody">
        <div className="speech">{replyText}</div>
        <div className="gloss">This is the in-fiction reply: the score moves aside, and the person you wrote to becomes the payoff.</div>
        {needs.length > 0 && (
          <div className="s-needs">
            <div className="cap">What the world still needs</div>
            {needs.map((need, index) => (
              <div className={`n ${need.met ? 'met' : 'miss'}`} key={`${need.label}-${index}`}>
                <span className="box">{need.met && <Check size={9} aria-hidden="true" />}</span>
                <span className="t">{need.label}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="s-score">
        <span className="cap">Accuracy · optional</span>
        <span className="pips" aria-label={`${score} of 4 clarity`}>
          {[0, 1, 2, 3].map((item) => <i key={item} className={item < score ? 'on' : ''} />)}
        </span>
      </div>
    </div>
  );
}

function MissionOutcomeHook({ mission, hook }: { mission: RealWorldMission; hook: Record<string, any> }) {
  return (
    <div className="s-outcome mission-outcome-hook">
      <div className="cap">— The scene resolves —</div>
      <div className="what">{hook.teaser || 'The reply changes what happens next.'}</div>
      <div className="hook">{hook.text}</div>
      <Link className="s-cta-see" href={missionFeuilletonHref(mission)}>
        See what happens <Eye size={18} aria-hidden="true" />
      </Link>
    </div>
  );
}

function missionWorldNeeds(mission: RealWorldMission) {
  const objectives = missionObjectives(mission).slice(0, 3);
  if (!objectives.length) return [];
  const progress = latestMissionObjectiveProgress(mission);
  return objectives.map((objective) => {
    const state = progress.find((item: any) => item?.id === objective.id);
    return { label: String(objective.label || 'Move the scene forward'), met: state?.met !== false };
  });
}

function latestMissionObjectiveProgress(mission: RealWorldMission) {
  const turns = [...(mission.turns || [])].reverse();
  for (const turn of turns) {
    const progress = turn?.correction?.objective_progress;
    if (Array.isArray(progress)) return progress;
  }
  const attempts = [...(mission.attempts || [])].reverse();
  for (const attempt of attempts) {
    const progress = attempt?.correction?.objective_progress;
    if (Array.isArray(progress)) return progress;
  }
  return [];
}

function missionCharacterKey(mission: RealWorldMission, messenger: MissionMessenger) {
  const haystack = `${messenger.contact_name} ${messenger.contact_role} ${mission.title} ${mission.brief} ${mission.prompt_payload?.custom_scenario || ''}`.toLowerCase();
  if (haystack.includes('marchand') || haystack.includes('landlord') || haystack.includes('propriétaire')) return 'marchand';
  if (haystack.includes('romy') || haystack.includes('romane')) return 'romy';
  if (haystack.includes('marin')) return 'marin';
  if (haystack.includes('lila')) return 'lila';
  if (haystack.includes('gus') || haystack.includes('augustin')) return 'gus';
  if (haystack.includes('margaux')) return 'margaux';
  return 'toi';
}

function missionReplyMood(readiness: Record<string, any>): 'warm' | 'cool' | 'confused' {
  const score = Number(readiness?.overall);
  if (!Number.isFinite(score)) return 'warm';
  if (score < 55) return 'confused';
  if (score < 78) return 'cool';
  return 'warm';
}

function missionReadinessPips(value: unknown) {
  const score = Number(value);
  if (!Number.isFinite(score)) return 0;
  if (score <= 4) return Math.max(0, Math.min(4, Math.round(score)));
  return Math.max(0, Math.min(4, Math.ceil(score / 25)));
}

function SerialAvatar({ who, initials, mood }: { who: string; initials?: string; mood?: 'warm' | 'cool' | 'confused' }) {
  const fallback: Record<string, string> = {
    marin: 'M',
    lila: 'L',
    gus: 'G',
    romy: 'R',
    margaux: 'Mx',
    marchand: 'M·',
    toi: 'T',
  };
  const label = String(initials || fallback[who] || 'T').slice(0, 3);
  return (
    <span className="s-ava" data-char={who} style={label.length > 1 ? { fontSize: 15 } : undefined}>
      {label}
      {mood && <span className={`mood-pip ${mood}`}><i /></span>}
    </span>
  );
}

function MobileMissionFinishCard({
  mission,
  completing,
  onComplete,
}: {
  mission: RealWorldMission;
  completing: boolean;
  onComplete: () => void;
}) {
  const isComplete = mission.status === 'completed';
  const userTurns = (mission.turns || []).filter((turn) => turn.role === 'user').length;
  const attempts = mission.attempts?.length || 0;
  const hasInteraction = userTurns > 0 || attempts > 0;
  const recap = mission.recap || {};
  const readiness = recap.readiness || null;
  const branch = recap.branch_outcome || null;
  const outcome = mission.outcome || recap.outcome || null;
  const hook = outcome?.hook || null;
  const savedCount = Number(recap.saved_to_srs?.saved_count || recap.saved_to_srs?.phrase_bank?.length || 0);
  const credit = recap.vocabulary_credit || {};
  const creditTotal = Object.values(credit).reduce((sum, value) => sum + (typeof value === 'number' ? value : 0), 0);
  const completeLabel = completing ? 'Finishing' : hasInteraction ? 'Finish mission' : 'Send one reply first';

  return (
    <section className={`paper mobile-mission-finish ${isComplete ? 'completed' : ''}`} data-testid="mobile-mission-finish">
      <div className="mobile-finish-copy">
          <span className="t-mono-low">{isComplete ? 'Mission recap' : 'Finish loop'}</span>
        <strong>{isComplete ? outcome?.reply_text ? 'The world replied' : branch?.label || 'Real-world readiness unlocked' : 'Close it when your reply is useful'}</strong>
        <p>
          {isComplete
            ? outcome?.reply_text || branch?.next_best_move || 'Your mission is saved, and the useful phrases are ready for follow-up practice.'
            : hasInteraction
              ? 'You have a real reply in the thread. Finish to save the recap and target credit.'
              : 'Send one short French reply, then finish the mission from here.'}
        </p>
        {isComplete && hook?.text && <p>{hook.text}</p>}
      </div>
      {isComplete && readiness ? (
        <div className="mobile-finish-recap" data-testid="mobile-mission-debrief">
          <span>
            <strong>{readiness.overall}</strong>
            <em>ready</em>
          </span>
          <span>
            <strong>{savedCount}</strong>
            <em>phrases</em>
          </span>
          <span>
            <strong>{creditTotal}</strong>
            <em>target credits</em>
          </span>
        </div>
      ) : (
        <div className="mobile-finish-recap pending" aria-label="Mission interaction progress">
          <span>
            <strong>{userTurns}</strong>
            <em>thread replies</em>
          </span>
          <span>
            <strong>{attempts}</strong>
            <em>dispatches</em>
          </span>
        </div>
      )}
      <div className="mobile-finish-actions">
        {isComplete ? (
          <Link className="btn solid" href={missionFeuilletonHref(mission)} data-testid="mission-feuilleton-mobile">
            Next episode <ArrowRight size={14} />
          </Link>
        ) : (
          <button
            className="btn solid"
            type="button"
            data-testid="mission-complete-mobile"
            disabled={completing || !hasInteraction}
            onClick={onComplete}
          >
            {completing ? <Loader2 className="spin" size={14} /> : <Check size={14} />}
            {completeLabel}
          </button>
        )}
      </div>
    </section>
  );
}

function DispatchDraft({
  mission,
  messenger,
  text,
  setText,
  submitting,
  onSubmit,
}: {
  mission: RealWorldMission;
  messenger: MissionMessenger;
  text: string;
  setText: (value: string) => void;
  submitting: boolean;
  onSubmit: () => void;
}) {
  const prompt = mission.prompt_payload || {};
  const minWords = Number(prompt.min_words || 35);
  const maxWords = Number(prompt.max_words || 150);
  const count = wordCount(text);
  const isClosed = mission.status === 'completed';
  return (
    <section className="paper dispatch-draft">
      <div className="workspace-head">
        <div>
          <div className="t-mono">FINAL DISPATCH</div>
          <h3>{prompt.writing_title || 'Commit the message'}</h3>
        </div>
        <span className={count >= minWords && count <= maxWords ? 'word-meter good' : 'word-meter'}>
          {count} / {minWords}-{maxWords} words
        </span>
      </div>
      <p className="workspace-note">{prompt.writing_instruction || messenger.dispatch_note}</p>
      {submitting && <AnalysisInterstitial mission={mission} mode="dispatch" />}
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        disabled={isClosed}
        placeholder={prompt.writing_placeholder || 'Write the polished version you would actually send.'}
      />
      <div className="draft-footer">
        <div>
          <span className="t-mono-low">REALISM CHECK</span>
          <strong>{messenger.success_signal}</strong>
        </div>
        <button className="btn red" disabled={submitting || !text.trim() || isClosed} onClick={onSubmit}>
          {submitting ? 'ANALYZING TARGETS' : 'REVIEW DISPATCH'} <Send size={14} />
        </button>
      </div>
    </section>
  );
}

function MissionChooser({
  today,
  selectedId,
  onSelect,
}: {
  today: MissionToday | null;
  selectedId?: string;
  onSelect: (mission: RealWorldMission) => void;
}) {
  const missions = missionQueue(today).slice(0, 5);
  return (
    <section className="paper mission-list">
      <header>
        <span className="t-mono">MISSION QUEUE</span>
        <ClipboardList size={16} />
      </header>
      {missions.map(({ label, mission }) => (
        <button
          key={`${label}-${mission.id}`}
          className={selectedId === mission.id ? 'active' : ''}
          onClick={() => onSelect(mission)}
        >
          <span className="t-mono-low">{label}</span>
          <strong>{missionDisplayTitle(mission)}</strong>
          <small>{missionObjectiveProgress(mission).text} · {missionDeadlineLabel(mission)}</small>
        </button>
      ))}
      {!missions.length && <p className="side-empty">No mission queued.</p>}
    </section>
  );
}

function SceneLens({ mission, messenger }: { mission: RealWorldMission | null; messenger: MissionMessenger }) {
  const card = sourceCard(mission);
  const source = mission?.source_snapshot || {};
  const showSource = Boolean(card.headline || source.digest);
  const targetVocabulary = Array.isArray(mission?.target_vocabulary)
    ? mission?.target_vocabulary || []
    : Array.isArray(mission?.prompt_payload?.target_vocabulary)
      ? mission?.prompt_payload?.target_vocabulary || []
      : [];
  return (
    <section className="paper scene-lens">
      <header>
        <span className="t-mono">SCENE LENS</span>
        <MapPinned size={16} />
      </header>
      <div className="lens-anchor">
        <Clock3 size={15} />
        <strong>{messenger.scene_anchor}</strong>
      </div>
      <div className="cue-grid">
        {messenger.ambient_cues.map((cue, index) => (
          <span key={`${cue}-${index}`}>{cue}</span>
        ))}
      </div>
      <div className="rules">
        <span className="t-mono-low">REALISM RULES</span>
        {messenger.realism_rules.map((rule, index) => (
          <p key={`${rule}-${index}`}>{rule}</p>
        ))}
      </div>
      {targetVocabulary.length > 0 && (
        <div className="mission-vocabulary-focus">
          <span className="t-mono-low">VOCABULARY FOCUS</span>
          <div>
            {targetVocabulary.slice(0, 4).map((item: any) => (
              <span key={`${item.word_id}-${item.word}`}>
                <strong>{item.word}</strong>
                {item.translation && <em>{item.translation}</em>}
                {item.example_sentence && <small>{compactText(item.example_sentence, 78)}</small>}
              </span>
            ))}
          </div>
        </div>
      )}
      {showSource && (
        <div className="source-block">
          <div className="t-mono yellow">{source.mode === 'live_france_rss' ? 'SOURCE CARD' : 'CURATED SOURCE'}</div>
          <h3>{card.headline || 'France context'}</h3>
          {(card.summary || source.digest) && <p>{card.summary || source.digest}</p>}
          <div className="source-meta">
            <span>{card.source || source.items?.[0]?.source || 'Atelier'}</span>
            {card.url && <a href={card.url} target="_blank" rel="noreferrer">Open source</a>}
          </div>
        </div>
      )}
    </section>
  );
}

function Objectives({ mission, correction }: { mission: RealWorldMission | null; correction: Record<string, any> | null }) {
  const progress = correction?.objective_progress || [];
  const objectives = missionObjectives(mission);
  return (
    <section className="paper objectives">
      <header>
        <span className="t-mono">MISSION GOALS</span>
        <span className="t-mono-low">{objectives.length}</span>
      </header>
      {objectives.map((objective) => {
        const state = progress.find((item: any) => item.id === objective.id);
        return (
          <div key={objective.id} className={state?.met ? 'met' : ''}>
            <span className="status-ring" />
            <p>{objective.label}</p>
            {state?.note && <small>{state.note}</small>}
          </div>
        );
      })}
      {!objectives.length && <p className="side-empty">Create a mission to see targets.</p>}
    </section>
  );
}

function CorrectionStack({ correction }: { correction: Record<string, any> | null }) {
  const errata = correctionErrata(correction);
  const feedback = correction ? correctionFeedback(correction) : null;
  return (
    <section className="correction-stack">
      <div className="between">
        <span className="t-mono">LIVE REPAIR</span>
        <span className="t-mono-low">{errata.length}</span>
      </div>
      {!correction && (
        <div className="empty-slip">Send a message or review a dispatch to see targeted repairs.</div>
      )}
      {correction && feedback && (
        <article className="paper correction-summary">
          <h3>{feedback.label}</h3>
          <p>{feedback.scoreLabel}</p>
          {feedback.support && <p>{feedback.support}</p>}
          {correction.corrected_answer && <small>{correction.corrected_answer}</small>}
          <VocabularyCreditBadge correction={correction} />
        </article>
      )}
      {errata.slice(0, 5).map((item: any, index: number) => (
        <RedInkRepairSlip
          key={`${item.display_label}-${index}`}
          label={item.display_label || item.error_category || 'Correction'}
          slipNumber={`NO. ${String(index + 1).padStart(2, '0')}`}
          learnerText={erratumText(item, ['learner_text', 'original_text', 'wrong_text'], 'Missing target')}
          correctedText={erratumText(item, ['corrected_target', 'correction', 'target'], 'Use the target form')}
          why={item.why_wrong || item.reason}
          repair={item.repair_hint || item.hint}
          source={[item.source_label, item.review_mode].filter(Boolean).join(' · ')}
          action={item.concept_id && <Link className="notebook-link" href={`/grammar?concept=${item.concept_id}`}>Review rule</Link>}
        />
      ))}
    </section>
  );
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

function MissionStyles() {
  return (
    <style jsx global>{`
      .missions-page {
        --paper: #f1ece1;
        --paper-2: #e8e0cf;
        --paper-3: #d8cdb6;
        --ink: #14110d;
        --ink-2: #4a4538;
        --ink-3: #8a826f;
        --red: #d8321a;
        --blue: #1d3a8a;
        --yellow: #f3c318;
        --green: #1c7c54;
        --phone: #101010;
        --serif: "EB Garamond", Garamond, "Times New Roman", serif;
        --grotesk: "Inter", "Helvetica Neue", Arial, sans-serif;
        min-height: 100vh;
        background:
          linear-gradient(90deg, rgba(20,17,13,.045) 1px, transparent 1px),
          linear-gradient(0deg, rgba(20,17,13,.035) 1px, transparent 1px),
          var(--paper);
        background-size: 28px 28px;
        color: var(--ink);
        font-family: var(--grotesk);
      }
      .missions-page * { box-sizing: border-box; }
      .missions-page button, .missions-page select, .missions-page textarea { font: inherit; color: inherit; }
      .missions-page button { border: 0; background: transparent; cursor: pointer; }
      .mission-spread { box-sizing: border-box; width: min(1360px, 100%); margin: 0 auto; padding: 0 clamp(18px, 4vw, 48px); }
      .missions-masthead { border-bottom: 1px solid var(--ink); background: rgba(241,236,225,.92); backdrop-filter: blur(10px); position: sticky; top: 0; z-index: 20; }
      .masthead-inner { min-height: 58px; display: flex; align-items: center; justify-content: space-between; gap: 24px; }
      .brand { display: inline-flex; align-items: center; gap: 12px; color: var(--ink); text-decoration: none; font-size: 22px; font-weight: 900; letter-spacing: 0; }
      .missions-masthead nav { display: flex; gap: 20px; align-items: center; flex-wrap: wrap; }
      .missions-masthead nav a, .t-mono, .btn { font-size: 10px; letter-spacing: .13em; text-transform: uppercase; font-weight: 900; text-decoration: none; }
      .missions-masthead nav a { color: var(--ink-3); border-bottom: 2px solid transparent; padding-bottom: 3px; }
      .missions-masthead nav a.active, .missions-masthead nav a:hover { color: var(--ink); border-color: var(--ink); }
      .t-mono-low { font-size: 10px; letter-spacing: .06em; text-transform: uppercase; color: var(--ink-2); font-weight: 800; }
      .red { color: var(--red); }
      .yellow { color: #8a6800; }
      .between { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
      .page-grid { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 28px; padding-top: 34px; padding-bottom: 80px; align-items: start; }
      .mission-main { min-width: 0; display: grid; gap: 24px; }
      .mission-side { display: grid; gap: 20px; align-content: start; }
      .mission-title { display: flex; align-items: end; justify-content: space-between; gap: 24px; border-bottom: 4px solid var(--ink); padding-bottom: 20px; }
      .mission-title h1 { margin: 8px 0 0; font-family: var(--serif); font-size: clamp(36px, 5vw, 58px); line-height: .95; letter-spacing: 0; font-style: italic; font-weight: 700; }
      .mission-builder { display: flex; gap: 10px; align-items: center; }
      .atelier-return { color: var(--ink); text-decoration: none; }
      .mission-builder select { min-height: 46px; border: 1px solid var(--ink) !important; background: var(--paper); padding: 0 12px; font-weight: 800; box-shadow: 4px 4px 0 var(--ink) !important; }
      .mobile-mission-switcher { display: none; }
      .mobile-mission-sheet-layer { display: none; }
      .mobile-custom-mission-entry, .mobile-mission-finish, .mobile-voice-layer, .mobile-state-actions { display: none; }
      .paper { background: var(--paper-2); border: 2px solid var(--ink); position: relative; }
      .loading, .empty-state { min-height: 240px; display: grid; place-items: center; gap: 10px; font-size: 10px; letter-spacing: .14em; font-weight: 900; text-transform: uppercase; }
      .loading-line { display: inline-flex; align-items: center; justify-content: center; gap: 10px; }
      .mobile-loading-stack, .mobile-empty-copy, .mobile-empty-cta { display: none; }
      .btn { display: inline-flex; align-items: center; justify-content: center; gap: 9px; min-height: 42px; padding: 0 18px; border: 1px solid var(--ink); background: var(--paper); transition: .12s ease; white-space: nowrap; }
      .btn:hover:not(:disabled) { background: var(--ink); color: var(--paper); }
      .btn:disabled { opacity: .45; cursor: not-allowed; }
      .btn.red { background: var(--red); border-color: var(--red); color: var(--paper); }
      .btn.solid { background: var(--ink); color: var(--paper); }
      .btn.solid.recording { background: var(--red); border-color: var(--red); }
      .btn.ghost { border-color: transparent; padding-inline: 10px; background: transparent; }
      .btn.lg { min-height: 56px; padding-inline: 28px; }
      .thread-context-banner {
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(260px, 360px);
        gap: 18px;
        align-items: center;
        border-left: 8px solid var(--red);
        background: var(--paper);
        padding: 18px 20px;
        box-shadow: 6px 6px 0 var(--ink);
      }
      .thread-context-copy h2 {
        margin: 7px 0 0;
        font-family: var(--serif);
        font-size: clamp(27px, 3vw, 38px);
        font-style: italic;
        font-weight: 700;
        line-height: 1;
        letter-spacing: 0;
      }
      .thread-context-copy p {
        max-width: 720px;
        margin: 9px 0 0;
        color: var(--ink-2);
        font-weight: 800;
        line-height: 1.4;
      }
      .thread-context-side {
        display: grid;
        gap: 10px;
        justify-items: end;
      }
      .thread-context-status {
        width: fit-content;
        border: 1px solid var(--ink);
        background: var(--yellow);
        padding: 5px 8px;
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .09em;
        line-height: 1;
        text-transform: uppercase;
      }
      .thread-context-chips {
        display: flex;
        justify-content: flex-end;
        flex-wrap: wrap;
        gap: 7px;
      }
      .thread-chip {
        display: grid;
        min-width: 110px;
        border: 1px solid var(--ink);
        background: var(--paper-2);
        padding: 8px 10px;
        box-shadow: 3px 3px 0 var(--ink);
      }
      .thread-chip strong {
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .08em;
        line-height: 1;
        text-transform: uppercase;
      }
      .thread-chip em {
        margin-top: 5px;
        font-size: 13px;
        font-style: normal;
        font-weight: 900;
        line-height: 1.1;
      }
      .thread-chip.grammar { background: var(--blue); color: var(--paper); }
      .thread-chip.vocabulary { background: var(--yellow); }
      .thread-chip.errata { background: var(--red); color: var(--paper); }
      .thread-chip.session { background: var(--paper-2); }
      .custom-composer { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 22px; padding: 22px; background: var(--paper-2); }
      .composer-copy { border-right: 2px solid var(--ink); padding-right: 22px; }
      .composer-topline span { display: none; }
      .composer-copy h2 { margin: 8px 0 0; font-size: 24px; line-height: 1; letter-spacing: 0; }
      .composer-copy p { margin: 10px 0 0; color: var(--ink-2); line-height: 1.4; }
      .composer-toggle { display: none; margin-top: 14px; }
      .composer-form { display: grid; gap: 12px; }
      .composer-form textarea { width: 100%; min-height: 96px; border: 1px solid var(--ink) !important; background: var(--paper); padding: 14px 16px; resize: vertical; box-shadow: 4px 4px 0 var(--ink) !important; line-height: 1.35; }
      .composer-row { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, .8fr) 160px; gap: 10px; }
      .composer-row input, .composer-row select { min-height: 42px; border: 1px solid var(--ink) !important; background: var(--paper); padding: 0 12px; box-shadow: 3px 3px 0 var(--ink) !important; font-weight: 800; min-width: 0; }
      .mission-passport { padding: 28px 32px; background: var(--paper); }
      .passport-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(220px, 320px); gap: 28px; align-items: start; }
      .mission-kicker { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }
      .mission-kicker span { border: 1px solid var(--ink); padding: 5px 8px; font-size: 10px; letter-spacing: .12em; text-transform: uppercase; font-weight: 900; background: var(--paper-2); }
      .mission-passport h2 { margin: 0; font-family: var(--serif); font-size: clamp(30px, 4vw, 48px); line-height: 1; letter-spacing: 0; font-style: italic; font-weight: 700; }
      .mission-passport p { max-width: 780px; color: var(--ink-2); line-height: 1.5; font-size: 17px; }
      .signal-card { min-height: 190px; background: var(--yellow); border: 2px solid var(--ink); padding: 18px; display: grid; align-content: space-between; box-shadow: 6px 6px 0 var(--ink); }
      .signal-card strong { display: block; font-size: 22px; line-height: 1.05; letter-spacing: 0; margin-top: 12px; }
      .signal-card small { color: var(--ink-2); line-height: 1.35; font-weight: 700; }
      .mission-loop { margin-top: 20px; border-top: 2px solid var(--ink); padding-top: 14px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
      .mission-loop span { background: var(--ink); color: var(--paper); padding: 7px 10px; font-size: 10px; letter-spacing: .1em; text-transform: uppercase; font-weight: 900; }
      .format-brief { display: grid; grid-template-columns: 44px minmax(0, 1fr); gap: 14px; align-items: start; padding: 16px 18px; background: var(--paper); }
      .format-icon { width: 44px; height: 44px; border: 2px solid var(--ink); background: var(--yellow); display: grid; place-items: center; box-shadow: 4px 4px 0 var(--ink); }
      .format-copy h3 { margin: 4px 0 6px; font-size: 22px; line-height: 1.02; }
      .format-copy p { margin: 0; color: var(--ink-2); line-height: 1.35; }
      .format-toggle { margin-top: 10px; border: 1px solid var(--ink); background: var(--paper-2); padding: 7px 10px; font-family: var(--mono); font-size: 10px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
      .format-audio { display: block; width: min(100%, 420px); margin-top: 12px; }
      .format-brief blockquote { margin: 12px 0 0; border-left: 4px solid var(--blue); padding: 9px 12px; background: var(--paper-2); font-family: var(--serif); font-style: italic; font-size: 20px; line-height: 1.32; }
      .format-chips, .format-fields { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; }
      .format-chips span, .format-fields span { border: 1px solid var(--ink); background: var(--paper-2); padding: 6px 8px; font-family: var(--mono); font-size: 10px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
      .workspace-head { display: flex; justify-content: space-between; gap: 20px; align-items: start; border-bottom: 2px solid var(--ink); padding-bottom: 14px; }
      .workspace-head h3 { margin: 6px 0 0; font-size: clamp(23px, 3vw, 32px); line-height: 1; letter-spacing: 0; font-weight: 900; }
      .messenger-workspace, .dispatch-draft { padding: 24px 28px; background: var(--paper); display: grid; gap: 18px; }
      .mobile-thread-summary { display: none; }
      .messenger-grid { display: grid; grid-template-columns: minmax(300px, 470px) minmax(240px, 1fr); gap: 24px; align-items: stretch; }
      .phone-shell { background: var(--phone); border: 3px solid var(--ink); border-radius: 30px; padding: 12px; box-shadow: 10px 10px 0 var(--ink); min-height: 650px; }
      .phone-screen { min-height: 626px; height: 100%; border-radius: 22px; background: #f7f3ea; overflow: hidden; display: grid; grid-template-rows: auto auto 1fr auto; border: 1px solid rgba(255,255,255,.2); }
      .phone-status { min-height: 34px; background: #efe8d8; display: flex; align-items: center; justify-content: space-between; padding: 0 18px; font-size: 11px; font-weight: 900; color: var(--ink-2); }
      .thread-contact { min-height: 78px; display: flex; gap: 12px; align-items: center; border-top: 1px solid rgba(20,17,13,.15); border-bottom: 1px solid rgba(20,17,13,.15); padding: 13px 16px; background: #fbf8f0; }
      .avatar { width: 46px; height: 46px; display: grid; place-items: center; border: 2px solid var(--ink); border-radius: 50%; background: var(--blue); color: white; font-weight: 900; font-size: 13px; }
      .thread-contact strong { display: block; font-size: 17px; line-height: 1.1; }
      .thread-contact span { display: block; margin-top: 4px; color: var(--ink-3); font-size: 12px; font-weight: 800; }
      .message-list { padding: 18px 14px; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; max-height: 430px; }
      .message-row { display: flex; }
      .message-row.user { justify-content: flex-end; }
      .message-bubble-real { max-width: min(82%, 320px); padding: 11px 13px 9px; border: 1px solid rgba(20,17,13,.18); border-radius: 18px; background: white; color: var(--ink); box-shadow: 0 1px 0 rgba(20,17,13,.08); }
      .message-row.user .message-bubble-real { background: var(--blue); color: white; border-color: var(--blue); border-bottom-right-radius: 5px; }
      .message-row.assistant .message-bubble-real { border-bottom-left-radius: 5px; }
      .message-bubble-real p { margin: 0; line-height: 1.35; overflow-wrap: anywhere; }
      .message-bubble-real span { display: block; margin-top: 6px; font-size: 10px; opacity: .72; font-weight: 800; text-transform: uppercase; letter-spacing: .06em; }
      .turn-notes { margin-top: 8px; }
      .turn-notes > summary { list-style: none; cursor: pointer; display: inline-flex; align-items: center; gap: 7px; padding: 3px 9px 3px 7px; border-radius: 999px; background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.34); font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: .05em; color: rgba(255,255,255,.9); user-select: none; transition: background .15s ease; }
      .turn-notes > summary::-webkit-details-marker { display: none; }
      .turn-notes > summary:hover { background: rgba(255,255,255,.22); }
      .turn-notes .turn-notes-dot { width: 7px; height: 7px; border-radius: 50%; background: rgba(255,255,255,.6); flex: none; }
      .turn-notes.needs-work .turn-notes-dot { background: var(--yellow); }
      .turn-notes.accepted .turn-notes-dot { background: #4fd08a; }
      .turn-notes .turn-notes-hint { opacity: .68; font-weight: 700; letter-spacing: .02em; text-transform: none; }
      .turn-notes[open] > summary { background: rgba(255,255,255,.24); margin-bottom: 8px; }
      .turn-notes-body { display: grid; gap: 8px; }
      .turn-verdict { display: grid; gap: 2px; width: fit-content; max-width: 100%; margin-top: 0; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.38); padding: 4px 7px; font-size: 10px; letter-spacing: 0; text-transform: none; }
      .turn-verdict strong { font-size: 10px; line-height: 1.1; text-transform: uppercase; letter-spacing: .04em; }
      .turn-verdict span,
      .turn-verdict em { overflow-wrap: anywhere; font-style: normal; line-height: 1.2; }
      .turn-verdict.accepted { background: rgba(28,124,84,.9); border-color: rgba(255,255,255,.5); }
      .turn-verdict.needs-work { background: rgba(243,195,24,.95); border-color: rgba(20,17,13,.38); color: var(--ink); }
      .turn-repair-card {
        display: grid;
        gap: 8px;
        margin-top: 9px;
        border: 1px solid rgba(255,255,255,.44);
        background: rgba(255,255,255,.12);
        padding: 8px;
        color: inherit;
      }
      .turn-repair-card .t-mono-low { color: rgba(255,255,255,.72); }
      .repair-markup { display: grid; gap: 4px; }
      .repair-markup p { margin: 0; overflow-wrap: anywhere; }
      .repair-markup .wrong {
        color: #ffb3a8;
        text-decoration: line-through;
        text-decoration-thickness: 2px;
      }
      .repair-markup .right {
        display: inline;
        width: fit-content;
        background: linear-gradient(transparent 58%, rgba(243,195,24,.52) 58%);
        color: white;
        font-weight: 900;
      }
      .repair-markup small {
        display: grid;
        gap: 3px;
        margin-top: 2px;
        color: rgba(255,255,255,.78);
        font-size: 11px;
        line-height: 1.3;
      }
      .analysis-interstitial {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr);
        gap: 12px;
        align-items: start;
        border: 2px solid var(--ink);
        background: var(--yellow);
        padding: 12px;
        color: var(--ink);
        box-shadow: 4px 4px 0 var(--ink);
      }
      .analysis-interstitial strong {
        display: block;
        margin-top: 2px;
        font-size: 15px;
        line-height: 1.15;
      }
      .analysis-interstitial p {
        margin: 4px 0 0;
        color: var(--ink-2);
        font-size: 12px;
        font-weight: 800;
        line-height: 1.35;
      }
      .analysis-targets {
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
        margin-top: 8px;
      }
      .analysis-targets em {
        border: 1px solid var(--ink);
        background: rgba(255,255,255,.55);
        padding: 4px 6px;
        font-size: 10px;
        font-style: normal;
        font-weight: 900;
        line-height: 1.1;
      }
      .analysis-targets .vocabulary { background: rgba(29,58,138,.12); }
      .analysis-targets .repair { background: rgba(216,50,26,.12); color: var(--red); }
      .branch-chip { display: inline-flex; margin-top: 7px; border: 1px solid rgba(20,17,13,.2); background: rgba(243,195,24,.35); padding: 4px 7px; font-size: 10px; font-weight: 900; line-height: 1.15; text-transform: uppercase; letter-spacing: .05em; }
      .branch-chip.understood { background: rgba(28,124,84,.16); color: var(--green); }
      .branch-chip.tone_mismatch, .branch-chip.needs_detail, .branch-chip.missing_next_step { background: rgba(216,50,26,.12); color: var(--red); }
      .retry-send-bar { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 9px 12px; background: rgba(216,50,26,.12); border-top: 1px solid rgba(216,50,26,.25); color: var(--red); font-size: 12px; font-weight: 900; }
      .retry-send-bar strong { display: block; line-height: 1.2; }
      .failed-snippet { display: block; max-width: 100%; margin-top: 3px; color: var(--ink-2); font-size: 11px; line-height: 1.25; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .retry-actions { display: flex; gap: 7px; flex-shrink: 0; }
      .retry-send-bar button { border: 1px solid var(--red); background: white; color: var(--red); padding: 5px 9px; font-size: 10px; letter-spacing: .08em; text-transform: uppercase; font-weight: 900; }
      .retry-send-bar button:disabled { opacity: .5; cursor: not-allowed; }
      .phone-composer { display: grid; gap: 8px; padding: 12px; background: #fbf8f0; border-top: 1px solid rgba(20,17,13,.14); }
      .composer-input-row { display: grid; grid-template-columns: 1fr 42px; gap: 8px; align-items: end; }
      .composer-mic { display: none; }
      .mobile-composer-status,
      .mobile-composer-tools { display: none; }
      .phone-composer textarea { width: 100%; min-height: 54px; max-height: 120px; border: 1px solid rgba(20,17,13,.32) !important; border-radius: 18px !important; background: white; padding: 12px 14px; resize: none; box-shadow: none !important; outline: none; font-size: 15px; line-height: 1.3; }
      .send-dot { width: 42px; height: 42px; border-radius: 50%; background: var(--red) !important; color: white !important; display: grid; place-items: center; }
      .send-dot:disabled { opacity: .4; cursor: not-allowed; }
      .thread-tools { display: grid; align-content: start; gap: 16px; }
      .thread-tools > p { margin: 0; color: var(--ink-2); line-height: 1.45; font-size: 16px; }
      .scene-strip { display: flex; gap: 10px; align-items: flex-start; border: 2px solid var(--ink); background: var(--paper-2); padding: 14px; font-weight: 900; line-height: 1.25; }
      .quick-replies { display: grid; gap: 9px; }
      .quick-replies button { text-align: left; border: 1px solid var(--ink); background: var(--paper); padding: 10px 12px; font-weight: 800; line-height: 1.25; box-shadow: 3px 3px 0 var(--ink); }
      .quick-replies button:hover:not(:disabled) { background: var(--yellow); }
      .workspace-note { margin: -4px 0 0; color: var(--ink-2); line-height: 1.45; max-width: 760px; }
      .word-meter { font-size: 10px; letter-spacing: .1em; text-transform: uppercase; color: var(--ink-2); font-weight: 800; border: 1px solid var(--ink); padding: 6px 8px; background: var(--paper-2); }
      .word-meter.good { background: rgba(28,124,84,.15); color: var(--green); }
      .dispatch-draft textarea { width: 100%; min-height: 190px; border: 1px solid var(--ink) !important; background: var(--paper); padding: 16px 18px; outline: none; resize: vertical; box-shadow: 5px 5px 0 var(--ink) !important; font-family: var(--serif); font-size: 24px; font-style: italic; line-height: 1.35; }
      .draft-footer { display: flex; align-items: center; justify-content: space-between; gap: 18px; flex-wrap: wrap; }
      .draft-footer div { display: grid; gap: 4px; max-width: 560px; }
      .draft-footer strong { line-height: 1.25; }
      .debrief-panel { padding: 24px 28px; background: var(--paper); display: grid; gap: 18px; }
      .mission-bridge-panel {
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(180px, 260px) minmax(240px, 320px);
        gap: 16px;
        align-items: center;
        padding: 18px;
        background: var(--paper);
      }
      .mission-bridge-panel h3 {
        margin: 6px 0 0;
        font-size: 24px;
        line-height: 1;
        letter-spacing: 0;
      }
      .mission-bridge-panel p {
        margin: 7px 0 0;
        color: var(--ink-2);
        font-size: 13px;
        font-weight: 800;
        line-height: 1.35;
      }
      .bridge-focus {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .bridge-focus span {
        border: 1px solid var(--ink);
        background: var(--yellow);
        padding: 5px 7px;
        font-size: 11px;
        font-weight: 900;
        line-height: 1.15;
      }
      .bridge-actions {
        display: grid;
        gap: 7px;
      }
      .bridge-actions a {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        min-height: 38px;
        border: 1px solid var(--ink);
        background: var(--paper-2);
        padding: 8px 10px;
        color: var(--ink);
        font-size: 11px;
        font-weight: 900;
        line-height: 1.15;
        text-decoration: none;
      }
      .bridge-actions a:hover { background: var(--ink); color: var(--paper); }
      .readiness-score { width: 88px; height: 88px; border: 2px solid var(--ink); border-radius: 50%; background: var(--yellow); display: grid; place-items: center; align-content: center; box-shadow: 5px 5px 0 var(--ink); }
      .readiness-score span { font-size: 30px; font-weight: 900; line-height: 1; }
      .readiness-score small { font-size: 10px; text-transform: uppercase; letter-spacing: .08em; font-weight: 900; }
      .readiness-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }
      .readiness-grid div { border: 1px solid var(--ink); background: var(--paper-2); min-height: 78px; padding: 10px; display: grid; align-content: space-between; }
      .readiness-grid span { font-size: 10px; text-transform: uppercase; letter-spacing: .08em; font-weight: 900; color: var(--ink-2); }
      .readiness-grid strong { font-size: 26px; line-height: 1; }
      .debrief-next { margin: 0; border-left: 4px solid var(--blue); padding: 10px 12px; background: var(--paper-2); color: var(--ink-2); font-weight: 800; line-height: 1.35; }
      .srs-bank { display: grid; gap: 10px; }
      .srs-bank article { border: 1px solid var(--ink); background: var(--paper-2); padding: 12px; display: grid; gap: 5px; }
      .srs-bank article strong { font-family: var(--serif); font-style: italic; font-size: 19px; line-height: 1.25; }
      .srs-bank article span, .srs-bank p { color: var(--ink-2); font-size: 12px; line-height: 1.35; margin: 0; }
      .next-seed { border: 2px solid var(--ink); background: var(--yellow); padding: 12px 14px; }
      .next-seed p { margin: 6px 0 0; font-weight: 900; line-height: 1.25; }
      .action-row, .complete-row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
      .complete-row { justify-content: flex-end; }
      .sr-file { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
      .voice-affordance { display: none; }
      .voice-warning { margin: 0; border-left: 4px solid var(--red); padding: 8px 12px; background: var(--paper-2); color: var(--ink-2); line-height: 1.35; }
      .field-validation { display: block; margin-top: 7px; color: var(--red); font-size: 12px; font-weight: 800; line-height: 1.3; }
      .mission-list header, .objectives header, .scene-lens header { min-height: 44px; padding: 0 14px; border-bottom: 1px solid var(--ink); display: flex; align-items: center; justify-content: space-between; }
      .mission-list button { width: 100%; text-align: left; padding: 14px; border-top: 1px solid var(--paper-3); display: grid; gap: 5px; }
      .mission-list button.active { background: var(--ink); color: var(--paper); }
      .mission-list button.active small, .mission-list button.active .t-mono-low { color: rgba(241,236,225,.75); }
      .mission-list strong { font-size: 15px; line-height: 1.18; }
      .mission-list small, .side-empty { color: var(--ink-2); }
      .side-empty { padding: 14px; margin: 0; }
      .scene-lens { background: var(--paper); }
      .lens-anchor { display: flex; gap: 10px; padding: 14px; border-bottom: 1px solid var(--paper-3); align-items: flex-start; }
      .lens-anchor strong { line-height: 1.25; }
      .cue-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; padding: 14px; border-bottom: 1px solid var(--paper-3); }
      .cue-grid span { min-height: 56px; display: flex; align-items: center; border: 1px solid var(--ink); background: var(--paper-2); padding: 9px; font-size: 12px; font-weight: 900; line-height: 1.2; }
      .rules { padding: 14px; display: grid; gap: 9px; }
      .rules p { margin: 0; border-left: 4px solid var(--blue); padding-left: 10px; color: var(--ink-2); line-height: 1.35; font-size: 13px; }
      .mission-vocabulary-focus {
        display: grid;
        gap: 9px;
        margin: 0 14px 14px;
        border-top: 1px solid var(--ink);
        border-bottom: 1px solid var(--ink);
        padding: 11px 0;
      }
      .mission-vocabulary-focus > div {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 7px;
      }
      .mission-vocabulary-focus > div > span {
        min-width: 0;
      }
      .mission-vocabulary-focus > div > span {
        display: grid;
        gap: 2px;
        border: 1px solid var(--ink);
        background: var(--paper-2);
        padding: 7px 8px;
      }
      .mission-vocabulary-focus strong,
      .mission-vocabulary-focus em,
      .mission-vocabulary-focus small {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .mission-vocabulary-focus strong {
        font-size: 13px;
        line-height: 1.1;
      }
      .mission-vocabulary-focus em {
        color: var(--ink-3);
        font-size: 11px;
        font-style: normal;
        font-weight: 800;
      }
      .mission-vocabulary-focus small {
        color: var(--ink-2);
        font-size: 10px;
        font-weight: 700;
        line-height: 1.2;
      }
      .source-block { margin: 0 14px 14px; border-left: 4px solid var(--yellow); background: var(--paper-2); padding: 14px; }
      .source-block h3 { margin: 8px 0 0; font-size: 19px; line-height: 1.1; letter-spacing: 0; }
      .source-block p { margin: 8px 0 0; color: var(--ink-2); line-height: 1.45; }
      .source-meta { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 12px; border-top: 1px solid rgba(20,17,13,.22); padding-top: 10px; font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
      .source-meta a { color: var(--blue); text-decoration: none; }
      .objectives > div { display: grid; grid-template-columns: 18px 1fr; gap: 8px 10px; padding: 12px 14px; border-top: 1px solid var(--paper-3); }
      .objectives p { margin: 0; line-height: 1.35; font-size: 13px; }
      .objectives small { grid-column: 2; color: var(--ink-2); }
      .status-ring { width: 10px; height: 10px; border: 2px solid var(--ink-3); border-radius: 50%; margin-top: 3px; display: inline-block; }
      .objectives .met .status-ring { background: var(--blue); border-color: var(--blue); }
      .correction-stack { display: grid; gap: 14px; }
      .empty-slip { border: 1px dashed var(--ink-3); padding: 16px; color: var(--ink-2); background: rgba(241,236,225,.72); }
      .correction-summary { padding: 14px; background: var(--paper); }
      .correction-summary h3 { margin: 0 0 8px; text-transform: uppercase; font-size: 18px; }
      .correction-summary p { margin: 5px 0 0; color: var(--ink-2); }
      .correction-summary small { display: block; margin-top: 8px; color: var(--ink-2); line-height: 1.35; }
      .errata-slip { position: relative; background: var(--paper); border: 2px solid var(--ink); padding: 38px 18px 18px; box-shadow: 5px 5px 0 var(--ink); transform: rotate(-1deg); }
      .slip-label { position: absolute; top: -12px; left: 16px; background: var(--red); color: var(--paper); padding: 5px 12px; font-size: 10px; letter-spacing: .1em; text-transform: uppercase; font-weight: 900; max-width: calc(100% - 80px); overflow-wrap: anywhere; }
      .slip-num { position: absolute; right: 0; top: 0; background: var(--ink); color: var(--paper); padding: 4px 8px; font-size: 10px; }
      .errata-slip .wrong, .errata-slip .right { font-family: var(--serif); font-style: italic; font-size: 19px; line-height: 1.35; overflow-wrap: anywhere; }
      .errata-slip .wrong { color: var(--red); text-decoration: line-through; text-decoration-thickness: 2px; }
      .errata-slip .right { background: linear-gradient(transparent 62%, rgba(243,195,24,.45) 62%); display: inline; }
      .why { margin-top: 14px; border-left: 4px solid var(--blue); padding-left: 12px; color: var(--ink-2); font-size: 13px; line-height: 1.45; }
      .notebook-link { color: var(--blue); font-size: 11px; font-weight: 800; text-decoration: none; text-transform: uppercase; letter-spacing: .06em; }
      .spin { animation: spin .7s linear infinite; }
      .crop-mark { position: absolute; width: 12px; height: 12px; pointer-events: none; }
      .crop-mark.tl { top: -1px; left: -1px; border-top: 1px solid var(--ink); border-left: 1px solid var(--ink); }
      .crop-mark.tr { top: -1px; right: -1px; border-top: 1px solid var(--ink); border-right: 1px solid var(--ink); }
      .crop-mark.bl { bottom: -1px; left: -1px; border-bottom: 1px solid var(--ink); border-left: 1px solid var(--ink); }
      .crop-mark.br { bottom: -1px; right: -1px; border-bottom: 1px solid var(--ink); border-right: 1px solid var(--ink); }
      @keyframes spin { to { transform: rotate(360deg); } }
      @keyframes mission-sheet-up {
        from { transform: translateY(100%); }
        to { transform: translateY(0); }
      }
      @media (max-width: 1120px) {
        .page-grid { grid-template-columns: 1fr; }
        .mission-side { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
      @media (max-width: 860px) {
        .mission-title, .workspace-head, .masthead-inner, .passport-grid, .messenger-grid, .thread-context-banner, .custom-composer, .format-brief { grid-template-columns: 1fr; align-items: flex-start; flex-direction: column; }
        .thread-context-side { justify-items: start; }
        .thread-context-chips { justify-content: flex-start; }
        .composer-copy { border-right: 0; border-bottom: 2px solid var(--ink); padding-right: 0; padding-bottom: 16px; }
        .composer-row, .readiness-grid { grid-template-columns: 1fr; }
        .mission-bridge-panel { grid-template-columns: 1fr; align-items: stretch; }
        .mission-builder { width: 100%; flex-direction: column; align-items: stretch; }
        .mission-builder .btn, .mission-builder select { width: 100%; }
        .mission-side { grid-template-columns: 1fr; }
        .phone-shell { min-height: 560px; box-shadow: 6px 6px 0 var(--ink); }
        .phone-screen { min-height: 536px; }
        .message-list { max-height: 340px; }
        .cue-grid { grid-template-columns: 1fr; }
      }
      @media (max-width: 760px) {
        .missions-page { overflow-x: hidden; }
        .missions-mobile-actions {
          display: inline-flex;
          align-items: center;
          gap: 8px;
        }
        .mobile-masthead-action {
          display: grid;
          width: 44px;
          height: 44px;
          place-items: center;
          border: 1px solid var(--ink) !important;
          background: transparent !important;
          color: var(--ink);
          text-decoration: none;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .08em;
          text-transform: uppercase;
        }
        .mobile-masthead-action.custom-draft {
          background: var(--red) !important;
          border-color: var(--red) !important;
          color: var(--paper);
        }
        a.mobile-masthead-action {
          width: auto;
          min-width: 64px;
          padding: 0 10px;
        }
        .page-grid {
          padding-top: 0;
          padding-bottom: calc(118px + env(safe-area-inset-bottom));
          gap: 0;
        }
        .mission-spread { padding-inline: 14px; }
        .paper { border-width: 1px; }
        .missions-masthead nav { gap: 12px; }
        .mission-loading {
          min-height: 360px;
          place-items: stretch;
          align-content: start;
          padding: 18px;
        }
        .mission-loading .loading-line {
          justify-content: flex-start;
          border-bottom: 2px solid var(--ink);
          padding-bottom: 14px;
          width: 100%;
        }
        .mobile-loading-stack {
          display: grid;
          gap: 12px;
          width: 100%;
          margin-top: 16px;
        }
        .mobile-loading-stack span {
          min-height: 58px;
          border: 1px solid rgba(20,17,13,.22);
          background: linear-gradient(90deg, rgba(241,236,225,.6), rgba(255,255,255,.7), rgba(241,236,225,.6));
        }
        .mobile-loading-stack span:first-child { min-height: 132px; }
        .mission-empty {
          min-height: 300px;
          padding: 22px 18px;
          place-items: start;
          align-content: center;
          text-align: left;
          font-size: 13px;
          line-height: 1.3;
        }
        .mission-empty > span {
          letter-spacing: .12em;
          text-transform: uppercase;
        }
        .mobile-empty-copy {
          display: block;
          margin: 4px 0 8px;
          color: var(--ink-2);
          font-size: 15px;
          font-weight: 700;
          letter-spacing: 0;
          line-height: 1.4;
          text-transform: none;
        }
        .mobile-empty-cta {
          display: inline-flex;
          width: 100%;
        }
        .mission-main {
          display: flex;
          flex-direction: column;
        }
        .mission-side {
          display: none;
        }
        .mission-title { order: 0; }
        .mobile-mission-switcher { order: 1; }
        .thread-context-banner { order: 4; }
        .messenger-workspace { order: 2; }
        .mission-bridge-panel { order: 3; }
        .mobile-mission-finish { order: 4; }
        .mobile-custom-mission-entry,
        .mission-passport,
        .custom-composer,
        .dispatch-draft,
        .debrief-panel,
        .complete-row {
          display: none;
        }
        .mission-title {
          display: none;
        }
        .thread-context-banner {
          margin: 12px 0 0;
          border-left-width: 5px;
          padding: 13px 14px;
          box-shadow: none;
        }
        .thread-context-copy h2 {
          font-size: 24px;
        }
        .thread-context-copy p {
          display: none;
        }
        .thread-context-status {
          letter-spacing: 0;
          text-transform: none;
        }
        .thread-chip {
          min-width: 0;
          box-shadow: none;
        }
        .mobile-mission-switcher {
          display: grid;
          grid-template-columns: auto minmax(0, 1fr) auto;
          gap: 9px;
          align-items: center;
          min-height: 48px;
          margin: 0 -14px;
          padding: 8px 14px;
          border-bottom: 1px solid var(--ink);
          background: var(--paper-2);
          text-align: left;
        }
        .mobile-meta {
          color: var(--ink-2);
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0;
          line-height: 1.25;
          text-transform: none;
        }
        .mobile-custom-mission-entry {
          order: 3;
          display: none;
          min-height: 48px;
          align-items: center;
          justify-content: center;
          gap: 8px;
          border: 1px solid var(--ink);
          background: #f8f3e8;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: 0;
          text-transform: none;
        }
        .mobile-mission-finish {
          display: grid;
          gap: 14px;
          border-width: 1px;
          padding: 15px;
          box-shadow: none;
          background: var(--paper);
        }
        .mobile-mission-finish.completed {
          border-left: 5px solid var(--green);
        }
        .mobile-finish-copy {
          display: grid;
          gap: 6px;
        }
        .mobile-finish-copy strong {
          font-family: var(--serif);
          font-size: 25px;
          font-style: italic;
          font-weight: 700;
          line-height: 1;
        }
        .mobile-finish-copy p {
          margin: 0;
          color: var(--ink-2);
          font-size: 14px;
          font-weight: 700;
          line-height: 1.35;
        }
        .mobile-finish-recap {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 8px;
        }
        .mobile-finish-recap.pending {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .mobile-finish-recap span {
          min-width: 0;
          border: 1px solid var(--ink);
          background: var(--paper-2);
          padding: 10px 8px;
        }
        .mobile-finish-recap strong {
          display: block;
          font-family: var(--serif);
          font-size: 25px;
          font-style: italic;
          line-height: 1;
        }
        .mobile-finish-recap em {
          display: block;
          overflow-wrap: anywhere;
          color: var(--ink-2);
          font-size: 11px;
          font-style: normal;
          font-weight: 800;
          line-height: 1.15;
          text-transform: none;
        }
        .mobile-finish-actions {
          display: grid;
        }
        .mobile-finish-actions .btn {
          width: 100%;
          min-height: 52px;
          letter-spacing: 0;
          text-transform: none;
          white-space: normal;
        }
        .mobile-mission-switcher[aria-expanded="true"] svg {
          transform: rotate(90deg);
        }
        .mobile-mission-switcher .switcher-dot {
          width: 10px;
          height: 10px;
          border: 1px solid var(--ink);
          border-radius: 50%;
          background: var(--red);
          box-shadow: inset 0 0 0 2px var(--paper-2);
        }
        .mobile-mission-switcher strong {
          display: block;
          overflow: hidden;
          margin-top: 2px;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-family: var(--serif);
          font-size: 19px;
          font-style: italic;
          line-height: 1;
        }
        .mobile-mission-switcher p {
          display: none;
        }
        .mobile-mission-sheet-layer {
          position: fixed;
          inset: 0;
          z-index: 130;
          display: block;
        }
        .mobile-sheet-backdrop {
          position: absolute;
          inset: 0;
          width: 100%;
          background: rgba(20,17,13,.4);
        }
        .mobile-mission-sheet {
          position: absolute;
          left: 0;
          right: 0;
          bottom: 0;
          max-height: min(82svh, 680px);
          overflow-y: auto;
          border-top: 1px solid var(--ink);
          background: var(--paper);
          padding: 10px 16px calc(18px + env(safe-area-inset-bottom));
          box-shadow: 0 -16px 40px rgba(20,17,13,.2);
          animation: mission-sheet-up 280ms ease-out both;
        }
        .custom-mission-sheet {
          display: grid;
          grid-template-rows: auto auto minmax(0, 1fr) auto;
          max-height: min(90svh, 740px);
          padding-bottom: 0;
        }
        .sheet-handle {
          width: 36px;
          height: 4px;
          margin: 0 auto 14px;
          border-radius: 2px;
          background: var(--ink-3);
          opacity: 1;
        }
        .mobile-mission-sheet header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 18px;
          padding-bottom: 12px;
          border-bottom: 1px solid var(--ink);
        }
        .mobile-mission-sheet h2 {
          margin: 4px 0 0;
          font-family: var(--serif);
          font-size: 30px;
          font-style: italic;
          line-height: 1;
        }
        .sheet-close {
          min-height: 34px;
          border: 1px solid var(--ink) !important;
          padding: 0 10px;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: 0;
          text-transform: none;
        }
        .sheet-count {
          margin: 10px 0 12px;
          color: var(--ink-2);
          font-size: 12px;
          font-weight: 700;
          text-transform: none;
          letter-spacing: 0;
        }
        .mission-sheet-group {
          display: grid;
          gap: 8px;
          margin-top: 14px;
        }
        .mission-sheet-group > p {
          margin: 0;
          border: 1px dashed var(--ink-3);
          padding: 12px;
          color: var(--ink-2);
          font-size: 13px;
          line-height: 1.35;
        }
        .mission-sheet-group button {
          display: grid;
          grid-template-columns: auto minmax(0, 1fr) auto;
          gap: 9px 10px;
          align-items: start;
          width: 100%;
          min-height: 60px;
          border: 1px solid var(--ink);
          background: #f8f3e8;
          padding: 11px 12px;
          text-align: left;
        }
        .mission-sheet-group button.active {
          background: var(--ink);
          color: var(--paper);
        }
        .mission-sheet-group button.active small,
        .mission-sheet-group button.active em {
          color: rgba(241,236,225,.74);
        }
        .mission-row-dot {
          width: 12px;
          height: 12px;
          margin-top: 3px;
          border: 1px solid currentColor;
          border-radius: 50%;
          background: var(--red);
        }
        .mission-sheet-group strong {
          display: block;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-family: var(--serif);
          font-size: 21px;
          font-style: italic;
          line-height: 1;
        }
        .mission-sheet-group small {
          display: block;
          margin-top: 4px;
          color: var(--ink-2);
          font-size: 11px;
          font-weight: 700;
          line-height: 1.2;
          text-transform: none;
          letter-spacing: 0;
        }
        .mission-sheet-group em {
          grid-column: 2 / 4;
          color: var(--ink-2);
          font-size: 12px;
          font-style: normal;
          font-weight: 800;
          line-height: 1.25;
        }
        .mission-row-chevron {
          grid-column: 3;
          grid-row: 1;
          margin-top: 4px;
          color: var(--ink-3);
        }
        .mobile-sheet-create {
          width: 100%;
          margin-top: 16px;
          min-height: 52px;
          letter-spacing: 0;
          text-transform: none;
        }
        .custom-step-dots {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 5px;
          margin: 14px 0;
        }
        .custom-step-dots span {
          height: 3px;
          background: var(--paper-3);
        }
        .custom-step-dots span.active {
          background: var(--ink);
        }
        .custom-step-panel {
          display: grid;
          gap: 12px;
          min-height: 0;
          overflow-y: auto;
          padding-bottom: 14px;
        }
        .custom-step-panel label {
          display: grid;
          gap: 7px;
        }
        .custom-step-panel label > span {
          font-size: 11px;
          color: var(--ink-3);
          font-weight: 800;
          letter-spacing: 0;
          text-transform: none;
        }
        .custom-step-panel input,
        .custom-step-panel select,
        .custom-step-panel textarea {
          width: 100%;
          border: 1px solid var(--ink) !important;
          background: #f8f3e8;
          padding: 11px 12px;
          box-shadow: none !important;
          outline: none;
          font-size: 15px;
        }
        .custom-step-panel textarea {
          min-height: 118px;
          resize: vertical;
          line-height: 1.4;
        }
        .custom-two {
          display: grid;
          grid-template-columns: 1fr;
          gap: 10px;
        }
        .custom-help,
        .sheet-validation {
          margin: 0;
          color: var(--ink-2);
          font-size: 13px;
          font-weight: 700;
          line-height: 1.4;
        }
        .sheet-validation {
          color: var(--red);
        }
        .target-concept-grid {
          display: flex;
          flex-wrap: wrap;
          gap: 7px;
        }
        .target-section-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          margin-top: 3px;
          border-bottom: 1px solid rgba(20,17,13,.22);
          padding-bottom: 5px;
        }
        .target-section-head span {
          font-size: 11px;
          font-weight: 900;
          letter-spacing: .08em;
          text-transform: uppercase;
        }
        .target-section-head small {
          color: var(--ink-2);
          font-size: 11px;
          font-weight: 800;
        }
        .target-concept-grid button {
          min-height: 36px;
          border: 1px solid var(--ink);
          background: #f8f3e8;
          padding: 7px 10px;
          text-align: left;
          font-size: 12px;
          font-weight: 800;
          line-height: 1.15;
        }
        .target-concept-grid button.due {
          background: var(--yellow);
          box-shadow: 2px 2px 0 var(--ink);
        }
        .target-concept-grid button.notebook {
          background: #f8f3e8;
        }
        .target-concept-grid button.selected {
          background: var(--ink);
          color: var(--paper);
          box-shadow: none;
        }
        .target-concept-grid button strong,
        .target-concept-grid button small,
        .target-concept-grid button span {
          display: block;
        }
        .target-concept-grid button span {
          margin-bottom: 5px;
          color: var(--red);
          font-size: 9px;
          font-weight: 900;
          line-height: 1;
          text-transform: uppercase;
        }
        .target-concept-grid button small {
          margin-top: 4px;
          color: var(--ink-3);
          font-size: 10px;
          font-weight: 800;
        }
        .target-concept-grid button.selected span,
        .target-concept-grid button.selected small {
          color: rgba(241,236,225,.72);
        }
        .target-vocabulary-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 7px;
        }
        .target-vocabulary-grid button {
          display: grid;
          gap: 3px;
          width: 100%;
          min-height: 58px;
          border: 1px solid var(--ink);
          background: #f8f3e8;
          padding: 9px 10px;
          text-align: left;
          box-shadow: 2px 2px 0 var(--ink);
        }
        .target-vocabulary-grid button.selected {
          background: var(--ink);
          color: var(--paper);
          box-shadow: none;
        }
        .target-vocabulary-grid span {
          color: var(--red);
          font-size: 9px;
          font-weight: 900;
          line-height: 1;
          text-transform: uppercase;
        }
        .target-vocabulary-grid strong {
          font-family: var(--serif);
          font-size: 20px;
          font-style: italic;
          line-height: 1;
        }
        .target-vocabulary-grid small,
        .target-vocabulary-grid em {
          overflow: hidden;
          color: var(--ink-2);
          font-size: 11px;
          font-style: normal;
          font-weight: 800;
          line-height: 1.25;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .target-vocabulary-grid em {
          color: var(--ink-3);
          font-weight: 700;
        }
        .target-vocabulary-grid button.selected span,
        .target-vocabulary-grid button.selected small,
        .target-vocabulary-grid button.selected em {
          color: rgba(241,236,225,.72);
        }
        .concept-loading {
          width: 100%;
          border: 1px dashed var(--ink-3);
          padding: 14px;
          color: var(--ink-2);
          font-size: 13px;
          font-weight: 800;
        }
        .custom-confirm-card {
          border: 1px solid var(--ink);
          background: var(--paper-2);
          padding: 12px;
        }
        .custom-confirm-card strong {
          display: block;
          margin-top: 7px;
          font-family: var(--serif);
          font-size: 23px;
          font-style: italic;
          line-height: 1;
        }
        .custom-confirm-card p {
          margin: 10px 0;
          color: var(--ink-2);
          font-size: 13px;
          line-height: 1.4;
        }
        .custom-confirm-card small {
          color: var(--ink-2);
          font-weight: 800;
        }
        .confirm-vocabulary {
          display: flex;
          flex-wrap: wrap;
          gap: 5px;
          margin-top: 10px;
        }
        .confirm-vocabulary span {
          border: 1px solid var(--ink);
          background: #f8f3e8;
          padding: 4px 7px;
          font-size: 11px;
          font-weight: 900;
        }
        .custom-flow-actions {
          position: sticky;
          bottom: 0;
          display: grid;
          grid-template-columns: 1fr 1.4fr;
          gap: 8px;
          margin: 0 -16px;
          padding: 10px 16px calc(14px + env(safe-area-inset-bottom));
          border-top: 1px solid var(--ink);
          background: var(--paper);
        }
        .custom-flow-actions button {
          min-height: 48px;
          border: 1px solid var(--ink);
          background: #f8f3e8;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: 0;
          text-transform: none;
        }
        .custom-flow-actions button:last-child {
          background: var(--ink);
          color: var(--paper);
        }
        .custom-flow-actions button:disabled {
          opacity: .45;
          cursor: not-allowed;
        }
        .messenger-workspace {
          gap: 12px;
          padding: 0;
          border-width: 0;
          background: transparent;
        }
        .messenger-workspace .workspace-head {
          display: none;
        }
        .mobile-thread-summary {
          display: none;
        }
        .custom-composer:not(.expanded) .composer-form {
          display: none;
        }
        .composer-copy {
          width: 100%;
          border-bottom: 0;
          padding-bottom: 0;
        }
        .composer-topline {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }
        .composer-topline span {
          display: inline-flex;
          border: 1px solid var(--ink);
          background: var(--yellow);
          padding: 4px 7px;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: 0;
          line-height: 1;
          text-transform: none;
        }
        .custom-composer.expanded .composer-copy {
          border-bottom: 2px solid var(--ink);
          padding-bottom: 14px;
          margin-bottom: 14px;
        }
        .composer-copy h2 {
          font-size: 21px;
        }
        .composer-copy p {
          font-size: 13px;
        }
        .composer-toggle {
          display: inline-flex;
          width: 100%;
        }
        .composer-form textarea {
          min-height: 128px;
          box-shadow: none !important;
        }
        .composer-row input, .composer-row select {
          box-shadow: none !important;
        }
        .phone-shell {
          width: 100%;
          max-width: 100%;
          min-width: 0;
          min-height: 0;
          border: 0;
          border-radius: 0;
          padding: 0;
          background: transparent;
          box-shadow: none;
        }
        .phone-screen {
          border-radius: 0;
          min-height: calc(100svh - 162px);
          max-height: none;
          border: 0;
          background: var(--paper);
        }
        .phone-status {
          display: none;
        }
        .thread-contact {
          display: none;
        }
        .message-list {
          max-height: none;
          min-height: 0;
          padding: 12px 2px 10px;
        }
        .message-bubble-real { max-width: 94%; }
        .message-bubble-real {
          border: 1px solid var(--ink);
          border-radius: 0;
          background: #f8f3e8;
          box-shadow: none;
        }
        .message-row.user .message-bubble-real {
          border-color: var(--ink);
          border-radius: 0;
          background: var(--ink);
          color: var(--paper);
        }
        .message-row.assistant .message-bubble-real {
          border-radius: 0;
        }
        .message-bubble-real span {
          text-transform: none;
          letter-spacing: 0;
        }
        .turn-repair-card {
          border-color: rgba(241,236,225,.32);
          background: rgba(241,236,225,.08);
        }
        .message-row.assistant .turn-repair-card,
        .message-row.assistant .repair-markup .right {
          color: var(--ink);
        }
        .message-row.assistant .turn-repair-card .t-mono-low,
        .message-row.assistant .repair-markup small {
          color: var(--ink-2);
        }
        .mission-bridge-panel {
          margin: 12px 0;
          padding: 14px;
          box-shadow: none;
        }
        .mission-bridge-panel h3 {
          font-size: 21px;
        }
        .bridge-actions a {
          min-height: 44px;
          font-size: 12px;
        }
        .analysis-interstitial {
          border-width: 1px;
          box-shadow: none;
        }
        .retry-send-bar {
          display: grid;
          grid-template-columns: minmax(0, 1fr);
          align-items: stretch;
          padding: 10px 12px;
        }
        .failed-snippet {
          white-space: nowrap;
        }
        .retry-actions {
          justify-content: flex-end;
          margin-top: 8px;
        }
        .retry-actions button {
          min-height: 32px;
          padding-inline: 12px;
        }
        .phone-composer {
          position: sticky;
          bottom: 0;
          z-index: 2;
          grid-template-columns: minmax(0, 1fr);
          padding: 8px 10px 10px;
          background: #f8f3e8;
          border-top-color: var(--ink);
        }
        .mobile-composer-status {
          display: grid;
          gap: 3px;
          border-left: 4px solid var(--blue);
          background: rgba(29,58,138,.08);
          padding: 6px 9px;
        }
        .mobile-composer-status span {
          font-size: 9px;
          font-weight: 900;
          letter-spacing: 0;
          text-transform: none;
          color: var(--ink-2);
        }
        .mobile-composer-status strong {
          font-size: 12px;
          line-height: 1.25;
        }
        .phone-composer.state-default .mobile-composer-status {
          border-left-color: var(--ink-3);
          background: rgba(20,17,13,.04);
        }
        .phone-composer.state-voice .mobile-composer-status {
          border-left-color: var(--yellow);
          background: rgba(243,195,24,.18);
        }
        .phone-composer.state-sent .mobile-composer-status {
          border-left-color: var(--green);
          background: rgba(28,124,84,.12);
        }
        .phone-composer.state-failed .mobile-composer-status {
          border-left-color: var(--red);
          background: rgba(216,50,26,.12);
        }
        .mobile-composer-tools {
          display: none;
        }
        .mobile-composer-tools button {
          min-height: 36px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 7px;
          border: 1px solid var(--ink);
          background: var(--paper);
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .1em;
          text-transform: uppercase;
        }
        .phone-composer textarea {
          min-height: 44px;
          max-height: 108px;
          border-color: var(--ink) !important;
          border-radius: 0 !important;
          background: #f8f3e8;
          padding: 10px 12px;
          font-size: 16px;
        }
        .composer-input-row {
          grid-template-columns: 44px minmax(0, 1fr) 44px;
          gap: 8px;
          align-items: end;
        }
        .composer-mic {
          display: grid;
          width: 44px;
          height: 44px;
          place-items: center;
          border: 1px solid var(--ink) !important;
          background: #f8f3e8 !important;
          color: var(--ink);
        }
        .composer-mic:disabled {
          opacity: .45;
          cursor: not-allowed;
        }
        .phone-composer.state-voice .composer-mic {
          background: var(--red) !important;
          color: var(--paper);
        }
        .send-dot {
          width: 44px;
          height: 44px;
          border: 1px solid var(--ink) !important;
          border-radius: 0;
          background: var(--ink) !important;
        }
        .mobile-state-actions {
          display: grid;
          width: 100%;
          gap: 9px;
        }
        .mission-error {
          border-color: var(--red);
        }
        .mobile-voice-layer {
          position: fixed;
          inset: 0;
          z-index: 150;
          display: block;
        }
        .mobile-voice-scrim {
          position: absolute;
          inset: 0;
          background: rgba(20,17,13,.4);
        }
        .mobile-voice-sheet {
          position: absolute;
          left: 0;
          right: 0;
          bottom: 0;
          border-top: 1px solid var(--ink);
          background: var(--paper);
          padding: 10px 16px calc(18px + env(safe-area-inset-bottom));
          box-shadow: 0 -16px 40px rgba(20,17,13,.22);
          animation: mission-sheet-up 280ms ease-out both;
        }
        .voice-sheet-head {
          display: flex;
          gap: 12px;
          align-items: center;
        }
        .voice-sheet-head h2 {
          margin: 3px 0 0;
          font-family: var(--serif);
          font-size: 30px;
          font-style: italic;
          line-height: 1;
        }
        .voice-live-dot {
          width: 44px;
          height: 44px;
          border: 1px solid var(--ink);
          border-radius: 50%;
          background: var(--red);
          box-shadow: inset 0 0 0 12px #f8f3e8;
          flex: 0 0 auto;
        }
        .voice-waveform {
          min-height: 78px;
          margin: 16px 0 10px;
          border: 1px solid var(--ink);
          background: #f8f3e8;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          padding: 12px;
        }
        .voice-waveform span {
          width: 4px;
          background: var(--ink);
        }
        .voice-waveform.recording span:nth-child(2n) {
          background: var(--red);
        }
        .mobile-voice-sheet p {
          margin: 0 0 14px;
          color: var(--ink-2);
          font-size: 13px;
          font-weight: 700;
          line-height: 1.4;
        }
        .voice-sheet-actions {
          display: grid;
          grid-template-columns: 1.2fr 1fr;
          gap: 8px;
        }
        .voice-sheet-actions button {
          min-height: 56px;
          border: 1px solid var(--ink);
          background: #f8f3e8;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: 0;
          text-transform: none;
        }
        .voice-sheet-actions .voice-stop {
          background: var(--red);
          border-color: var(--red);
          color: var(--paper);
        }
        .voice-sheet-actions button:disabled {
          opacity: .5;
          cursor: not-allowed;
        }
        .thread-tools {
          display: none;
        }
        .voice-affordance {
          display: flex;
          gap: 12px;
          align-items: flex-start;
          border: 2px solid var(--ink);
          background: var(--yellow);
          padding: 12px;
          box-shadow: 3px 3px 0 var(--ink);
        }
        .voice-affordance > span {
          width: 34px;
          height: 34px;
          border-radius: 50%;
          border: 2px solid var(--ink);
          background: var(--paper);
          display: grid;
          place-items: center;
          flex: 0 0 auto;
        }
        .voice-affordance.recording > span,
        .voice-affordance.transcribing > span {
          background: var(--red);
          color: var(--paper);
        }
        .voice-affordance strong {
          display: block;
          font-size: 14px;
          line-height: 1.15;
        }
        .voice-affordance small {
          display: block;
          margin-top: 4px;
          color: var(--ink-2);
          font-size: 12px;
          font-weight: 800;
          line-height: 1.25;
        }
        .scene-strip {
          padding: 12px;
        }
        .thread-tools > p {
          font-size: 14px;
        }
        .quick-replies {
          grid-template-columns: 1fr;
        }
        .complete-row, .draft-footer, .action-row { align-items: stretch; flex-direction: column; }
        .complete-row .btn, .draft-footer .btn, .action-row .btn { width: 100%; }
      }
    `}</style>
  );
}

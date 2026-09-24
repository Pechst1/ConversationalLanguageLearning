import React, { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { useRouter } from 'next/router';

import { atelierChrome } from '@/lib/atelier-v2-copy';
import { useChromeLanguage } from '@/lib/learner-language';
import { pickByLanguage } from '@/lib/language-rule';
import { castIdFor } from '@/lib/cast-faces';
import type { ControlLanguage } from '@/types/daily-journey';
import PhoneProductNav from '@/components/layout/PhoneProductNav';
import { LogoToken } from '@/components/ui/Seal';
import {
  ArrowLeftIcon,
  AtelierV2Root,
  Chip,
  IconAction,
  MicIcon,
  ShapeToken,
  Skeleton,
  StateBlock,
  StopIcon,
  useControlLanguage,
} from '@/components/atelier-v2/ui';
import {
  CourrierStyles,
  CrArtefactCard,
  CrArtefactTaskCard,
  CrArtefactUnread,
  CrComposer,
  CrDesk,
  CrGhost,
  CrIntakeEntry,
  CrIntakeLink,
  CrMemo,
  CrPS,
  CrRepair,
  CrRibbon,
  CrSeal,
  CrSituation,
  CrSlip,
  crSealNumbers,
} from '@/components/courrier/Courrier';
import {
  CrCorrespondent,
  CrLapsedNotice,
  crMoodFace,
  crMoodKey,
  crMoodSentence,
  crMoodValue,
  crOutcomeLabel,
  crOutcomeSentence,
} from '@/components/courrier/Correspondance';
import { courrierCopy, crFill, useCrCopy, type CourrierCopy } from '@/components/courrier/courrier-copy';
import apiService, {
  IntakeArtefact,
  IntakeEnvelope,
  MissionMeasured,
  MissionToday,
  RealWorldMission,
  SerialToday,
} from '@/services/api';
import { createAudioMediaRecorder, recordedAudioBlob } from '@/lib/audio-recording';
import { serialQueryString, writeLocalDayProgressFlag } from '@/lib/atelier-next';
import { clearResumeActivity, readLocalJson, saveResumeActivity, writeLocalJson } from '@/lib/pilot-resilience';

// Only what the Courrier actually prints. contact_role, contact_initials,
// presence, thread_title, inbox_context and ambient_cues were computed on every
// render and read by nothing — dead plumbing carrying dead English defaults.
type MissionMessenger = {
  channel_label: string;
  contact_name: string;
  scene_anchor: string;
  dispatch_note: string;
  opening_message: string;
  quick_replies: string[];
  success_signal: string;
  twist?: string | null;
};

type QuerySeed = {
  missionId?: string;
  serialThreadId?: string;
  episodeIndex?: number;
  atelierSessionId?: string;
  conceptIds: number[];
  vocabularyIds: number[];
  erratumIds: string[];
};

function firstQuery(value: string | string[] | undefined) {
  if (!value) return undefined;
  return Array.isArray(value) ? value[0] : value;
}

function queryStringList(value: string | string[] | undefined) {
  const list = !value ? [] : Array.isArray(value) ? value : [value];
  return list.map((item) => item.trim()).filter(Boolean);
}

function queryNumberList(value: string | string[] | undefined) {
  return queryStringList(value)
    .map((item) => Number(item))
    .filter((item) => Number.isFinite(item));
}

function compactText(value: unknown, max = 180) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1).trim()}...`;
}

function _normalizeVisibleMessage(value: unknown) {
  return String(value || '').replace(/\s+/g, ' ').trim().toLocaleLowerCase('fr');
}

function uniqueText(items: string[], limit = 4) {
  const seen = new Set<string>();
  const result: string[] = [];
  items.forEach((item) => {
    const text = item.trim();
    const key = text.toLowerCase();
    if (!text || seen.has(key) || result.length >= limit) return;
    seen.add(key);
    result.push(text);
  });
  return result;
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item || '').trim()).filter(Boolean)
    : [];
}

function missionSlimPayload(mission: RealWorldMission | null): Record<string, any> {
  const raw = mission?.prompt_payload?.slim_payload;
  return raw && typeof raw === 'object' ? raw as Record<string, any> : {};
}

function missionVariety(mission: RealWorldMission | null): Record<string, any> {
  const raw = mission?.prompt_payload?.variety;
  return raw && typeof raw === 'object' ? raw as Record<string, any> : {};
}

function missionMessenger(mission: RealWorldMission | null): MissionMessenger {
  const prompt = mission?.prompt_payload || {};
  const raw = prompt.messenger && typeof prompt.messenger === 'object' ? prompt.messenger as Record<string, any> : {};
  const slim = missionSlimPayload(mission);
  // WP-82: these fallbacks stand in for the letter's own words (the frame, the
  // ask, the character's opening line), which are content — French at every
  // level, rendered with `lang="fr"`. None of them is chrome.
  return {
    channel_label: String(raw.channel_label || missionVariety(mission).channel_label || 'Message'),
    contact_name: String(raw.contact_name || 'Camille'),
    scene_anchor: String(slim.frame || raw.scene_anchor || mission?.brief || 'Un moment de la vraie vie, en français.'),
    dispatch_note: String(slim.ask || raw.dispatch_note || mission?.brief || 'Une réponse naturelle en français.'),
    opening_message: String(raw.opening_message || prompt.conversation_opening || 'Bonjour, vous pouvez me répondre ?'),
    quick_replies: uniqueText(asStringList(raw.quick_replies), 3),
    success_signal: String(raw.success_signal || 'Votre correspondant sait quoi faire ensuite.'),
    twist: raw.twist || missionVariety(mission).twist || null,
  };
}

function missionTitle(mission: RealWorldMission | null) {
  if (!mission) return 'Mission';
  const variety = missionVariety(mission);
  // Prefer the specific scene title ("Parcel Detour") over the generic domain label.
  return String(mission.title || variety.domain_label || 'Mission');
}

function missionFrame(mission: RealWorldMission | null, messenger: MissionMessenger, chromeLang: ControlLanguage = 'fr') {
  const slim = missionSlimPayload(mission);
  const frame = compactText(slim.frame || messenger.scene_anchor || mission?.brief, 210);
  // The objective is chrome (the one-language rule): the version in the
  // learner's chrome language when the letter carries it (`ask_by_language`,
  // app/services/missions.py `success_signal_i18n`). Fallback — a letter with
  // no version in that language keeps its French objective, marked `fr`.
  const localized = pickByLanguage(slim.ask_by_language, chromeLang);
  const french = pickByLanguage(slim.ask_by_language, 'fr');
  const ask = compactText(
    localized || french || slim.ask || messenger.dispatch_note || messenger.success_signal,
    150,
  );
  const askLang: string = localized ? chromeLang : 'fr';
  return { frame, ask, askLang };
}

function pickMission(today: MissionToday | null) {
  return today?.active_mission
    || today?.weekly_mission
    || today?.post_session_recommendation
    || null;
}

function missionTurns(mission: RealWorldMission | null) {
  return [...(mission?.turns || [])].sort((a, b) => Number(a.turn_index || 0) - Number(b.turn_index || 0));
}

// The word ribbon ("à placer :") — the target word itself, marked "used" once it
// surfaces in one of the learner's own turns.
function ribbonWords(mission: RealWorldMission | null): { t: string; used?: boolean }[] {
  const direct = Array.isArray(mission?.target_vocabulary) ? mission?.target_vocabulary || [] : [];
  const prompt = Array.isArray(mission?.prompt_payload?.target_vocabulary)
    ? mission?.prompt_payload?.target_vocabulary || []
    : [];
  const said = missionTurns(mission)
    .filter((turn) => turn.role === 'user')
    .map((turn) => String(turn.text || '').toLowerCase())
    .join(' ');
  const seen = new Set<string>();
  const result: { t: string; used?: boolean }[] = [];
  (direct.length ? direct : prompt).forEach((item: Record<string, any>) => {
    const word = String(item.word || '').trim();
    const key = word.toLowerCase();
    if (!word || seen.has(key) || result.length >= 3) return;
    seen.add(key);
    result.push({ t: word, used: key.length > 1 && said.includes(key) });
  });
  return result;
}

// The backend rotates five mission formats (serial_arc_planner.py) and ships a
// per-format payload + writing scaffold. These readers surface it so the
// composer can adapt; the visual "Le Courrier" reskin is a separate pass.
type MissionFormat = 'chat_message' | 'email_formal' | 'admin_form' | 'voicemail_reply' | 'phone_call';

function missionFormat(mission: RealWorldMission | null): MissionFormat {
  const raw = String(mission?.mission_format || mission?.prompt_payload?.mission_format || 'chat_message');
  const known: MissionFormat[] = ['chat_message', 'email_formal', 'admin_form', 'voicemail_reply', 'phone_call'];
  return (known as string[]).includes(raw) ? (raw as MissionFormat) : 'chat_message';
}

function missionFormatPayload(mission: RealWorldMission | null): Record<string, any> {
  const raw = mission?.prompt_payload?.mission_format_payload;
  return raw && typeof raw === 'object' ? raw as Record<string, any> : {};
}

function missionWriting(mission: RealWorldMission | null): { title: string; instruction: string; placeholder: string } {
  const prompt = mission?.prompt_payload || {};
  return {
    title: String(prompt.writing_title || ''),
    instruction: String(prompt.writing_instruction || ''),
    placeholder: String(prompt.writing_placeholder || ''),
  };
}

function missionIsVoice(format: MissionFormat) {
  return format === 'voicemail_reply' || format === 'phone_call';
}

function missionCadenceLabel(mission: RealWorldMission | null, t: CourrierCopy): string | null {
  const cadence = String(mission?.cadence || '');
  if (cadence === 'weekly') return t.cadence_weekly;
  if (cadence === 'post_session') return t.cadence_post_session;
  return null; // ad_hoc needs no marginal label
}

// WP-82: the labels and instructions are chrome (`t`); the email and form
// placeholders are French templates of the letter itself, so they stay French.
function formatComposerCopy(
  format: MissionFormat,
  writing: { title: string; instruction: string; placeholder: string },
  t: CourrierCopy,
) {
  // The server writes `writing_title` / `writing_instruction` in French: they
  // are chrome, so they are only used when the chrome is French (B1+).
  const serverChrome = t.lang === 'fr';
  const title = serverChrome ? writing.title : '';
  const instruction = serverChrome ? writing.instruction : '';
  switch (format) {
    case 'email_formal':
      return {
        label: title || t.composer_label_email,
        instruction: instruction || t.composer_instruction_email,
        placeholder: writing.placeholder || 'Objet : ...\n\nMadame, Monsieur,\n...',
      };
    case 'admin_form':
      return {
        label: title || t.composer_label_form,
        instruction: instruction || t.composer_instruction_form,
        placeholder: writing.placeholder || 'Nom :\nAdresse :\nDemande :',
      };
    case 'voicemail_reply':
      return { label: t.composer_label_voicemail, instruction: t.composer_instruction_voicemail, placeholder: t.composer_placeholder_voice };
    case 'phone_call':
      return { label: t.composer_label_call, instruction: t.composer_instruction_call, placeholder: t.composer_placeholder_voice };
    default:
      return { label: t.composer_label_chat, instruction: '', placeholder: t.composer_placeholder_chat };
  }
}

// The composer verb per artefact, in the chrome language.
function submitLabel(format: MissionFormat, t: CourrierCopy) {
  if (format === 'email_formal') return t.send_email;
  if (format === 'admin_form') return t.send_form;
  return t.send;
}

// Real grammar fixes only, mirroring the quiet-repair rules: drop task-compliance
// notes and vocabulary nudges; keep corrections that carry a fix or a reason.
function repairLines(correction: Record<string, any> | undefined): { fixed?: string; why?: string }[] {
  if (!correction) return [];
  const errata = (Array.isArray(correction.errata) ? correction.errata : []).filter((item: any) => {
    const kind = String(item?.task_error_type || '');
    if (kind === 'task_compliance' || kind.startsWith('vocabulary')) return false;
    return Boolean(item?.corrected_target || item?.why_wrong);
  });
  // The corrector returns at most three real mistakes; show all of them, so the
  // "N réparations enregistrées" line below the card can never outrun the card.
  return errata.slice(0, 3).map((item: any) => ({
    fixed: item.corrected_target ? String(item.corrected_target) : undefined,
    why: item.why_wrong ? String(item.why_wrong) : undefined,
  }));
}

// Repairs actually filed in error memory. `saved_count` also counts vocabulary
// credit rows, which this card never shows — reading it printed "1 réparation
// enregistrée" under a card with nothing repaired on it.
function correctionPersistence(correction: Record<string, any> | undefined) {
  const persistence = correction?.persistence as Record<string, any> | undefined;
  if (!persistence) return 0;
  if (typeof persistence.repair_count === 'number') return Math.max(0, persistence.repair_count);
  const records = Array.isArray(persistence.records) ? persistence.records : [];
  return records.filter((row: any) => !row?.linked_word_id && String(row?.error_category || '') !== 'vocabulary').length;
}

function correctedReply(correction: Record<string, any> | undefined, learnerText: unknown) {
  const corrected = String(correction?.corrected_answer || '').trim();
  const original = String(learnerText || '').trim();
  if (!corrected || corrected.localeCompare(original, undefined, { sensitivity: 'accent' }) === 0) return '';
  return corrected;
}

function currentComposerInstruction(
  mission: RealWorldMission | null,
  base: { label: string; instruction: string; placeholder: string },
  t: CourrierCopy,
): { label: string; instruction: string; placeholder: string } {
  if (!missionTurns(mission).some((turn) => turn.role === 'user')) return base;
  const assistantTurns = missionTurns(mission).filter((turn) => turn.role === 'assistant');
  const latest = assistantTurns.slice(-1)[0] as Record<string, any> | undefined;
  if (!latest) {
    return base;
  }
  const assistantText = compactText(latest.text, 150);
  const branch = latest.audio_payload?.branch || {};
  const state = String(branch.state || '');
  if (state === 'understood') {
    return {
      label: t.composer_label_last,
      instruction: t.composer_instruction_last,
      placeholder: t.composer_placeholder_last,
    };
  }
  return {
    label: t.composer_label_reply,
    instruction: assistantText
      ? crFill(t.composer_instruction_quoted, { text: assistantText })
      : t.composer_instruction_reply,
    placeholder: t.composer_placeholder_reply,
  };
}

// Slip time rule ("08 h 12"), printed only when the turn carries a timestamp —
// never invented (honest-data contract).
function slipTime(turn: Record<string, any> | null): string | undefined {
  const raw = turn?.created_at || turn?.timestamp || null;
  if (!raw) return undefined;
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return undefined;
  return `${String(date.getHours()).padStart(2, '0')} h ${String(date.getMinutes()).padStart(2, '0')}`;
}

// «12 septembre» / «12 September» / «12. September», in the chrome locale.
function chromeDate(raw: string | null | undefined, locale: string): string {
  const date = raw ? new Date(raw) : new Date();
  const safe = Number.isNaN(date.getTime()) ? new Date() : date;
  return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'long' }).format(safe);
}

// The kicker: a serial act flips to the blue "Le Feuilleton · Acte N" furniture.
function deskKicker(mission: RealWorldMission | null, isSerialAct: boolean, actNumber: number | null, t: CourrierCopy) {
  if (!isSerialAct) return t.courrier;
  return actNumber != null ? crFill(t.feuilleton_act, { n: actNumber }) : t.feuilleton;
}

// Status as printed marginalia (never a pill), in the chrome language.
function deskStatusLine(mission: RealWorldMission | null, format: MissionFormat, completed: boolean, t: CourrierCopy): string {
  if (completed) return crFill(t.status_done, { date: chromeDate(mission?.completed_at, t.locale) });
  // WP-64's fourth status. Marginalia, like the rest: a letter that stopped
  // waiting is a fact of the correspondence, not a verdict on the learner.
  if (mission?.status === 'lapsed') return t.status_lapsed;
  if (mission?.status === 'in_progress') return t.status_in_progress;
  if (format === 'email_formal') return t.status_email;
  if (format === 'admin_form') return t.status_form;
  if (format === 'voicemail_reply') return t.status_voicemail;
  if (format === 'phone_call') return t.status_call;
  return t.status_received;
}

function latestAssistantReply(mission: RealWorldMission | null) {
  return missionTurns(mission).filter((turn) => turn.role === 'assistant').slice(-1)[0]?.text || '';
}

function hasInteraction(mission: RealWorldMission | null) {
  return Boolean((mission?.attempts || []).length || missionTurns(mission).some((turn) => turn.role === 'user'));
}

function querySeed(routerQuery: Record<string, string | string[] | undefined>): QuerySeed {
  const episodeRaw = firstQuery(routerQuery.episode_index);
  const episodeIndex = episodeRaw === undefined ? undefined : Number(episodeRaw);
  return {
    missionId: firstQuery(routerQuery.mission) || firstQuery(routerQuery.mission_id),
    serialThreadId: firstQuery(routerQuery.serial_thread_id),
    episodeIndex: Number.isFinite(episodeIndex) ? episodeIndex : undefined,
    atelierSessionId: firstQuery(routerQuery.atelier_session_id),
    conceptIds: queryNumberList(routerQuery.concept_id),
    vocabularyIds: queryNumberList(routerQuery.vocabulary_id),
    erratumIds: queryStringList(routerQuery.erratum_id),
  };
}

// The serial gate refuses a new act while the current episode is still unread
// (409 serial_episode_not_ready). Saying only "n'a pas pu être ouvert" left the
// learner with a retry button that can never work; name the actual blocker.
// The state keeps the kind, not the sentence, so the sentence follows the
// chrome language even when the profile settles after the failure.
type LoadErrorKind = 'not_ready' | 'open';

function loadErrorKind(error: any): LoadErrorKind {
  const detail = error?.response?.data?.detail;
  if (detail && typeof detail === 'object' && detail.code === 'serial_episode_not_ready') return 'not_ready';
  return 'open';
}

function loadErrorMessage(kind: LoadErrorKind, t: CourrierCopy): string {
  return kind === 'not_ready' ? t.error_not_ready : t.error_open;
}

// WP-34's refusals already arrive in French from the server (`detail.message_fr`
// — the weekly cap, an unreadable photo, a document too long). Printing our own
// sentence over them would be inventing a reason we do not know.
function intakeErrorMessage(error: any, t: CourrierCopy): string {
  const detail = error?.response?.data?.detail;
  const french = detail && typeof detail === 'object' ? String(detail.message_fr || '') : '';
  return french || t.intake_error;
}

function shouldCreateFromSeed(seed: QuerySeed) {
  return Boolean(
    seed.serialThreadId
    || seed.atelierSessionId
    || seed.conceptIds.length
    || seed.vocabularyIds.length
    || seed.erratumIds.length,
  );
}

function routeForMissionSerialBeat(serial: SerialToday | null | undefined) {
  if (!serial?.thread_id || typeof serial.episode_index !== 'number') return '/atelier';
  const query = serialQueryString(serial);
  if (serial.kind === 'mission') return `/missions${query}`;
  if (serial.kind === 'feuilleton') return `/graphic-novel${query}`;
  return '/atelier';
}

// Archive status, in the chrome language — printed as marginalia on each row.
function archiveStatus(mission: RealWorldMission | null, t: CourrierCopy) {
  if (!mission) return '';
  if (mission.status === 'completed') return t.archive_done;
  if (mission.status === 'in_progress') return t.archive_in_progress;
  return t.archive_todo;
}

// Records a spoken reply and transcribes it via /missions/audio/transcribe,
// then hands the text back to the composer. Used for voicemail/phone formats.
// It is the design's round red press (mic → ink "recording" → pending) and
// stands in the composer where the send press would otherwise be, so the
// screen keeps exactly one 3D press. The state is also said in words.
type MicState = 'idle' | 'recording' | 'transcribing';

function CourrierMic({
  onTranscript,
  onStateChange,
  disabled,
}: {
  onTranscript: (text: string) => void;
  onStateChange?: (state: MicState) => void;
  disabled?: boolean;
}) {
  const [state, setState] = useState<MicState>('idle');
  const [problem, setProblem] = useState<string | null>(null);
  // WP-82: the mic's words are the composer's chrome, so they read the same
  // chrome language as the card around them — never a second language.
  const chrome = atelierChrome(useControlLanguage());
  const t = useCrCopy();
  const [seconds, setSeconds] = useState(0);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearTimer = () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };
  useEffect(() => () => clearTimer(), []);
  useEffect(() => { onStateChange?.(state); }, [onStateChange, state]);

  const start = async () => {
    setProblem(null);
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setProblem(chrome.mic_unavailable);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = createAudioMediaRecorder(stream);
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => { if (event.data.size > 0) chunksRef.current.push(event.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        clearTimer();
        setState('transcribing');
        try {
          const blob = recordedAudioBlob(chunksRef.current, recorder);
          const text = await apiService.transcribeMissionAudio(blob);
          if (text && text.trim()) onTranscript(text.trim());
          else setProblem(chrome.transcription_empty);
        } catch (transcribeError) {
          console.error(transcribeError);
          setProblem(chrome.transcription_failed);
        } finally {
          setState('idle');
        }
      };
      recorder.start();
      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds((value) => value + 1), 1000);
      setState('recording');
    } catch (permissionError) {
      console.error(permissionError);
      setProblem(chrome.mic_denied);
      setState('idle');
    }
  };

  const stop = () => {
    if (recorderRef.current && state === 'recording') recorderRef.current.stop();
  };

  const timer = `${Math.floor(seconds / 60)} : ${String(seconds % 60).padStart(2, '0')}`;

  return (
    <>
      <IconAction
        label={state === 'recording' ? t.mic_stop : t.mic_start}
        tone={state === 'recording' ? 'recording' : 'action'}
        pressable
        className="cr-send"
        pending={state === 'transcribing'}
        disabled={disabled}
        onClick={state === 'recording' ? stop : start}
      >
        {state === 'recording' ? <StopIcon size={20} /> : <MicIcon size={20} />}
      </IconAction>
      {state === 'recording' && (
        <p className="cr-mic-state cr-mic-state--rec" role="status" aria-live="polite">
          <ShapeToken kind="action" size="sm" />
          <span>{crFill(t.mic_recording, { timer })}</span>
        </p>
      )}
      {state === 'transcribing' && (
        <p className="cr-mic-state" role="status" aria-live="polite">
          <ShapeToken kind="story" size="sm" />
          <span>{chrome.transcribing}</span>
        </p>
      )}
      {problem && <p className="cr-mic-problem" role="status">{problem}</p>}
    </>
  );
}

export default function MissionsPage() {
  const router = useRouter();
  // WP-82 — one language rule: the Courrier's chrome is the learner's
  // language up to A2 and French from B1. Computed once, handed to the
  // page's AtelierV2Root; every Courrier component reads it from there.
  const chromeLang = useChromeLanguage();
  const t = courrierCopy(chromeLang);
  const [today, setToday] = useState<MissionToday | null>(null);
  const [mission, setMission] = useState<RealWorldMission | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [error, setError] = useState<LoadErrorKind | null>(null);
  const [reply, setReply] = useState('');
  const [micState, setMicState] = useState<MicState>('idle');
  const [completedNextSerial, setCompletedNextSerial] = useState<SerialToday | null>(null);
  // WP-34's surface (WP-37 §2.1). «Vos documents» is a second view of this
  // route rather than a second page: it is the Courrier's own intake, it opens
  // Courrier tasks, and giving it its own view keeps exactly one 3D press on
  // screen — «Faire lire» here, the reply there.
  const [intake, setIntake] = useState<IntakeEnvelope | null>(null);
  const [intakeLoading, setIntakeLoading] = useState(true);
  const [intakeReading, setIntakeReading] = useState(false);
  const [intakeError, setIntakeError] = useState<string | null>(null);
  const [deletingArtefactId, setDeletingArtefactId] = useState<string | null>(null);
  const loadRequestRef = useRef(0);
  const replyRef = useRef<HTMLTextAreaElement | null>(null);

  const seed = useMemo(() => querySeed(router.query as Record<string, string | string[] | undefined>), [router.query]);
  const intakeMode = Boolean(firstQuery(router.query.intake));
  const messenger = useMemo(() => missionMessenger(mission), [mission]);
  const frame = useMemo(() => missionFrame(mission, messenger, chromeLang), [mission, messenger, chromeLang]);
  const turns = useMemo(() => missionTurns(mission), [mission]);
  const ribbon = useMemo(() => ribbonWords(mission), [mission]);
  const isSerialAct = Boolean(mission?.serial_thread_id || seed.serialThreadId);
  const completed = mission?.status === 'completed';
  // WP-64: an overdue chain letter stops waiting. There is nothing left to
  // write, so the situation, the ribbon and the composer come off the screen —
  // but nothing on it calls it a failure.
  const lapsed = mission?.status === 'lapsed';
  const interactionReady = hasInteraction(mission);
  const canSend = reply.trim().length > 0 && !submitting && !completed && !lapsed;
  const format = useMemo(() => missionFormat(mission), [mission]);
  const writing = useMemo(() => missionWriting(mission), [mission]);
  const formatPayload = useMemo(() => missionFormatPayload(mission), [mission]);
  const composerCopy = useMemo(() => formatComposerCopy(format, writing, t), [format, writing, t]);
  const turnComposerCopy = useMemo(
    () => currentComposerInstruction(
      mission,
      {
        ...composerCopy,
        instruction: composerCopy.instruction || frame.ask,
      },
      t,
    ),
    [composerCopy, frame.ask, mission, t],
  );
  const cadenceLabel = missionCadenceLabel(mission, t);
  const isVoiceFormat = missionIsVoice(format);
  const recentCompleted = today?.recent_completed || [];
  const openingMessage = isVoiceFormat && formatPayload.transcript
    ? String(formatPayload.transcript)
    : messenger.opening_message;
  const visibleTurns = useMemo(() => {
    let hasLearnerTurn = false;
    const openingKey = _normalizeVisibleMessage(openingMessage);
    return turns.filter((turn) => {
      if (turn.role === 'user') {
        hasLearnerTurn = true;
        return true;
      }
      return hasLearnerTurn || _normalizeVisibleMessage(turn.text) !== openingKey;
    });
  }, [openingMessage, turns]);
  const actNumber = typeof mission?.episode_index === 'number'
    ? mission.episode_index + 1
    : typeof seed.episodeIndex === 'number' ? seed.episodeIndex + 1 : null;
  const mintedToken = Array.isArray((mission?.recap as Record<string, any>)?.minted_collectibles)
    && (mission?.recap as Record<string, any>).minted_collectibles.some((item: any) => item?.kind === 'logo_token');

  const routeToMission = useCallback((next: RealWorldMission) => {
    if (!router.isReady) return;
    const current = firstQuery(router.query.mission);
    if (current === next.id) return;
    void router.replace({ pathname: '/missions', query: { mission: next.id } }, undefined, { shallow: true });
  }, [router]);

  const createSeededMission = useCallback(async (
    nextSeed: QuerySeed,
    isCurrent: () => boolean = () => true,
  ) => {
    if (!isCurrent()) return null;
    setCreating(true);
    try {
      const next = await apiService.createMission({
        mission_type: 'message',
        cadence: nextSeed.atelierSessionId ? 'post_session' : 'ad_hoc',
        atelier_session_id: nextSeed.atelierSessionId,
        serial_thread_id: nextSeed.serialThreadId,
        episode_index: nextSeed.episodeIndex,
        preferred_concept_ids: nextSeed.conceptIds.length ? nextSeed.conceptIds : undefined,
        preferred_errata_ids: nextSeed.erratumIds.length ? nextSeed.erratumIds : undefined,
        preferred_vocabulary_ids: nextSeed.vocabularyIds.length ? nextSeed.vocabularyIds : undefined,
        use_news: false,
      });
      if (!isCurrent()) return null;
      setMission(next);
      setCompletedNextSerial(null);
      routeToMission(next);
      return next;
    } finally {
      if (isCurrent()) setCreating(false);
    }
  }, [routeToMission]);

  const loadMission = useCallback(async () => {
    if (!router.isReady) return;
    if (intakeMode) {
      // The intake view loads no mission and — the part that matters — creates
      // none. Falling through would post a new mission (a paid generation) for
      // a learner who came here to paste a letter, and would then rewrite the
      // URL to that mission and throw the view away.
      setLoading(false);
      return;
    }
    const requestId = ++loadRequestRef.current;
    const isCurrent = () => loadRequestRef.current === requestId && router.pathname === '/missions';
    setLoading(true);
    setError(null);
    try {
      if (seed.missionId) {
        const next = await apiService.getMission(seed.missionId);
        if (!isCurrent()) return;
        setMission(next);
        setCompletedNextSerial(null);
        setToday(null);
        return;
      }
      if (shouldCreateFromSeed(seed)) {
        await createSeededMission(seed, isCurrent);
        return;
      }
      const nextToday = await apiService.getMissionsToday();
      if (!isCurrent()) return;
      setToday(nextToday);
      const next = pickMission(nextToday);
      if (next) {
        setMission(next);
        setCompletedNextSerial(null);
        routeToMission(next);
      } else {
        await createSeededMission(seed, isCurrent);
      }
    } catch (loadError) {
      console.error(loadError);
      if (!isCurrent()) return;
      setError(loadErrorKind(loadError));
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, [createSeededMission, intakeMode, routeToMission, router.isReady, router.pathname, seed]);

  useEffect(() => {
    void loadMission();
    return () => {
      loadRequestRef.current += 1;
    };
  }, [loadMission]);

  useEffect(() => {
    if (!intakeMode || !router.isReady) return undefined;
    let alive = true;
    setIntakeLoading(true);
    apiService.getIntakeArtefacts()
      .then((envelope) => { if (alive) setIntake(envelope); })
      .catch((loadError) => {
        console.error(loadError);
        if (alive) setIntakeError(intakeErrorMessage(loadError, t));
      })
      .finally(() => { if (alive) setIntakeLoading(false); });
    return () => { alive = false; };
    // `t` is read at failure time only; a language change must not refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intakeMode, router.isReady]);

  const readDocument = useCallback(async (input: { text?: string; file?: File }) => {
    if (intakeReading) return;
    setIntakeReading(true);
    setIntakeError(null);
    try {
      const envelope = input.file
        ? await apiService.readIntakePhoto(input.file, input.file.name || 'document.jpg')
        : await apiService.readIntakeText(String(input.text || ''));
      setIntake(envelope);
    } catch (readError) {
      console.error(readError);
      setIntakeError(intakeErrorMessage(readError, t));
    } finally {
      setIntakeReading(false);
    }
  }, [intakeReading, t]);

  const deleteDocument = useCallback(async (artefactId: string) => {
    if (deletingArtefactId) return;
    setDeletingArtefactId(artefactId);
    setIntakeError(null);
    try {
      // The button says it removes the document *and* its task, so the list is
      // re-read from the server rather than spliced here: a task the server
      // kept must not disappear from the screen.
      await apiService.deleteIntakeArtefact(artefactId);
      setIntake(await apiService.getIntakeArtefacts());
    } catch (deleteError) {
      console.error(deleteError);
      setIntakeError(intakeErrorMessage(deleteError, t));
    } finally {
      setDeletingArtefactId(null);
    }
  }, [deletingArtefactId, t]);

  useEffect(() => {
    if (!mission?.id || mission.status === 'completed') return;
    const key = `pilot:mission-draft:${mission.id}`;
    const draft = readLocalJson<string>(key, '');
    setReply((current) => current || draft);
    saveResumeActivity({
      href: `/missions?mission=${mission.id}`,
      kind: 'mission',
      entityId: mission.id,
    });
  }, [mission?.id, mission?.status]);

  useEffect(() => {
    if (!mission?.id || mission.status === 'completed') return;
    writeLocalJson(`pilot:mission-draft:${mission.id}`, reply);
  }, [mission?.id, mission?.status, reply]);

  const sendReply = async (event?: FormEvent) => {
    event?.preventDefault();
    const text = reply.trim();
    if (!mission || !text || submitting || completed) return;
    setSubmitting(true);
    try {
      const result = await apiService.submitMissionTurn(mission.id, { text, mode: 'chat' });
      setMission({ ...result.mission, outcome: result.outcome || result.mission.outcome });
      setReply('');
      window.localStorage.removeItem(`pilot:mission-draft:${mission.id}`);
    } catch (sendError) {
      console.error(sendError);
      toast.error(t.toast_send_failed);
    } finally {
      setSubmitting(false);
    }
  };

  const finishMission = async () => {
    if (!mission || completing || completed || !interactionReady) return;
    setCompleting(true);
    try {
      const result = await apiService.completeMission(mission.id);
      setMission(result.mission);
      clearResumeActivity('mission');
      window.localStorage.removeItem(`pilot:mission-draft:${mission.id}`);
      setCompletedNextSerial(result.next_serial || null);
      if (!result.mission.serial_thread_id) {
        writeLocalDayProgressFlag('missionDone');
      }
      toast.success(isSerialAct ? t.toast_act_done : t.toast_courrier_done);
    } catch (completeError) {
      console.error(completeError);
      toast.error(t.toast_finish_failed);
    } finally {
      setCompleting(false);
    }
  };

  const startFreshMission = async () => {
    setError(null);
    try {
      const next = await createSeededMission({
        conceptIds: seed.conceptIds,
        vocabularyIds: seed.vocabularyIds,
        erratumIds: seed.erratumIds,
      });
      if (!next) return;
      setCompletedNextSerial(null);
      toast.success(next.serial_thread_id ? t.toast_new_act : t.toast_new_courrier);
    } catch (createError) {
      console.error(createError);
      toast.error(t.toast_new_failed);
    }
  };

  const returnToAtelierHome = useCallback((event?: React.MouseEvent) => {
    event?.preventDefault();
    loadRequestRef.current += 1;
    void router.push('/atelier').catch(() => {
      window.location.assign('/atelier');
    });
  }, [router]);

  const kicker = deskKicker(mission, isSerialAct, actNumber, t);
  const statusLine = deskStatusLine(mission, format, completed, t);
  const memoRows: [string, string][] = [
    [t.memo_from, String(formatPayload.caller || messenger.contact_name)],
    [t.memo_channel, messenger.channel_label],
  ];
  const translateFrame = () => apiService.translateToEnglish([frame.frame, frame.ask].filter(Boolean).join(' '));
  const useQuickReply = (value: string) => {
    setReply(value);
    window.requestAnimationFrame(() => replyRef.current?.focus());
  };

  // Header line: "<cadence or act> · <mission title>" — the design's
  // "Mission de la semaine · résumer un titre".
  const deskLine = `${cadenceLabel || kicker} · ${missionTitle(mission)}`;
  const placedCount = ribbon.filter((word) => word.used).length;
  const deskChip = completed ? (
    <Chip className="cr-status" icon={<ShapeToken kind="done" size="sm" />}>{t.chip_done}</Chip>
  ) : ribbon.length > 0 ? (
    <Chip tone="reward" icon={<ShapeToken kind="done" size="sm" />}>
      {placedCount}/{ribbon.length}
      <span className="av2-sr"> {t.chip_placed_sr}</span>
    </Chip>
  ) : (
    <Chip tone="quiet" className="cr-status" icon={<ShapeToken kind="story" size="sm" />}>{statusLine}</Chip>
  );
  // The mic stands where the send press would be while there is nothing to
  // send (or while it is busy); with a draft the round red press becomes send.
  const showMic = isVoiceFormat && (reply.trim().length === 0 || micState !== 'idle');
  // The situation card already prints the ask; the composer only repeats an
  // instruction when it says something new (a format scaffold, a follow-up).
  const composerInstruction = turnComposerCopy.instruction && turnComposerCopy.instruction !== frame.ask
    ? turnComposerCopy.instruction
    : '';
  const recapTurns = Number(mission?.recap?.turns || 0);
  const recapErrata = Number(mission?.recap?.errata_logged || 0);
  const recapSaved = Number(mission?.recap?.saved_to_srs?.saved_count || 0);
  /* WP-65 — the correspondence. Every field is mirrored flat and inside
     `courrier`; both are read so a payload from either side of WP-64's deploy
     renders, and `outcome` is only ever in the block (the top-level key is the
     legacy serial state delta). */
  const courrier = mission?.courrier || null;
  const correspondent = mission?.correspondent || courrier?.correspondent || null;
  const chain = mission?.chain || courrier?.chain || null;
  const expiresAt = mission?.expires_at || courrier?.expires_at || null;
  const threadHistory = mission?.thread_history || courrier?.thread_history || [];
  const letterOutcome = courrier?.outcome || (mission?.recap as Record<string, any>)?.courrier_outcome || null;
  // `recap.measured` (mission-debrief-v2). Absent on a letter finished before
  // WP-64 shipped — those keep the three-count grid rather than losing it.
  const measured = (mission?.recap as Record<string, any>)?.measured as MissionMeasured | undefined;
  // Appendix A — the answered letter is ONE seal: the verdict, one sentence,
  // at most three counted numbers. The outcome's own sentence is chrome; a
  // letter with no outcome keeps its success line, which is the letter's
  // French. No credit rows, no debrief rows, no objectives, no last message.
  const outcomeSentence = crOutcomeSentence(letterOutcome, correspondent?.name, chromeLang);
  const sealVerdict = crOutcomeLabel(letterOutcome, chromeLang) || (isSerialAct ? t.seal_act_done : t.seal_resolved);
  const sealNumbers = crSealNumbers(measured, { turns: recapTurns, errata: recapErrata, saved: recapSaved }, chromeLang);
  // The correspondent's face on the seal, in the mood the letter left
  // (`recap.correspondent_mood_value_after`, or the legacy French line).
  const moodRecap = (mission?.recap || {}) as Record<string, any>;
  const moodKey = crMoodKey(crMoodValue(moodRecap.correspondent_mood_value_after, moodRecap.correspondent_mood_after));
  const moodName = String(correspondent?.name || '').trim();
  const sealMood = moodKey && moodName
    ? {
        name: moodName,
        characterId: castIdFor(mission?.prompt_payload?.serial_character_id, correspondent?.id, moodName),
        face: crMoodFace(moodKey),
        line: crMoodSentence(moodKey, moodName, t),
      }
    : null;
  // A because-line is chrome; the server sends it in all three languages.
  const reasonText = pickByLanguage(
    mission?.recommendation_reason?.text_by_language,
    chromeLang,
    String(mission?.recommendation_reason?.text || ''),
  );
  // WP-83: the composer opens itself once there is something in it.
  const composerOpen = reply.trim().length > 0 || micState !== 'idle';

  return (
    <>
      <Head>
        <title>
          {`${intakeMode ? t.documents_title : isSerialAct ? t.feuilleton : t.courrier} · L’Atelier`}
        </title>
      </Head>
      <AtelierV2Root
        as="main"
        language={chromeLang}
        className="cr motion"
        aria-label={intakeMode ? t.page_aria_intake : isSerialAct ? t.page_aria_act : t.courrier}
      >
        {intakeMode ? (
          /* WP-34's surface, mounted (WP-37 §2.1). Everything here already
             existed and was imported by no page: the components, the client
             calls and 82 backend tests. */
          <div className="cr-page">
            {/* WP-45: the desk's name and line said «Vos documents» twice, once
                here and once in the head the intake now carries from
                `Documents.dc.html`. What is left is the part the artboard does
                not draw and the screen still needs: the way back. */}
            <p className="cr-desk cr-desk--back">
              <Link
                className="av2-icon-btn cr-back"
                href="/atelier"
                onClick={returnToAtelierHome}
                aria-label={t.back_atelier}
                title={t.back_atelier}
              >
                <ArrowLeftIcon size={20} />
              </Link>
            </p>
            {intakeLoading && !intake ? (
              <div className="cr-skel" aria-busy="true" aria-live="polite">
                <span className="av2-sr">{t.loading_documents}</span>
                <Skeleton height={44} radius={999} />
                <Skeleton height={150} />
                <Skeleton height={72} />
              </div>
            ) : (
              <>
                <CrIntakeEntry
                  cap={intake?.cap}
                  onRead={(input) => { void readDocument(input); }}
                  reading={intakeReading}
                  error={intakeError}
                  onDismissError={() => setIntakeError(null)}
                />
                {(intake?.artefacts || []).map((artefact: IntakeArtefact) => (
                  <React.Fragment key={artefact.id}>
                    {artefact.status === 'read' ? (
                      <>
                        <CrArtefactCard
                          artefact={artefact}
                          onDelete={() => { void deleteDocument(artefact.id); }}
                          deleting={deletingArtefactId === artefact.id}
                        />
                        {/* The task is shown here and answered in the Courrier,
                            where the composer and the corrector already live.
                            No `onStart`, and no ghost row beneath it: WP-45 put
                            the way through — «Répondre à …» — inside the card
                            above, as `Documents.dc.html` draws it, and that is
                            this screen's one press. */}
                        <CrArtefactTaskCard task={artefact.task} />
                      </>
                    ) : (
                      <CrArtefactUnread
                        sourceKind={artefact.source_kind}
                        onDelete={() => { void deleteDocument(artefact.id); }}
                      />
                    )}
                  </React.Fragment>
                ))}
                {intake && intake.artefacts.length === 0 && (
                  <p className="cr-reason">{t.intake_empty}</p>
                )}
              </>
            )}
          </div>
        ) : loading && !mission ? (
          <div className="cr-page" aria-busy="true" aria-live="polite">
            <span className="av2-sr">{t.loading_courrier}</span>
            <div className="cr-skel">
              <Skeleton height={44} radius={999} />
              <Skeleton height={72} />
              <Skeleton height={56} />
              <Skeleton height={72} />
              <Skeleton height={50} />
            </div>
          </div>
        ) : error ? (
          <div className="cr-page cr-page--centre">
            <StateBlock
              tone="error"
              title={t.error_title}
              body={loadErrorMessage(error, t)}
              action={{ label: t.retry, onSelect: () => { void loadMission(); }, tone: 'primary' }}
            />
            <CrGhost href="/atelier" onClick={returnToAtelierHome}>{t.back_home}</CrGhost>
          </div>
        ) : !mission ? (
          <div className="cr-page cr-page--centre">
            <StateBlock
              tone="empty"
              title={t.empty_title}
              body={t.empty_body}
              action={{ label: t.back_home, onSelect: () => returnToAtelierHome(), tone: 'primary' }}
            />
            <CrIntakeLink />
          </div>
        ) : (
          <>
            <div className="cr-page">
              <CrDesk
                name={String(formatPayload.caller || messenger.contact_name)}
                line={deskLine}
                chip={deskChip}
                onBack={returnToAtelierHome}
              />
              {reasonText && <p className="cr-reason">{reasonText}</p>}

              {/* WP-65 — the correspondent view: who is writing, how they feel,
                  which letter of the affair this is, by when, and the letters
                  already exchanged with the same person over the weeks. It sits
                  above the situation because it is the context the situation is
                  in, and it renders nothing at all when the letter has nobody
                  behind it (a pre-WP-64 row, a serial act). */}
              <CrCorrespondent
                correspondent={correspondent}
                chain={chain}
                expiresAt={expiresAt}
                history={threadHistory}
                lapsed={lapsed}
                showMood={!completed}
              />

              {lapsed && <CrLapsedNotice name={correspondent?.name} />}

              {!completed && !lapsed && (
                <>
                  <CrSituation frame={frame.frame} ask={frame.ask} askLang={frame.askLang} translate={translateFrame} />
                  <CrRibbon words={ribbon} />
                </>
              )}

              <div className="cr-thread">
                {isVoiceFormat ? (
                  <CrMemo
                    rows={memoRows}
                    transcript={openingMessage}
                    stamp={interactionReady ? t.memo_answered : null}
                    translate={() => apiService.translateToEnglish(openingMessage)}
                  />
                ) : (
                  <CrSlip who={messenger.contact_name} translate={() => apiService.translateToEnglish(openingMessage)}>
                    {openingMessage}
                  </CrSlip>
                )}
                {!completed && <CrPS text={messenger.twist} />}

                {visibleTurns.map((turn) => {
                  const isUser = turn.role === 'user';
                  const correction = isUser ? (turn as Record<string, any>).correction : undefined;
                  const lines = repairLines(correction);
                  const correctedAnswer = correctedReply(correction, turn.text);
                  const savedCount = correctionPersistence(correction);
                  return (
                    <React.Fragment key={turn.id || `${turn.turn_index}-${turn.role}`}>
                      <CrSlip
                        who={isUser ? t.you : messenger.contact_name}
                        time={slipTime(turn)}
                        you={isUser}
                        sent={isUser}
                        translate={isUser ? undefined : () => apiService.translateToEnglish(String(turn.text || ''))}
                      >
                        {turn.text}
                      </CrSlip>
                      {/* WP-74: the corrector was unavailable. Not a pass, not a
                          fault — say plainly that nobody has corrected it yet. */}
                      {isUser && correction?.verdict === 'unassessed' && lines.length === 0 && !correctedAnswer && (
                        <p className="cr-unassessed" role="status">{t.unassessed}</p>
                      )}
                      {isUser && (lines.length > 0 || correctedAnswer) && (
                        <CrRepair
                          correctedAnswer={correctedAnswer}
                          lines={lines}
                          savedCount={savedCount}
                        />
                      )}
                    </React.Fragment>
                  );
                })}
                {submitting && (
                  <div className="cr-typing" role="status" aria-live="polite">
                    <span className="rollers" aria-hidden="true"><i /><i /><i /></span>
                    <span>{crFill(t.typing, { name: messenger.contact_name })}</span>
                  </div>
                )}
              </div>

              {/* WP-83: the composer sits in the flow right after the letter,
                  collapsed to one «Répondre» pill until the learner asks for
                  it — never sticky, never over the letter it answers. */}
              {!completed && !lapsed && (
                <CrComposer
                  quick={messenger.quick_replies}
                  onQuick={useQuickReply}
                  cta={submitLabel(format, t)}
                  onSubmit={sendReply}
                  sending={submitting}
                  canSubmit={canSend}
                  canFinish={interactionReady}
                  finishing={completing}
                  onFinish={finishMission}
                  open={composerOpen}
                  voice={showMic ? (
                    <CourrierMic
                      disabled={submitting}
                      onStateChange={setMicState}
                      onTranscript={(text) => setReply((current) => (current.trim() ? `${current.trim()} ${text}` : text))}
                    />
                  ) : undefined}
                >
                  <label className="av2-field">
                    <span className={format === 'chat_message' && !composerInstruction ? 'av2-sr' : 'av2-field__label'}>
                      {turnComposerCopy.label}
                    </span>
                    {composerInstruction && <p className="cr-instruction">{composerInstruction}</p>}
                    <textarea
                      ref={replyRef}
                      className={'av2-field__control cr-draft' + (format === 'email_formal' || format === 'admin_form' ? ' cr-draft--tall' : '')}
                      lang="fr"
                      autoCorrect="off"
                      autoCapitalize="off"
                      spellCheck={false}
                      rows={1}
                      value={reply}
                      onChange={(event) => setReply(event.target.value)}
                      placeholder={turnComposerCopy.placeholder || composerCopy.placeholder}
                      aria-label={turnComposerCopy.label}
                    />
                  </label>
                </CrComposer>
              )}

              {completed && (
                <section className="cr-resolve" aria-label={t.resolved_aria}>
                  <CrSeal
                    verdict={sealVerdict}
                    date={chromeDate(mission?.completed_at, t.locale)}
                    sentence={outcomeSentence || frame.ask}
                    sentenceLang={outcomeSentence ? undefined : frame.askLang}
                    mood={sealMood}
                    numbers={sealNumbers}
                    token={mintedToken ? <LogoToken pop /> : undefined}
                  />
                  {/* One 3D press per screen: the forward move. When the act
                      continues, that is the next act; otherwise the next
                      courrier. Everything else stays quiet. */}
                  <div className="cr-nexts">
                    {isSerialAct && completedNextSerial?.thread_id ? (
                      <CrGhost primary href={routeForMissionSerialBeat(completedNextSerial)}>{t.next_act}</CrGhost>
                    ) : (
                      <CrGhost primary onClick={startFreshMission} disabled={creating}>{t.new_courrier}</CrGhost>
                    )}
                    <CrGhost href="/atelier" onClick={returnToAtelierHome}>{t.back_atelier}</CrGhost>
                    {isSerialAct && completedNextSerial?.thread_id && (
                      <CrGhost quiet onClick={startFreshMission} disabled={creating}>{t.new_courrier}</CrGhost>
                    )}
                  </div>
                </section>
              )}

              {/* A lapsed letter has no composer, so it would otherwise be a
                  screen with no way forward. One quiet press, and it opens the
                  next letter rather than re-opening this one: the delay is
                  past, and offering a retry would be pretending it is not. */}
              {lapsed && (
                <div className="cr-nexts">
                  <CrGhost primary onClick={startFreshMission} disabled={creating}>{t.new_courrier}</CrGhost>
                  <CrGhost href="/atelier" onClick={returnToAtelierHome}>{t.back_atelier}</CrGhost>
                </div>
              )}

              {/* WP-37 §2.1: the Courrier's own way in to «Vos documents». A
                  row, not a press — the screen's press is the reply. */}
              <CrIntakeLink />

              {recentCompleted.length > 0 && (
                <section className="cr-archive" aria-label={t.archive_k}>
                  <p className="cr-archive-k">{t.archive_k}</p>
                  <ul>
                    {/* Filter before slicing, or the open courrier silently eats a row. */}
                    {recentCompleted.filter((past) => past.id !== mission?.id).slice(0, 8).map((past) => (
                      <li key={past.id}>
                        <Link className="cr-archive-row" href={{ pathname: '/missions', query: { mission: past.id } }}>
                          <b lang="fr">{missionTitle(past)}</b>
                          <span>
                            <ShapeToken kind={past.status === 'completed' ? 'done' : 'story'} size="sm" />
                            {archiveStatus(past, t)}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          </>
        )}
      </AtelierV2Root>
      <PhoneProductNav active="missions" />
      <CourrierStyles />
      <MissionsStageStyles />
    </>
  );
}

// The page ground behind the phone-shell `.av2.cr`; bottom-nav clearance is
// handled inside `.av2.cr` (see CourrierStyles).
function MissionsStageStyles() {
  return (
    <style jsx global>{`
      body { background: var(--app-paper); }
      .av2.cr { margin: 0 auto; }
    `}</style>
  );
}

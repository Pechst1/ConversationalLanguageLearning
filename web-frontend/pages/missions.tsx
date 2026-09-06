import React, { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { useRouter } from 'next/router';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import { LogoToken } from '@/components/ui/Seal';
import { LaUneStyles, LuNotice } from '@/components/laune/LaUne';
import {
  CourrierStyles,
  CrComposer,
  CrDesk,
  CrGhost,
  CrMemo,
  CrPS,
  CrRepair,
  CrRibbon,
  CrSituation,
  CrSlip,
  IcoBack,
  IcoMic,
  IcoStop,
} from '@/components/courrier/Courrier';
import apiService, { MissionToday, RealWorldMission, SerialToday } from '@/services/api';
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

function missionFrame(mission: RealWorldMission | null, messenger: MissionMessenger) {
  const slim = missionSlimPayload(mission);
  const frame = compactText(slim.frame || messenger.scene_anchor || mission?.brief, 210);
  const ask = compactText(slim.ask || messenger.dispatch_note || messenger.success_signal, 150);
  return { frame, ask };
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

function missionCadenceLabel(mission: RealWorldMission | null): string | null {
  const cadence = String(mission?.cadence || '');
  if (cadence === 'weekly') return 'Courrier de la semaine';
  if (cadence === 'post_session') return 'Après la séance';
  return null; // ad_hoc needs no marginal label
}

function formatComposerCopy(format: MissionFormat, writing: { title: string; instruction: string; placeholder: string }) {
  switch (format) {
    case 'email_formal':
      return {
        label: writing.title || 'Votre email',
        instruction: writing.instruction || 'Écrivez l’email avec un objet, une formule d’appel, le corps et une formule de politesse.',
        placeholder: writing.placeholder || 'Objet : ...\n\nMadame, Monsieur,\n...',
      };
    case 'admin_form':
      return {
        label: writing.title || 'Le formulaire',
        instruction: writing.instruction || 'Remplissez les champs en français, en phrases complètes là où c’est demandé.',
        placeholder: writing.placeholder || 'Nom :\nAdresse :\nDemande :',
      };
    case 'voicemail_reply':
      return { label: 'Votre message vocal', instruction: 'Répondez à l’oral — ou écrivez votre réponse.', placeholder: 'Parlez, ou écrivez ici…' };
    case 'phone_call':
      return { label: 'Au téléphone', instruction: 'Réponse courte et orale — parlez, ou écrivez.', placeholder: 'Parlez, ou écrivez ici…' };
    default:
      return { label: 'Votre dépêche', instruction: '', placeholder: 'Votre réponse en français…' };
  }
}

// The composer verb per artefact — the ink press-bar's French label.
function submitLabel(format: MissionFormat) {
  if (format === 'email_formal') return 'Envoyer l’email';
  if (format === 'admin_form') return 'Déposer';
  return 'Envoyer';
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
      label: 'Dernière réponse',
      instruction: 'La situation est comprise. Confirmez le dernier détail ou terminez la mission.',
      placeholder: 'Confirmez brièvement en français…',
    };
  }
  return {
    label: 'Votre réponse',
    instruction: assistantText
      ? `Dernier message : « ${assistantText} » Répondez à cette demande et faites avancer la situation.`
      : 'Répondez au dernier message et faites avancer la situation.',
    placeholder: 'Répondez au dernier message…',
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

function frenchDate(raw: string | null | undefined): string {
  const date = raw ? new Date(raw) : new Date();
  const safe = Number.isNaN(date.getTime()) ? new Date() : date;
  return new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long' }).format(safe);
}

// The kicker: a serial act flips to the blue "Le Feuilleton · Acte N" furniture.
function deskKicker(mission: RealWorldMission | null, isSerialAct: boolean, actNumber: number | null) {
  if (!isSerialAct) return 'Le Courrier';
  return actNumber != null ? `Le Feuilleton · Acte ${actNumber}` : 'Le Feuilleton';
}

// Status as printed marginalia (never a pill), in the fiction's French.
function deskStatusLine(mission: RealWorldMission | null, format: MissionFormat, completed: boolean): string {
  if (completed) return `Bouclé · ${frenchDate(mission?.completed_at)}`;
  if (mission?.status === 'in_progress') return 'En cours';
  if (format === 'email_formal') return 'Reçu · à rédiger';
  if (format === 'admin_form') return 'Dossier · à déposer';
  if (format === 'voicemail_reply') return 'Message reçu · à rappeler';
  if (format === 'phone_call') return 'Appel · ligne ouverte';
  return 'Reçu ce matin';
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
function loadErrorMessage(error: any): string {
  const detail = error?.response?.data?.detail;
  if (detail && typeof detail === 'object' && detail.code === 'serial_episode_not_ready') {
    return 'L’acte suivant n’est pas encore ouvert : lisez d’abord l’épisode en cours du Feuilleton.';
  }
  return 'Ce moment de mission n’a pas pu être ouvert.';
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

// Archive status in the fiction's French — printed as marginalia on each row.
function archiveStatus(mission: RealWorldMission | null) {
  if (!mission) return '';
  if (mission.status === 'completed') return 'Bouclé';
  if (mission.status === 'in_progress') return 'En cours';
  return 'À traiter';
}

// The credit rows on the resolved dossier. Every value maps to a recap field;
// rows only print when their number is real (no invented totals).
function resolutionCredit(mission: RealWorldMission | null, isSerialAct: boolean, hasNextAct: boolean) {
  const recap = (mission?.recap || {}) as Record<string, any>;
  const produced = Number(recap.vocabulary_credit?.produced_correct || 0);
  // The filed repairs, not the ones this page happened to print: the dossier and
  // the per-message cards must not quote two different totals for one thing.
  const repairs = missionTurns(mission).reduce(
    (total, turn) => total + correctionPersistence((turn as Record<string, any>).correction),
    0,
  );
  const rows: { label: string; value: string }[] = [];
  if (produced > 0) rows.push({ label: 'Lexique crédité', value: `${produced} mot${produced === 1 ? '' : 's'}` });
  if (repairs > 0) rows.push({ label: 'Réparations', value: `${repairs} enregistrée${repairs === 1 ? '' : 's'}` });
  if (isSerialAct && hasNextAct) rows.push({ label: 'Feuilleton', value: 'Acte suivant' });
  return rows;
}

// Records a spoken reply and transcribes it via /missions/audio/transcribe,
// then hands the text back to the composer. Used for voicemail/phone formats.
// Styled as the design's "cr-mic" bar (idle / recording / transcribing).
function CourrierMic({ onTranscript, disabled }: { onTranscript: (text: string) => void; disabled?: boolean }) {
  const [state, setState] = useState<'idle' | 'recording' | 'transcribing'>('idle');
  const [problem, setProblem] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearTimer = () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };
  useEffect(() => () => clearTimer(), []);

  const start = async () => {
    setProblem(null);
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setProblem('Le micro n’est pas disponible ici.');
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
          else setProblem('Rien n’a été transcrit — réessayez.');
        } catch (transcribeError) {
          console.error(transcribeError);
          setProblem('La transcription a échoué — réessayez, ou écrivez votre réponse.');
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
      setProblem('Micro refusé — autorisez l’accès, ou écrivez votre réponse.');
      setState('idle');
    }
  };

  const stop = () => {
    if (recorderRef.current && state === 'recording') recorderRef.current.stop();
  };

  const timer = `${Math.floor(seconds / 60)} : ${String(seconds % 60).padStart(2, '0')}`;

  return (
    <div className="cr-mic">
      {state === 'transcribing' ? (
        <div className="cr-transcribe">
          Transcription en cours
          <span className="rollers" aria-hidden="true"><i /><i /><i /></span>
        </div>
      ) : (
        <button
          type="button"
          className={`bar ${state === 'recording' ? 'rec' : 'idle'}`}
          onClick={state === 'recording' ? stop : start}
          disabled={disabled}
          aria-label={state === 'recording' ? 'Arrêter l’enregistrement' : 'Enregistrer une réponse vocale'}
        >
          {state === 'recording' ? (
            <>
              <span className="wave" aria-hidden="true"><i /><i /><i /><i /><i /></span>
              <span className="timer">{timer}</span>
              <IcoStop />
            </>
          ) : (
            <><IcoMic /> Parler</>
          )}
        </button>
      )}
      {problem && <span className="cr-mic-problem" role="status">{problem}</span>}
    </div>
  );
}

export default function MissionsPage() {
  const router = useRouter();
  const [today, setToday] = useState<MissionToday | null>(null);
  const [mission, setMission] = useState<RealWorldMission | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState('');
  const [completedNextSerial, setCompletedNextSerial] = useState<SerialToday | null>(null);
  const loadRequestRef = useRef(0);
  const replyRef = useRef<HTMLTextAreaElement | null>(null);

  const seed = useMemo(() => querySeed(router.query as Record<string, string | string[] | undefined>), [router.query]);
  const messenger = useMemo(() => missionMessenger(mission), [mission]);
  const frame = useMemo(() => missionFrame(mission, messenger), [mission, messenger]);
  const turns = useMemo(() => missionTurns(mission), [mission]);
  const ribbon = useMemo(() => ribbonWords(mission), [mission]);
  const isSerialAct = Boolean(mission?.serial_thread_id || seed.serialThreadId);
  const completed = mission?.status === 'completed';
  const interactionReady = hasInteraction(mission);
  const canSend = reply.trim().length > 0 && !submitting && !completed;
  const format = useMemo(() => missionFormat(mission), [mission]);
  const writing = useMemo(() => missionWriting(mission), [mission]);
  const formatPayload = useMemo(() => missionFormatPayload(mission), [mission]);
  const composerCopy = useMemo(() => formatComposerCopy(format, writing), [format, writing]);
  const turnComposerCopy = useMemo(
    () => currentComposerInstruction(
      mission,
      {
        ...composerCopy,
        instruction: composerCopy.instruction || frame.ask,
      },
    ),
    [composerCopy, frame.ask, mission],
  );
  const cadenceLabel = missionCadenceLabel(mission);
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
      setError(loadErrorMessage(loadError));
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, [createSeededMission, routeToMission, router.isReady, router.pathname, seed]);

  useEffect(() => {
    void loadMission();
    return () => {
      loadRequestRef.current += 1;
    };
  }, [loadMission]);

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
      toast.error('Le message n’est pas parti.');
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
      toast.success(isSerialAct ? 'Acte bouclé' : 'Courrier bouclé');
    } catch (completeError) {
      console.error(completeError);
      toast.error('Ce moment n’a pas pu être terminé.');
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
      toast.success(next.serial_thread_id ? 'Nouvel acte ouvert' : 'Nouveau courrier ouvert');
    } catch (createError) {
      console.error(createError);
      toast.error('Le nouveau moment n’a pas pu être créé.');
    }
  };

  const returnToAtelierHome = useCallback((event: React.MouseEvent) => {
    event.preventDefault();
    loadRequestRef.current += 1;
    void router.push('/atelier').catch(() => {
      window.location.assign('/atelier');
    });
  }, [router]);

  const kicker = deskKicker(mission, isSerialAct, actNumber);
  const statusLine = deskStatusLine(mission, format, completed);
  const nextBest = mission?.recap?.branch_outcome?.next_best_move || latestAssistantReply(mission) || null;
  const creditRows = completed
    ? resolutionCredit(mission, isSerialAct, Boolean(completedNextSerial?.thread_id))
    : [];
  const memoRows: [string, string][] = [
    ['De la part de', String(formatPayload.caller || messenger.contact_name)],
    ['Canal', messenger.channel_label],
  ];
  const translateFrame = () => apiService.translateToEnglish([frame.frame, frame.ask].filter(Boolean).join(' '));
  const useQuickReply = (value: string) => {
    setReply(value);
    window.requestAnimationFrame(() => replyRef.current?.focus());
  };

  return (
    <>
      <Head>
        <title>{isSerialAct ? 'Le Feuilleton · Acte' : 'Le Courrier'} · L’Atelier</title>
      </Head>
      <main className="cr-stage">
        <div className="cr motion" aria-label={isSerialAct ? 'Le Feuilleton · acte' : 'Le Courrier'}>
          {loading && !mission ? (
            <div className="cr-page">
              <div className="cr-skel" aria-hidden="true">
                <div className="slipph" />
                <div className="slipph you" />
                <div className="slipph" />
                <div className="barph" />
              </div>
            </div>
          ) : error ? (
            <div className="cr-page">
              <CrDesk
                kicker="Le Courrier"
                title="Le courrier du jour"
                statusLine="Distribution interrompue"
                onBack={returnToAtelierHome}
              />
              <LuNotice tone="red" label="Courrier égaré" message={error} onRetry={loadMission} />
            </div>
          ) : !mission ? (
            <div className="cr-page cr-empty-page">
              <div className="cr-empty">
                <div className="rubric">Le Courrier</div>
                <div className="endmark" />
                <h2>Aucun courrier — la Une vous attend.</h2>
                <p>Le facteur repassera avec l’édition de demain.</p>
                <div>
                  <Link className="free" href="/atelier" onClick={returnToAtelierHome}><IcoBack /> Retour à la Une</Link>
                </div>
              </div>
            </div>
          ) : (
            <>
              <div className="cr-page">
                <CrDesk
                  kicker={kicker}
                  blue={isSerialAct}
                  title={missionTitle(mission)}
                  cadence={cadenceLabel}
                  status={completed ? 'done' : 'open'}
                  statusLine={statusLine}
                  onBack={returnToAtelierHome}
                />
                {mission.recommendation_reason?.text && (
                  <p className="cr-reason">{mission.recommendation_reason.text}</p>
                )}

                {!completed && (
                  <>
                    <CrSituation frame={frame.frame} ask={frame.ask} translate={translateFrame} />
                    <CrPS text={messenger.twist} />
                    <CrRibbon words={ribbon} />
                  </>
                )}

                <div className="cr-thread">
                  {isVoiceFormat ? (
                    <CrMemo
                      rows={memoRows}
                      transcript={openingMessage}
                      stamp={interactionReady ? 'Répondu' : null}
                      translate={() => apiService.translateToEnglish(openingMessage)}
                    />
                  ) : (
                    <CrSlip who={messenger.contact_name} translate={() => apiService.translateToEnglish(openingMessage)}>
                      {openingMessage}
                    </CrSlip>
                  )}

                  {visibleTurns.map((turn) => {
                    const isUser = turn.role === 'user';
                    const correction = isUser ? (turn as Record<string, any>).correction : undefined;
                    const lines = repairLines(correction);
                    const correctedAnswer = correctedReply(correction, turn.text);
                    const savedCount = correctionPersistence(correction);
                    return (
                      <React.Fragment key={turn.id || `${turn.turn_index}-${turn.role}`}>
                        <CrSlip
                          who={isUser ? 'Vous' : messenger.contact_name}
                          time={slipTime(turn)}
                          you={isUser}
                          sent={isUser}
                          translate={isUser ? undefined : () => apiService.translateToEnglish(String(turn.text || ''))}
                        >
                          {turn.text}
                        </CrSlip>
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
                      <span>{messenger.contact_name} rédige sa réponse</span>
                    </div>
                  )}
                </div>

                {completed && (
                  <div className="cr-resolve" aria-label="Dossier résolu">
                    <div className="cr-resolve-kicker">Compte rendu de mission</div>
                    <span className="lu-stamp big" style={{ '--tilt': '-5deg' } as React.CSSProperties}>
                      {isSerialAct ? 'Acte bouclé' : 'Résolu'}
                      <span className="d">{frenchDate(mission?.completed_at)}</span>
                    </span>
                    <p className="sub">{messenger.success_signal}</p>
                    {mintedToken && (
                      <>
                        <div className="tok-stage"><LogoToken pop /></div>
                        <div className="earned">Jeton frappé</div>
                      </>
                    )}
                    {creditRows.length > 0 && (
                      <div className="cr-credit">
                        {creditRows.map((row) => (
                          <div className="row" key={row.label}>
                            <span>{row.label}</span>
                            <b>{row.value}</b>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="cr-recap-grid">
                      <div>
                        <strong>{Number(mission.recap?.turns || 0)}</strong>
                        <span>réponse{Number(mission.recap?.turns || 0) === 1 ? '' : 's'}</span>
                      </div>
                      <div>
                        <strong>{Number(mission.recap?.errata_logged || 0)}</strong>
                        <span>erreur{Number(mission.recap?.errata_logged || 0) === 1 ? '' : 's'} repérée{Number(mission.recap?.errata_logged || 0) === 1 ? '' : 's'}</span>
                      </div>
                      <div>
                        <strong>{Number(mission.recap?.saved_to_srs?.saved_count || 0)}</strong>
                        <span>phrase{Number(mission.recap?.saved_to_srs?.saved_count || 0) === 1 ? '' : 's'} sauvegardée{Number(mission.recap?.saved_to_srs?.saved_count || 0) === 1 ? '' : 's'}</span>
                      </div>
                    </div>
                    {mission.recap?.readiness && (
                      <div className="cr-readiness">
                        <span>Prêt pour la vraie vie</span>
                        <strong>{Number(mission.recap.readiness.overall || 0)}%</strong>
                      </div>
                    )}
                    {Array.isArray(mission.recap?.objective_results) && mission.recap.objective_results.length > 0 && (
                      <div className="cr-objectives" aria-label="Objectifs de mission">
                        <span className="k">Objectifs</span>
                        {mission.recap.objective_results.map((objective: Record<string, any>, index: number) => (
                          <div className={objective.met ? 'met' : 'open'} key={String(objective.id || index)}>
                            <span aria-hidden="true">{objective.met ? '✓' : '○'}</span>
                            <b>{String(objective.label || 'Objectif de mission')}</b>
                          </div>
                        ))}
                      </div>
                    )}
                    {nextBest && <p className="sub" style={{ maxWidth: 300 }}>{nextBest}</p>}
                    {/* One primary action per screen: the forward move. When the act
                        continues, that is the next act; otherwise it is the next
                        courrier. Everything else stays a quiet ghost. */}
                    <div className="cr-nexts">
                      {isSerialAct && completedNextSerial?.thread_id ? (
                        <CrGhost primary href={routeForMissionSerialBeat(completedNextSerial)}>Lire l’acte suivant</CrGhost>
                      ) : (
                        <CrGhost primary onClick={startFreshMission} disabled={creating}>Nouveau courrier</CrGhost>
                      )}
                      <CrGhost href="/atelier" onClick={returnToAtelierHome}>Retour à l’Atelier</CrGhost>
                      {isSerialAct && completedNextSerial?.thread_id && (
                        <CrGhost quiet onClick={startFreshMission} disabled={creating}>Nouveau courrier</CrGhost>
                      )}
                    </div>
                  </div>
                )}

                {recentCompleted.length > 0 && (
                  <section className="cr-archive" aria-label="Courrier passé">
                    <span className="k">Courrier passé</span>
                    <ul>
                      {/* Filter before slicing, or the open courrier silently eats a row. */}
                      {recentCompleted.filter((past) => past.id !== mission?.id).slice(0, 8).map((past) => (
                        <li key={past.id}>
                          <Link href={{ pathname: '/missions', query: { mission: past.id } }}>
                            <b>{missionTitle(past)}</b>
                            <span>{archiveStatus(past)}</span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </div>

              {!completed && (
                <CrComposer
                  quick={messenger.quick_replies}
                  onQuick={useQuickReply}
                  cta={submitLabel(format)}
                  onSubmit={sendReply}
                  sending={submitting}
                  canSubmit={canSend}
                  canFinish={interactionReady}
                  finishing={completing}
                  onFinish={finishMission}
                  finishLabel="Terminer"
                >
                  {(turnComposerCopy.label || turnComposerCopy.instruction) && (
                    <>
                      <span className="cr-label">{turnComposerCopy.label}</span>
                      {turnComposerCopy.instruction && <p className="cr-instruction">{turnComposerCopy.instruction}</p>}
                    </>
                  )}
                  {isVoiceFormat && (
                    <CourrierMic
                      disabled={submitting}
                      onTranscript={(text) => setReply((current) => (current.trim() ? `${current.trim()} ${text}` : text))}
                    />
                  )}
                  <textarea
                    ref={replyRef}
                    className={'cr-draft' + (format === 'email_formal' || format === 'admin_form' ? ' tall' : '')}
                    value={reply}
                    onChange={(event) => setReply(event.target.value)}
                    placeholder={turnComposerCopy.placeholder || composerCopy.placeholder}
                    aria-label={turnComposerCopy.label}
                  />
                </CrComposer>
              )}
            </>
          )}
        </div>
      </main>
      <PhoneProductNav active="missions" />
      <LaUneStyles />
      <CourrierStyles />
      <MissionsStageStyles />
    </>
  );
}

// The stage centres the phone-shell `.cr` and paints the theme-aware paper
// behind it. Bottom nav clearance is handled inside `.cr` (see CourrierStyles).
function MissionsStageStyles() {
  return (
    <style jsx global>{`
      .cr-stage {
        min-height: 100svh;
        display: grid;
        justify-items: center;
        align-items: start;
        background: var(--app-paper);
      }
      .cr .cr-empty-page {
        display: flex;
        flex-direction: column;
        justify-content: center;
        flex: 1 1 auto;
      }
      .cr .cr-reason { margin: 8px var(--cr-pad, 18px) 18px; color: var(--app-ink-3); font: italic 12px/1.4 var(--app-serif); }
    `}</style>
  );
}

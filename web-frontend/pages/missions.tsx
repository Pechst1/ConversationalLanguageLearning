import React, { useEffect, useMemo, useRef, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  ArrowRight,
  Check,
  ClipboardList,
  Clock3,
  Loader2,
  MapPinned,
  Mic,
  Play,
  Send,
  Sparkles,
  Square,
  Upload,
} from 'lucide-react';
import toast from 'react-hot-toast';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import api, { MissionToday, RealWorldMission } from '@/services/api';

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
  preferred_concept_ids?: number[];
  preferred_errata_ids?: string[];
  use_news?: boolean;
  custom_scenario?: string;
  desired_outcome?: string;
  relationship?: string;
  register?: string;
};

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

function latestCorrection(mission: RealWorldMission | null): Record<string, any> | null {
  if (!mission) return null;
  const attempt = (mission.attempts || []).slice(-1)[0];
  const userTurn = (mission.turns || []).filter((turn) => turn.role === 'user').slice(-1)[0];
  return userTurn?.correction || attempt?.correction || null;
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

function missionStatusLabel(status?: string) {
  if (!status) return 'ready';
  return status.replace('_', ' ');
}

function sourceCard(mission: RealWorldMission | null): Record<string, any> {
  return mission?.prompt_payload?.source_context_card || {};
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
  const [writingText, setWritingText] = useState('');
  const [turnText, setTurnText] = useState('');
  const [turnMode, setTurnMode] = useState<'chat' | 'voice'>('chat');
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [submittingWriting, setSubmittingWriting] = useState(false);
  const [submittingTurn, setSubmittingTurn] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const queryHandledRef = useRef(false);

  const correction = useMemo(() => latestCorrection(mission), [mission]);
  const messenger = useMemo(() => getMessenger(mission), [mission]);

  function syncTodayMission(next: RealWorldMission) {
    setToday((current) => {
      if (!current) return current;
      const replace = (item: RealWorldMission | null) => item?.id === next.id ? next : item;
      return {
        weekly_mission: replace(current.weekly_mission),
        post_session_recommendation: replace(current.post_session_recommendation),
        active_mission: next.status === 'in_progress' ? next : replace(current.active_mission),
        recent_completed: (current.recent_completed || []).map((item) => item.id === next.id ? next : item),
      };
    });
  }

  async function loadToday() {
    setLoading(true);
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
      toast.error('Could not load missions.');
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
    const atelierSessionId = typeof router.query.atelier_session_id === 'string' ? router.query.atelier_session_id : null;
    const conceptQuery = router.query.concept_id;
    const conceptIds = (Array.isArray(conceptQuery) ? conceptQuery : conceptQuery ? [conceptQuery] : [])
      .map((item) => Number(item))
      .filter((item) => Number.isFinite(item));
    const erratumId = typeof router.query.erratum_id === 'string' ? router.query.erratum_id : null;
    if (!atelierSessionId && !conceptIds.length && !erratumId) return;
    queryHandledRef.current = true;
    void createMission({
      cadence: atelierSessionId ? 'post_session' : 'ad_hoc',
      atelier_session_id: atelierSessionId || undefined,
      preferred_concept_ids: conceptIds.length ? conceptIds : undefined,
      preferred_errata_ids: erratumId ? [erratumId] : undefined,
      use_news: false,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.isReady, router.query.atelier_session_id, router.query.concept_id, router.query.erratum_id]);

  async function createMission(extra?: CreateMissionOptions) {
    setCreating(true);
    try {
      const nextType = extra?.mission_type || missionType;
      const next = await api.createMission({
        mission_type: nextType,
        cadence: extra?.cadence || 'ad_hoc',
        use_news: extra?.use_news ?? nextType === 'news_summary',
        atelier_session_id: extra?.atelier_session_id,
        preferred_concept_ids: extra?.preferred_concept_ids,
        preferred_errata_ids: extra?.preferred_errata_ids,
        custom_scenario: extra?.custom_scenario,
        desired_outcome: extra?.desired_outcome,
        relationship: extra?.relationship,
        register: extra?.register,
      });
      setMission(next);
      setWritingText('');
      setTurnText('');
      setTurnMode('chat');
      setMicError(null);
      if (extra?.custom_scenario) {
        setCustomScenario('');
        setCustomOutcome('');
        setCustomRelationship('');
        setCustomRegister('polite neutral');
      }
      router.replace({ pathname: '/missions', query: { mission: next.id } }, undefined, { shallow: true });
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

  async function submitTurn(mode: 'chat' | 'voice' = 'chat') {
    if (!mission || !turnText.trim()) return;
    setSubmittingTurn(true);
    try {
      const result = await api.submitMissionTurn(mission.id, { text: turnText, mode });
      setMission(result.mission);
      syncTodayMission(result.mission);
      setTurnText('');
      setTurnMode('chat');
    } catch (error) {
      console.error(error);
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
      const nextToday = await api.getMissionsToday();
      setToday(nextToday);
      setMission(result.mission);
      toast.success('Mission completed.');
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
        setMicError(null);
      } else {
        toast('No speech detected.');
      }
    } catch (error) {
      console.error(error);
      toast.error('Could not transcribe this recording.');
    } finally {
      setTranscribing(false);
    }
  }

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia) {
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
        <EditorialMasthead active="missions" />

        <div className="mission-spread page-grid">
          <section className="mission-main">
            <div className="mission-title">
              <div>
                <div className="t-mono">REAL-WORLD FIELD LOOP</div>
                <h1>Missions</h1>
              </div>
              <div className="mission-builder">
                <select value={missionType} onChange={(event) => setMissionType(event.target.value)} aria-label="Mission type">
                  {missionTypes.map((type) => <option key={type.id} value={type.id}>{type.label}</option>)}
                </select>
                <button className="btn red" disabled={creating} onClick={() => createMission({ cadence: 'ad_hoc' })}>
                  {creating ? <Loader2 className="spin" size={14} /> : <Sparkles size={14} />}
                  {creating ? 'CREATING' : 'NEW MISSION'} <ArrowRight size={14} />
                </button>
              </div>
            </div>

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
              <div className="paper loading"><Loader2 className="spin" /> LOADING MISSIONS</div>
            ) : mission ? (
              <>
                <MissionPassport mission={mission} messenger={messenger} />
                <RealityMessenger
                  mission={mission}
                  messenger={messenger}
                  turnText={turnText}
                  setTurnText={(value) => {
                    setTurnText(value);
                    setTurnMode('chat');
                  }}
                  submitting={submittingTurn}
                  recording={recording}
                  transcribing={transcribing}
                  playing={playing}
                  micError={micError}
                  onSubmitTurn={() => submitTurn(turnMode)}
                  onRecord={() => recording ? stopRecording() : void startRecording()}
                  onUploadAudio={uploadAudioFile}
                  onPlay={playLastAssistant}
                />
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
                  <Link className="btn" href={`/graphic-novel?mission_id=${mission.id}`}>
                    MAKE FEUILLETON <ArrowRight size={14} />
                  </Link>
                  <button className="btn solid lg" disabled={completing || mission.status === 'completed'} onClick={completeMission}>
                    {mission.status === 'completed' ? 'MISSION COMPLETE' : 'COMPLETE MISSION'} <Check size={15} />
                  </button>
                </div>
              </>
            ) : (
              <div className="paper empty-state">No mission is available yet.</div>
            )}
          </section>

          <aside className="mission-side">
            <MissionChooser today={today} selectedId={mission?.id} onSelect={selectMission} />
            <SceneLens mission={mission} messenger={messenger} />
            <Objectives mission={mission} correction={correction} />
            <CorrectionStack correction={correction} />
          </aside>
        </div>
      </main>
    </>
  );
}

function MissionPassport({ mission, messenger }: { mission: RealWorldMission; messenger: MissionMessenger }) {
  return (
    <section className="paper mission-passport">
      <CropMarks />
      <div className="passport-grid">
        <div>
          <div className="mission-kicker">
            <span>{missionTypeLabel(mission.mission_type)}</span>
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
  return (
    <section className="paper custom-composer">
      <div className="composer-copy">
        <div className="t-mono">CUSTOM REALITY MISSION</div>
        <h2>Bring the thing you actually need to say.</h2>
        <p>Use the exact situation, person, outcome, and tone you need outside the app.</p>
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
  setTurnText,
  submitting,
  recording,
  transcribing,
  playing,
  micError,
  onSubmitTurn,
  onRecord,
  onUploadAudio,
  onPlay,
}: {
  mission: RealWorldMission;
  messenger: MissionMessenger;
  turnText: string;
  setTurnText: (value: string) => void;
  submitting: boolean;
  recording: boolean;
  transcribing: boolean;
  playing: boolean;
  micError: string | null;
  onSubmitTurn: () => void;
  onRecord: () => void;
  onUploadAudio: (file?: File | null) => void;
  onPlay: () => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
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

  return (
    <section className="paper messenger-workspace">
      <div className="workspace-head">
        <div>
          <div className="t-mono">REALITY MESSENGER</div>
          <h3>{messenger.thread_title}</h3>
        </div>
        <button className="btn ghost" disabled={!canPlay || playing} onClick={onPlay}>
          {playing ? 'PLAYING' : 'PLAY LAST'} <Play size={13} />
        </button>
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
            <div className="message-list">
              {visibleTurns.map((turn, index) => (
                <MessageBubble key={turn.id || `${turn.role}-${index}`} turn={turn} />
              ))}
            </div>
            <div className="phone-composer">
              <textarea
                value={turnText}
                onChange={(event) => setTurnText(event.target.value)}
                disabled={isClosed}
                placeholder="Write the next French message..."
              />
              <button className="send-dot" disabled={submitting || transcribing || recording || !turnText.trim() || isClosed} onClick={onSubmitTurn} aria-label="Send message">
                {submitting ? <Loader2 className="spin" size={15} /> : <Send size={15} />}
              </button>
            </div>
          </div>
        </div>

        <div className="thread-tools">
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
    </section>
  );
}

function MessageBubble({ turn }: { turn: Record<string, any> }) {
  const isUser = turn.role === 'user';
  const correction = turn.correction || {};
  const branch = turn.audio_payload?.branch;
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
        {isUser && correction.verdict && (
          <small className={`turn-verdict ${correction.verdict === 'accepted' ? 'accepted' : ''}`}>
            {correction.verdict} · {correction.score_0_4 ?? 0}/4
          </small>
        )}
      </div>
    </div>
  );
}

function MissionDebrief({ mission }: { mission: RealWorldMission }) {
  const recap = mission.recap || {};
  const readiness = recap.readiness || null;
  const saved = recap.saved_to_srs?.phrase_bank || [];
  const branch = recap.branch_outcome || null;
  if (mission.status !== 'completed' || !readiness) return null;
  return (
    <section className="paper debrief-panel">
      <div className="workspace-head">
        <div>
          <div className="t-mono">MISSION DEBRIEF</div>
          <h3>{branch?.label || 'Real-world readiness'}</h3>
        </div>
        <div className="readiness-score">
          <span>{readiness.overall}</span>
          <small>ready</small>
        </div>
      </div>
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
          {submitting ? 'REVIEWING' : 'REVIEW DISPATCH'} <Send size={14} />
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
  const missions = [
    today?.active_mission && { label: 'Active', mission: today.active_mission },
    today?.post_session_recommendation && { label: 'Post-session', mission: today.post_session_recommendation },
    today?.weekly_mission && { label: 'Weekly', mission: today.weekly_mission },
    ...(today?.recent_completed || []).slice(0, 2).map((mission) => ({ label: 'Done', mission })),
  ].filter(Boolean) as Array<{ label: string; mission: RealWorldMission }>;
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
          <small>{missionStatusLabel(mission.status)} · {missionTypeLabel(mission.mission_type)}</small>
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
  const objectives = (mission?.objectives || []).filter(
    (objective) => mission?.mission_type === 'news_summary' || objective.kind !== 'source',
  );
  return (
    <section className="paper objectives">
      <header>
        <span className="t-mono">OBJECTIVES</span>
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
  const errata = correction?.errata || [];
  return (
    <section className="correction-stack">
      <div className="between">
        <span className="t-mono">LIVE REPAIR</span>
        <span className="t-mono-low">{errata.length}</span>
      </div>
      {!correction && (
        <div className="empty-slip">Send a message or review a dispatch to see targeted repairs.</div>
      )}
      {correction && (
        <article className="paper correction-summary">
          <h3>{correction.verdict}</h3>
          <p>Score {correction.score_0_4}/4</p>
          {correction.corrected_answer && <small>{correction.corrected_answer}</small>}
          {correction.missing_targets?.length > 0 && (
            <p>{correction.missing_targets.length} target still missing.</p>
          )}
        </article>
      )}
      {errata.slice(0, 5).map((item: any, index: number) => (
        <article key={`${item.display_label}-${index}`} className="errata-slip">
          <span className="slip-label">{item.display_label}</span>
          <span className="slip-num">NO. {String(index + 1).padStart(2, '0')}</span>
          <div className="t-mono-low">YOU WROTE</div>
          <p className="wrong">{item.learner_text}</p>
          <div className="t-mono-low red">CORRECTED</div>
          <p className="right">{item.corrected_target}</p>
          <div className="why">
            <p><strong>Why.</strong> {item.why_wrong}</p>
            <p><strong>Repair.</strong> {item.repair_hint}</p>
          </div>
          {item.concept_id && <Link className="notebook-link" href={`/grammar?concept=${item.concept_id}`}>Review rule</Link>}
        </article>
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
      .mission-spread { width: min(1360px, 100%); margin: 0 auto; padding: 0 clamp(18px, 4vw, 48px); }
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
      .mission-builder select { min-height: 46px; border: 1px solid var(--ink) !important; background: var(--paper); padding: 0 12px; font-weight: 800; box-shadow: 4px 4px 0 var(--ink) !important; }
      .paper { background: var(--paper-2); border: 2px solid var(--ink); position: relative; }
      .loading, .empty-state { min-height: 240px; display: grid; place-items: center; gap: 10px; font-size: 10px; letter-spacing: .14em; font-weight: 900; text-transform: uppercase; }
      .btn { display: inline-flex; align-items: center; justify-content: center; gap: 9px; min-height: 42px; padding: 0 18px; border: 1px solid var(--ink); background: var(--paper); transition: .12s ease; white-space: nowrap; }
      .btn:hover:not(:disabled) { background: var(--ink); color: var(--paper); }
      .btn:disabled { opacity: .45; cursor: not-allowed; }
      .btn.red { background: var(--red); border-color: var(--red); color: var(--paper); }
      .btn.solid { background: var(--ink); color: var(--paper); }
      .btn.solid.recording { background: var(--red); border-color: var(--red); }
      .btn.ghost { border-color: transparent; padding-inline: 10px; background: transparent; }
      .btn.lg { min-height: 56px; padding-inline: 28px; }
      .custom-composer { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 22px; padding: 22px; background: var(--paper-2); }
      .composer-copy { border-right: 2px solid var(--ink); padding-right: 22px; }
      .composer-copy h2 { margin: 8px 0 0; font-size: 24px; line-height: 1; letter-spacing: 0; }
      .composer-copy p { margin: 10px 0 0; color: var(--ink-2); line-height: 1.4; }
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
      .workspace-head { display: flex; justify-content: space-between; gap: 20px; align-items: start; border-bottom: 2px solid var(--ink); padding-bottom: 14px; }
      .workspace-head h3 { margin: 6px 0 0; font-size: clamp(23px, 3vw, 32px); line-height: 1; letter-spacing: 0; font-weight: 900; }
      .messenger-workspace, .dispatch-draft { padding: 24px 28px; background: var(--paper); display: grid; gap: 18px; }
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
      .turn-verdict { display: inline-flex; margin-top: 7px; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.38); padding: 3px 6px; font-size: 10px; text-transform: uppercase; letter-spacing: .05em; }
      .turn-verdict.accepted { background: rgba(28,124,84,.9); border-color: rgba(255,255,255,.5); }
      .branch-chip { display: inline-flex; margin-top: 7px; border: 1px solid rgba(20,17,13,.2); background: rgba(243,195,24,.35); padding: 4px 7px; font-size: 10px; font-weight: 900; line-height: 1.15; text-transform: uppercase; letter-spacing: .05em; }
      .branch-chip.understood { background: rgba(28,124,84,.16); color: var(--green); }
      .branch-chip.tone_mismatch, .branch-chip.needs_detail, .branch-chip.missing_next_step { background: rgba(216,50,26,.12); color: var(--red); }
      .phone-composer { display: grid; grid-template-columns: 1fr 42px; gap: 8px; align-items: end; padding: 12px; background: #fbf8f0; border-top: 1px solid rgba(20,17,13,.14); }
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
      .voice-warning { margin: 0; border-left: 4px solid var(--red); padding: 8px 12px; background: var(--paper-2); color: var(--ink-2); line-height: 1.35; }
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
      @media (max-width: 1120px) {
        .page-grid { grid-template-columns: 1fr; }
        .mission-side { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
      @media (max-width: 860px) {
        .mission-title, .workspace-head, .masthead-inner, .passport-grid, .messenger-grid, .custom-composer { grid-template-columns: 1fr; align-items: flex-start; flex-direction: column; }
        .composer-copy { border-right: 0; border-bottom: 2px solid var(--ink); padding-right: 0; padding-bottom: 16px; }
        .composer-row, .readiness-grid { grid-template-columns: 1fr; }
        .mission-builder { width: 100%; flex-direction: column; align-items: stretch; }
        .mission-builder .btn, .mission-builder select { width: 100%; }
        .mission-side { grid-template-columns: 1fr; }
        .phone-shell { min-height: 560px; box-shadow: 6px 6px 0 var(--ink); }
        .phone-screen { min-height: 536px; }
        .message-list { max-height: 340px; }
        .cue-grid { grid-template-columns: 1fr; }
      }
      @media (max-width: 560px) {
        .mission-spread { padding-inline: 14px; }
        .missions-masthead nav { gap: 12px; }
        .mission-passport, .messenger-workspace, .dispatch-draft { padding: 20px 18px; }
        .phone-shell { border-radius: 22px; padding: 8px; }
        .phone-screen { border-radius: 16px; }
        .message-bubble-real { max-width: 90%; }
        .complete-row, .draft-footer, .action-row { align-items: stretch; flex-direction: column; }
        .complete-row .btn, .draft-footer .btn, .action-row .btn { width: 100%; }
      }
    `}</style>
  );
}

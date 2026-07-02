import React, { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Languages,
  Loader2,
  MessageCircle,
  RefreshCw,
  Send,
  Sparkles,
} from 'lucide-react';
import toast from 'react-hot-toast';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import apiService, { MissionToday, RealWorldMission, SerialToday } from '@/services/api';
import { serialQueryString, writeLocalDayProgressFlag } from '@/lib/atelier-next';

type MissionMessenger = {
  channel_label: string;
  contact_name: string;
  contact_role: string;
  contact_initials: string;
  presence: string;
  thread_title: string;
  scene_anchor: string;
  dispatch_note: string;
  inbox_context: string;
  opening_message: string;
  ambient_cues: string[];
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
    contact_role: String(raw.contact_role || 'local contact'),
    contact_initials: String(raw.contact_initials || 'CA').slice(0, 3).toUpperCase(),
    presence: String(raw.presence || 'available now'),
    thread_title: String(raw.thread_title || `${raw.contact_name || 'Camille'} · ${mission?.title || 'real moment'}`),
    scene_anchor: String(slim.frame || raw.scene_anchor || mission?.brief || 'A real-world moment in French'),
    dispatch_note: String(slim.ask || raw.dispatch_note || mission?.brief || 'Send one natural French reply.'),
    inbox_context: String(raw.inbox_context || slim.frame || mission?.brief || 'The other person needs a useful reply.'),
    opening_message: String(raw.opening_message || prompt.conversation_opening || 'Bonjour, vous pouvez me répondre ?'),
    ambient_cues: asStringList(raw.ambient_cues).length
      ? asStringList(raw.ambient_cues)
      : ['one practical detail', 'a real person waiting', 'short reply rhythm'],
    quick_replies: uniqueText(asStringList(raw.quick_replies), 3),
    success_signal: String(raw.success_signal || 'The other person knows what to do next.'),
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

function targetWords(mission: RealWorldMission | null) {
  const direct = Array.isArray(mission?.target_vocabulary) ? mission?.target_vocabulary || [] : [];
  const prompt = Array.isArray(mission?.prompt_payload?.target_vocabulary)
    ? mission?.prompt_payload?.target_vocabulary || []
    : [];
  return uniqueText(
    (direct.length ? direct : prompt)
      .map((item: Record<string, any>) => [item.word, item.translation].filter(Boolean).join(' - ')),
    3,
  );
}

function missionTurns(mission: RealWorldMission | null) {
  return [...(mission?.turns || [])].sort((a, b) => Number(a.turn_index || 0) - Number(b.turn_index || 0));
}

// Immediate, quiet repair shown under the learner's OWN message — never in the
// character's reply (the character stays in role). Real grammar fixes only; the
// errata are already saved to the spaced-repetition Repair queue server-side.
function TurnRepair({ correction }: { correction: Record<string, any> | undefined }) {
  if (!correction) return null;
  const errata = (Array.isArray(correction.errata) ? correction.errata : []).filter((item: any) => {
    const kind = String(item?.task_error_type || '');
    // Only real language fixes — not "too short" task-compliance notes, and not the
    // "you didn't use word X" vocabulary nudges (those aren't corrections of an error).
    if (kind === 'task_compliance' || kind.startsWith('vocabulary')) return false;
    return Boolean(item?.corrected_target || item?.why_wrong);
  });
  const verdict = String(correction.verdict || '');
  if (errata.length === 0) {
    if (verdict === 'correct' || verdict === 'accepted') {
      return <div className="turn-repair clean"><Check size={11} /> Clean</div>;
    }
    return null;
  }
  return (
    <div className="turn-repair">
      {errata.slice(0, 2).map((item: any, index: number) => (
        <div key={index} className="turn-repair-line">
          {item.corrected_target && <span className="fix">{item.corrected_target}</span>}
          {item.why_wrong && <span className="why">{item.why_wrong}</span>}
        </div>
      ))}
      <span className="saved">Saved to your repairs</span>
    </div>
  );
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

function statusCopy(mission: RealWorldMission | null) {
  if (!mission) return 'Loading';
  if (mission.status === 'completed') return 'Resolved';
  if (mission.status === 'in_progress') return 'In progress';
  return 'Ready';
}

function completionLine(mission: RealWorldMission | null) {
  const recap = (mission?.recap || {}) as Record<string, any>;
  const minted = Array.isArray(recap.minted_collectibles) ? recap.minted_collectibles.length : 0;
  const produced = Number(recap.vocabulary_credit?.produced_correct || 0);
  if (minted && produced) return `Token minted · ${produced} word${produced === 1 ? '' : 's'} credited`;
  if (minted) return 'Token minted';
  if (produced) return `${produced} word${produced === 1 ? '' : 's'} credited`;
  return 'Saved to your practice loop';
}

function TranslateButton({ text, label = 'Translate' }: { text: string; label?: string }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [translation, setTranslation] = useState('');

  const reveal = async () => {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (translation || loading) return;
    setLoading(true);
    try {
      setTranslation(await apiService.translateToEnglish(text));
    } catch (error) {
      console.error(error);
      setTranslation('Translation unavailable.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mission-translate">
      <button type="button" onClick={reveal} className="translate-button">
        <Languages size={15} />
        {open ? 'Hide English' : label}
      </button>
      {open && (
        <p className="translation-text">
          {loading ? 'Translating...' : translation || 'Translation unavailable.'}
        </p>
      )}
    </div>
  );
}

function MissionMark({ completed = false }: { completed?: boolean }) {
  return (
    <span className={`mission-mark ${completed ? 'complete' : ''}`} aria-hidden="true">
      <i />
      <b />
      <em />
    </span>
  );
}

function LoadingState() {
  return (
    <>
      <main className="missions-page">
        <section className="mission-loading" aria-live="polite">
          <Loader2 className="spin" size={22} />
          <p>Opening today&apos;s moment...</p>
        </section>
      </main>
      <PhoneProductNav active="missions" />
      <MissionStyles />
    </>
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

  const seed = useMemo(() => querySeed(router.query as Record<string, string | string[] | undefined>), [router.query]);
  const messenger = useMemo(() => missionMessenger(mission), [mission]);
  const frame = useMemo(() => missionFrame(mission, messenger), [mission, messenger]);
  const turns = useMemo(() => missionTurns(mission), [mission]);
  const words = useMemo(() => targetWords(mission), [mission]);
  const isSerialAct = Boolean(mission?.serial_thread_id || seed.serialThreadId);
  const completed = mission?.status === 'completed';
  const interactionReady = hasInteraction(mission);
  const canSend = reply.trim().length > 0 && !submitting && !completed;

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
      setError('Could not open the mission moment.');
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

  const sendReply = async (event?: FormEvent) => {
    event?.preventDefault();
    const text = reply.trim();
    if (!mission || !text || submitting || completed) return;
    setSubmitting(true);
    try {
      const result = await apiService.submitMissionTurn(mission.id, { text, mode: 'chat' });
      setMission({ ...result.mission, outcome: result.outcome || result.mission.outcome });
      setReply('');
    } catch (sendError) {
      console.error(sendError);
      toast.error('Message did not send.');
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
      setCompletedNextSerial(result.next_serial || null);
      if (!result.mission.serial_thread_id) {
        writeLocalDayProgressFlag('missionDone');
      }
      toast.success(isSerialAct ? 'Act resolved' : 'Mission resolved');
      if (result.next_serial && result.mission.serial_thread_id) {
        void router.push(routeForMissionSerialBeat(result.next_serial));
      }
    } catch (completeError) {
      console.error(completeError);
      toast.error('Could not finish this moment.');
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
      toast.success(next.serial_thread_id ? 'Act opened' : 'Mission opened');
    } catch (createError) {
      console.error(createError);
      toast.error('Could not create a new moment.');
    }
  };

  const returnToAtelierHome = useCallback((event: React.MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    loadRequestRef.current += 1;
    void router.push('/atelier').catch(() => {
      window.location.assign('/atelier');
    });
  }, [router]);

  if (loading && !mission) return <LoadingState />;

  const assistantReply = latestAssistantReply(mission);
  const completion = completed ? completionLine(mission) : null;
  const translatePrompt = [frame.frame, frame.ask, messenger.opening_message].filter(Boolean).join(' ');

  return (
    <>
      <Head>
        <title>{isSerialAct ? 'Feuilleton Act' : 'Mission'} · Conversational Language Learning</title>
      </Head>
      <main className="missions-page">
        <header className="mission-nav">
          <Link href="/atelier" className="back-link" aria-label="Return to Atelier home" onClick={returnToAtelierHome}>
            <ArrowLeft size={16} />
            Atelier
          </Link>
          <span>{statusCopy(mission)}</span>
        </header>

        {error ? (
          <section className="mission-error">
            <MessageCircle size={24} />
            <h1>{error}</h1>
            <button type="button" onClick={loadMission} className="ink-button">
              <RefreshCw size={16} />
              Retry
            </button>
          </section>
        ) : (
          <section className="mission-stage" aria-label={isSerialAct ? 'Feuilleton act' : 'Mission'}>
            <div className="scene-column">
              <section className="scene-frame">
                <div className="frame-top">
                  <MissionMark completed={completed} />
                  <div>
                    <span>{isSerialAct ? 'Feuilleton act' : 'Mission'}</span>
                    <h1>{missionTitle(mission)}</h1>
                  </div>
                </div>
                <p>{frame.frame}</p>
                <strong>{frame.ask}</strong>
                <TranslateButton text={translatePrompt} label="Translate frame" />
              </section>

              {words.length > 0 && (
                <section className="word-ribbon" aria-label="Target words">
                  {words.map((word) => (
                    <span key={word}>{word}</span>
                  ))}
                </section>
              )}

              {completed && (
                <section className="reward-strip" aria-label="Mission payoff">
                  <div className="token-preview minted">
                    <Check size={18} />
                  </div>
                  <div>
                    <span>{completion}</span>
                    <p>{messenger.success_signal}</p>
                  </div>
                </section>
              )}
            </div>

            <section className="phone-column">
              <div className="thread-head">
                <div className="avatar">{messenger.contact_initials}</div>
                <div>
                  <span>{messenger.channel_label}</span>
                  <strong>{messenger.contact_name}</strong>
                  <p>{messenger.contact_role} · {messenger.presence}</p>
                </div>
              </div>

              <div className="thread-body" aria-live="polite">
                <article className="message-row assistant">
                  <div className="bubble">
                    <span>{messenger.thread_title}</span>
                    <p>{messenger.opening_message}</p>
                    <TranslateButton text={messenger.opening_message} />
                  </div>
                </article>

                {turns.map((turn) => (
                  <article key={turn.id || `${turn.turn_index}-${turn.role}`} className={`message-row ${turn.role === 'user' ? 'user' : 'assistant'}`}>
                    <div className="bubble">
                      <p>{turn.text}</p>
                      {turn.role === 'assistant' && <TranslateButton text={turn.text} />}
                    </div>
                    {turn.role === 'user' && <TurnRepair correction={(turn as Record<string, any>).correction} />}
                  </article>
                ))}

                {completed && (
                  <article className="resolution-note">
                    <MissionMark completed />
                    <div>
                      <span>{completion}</span>
                      <p>{mission?.recap?.branch_outcome?.next_best_move || assistantReply || 'The exchange is saved.'}</p>
                    </div>
                  </article>
                )}
              </div>

              {!completed && (
                <form className="composer" onSubmit={sendReply}>
                  <label htmlFor="mission-reply">Your reply in French</label>
                  <textarea
                    id="mission-reply"
                    value={reply}
                    onChange={(event) => setReply(event.target.value)}
                    placeholder="Bonjour..."
                    rows={5}
                  />
                  {messenger.quick_replies.length > 0 && (
                    <div className="reply-starters" aria-label="Reply starters">
                      {messenger.quick_replies.map((starter) => (
                        <button
                          type="button"
                          key={starter}
                          onClick={() => setReply((current) => current ? `${current.trim()} ${starter}` : starter)}
                        >
                          {starter}
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="composer-actions">
                    <button type="submit" className="send-button" disabled={!canSend}>
                      {submitting ? <Loader2 className="spin" size={16} /> : <Send size={16} />}
                      Send
                    </button>
                    <button
                      type="button"
                      className="finish-button"
                      disabled={completing || !interactionReady}
                      onClick={finishMission}
                    >
                      {completing ? <Loader2 className="spin" size={16} /> : <Check size={16} />}
                      {interactionReady ? 'Finish' : 'Send first'}
                    </button>
                  </div>
                </form>
              )}

              {completed && (
                <div className="completed-actions">
                  {isSerialAct ? (
                    <Link href={routeForMissionSerialBeat(completedNextSerial)} className="quiet-link">
                      Next act <ArrowRight size={14} />
                    </Link>
                  ) : null}
                  <Link href="/vocabulary" className="quiet-link">
                    Coverage map <ArrowRight size={14} />
                  </Link>
                  {!isSerialAct && (
                    <button type="button" onClick={startFreshMission} className="quiet-link as-button" disabled={creating}>
                      {creating ? <Loader2 className="spin" size={14} /> : <RefreshCw size={14} />}
                      New moment
                    </button>
                  )}
                </div>
              )}
            </section>
          </section>
        )}
      </main>
      <PhoneProductNav active="missions" />
      <MissionStyles />
    </>
  );
}

function MissionStyles() {
  return (
    <style jsx global>{`
      :root {
        --mission-paper: #f4eee2;
        --mission-sheet: #fffaf0;
        --mission-ink: #191715;
        --mission-muted: #6d665c;
        --mission-red: #e24a3b;
        --mission-blue: #2f6fdd;
        --mission-yellow: #f0c94a;
        --mission-green: #2f9b68;
        --mission-line: rgba(25, 23, 21, .18);
      }

      .missions-page {
        min-height: 100vh;
        background:
          linear-gradient(90deg, rgba(25, 23, 21, .04) 1px, transparent 1px),
          var(--mission-paper);
        background-size: 42px 42px;
        color: var(--mission-ink);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }

      .missions-page * {
        box-sizing: border-box;
      }

      .missions-page button,
      .missions-page textarea {
        font: inherit;
      }

      .mission-nav {
        position: sticky;
        top: 0;
        z-index: 10;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 18px;
        padding: 16px max(18px, calc((100vw - 1180px) / 2));
        border-bottom: 2px solid var(--mission-ink);
        background: rgba(244, 238, 226, .95);
        backdrop-filter: blur(10px);
        font-size: 11px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }

      .back-link,
      .quiet-link {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        color: inherit;
        text-decoration: none;
      }

      .back-link {
        min-height: 40px;
        margin: -10px 0 -10px -8px;
        padding: 0 8px;
      }

      .back-link:focus-visible {
        outline: 2px solid var(--mission-blue);
        outline-offset: 2px;
      }

      .mission-stage {
        width: min(1180px, 100%);
        margin: 0 auto;
        padding: 34px 18px 46px;
        display: grid;
        grid-template-columns: minmax(290px, 430px) minmax(0, 1fr);
        gap: 28px;
        align-items: start;
      }

      .scene-column,
      .phone-column {
        min-width: 0;
        display: grid;
        gap: 16px;
      }

      .scene-frame,
      .reward-strip,
      .word-ribbon,
      .phone-column,
      .mission-error,
      .mission-loading {
        border: 2px solid var(--mission-ink);
        background: var(--mission-sheet);
        box-shadow: 8px 8px 0 var(--mission-ink);
      }

      .scene-frame {
        padding: 24px;
        display: grid;
        gap: 18px;
      }

      .frame-top {
        display: flex;
        gap: 16px;
        align-items: center;
      }

      .frame-top span,
      .thread-head span,
      .bubble span,
      .reward-strip span,
      .composer label,
      .word-ribbon span {
        display: block;
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .13em;
        text-transform: uppercase;
        color: var(--mission-muted);
      }

      .frame-top h1 {
        margin: 3px 0 0;
        font-family: Georgia, "Times New Roman", serif;
        font-size: 27px;
        line-height: 1.05;
        font-style: italic;
        font-weight: 700;
        letter-spacing: 0;
        color: var(--mission-ink);
      }

      .scene-frame p,
      .reward-strip p,
      .thread-head p,
      .resolution-note p {
        margin: 0;
        color: var(--mission-muted);
        line-height: 1.45;
      }

      .scene-frame strong {
        display: block;
        font-size: 20px;
        line-height: 1.28;
        font-weight: 850;
      }

      .scene-frame small {
        display: block;
        border-left: 5px solid var(--mission-yellow);
        padding-left: 12px;
        color: var(--mission-muted);
        line-height: 1.4;
      }

      .mission-mark {
        width: 54px;
        height: 54px;
        position: relative;
        display: inline-grid;
        place-items: center;
        flex: 0 0 auto;
        background: var(--mission-yellow);
        border: 2px solid var(--mission-ink);
      }

      .mission-mark i,
      .mission-mark b,
      .mission-mark em {
        position: absolute;
        display: block;
        border: 2px solid var(--mission-ink);
      }

      .mission-mark i {
        width: 28px;
        height: 28px;
        background: var(--mission-red);
        transform: rotate(45deg);
      }

      .mission-mark b {
        width: 20px;
        height: 20px;
        border-radius: 999px;
        background: var(--mission-blue);
        right: 4px;
        bottom: 4px;
      }

      .mission-mark em {
        width: 0;
        height: 0;
        border-left: 11px solid transparent;
        border-right: 11px solid transparent;
        border-bottom: 20px solid var(--mission-green);
        border-top: 0;
        left: 4px;
        top: 4px;
      }

      .mission-mark.complete {
        background: var(--mission-green);
      }

      .reward-strip {
        display: grid;
        grid-template-columns: 50px minmax(0, 1fr);
        gap: 14px;
        align-items: center;
        padding: 16px;
      }

      .token-preview {
        width: 46px;
        height: 46px;
        display: grid;
        place-items: center;
        border: 2px solid var(--mission-ink);
        background: var(--mission-yellow);
      }

      .token-preview.minted {
        background: var(--mission-green);
        color: white;
      }

      .word-ribbon {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 12px;
        box-shadow: 5px 5px 0 var(--mission-ink);
      }

      .word-ribbon span {
        padding: 7px 9px;
        border: 1px solid var(--mission-ink);
        background: white;
        color: var(--mission-ink);
        letter-spacing: .07em;
      }

      .phone-column {
        padding: 0;
        overflow: hidden;
      }

      .thread-head {
        min-height: 78px;
        display: grid;
        grid-template-columns: 48px minmax(0, 1fr);
        gap: 13px;
        align-items: center;
        padding: 16px 18px;
        border-bottom: 2px solid var(--mission-ink);
        background: white;
      }

      .avatar {
        width: 48px;
        height: 48px;
        border: 2px solid var(--mission-ink);
        display: grid;
        place-items: center;
        background: var(--mission-blue);
        color: white;
        font-weight: 950;
      }

      .thread-head strong {
        display: block;
        font-size: 18px;
        line-height: 1.1;
      }

      .thread-body {
        min-height: 360px;
        max-height: 56vh;
        overflow: auto;
        padding: 22px;
        display: flex;
        flex-direction: column;
        gap: 14px;
        background:
          linear-gradient(180deg, rgba(47, 111, 221, .08), transparent 160px),
          #f7f3eb;
      }

      .message-row {
        display: flex;
      }

      .message-row.user {
        justify-content: flex-end;
        flex-direction: column;
        align-items: flex-end;
      }

      .turn-repair {
        width: min(560px, 86%);
        margin-top: 5px;
        display: grid;
        gap: 3px;
        justify-items: end;
        text-align: right;
      }
      .turn-repair.clean {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .1em;
        text-transform: uppercase;
        color: var(--mission-green);
      }
      .turn-repair-line {
        display: grid;
        gap: 1px;
        justify-items: end;
        border-right: 3px solid var(--mission-red);
        padding-right: 9px;
      }
      .turn-repair-line .fix {
        font-family: var(--font-serif, Garamond, serif);
        font-style: italic;
        font-size: 16px;
        color: var(--mission-ink);
      }
      .turn-repair-line .why {
        font-size: 12px;
        color: var(--mission-muted);
        line-height: 1.35;
      }
      .turn-repair .saved {
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
        color: var(--mission-muted);
      }

      .bubble {
        width: min(560px, 86%);
        border: 2px solid var(--mission-ink);
        background: white;
        padding: 13px 15px;
        box-shadow: 4px 4px 0 var(--mission-ink);
      }

      .message-row.user .bubble {
        background: var(--mission-ink);
        color: white;
        box-shadow: 4px 4px 0 var(--mission-blue);
      }

      .message-row.user .bubble p {
        color: white;
      }

      .bubble p {
        margin: 5px 0 0;
        line-height: 1.45;
        white-space: pre-wrap;
      }

      .mission-translate {
        display: grid;
        gap: 6px;
        margin-top: 10px;
      }

      .translate-button {
        width: fit-content;
        display: inline-flex;
        align-items: center;
        gap: 7px;
        border: 1px solid var(--mission-ink);
        background: var(--mission-sheet);
        color: var(--mission-ink);
        padding: 7px 9px;
        font-size: 11px;
        font-weight: 850;
        cursor: pointer;
      }

      .message-row.user .translate-button {
        display: none;
      }

      .translation-text {
        margin: 0;
        color: var(--mission-muted);
        font-size: 13px;
        line-height: 1.35;
      }

      .resolution-note {
        display: grid;
        grid-template-columns: 48px minmax(0, 1fr);
        gap: 12px;
        align-items: center;
        border: 2px solid var(--mission-ink);
        background: white;
        padding: 14px;
        box-shadow: 4px 4px 0 var(--mission-green);
      }

      .composer {
        display: grid;
        gap: 12px;
        padding: 18px;
        border-top: 2px solid var(--mission-ink);
        background: white;
      }

      .composer textarea {
        width: 100%;
        min-height: 132px;
        resize: vertical;
        border: 2px solid var(--mission-ink);
        background: var(--mission-sheet);
        padding: 14px;
        line-height: 1.45;
        outline: none;
      }

      .composer textarea:focus {
        box-shadow: 0 0 0 3px var(--mission-yellow);
      }

      .reply-starters {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .reply-starters button {
        border: 1px solid var(--mission-ink);
        background: var(--mission-paper);
        padding: 7px 9px;
        font-size: 13px;
        cursor: pointer;
      }

      .composer-actions,
      .completed-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
      }

      .send-button,
      .finish-button,
      .ink-button,
      .quiet-link.as-button {
        min-height: 44px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 9px;
        border: 2px solid var(--mission-ink);
        padding: 0 16px;
        font-weight: 900;
        cursor: pointer;
        text-decoration: none;
      }

      .send-button,
      .ink-button {
        background: var(--mission-ink);
        color: white;
      }

      .finish-button,
      .quiet-link.as-button,
      .quiet-link {
        background: white;
        color: var(--mission-ink);
      }

      .send-button:disabled,
      .finish-button:disabled,
      .quiet-link.as-button:disabled {
        cursor: not-allowed;
        opacity: .5;
      }

      .completed-actions {
        padding: 16px 18px 18px;
        border-top: 2px solid var(--mission-ink);
        background: white;
      }

      .mission-loading,
      .mission-error {
        width: min(520px, calc(100% - 36px));
        margin: 80px auto;
        padding: 28px;
        display: grid;
        gap: 16px;
        justify-items: start;
      }

      .mission-error h1,
      .mission-loading p {
        margin: 0;
        font-size: 20px;
      }

      .spin {
        animation: mission-spin 900ms linear infinite;
      }

      @keyframes mission-spin {
        to { transform: rotate(360deg); }
      }

      @media (max-width: 860px) {
        .missions-page {
          padding-bottom: var(--phone-bottom-nav-space);
        }
        .mission-stage {
          grid-template-columns: 1fr;
          padding: 18px 14px 28px;
          gap: 18px;
        }

        .mission-nav {
          padding-inline: 14px;
        }

        .scene-frame,
        .phone-column {
          box-shadow: 5px 5px 0 var(--mission-ink);
        }

        .frame-top h1 {
          font-size: 29px;
        }

        .thread-body {
          min-height: 300px;
          max-height: none;
          padding: 16px;
        }

        .bubble {
          width: 94%;
        }
      }

      @media (max-width: 520px) {
        .scene-frame {
          padding: 18px;
        }

        .frame-top {
          align-items: flex-start;
        }

        .mission-mark {
          width: 48px;
          height: 48px;
        }

        .composer-actions,
        .completed-actions {
          display: grid;
          grid-template-columns: 1fr;
        }

        .send-button,
        .finish-button,
        .quiet-link {
          width: 100%;
        }
      }
    `}</style>
  );
}

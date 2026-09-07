import Head from 'next/head';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect, useRef, useState } from 'react';
import {
  ArrowLeft,
  Eye,
  EyeOff,
  HelpCircle,
  Mic,
  Square,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react';
import toast from 'react-hot-toast';

import { atelierChrome } from '@/lib/atelier-v2-copy';
import { createAudioMediaRecorder, recordedAudioBlob } from '@/lib/audio-recording';
import { useLearnerLanguage } from '@/lib/learner-language';
import { useAppSession } from '@/lib/app-auth';
import apiService from '@/services/api';

type Status = 'idle' | 'selecting' | 'starting' | 'listening' | 'processing' | 'speaking' | 'ended';
type CastMember = {
  id: string;
  name: string;
  role?: string | null;
  model_sheet_url?: string | null;
  accent_colour?: string | null;
  relationship?: { closeness?: number; register?: string; last_summary?: string; callbacks?: string[] };
};
type Correction = {
  original: string;
  correction: string;
  explanation: string;
  concept_id?: number | null;
  concept_name?: string | null;
};
type StudioState = {
  sessionId: string | null;
  status: Status;
  history: Array<{ role: 'user' | 'assistant'; content: string }>;
  aiResponse: string;
  showText: boolean;
  elapsedSeconds: number;
  totalXP: number;
  turns: number;
  producedWords: number;
  dueWordsReused: string[];
  errors: Correction[];
  longestAnswerWords: number;
  longestAnswer: string;
  tomorrowFocus: string;
  castMember: CastMember | null;
};

const INITIAL_STATE: StudioState = {
  sessionId: null,
  status: 'idle',
  history: [],
  aiResponse: '',
  showText: false,
  elapsedSeconds: 0,
  totalXP: 0,
  turns: 0,
  producedWords: 0,
  dueWordsReused: [],
  errors: [],
  longestAnswerWords: 0,
  longestAnswer: '',
  tomorrowFocus: '',
  castMember: null,
};

// Safety net for a voice that never announces its end (blocked autoplay, a
// speech-synthesis engine that swallows `onend`, a stalled element).
const SPEAKING_TIMEOUT_MS = 60000;
// Below this a recording holds container headers and no speech.
const EMPTY_RECORDING_BYTES = 1200;

const KICKER_BY_STATUS: Record<Status, string> = {
  idle: 'APPEL OUVERT',
  selecting: 'APPEL OUVERT',
  starting: 'LIGNE EN PRÉPARATION',
  listening: 'APPEL EN COURS',
  processing: 'APPEL EN COURS',
  speaking: 'APPEL EN COURS',
  ended: 'APPEL CLASSÉ',
};

// Screen readers get the same French stage line the page prints, never the
// internal status key.
const METER_LABEL_BY_STATUS: Partial<Record<Status, string>> = {
  listening: 'À vous de parler',
  processing: 'La réponse se compose',
  speaking: 'Votre interlocuteur parle',
};

const plural = (count: number, singular: string, many: string) => (
  `${count} ${count > 1 ? many : singular}`
);

const SCENES = [
  { id: 'bakery', title: 'À la boulangerie', note: 'Commander sans préparer son texte.' },
  { id: 'directions', title: 'Perdu dans la ville', note: 'Demander et reformuler un chemin.' },
  { id: 'restaurant_order', title: 'Au bistrot', note: 'Commander et préciser une contrainte.' },
];

export default function AudioSessionPage() {
  const router = useRouter();
  const { data: authSession, status: authStatus } = useAppSession();
  const [state, setState] = useState<StudioState>(INITIAL_STATE);
  const [isMuted, setIsMuted] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [showEndConfirm, setShowEndConfirm] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  // Le Studio's fiction is French; the microphone failures explain a fault and
  // follow the learner's own language (WP-21).
  const chrome = atelierChrome(useLearnerLanguage());
  const pendingTurnRef = useRef<Promise<void> | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const endedRef = useRef(false);
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    if (authStatus === 'unauthenticated') void router.replace('/auth/signin');
  }, [authStatus, router]);

  useEffect(() => {
    if (!['listening', 'processing', 'speaking'].includes(state.status)) return;
    timerRef.current = window.setInterval(() => {
      setState((current) => ({ ...current, elapsedSeconds: current.elapsedSeconds + 1 }));
    }, 1000);
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
    };
  }, [state.status]);

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    audioRef.current?.pause();
    window.speechSynthesis?.cancel();
  }, []);

  const playTTS = async (text: string) => {
    // Whoever finishes first hands the turn back to the learner: a silent
    // failure used to leave the page in `speaking` for good, with the mic
    // disabled and no way out but a reload.
    let released = false;
    const handBack = () => {
      if (released) return;
      released = true;
      window.clearTimeout(watchdog);
      if (endedRef.current) return;
      setState((current) => (current.status === 'ended' ? current : { ...current, status: 'listening' }));
    };
    const watchdog = window.setTimeout(handBack, SPEAKING_TIMEOUT_MS);

    if (isMuted) {
      handBack();
      return;
    }
    try {
      const audioData = await apiService.synthesizeSpeech(text);
      const url = URL.createObjectURL(new Blob([audioData], { type: 'audio/mpeg' }));
      const audio = new Audio(url);
      audioRef.current?.pause();
      audioRef.current = audio;
      const finish = () => {
        URL.revokeObjectURL(url);
        handBack();
      };
      audio.onended = finish;
      audio.onerror = finish;
      await audio.play();
    } catch {
      if (!('speechSynthesis' in window)) {
        handBack();
        return;
      }
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'fr-FR';
      utterance.rate = 0.9;
      utterance.onend = handBack;
      utterance.onerror = handBack;
      window.speechSynthesis.speak(utterance);
    }
  };

  const startSession = async (scenarioId?: string) => {
    setState((current) => ({ ...current, status: 'starting' }));
    try {
      const response = await apiService.startAudioSession(scenarioId);
      const castMember = (response.context?.cast_member || null) as CastMember | null;
      endedRef.current = false;
      setState({
        ...INITIAL_STATE,
        sessionId: response.session_id,
        status: 'speaking',
        history: [{ role: 'assistant', content: response.opening_message }],
        aiResponse: response.opening_message,
        castMember,
      });
      await playTTS(response.opening_message);
    } catch (error) {
      console.error(error);
      setState(INITIAL_STATE);
      toast.error("L’appel n’a pas pu commencer.");
    }
  };

  const processAudio = async (blob: Blob) => {
    try {
      const transcript = (await apiService.transcribeAudio(blob)).trim();
      if (!transcript) {
        setState((current) => ({ ...current, status: 'listening' }));
        return;
      }
      const normalized = transcript.toLocaleLowerCase().replace(/[.,!?]/g, '').trim();
      if (['au revoir', 'terminer', 'finir', 'stop'].includes(normalized)) {
        // This turn IS the closing gesture: clear it before ending, or
        // endSession would wait on the promise it is itself running inside.
        pendingTurnRef.current = null;
        await endSession();
        return;
      }
      const snapshot = stateRef.current;
      setState((current) => ({
        ...current,
        history: [...current.history, { role: 'user', content: transcript }],
      }));
      const response = await apiService.respondToAudioSession({
        session_id: snapshot.sessionId!,
        user_text: transcript,
        conversation_history: snapshot.history,
      });
      const wordCount = transcript.split(/\s+/).filter(Boolean).length;
      if (endedRef.current) {
        // The call was closed while this turn was in flight: keep the summary
        // on screen, but let the turn's corrections reach it instead of vanishing.
        setState((current) => ({
          ...current,
          errors: [...current.errors, ...(response.detected_errors || [])],
        }));
        return;
      }
      setState((current) => ({
        ...current,
        aiResponse: response.ai_response,
        history: [
          ...current.history,
          { role: 'assistant', content: response.ai_response },
        ],
        totalXP: current.totalXP + Number(response.xp_awarded || 0),
        turns: current.turns + 1,
        producedWords: current.producedWords + wordCount,
        dueWordsReused: Array.from(new Set([
          ...current.dueWordsReused,
          ...(response.vocabulary_credit?.words || []),
        ])),
        errors: [...current.errors, ...(response.detected_errors || [])],
        showText: current.showText || Boolean(response.should_show_text),
        status: 'speaking',
      }));
      await playTTS(response.ai_response);
    } catch (error) {
      console.error(error);
      if (endedRef.current) return;
      toast.error("La réponse n’a pas été transmise. Vous pouvez reprendre.");
      setState((current) => ({ ...current, status: 'listening' }));
    }
  };

  const startRecording = async () => {
    if (state.status !== 'listening') return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = createAudioMediaRecorder(stream);
      streamRef.current = stream;
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        setIsRecording(false);
        const blob = recordedAudioBlob(chunksRef.current, recorder);
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        if (blob.size < EMPTY_RECORDING_BYTES) {
          // Nothing was captured (tapped twice, muted hardware): say so plainly
          // instead of sending an empty file and reporting a failed reply.
          setState((current) => ({ ...current, status: 'listening' }));
          toast(chrome.nothing_heard);
          return;
        }
        // Remember the turn so that classing the call waits for it instead of
        // filing a recap that is missing the last thing the learner said.
        const turn = processAudio(blob).finally(() => {
          if (pendingTurnRef.current === turn) pendingTurnRef.current = null;
        });
        pendingTurnRef.current = turn;
      };
      recorder.start();
      setMicError(null);
      setIsRecording(true);
    } catch (error) {
      console.error(error);
      const denied = error instanceof DOMException
        && ['NotAllowedError', 'SecurityError', 'PermissionDeniedError'].includes(error.name);
      const message = denied
        ? chrome.mic_denied
        : chrome.mic_unavailable;
      setMicError(message);
      toast.error(message);
    }
  };

  const stopRecording = () => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === 'inactive') return;
    setIsRecording(false);
    setState((current) => ({ ...current, status: 'processing' }));
    recorder.stop();
  };

  const toggleRecording = () => {
    if (isRecording || recorderRef.current?.state === 'recording') {
      stopRecording();
      return;
    }
    void startRecording();
  };

  const endSession = async () => {
    setShowEndConfirm(false);
    // A turn already on its way still belongs to this call: wait for it so the
    // server counts it before it computes the recap.
    const pending = pendingTurnRef.current;
    if (pending) {
      setState((current) => (
        current.status === 'ended' ? current : { ...current, status: 'processing' }
      ));
      try {
        await pending;
      } catch {
        // processAudio already surfaced its own failure.
      }
    }
    endedRef.current = true;
    window.speechSynthesis?.cancel();
    audioRef.current?.pause();
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.onstop = null;
      recorder.stop();
    }
    recorderRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setIsRecording(false);
    const sessionId = stateRef.current.sessionId;
    if (!sessionId) {
      setState((current) => ({ ...current, status: 'ended' }));
      return;
    }
    try {
      const summary = await apiService.endAudioSession({ session_id: sessionId });
      setState((current) => ({
        ...current,
        status: 'ended',
        elapsedSeconds: summary.duration_seconds,
        totalXP: summary.total_xp,
        turns: summary.turns,
        producedWords: summary.produced_words,
        dueWordsReused: summary.due_words_reused || current.dueWordsReused,
        // The end API only returns a count (errors_practiced), never the
        // correction details — the summary's corrections come from the
        // detected_errors tracked turn by turn during the live call.
        errors: current.errors,
        longestAnswerWords: summary.longest_answer_words,
        longestAnswer: summary.longest_answer,
        tomorrowFocus: summary.tomorrow_focus,
      }));
    } catch (error) {
      console.error(error);
      setState((current) => ({ ...current, status: 'ended' }));
    }
  };

  const formatTime = (seconds: number) => (
    `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
  );

  if (authStatus === 'loading' || !authSession) {
    return <div className="studio-loading" aria-label="Chargement du Studio"><span /></div>;
  }

  return (
    <>
      <Head><title>Le Studio · L’Atelier</title></Head>
      <main className="studio">
        <header className="studio-masthead">
          <Link href="/atelier" aria-label="Retour à La Une"><ArrowLeft size={17} /></Link>
          <div>
            {/* No call number exists in this flow — "N°" only ever appears before an actual number.
                The kicker states the call's real stage: a classed call is not "en cours". */}
            <span>LE STUDIO · {KICKER_BY_STATUS[state.status]}</span>
            <h1>Le Studio</h1>
          </div>
          <span className="studio-time">{formatTime(state.elapsedSeconds)}</span>
        </header>

        {state.status === 'idle' && (
          <section className="studio-intro print-in">
            <div className="studio-rule">CONVERSATION · 5 MINUTES</div>
            <h2>Une voix, une vraie réponse.</h2>
            <p>
              La conversation reprend votre histoire et vos mots du jour. Les corrections
              restent discrètes : vous gardez le fil.
            </p>
            <button className="studio-primary press" onClick={() => void startSession()}>
              <Mic size={22} /> Commencer à parler
            </button>
            <button className="studio-secondary" onClick={() => setState((current) => ({ ...current, status: 'selecting' }))}>
              Choisir une scène
            </button>
          </section>
        )}

        {state.status === 'selecting' && (
          <section className="studio-scenes print-in">
            <div className="studio-rule">SCÈNES DE RECHANGE</div>
            <h2>Un décor précis</h2>
            {SCENES.map((scene) => (
              <button key={scene.id} onClick={() => void startSession(scene.id)}>
                <strong>{scene.title}</strong><span>{scene.note}</span>
              </button>
            ))}
            <button className="studio-text-button" onClick={() => setState(INITIAL_STATE)}>Retour</button>
          </section>
        )}

        {state.status === 'starting' && (
          <section className="studio-wait" aria-live="polite">
            <span className="studio-spinner" />
            <strong>La ligne se prépare…</strong>
          </section>
        )}

        {['listening', 'processing', 'speaking'].includes(state.status) && (
          <section className="studio-call print-in">
            <CastHeader cast={state.castMember} />
            <div
              className={`studio-meter ${state.status}`}
              aria-label={METER_LABEL_BY_STATUS[state.status] || 'Appel en cours'}
            >
              {Array.from({ length: 11 }, (_, index) => <i key={index} />)}
              <div className="studio-seal">
                {state.status === 'listening' ? <Mic size={35} /> : <Volume2 size={35} />}
              </div>
            </div>
            <p className="studio-status" aria-live="polite">
              {state.status === 'speaking' && `${state.castMember?.name || 'Votre interlocuteur'} parle`}
              {state.status === 'listening' && 'À vous de parler'}
              {state.status === 'processing' && 'La réponse se compose'}
            </p>
            {(state.showText || isMuted) && state.aiResponse && (
              <blockquote>{state.aiResponse}</blockquote>
            )}
            <div className="studio-controls">
              {/* Muting must not silence the character outright: the reply stays
                  readable for as long as the sound is off. */}
              <button
                aria-label={isMuted ? 'Rétablir le son' : 'Couper le son'}
                onClick={() => setIsMuted((value) => !value)}
              >
                {isMuted ? <VolumeX /> : <Volume2 />}
              </button>
              <button
                className="studio-mic press"
                disabled={state.status === 'processing' || state.status === 'speaking'}
                onClick={toggleRecording}
                aria-label={isRecording ? 'Arrêter l’enregistrement' : 'Commencer à parler'}
              >
                {state.status === 'processing' || isRecording ? <Square /> : <Mic />}
              </button>
              <button aria-label={state.showText ? 'Masquer le texte' : 'Afficher le texte'} onClick={() => setState((current) => ({ ...current, showText: !current.showText }))}>
                {state.showText ? <EyeOff /> : <Eye />}
              </button>
            </div>
            {micError && <p className="studio-mic-error" role="status">{micError}</p>}
            <button className="studio-end" onClick={() => setShowEndConfirm(true)}>Terminer l’appel</button>
          </section>
        )}

        {state.status === 'ended' && (
          <section className="studio-summary print-in">
            <div className="studio-filed">BON À TIRER</div>
            <h2>Conversation transmise.</h2>
            {/* Counts are what really happened, so they have to read as French:
                one tour, one mot, and "malgré 0 fautes" is not a sentence. */}
            <p className="studio-honest">
              {state.turns === 0 ? (
                'Aucun tour parlé : l’appel s’est arrêté avant votre première phrase.'
              ) : (
                <>
                  {plural(state.turns, 'tour parlé', 'tours parlés')} · réponse la plus longue{' '}
                  {plural(state.longestAnswerWords, 'mot', 'mots')} ·{' '}
                  {plural(
                    state.dueWordsReused.length,
                    'mot du jour réemployé',
                    'mots du jour réemployés',
                  )}
                  {state.errors.length > 0
                    ? ` · communiqué malgré ${plural(state.errors.length, 'faute de forme', 'fautes de forme')}.`
                    : ' · communiqué sans faute de forme relevée.'}
                </>
              )}
            </p>
            <dl>
              <div><dt>Durée</dt><dd>{formatTime(state.elapsedSeconds)}</dd></div>
              <div><dt>Tours</dt><dd>{state.turns}</dd></div>
              <div><dt>Mots produits</dt><dd>{state.producedWords}</dd></div>
              <div><dt>Mots repris</dt><dd>{state.dueWordsReused.join(' · ') || '—'}</dd></div>
            </dl>
            {state.longestAnswer && (
              <aside><span>VOTRE PLUS LONGUE RÉPONSE</span><p>« {state.longestAnswer} »</p></aside>
            )}
            {state.errors.length > 0 && (
              <div className="studio-corrections">
                <span>CORRECTIONS DISCRÈTES</span>
                {state.errors.map((error, index) => (
                  <div key={`${error.original}-${index}`}>
                    <s>{error.original}</s><strong>{error.correction}</strong><p>{error.explanation}</p>
                  </div>
                ))}
              </div>
            )}
            <aside className="studio-tomorrow"><span>POUR DEMAIN</span><p>{state.tomorrowFocus}</p></aside>
            <button className="studio-primary press" onClick={() => setState(INITIAL_STATE)}>Nouvel appel</button>
            <Link className="studio-secondary" href="/atelier">Retour à La Une</Link>
          </section>
        )}
      </main>

      {showHelp && (
        <div className="studio-modal" role="dialog" aria-modal="true" aria-label="Mode d’emploi">
          <div><button aria-label="Fermer" onClick={() => setShowHelp(false)}><X /></button><h2>Le geste</h2>
            <p>Touchez le micro, parlez, puis touchez le carré. L’œil révèle la dernière phrase si nécessaire.</p>
          </div>
        </div>
      )}
      {showEndConfirm && (
        <div className="studio-modal" role="dialog" aria-modal="true" aria-label="Terminer l’appel">
          <div><h2>Classer cet appel ?</h2><p>Votre conversation sera ajoutée au dossier du jour.</p>
            <div className="studio-modal-actions">
              <button onClick={() => setShowEndConfirm(false)}>Continuer</button>
              <button className="press" onClick={() => void endSession()}>Classer</button>
            </div>
          </div>
        </div>
      )}
      {['listening', 'processing', 'speaking'].includes(state.status) && (
        <button className="studio-help" aria-label="Aide" onClick={() => setShowHelp(true)}><HelpCircle /></button>
      )}
      <StudioStyles />
    </>
  );
}

function CastHeader({ cast }: { cast: CastMember | null }) {
  const [imageFailed, setImageFailed] = useState(false);
  const initials = (cast?.name || 'Le Studio').split(/\s+/).map((part) => part[0]).join('').slice(0, 2);
  return (
    <div className="studio-cast">
      <div className="studio-portrait">
        {cast?.model_sheet_url && !imageFailed
          ? <Image src={cast.model_sheet_url} alt="" fill sizes="56px" onError={() => setImageFailed(true)} />
          : <span>{initials}</span>}
      </div>
      <div><span>EN LIGNE</span><strong>{cast?.name || 'Conversation libre'}</strong><em>{cast?.role || 'Le Studio'}</em></div>
    </div>
  );
}

function StudioStyles() {
  return <style jsx global>{`
    .studio { --studio-accent: var(--app-blue); min-height: 100svh; color: var(--app-ink); background: var(--app-paper); padding-bottom: calc(40px + env(safe-area-inset-bottom)); font-family: var(--app-sans); }
    .studio button, .studio a { color: inherit; font: inherit; }
    .studio-masthead { display: grid; grid-template-columns: 42px 1fr auto; align-items: center; gap: 12px; max-width: 480px; margin: auto; padding: calc(12px + env(safe-area-inset-top)) 18px 12px; border-bottom: 2px solid var(--app-ink); }
    .studio-masthead > a { width: 34px; height: 34px; display: grid; place-items: center; border: 1px solid var(--app-ink); background: var(--app-sheet); }
    .studio-masthead span { font: 800 9px/1.2 var(--app-mono); letter-spacing: .14em; }
    .studio-masthead h1 { margin: 2px 0 0; font: italic 700 28px/1 var(--app-serif); }
    .studio-time { padding: 6px 8px; border: 1px solid var(--app-ink); background: var(--app-sheet); }
    .studio-intro, .studio-scenes, .studio-call, .studio-summary, .studio-wait { max-width: 430px; margin: 0 auto; padding: 44px 24px; }
    .studio-rule, .studio-scenes > div:first-child { color: var(--app-ink-3); font: 800 10px/1 var(--app-mono); letter-spacing: .16em; }
    .studio h2 { max-width: 360px; margin: 14px auto 12px; font: italic 700 42px/.98 var(--app-serif); }
    .studio-intro { text-align: center; }
    .studio-intro > p { max-width: 350px; margin: 0 auto 30px; color: var(--app-ink-2); font: 16px/1.6 var(--app-serif); }
    /* Soft journal action pair: pill geometry, sentence case, ink / outline. */
    .studio-primary { display: flex; align-items: center; justify-content: center; gap: 10px; width: 100%; min-height: 54px; padding: 0 22px; border-radius: 999px; border: 1px solid var(--app-ink); background: var(--app-ink); color: var(--app-paper) !important; font-size: var(--t-body) !important; font-weight: 600 !important; letter-spacing: .01em; text-transform: none; transition: background .16s ease, color .16s ease; }
    .studio-primary:active { background: var(--app-paper-2); color: var(--app-ink) !important; }
    .studio-primary:disabled { opacity: .5; }
    .studio-secondary { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 54px; margin-top: 12px; padding: 0 22px; border-radius: 999px; border: 1px solid var(--app-ink); background: transparent; color: var(--app-ink); text-decoration: none; font-size: var(--t-body) !important; font-weight: 600 !important; letter-spacing: .01em; text-transform: none; transition: background .16s ease, color .16s ease; }
    .studio-secondary:active { background: var(--app-paper-2); color: var(--app-ink); }
    .press { transition: transform 120ms ease, opacity 120ms ease; }
    .press:active { transform: translateY(2px) scale(.99); opacity: .84; }
    .studio-scenes h2 { margin-left: 0; }
    .studio-scenes > button:not(.studio-text-button) { display: grid; gap: 5px; width: 100%; padding: 16px 4px; border: 0; border-top: 1px solid var(--app-paper-3); background: transparent; text-align: left; }
    .studio-scenes button strong { font: italic 700 21px/1.1 var(--app-serif); }
    .studio-scenes button span { color: var(--app-ink-3); font-size: 12px; }
    .studio-text-button, .studio-end { display: block; margin: 20px auto 0; border: 0; background: transparent; color: var(--app-ink-3) !important; text-decoration: underline; }
    .studio-wait { min-height: 60svh; display: grid; place-items: center; align-content: center; gap: 18px; }
    .studio-spinner { width: 48px; height: 48px; border: 2px solid var(--app-paper-3); border-top-color: var(--app-ink); border-radius: 50%; animation: studio-spin .7s linear infinite; }
    .studio-cast { display: flex; align-items: center; gap: 12px; padding-bottom: 14px; border-bottom: 1px solid var(--app-paper-3); }
    .studio-portrait { position: relative; width: 58px; height: 58px; overflow: hidden; border: 1px solid var(--app-ink); background: var(--app-yellow); }
    .studio-portrait img { object-fit: cover; object-position: top center; }
    .studio-portrait span { width: 100%; height: 100%; display: grid; place-items: center; font: 900 16px/1 var(--app-mono); }
    .studio-cast > div:last-child { display: grid; }
    .studio-cast span, .studio-summary aside span, .studio-corrections > span { color: var(--app-ink-3); font: 800 9px/1.2 var(--app-mono); letter-spacing: .14em; }
    .studio-cast strong { margin-top: 3px; font: italic 700 22px/1 var(--app-serif); }
    .studio-cast em { margin-top: 3px; color: var(--app-ink-2); font: 12px/1.2 var(--app-serif); }
    .studio-meter { position: relative; height: 250px; margin: 24px 0 14px; display: flex; align-items: center; justify-content: center; gap: 6px; overflow: hidden; border: 1px solid var(--app-ink); background: var(--app-sheet); }
    .studio-meter i { width: 7px; height: 20%; background: var(--studio-accent); opacity: .55; transform: scaleY(.3); }
    .studio-meter.speaking i, .studio-meter.listening i { animation: studio-wave .9s ease-in-out infinite alternate; }
    .studio-meter i:nth-child(2n) { animation-delay: -180ms; }
    .studio-meter i:nth-child(3n) { animation-delay: -360ms; }
    .studio-seal { position: absolute; width: 94px; height: 94px; display: grid; place-items: center; border: 2px solid var(--app-ink); border-radius: 50%; background: var(--app-paper); }
    .studio-meter.processing .studio-seal { animation: studio-pulse .6s ease-in-out infinite alternate; }
    .studio-status { margin: 0 0 20px; text-align: center; color: var(--app-ink-2); font: italic 17px/1.2 var(--app-serif); }
    .studio-call blockquote { margin: 0 0 20px; padding: 14px 16px; border-left: 3px solid var(--studio-accent); background: var(--app-paper-2); font: italic 18px/1.4 var(--app-serif); }
    .studio-controls { display: flex; align-items: center; justify-content: center; gap: 24px; }
    .studio-controls button { width: 48px; height: 48px; display: grid; place-items: center; border: 1px solid var(--app-ink); background: var(--app-sheet); }
    .studio-controls .studio-mic { width: 76px; height: 76px; border: 2px solid var(--app-ink); border-radius: 50%; background: var(--app-yellow); }
    .studio-controls button:disabled { opacity: .42; }
    .studio-mic-error { max-width: 340px; margin: 16px auto 0; padding: 10px 12px; border-left: 3px solid var(--app-red); background: var(--app-paper-2); color: var(--app-ink-2); font: 14px/1.45 var(--app-serif); text-align: left; }
    .studio-filed { display: inline-block; padding: 7px 10px; border: 2px solid var(--app-blue); color: var(--app-blue); transform: rotate(-2deg); font: 900 11px/1 var(--app-mono); letter-spacing: .12em; animation: studio-thud 120ms ease-out both; }
    .studio-summary h2 { margin-left: 0; }
    .studio-honest { color: var(--app-ink-2); font: italic 17px/1.5 var(--app-serif); }
    .studio-summary dl { display: grid; grid-template-columns: 1fr 1fr; margin: 24px 0; border-top: 1px solid var(--app-ink); border-left: 1px solid var(--app-ink); }
    .studio-summary dl div { min-height: 78px; padding: 12px; border-right: 1px solid var(--app-ink); border-bottom: 1px solid var(--app-ink); background: var(--app-sheet); }
    .studio-summary dt { color: var(--app-ink-3); font: 800 9px/1 var(--app-mono); letter-spacing: .1em; text-transform: uppercase; }
    .studio-summary dd { margin: 8px 0 0; font: italic 700 22px/1.1 var(--app-serif); }
    .studio-summary aside { margin: 18px 0; padding: 14px 16px; border-left: 3px solid var(--app-blue); background: var(--app-paper-2); }
    .studio-summary aside p { margin: 7px 0 0; color: var(--app-ink-2); font: italic 16px/1.4 var(--app-serif); }
    .studio-corrections { margin: 18px 0; }
    .studio-corrections > div { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 12px; padding: 12px 0; border-top: 1px solid var(--app-paper-3); }
    .studio-corrections s { color: var(--app-ink-2); text-decoration-color: var(--app-red); text-decoration-thickness: 2px; }
    .studio-corrections strong { color: var(--app-ink); }
    .studio-corrections p { grid-column: 1/-1; margin: 0; color: var(--app-ink-3); font: italic 13px/1.4 var(--app-serif); }
    .studio-tomorrow { border-left-color: var(--app-yellow) !important; }
    .studio-modal { position: fixed; inset: 0; z-index: 90; display: grid; place-items: center; padding: 20px; background: color-mix(in srgb, var(--app-ink) 64%, transparent); }
    .studio-modal > div { position: relative; width: min(100%, 360px); padding: 24px; border: 1.5px solid var(--app-ink); background: var(--app-paper); }
    .studio-modal > div > button:first-child { position: absolute; top: 10px; right: 10px; border: 0; background: transparent; }
    .studio-modal h2 { margin: 0 0 10px; font-size: 30px; }
    .studio-modal p { color: var(--app-ink-2); font: 15px/1.5 var(--app-serif); }
    .studio-modal-actions { display: flex; gap: 10px; }
    .studio-modal-actions button { flex: 1; padding: 12px; border: 1px solid var(--app-ink); background: var(--app-sheet); }
    .studio-modal-actions button:last-child { background: var(--app-ink); color: var(--app-paper); }
    .studio-help { position: fixed; right: 16px; bottom: calc(16px + env(safe-area-inset-bottom)); width: 42px; height: 42px; display: grid; place-items: center; border: 1px solid var(--app-ink); border-radius: 50%; background: var(--app-sheet); color: var(--app-ink); }
    .studio-loading { min-height: 100svh; display: grid; place-items: center; background: var(--app-paper); }
    .studio-loading span { width: 40px; height: 40px; border: 2px solid var(--app-paper-3); border-top-color: var(--app-ink); border-radius: 50%; animation: studio-spin .7s linear infinite; }
    .print-in { animation: studio-print 180ms ease-out both; }
    @keyframes studio-spin { to { transform: rotate(360deg); } }
    @keyframes studio-print { from { opacity: 0; transform: translateY(4px); } }
    @keyframes studio-wave { to { transform: scaleY(3.5); opacity: .9; } }
    @keyframes studio-pulse { to { transform: scale(.94); } }
    @keyframes studio-thud { from { transform: rotate(-2deg) scale(1.18); opacity: .4; } }
    @media (prefers-reduced-motion: reduce) {
      .studio *, .studio-loading span { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
    }
  `}</style>;
}

/* Le Studio — the spoken call, on the Claude design (Atelier V2).
 *
 * WP-20: the page keeps its data flow, its state machine and every honest
 * failure state exactly as they were; only the chrome moved. It now sits
 * inside `AtelierV2Root` and is drawn with the system's own primitives —
 * `Action`, `IconAction`, `Chip`, `Surface`, `Stack`, `Notice`, `Dialog`,
 * `BottomSheet`, the Bauhaus shape icons — and the rules it still owns are
 * written `.av2 .studio-…`, in `--av2-*` tokens only.
 */

import Head from 'next/head';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect, useRef, useState } from 'react';
import { Eye, EyeOff, HelpCircle, Volume2, VolumeX } from 'lucide-react';
import toast from 'react-hot-toast';

import {
  Action,
  ArrowLeftIcon,
  ArrowRightIcon,
  AtelierV2Root,
  BottomSheet,
  Chip,
  Dialog,
  IconAction,
  MicIcon,
  Notice,
  SpinnerToken,
  StopIcon,
  Surface,
} from '@/components/atelier-v2/ui';
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
  idle: 'Appel ouvert',
  selecting: 'Appel ouvert',
  starting: 'Ligne en préparation',
  listening: 'Appel en cours',
  processing: 'Appel en cours',
  speaking: 'Appel en cours',
  ended: 'Appel classé',
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
  const learnerLanguage = useLearnerLanguage();
  const chrome = atelierChrome(learnerLanguage);
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
    return (
      <>
        <AtelierV2Root
          as="main"
          language={learnerLanguage}
          className="studio studio-loading"
          aria-label="Chargement du Studio"
          aria-busy="true"
        >
          <span className="studio-spinner" />
        </AtelierV2Root>
        <StudioStyles />
      </>
    );
  }

  const inCall = ['listening', 'processing', 'speaking'].includes(state.status);

  return (
    <>
      <Head><title>Le Studio · L’Atelier</title></Head>
      <AtelierV2Root as="main" language={learnerLanguage} className="av2-screen studio">
        <header className="av2-session__head studio-head">
          <Link href="/atelier" aria-label="Retour à La Une" className="av2-icon-btn studio-back">
            <ArrowLeftIcon size={18} />
          </Link>
          <div className="studio-head__main">
            {/* No call number exists in this flow — "N°" only ever appears before an actual number.
                The kicker states the call's real stage: a classed call is not "en cours". */}
            <p className="av2-label">Le Studio · {KICKER_BY_STATUS[state.status]}</p>
            <h1 className="av2-headline av2-headline--display">Le Studio</h1>
          </div>
          <Chip className="studio-time">{formatTime(state.elapsedSeconds)}</Chip>
        </header>

        <div className="av2-screen__body studio-body">
          {state.status === 'idle' && (
            <section className="studio-panel studio-intro">
              <p className="av2-label">Conversation · 5 minutes</p>
              <h2 className="av2-headline av2-headline--screen">Une voix, une vraie réponse.</h2>
              <p className="av2-body av2-body--lg studio-lede">
                La conversation reprend votre histoire et vos mots du jour. Les corrections
                restent discrètes : vous gardez le fil.
              </p>
              <div className="studio-actions">
                <Action tone="primary" icon={<MicIcon size={18} />} onClick={() => void startSession()}>
                  Commencer à parler
                </Action>
                <Action
                  tone="secondary"
                  onClick={() => setState((current) => ({ ...current, status: 'selecting' }))}
                >
                  Choisir une scène
                </Action>
              </div>
            </section>
          )}

          {state.status === 'selecting' && (
            <section className="studio-panel studio-scenes">
              <p className="av2-label">Scènes de rechange</p>
              <h2 className="av2-headline av2-headline--screen">Un décor précis</h2>
              <div className="studio-scene-list">
                {SCENES.map((scene) => (
                  <button
                    key={scene.id}
                    type="button"
                    className="av2-row studio-scene"
                    onClick={() => void startSession(scene.id)}
                  >
                    <span className="av2-row__main">
                      <strong className="av2-headline av2-headline--rule studio-scene__title">
                        {scene.title}
                      </strong>
                      <span className="av2-body studio-scene__note">{scene.note}</span>
                    </span>
                    <ArrowRightIcon size={16} />
                  </button>
                ))}
              </div>
              <div className="studio-actions">
                <Action tone="quiet" onClick={() => setState(INITIAL_STATE)}>Retour</Action>
              </div>
            </section>
          )}

          {state.status === 'starting' && (
            <section className="studio-wait" role="status" aria-live="polite" aria-busy="true">
              <SpinnerToken />
              <strong className="av2-headline av2-headline--rule">La ligne se prépare…</strong>
            </section>
          )}

          {inCall && (
            <section className="studio-panel studio-call">
              <CastHeader cast={state.castMember} />
              <div
                className="studio-meter"
                data-status={state.status}
                role="img"
                aria-label={METER_LABEL_BY_STATUS[state.status] || 'Appel en cours'}
              >
                {Array.from({ length: 11 }, (_, index) => <i key={index} />)}
                <span className="studio-seal" aria-hidden="true">
                  {state.status === 'listening' ? <MicIcon size={30} /> : <Volume2 size={30} />}
                </span>
              </div>
              <p className="studio-status" aria-live="polite">
                {state.status === 'speaking' && `${state.castMember?.name || 'Votre interlocuteur'} parle`}
                {state.status === 'listening' && 'À vous de parler'}
                {state.status === 'processing' && 'La réponse se compose'}
              </p>
              {(state.showText || isMuted) && state.aiResponse && (
                <blockquote className="av2-surface studio-quote" lang="fr">
                  {state.aiResponse}
                </blockquote>
              )}
              <div className="studio-controls">
                {/* Muting must not silence the character outright: the reply stays
                    readable for as long as the sound is off. */}
                <IconAction
                  label={isMuted ? 'Rétablir le son' : 'Couper le son'}
                  pressable
                  onClick={() => setIsMuted((value) => !value)}
                >
                  {isMuted ? <VolumeX size={18} /> : <Volume2 size={18} />}
                </IconAction>
                <IconAction
                  label={isRecording ? 'Arrêter l’enregistrement' : 'Commencer à parler'}
                  tone={isRecording || state.status === 'processing' ? 'recording' : 'action'}
                  pressable
                  className="studio-mic"
                  disabled={state.status === 'processing' || state.status === 'speaking'}
                  onClick={toggleRecording}
                >
                  {state.status === 'processing' || isRecording ? <StopIcon size={26} /> : <MicIcon size={26} />}
                </IconAction>
                <IconAction
                  label={state.showText ? 'Masquer le texte' : 'Afficher le texte'}
                  pressable
                  onClick={() => setState((current) => ({ ...current, showText: !current.showText }))}
                >
                  {state.showText ? <EyeOff size={18} /> : <Eye size={18} />}
                </IconAction>
              </div>
              {micError && (
                <div className="studio-mic-error">
                  <Notice tone="alert" live="status" shape="action">
                    <p>{micError}</p>
                  </Notice>
                </div>
              )}
              <div className="studio-actions studio-actions--end">
                <Action tone="quiet" onClick={() => setShowEndConfirm(true)}>Terminer l’appel</Action>
              </div>
            </section>
          )}

          {state.status === 'ended' && (
            <section className="studio-panel studio-summary">
              <Chip tone="story" className="studio-filed">BON À TIRER</Chip>
              <h2 className="av2-headline av2-headline--screen">Conversation transmise.</h2>
              {/* Counts are what really happened, so they have to read as French:
                  one tour, one mot, and "malgré 0 fautes" is not a sentence. */}
              <p className="av2-body av2-body--lg studio-honest">
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
              <dl className="studio-stats">
                <Surface shape="tile" className="studio-stat">
                  <dt className="av2-label">Durée</dt>
                  <dd className="av2-headline av2-headline--rule">{formatTime(state.elapsedSeconds)}</dd>
                </Surface>
                <Surface shape="tile" className="studio-stat">
                  <dt className="av2-label">Tours</dt>
                  <dd className="av2-headline av2-headline--rule">{state.turns}</dd>
                </Surface>
                <Surface shape="tile" className="studio-stat">
                  <dt className="av2-label">Mots produits</dt>
                  <dd className="av2-headline av2-headline--rule">{state.producedWords}</dd>
                </Surface>
                <Surface shape="tile" className="studio-stat">
                  <dt className="av2-label">Mots repris</dt>
                  <dd className="av2-headline av2-headline--rule">{state.dueWordsReused.join(' · ') || '—'}</dd>
                </Surface>
              </dl>
              {state.longestAnswer && (
                <Surface as="section" shape="tile" className="studio-aside">
                  <p className="av2-label">Votre plus longue réponse</p>
                  <p className="av2-fr studio-aside__body">« {state.longestAnswer} »</p>
                </Surface>
              )}
              {state.errors.length > 0 && (
                <section className="studio-corrections">
                  <p className="av2-label">Corrections discrètes</p>
                  {state.errors.map((error, index) => (
                    <div className="studio-correction" key={`${error.original}-${index}`}>
                      <s className="av2-correction__span">{error.original}</s>
                      <strong className="av2-correction__fix">{error.correction}</strong>
                      <p className="studio-correction__note">{error.explanation}</p>
                    </div>
                  ))}
                </section>
              )}
              <Surface as="section" shape="tile" className="studio-aside studio-tomorrow">
                <p className="av2-label">Pour demain</p>
                <p className="av2-fr studio-aside__body">{state.tomorrowFocus}</p>
              </Surface>
              <div className="studio-actions">
                <Action tone="primary" onClick={() => setState(INITIAL_STATE)}>Nouvel appel</Action>
                <Link className="av2-btn av2-btn--secondary" href="/atelier">Retour à La Une</Link>
              </div>
            </section>
          )}
        </div>

        <BottomSheet
          open={showHelp}
          eyebrow="Mode d’emploi"
          title="Le geste"
          onClose={() => setShowHelp(false)}
        >
          <p className="av2-body av2-body--lg">
            Touchez le micro, parlez, puis touchez le carré. L’œil révèle la dernière phrase si nécessaire.
          </p>
        </BottomSheet>

        <Dialog
          open={showEndConfirm}
          title="Classer cet appel ?"
          body="Votre conversation sera ajoutée au dossier du jour."
          onClose={() => setShowEndConfirm(false)}
          actions={(
            <>
              <Action tone="secondary" onClick={() => setShowEndConfirm(false)}>Continuer</Action>
              <Action tone="done" onClick={() => void endSession()}>Classer</Action>
            </>
          )}
        />

        {inCall && (
          <IconAction
            label="Aide"
            pressable
            className="studio-help"
            onClick={() => setShowHelp(true)}
          >
            <HelpCircle size={18} />
          </IconAction>
        )}
      </AtelierV2Root>
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
          : <span aria-hidden="true">{initials}</span>}
      </div>
      <div className="studio-cast__id">
        <span className="av2-label">En ligne</span>
        <strong className="av2-headline av2-headline--rule">{cast?.name || 'Conversation libre'}</strong>
        <em className="av2-body studio-cast__role">{cast?.role || 'Le Studio'}</em>
      </div>
    </div>
  );
}

/* ---- the page's own rules — `.av2 .studio-…`, `--av2-*` tokens only -------- */
function StudioStyles() {
  return <style jsx global>{`
    .av2.studio {
      min-height: 100svh;
      padding-bottom: calc(28px + var(--av2-safe-bottom));
    }
    .av2.studio-loading {
      display: grid;
      place-items: center;
      background: var(--av2-paper);
    }
    .av2 .studio-spinner {
      width: 40px;
      height: 40px;
      border: 2px solid var(--av2-line);
      border-top-color: var(--av2-ink);
      border-radius: 999px;
      animation: studio-spin 0.7s linear infinite;
    }

    /* masthead */
    .av2 .studio-head { gap: 12px; padding-top: calc(12px + env(safe-area-inset-top)); }
    .av2 .studio-head__main { flex: 1 1 auto; min-width: 0; }
    .av2 .studio-head__main p { margin: 0; }
    .av2 .studio-head__main h1 { margin: 2px 0 0; }
    .av2 a.studio-back { display: inline-grid; text-decoration: none; }
    .av2 .studio-time { flex: none; font-variant-numeric: tabular-nums; }

    /* the single column */
    .av2 .studio-body { max-width: 32rem; width: 100%; margin: 0 auto; }
    .av2 .studio-panel { display: flex; flex-direction: column; gap: 12px; min-width: 0; padding-top: 12px; }
    .av2 .studio-panel > p:first-child { margin: 0; }
    .av2 .studio-panel h2 { margin: 0; }
    .av2 .studio-lede { margin: 0; }
    .av2 .studio-actions { display: flex; flex-direction: column; gap: 10px; margin-top: 8px; min-width: 0; }
    .av2 .studio-actions--end { margin-top: 4px; }

    /* scenes */
    .av2 .studio-scene-list { display: flex; flex-direction: column; gap: 8px; }
    .av2 .studio-scene {
      border: 0;
      background: var(--av2-card);
      border-radius: var(--av2-r-tile);
      box-shadow: 0 var(--av2-press-md) 0 var(--av2-line-2);
      font: inherit;
      text-align: left;
      cursor: pointer;
      transition: transform var(--av2-press-dur), box-shadow var(--av2-press-dur);
    }
    .av2 .studio-scene:active { transform: translateY(var(--av2-press-md)); box-shadow: 0 0 0 transparent; }
    .av2 .studio-scene .av2-row__main { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
    .av2 .studio-scene__title { display: block; font-weight: 600; }
    .av2 .studio-scene__note { color: var(--av2-muted); }

    /* the line preparing */
    .av2 .studio-wait {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 14px;
      min-height: 50svh;
    }

    /* the live call */
    .av2 .studio-cast {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--av2-line);
    }
    .av2 .studio-portrait {
      position: relative;
      flex: none;
      width: 56px;
      height: 56px;
      overflow: hidden;
      border-radius: var(--av2-r-pill);
      background: var(--av2-yellow);
      color: var(--av2-on-yellow);
    }
    .av2 .studio-portrait img { object-fit: cover; object-position: top center; }
    .av2 .studio-portrait span {
      width: 100%;
      height: 100%;
      display: grid;
      place-items: center;
      font-size: var(--av2-t-body);
      font-weight: 700;
    }
    .av2 .studio-cast__id { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .av2 .studio-cast__role { font-style: italic; color: var(--av2-muted); }

    .av2 .studio-meter {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      height: 220px;
      margin: 4px 0;
      overflow: hidden;
      border-radius: var(--av2-r-hero);
      background: var(--av2-card);
    }
    .av2 .studio-meter i { width: 7px; height: 20%; border-radius: 4px; background: var(--av2-blue); opacity: 0.55; transform: scaleY(0.3); }
    .av2 .studio-meter[data-status='listening'] i,
    .av2 .studio-meter[data-status='speaking'] i { animation: studio-wave 0.9s ease-in-out infinite alternate; }
    .av2 .studio-meter i:nth-child(2n) { animation-delay: -180ms; }
    .av2 .studio-meter i:nth-child(3n) { animation-delay: -360ms; }
    .av2 .studio-seal {
      position: absolute;
      width: 92px;
      height: 92px;
      display: grid;
      place-items: center;
      border-radius: 999px;
      background: var(--av2-paper);
      color: var(--av2-ink);
    }
    .av2 .studio-meter[data-status='processing'] .studio-seal { animation: studio-pulse 0.6s ease-in-out infinite alternate; }
    .av2 .studio-status {
      margin: 0;
      text-align: center;
      font-family: var(--av2-serif);
      font-style: italic;
      font-size: var(--av2-t-rule);
      color: var(--av2-ink-2);
    }
    .av2 blockquote.studio-quote {
      margin: 0;
      padding: 14px 16px;
      font-family: var(--av2-serif);
      font-style: italic;
      font-size: var(--av2-t-option);
      line-height: 1.4;
      color: var(--av2-ink);
    }
    .av2 .studio-controls { display: flex; align-items: center; justify-content: center; gap: 22px; }
    .av2 .studio-controls .studio-mic { width: 76px; height: 76px; border-radius: 999px; }
    .av2 .studio-mic-error { min-width: 0; }

    /* the recap */
    .av2 .studio-filed { align-self: flex-start; font-weight: 700; letter-spacing: 0.08em; }
    .av2 .studio-honest { margin: 0; font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-body); }
    .av2 .studio-stats {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin: 6px 0 0;
    }
    .av2 .studio-stat { min-height: 76px; }
    .av2 .studio-stat dd { margin: 6px 0 0; overflow-wrap: anywhere; }
    .av2 .studio-aside { border-left: 3px solid var(--av2-blue); }
    .av2 .studio-aside p { margin: 0; }
    .av2 .studio-aside__body { margin-top: 6px !important; font-style: italic; color: var(--av2-ink-2); }
    .av2 .studio-tomorrow { border-left-color: var(--av2-yellow); }
    .av2 .studio-corrections { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
    .av2 .studio-corrections > p { margin: 0; }
    .av2 .studio-correction {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px 12px;
      padding: 12px 14px;
      border-radius: var(--av2-r-card);
      background: var(--av2-card);
      min-width: 0;
    }
    .av2 .studio-correction s { text-decoration-color: var(--av2-red); text-decoration-thickness: 2px; }
    .av2 .studio-correction__note {
      grid-column: 1 / -1;
      margin: 0;
      font-size: var(--av2-t-meta);
      line-height: 1.45;
      font-style: italic;
      color: var(--av2-muted);
    }

    /* the floating help affordance */
    .av2 .studio-help {
      position: fixed;
      right: 16px;
      bottom: calc(16px + var(--av2-safe-bottom));
      z-index: 40;
    }

    @keyframes studio-spin { to { transform: rotate(360deg); } }
    @keyframes studio-wave { to { transform: scaleY(3.5); opacity: 0.9; } }
    @keyframes studio-pulse { to { transform: scale(0.94); } }
    @media (prefers-reduced-motion: reduce) {
      .av2.studio *, .av2 .studio-spinner { animation: none !important; transition: none !important; }
    }
  `}</style>;
}

/* Les appels · /appel — someone from the story is on the phone.

   Own-shell and immersive, like /radio: the caller's face, the clock, their line
   spoken in their voice (the text only on request: a call is listening), one press
   held to talk, «Écrire plutôt» for typing, and the red «Raccrocher».

   Reached from the ringing card on the Atelier home (components/appels/IncomingCall).

   Query:
     ?mock=1   DEV ONLY (never in a production build): the in-memory client of
               lib/appels-mock.ts. ?lang=de|en|fr, ?state=ringing|missed. */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { useCallRecorder } from '@/components/appels/useCallRecorder';
import type { ResolvedClip } from '@/components/atelier-v2/journey/line-audio';
import { useLineVoice, type VoiceLine } from '@/components/atelier-v2/journey/useLineVoice';
import { Action, AtelierV2Root, MicIcon, Skeleton, StateBlock } from '@/components/atelier-v2/ui';
import {
  appelsClient,
  appelsCopy,
  callClock,
  callerPortrait,
  lastCallerTurn,
  type AppelsClient,
  type Call,
} from '@/lib/appels-api';
import { frenchSpacing } from '@/lib/french-typography';
import { enterImmersiveSurface } from '@/lib/immersive-surface';
import { useChromeLanguage } from '@/lib/learner-language';
import { getLineAudioClip } from '@/services/daily-journey';

const HOME = '/atelier';

type PageState = { kind: 'loading' } | { kind: 'none' } | { kind: 'error' } | { kind: 'call'; call: Call };

function queryString(value: string | string[] | undefined): string | null {
  const one = Array.isArray(value) ? value[0] : value;
  return one && one.trim() ? one.trim() : null;
}

export default function AppelPage() {
  const router = useRouter();
  const chrome = useChromeLanguage();
  const mock = process.env.NODE_ENV !== 'production' && router.query.mock === '1';
  const langParam = queryString(router.query.lang);
  const language = mock && langParam ? langParam : chrome;
  const copy = appelsCopy(language);
  const [client, setClient] = useState<AppelsClient | null>(null);
  const [state, setState] = useState<PageState>({ kind: 'loading' });
  const [busy, setBusy] = useState(false);
  const [showText, setShowText] = useState(false);
  const [typing, setTyping] = useState(false);
  const [draft, setDraft] = useState('');
  const [failure, setFailure] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!router.isReady) return;
    let alive = true;
    if (process.env.NODE_ENV !== 'production' && mock) {
      const start = queryString(router.query.state) ?? 'ringing';
      void import('@/lib/appels-mock').then(({ createMockAppelsClient }) => {
        if (alive) setClient(createMockAppelsClient({ start, latency: 500 }));
      });
    } else {
      setClient(appelsClient());
    }
    return () => {
      alive = false;
    };
    // The client is built once per page load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.isReady, mock]);

  const load = useCallback(async () => {
    if (!client) return;
    setState({ kind: 'loading' });
    try {
      const call = await client.today();
      setState(call ? { kind: 'call', call } : { kind: 'none' });
    } catch {
      setState({ kind: 'error' });
    }
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  const call = state.kind === 'call' ? state.call : null;
  useEffect(() => (call ? enterImmersiveSurface() : undefined), [Boolean(call)]); // eslint-disable-line react-hooks/exhaustive-deps

  // The clock runs while the call is on.
  const live = call?.status === 'live';
  useEffect(() => {
    if (!live) return undefined;
    const started = Date.now() - seconds * 1000;
    const handle = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 500);
    return () => clearInterval(handle);
    // Restarted only when the call goes live or ends.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live]);

  // Each caller line has its own clip (or none: the device's French voice reads it).
  const clips = useRef<Map<string, string>>(new Map());
  const resolve = useCallback(async (line: VoiceLine): Promise<ResolvedClip | null> => {
    const clipId = clips.current.get(line.key);
    if (!clipId || mock) return null;
    try {
      const url = URL.createObjectURL(await getLineAudioClip(clipId));
      return { url, release: () => URL.revokeObjectURL(url) };
    } catch {
      return null;
    }
  }, [mock]);
  const voice = useLineVoice({ resolve });

  const lineFor = useCallback(
    (key: string, text: string, clipId?: string | null): VoiceLine => {
      if (clipId) clips.current.set(key, clipId);
      return { key, text_fr: text, character_id: call?.caller.id ?? null };
    },
    [call?.caller.id],
  );

  // A new caller line says itself once, as a phone would.
  const last = lastCallerTurn(call);
  const lastKey = call && last ? `${call.id}:${last.index}` : null;
  const spokenRef = useRef<string | null>(null);
  useEffect(() => {
    if (!call || !last || !lastKey || call.status === 'missed' || spokenRef.current === lastKey) return;
    spokenRef.current = lastKey;
    voice.speak(lineFor(lastKey, last.turn.text_fr, last.turn.clip_id));
    // Keyed on the line, not on the voice object.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastKey]);

  const act = useCallback(
    async (run: () => Promise<Call>) => {
      setBusy(true);
      setFailure(null);
      try {
        const next = await run();
        setState({ kind: 'call', call: next });
      } catch {
        setFailure(copy.error);
      } finally {
        setBusy(false);
      }
    },
    [copy.error],
  );

  const send = useCallback(
    (text: string, mode: 'text' | 'voice') => {
      if (!client || !call || !text.trim()) return;
      voice.stop();
      setDraft('');
      void act(() => client.say(call.id, text.trim(), mode));
    },
    [act, call, client, voice],
  );

  const recorder = useCallRecorder(live && !mock ? call!.id : null, (text) => send(text, 'voice'));
  const mockTalk = useCallback(() => send('Oui, ça va bien. Et toi ?', 'voice'), [send]);

  const exit = useCallback(() => {
    voice.stop();
    void router.push(HOME);
  }, [router, voice]);

  const portrait = callerPortrait(call);
  const name = call?.caller.name ?? '';
  const transcript = useMemo(() => call?.turns ?? [], [call]);

  let body: React.ReactNode;
  if (call?.status === 'ringing') {
    body = (
      <section className="ap-ring" aria-live="polite">
        <Face src={portrait} name={name} ringing />
        <h1 className="ap-title">{copy.calling(name)}</h1>
        <p className="ap-hint">{copy.calling_hint}</p>
        <div className="ap-ring__actions">
          <Action tone="primary" pending={busy} pendingLabel={copy.listening} onClick={() => void act(() => client!.answer(call.id))}>
            {copy.answer}
          </Action>
          <Action disabled={busy} onClick={() => void act(() => client!.decline(call.id))}>
            {copy.decline}
          </Action>
        </div>
      </section>
    );
  } else if (call?.status === 'live') {
    const recording = recorder.phase === 'recording';
    const waiting = busy || recorder.phase === 'transcribing';
    body = (
      <section className="ap-live">
        <Face src={portrait} name={name} speaking={Boolean(voice.speakingKey)} />
        <p className="ap-name">{name}</p>
        <p className="ap-clock" aria-label={callClock(seconds)}>{callClock(seconds)}</p>
        <div className="ap-line">
          {waiting ? (
            <p className="ap-hint" role="status">{copy.thinking}</p>
          ) : last ? (
            <>
              <button
                type="button"
                className="ap-link"
                onClick={() => (voice.speakingKey ? voice.stop() : voice.speak(lineFor(lastKey!, last.turn.text_fr, last.turn.clip_id)))}
              >
                {voice.speakingKey ? copy.stop : copy.play}
              </button>
              <button type="button" className="ap-link" onClick={() => setShowText((value) => !value)}>
                {showText ? copy.hide_text : copy.show_text}
              </button>
            </>
          ) : null}
        </div>
        {showText && <Transcript turns={transcript} name={name} you={copy.you} />}
        <p className="ap-meta">{copy.turns_left(call.turns_left)}</p>
        {failure && <p className="ap-failure" role="alert">{failure}</p>}
        {recorder.failure && (
          <p className="ap-failure" role="alert">
            {recorder.failure === 'empty' ? copy.empty : recorder.failure === 'failed' ? copy.error : copy.mic_refused}
          </p>
        )}
        {typing || (recorder.failure && recorder.failure !== 'empty' && recorder.failure !== 'failed') ? (
          <form
            className="ap-type"
            onSubmit={(event) => {
              event.preventDefault();
              send(draft, 'text');
            }}
          >
            <input
              className="ap-type__field"
              lang="fr"
              autoFocus
              value={draft}
              placeholder={copy.placeholder}
              onChange={(event) => setDraft(event.target.value)}
              disabled={waiting}
            />
            <Action tone="primary" inline type="submit" disabled={waiting || !draft.trim()}>
              {copy.send}
            </Action>
          </form>
        ) : (
          <button
            type="button"
            className="ap-talk"
            data-recording={recording ? '' : undefined}
            disabled={waiting}
            aria-label={copy.talk}
            onPointerDown={(event) => {
              event.preventDefault();
              voice.stop();
              if (mock) return;
              void recorder.start();
            }}
            onPointerUp={() => (mock ? mockTalk() : recorder.stop())}
            onPointerLeave={() => recording && recorder.stop()}
            onContextMenu={(event) => event.preventDefault()}
          >
            <MicIcon size={28} />
            <span>{recording ? copy.talking : copy.talk}</span>
          </button>
        )}
        <div className="ap-live__foot">
          {!typing && (
            <button type="button" className="ap-link" onClick={() => setTyping(true)}>
              {copy.write}
            </button>
          )}
          <button type="button" className="ap-hangup" disabled={busy} onClick={() => void act(() => client!.hangUp(call.id))}>
            {copy.hang_up}
          </button>
        </div>
      </section>
    );
  } else if (call?.status === 'missed') {
    const key = `${call.id}:voicemail`;
    body = (
      <section className="ap-end">
        <Face src={portrait} name={name} />
        <h1 className="ap-title">{copy.voicemail_title(name)}</h1>
        {call.voicemail && (
          <>
            <Action
              tone="primary"
              onClick={() =>
                voice.speakingKey === key ? voice.stop() : voice.speak(lineFor(key, call.voicemail!.text_fr, call.voicemail!.clip_id))
              }
            >
              {voice.speakingKey === key ? copy.stop : copy.play}
            </Action>
            <button type="button" className="ap-link" onClick={() => setShowText((value) => !value)}>
              {showText ? copy.hide_text : copy.show_text}
            </button>
            {showText && <p className="ap-said" lang="fr">{frenchSpacing(call.voicemail.text_fr)}</p>}
          </>
        )}
        <Action onClick={exit}>{copy.back_home}</Action>
      </section>
    );
  } else if (call?.status === 'ended') {
    body = (
      <section className="ap-end">
        <Face src={portrait} name={name} />
        <h1 className="ap-title">{copy.ended_title(name)}</h1>
        <p className="ap-hint">{copy.ended_body}</p>
        {call.reason_en && (
          <p className="ap-why">
            <span>{copy.why}</span> {call.reason_en}
          </p>
        )}
        <Transcript turns={transcript} name={name} you={copy.you} />
        <Action tone="primary" onClick={exit}>{copy.back_home}</Action>
      </section>
    );
  } else if (state.kind === 'none') {
    body = <StateBlock tone="empty" title={copy.page_title} body={copy.calling_hint} action={{ label: copy.back_home, onSelect: exit }} />;
  } else if (state.kind === 'error') {
    body = <StateBlock tone="error" title={copy.error} body="" action={{ label: copy.retry, onSelect: () => void load() }} />;
  } else {
    body = (
      <div className="ap-loading" role="status" aria-busy="true">
        <Skeleton height={140} />
        <Skeleton height={18} />
      </div>
    );
  }

  return (
    <>
      <Head>
        <title>{copy.page_title}</title>
      </Head>
      <AtelierV2Root as="main" language={language} className="ap-page" aria-label={copy.page_title} data-status={call?.status}>
        {body}
        {mock && <p className="ap-mock">mock</p>}
      </AtelierV2Root>
    </>
  );
}

function Face({ src, name, ringing = false, speaking = false }: { src: string | null; name: string; ringing?: boolean; speaking?: boolean }) {
  return (
    <div className="ap-face" data-ringing={ringing ? '' : undefined} data-speaking={speaking ? '' : undefined}>
      {src ? <img src={src} alt={name} /> : <span aria-hidden="true">{name.slice(0, 1)}</span>}
    </div>
  );
}

function Transcript({ turns, name, you }: { turns: Call['turns']; name: string; you: string }) {
  return (
    <ol className="ap-transcript">
      {turns.map((turn, index) => (
        <li key={index} className="ap-transcript__line" data-who={turn.who}>
          <span className="ap-transcript__who">{turn.who === 'caller' ? name : you}</span>
          <p lang="fr">{frenchSpacing(turn.text_fr)}</p>
        </li>
      ))}
    </ol>
  );
}

/**
 * «Papier · la voix» (2026-11-22) · the plumbing the players share.
 *
 *  * `VoixProvider` — the page's client (the API, or the dev mock). No provider, or the switch
 *    off (the manifest is a 404): nothing here does anything and the players are as before.
 *  * `useVoixSession(id)` — the session's manifest and the `resolve` the player gives
 *    `useLineVoice`: a line the session may speak gets its server clip (in the server's voice for
 *    that line); any other line, and every line when clips cannot be made, the device's voice.
 *    A clip that cannot be had marks the session `failed`: every text then shows at once.
 *  * `VoixScope` — inside a player: which counter lines are still heard before they are read,
 *    and the hooks the bubble, the lead and the dictée read (`useVxVeil`, `useVxReplay`,
 *    `useVoixScope`). A line played to its end, or opened with «Lire», stays read.
 */

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import type { LineVoice, VoiceLine } from '@/components/atelier-v2/journey/useLineVoice';
import type { ResolvedClip } from '@/components/atelier-v2/journey/line-audio';
import { autoplayKey, sessionAutoplayLedger } from '@/components/atelier-v2/journey/voice-autoplay';
import { voicesAloud } from '@/lib/voice-preference';
import type { VoixClient, VxManifest } from '@/lib/revue-voix';
import type { RvLanguage } from '@/lib/revue-types';

import { voixCopy, type VoixCopy } from './voix-copy';
import { anyVeiled, findLine, heardKey, isVeiled, mayAutoplay, readRevealed, writeRevealed, type VeilState } from './voix-model';

const ClientContext = createContext<VoixClient | null>(null);

export function VoixProvider({ client, children }: { client: VoixClient | null; children: React.ReactNode }) {
  return <ClientContext.Provider value={client}>{children}</ClientContext.Provider>;
}

export function useVoixClient(): VoixClient | null {
  return useContext(ClientContext);
}

// ---------------------------------------------------------------------------
// A gesture on this page: the browser lets a page play sound only after one
// ---------------------------------------------------------------------------

let gestured = false;
let listening = false;

function watchGestures(): void {
  if (listening || typeof document === 'undefined') return;
  listening = true;
  const mark = () => {
    gestured = true;
  };
  document.addEventListener('pointerdown', mark, { capture: true, passive: true });
  document.addEventListener('keydown', mark, { capture: true });
}

export function hadGesture(): boolean {
  if (gestured) return true;
  const activation = typeof navigator !== 'undefined' ? (navigator as Navigator & { userActivation?: { hasBeenActive?: boolean } }).userActivation : undefined;
  return Boolean(activation?.hasBeenActive);
}

// ---------------------------------------------------------------------------
// The session
// ---------------------------------------------------------------------------

export type VoixSession = {
  manifest: VxManifest | null;
  failed: boolean;
  resolve: (line: VoiceLine) => Promise<ResolvedClip | null>;
};

export function useVoixSession(sessionId: string): VoixSession {
  const client = useVoixClient();
  const [manifest, setManifest] = useState<VxManifest | null>(null);
  const [failed, setFailed] = useState(false);
  const manifestRef = useRef<VxManifest | null>(null);
  manifestRef.current = manifest;

  useEffect(() => {
    watchGestures();
  }, []);

  useEffect(() => {
    setManifest(null);
    setFailed(false);
    if (!client) return undefined;
    let alive = true;
    client
      .manifest(sessionId)
      .then((next) => {
        if (alive) setManifest(next);
      })
      .catch(() => {
        // The voice is an extra: the paper reads as before.
      });
    return () => {
      alive = false;
    };
  }, [client, sessionId]);

  const resolve = useCallback(
    async (line: VoiceLine): Promise<ResolvedClip | null> => {
      const current = manifestRef.current;
      if (!client || !current || current.audio !== 'ready') return null;
      const known = findLine(current, line.text_fr) ?? (current.dictee && current.dictee.textFr === line.text_fr ? current.dictee : null);
      if (!known) return null; // not the session's line: the device reads it, no request
      const clip = await client.resolver(sessionId)(line).catch(() => null);
      if (!clip) setFailed(true);
      return clip;
    },
    [client, sessionId],
  );

  return { manifest, failed, resolve };
}

// ---------------------------------------------------------------------------
// The player's scope
// ---------------------------------------------------------------------------

export type VoixScopeValue = {
  sessionId: string;
  manifest: VxManifest;
  failed: boolean;
  voice: LineVoice;
  copy: VoixCopy;
  /** The learner's mother tongue: the dictée's explanations. */
  motherTongue: RvLanguage;
  client: VoixClient;
  state: VeilState;
  reveal: (key: string) => void;
};

const ScopeContext = createContext<VoixScopeValue | null>(null);

function browserStorage(): Storage | null {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null;
  } catch {
    return null;
  }
}

export function useVoixScope(): VoixScopeValue | null {
  return useContext(ScopeContext);
}

export function VoixScope({
  session,
  voice,
  pending = [],
  chrome,
  motherTongue,
  children,
}: {
  session: VoixSession & { id: string };
  voice: LineVoice;
  /** The counter's lines still to be heard first (`pendingLines(view)`). */
  pending?: readonly string[];
  chrome: RvLanguage;
  motherTongue: RvLanguage;
  children: React.ReactNode;
}) {
  const client = useVoixClient();
  const [revealed, setRevealed] = useState<ReadonlySet<string>>(() => new Set());
  // A line heard or opened before a reload stays revealed (kept per session on this device).
  useEffect(() => {
    setRevealed(readRevealed(browserStorage(), session.id));
  }, [session.id]);
  const reveal = useCallback(
    (key: string) => {
      setRevealed((current) => {
        if (current.has(key)) return current;
        const next = new Set(Array.from(current).concat(key));
        writeRevealed(browserStorage(), session.id, next);
        return next;
      });
    },
    [session.id],
  );

  // A line played to its end (or stopped) has been heard: its words stay.
  const last = useRef<string | null>(null);
  useEffect(() => {
    const previous = last.current;
    last.current = voice.speakingKey;
    if (previous && previous !== voice.speakingKey && previous.startsWith('vx|')) reveal(previous);
  }, [reveal, voice.speakingKey]);

  const pendingKey = pending.join('\n');
  const value = useMemo<VoixScopeValue | null>(() => {
    if (!client || !session.manifest) return null;
    return {
      sessionId: session.id,
      manifest: session.manifest,
      failed: session.failed,
      voice,
      copy: voixCopy(chrome),
      motherTongue,
      client,
      state: { manifest: session.manifest, pending: pendingKey ? pendingKey.split('\n') : [], revealed, failed: session.failed },
      reveal,
    };
  }, [chrome, client, motherTongue, pendingKey, reveal, revealed, session.failed, session.id, session.manifest, voice]);

  return <ScopeContext.Provider value={value}>{children}</ScopeContext.Provider>;
}

// ---------------------------------------------------------------------------
// What a bubble asks
// ---------------------------------------------------------------------------

export type VxLineHandle = {
  key: string;
  speaking: boolean;
  play: () => void;
  read: () => void;
  progress: () => number | null;
  copy: VoixCopy;
};

function handleFor(scope: VoixScopeValue, speakerId: string, textFr: string): VxLineHandle {
  const key = heardKey(speakerId, textFr);
  const { voice } = scope;
  return {
    key,
    speaking: voice.speakingKey === key,
    play: () => voice.speak({ key, text_fr: textFr, character_id: speakerId }),
    read: () => scope.reveal(key),
    progress: () => (voice.speakingKey === key ? voice.progress?.() ?? null : null),
    copy: scope.copy,
  };
}

/** The line as a veil (heard before it is read), or null: its words show as before. */
export function useVxVeil(speakerId: string, textFr: string, past = false): VxLineHandle | null {
  const scope = useVoixScope();
  const veiled = Boolean(scope && !past && isVeiled(scope.state, speakerId, textFr));
  const handle = scope && veiled ? handleFor(scope, speakerId, textFr) : null;
  // Said once, unasked, when it comes in: after a gesture here, with «voices aloud» on.
  const key = handle?.key ?? null;
  const play = handle?.play;
  useEffect(() => {
    if (!key || !play) return;
    if (!mayAutoplay({ voicesAloud: voicesAloud(), gesture: hadGesture() })) return;
    if (scope?.voice.speakingKey) return;
    if (sessionAutoplayLedger.claim(autoplayKey('voix', key, textFr))) play();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return handle;
}

/** The line, when the session may speak it: tapping the speaker's face says it again. */
export function useVxReplay(speakerId: string, textFr: string): VxLineHandle | null {
  const scope = useVoixScope();
  if (!scope || !findLine(scope.manifest, textFr)) return null;
  return handleFor(scope, speakerId, textFr);
}

/**
 * Is any of these regulars' lines (`[speakerId, textFr]`) still waiting to be heard? The step
 * then says «listen first» rather than asking for the reaction its veil still hides.
 */
export function useVxListening(lines: readonly (readonly [string, string])[]): boolean {
  const scope = useVoixScope();
  return anyVeiled(scope?.state, lines);
}

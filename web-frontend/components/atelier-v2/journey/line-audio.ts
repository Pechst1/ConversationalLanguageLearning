/**
 * WP-91 «Les voix» — where a character's line gets its sound.
 *
 * Pure plumbing with the transport injected, so node tests can drive it:
 *
 *  * `createLineAudioResolver` asks the server for a line (`POST …/line-audio`),
 *    fetches the clip's bytes with the session, and hands `useLineVoice` a
 *    fresh object URL plus the `release` that revokes it. The *bytes* are kept
 *    for the session, per character and text, so a second play costs nothing
 *    — not even a request — while every URL is revoked when its playback ends.
 *  * `status: "disabled"`, a 404, a network error: `null`, and the device's
 *    French voice reads the line. Once the server says `disabled` it is not
 *    asked again this session.
 *  * `recallClipId` reads the authenticated clip path a listen_tap or
 *    dictation prompt carries.
 *  * `pickFrenchVoice` chooses the device voice: fr-FR first, then any French,
 *    and — when the device has several — the same one for the same character
 *    every time, so a voice belongs to a face even offline.
 *
 * Deliberately not here: anything that listens to the learner (WP-27).
 */

import type { LineAudioBody, LineAudioResult } from '@/types/daily-journey';

/** What `useLineVoice`'s `resolve` may return: a URL, or a URL it must release. */
export type ResolvedClip = { url: string; release?: () => void };

export type LineAudioTransport = {
  request: (body: LineAudioBody) => Promise<LineAudioResult>;
  fetchClip: (clipId: string) => Promise<Blob>;
};

export type ObjectUrls = {
  create: (blob: Blob) => string;
  revoke: (url: string) => void;
};

const browserUrls: ObjectUrls = {
  create: (blob) => URL.createObjectURL(blob),
  revoke: (url) => URL.revokeObjectURL(url),
};

/** The session's clips, by character and text. Bounded: a long session never hoards audio. */
export const LINE_AUDIO_CACHE_LIMIT = 60;

export type LineAudioCache = {
  blobs: Map<string, Promise<Blob | null>>;
  /** The server said `disabled`: the device voice for the rest of the session. */
  disabled: boolean;
};

export function createLineAudioCache(): LineAudioCache {
  return { blobs: new Map(), disabled: false };
}

/** The one cache the app shares; tests make their own. */
export const sessionLineAudioCache: LineAudioCache = createLineAudioCache();

export function lineAudioKey(line: { text_fr: string; character_id?: string | null }): string {
  return `${String(line.character_id || '').trim().toLowerCase()}|${line.text_fr.trim()}`;
}

function remember(cache: LineAudioCache, key: string, value: Promise<Blob | null>) {
  cache.blobs.delete(key);
  cache.blobs.set(key, value);
  while (cache.blobs.size > LINE_AUDIO_CACHE_LIMIT) {
    const oldest = cache.blobs.keys().next().value;
    if (oldest === undefined) break;
    cache.blobs.delete(oldest);
  }
}

/**
 * A resolver for `useLineVoice({ resolve })`: `null` means "use the device voice".
 * Concurrent asks for the same line share one request.
 */
export function createLineAudioResolver(
  transport: LineAudioTransport,
  options: { cache?: LineAudioCache; urls?: ObjectUrls } = {},
): (line: { text_fr: string; character_id?: string | null }) => Promise<ResolvedClip | null> {
  const cache = options.cache ?? sessionLineAudioCache;
  const urls = options.urls ?? browserUrls;

  return async (line) => {
    const text = line.text_fr.trim();
    if (!text || cache.disabled) return null;
    const key = lineAudioKey(line);
    let pending = cache.blobs.get(key);
    if (pending) {
      remember(cache, key, pending); // most recently used
    } else {
      pending = (async () => {
        const result = await transport.request({ text_fr: text, character_id: line.character_id ?? null });
        if (!result || result.status !== 'ready' || !result.clip_id) {
          if (result?.status === 'disabled') cache.disabled = true;
          return null;
        }
        return transport.fetchClip(result.clip_id);
      })().catch(() => {
        // A failure is not remembered: the next tap may find the network back.
        cache.blobs.delete(key);
        return null;
      });
      remember(cache, key, pending);
    }
    const blob = await pending;
    if (!blob) {
      // `disabled` is remembered by the flag; a missing clip is asked again later.
      if (cache.blobs.get(key) === pending) cache.blobs.delete(key);
      return null;
    }
    const url = urls.create(blob);
    let released = false;
    return {
      url,
      release: () => {
        if (released) return;
        released = true;
        urls.revoke(url);
      },
    };
  };
}

/**
 * The clip id in an authenticated recall clip path
 * (`/api/v1/daily-journeys/line-audio/{clip_id}`), or null for anything else.
 */
export function recallClipId(audioUrl: string | null | undefined): string | null {
  const match = /\/daily-journeys\/line-audio\/([^/?#]+)/.exec(String(audioUrl || ''));
  if (!match) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

/** A clip's bytes by id, for the session (listen_tap and dictation replay free). */
export function createClipLoader(
  fetchClip: (clipId: string) => Promise<Blob>,
  cache: Map<string, Promise<Blob | null>> = new Map(),
): (clipId: string) => Promise<Blob | null> {
  return (clipId) => {
    const held = cache.get(clipId);
    if (held) return held;
    const pending = fetchClip(clipId).catch(() => {
      cache.delete(clipId);
      return null;
    });
    cache.set(clipId, pending);
    return pending;
  };
}

type VoiceLike = { lang: string; name: string; localService?: boolean; default?: boolean };

function hash(value: string): number {
  let h = 0;
  for (let i = 0; i < value.length; i += 1) h = (h * 31 + value.charCodeAt(i)) >>> 0;
  return h;
}

/**
 * The device voice for a line: a fr-FR voice when there is one (any French
 * otherwise), the same one per character when there are several, and `null`
 * when the device has no French voice (the utterance's `lang` still asks).
 */
export function pickFrenchVoice<V extends VoiceLike>(
  voices: readonly V[],
  characterId?: string | null,
): V | null {
  const lang = (voice: V) => String(voice.lang || '').replace('_', '-').toLowerCase();
  const france = voices.filter((voice) => lang(voice) === 'fr-fr');
  const french = france.length ? france : voices.filter((voice) => lang(voice).startsWith('fr'));
  if (!french.length) return null;
  // Local voices first: they speak offline and without a network wait.
  const local = french.filter((voice) => voice.localService !== false);
  const pool = local.length ? local : french;
  const who = String(characterId || '').trim();
  if (!who) return pool.find((voice) => voice.default) ?? pool[0];
  const sorted = [...pool].sort((a, b) => a.name.localeCompare(b.name));
  return sorted[hash(who) % sorted.length];
}

/** How long a device utterance may take before its ring is taken down anyway. */
export function speechSafetyMs(text: string): number {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return 2500 + words * 650;
}

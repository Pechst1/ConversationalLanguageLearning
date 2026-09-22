/**
 * WP-76 — three small sounds: correct, wrong, day complete.
 *
 * Original tones (`scripts/generate-feel-sounds.py`), each under 20 KB, played
 * through Web Audio so a tap answers in the same frame once the buffers are
 * decoded.
 *
 * Default (decided in WP-76, changeable in Réglages → «Sons»):
 *   * **on in the iOS app.** It is a phone app used in short sessions, the
 *     sounds are quiet (≈ −9 dBFS), and the audio session is set to
 *     `ambient`, so the ringer switch silences them and the learner's music
 *     keeps playing — the platform's own "silent means silent" rule.
 *   * **off on the web.** A browser tab that starts making noise is a surprise
 *     in an office or a library, and the web has no ringer switch to honour.
 *
 * Nothing here throws: a device that cannot play simply stays quiet.
 */

import { isNativePlatform } from '@/lib/native-platform';

export type FeelSound = 'correct' | 'wrong' | 'complete';

export const SOUND_PREFERENCE_KEY = 'atelier.sounds';
export const FEEL_SOUNDS: FeelSound[] = ['correct', 'wrong', 'complete'];

const SOURCES: Record<FeelSound, string> = {
  correct: '/sounds/correct.wav',
  wrong: '/sounds/wrong.wav',
  complete: '/sounds/complete.wav',
};

/** The default before the learner has chosen: on in the app, off on the web. */
export function defaultSoundsEnabled(native: boolean = isNativePlatform()): boolean {
  return native;
}

export function readSoundPreference(): boolean | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = window.localStorage.getItem(SOUND_PREFERENCE_KEY);
    if (stored === 'on') return true;
    if (stored === 'off') return false;
  } catch {
    /* storage can be blocked; the default applies */
  }
  return null;
}

export function soundsEnabled(): boolean {
  if (typeof window === 'undefined') return false;
  return readSoundPreference() ?? defaultSoundsEnabled();
}

export function setSoundsEnabled(enabled: boolean): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(SOUND_PREFERENCE_KEY, enabled ? 'on' : 'off');
  } catch {
    /* a preference that cannot be stored lasts until the page closes */
  }
  if (enabled) preloadFeelSounds();
}

// ---------------------------------------------------------------------------
// Playback
// ---------------------------------------------------------------------------

type AudioContextCtor = typeof AudioContext;

let context: AudioContext | null = null;
const raw = new Map<FeelSound, Promise<ArrayBuffer | null>>();
const decoded = new Map<FeelSound, Promise<AudioBuffer | null>>();

function audioContextCtor(): AudioContextCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as { AudioContext?: AudioContextCtor; webkitAudioContext?: AudioContextCtor };
  return w.AudioContext ?? w.webkitAudioContext ?? null;
}

/**
 * Safari 16.4+ (and the iOS app's WKWebView) expose the Audio Session API.
 * `ambient` obeys the ringer switch and mixes with other audio instead of
 * pausing the learner's podcast for a 0.3 s chime.
 */
function preferAmbientSession() {
  try {
    const session = (navigator as Navigator & { audioSession?: { type: string } }).audioSession;
    if (session && session.type !== 'ambient') session.type = 'ambient';
  } catch {
    /* not supported: the platform default applies */
  }
}

function fetchRaw(kind: FeelSound): Promise<ArrayBuffer | null> {
  let pending = raw.get(kind);
  if (!pending) {
    pending =
      typeof fetch === 'function'
        ? fetch(SOURCES[kind])
            .then((response) => (response.ok ? response.arrayBuffer() : null))
            .catch(() => null)
        : Promise.resolve(null);
    raw.set(kind, pending);
  }
  return pending;
}

function ensureContext(): AudioContext | null {
  if (context) return context;
  const Ctor = audioContextCtor();
  if (!Ctor) return null;
  try {
    preferAmbientSession();
    context = new Ctor();
  } catch {
    context = null;
  }
  return context;
}

function decode(kind: FeelSound): Promise<AudioBuffer | null> {
  let pending = decoded.get(kind);
  if (!pending) {
    pending = fetchRaw(kind).then((bytes) => {
      const ctx = ensureContext();
      if (!bytes || !ctx) return null;
      // decodeAudioData detaches its input; decode a copy so a retry can reuse it.
      return new Promise<AudioBuffer | null>((resolve) => {
        try {
          const result = ctx.decodeAudioData(bytes.slice(0), (buffer) => resolve(buffer), () => resolve(null));
          if (result && typeof (result as Promise<AudioBuffer>).catch === 'function') {
            (result as Promise<AudioBuffer>).catch(() => resolve(null));
          }
        } catch {
          resolve(null);
        }
      });
    });
    decoded.set(kind, pending);
  }
  return pending;
}

/** Fetch the three files ahead of the first answer. Cheap: ~36 KB, cached. */
export function preloadFeelSounds(): void {
  if (typeof window === 'undefined' || !soundsEnabled()) return;
  for (const kind of FEEL_SOUNDS) void fetchRaw(kind);
}

/** Play one sound if the learner wants sounds and the page is in front. */
export function playFeelSound(kind: FeelSound): void {
  if (typeof window === 'undefined' || !soundsEnabled()) return;
  if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
  const ctx = ensureContext();
  if (!ctx) return;
  try {
    if (ctx.state === 'suspended') void ctx.resume();
  } catch {
    /* resumes on the next gesture */
  }
  void decode(kind).then((buffer) => {
    if (!buffer) return;
    try {
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      source.start();
    } catch {
      /* a device that cannot play stays quiet */
    }
  });
}

/**
 * The page's audio session, and the one exception to «silent means silent».
 *
 * WP-76 set the iOS audio session to `ambient` the first time a feel sound
 * plays (`lib/sound.ts`), so the ringer switch silences the chimes and the
 * learner's music keeps playing. But `navigator.audioSession.type` is one
 * setting for the whole page: WebKit turns it into a category *override*
 * (`MediaSessionManagerCocoa::updateSessionState`), so from that first chime
 * on, every `<audio>` and every browser voice is ambient too. On an iPhone
 * with the switch on silent, La Forge's «Anhören» — and every other button
 * that speaks a sentence — played nothing (2026-11-04).
 *
 * A voice the learner *asked for* with a tap is content, not a cue: like a
 * podcast or a video, it plays through the switch. So an asked voice holds the
 * session at `playback` while it sounds, and the page goes back to its resting
 * type (`ambient` once a chime has set it) when the last asked voice is done.
 * Voices that speak unasked (WP-91) keep the resting type.
 *
 * Nothing here throws: a platform without the Audio Session API (every browser
 * but Safari 16.4+ and the iOS app's WKWebView) is simply left alone.
 */

type SessionLike = { type: string };

function audioSession(): SessionLike | null {
  try {
    if (typeof navigator === 'undefined') return null;
    const session = (navigator as Navigator & { audioSession?: SessionLike }).audioSession;
    return session && typeof session === 'object' ? session : null;
  } catch {
    return null;
  }
}

function setType(type: string): void {
  const session = audioSession();
  if (!session) return;
  try {
    if (session.type !== type) session.type = type;
  } catch {
    /* an unknown type or a locked session: the platform default applies */
  }
}

/** Asked voices sounding now. */
let held = 0;
/** The type the page rests at between asked voices (`null`: the platform's own). */
let resting: string | null = null;
/** The type found when the first asked voice took the session. */
let before: string | null = null;

/**
 * The page's type between asked voices: `ambient` for the feel sounds. Applied
 * at once unless an asked voice is sounding; then it waits for that voice.
 */
export function setRestingSession(type: string): void {
  resting = type;
  if (held === 0) setType(type);
}

/**
 * Take the session for a voice the learner asked for. Returns the release,
 * which is safe to call more than once; the last release restores the
 * resting type.
 */
export function holdForAskedVoice(): () => void {
  if (held === 0) before = audioSession()?.type ?? null;
  held += 1;
  setType('playback');
  let released = false;
  return () => {
    if (released) return;
    released = true;
    held = Math.max(0, held - 1);
    if (held > 0) return;
    const back = resting ?? before;
    before = null;
    if (back) setType(back);
  };
}

/**
 * Play a clip the learner asked for (a tap on «Anhören», «Écouter»…). The
 * session is `playback` from before `play()` until the clip ends, pauses,
 * fails or is refused.
 */
export function playAskedVoice(player: HTMLAudioElement): Promise<void> {
  const release = holdForAskedVoice();
  for (const event of ['ended', 'pause', 'error', 'abort', 'emptied']) {
    try {
      player.addEventListener(event, release, { once: true });
    } catch {
      /* a stand-in without events: released on refusal only */
    }
  }
  let started: Promise<void> | undefined;
  try {
    started = player.play();
  } catch (error) {
    release();
    return Promise.reject(error);
  }
  return Promise.resolve(started).catch((error) => {
    release();
    throw error;
  });
}

/**
 * Speak a sentence the learner asked for in the browser's own voice, under the
 * same `playback` session. Returns false when the browser has no voice.
 */
export function speakAskedVoice(utterance: SpeechSynthesisUtterance): boolean {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return false;
  const release = holdForAskedVoice();
  const ownEnd = utterance.onend;
  const ownError = utterance.onerror;
  utterance.onend = function onEnd(event) {
    release();
    return ownEnd?.call(this, event);
  };
  utterance.onerror = function onError(event) {
    release();
    return ownError?.call(this, event);
  };
  try {
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  } catch {
    release();
    return false;
  }
  return true;
}

/** Test seam: forget every hold (the resting type, like the page's AudioContext, stays). */
export function resetAudioSessionForTests(): void {
  held = 0;
  before = null;
}

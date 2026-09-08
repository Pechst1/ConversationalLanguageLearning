/**
 * Native and browser lifecycle for the daily journey (WP-10).
 *
 * The app ships as a Capacitor WKWebView as well as a browser page, and this
 * build carries no `@capacitor/app` or `@capacitor/keyboard` plugin. Adding one
 * would be a native dependency change well outside a resilience package, so
 * every signal below is taken from a web API that WKWebView really implements:
 *
 *   background / foreground   `visibilitychange`, `pagehide`/`pageshow`,
 *                             and the Page Lifecycle `freeze`/`resume` events
 *   connectivity              `navigator.onLine` plus `online`/`offline`
 *   software keyboard         `window.visualViewport`
 *   safe areas                `env(safe-area-inset-*)`, already in globals.css
 *   audio interruption        `MediaStreamTrack` mute/unmute/ended — this is
 *                             what an incoming call does to a live capture
 *   audio route change        `navigator.mediaDevices.devicechange`
 *
 * Every installer returns its own teardown and is safe to call on the server,
 * where it becomes a no-op. The geometry decisions are pure functions so the
 * node harness can test them without a DOM.
 */

export type Teardown = () => void;

const noop: Teardown = () => {};

function hasWindow(): boolean {
  return typeof window !== 'undefined' && typeof document !== 'undefined';
}

// ---------------------------------------------------------------------------
// Foreground / background
// ---------------------------------------------------------------------------

export type LifecycleHandlers = {
  /** The app came back: revalidate against the server before trusting anything. */
  onResume?: (reason: 'visible' | 'pageshow' | 'resume' | 'online') => void;
  /** The app is going away and may not come back: persist now, synchronously. */
  onSuspend?: (reason: 'hidden' | 'pagehide' | 'freeze') => void;
};

/**
 * Observe the transitions that precede an app kill.
 *
 * iOS gives no warning before terminating a suspended WebView, so `pagehide`
 * and `visibilitychange → hidden` are the last moments a draft can be written.
 * Both are treated as "persist now"; neither is treated as "the session ended".
 */
export function installAppLifecycle(handlers: LifecycleHandlers): Teardown {
  if (!hasWindow()) return noop;
  const { onResume, onSuspend } = handlers;

  const onVisibility = () => {
    if (document.visibilityState === 'hidden') onSuspend?.('hidden');
    else onResume?.('visible');
  };
  const onPageHide = () => onSuspend?.('pagehide');
  const onPageShow = () => onResume?.('pageshow');
  const onFreeze = () => onSuspend?.('freeze');
  const onResumeEvent = () => onResume?.('resume');

  document.addEventListener('visibilitychange', onVisibility);
  window.addEventListener('pagehide', onPageHide);
  window.addEventListener('pageshow', onPageShow);
  // Page Lifecycle API: Chrome/Android fire these; Safari ignores them.
  document.addEventListener('freeze', onFreeze);
  document.addEventListener('resume', onResumeEvent);

  return () => {
    document.removeEventListener('visibilitychange', onVisibility);
    window.removeEventListener('pagehide', onPageHide);
    window.removeEventListener('pageshow', onPageShow);
    document.removeEventListener('freeze', onFreeze);
    document.removeEventListener('resume', onResumeEvent);
  };
}

// ---------------------------------------------------------------------------
// Connectivity
// ---------------------------------------------------------------------------

export function isOnline(): boolean {
  if (typeof navigator === 'undefined') return true;
  // `onLine` is only ever trustworthy when it says *false*; a true value still
  // needs a real request to confirm, which is why nothing here claims "synced".
  return navigator.onLine !== false;
}

export function installConnectivityWatch(onChange: (online: boolean) => void): Teardown {
  if (!hasWindow()) return noop;
  const online = () => onChange(true);
  const offline = () => onChange(false);
  window.addEventListener('online', online);
  window.addEventListener('offline', offline);
  return () => {
    window.removeEventListener('online', online);
    window.removeEventListener('offline', offline);
  };
}

// ---------------------------------------------------------------------------
// Software keyboard
// ---------------------------------------------------------------------------

/** A difference smaller than this is chrome or rounding, not a keyboard. */
export const KEYBOARD_MIN_INSET = 60;

/**
 * How much of the viewport the software keyboard is covering, in CSS pixels.
 *
 * Deliberately measured against a **baseline of the largest visual height seen
 * while nothing was focused**, not against `window.innerHeight`. Measuring in
 * the browser pane showed why: `innerHeight` was 812 while
 * `visualViewport.height` was 476 with no keyboard anywhere near — a viewport
 * that is emulated, scaled, or wrapped in browser chrome makes the two disagree
 * permanently, and an `innerHeight` comparison would then report a 336px
 * keyboard for the whole session and shove the layout around forever.
 *
 * The focus condition is the second half of the guard: a keyboard is only ever
 * up when something editable holds focus, so a viewport that shrinks for any
 * other reason cannot be mistaken for one.
 */
export function keyboardInsetFrom(input: {
  /** Largest visual height observed while no editable element was focused. */
  baselineHeight: number;
  visualHeight: number;
  editableFocused: boolean;
}): number {
  if (!input.editableFocused) return 0;
  const covered = input.baselineHeight - input.visualHeight;
  if (!Number.isFinite(covered)) return 0;
  return covered > KEYBOARD_MIN_INSET ? Math.round(covered) : 0;
}

/**
 * How far to scroll so the answer field *and* its primary action clear the
 * keyboard, without pushing the field itself off the top.
 *
 * Positive result means "scroll down by this many pixels". The clamp on
 * `fieldTop` is the point of the function: naively scrolling the button into
 * view moves the learner's own words off screen while they are typing them.
 */
export function keyboardScrollAdjustment(input: {
  /** Client-space y where the keyboard starts covering the page. */
  keyboardTop: number;
  fieldTop: number;
  fieldBottom: number;
  /** Bottom of the primary action, when there is one after the field. */
  actionBottom: number | null;
  margin?: number;
}): number {
  const margin = input.margin ?? 12;
  const needed =
    input.actionBottom === null
      ? input.fieldBottom
      : Math.max(input.fieldBottom, input.actionBottom);
  const overflow = needed + margin - input.keyboardTop;
  if (!Number.isFinite(overflow) || overflow <= 0) return 0;
  const headroom = Math.max(0, input.fieldTop - margin);
  return Math.round(Math.min(overflow, headroom));
}

export type KeyboardState = { inset: number; open: boolean };

/**
 * The inset `installKeyboardInsets` last published.
 *
 * Read from the DOM rather than recomputed so the focus guard and the layout
 * always agree about whether a keyboard is up — one calibrated measurement,
 * one answer.
 */
export function readKeyboardInset(): number {
  if (!hasWindow()) return 0;
  const raw = document.documentElement.style.getPropertyValue('--app-keyboard-inset');
  const value = parseFloat(raw);
  return Number.isFinite(value) ? value : 0;
}

/**
 * Publish the keyboard inset as `--app-keyboard-inset` and `data-keyboard`.
 *
 * A distinct variable from `viewport-metrics.ts`'s `--app-viewport-*`, which
 * measures the viewport but says nothing about what is covering it.
 */
export function installKeyboardInsets(onChange?: (state: KeyboardState) => void): Teardown {
  if (!hasWindow()) return noop;
  const root = document.documentElement;
  const visual = window.visualViewport;
  let timer = 0;
  let last = -1;
  /** Recalibrated whenever nothing is focused, so it follows rotation and chrome. */
  let baseline = visual?.height ?? window.innerHeight ?? 0;

  const measure = () => {
    timer = 0;
    const height = visual?.height ?? window.innerHeight ?? 0;
    const focused = isEditable(document.activeElement);
    if (!focused && height > baseline) baseline = height;
    const inset = keyboardInsetFrom({
      baselineHeight: baseline,
      visualHeight: height,
      editableFocused: focused,
    });
    if (inset === last) return;
    last = inset;
    root.style.setProperty('--app-keyboard-inset', `${inset}px`);
    if (inset > 0) root.dataset.keyboard = 'open';
    else delete root.dataset.keyboard;
    onChange?.({ inset, open: inset > 0 });
  };

  // A short timeout rather than `requestAnimationFrame`: rAF is throttled to
  // nothing in a backgrounded or offscreen WebView — measured here, where it
  // never fired at all — and the inset would then be stuck at its last value.
  const schedule = () => {
    if (timer) return;
    timer = window.setTimeout(measure, 50);
  };

  measure();
  window.addEventListener('resize', schedule);
  window.addEventListener('orientationchange', schedule);
  document.addEventListener('focusin', schedule);
  document.addEventListener('focusout', schedule);
  visual?.addEventListener('resize', schedule);
  visual?.addEventListener('scroll', schedule);

  return () => {
    if (timer) window.clearTimeout(timer);
    window.removeEventListener('resize', schedule);
    window.removeEventListener('orientationchange', schedule);
    document.removeEventListener('focusin', schedule);
    document.removeEventListener('focusout', schedule);
    visual?.removeEventListener('resize', schedule);
    visual?.removeEventListener('scroll', schedule);
    root.style.removeProperty('--app-keyboard-inset');
    delete root.dataset.keyboard;
  };
}

const EDITABLE = /^(input|textarea)$/i;

function isEditable(node: EventTarget | null): node is HTMLElement {
  const element = node as HTMLElement | null;
  if (!element || !element.tagName) return false;
  if (EDITABLE.test(element.tagName)) return true;
  return element.isContentEditable === true;
}

/**
 * The primary action for a field: the first enabled button that follows it in
 * document order *and* sits below it on screen.
 *
 * The geometric half of that rule is not decoration. Measured against the real
 * sign-in form, the first following button is the password reveal toggle, which
 * is positioned inside the field itself — scrolling to keep that visible would
 * do nothing about the submit button underneath it.
 */
export function actionAfter(field: HTMLElement, fieldBottom: number): HTMLElement | null {
  const buttons = Array.prototype.slice.call(
    document.querySelectorAll('button:not([disabled]), [type="submit"]:not([disabled])'),
  ) as HTMLElement[];
  for (let index = 0; index < buttons.length; index += 1) {
    const button = buttons[index];
    // DOCUMENT_POSITION_FOLLOWING === 4
    if ((field.compareDocumentPosition(button) & 4) === 0) continue;
    if (button.getBoundingClientRect().top >= fieldBottom - 1) return button;
  }
  return null;
}

/**
 * Keep the focused field and its primary action above the software keyboard.
 *
 * Generic on purpose: it keys off focus and document order, not off any
 * renderer's class names, so it keeps working when WP-07's markup is replaced
 * by the Claude-Design one.
 */
export function installKeyboardFocusGuard(delayMs = 180): Teardown {
  if (!hasWindow()) return noop;
  let timer = 0;

  const adjust = (field: HTMLElement) => {
    const visual = window.visualViewport;
    // Where the covered region starts, in the same client coordinates the
    // element rects below are measured in.
    const keyboardTop = (visual?.height ?? window.innerHeight) + (visual?.offsetTop ?? 0);
    const inset = readKeyboardInset();
    if (inset === 0) return;
    const fieldRect = field.getBoundingClientRect();
    const action = actionAfter(field, fieldRect.bottom);
    const actionRect = action ? action.getBoundingClientRect() : null;
    const delta = keyboardScrollAdjustment({
      keyboardTop,
      fieldTop: fieldRect.top,
      fieldBottom: fieldRect.bottom,
      actionBottom: actionRect ? actionRect.bottom : null,
    });
    if (delta > 0) window.scrollBy({ top: delta, behavior: 'smooth' });
  };

  const onFocusIn = (event: FocusEvent) => {
    if (!isEditable(event.target)) return;
    const field = event.target as HTMLElement;
    window.clearTimeout(timer);
    // The keyboard animates in; measuring before it settles reads zero inset.
    timer = window.setTimeout(() => adjust(field), delayMs);
  };

  document.addEventListener('focusin', onFocusIn);
  return () => {
    window.clearTimeout(timer);
    document.removeEventListener('focusin', onFocusIn);
  };
}

// ---------------------------------------------------------------------------
// Audio interruption and route changes
// ---------------------------------------------------------------------------

export type AudioInterruptionHandlers = {
  /** A call, Siri, or a lost route silenced the capture. The turn is not lost. */
  onInterrupted?: (reason: 'muted' | 'ended') => void;
  onResumed?: () => void;
  /** Headphones in or out: the capture may now be a different microphone. */
  onRouteChange?: () => void;
};

/**
 * Watch a live capture for the interruptions iOS actually produces.
 *
 * An incoming call mutes the track rather than erroring the recorder, so a
 * recorder that only listens for `onerror` records silence and then reports a
 * failure the learner cannot act on. Callers must treat an interruption as
 * "the learner still holds this turn", never as a wrong answer.
 */
export function observeAudioInterruptions(
  stream: MediaStream | null,
  handlers: AudioInterruptionHandlers,
): Teardown {
  if (!stream) return noop;
  const tracks = stream.getAudioTracks ? stream.getAudioTracks() : [];
  const onMute = () => handlers.onInterrupted?.('muted');
  const onEnded = () => handlers.onInterrupted?.('ended');
  const onUnmute = () => handlers.onResumed?.();
  tracks.forEach((track) => {
    track.addEventListener('mute', onMute);
    track.addEventListener('unmute', onUnmute);
    track.addEventListener('ended', onEnded);
  });

  const devices = typeof navigator !== 'undefined' ? navigator.mediaDevices : undefined;
  const onDeviceChange = () => handlers.onRouteChange?.();
  devices?.addEventListener?.('devicechange', onDeviceChange);

  return () => {
    tracks.forEach((track) => {
      track.removeEventListener('mute', onMute);
      track.removeEventListener('unmute', onUnmute);
      track.removeEventListener('ended', onEnded);
    });
    devices?.removeEventListener?.('devicechange', onDeviceChange);
  };
}

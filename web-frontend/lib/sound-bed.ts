/**
 * WP-145 «Ambiance» — the sound of the place under a story scene.
 *
 * Each place of the season has a bed: rain on the café window at Le Mistral,
 * the murmur of the canal market, the rumble of a métro platform, the quiet of
 * a flat. A bed is a 16 s stereo loop **synthesised here** (filtered noise,
 * slow periodic swells, a few events) — no audio file, no licence, no
 * download. The loop is seamless: every swell has a whole number of cycles in
 * the loop, the noise tail is cross-faded into its head, and events wrap.
 *
 * Under the voices: while a character's line plays the bed drops by 12 dB
 * (`DUCK_DB`) on a short ramp, and comes back slowly after. The scene fades it
 * in when it opens and out when it closes.
 *
 * Gates, all of them needed:
 *   * the «Sons» switch (`lib/sound.ts`) — the app's mute switch;
 *   * the learner's «Ambiance» setting — by default **on in the iOS app, off on
 *     the web** (the public browser: a tab that starts making noise in an
 *     office is a surprise), the same default as «Sons» and the voices;
 *   * the learner's first gesture in the scene (autoplay policy): no
 *     AudioContext is created before it, and the context is the one the feel
 *     sounds use (`sharedAudioContext`), resumed inside the gesture;
 *   * the page in front: hiding the page stops the bed and suspends the
 *     context.
 *
 * Nothing here throws: a device that cannot play simply stays quiet.
 */

import { isNativePlatform } from '@/lib/native-platform';
import { existingAudioContext, sharedAudioContext, soundsEnabled } from '@/lib/sound';

// ---------------------------------------------------------------------------
// Places → beds
// ---------------------------------------------------------------------------

export type BedId = 'cafe' | 'market' | 'canal' | 'metro' | 'room' | 'stairwell' | 'office' | 'wind';

export const BED_IDS: BedId[] = ['cafe', 'market', 'canal', 'metro', 'room', 'stairwell', 'office', 'wind'];

/** The quiet bed of a place we have no sound for: a room's air. */
export const DEFAULT_BED: BedId = 'room';

/**
 * Every place of season 1 (`app/services/season/world.py` SEASON_ONE_LOCATIONS)
 * and the older serial plates, with the bed it sounds like.
 */
export const PLACE_BEDS: Readonly<Record<string, BedId>> = {
  // Le Mistral: rain on the window, the room's murmur, a cup now and then.
  le_mistral: 'cafe',
  mistral_back_room: 'cafe',
  // The canal at night: rain on the water, the water at the quay, the city far off.
  quai_de_valmy: 'canal',
  // The street, the market, the shops on it: a crowd's murmur.
  marche_canal: 'market',
  rue_de_lancry: 'market',
  boulangerie: 'market',
  brocante: 'market',
  // Under the city.
  metro_platform: 'metro',
  gare_de_lest: 'metro',
  // Flats: the quiet default, a room's air and the street through a window.
  user_apartment: 'room',
  odile_flat: 'room',
  marin_lila_flat: 'room',
  gus_loft: 'room',
  // The stairwell: a low hum and a little resonance.
  stairwell: 'stairwell',
  // Offices and rooms with ventilation.
  ngo_office: 'office',
  office_admin: 'office',
  mairie: 'office',
  marchand_office: 'office',
  notaire: 'office',
  newsroom: 'office',
  ecole: 'office',
  // Open air: wind, a bird or two.
  buttes_chaumont: 'wind',
  toit: 'wind',
};

export function bedForPlace(place: string | null | undefined): BedId {
  const key = String(place ?? '').trim().toLowerCase();
  return PLACE_BEDS[key] ?? DEFAULT_BED;
}

/**
 * The place a plate shows, from its file name: `/assets/serial/locations/
 * le_mistral-counter.webp` → `le_mistral`. A fallback for a scene whose
 * location id is not known; borrowed plates give the lender's place.
 */
export function placeFromPlate(url: string | null | undefined): string | null {
  const raw = String(url ?? '').split(/[?#]/)[0];
  const match = /\/locations\/([a-z0-9_]+)(?:-[a-z0-9_-]+)?\.[a-z0-9]+$/i.exec(raw);
  return match ? match[1].toLowerCase() : null;
}

/** The scene's place: its location id, else the place its plate shows. */
export function scenePlace(locationId: string | null | undefined, plateUrl?: string | null): string | null {
  const id = String(locationId ?? '').trim();
  return id || placeFromPlate(plateUrl);
}

// ---------------------------------------------------------------------------
// The «Ambiance» setting and the gates
// ---------------------------------------------------------------------------

export const AMBIANCE_PREFERENCE_KEY = 'atelier.ambiance';

/** The default before the learner has chosen: on in the app, off on the web. */
export function defaultAmbianceEnabled(native: boolean = isNativePlatform()): boolean {
  return native;
}

export function readAmbiancePreference(): boolean | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = window.localStorage.getItem(AMBIANCE_PREFERENCE_KEY);
    if (stored === 'on') return true;
    if (stored === 'off') return false;
  } catch {
    /* storage can be blocked; the default applies */
  }
  return null;
}

/** The «Ambiance» setting alone (what Réglages shows). */
export function ambiancePreferred(): boolean {
  if (typeof window === 'undefined') return false;
  return readAmbiancePreference() ?? defaultAmbianceEnabled();
}

export function setAmbianceEnabled(enabled: boolean): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(AMBIANCE_PREFERENCE_KEY, enabled ? 'on' : 'off');
  } catch {
    /* a preference that cannot be stored lasts until the page closes */
  }
}

/** Pure: may a bed sound now? Every gate must be open. */
export function ambianceGate(input: { sounds: boolean; ambiance: boolean; hidden?: boolean }): boolean {
  return Boolean(input.sounds && input.ambiance && !input.hidden);
}

/** «Sons» on and «Ambiance» on: the bed may play (the page and gesture gates are the bed's). */
export function ambianceEnabled(): boolean {
  if (typeof window === 'undefined') return false;
  return ambianceGate({ sounds: soundsEnabled(), ambiance: ambiancePreferred() });
}

// ---------------------------------------------------------------------------
// Envelopes: fades and ducking
// ---------------------------------------------------------------------------

/** How far the bed drops while a line plays. */
export const DUCK_DB = -12;
/** Down quickly when a line starts… */
export const DUCK_ATTACK_S = 0.12;
/** …and back slowly after it, so two lines in a row do not pump. */
export const DUCK_RELEASE_S = 0.6;
export const FADE_IN_S = 2.5;
export const FADE_OUT_S = 1.2;
/** Page hidden: out at once, without a click. */
export const HIDE_FADE_S = 0.06;
/** Ramps end at this rather than 0 so an exponential or linear ramp never divides by zero. */
const SILENT = 0.0001;

export function dbToGain(db: number): number {
  return Math.pow(10, db / 20);
}

/** The bed's gain under the voices: 1, or −12 dB while a line plays. */
export function duckTarget(speaking: boolean): number {
  return speaking ? dbToGain(DUCK_DB) : 1;
}

/** One linear ramp of a gain, in the context's seconds. */
export type Ramp = { from: number; to: number; start: number; end: number };

export function holdRamp(value: number, at = 0): Ramp {
  return { from: value, to: value, start: at, end: at };
}

/** The gain a ramp gives at time `t`: `from` before it, `to` after, linear between. */
export function rampValueAt(ramp: Ramp, t: number): number {
  if (t <= ramp.start) return ramp.from;
  if (t >= ramp.end || ramp.end <= ramp.start) return ramp.to;
  return ramp.from + ((ramp.to - ramp.from) * (t - ramp.start)) / (ramp.end - ramp.start);
}

/**
 * The next ramp toward `target`, starting from wherever the current one is at
 * `now` — a line that starts while the bed is still coming back up ducks from
 * there, not from full.
 */
export function rampToward(current: Ramp, target: number, now: number, seconds: number): Ramp {
  const from = rampValueAt(current, now);
  // The remaining distance sets the time: half the way takes half the ramp.
  const span = Math.abs(target - from);
  const full = Math.abs(1 - dbToGain(DUCK_DB)) || 1;
  const time = Math.max(0, seconds) * Math.min(1, span / full);
  return { from, to: target, start: now, end: now + time };
}

/** The ducking ramp for a change of the speaking state. */
export function duckRamp(current: Ramp, speaking: boolean, now: number): Ramp {
  return rampToward(current, duckTarget(speaking), now, speaking ? DUCK_ATTACK_S : DUCK_RELEASE_S);
}

// ---------------------------------------------------------------------------
// Synthesis: a seamless loop per bed
// ---------------------------------------------------------------------------

/** 16 s: long enough that the ear does not catch the loop, short to render. */
export const BED_SECONDS = 16;
/** Ambience needs no more than 11 kHz; half the samples of 44.1 kHz. */
export const BED_SAMPLE_RATE = 22050;
/** The noise tail cross-faded into the head at the seam. */
export const BED_CROSSFADE_S = 1;

/** The right channel reads the loop this much later than the left. */
export const BED_STEREO_LAG_S = 0.37;

/** The loudness of each bed (RMS, full scale = 1): quiet rooms, busier streets. */
export const BED_LEVEL: Readonly<Record<BedId, number>> = {
  cafe: 0.05,
  market: 0.055,
  canal: 0.05,
  metro: 0.055,
  room: 0.018,
  stairwell: 0.02,
  office: 0.022,
  wind: 0.04,
};

/** Never louder than this, whatever the events add. */
export const BED_PEAK = 0.9;

export type RenderedBed = { sampleRate: number; channels: [Float32Array, Float32Array] };

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function seedOf(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

type Biquad = { b0: number; b1: number; b2: number; a1: number; a2: number };

/** RBJ cookbook biquads. */
function biquad(kind: 'lowpass' | 'highpass' | 'bandpass', freq: number, q: number, rate: number): Biquad {
  const w = (2 * Math.PI * Math.min(freq, rate * 0.45)) / rate;
  const cos = Math.cos(w);
  const alpha = Math.sin(w) / (2 * q);
  const a0 = 1 + alpha;
  let b0: number;
  let b1: number;
  let b2: number;
  if (kind === 'lowpass') {
    b0 = (1 - cos) / 2;
    b1 = 1 - cos;
    b2 = (1 - cos) / 2;
  } else if (kind === 'highpass') {
    b0 = (1 + cos) / 2;
    b1 = -(1 + cos);
    b2 = (1 + cos) / 2;
  } else {
    b0 = alpha;
    b1 = 0;
    b2 = -alpha;
  }
  return { b0: b0 / a0, b1: b1 / a0, b2: b2 / a0, a1: (-2 * cos) / a0, a2: (1 - alpha) / a0 };
}

function filter(buf: Float32Array, c: Biquad): Float32Array {
  let x1 = 0;
  let x2 = 0;
  let y1 = 0;
  let y2 = 0;
  for (let i = 0; i < buf.length; i += 1) {
    const x = buf[i];
    const y = c.b0 * x + c.b1 * x1 + c.b2 * x2 - c.a1 * y1 - c.a2 * y2;
    x2 = x1;
    x1 = x;
    y2 = y1;
    y1 = y;
    buf[i] = y;
  }
  return buf;
}

function white(rand: () => number, n: number): Float32Array {
  const out = new Float32Array(n);
  for (let i = 0; i < n; i += 1) out[i] = rand() * 2 - 1;
  return out;
}

/** Brown(ish) noise: leaky integrated white, scaled to about white's level. */
function brown(rand: () => number, n: number): Float32Array {
  const out = new Float32Array(n);
  let y = 0;
  for (let i = 0; i < n; i += 1) {
    y = (y + 0.02 * (rand() * 2 - 1)) / 1.02;
    out[i] = y * 3.5;
  }
  return out;
}

type Synth = {
  rand: () => number;
  rate: number;
  /** Samples in the loop. */
  n: number;
  /** Samples rendered for the noise layers: the loop plus the cross-fade tail. */
  m: number;
};

/** A swell with a whole number of cycles in the loop, so it meets itself at the seam. */
function swell(i: number, n: number, cycles: number, phase = 0): number {
  return Math.sin(2 * Math.PI * (cycles * (i / n) + phase));
}

/** `hz` rounded to the nearest rate with a whole number of cycles in the loop. */
function loopCycles(hz: number, seconds: number): number {
  return Math.max(1, Math.round(hz * seconds));
}

function layer(s: Synth, make: (s: Synth) => Float32Array, gain: number, mix: Float32Array, env?: (i: number) => number) {
  const buf = make(s);
  for (let i = 0; i < s.m; i += 1) mix[i] += buf[i] * gain * (env ? env(i) : 1);
}

const band = (lo: number, hi: number, kind: 'white' | 'brown' = 'white') => (s: Synth) => {
  const buf = kind === 'white' ? white(s.rand, s.m) : brown(s.rand, s.m);
  if (lo > 0) filter(buf, biquad('highpass', lo, 0.707, s.rate));
  if (hi > 0) filter(buf, biquad('lowpass', hi, 0.707, s.rate));
  return buf;
};

const peak = (centre: number, q: number) => (s: Synth) => filter(white(s.rand, s.m), biquad('bandpass', centre, q, s.rate));

/** A crowd's murmur: voice-band noise, each «voice» swelling at a syllable rate. */
function babble(s: Synth, mix: Float32Array, voices: number, gain: number) {
  const seconds = s.n / s.rate;
  for (let v = 0; v < voices; v += 1) {
    const centre = 280 + s.rand() * 720;
    const fast = loopCycles(2.5 + s.rand() * 3.5, seconds);
    const slow = loopCycles(0.12 + s.rand() * 0.35, seconds);
    const p1 = s.rand();
    const p2 = s.rand();
    layer(s, peak(centre, 2.2), gain, mix, (i) => {
      const syllable = 0.5 + 0.5 * swell(i, s.n, fast, p1);
      const phrase = 0.35 + 0.65 * Math.max(0, swell(i, s.n, slow, p2));
      return syllable * syllable * phrase;
    });
  }
}

/** Short decaying tones (drops on glass, a cup, a bird), written with wrap-around. */
function ping(out: Float32Array, rate: number, at: number, freq: number, decayS: number, amp: number, glideTo?: number) {
  const n = out.length;
  const length = Math.min(n - 1, Math.round(decayS * rate * 5));
  let phase = 0;
  for (let k = 0; k < length; k += 1) {
    const t = k / rate;
    const f = glideTo ? freq + ((glideTo - freq) * k) / length : freq;
    phase += (2 * Math.PI * f) / rate;
    const attack = Math.min(1, k / Math.max(1, rate * 0.0015));
    out[(at + k) % n] += Math.sin(phase) * amp * attack * Math.exp(-t / decayS);
  }
}

/** A tone that rises, glides and fades: the métro's swept whine, a bird's call. */
function sweep(out: Float32Array, rate: number, at: number, seconds: number, from: number, to: number, amp: number) {
  const n = out.length;
  const length = Math.min(n - 1, Math.round(seconds * rate));
  let phase = 0;
  for (let k = 0; k < length; k += 1) {
    const x = k / length;
    const f = from * Math.pow(to / from, x);
    phase += (2 * Math.PI * f) / rate;
    const env = Math.sin(Math.PI * x) ** 2;
    out[(at + k) % n] += (Math.sin(phase) + 0.3 * Math.sin(2 * phase)) * amp * env;
  }
}

/** Circular distance on the loop, 0…0.5, for swells centred on a moment. */
function loopDistance(i: number, n: number, centre: number): number {
  const d = Math.abs(i / n - centre) % 1;
  return Math.min(d, 1 - d);
}

/** The noise layers of one channel, `m` samples long. */
function noiseBed(bed: BedId, s: Synth): Float32Array {
  const mix = new Float32Array(s.m);
  const seconds = s.n / s.rate;
  switch (bed) {
    case 'cafe':
      // Rain on the window: bright hiss, swelling twice per loop.
      layer(s, band(1500, 7000), 0.35, mix, (i) => 0.8 + 0.2 * swell(i, s.n, 2));
      // The room behind: low murmur and a warm floor.
      babble(s, mix, 4, 0.55);
      layer(s, band(0, 180, 'brown'), 0.4, mix);
      break;
    case 'market':
      babble(s, mix, 7, 0.9);
      layer(s, band(0, 150, 'brown'), 0.5, mix);
      layer(s, band(3000, 0), 0.04, mix);
      break;
    case 'canal':
      // Rain on the water, then the water at the quay, then the city far off.
      layer(s, band(400, 4000), 0.4, mix, (i) => 0.85 + 0.15 * swell(i, s.n, 3));
      layer(s, band(0, 300, 'brown'), 0.7, mix, (i) => {
        const lap = 0.5 + 0.5 * swell(i, s.n, loopCycles(0.31, seconds));
        const lap2 = 0.5 + 0.5 * swell(i, s.n, loopCycles(0.45, seconds), 0.3);
        return 0.25 + 0.75 * lap * lap2;
      });
      layer(s, band(0, 100, 'brown'), 0.45, mix);
      break;
    case 'metro':
      // The rumble rises as a train comes in and passes, once per loop.
      layer(s, band(0, 90, 'brown'), 0.9, mix, (i) => {
        const d = loopDistance(i, s.n, 0.55);
        return 0.45 + 1.1 * (d < 0.2 ? 0.5 + 0.5 * Math.cos((Math.PI * d) / 0.2) : 0);
      });
      layer(s, peak(900, 0.8), 0.09, mix);
      break;
    case 'room':
      layer(s, band(0, 220, 'brown'), 0.6, mix);
      layer(s, band(0, 900), 0.03, mix, (i) => 0.7 + 0.3 * swell(i, s.n, 1));
      break;
    case 'stairwell':
      layer(s, band(0, 160, 'brown'), 0.5, mix);
      layer(s, peak(350, 3), 0.12, mix);
      for (let i = 0; i < s.m; i += 1) {
        // Mains hum: 50 Hz is a whole number of cycles in any whole-second loop.
        const t = i / s.rate;
        mix[i] += 0.035 * Math.sin(2 * Math.PI * 50 * t) + 0.02 * Math.sin(2 * Math.PI * 100 * t);
      }
      break;
    case 'office':
      layer(s, peak(450, 0.6), 0.28, mix);
      layer(s, band(0, 200, 'brown'), 0.3, mix);
      for (let i = 0; i < s.m; i += 1) mix[i] += 0.012 * Math.sin((2 * Math.PI * 100 * i) / s.rate);
      break;
    case 'wind':
    default: {
      const a = loopCycles(0.19, seconds);
      const b = loopCycles(0.44, seconds);
      const p = s.rand();
      layer(s, peak(500, 0.5), 0.5, mix, (i) => 0.4 + 0.6 * (0.5 + 0.5 * swell(i, s.n, a, p)) * (0.6 + 0.4 * swell(i, s.n, b)));
      layer(s, band(0, 120, 'brown'), 0.3, mix);
      break;
    }
  }
  return mix;
}

/** Fold the tail into the head (equal power, the layers are noise) so the loop has no seam. */
function foldLoop(mix: Float32Array, n: number, x: number): Float32Array {
  const out = new Float32Array(n);
  out.set(mix.subarray(0, n));
  for (let i = 0; i < x; i += 1) {
    const w = (Math.PI / 2) * (i / x);
    out[i] = mix[i] * Math.sin(w) + mix[n + i] * Math.cos(w);
  }
  return out;
}

/** The events of a bed, one set per loop, written into both channels with a pan. */
function events(bed: BedId, rand: () => number, rate: number, channels: [Float32Array, Float32Array]) {
  const n = channels[0].length;
  const seconds = n / rate;
  const put = (pan: number, draw: (out: Float32Array, gain: number) => void) => {
    // pan −1…1, equal power
    const angle = ((pan + 1) * Math.PI) / 4;
    draw(channels[0], Math.cos(angle));
    draw(channels[1], Math.sin(angle));
  };
  const at = () => Math.floor(rand() * n);
  if (bed === 'cafe' || bed === 'canal') {
    // Drops: on the glass at the café, on the stones and the water on the quai.
    const perSecond = bed === 'cafe' ? 16 : 9;
    const [lo, hi] = bed === 'cafe' ? [1800, 5000] : [900, 2600];
    for (let k = 0; k < perSecond * seconds; k += 1) {
      const start = at();
      const freq = lo + rand() * (hi - lo);
      const amp = 0.02 + 0.1 * rand() * rand();
      const pan = rand() * 2 - 1;
      put(pan, (out, g) => ping(out, rate, start, freq, 0.004, amp * g));
    }
  }
  if (bed === 'cafe') {
    // A cup on a saucer, twice a loop.
    for (let k = 0; k < 2; k += 1) {
      const start = at();
      const pan = rand() - 0.5;
      put(pan, (out, g) => {
        ping(out, rate, start, 2650, 0.09, 0.05 * g);
        ping(out, rate, start, 3920, 0.06, 0.03 * g);
      });
    }
  }
  if (bed === 'market') {
    // Paper bags, a crate set down: short bright rustles.
    for (let k = 0; k < 6; k += 1) {
      const start = at();
      const pan = rand() * 1.6 - 0.8;
      const freq = 900 + rand() * 1800;
      put(pan, (out, g) => ping(out, rate, start, freq, 0.012, 0.05 * g));
    }
  }
  if (bed === 'metro') {
    // The train's swept whine as it brakes, at the top of the rumble.
    const start = Math.floor(0.5 * n);
    put(0.3, (out, g) => sweep(out, rate, start, 1.8, 1350, 980, 0.05 * g));
  }
  if (bed === 'wind') {
    // A sparrow or two.
    for (let k = 0; k < 3; k += 1) {
      const start = at();
      const pan = rand() * 1.6 - 0.8;
      const from = 3200 + rand() * 1500;
      for (let c = 0; c < 3; c += 1) {
        const offset = start + Math.floor(c * 0.11 * rate);
        put(pan, (out, g) => sweep(out, rate, offset, 0.07, from, from * 1.25, 0.02 * g));
      }
    }
  }
}

function rms(channels: Float32Array[]): number {
  let sum = 0;
  let count = 0;
  for (const ch of channels) {
    for (let i = 0; i < ch.length; i += 1) sum += ch[i] * ch[i];
    count += ch.length;
  }
  return count ? Math.sqrt(sum / count) : 0;
}

/**
 * Render a bed: two channels of `seconds` at `sampleRate`, deterministic for a
 * bed (the same seed every time), levelled to `BED_LEVEL` and loop-seamless.
 */
export function renderBed(
  bed: BedId,
  options: { sampleRate?: number; seconds?: number; seed?: number } = {},
): RenderedBed {
  const rate = options.sampleRate ?? BED_SAMPLE_RATE;
  const seconds = Math.max(1, Math.round(options.seconds ?? BED_SECONDS));
  const n = rate * seconds;
  const x = Math.min(Math.floor(n / 4), Math.round(BED_CROSSFADE_S * rate));
  const seed = options.seed ?? seedOf(bed);
  // One channel of noise layers; the other is the same loop read a little
  // later (`BED_STEREO_LAG_S`), which decorrelates noise at half the cost of
  // rendering it twice and keeps the slow swells (a train coming in) together.
  const left = foldLoop(noiseBed(bed, { rand: mulberry32(seed), rate, n, m: n + x }), n, x);
  const right = new Float32Array(n);
  const lag = Math.round(BED_STEREO_LAG_S * rate) % n;
  right.set(left.subarray(lag));
  right.set(left.subarray(0, lag), n - lag);
  const channels: [Float32Array, Float32Array] = [left, right];
  events(bed, mulberry32(seed ^ 0x5bd1e995), rate, channels);
  const level = rms(channels);
  let scale = level > 0 ? BED_LEVEL[bed] / level : 0;
  let top = 0;
  for (const ch of channels) for (let i = 0; i < ch.length; i += 1) top = Math.max(top, Math.abs(ch[i]));
  if (top * scale > BED_PEAK) scale = BED_PEAK / top;
  for (const ch of channels) for (let i = 0; i < ch.length; i += 1) ch[i] *= scale;
  return { sampleRate: rate, channels };
}

const rendered = new Map<BedId, RenderedBed>();

/**
 * The bed's samples, rendered once per page load. Pure JS — no AudioContext —
 * so a scene can call it while the learner reads (`prepareBed`), and the gesture
 * that starts the bed only copies samples into a buffer.
 */
export function renderedBed(bed: BedId): RenderedBed {
  let done = rendered.get(bed);
  if (!done) {
    done = renderBed(bed);
    rendered.set(bed, done);
  }
  return done;
}

/** Render a bed ahead of the gesture, when the page is idle. Cheap if already done. */
export function prepareBed(bed: BedId): () => void {
  if (typeof window === 'undefined' || rendered.has(bed)) return () => {};
  const w = window as Window & {
    requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number;
    cancelIdleCallback?: (id: number) => void;
  };
  if (typeof w.requestIdleCallback === 'function') {
    const id = w.requestIdleCallback(() => void renderedBed(bed), { timeout: 2000 });
    return () => w.cancelIdleCallback?.(id);
  }
  const id = setTimeout(() => void renderedBed(bed), 400);
  return () => clearTimeout(id);
}

// ---------------------------------------------------------------------------
// Playback
// ---------------------------------------------------------------------------

type Playing = { bed: BedId; source: AudioBufferSourceNode; fade: GainNode; ramp: Ramp };

export type SoundBedDeps = {
  /** The shared AudioContext; created on first call, so only called from a gesture. */
  context: () => AudioContext | null;
  /** The context if it already exists (never creates one). */
  existing?: () => AudioContext | null;
  /** «Sons» and «Ambiance» both on. */
  enabled: () => boolean;
  /** The page is hidden. */
  hidden?: () => boolean;
  /** The bed's samples (default: `renderedBed`, cached per page load). */
  render?: (bed: BedId) => RenderedBed;
};

function applyRamp(param: AudioParam, ramp: Ramp) {
  try {
    param.cancelScheduledValues(ramp.start);
    param.setValueAtTime(Math.max(SILENT, ramp.from), ramp.start);
    param.linearRampToValueAtTime(Math.max(SILENT, ramp.to), Math.max(ramp.end, ramp.start + 0.001));
  } catch {
    /* a context that cannot ramp keeps its last value */
  }
}

/**
 * One bed at a time for the whole app. The scene opens it (`open`), the
 * learner's gesture starts it (`gesture`), the voices duck it
 * (`setSpeaking`), the scene closes it (`close`), the page's hiding stops it
 * (`hide`).
 */
export class SoundBed {
  private ctx: AudioContext | null = null;
  private duck: GainNode | null = null;
  private duckState: Ramp = holdRamp(1);
  private playing: Playing | null = null;
  private bed: BedId | null = null;
  private speaking = false;
  private readonly buffers = new Map<BedId, AudioBuffer>();

  constructor(private readonly deps: SoundBedDeps) {}

  /** For tests and the console: what the bed is doing. */
  snapshot() {
    const now = this.ctx?.currentTime ?? 0;
    return {
      open: this.bed !== null,
      bed: this.bed,
      playing: this.playing?.bed ?? null,
      contextState: this.ctx?.state ?? null,
      speaking: this.speaking,
      duckGain: rampValueAt(this.duckState, now),
      duckTarget: this.duckState.to,
    };
  }

  /** A scene opened at `bed`. Nothing sounds, and no context is made, until a gesture. */
  open(bed: BedId): void {
    this.bed = bed;
  }

  /** The scene moved to another place: cross-fade if the bed is playing. */
  setBed(bed: BedId): void {
    if (this.bed === null || this.bed === bed) return;
    this.bed = bed;
    if (this.playing) {
      this.fadeOut(FADE_OUT_S);
      this.start();
    }
  }

  /**
   * The learner touched the scene. Inside the gesture: make (or reuse) the one
   * context, resume it, and start the bed if it is not playing. Returns whether
   * the bed is (now) playing.
   */
  gesture(): boolean {
    if (this.bed === null || this.deps.hidden?.() || !this.deps.enabled()) return false;
    const ctx = this.ctx ?? this.deps.context();
    if (!ctx) return false;
    this.ctx = ctx;
    this.resume();
    if (!this.playing) this.start();
    return this.playing !== null;
  }

  /** A line started or ended. */
  setSpeaking(speaking: boolean): void {
    if (speaking === this.speaking) return;
    this.speaking = speaking;
    if (!this.ctx || !this.duck) return;
    this.duckState = duckRamp(this.duckState, speaking, this.ctx.currentTime);
    applyRamp(this.duck.gain, this.duckState);
  }

  /** The scene closed: fade out and forget the place. The context stays (it is shared). */
  close(): void {
    this.bed = null;
    this.fadeOut(FADE_OUT_S);
  }

  /** The page went away: stop at once and suspend the context. */
  hide(): void {
    this.fadeOut(HIDE_FADE_S);
    const ctx = this.ctx ?? this.deps.existing?.() ?? null;
    try {
      if (ctx && ctx.state === 'running') void ctx.suspend().catch(() => {});
    } catch {
      /* nothing to suspend */
    }
  }

  /** The page came back: resume and fade in again if the scene is still open. */
  show(): void {
    const ctx = this.ctx;
    if (!ctx || this.bed === null || !this.deps.enabled()) return;
    try {
      void Promise.resolve(ctx.resume())
        .then(() => {
          if (this.bed !== null && !this.playing && !this.deps.hidden?.() && this.deps.enabled()) this.start();
        })
        .catch(() => {});
    } catch {
      /* the next gesture resumes it */
    }
  }

  private resume() {
    const ctx = this.ctx;
    if (!ctx) return;
    try {
      if (ctx.state !== 'running') void Promise.resolve(ctx.resume()).catch(() => {});
    } catch {
      /* resumes on the next gesture */
    }
  }

  private buffer(bed: BedId): AudioBuffer | null {
    const ctx = this.ctx;
    if (!ctx) return null;
    const cached = this.buffers.get(bed);
    if (cached) return cached;
    try {
      const samples = (this.deps.render ?? renderedBed)(bed);
      const buffer = ctx.createBuffer(2, samples.channels[0].length, samples.sampleRate);
      samples.channels.forEach((data, c) => buffer.getChannelData(c).set(data));
      this.buffers.set(bed, buffer);
      return buffer;
    } catch {
      return null;
    }
  }

  private start() {
    const ctx = this.ctx;
    const bed = this.bed;
    if (!ctx || bed === null) return;
    try {
      if (!this.duck) {
        this.duck = ctx.createGain();
        this.duck.connect(ctx.destination);
        this.duckState = holdRamp(duckTarget(this.speaking), ctx.currentTime);
        this.duck.gain.setValueAtTime(this.duckState.to, ctx.currentTime);
      }
      const buffer = this.buffer(bed);
      if (!buffer) return;
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.loop = true;
      const fade = ctx.createGain();
      const now = ctx.currentTime;
      const ramp: Ramp = { from: SILENT, to: 1, start: now, end: now + FADE_IN_S };
      applyRamp(fade.gain, ramp);
      source.connect(fade);
      fade.connect(this.duck);
      source.start(now);
      this.playing = { bed, source, fade, ramp };
    } catch {
      this.playing = null; // a device that cannot play stays quiet
    }
  }

  private fadeOut(seconds: number) {
    const playing = this.playing;
    const ctx = this.ctx;
    this.playing = null;
    if (!playing || !ctx) return;
    const now = ctx.currentTime;
    const ramp = rampToward(playing.ramp, SILENT, now, seconds);
    // A fade-out takes its full time whatever the level (rampToward scales by the duck span).
    ramp.end = now + seconds;
    applyRamp(playing.fade.gain, ramp);
    try {
      playing.source.onended = () => {
        try {
          playing.source.disconnect();
          playing.fade.disconnect();
        } catch {
          /* already gone */
        }
      };
      playing.source.stop(now + seconds + 0.05);
    } catch {
      /* already stopped */
    }
  }
}

let shared: SoundBed | null = null;

/** The app's one sound bed. Creating it creates no AudioContext. */
export function soundBed(): SoundBed {
  if (!shared) {
    shared = new SoundBed({
      context: sharedAudioContext,
      existing: existingAudioContext,
      enabled: ambianceEnabled,
      hidden: () => typeof document !== 'undefined' && document.visibilityState === 'hidden',
    });
  }
  return shared;
}

/** Test seam: forget the shared bed. */
export function resetSoundBedForTests(): void {
  shared = null;
}

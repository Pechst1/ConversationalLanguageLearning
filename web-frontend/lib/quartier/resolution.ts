/**
 * Le Quartier · how many pixels a frame can afford.
 *
 * The engine draws the scene into a plate at `scale` device pixels per CSS pixel, and a hot phone
 * draws fewer pixels rather than fewer frames. The governor reads only the time between frames,
 * and that time is not the phone's work: the display sets its floor. A 60 Hz screen never shows a
 * frame sooner than 16.7 ms, a phone in Low Power Mode (or a web view the system throttles) runs
 * the loop at 30 Hz, a ProMotion screen at 120. Until November 2026 the engine compared the
 * average interval with fixed numbers (down past 21 ms, up under 14.5 ms): at 30 Hz every room
 * fell to the floor (0.75, a third of the pixels a phone has) however little it drew, and at 60 Hz
 * the way back up was out of reach (an average under 14.5 ms cannot happen at 16.7 ms a frame),
 * so every hitch (a page handed over, the cast standing up, a sound decoding) lowered the
 * resolution for good. Marin and Lila's flat on the owner's iPhone was the picture of it.
 *
 * So the governor measures against the display's own cadence: the shortest interval the loop has
 * kept up (the tenth percentile of a window, the lowest seen). It lowers the resolution only when
 * the typical frame (the median, which a hitch of a few frames does not move) misses that cadence,
 * and raises it again once frames keep the cadence. A loop that never ran faster than 30 Hz may be
 * a throttled display or a phone that cannot keep up: one probe at half the pixels tells them apart
 * (a phone that was struggling gets faster frames, a throttled display does not).
 */

/** The fewest pixels the quarter is ever drawn with, per CSS pixel. */
export const SCALE_FLOOR = 0.75;
/** The most: a phone's three device pixels a point cost more than the print shows. */
export const SCALE_CEILING = 2;

const WINDOW = 40;
const STEP_DOWN = 0.15;
const STEP_UP = 0.1;
/** after a change, the frames it takes to tell */
const SETTLE_MS = 1500;
/** after missing at a scale, how long before trying it again (doubled each time it misses again) */
const HOLD_MS = 6000;
const HOLD_MAX_MS = 60000;
/** the typical frame misses the cadence: more than a fifth over it */
const MISS = 1.2;
/** the typical frame keeps the cadence */
const KEEP = 1.08;
/** a cadence this slow may be the display's (30 Hz) or the phone's: probe it once */
const SLOW_CADENCE_MS = 25;
/** the probe draws half the pixels (0.7 a side): a struggling phone shows it at once */
const PROBE = 0.7;

export interface GovernorState {
  scale: number;
  /** the display's frame interval as the loop has shown it, ms */
  cadence: number;
  /** the median interval of the last window, ms */
  median: number;
}

export class ResolutionGovernor {
  scale: number;
  cadence = Infinity;
  median = 0;
  private readonly max: number;
  private times: number[] = [];
  private lastChange = -Infinity;
  /** a scale that missed recently, and until when it is not tried again */
  private ceiling: { scale: number; until: number; hold: number } | null = null;
  /** the probe of a slow cadence: the scale and median before it, or done */
  private probe: { from: number; median: number } | 'done' | null = null;

  constructor(max: number, start = max) {
    this.max = Math.max(SCALE_FLOOR, Math.min(SCALE_CEILING, max));
    this.scale = Math.max(SCALE_FLOOR, Math.min(this.max, start));
  }

  /** The interval since the last frame (ms) at time `t` (ms). Returns the new scale when it changes, else null. */
  frame(ms: number, t: number): number | null {
    if (!(ms > 0) || ms > 1000) return null;
    this.times.push(ms);
    if (this.times.length > WINDOW) this.times.shift();
    if (this.times.length < WINDOW) return null;
    const sorted = [...this.times].sort((a, b) => a - b);
    this.median = sorted[WINDOW >> 1];
    this.cadence = Math.min(this.cadence, Math.max(4, sorted[Math.floor(WINDOW * 0.1)]));
    if (t - this.lastChange < SETTLE_MS) return null;

    // the probe's answer: faster frames a step lower mean the phone was struggling
    if (this.probe && this.probe !== 'done') {
      const { from, median } = this.probe;
      this.probe = 'done';
      if (this.median < median * 0.85) {
        // the phone, not the display: the cadence it can keep is the faster one now seen
        return null;
      }
      // the display's 30 Hz: nothing to gain from fewer pixels
      this.cadence = Math.min(this.cadence, median);
      return this.set(from, t);
    }

    if (this.cadence >= SLOW_CADENCE_MS && this.probe === null && this.scale - STEP_DOWN >= SCALE_FLOOR) {
      this.probe = { from: this.scale, median: this.median };
      return this.set(Math.max(SCALE_FLOOR, this.scale * PROBE), t);
    }

    if (this.median > this.cadence * MISS && this.scale > SCALE_FLOOR) {
      const hold = this.ceiling && this.ceiling.scale <= this.scale + 0.001 ? Math.min(HOLD_MAX_MS, this.ceiling.hold * 2) : HOLD_MS;
      this.ceiling = { scale: this.scale, until: t + hold, hold };
      return this.set(Math.max(SCALE_FLOOR, this.scale - STEP_DOWN), t);
    }
    if (this.median <= this.cadence * KEEP && this.scale < this.max) {
      const cap = this.ceiling && t < this.ceiling.until ? Math.min(this.max, this.ceiling.scale - 0.05) : this.max;
      if (this.scale + 0.001 < cap) return this.set(Math.min(cap, this.scale + STEP_UP), t);
    }
    return null;
  }

  state(): GovernorState {
    return { scale: this.scale, cadence: Number.isFinite(this.cadence) ? this.cadence : 0, median: this.median };
  }

  private set(scale: number, t: number): number {
    this.scale = Math.round(scale * 100) / 100;
    this.lastChange = t;
    // a new resolution is a new measure
    this.times = [];
    return this.scale;
  }
}

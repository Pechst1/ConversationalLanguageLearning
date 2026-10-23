/**
 * Le Quartier · the sound of the place, made on the phone (no files to load).
 *
 * Rain on the quai (muffled once the door shuts), the café's murmur, your steps (wet outside,
 * on tiles inside), the neon's hum when you stand under it, and the few cues the director asks
 * for: the door's bell, a key on the zinc, a cup on its saucer, a chair pulled out, paper.
 * Everything is white noise and a few sine partials through filters; an AudioContext may only
 * start from a tap, so `start()` is called from the title card's button.
 */
import type { Cue } from './stage';

export interface Ambience {
  indoors: boolean;
  walking: boolean;
  rain: boolean;
  night: boolean;
  /** metres from the neon (its hum carries a few metres) */
  neon: number;
}

export class Sound {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private noise: AudioBuffer | null = null;
  private rainGain: GainNode | null = null;
  private rainTone: BiquadFilterNode | null = null;
  private roomGain: GainNode | null = null;
  private humGain: GainNode | null = null;
  private stepAt = 0;
  private stepSide = 0;
  private on = true;

  get enabled() {
    return this.on;
  }

  /** Call from a tap. Safe to call twice. */
  start() {
    if (this.ctx || typeof window === 'undefined') return;
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return;
    const ctx = new Ctor();
    this.ctx = ctx;
    const master = ctx.createGain();
    master.gain.value = this.on ? 0.9 : 0;
    master.connect(ctx.destination);
    this.master = master;
    // two seconds of noise, looped by everything that hisses
    const len = ctx.sampleRate * 2;
    const buf = ctx.createBuffer(1, len, ctx.sampleRate);
    const d = buf.getChannelData(0);
    let b0 = 0;
    let b1 = 0;
    for (let i = 0; i < len; i++) {
      const w = Math.random() * 2 - 1;
      // a little pinker than white: rain is not a hiss
      b0 = 0.97 * b0 + w * 0.15;
      b1 = 0.6 * b1 + w * 0.4;
      d[i] = (b0 + b1 + w * 0.2) * 0.5;
    }
    this.noise = buf;
    // the rain
    {
      const src = this.loop();
      const hp = ctx.createBiquadFilter();
      hp.type = 'highpass';
      hp.frequency.value = 500;
      const lp = ctx.createBiquadFilter();
      lp.type = 'lowpass';
      lp.frequency.value = 6500;
      const g = ctx.createGain();
      g.gain.value = 0;
      src.connect(hp).connect(lp).connect(g).connect(master);
      this.rainGain = g;
      this.rainTone = lp;
    }
    // the room: voices too far to make out, a cup now and then
    {
      const src = this.loop();
      const bp = ctx.createBiquadFilter();
      bp.type = 'bandpass';
      bp.frequency.value = 340;
      bp.Q.value = 0.9;
      const g = ctx.createGain();
      g.gain.value = 0;
      const lfo = ctx.createOscillator();
      lfo.frequency.value = 0.31;
      const depth = ctx.createGain();
      depth.gain.value = 0.25;
      const body = ctx.createGain();
      body.gain.value = 1;
      lfo.connect(depth).connect(body.gain);
      lfo.start();
      src.connect(bp).connect(body).connect(g).connect(master);
      this.roomGain = g;
    }
    // the neon's hum
    {
      const g = ctx.createGain();
      g.gain.value = 0;
      for (const [f, a] of [
        [100, 0.6],
        [200, 0.25],
        [300, 0.1],
      ]) {
        const o = ctx.createOscillator();
        o.type = 'sine';
        o.frequency.value = f;
        const og = ctx.createGain();
        og.gain.value = a;
        o.connect(og).connect(g);
        o.start();
      }
      g.connect(master);
      this.humGain = g;
    }
  }

  setEnabled(on: boolean) {
    this.on = on;
    if (this.master && this.ctx) this.master.gain.setTargetAtTime(on ? 0.9 : 0, this.ctx.currentTime, 0.15);
    if (on) void this.ctx?.resume();
  }

  /** Follow the place: every frame or so. */
  update(a: Ambience) {
    const ctx = this.ctx;
    if (!ctx || !this.rainGain || !this.roomGain || !this.humGain || !this.rainTone) return;
    const t = ctx.currentTime;
    const rain = a.rain ? (a.indoors ? 0.12 : 0.34) : a.indoors ? 0 : 0.04;
    this.rainGain.gain.setTargetAtTime(rain, t, 0.4);
    this.rainTone.frequency.setTargetAtTime(a.indoors ? 900 : 6500, t, 0.3);
    this.roomGain.gain.setTargetAtTime(a.indoors ? 0.2 : 0, t, 0.5);
    const hum = a.night && !a.indoors ? Math.max(0, 1 - a.neon / 9) * 0.035 : 0;
    this.humGain.gain.setTargetAtTime(hum, t, 0.3);
    if (a.walking && t - this.stepAt > 0.52) {
      this.stepAt = t;
      this.step(a.indoors, a.rain);
    }
  }

  cue(c: Cue) {
    if (!this.ctx || !this.on) return;
    if (c === 'bell') {
      this.bell(0);
      this.bell(0.16);
    } else if (c === 'door') this.thud(0.0, 180, 0.35);
    else if (c === 'key') this.chime([3150, 4720, 6100], 0.22, 0.09);
    else if (c === 'cup') {
      this.chime([2480, 3720], 0.32, 0.08);
      this.thud(0.02, 420, 0.12);
    } else if (c === 'chair') this.scrape();
    else if (c === 'paper') this.flick();
    else if (c === 'phone') {
      this.buzz(0);
      this.buzz(0.3);
    }
  }

  dispose() {
    void this.ctx?.close();
    this.ctx = null;
  }

  /* ---- voices ------------------------------------------------------------------------------ */

  private loop() {
    const ctx = this.ctx as AudioContext;
    const src = ctx.createBufferSource();
    src.buffer = this.noise;
    src.loop = true;
    src.loopStart = Math.random();
    src.start(0, Math.random() * 1.5);
    return src;
  }

  private burst(at: number, seconds: number) {
    const ctx = this.ctx as AudioContext;
    const src = ctx.createBufferSource();
    src.buffer = this.noise;
    src.start(ctx.currentTime + at, Math.random() * 1.5, seconds + 0.05);
    return src;
  }

  private env(at: number, peak: number, decay: number) {
    const ctx = this.ctx as AudioContext;
    const g = ctx.createGain();
    const t = ctx.currentTime + at;
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(peak, t + 0.004);
    g.gain.exponentialRampToValueAtTime(0.0001, t + decay);
    g.connect(this.master as GainNode);
    return g;
  }

  private bell(at: number) {
    const ctx = this.ctx as AudioContext;
    for (const [f, a, d] of [
      [1880, 0.16, 1.4],
      [2760, 0.08, 0.9],
      [4130, 0.05, 0.5],
      [5340, 0.025, 0.3],
    ]) {
      const o = ctx.createOscillator();
      o.frequency.value = f * (1 + (Math.random() - 0.5) * 0.004);
      const g = this.env(at, a, d);
      o.connect(g);
      o.start(ctx.currentTime + at);
      o.stop(ctx.currentTime + at + d + 0.05);
    }
  }

  private chime(freqs: number[], decay: number, peak: number) {
    const ctx = this.ctx as AudioContext;
    freqs.forEach((f, i) => {
      const o = ctx.createOscillator();
      o.frequency.value = f;
      const g = this.env(0, peak / (i + 1), decay * (1 - i * 0.2));
      o.connect(g);
      o.start();
      o.stop(ctx.currentTime + decay + 0.05);
    });
  }

  /** A phone in a pocket: one short low rattle. */
  private buzz(at: number) {
    const ctx = this.ctx as AudioContext;
    const t = ctx.currentTime + at;
    const o = ctx.createOscillator();
    o.type = 'square';
    o.frequency.value = 160;
    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = 380;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(0.06, t + 0.012);
    g.gain.setValueAtTime(0.06, t + 0.17);
    g.gain.linearRampToValueAtTime(0, t + 0.2);
    g.connect(this.master as GainNode);
    o.connect(lp).connect(g);
    o.start(t);
    o.stop(t + 0.22);
  }

  private thud(at: number, freq: number, peak: number) {
    const ctx = this.ctx as AudioContext;
    const src = this.burst(at, 0.14);
    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = freq;
    src.connect(lp).connect(this.env(at, peak, 0.14));
  }

  private step(indoors: boolean, wet: boolean) {
    const ctx = this.ctx as AudioContext;
    this.stepSide = 1 - this.stepSide;
    const src = this.burst(0, 0.09);
    const f = ctx.createBiquadFilter();
    f.type = indoors ? 'bandpass' : 'lowpass';
    f.frequency.value = indoors ? 1300 + this.stepSide * 140 : 520 + this.stepSide * 60;
    src.connect(f).connect(this.env(0, indoors ? 0.12 : 0.2, indoors ? 0.07 : 0.09));
    if (!indoors && wet) {
      const s = this.burst(0.012, 0.07);
      const hp = ctx.createBiquadFilter();
      hp.type = 'highpass';
      hp.frequency.value = 2600;
      s.connect(hp).connect(this.env(0.012, 0.05, 0.07));
    }
  }

  private scrape() {
    const ctx = this.ctx as AudioContext;
    const src = this.burst(0, 0.55);
    const bp = ctx.createBiquadFilter();
    bp.type = 'bandpass';
    bp.Q.value = 6;
    bp.frequency.setValueAtTime(700, ctx.currentTime);
    bp.frequency.linearRampToValueAtTime(1100, ctx.currentTime + 0.5);
    src.connect(bp).connect(this.env(0, 0.3, 0.55));
  }

  private flick() {
    const ctx = this.ctx as AudioContext;
    const src = this.burst(0, 0.06);
    const hp = ctx.createBiquadFilter();
    hp.type = 'highpass';
    hp.frequency.value = 2400;
    src.connect(hp).connect(this.env(0, 0.08, 0.06));
  }
}

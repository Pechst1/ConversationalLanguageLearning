#!/usr/bin/env node
// WP-145 · the sound bed on a real day-1 scene. Starts the walk's own stack (throwaway
// database, fake-provider API, Next dev), signs a learner in by cookie with «Sons» and
// «Ambiance» on, plays day 1 in headless Chromium with the user-gesture autoplay policy,
// and logs, from an instrumented AudioContext: when the context is created (and whether
// a gesture had happened), its state, every gain ramp (value and length: 2.5 s = fade in,
// 0.12 s to 0.2512 = duck under a line, 0.6 s back to 1 = release, 1.2 s to 0 = fade
// out) and the looping buffers started. Exit 1 when the bed never ran or never ducked.
//
//   PATH=<repo>/venv/bin:$PATH WALK_ART_SET=drawn node e2e/wp145-bed.mjs
import { chromium } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Findings } from './lib/assertions.mjs';
import { LearnerWalk } from './lib/learner-walk.mjs';
import { registerLearner } from './lib/session.mjs';
import { startStack } from './lib/stack.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const SECRET = 'e3-walk-secret-not-for-production';
const outDir = path.join(here, 'out', `wp145-${new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)}`);
mkdirSync(outDir, { recursive: true });

const INSTRUMENT = () => {
  try {
    window.localStorage.setItem('atelier.sounds', 'on');
    window.localStorage.setItem('atelier.ambiance', 'on');
    // The vertical page reveals lines with the voice when it speaks unasked: a line plays.
    window.localStorage.setItem('atelier.voices', 'on');
  } catch { /* storage refused */ }
  const Orig = window.AudioContext;
  if (!Orig) return;
  const log = (...a) => console.log('[bed]', (performance.now() / 1000).toFixed(2), ...a);
  window.AudioContext = class extends Orig {
    constructor(...args) {
      super(...args);
      log('context-created', 'gesture-before=' + Boolean(navigator.userActivation && navigator.userActivation.hasBeenActive), 'state=' + this.state);
      this.addEventListener('statechange', () => log('state', this.state));
      window.__bedContexts = (window.__bedContexts || []).concat(this);
    }
  };
  const ramp = AudioParam.prototype.linearRampToValueAtTime;
  AudioParam.prototype.linearRampToValueAtTime = function patched(value, end) {
    const ctx = (window.__bedContexts || [])[0];
    const now = ctx ? ctx.currentTime : 0;
    log('ramp', value.toFixed(4), 'over', (end - now).toFixed(2) + 's');
    return ramp.call(this, value, end);
  };
  const start = AudioBufferSourceNode.prototype.start;
  AudioBufferSourceNode.prototype.start = function patched(...args) {
    if (this.loop && this.buffer) {
      const data = this.buffer.getChannelData(0);
      let sum = 0;
      for (let i = 0; i < data.length; i += 1) sum += data[i] * data[i];
      log('loop-start', this.buffer.duration.toFixed(1) + 's', 'rms=' + Math.sqrt(sum / data.length).toFixed(4));
    }
    return start.apply(this, args);
  };
  document.addEventListener('visibilitychange', () => log('visibility', document.visibilityState));
};

let stack;
let browser;
const lines = [];
try {
  stack = await startStack({ logDir: path.join(outDir, 'logs'), secret: SECRET });
  browser = await chromium.launch({ args: ['--autoplay-policy=user-gesture-required'] });
  const learner = await registerLearner({ api: stack.api, secret: SECRET, native: 'en', level: 'A1.1', tag: 'bed' });
  const context = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true, locale: 'en-GB' });
  await context.addCookies([{ name: 'next-auth.session-token', value: learner.cookie, url: stack.web }]);
  if (process.env.WALK_ART_SET) {
    await context.addInitScript((value) => {
      try { window.localStorage.setItem('atelier.artSet', value); } catch { /* storage refused */ }
    }, process.env.WALK_ART_SET);
  }
  await context.addInitScript(INSTRUMENT);
  const findings = new Findings();
  const walk = new LearnerWalk({ page: null, findings, outDir, lang: 'en', level: 'A1.1', stack, shots: { root: outDir, list: [] }, scale: 1 });
  const page = await walk.newSession(context);
  page.on('console', (msg) => {
    const text = msg.text();
    if (text.startsWith('[bed]')) {
      lines.push(text);
      console.log(text);
    }
  });
  const kinds = await walk.playJourney({ maxSeconds: 180 });
  console.log('[wp145] kinds:', kinds.join(' > '));
  // Hide the page, as switching apps would.
  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
  }).catch(() => {});
  await new Promise((r) => setTimeout(r, 500));
} finally {
  writeFileSync(path.join(outDir, 'bed.log'), lines.join('\n') + '\n');
  await browser?.close().catch(() => {});
  await stack?.stop?.().catch(() => {});
}

const created = lines.find((l) => l.includes('context-created'));
const ran = lines.some((l) => l.includes('state running')) && lines.some((l) => l.includes('loop-start'));
const ducked = lines.some((l) => /ramp 0\.2512 over 0\.1/.test(l));
console.log(`[wp145] context: ${created || 'never created'}; running+loop: ${ran}; ducked: ${ducked}; log: ${path.join(outDir, 'bed.log')}`);
process.exit(created && !created.includes('gesture-before=false') && ran && ducked ? 0 : 1);

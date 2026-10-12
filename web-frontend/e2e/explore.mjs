#!/usr/bin/env node
// The exploratory walk: the same throwaway stack as `npm run walk`, but nobody scripts
// the learner. An agent (or a person) plays the app one action at a time over a small
// local HTTP API, reads each screen as text plus a screenshot, writes its own free-text
// answers, and records what it found. Every action and every screen goes into
// transcript.jsonl in the output folder, so each finding can point at the screen it is
// about.
//
//   npm run explore -- [--native de] [--level A1.1] [--fresh] [--out DIR] [--port 7777]
//
// --fresh skips the API sign-up and starts on the sign-in page, as a stranger would.
// Then, from any shell:
//   curl -s localhost:7777/snap                         what is on the screen (+ screenshot)
//   curl -s localhost:7777/click -d '{"text":"Weiter"}' tap a button or link by its text
//   curl -s localhost:7777/click -d '{"index":3}'       … or by its number in /snap
//   curl -s localhost:7777/type  -d '{"text":"Bonjour"}'  fill the visible text field
//   curl -s localhost:7777/key   -d '{"key":"Enter"}'
//   curl -s localhost:7777/goto  -d '{"path":"/atelier"}'
//   curl -s localhost:7777/clock -d '{"days":1}'        move the server's «today»
//   curl -s localhost:7777/learner -d '{"native":"en","level":"A2.1"}'  a new learner
//   curl -s localhost:7777/note  -d '{"severity":"high","title":"…","detail":"…"}'
//   curl -s localhost:7777/stop                         tear everything down
// /note appends a finding to findings.jsonl next to the transcript, tied to the last
// screenshot. The stack is the fake story provider, as in the scripted walk: no paid call.
import { chromium } from '@playwright/test';
import { appendFileSync, mkdirSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { registerLearner } from './lib/session.mjs';
import { sleep, startStack } from './lib/stack.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : dflt;
};
const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
const outDir = path.resolve(opt('out', path.join(here, 'out', `explore-${stamp}`)));
const port = Number(opt('port', 7777));
const SECRET = 'e3-walk-secret-not-for-production';
mkdirSync(outDir, { recursive: true });

const log = (file, row) => appendFileSync(path.join(outDir, file), `${JSON.stringify({ at: new Date().toISOString(), ...row })}\n`);

// What a learner can see: the main text, the controls with a number each, the fields.
const READ_SCREEN = () => {
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0';
  };
  const controls = [...document.querySelectorAll('button, a[href], [role=button], [role=tab], [role=radio], [role=option], input[type=checkbox], input[type=radio], select')]
    .filter(vis)
    .map((el) => ({
      text: (el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 80),
      tag: el.tagName.toLowerCase(),
      disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
    }));
  const fields = [...document.querySelectorAll('textarea, input:not([type]), input[type=text], input[type=email], input[type=password], input[type=search]')]
    .filter(vis)
    .map((el) => ({ kind: el.tagName.toLowerCase(), type: el.type || '', placeholder: el.placeholder || '', label: el.getAttribute('aria-label') || '', value: el.value, disabled: el.disabled || el.readOnly }));
  const root = document.querySelector('main') || document.body;
  return {
    url: location.pathname + location.search,
    title: document.title,
    text: (root.innerText || '').replace(/\n{3,}/g, '\n\n').trim().slice(0, 6000),
    controls,
    fields,
    busy: document.querySelector('[aria-busy="true"], [data-pending="true"]') !== null,
  };
};

let stack;
let browser;
let context;
let page;
let seq = 0;
let lastShot = null;
const consoleErrors = [];

async function newLearner({ native = 'de', level = 'A1.1', fresh = false } = {}) {
  if (context) await context.close();
  context = await browser.newContext({
    viewport: { width: 375, height: 812 },
    isMobile: true,
    hasTouch: true,
    locale: native === 'fr' ? 'fr-FR' : native === 'de' ? 'de-DE' : 'en-GB',
  });
  let learner = null;
  if (!fresh) {
    learner = await registerLearner({ api: stack.api, secret: SECRET, native, level, tag: 'explore' });
    await context.addCookies([{ name: 'next-auth.session-token', value: learner.cookie, url: stack.web }]);
  }
  page = await context.newPage();
  page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${String(e.message).slice(0, 200)}`));
  page.on('response', (r) => {
    if (r.status() >= 500 && r.url().includes('/api/')) consoleErrors.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`);
  });
  await page.goto(`${stack.web}${fresh ? '/' : '/atelier'}`, { waitUntil: 'domcontentloaded' });
  log('transcript.jsonl', { action: 'learner', native, level, fresh, email: learner?.email });
  return { native, level, email: learner?.email || null };
}

async function settle() {
  // Let requests and animations finish; a screen that says it is busy gets up to 20 s.
  await page.waitForLoadState('domcontentloaded').catch(() => {});
  await sleep(700);
  for (let i = 0; i < 40; i += 1) {
    const busy = await page.evaluate(() => document.querySelector('[aria-busy="true"], [data-pending="true"]') !== null).catch(() => false);
    if (!busy) break;
    await sleep(500);
  }
}

async function snap() {
  await settle();
  seq += 1;
  const screen = await page.evaluate(READ_SCREEN);
  const file = path.join(outDir, `${String(seq).padStart(3, '0')}.png`);
  await page.screenshot({ path: file, animations: 'disabled' });
  lastShot = path.relative(outDir, file);
  const errors = consoleErrors.splice(0);
  log('transcript.jsonl', { action: 'snap', shot: lastShot, ...screen, errors });
  return {
    shot: file,
    ...screen,
    controls: screen.controls.map((c, i) => `${i}: [${c.tag}${c.disabled ? ', disabled' : ''}] ${c.text}`),
    errors,
  };
}

async function click({ text, index, exact = false }) {
  const loc = page.locator('button, a[href], [role=button], [role=tab], [role=radio], [role=option], input[type=checkbox], input[type=radio], select').filter({ visible: true });
  let target;
  if (index !== undefined) target = loc.nth(Number(index));
  else target = loc.filter({ hasText: exact ? new RegExp(`^\\s*${text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*$`) : text }).first();
  if (!(await target.count())) target = page.getByLabel(text).first();
  await target.click({ timeout: 8000 });
  log('transcript.jsonl', { action: 'click', text, index });
}

async function type({ text, field = 0, label }) {
  const loc = label
    ? page.getByLabel(label).first()
    : page.locator('textarea, input:not([type]), input[type=text], input[type=email], input[type=password], input[type=search]').filter({ visible: true }).nth(Number(field));
  await loc.fill(text, { timeout: 8000 });
  log('transcript.jsonl', { action: 'type', text, field, label });
}

const routes = {
  snap: () => snap(),
  click: async (b) => { await click(b); return snap(); },
  type: async (b) => { await type(b); return { ok: true }; },
  key: async ({ key }) => { await page.keyboard.press(key); log('transcript.jsonl', { action: 'key', key }); return snap(); },
  goto: async ({ path: p }) => { await page.goto(`${stack.web}${p}`, { waitUntil: 'domcontentloaded' }); log('transcript.jsonl', { action: 'goto', path: p }); return snap(); },
  scroll: async ({ dy = 600 }) => { await page.mouse.wheel(0, dy); return snap(); },
  wait: async ({ ms = 2000 }) => { await sleep(Number(ms)); return snap(); },
  clock: async ({ days }) => { await stack.setClock(Number(days)); log('transcript.jsonl', { action: 'clock', days }); return { ok: true, days }; },
  learner: (b) => newLearner(b),
  note: (b) => {
    log('findings.jsonl', { shot: lastShot, url: page.url().replace(stack.web, ''), ...b });
    return { ok: true };
  },
  stop: async () => {
    setTimeout(async () => { await browser?.close(); await stack?.stop(); process.exit(0); }, 50);
    return { ok: true, out: outDir };
  },
};

async function main() {
  stack = await startStack({ logDir: path.join(outDir, 'logs'), secret: SECRET });
  browser = await chromium.launch(process.env.WALK_CHROMIUM ? { executablePath: process.env.WALK_CHROMIUM } : {});
  await newLearner({ native: opt('native', 'de'), level: opt('level', 'A1.1'), fresh: argv.includes('--fresh') });
  http
    .createServer(async (req, res) => {
      let body = '';
      for await (const chunk of req) body += chunk;
      const name = req.url.replace(/^\//, '').split('?')[0];
      const fn = routes[name];
      res.setHeader('content-type', 'application/json');
      if (!fn) { res.statusCode = 404; res.end(JSON.stringify({ error: `unknown command ${name}`, commands: Object.keys(routes) })); return; }
      try {
        res.end(JSON.stringify(await fn(body ? JSON.parse(body) : {}), null, 1));
      } catch (e) {
        res.statusCode = 500;
        res.end(JSON.stringify({ error: String(e.message || e).slice(0, 600) }));
      }
    })
    .listen(port, '127.0.0.1', () => console.log(`[explore] ready on http://127.0.0.1:${port} · app ${stack.web} · out ${outDir}`));
}

process.on('SIGINT', async () => { await browser?.close(); await stack?.stop(); process.exit(130); });
main().catch(async (e) => { console.error(e); await stack?.stop(); process.exit(1); });

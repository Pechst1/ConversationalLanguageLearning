#!/usr/bin/env node
// The exploratory walk against the REAL API: the static native bundle, served by a local
// proxy that forwards /api/ to production, played in a phone-sized browser. Same control
// API as `npm run explore` (snap, click, type, key, goto, scroll, wait, note, stop), so
// the explore-walk skill drives it unchanged; there is no clock and no throwaway learner,
// because this is the real server and a real (test) account.
//
//   ATELIER_WALK_EMAIL=… ATELIER_WALK_PASSWORD=… npm run explore:live -- [--api URL] [--port 7778] [--app-port 7781] [--skip-build] [--out DIR]
//
// It signs in through the sign-in screen, as a person would. Use a dedicated test
// account that is on the API's registration allowlist, never a learner's own account:
// every answer is written to the production database and the model calls are paid.
import { chromium } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { appendFileSync, existsSync, mkdirSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { startLiveProxy } from './lib/live-proxy.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, '..');
const argv = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : dflt;
};
const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
const outDir = path.resolve(opt('out', path.join(here, 'out', `explore-live-${stamp}`)));
const port = Number(opt('port', 7778));
const appPort = Number(opt('app-port', 7781));
const upstream = opt('api', process.env.ATELIER_LIVE_API || 'https://atelier-api-3njh.onrender.com');
const email = process.env.ATELIER_WALK_EMAIL;
const password = process.env.ATELIER_WALK_PASSWORD;
mkdirSync(outDir, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (file, row) => appendFileSync(path.join(outDir, file), `${JSON.stringify({ at: new Date().toISOString(), ...row })}\n`);

if (!email || !password) {
  console.error('[explore-live] set ATELIER_WALK_EMAIL and ATELIER_WALK_PASSWORD (a test account, never a learner).');
  process.exit(2);
}

// The bundle is built for the proxy's origin: every API call stays same-origin.
function build() {
  const appOrigin = `http://127.0.0.1:${appPort}`;
  const env = {
    ...process.env,
    NEXT_PUBLIC_API_BASE_URL: `${appOrigin}/api/v1`,
    NEXT_PUBLIC_WS_URL: upstream.replace(/^http/, 'ws'),
    ALLOW_LOCAL_NATIVE_API: 'true',
    NEXT_PUBLIC_NATIVE_PUSH_ENABLED: 'false',
  };
  console.log(`[explore-live] building the native bundle for ${appOrigin} …`);
  const r = spawnSync('npm', ['run', 'build:native'], { cwd: webRoot, env, stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8' });
  if (r.status !== 0) {
    console.error(r.stdout.slice(-3000), r.stderr.slice(-3000));
    throw new Error('native build failed');
  }
}

// What a learner can see: the main text, the controls with a number each, the fields.
// (Same reader as e2e/explore.mjs, so transcripts from both walks compare line by line.)
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
    .map((el) => ({ kind: el.tagName.toLowerCase(), type: el.type || '', placeholder: el.placeholder || '', label: el.getAttribute('aria-label') || '', value: el.type === 'password' ? '••' : el.value, disabled: el.disabled || el.readOnly }));
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

let proxy;
let browser;
let page;
let seq = 0;
let lastShot = null;
const consoleErrors = [];

async function settle() {
  // Real generation is slower than the fake provider: a busy screen gets up to 45 s.
  await page.waitForLoadState('domcontentloaded').catch(() => {});
  await sleep(900);
  for (let i = 0; i < 90; i += 1) {
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

const CONTROLS = 'button, a[href], [role=button], [role=tab], [role=radio], [role=option], input[type=checkbox], input[type=radio], select';

async function click({ text, index, exact = false }) {
  const loc = page.locator(CONTROLS).filter({ visible: true });
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

async function signIn() {
  // The static sign-in page, straight away: the welcome screen's link only works once
  // the page has hydrated, which a click right after load can beat.
  await page.goto(`${proxy.url}/auth/signin/`, { waitUntil: 'networkidle' });
  await page.locator('input[type=email]').first().fill(email, { timeout: 30000 });
  await page.locator('input[type=password]').first().fill(password);
  await page.locator('button[type=submit], button').filter({ hasText: /^\s*(sign in|se connecter|anmelden)\s*$/i }).first().click();
  // A cold Render instance can take most of a minute to answer the first request.
  await page.waitForFunction(() => !document.querySelector('input[type=password]'), null, { timeout: 90000 });
  log('transcript.jsonl', { action: 'sign-in', email });
}

const routes = {
  snap: () => snap(),
  click: async (b) => { await click(b); return snap(); },
  type: async (b) => { await type(b); return { ok: true }; },
  key: async ({ key }) => { await page.keyboard.press(key); log('transcript.jsonl', { action: 'key', key }); return snap(); },
  goto: async ({ path: p }) => { await page.goto(`${proxy.url}${p}`, { waitUntil: 'domcontentloaded' }); log('transcript.jsonl', { action: 'goto', path: p }); return snap(); },
  scroll: async ({ dy = 600 }) => { await page.mouse.wheel(0, dy); return snap(); },
  wait: async ({ ms = 2000 }) => { await sleep(Number(ms)); return snap(); },
  note: (b) => {
    log('findings.jsonl', { shot: lastShot, url: page.url().replace(proxy.url, ''), live: true, ...b });
    return { ok: true };
  },
  stop: async () => {
    setTimeout(async () => { await browser?.close(); await proxy?.close(); process.exit(0); }, 50);
    return { ok: true, out: outDir };
  },
};

async function main() {
  const root = path.join(webRoot, 'out');
  if (!argv.includes('--skip-build') || !existsSync(root)) build();
  proxy = await startLiveProxy({ port: appPort, root, upstream, log: (row) => log('proxy.jsonl', row) });
  browser = await chromium.launch(process.env.WALK_CHROMIUM ? { executablePath: process.env.WALK_CHROMIUM } : {});
  const context = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true, locale: 'de-DE' });
  // Run the bundle as the app does: Capacitor reports a native platform, so sign-in uses
  // the token flow the phone uses (not next-auth, which needs a Next server), and every
  // plugin falls back to its web implementation (secure storage → localStorage).
  await context.addInitScript(() => { window.CapacitorCustomPlatform = { name: 'ios', plugins: {} }; });
  page = await context.newPage();
  page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${String(e.message).slice(0, 200)}`));
  page.on('response', (r) => {
    if (r.status() >= 500 && r.url().includes('/api/')) consoleErrors.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`);
  });
  await signIn();
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
    .listen(port, '127.0.0.1', () => console.log(`[explore-live] ready on http://127.0.0.1:${port} · app ${proxy.url} → ${upstream} · out ${outDir}`));
}

process.on('SIGINT', async () => { await browser?.close(); await proxy?.close(); process.exit(130); });
main().catch(async (e) => { console.error(e); await browser?.close(); await proxy?.close(); process.exit(1); });

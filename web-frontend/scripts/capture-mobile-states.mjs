import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import path from 'node:path';

const require = createRequire(import.meta.url);
const { encode } = require('next-auth/jwt');

const frontendUrl = process.env.FRONTEND_URL || 'http://localhost:3000';
const backendUrl = process.env.API_URL || 'http://localhost:8000';
const nextAuthSecret = process.env.NEXTAUTH_SECRET || 'your-secret-here-make-it-long-and-random';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const captureDir = path.resolve(process.env.CAPTURE_DIR || '../docs/mobile-visual-checks/latest');
const remotePort = Number(process.env.CHROME_DEBUG_PORT || 9333 + Math.floor(Math.random() * 400));
const previewEmail = process.env.PREVIEW_EMAIL || `mobile-capture-${Date.now()}@example.com`;
const previewPassword = process.env.PREVIEW_PASSWORD || 'previewsecurepassword';
const previewTheme = process.env.PREVIEW_THEME || 'light';

const viewport = {
  width: Number(process.env.CAPTURE_WIDTH || 390),
  height: Number(process.env.CAPTURE_HEIGHT || 844),
  deviceScaleFactor: Number(process.env.CAPTURE_SCALE || 3),
  mobile: true,
};
const shouldCreateFeuilletonScene = process.env.CAPTURE_CREATE_FEUILLETON === 'true';
let previewFeuilletonSceneId = process.env.CAPTURE_FEUILLETON_SCENE_ID || '';
let previewAccessToken = '';

const allFrames = [
  {
    name: 'mobile-primitives-static',
    route: '/mobile-visual-qa',
    waitFor: "Boolean(document.querySelector('[data-mobile-visual-qa]'))",
    public: true,
  },
  { name: 'atelier-home-active', route: '/atelier', waitFor: "/Begin session|Continue session|Session not ready/i.test(document.body.innerText)" },
  {
    name: 'atelier-more-sheet',
    route: '/atelier',
    waitFor: "/Begin session|Continue session|Session not ready/i.test(document.body.innerText)",
    action: async (client) => {
      await runAction(client, openAtelierSession());
      await waitForExpression(client, "Boolean(document.querySelector('.mobile-context-details summary'))", 5000);
      await runAction(client, clickFirst('.mobile-context-details summary'));
    },
  },
  {
    name: 'atelier-vocabulary-practice-sheet',
    route: '/atelier',
    waitFor: "/Begin session|Continue session|Session not ready/i.test(document.body.innerText)",
    action: async (client) => {
      await runAction(client, openAtelierSession());
      await waitForExpression(client, "Boolean(document.querySelector('.mobile-vocab-focus, .continue-vocab, .desktop-vocab-focus'))", 5000);
    },
  },
  {
    name: 'atelier-session-active',
    route: '/atelier',
    waitFor: "/Begin session|Continue session|Session not ready/i.test(document.body.innerText)",
    action: openAtelierSession(),
    afterActionDelay: 2500,
  },
  { name: 'notebook-list', route: '/grammar', waitFor: "document.body.innerText.includes('Grammar Notebook')" },
  {
    name: 'notebook-detail',
    route: '/grammar?concept=2',
    waitFor: "document.body.innerText.includes('Grammar Notebook')",
    action: clickConceptAndScrollToDetail(),
  },
  { name: 'vocabulary-notebook', route: '/vocabulary', waitFor: "document.body.innerText.includes('Vocabulary Notebook')" },
  {
    name: 'vocabulary-practice-sheet',
    route: '/vocabulary',
    waitFor: "document.body.innerText.includes('Vocabulary Notebook')",
    action: clickFirst('.vocab-row'),
    optional: true,
  },
  { name: 'missions-active-chat', route: '/missions', waitFor: "Boolean(document.querySelector('[data-testid=\"mobile-mission-switcher\"], [data-testid=\"mission-messenger\"], .mission-empty'))" },
  {
    name: 'missions-switcher-sheet',
    route: '/missions',
    waitFor: "Boolean(document.querySelector('[data-testid=\"mobile-mission-switcher\"], [data-testid=\"mission-messenger\"], .mission-empty'))",
    action: clickAria('Open mission switcher'),
  },
  {
    name: 'missions-custom-sheet-step-1',
    route: '/missions',
    waitFor: "Boolean(document.querySelector('[data-testid=\"mobile-mission-switcher\"], [data-testid=\"mission-messenger\"], .mission-empty'))",
    action: async (client) => {
      await runAction(client, clickAria('Open mission switcher'));
      await waitForExpression(client, "Boolean(document.querySelector('.mobile-mission-sheet .mobile-sheet-create'))", 5000);
      await runAction(client, clickFirst('.mobile-mission-sheet .mobile-sheet-create'));
      await waitForExpression(client, "Boolean(document.querySelector('.custom-mission-sheet'))", 5000);
    },
  },
  {
    name: 'missions-custom-e2e-recap',
    route: '/missions',
    waitFor: "Boolean(document.querySelector('[data-testid=\"mobile-mission-switcher\"], [data-testid=\"mission-messenger\"], .mission-empty'))",
    action: completeCustomMissionE2E(),
    afterActionWaitFor: "Boolean(document.querySelector('[data-testid=\"mobile-mission-debrief\"]'))",
    afterActionDelay: 1200,
  },
  {
    name: 'missions-voice-sheet',
    route: '/missions',
    waitFor: "Boolean(document.querySelector('[data-testid=\"mobile-mission-switcher\"], [data-testid=\"mission-messenger\"], .mission-empty'))",
    action: clickAria(/Record voice message|Stop recording/i),
    optional: true,
  },
  { name: 'feuilleton-active-or-empty', route: feuilletonRoute, waitFor: "document.body.innerText.includes('Feuilleton')" },
  {
    name: 'feuilleton-task-sheet',
    route: feuilletonRoute,
    waitFor: "document.body.innerText.includes('Feuilleton')",
    action: openFeuilletonTaskOrLockedState(),
    afterActionWaitFor: "Boolean(document.querySelector('.mobile-task-flyin, .mobile-bottom-sheet, [data-feuilleton-empty=\"true\"], .edition-preparing'))",
  },
  {
    name: 'feuilleton-final-task',
    route: feuilletonRoute,
    waitFor: "document.body.innerText.includes('Feuilleton')",
    action: scrollToFeuilletonFinalTask(),
    optional: true,
  },
  {
    name: 'serial-archive',
    route: '/serial',
    waitFor: "document.body.innerText.includes('Season 1') && Boolean(document.querySelector('.serial-page'))",
  },
  {
    name: 'serial-cast',
    route: '/serial/cast',
    waitFor: "document.body.innerText.includes('Cast') && Boolean(document.querySelector('.cast-page'))",
  },
  {
    name: 'serial-episode-detail',
    route: '/serial/episode/0',
    waitFor: "document.body.innerText.includes('Episode') && Boolean(document.querySelector('.replay-page'))",
  },
];

const requestedFrames = (process.env.CAPTURE_FRAMES || '')
  .split(',')
  .map((item) => item.trim())
  .filter(Boolean);
const frames = requestedFrames.length
  ? allFrames.filter((frame) => requestedFrames.includes(frame.name))
  : allFrames;
const skipAuth = process.env.CAPTURE_SKIP_AUTH === 'true' || (requestedFrames.length > 0 && frames.every((frame) => frame.public));

if (requestedFrames.length > 0 && frames.length === 0) {
  throw new Error(`No capture frames matched CAPTURE_FRAMES=${requestedFrames.join(',')}`);
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`${url} failed: ${response.status} ${await response.text()}`);
  }
  return response.json();
}

async function request(url, options = {}) {
  return fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
}

async function createPreviewSession() {
  const registerResponse = await request(`${backendUrl}/api/v1/auth/register`, {
    method: 'POST',
    body: JSON.stringify({
      email: previewEmail,
      password: previewPassword,
      full_name: 'Mobile Capture',
      native_language: 'de',
      target_language: 'fr',
      proficiency_level: 'A1',
      theme: previewTheme,
      font_size: 'medium',
    }),
  });

  if (!registerResponse.ok && registerResponse.status !== 400) {
    throw new Error(`Registration failed: ${registerResponse.status} ${await registerResponse.text()}`);
  }

  const tokenResponse = await requestJson(`${backendUrl}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: previewEmail, password: previewPassword }),
  });
  previewAccessToken = tokenResponse.access_token;

  const user = await requestJson(`${backendUrl}/api/v1/users/me`, {
    headers: { Authorization: `Bearer ${tokenResponse.access_token}` },
  });

  await request(`${backendUrl}/api/v1/users/me/settings`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${tokenResponse.access_token}` },
    body: JSON.stringify({ theme: previewTheme, font_size: 'medium' }),
  });

  if (shouldCreateFeuilletonScene && !previewFeuilletonSceneId) {
    const sceneResponse = await requestJson(`${backendUrl}/api/v1/graphic-novel/scenes`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${tokenResponse.access_token}`,
      },
      body: JSON.stringify({
        cadence: 'ad_hoc',
        use_news: false,
        panel_count: 6,
        render_mode: 'panels',
        image_quality: 'medium',
        force_new: true,
      }),
    });
    previewFeuilletonSceneId = sceneResponse.scene?.id || '';
  }

  const [, payload] = tokenResponse.access_token.split('.');
  const decoded = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));

  return encode({
    secret: nextAuthSecret,
    token: {
      id: user.id,
      email: user.email,
      name: user.full_name || user.email,
      accessToken: tokenResponse.access_token,
      refreshToken: tokenResponse.refresh_token,
      accessTokenExpires: decoded.exp * 1000,
    },
  });
}

function feuilletonRoute() {
  return previewFeuilletonSceneId
    ? `/graphic-novel?scene=${encodeURIComponent(previewFeuilletonSceneId)}`
    : '/graphic-novel';
}

async function waitForJson(url, attempts = 80) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return response.json();
    } catch {}
    await delay(100);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function createTab(url) {
  const response = await fetch(`http://127.0.0.1:${remotePort}/json/new?${encodeURIComponent(url)}`, {
    method: 'PUT',
  });
  if (!response.ok) throw new Error(`Could not create Chrome tab: ${response.status}`);
  return response.json();
}

function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let nextId = 1;
  const pending = new Map();

  ws.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else resolve(message.result || {});
  });

  return new Promise((resolve, reject) => {
    ws.addEventListener('open', () => {
      resolve({
        send(method, params = {}) {
          const id = nextId;
          nextId += 1;
          ws.send(JSON.stringify({ id, method, params }));
          return new Promise((commandResolve, commandReject) => {
            pending.set(id, { resolve: commandResolve, reject: commandReject });
          });
        },
        close() {
          ws.close();
        },
      });
    });
    ws.addEventListener('error', reject);
  });
}

async function waitForExpression(client, expression, timeoutMs = 10_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const result = await client.send('Runtime.evaluate', {
      expression: `Boolean(${expression})`,
      returnByValue: true,
    });
    if (result?.result?.value) return;
    await delay(200);
  }
  throw new Error(`Timed out waiting for expression: ${expression}`);
}

async function waitForRuntimeValue(client, expression, timeoutMs = 10_000, label = expression) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const result = await client.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
    });
    const value = result?.result?.value;
    if (value) return value;
    await delay(200);
  }
  throw new Error(`Timed out waiting for runtime value: ${label}`);
}

async function runAction(client, action) {
  if (!action) return;
  if (typeof action === 'function') {
    await action(client);
    return;
  }
  const result = await client.send('Runtime.evaluate', {
    expression: action,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result?.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || 'Action failed');
  }
  if (result?.result?.value === false) {
    throw new Error('Action target not found');
  }
}

function clickByText(selector, regex) {
  return `
    (() => {
      const pattern = ${regex.toString()};
      const el = Array.from(document.querySelectorAll(${JSON.stringify(selector)}))
        .find((node) => pattern.test((node.textContent || '').trim()));
      if (!el) return false;
      el.scrollIntoView({ block: 'center', inline: 'center' });
      el.click();
      return true;
    })()
  `;
}

function clickAria(label) {
  const matcher = typeof label === 'string' ? JSON.stringify(label) : label.toString();
  const isRegex = label instanceof RegExp;
  return `
    (() => {
      const matcher = ${matcher};
      const el = Array.from(document.querySelectorAll('[aria-label]'))
        .find((node) => ${isRegex ? "matcher.test(node.getAttribute('aria-label') || '')" : "(node.getAttribute('aria-label') || '') === matcher"});
      if (!el) return false;
      el.scrollIntoView({ block: 'center', inline: 'center' });
      el.click();
      return true;
    })()
  `;
}

function clickFirst(selector) {
  return `
    (() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return false;
      el.scrollIntoView({ block: 'center', inline: 'center' });
      el.click();
      return true;
    })()
  `;
}

function completeCustomMissionE2E() {
  return async (client) => {
    await runAction(client, createCustomMissionAndFocusComposer());
    const missionId = await waitForRuntimeValue(
      client,
      "new URL(window.location.href).searchParams.get('mission')",
      10_000,
      'custom mission id in URL',
    );
    if (!previewAccessToken) throw new Error('Custom mission E2E requires an authenticated preview token');
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${previewAccessToken}`,
    };
    await requestJson(`${backendUrl}/api/v1/missions/${encodeURIComponent(missionId)}/turns`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        text: 'Bonjour Madame Laurent, je dois constater que le chauffage ne fonctionne plus depuis hier soir. Pourriez-vous proposer un créneau de réparation cette semaine ?',
        mode: 'chat',
      }),
    });
    await requestJson(`${backendUrl}/api/v1/missions/${encodeURIComponent(missionId)}/complete`, {
      method: 'POST',
      headers,
    });
    await client.send('Page.navigate', { url: `${frontendUrl}/missions?mission=${encodeURIComponent(missionId)}` });
    await waitForExpression(client, "Boolean(document.querySelector('[data-testid=\"mobile-mission-debrief\"]'))", 20000);
    await runAction(client, `
      (() => {
        const el = document.querySelector('[data-testid="mobile-mission-debrief"]');
        if (!el) return false;
        el.scrollIntoView({ block: 'center', inline: 'nearest' });
        return true;
      })()
    `);
  };
}

function createCustomMissionAndFocusComposer() {
  return `
    (async () => {
      const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      const waitFor = async (matcher, timeoutMs = 18000, label = 'custom mission E2E step') => {
        const deadline = Date.now() + timeoutMs;
        while (Date.now() < deadline) {
          const value = typeof matcher === 'function' ? matcher() : document.querySelector(matcher);
          if (value) return value;
          await delay(250);
        }
        throw new Error('Timed out in custom mission E2E: ' + label);
      };
      const click = async (matcher, timeoutMs, label) => {
        const el = await waitFor(matcher, timeoutMs, label);
        el.scrollIntoView({ block: 'center', inline: 'center' });
        el.click();
        return el;
      };
      const setNativeValue = (el, value) => {
        const proto = el instanceof HTMLTextAreaElement
          ? HTMLTextAreaElement.prototype
          : el instanceof HTMLSelectElement
            ? HTMLSelectElement.prototype
            : HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
        if (setter) setter.call(el, value);
        else el.value = value;
        if (el._valueTracker) el._valueTracker.setValue('');
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      };

      await click('[aria-label="Open mission switcher"]', 18000, 'open switcher');
      await click('[data-testid="mission-switcher-create-custom"]', 18000, 'open custom sheet');
      await waitFor('[data-testid="custom-mission-sheet"]', 18000, 'custom sheet visible');

      setNativeValue(await waitFor('[data-testid="custom-mission-scenario"]', 18000, 'scenario field'), 'I need to text my landlord because the heating stopped last night and I need a repair appointment.');
      setNativeValue(await waitFor('[data-testid="custom-mission-outcome"]', 18000, 'outcome field'), 'The landlord confirms a repair slot this week.');
      setNativeValue(await waitFor('[data-testid="custom-mission-relationship"]', 18000, 'relationship field'), 'landlord');
      setNativeValue(await waitFor('[data-testid="custom-mission-register"]', 18000, 'register select'), 'polite formal');
      await delay(200);
      await click(() => {
        const button = document.querySelector('[data-testid="custom-mission-next"]');
        return button && !button.disabled ? button : null;
      }, 18000, 'topic next');

      await waitFor(() => /Target concepts/i.test(document.querySelector('#custom-mission-title')?.textContent || ''), 18000, 'target step title');
      await delay(500);
      const target = document.querySelector('[data-testid="custom-concept-option"], [data-testid="custom-vocabulary-option"]');
      if (target) target.click();
      await click(() => {
        const button = document.querySelector('[data-testid="custom-mission-next"]');
        return button && !button.disabled ? button : null;
      }, 18000, 'target next');

      await waitFor(() => /Confirm\\/name/i.test(document.querySelector('#custom-mission-title')?.textContent || ''), 18000, 'confirm step title');
      setNativeValue(await waitFor('[data-testid="custom-mission-name"]', 18000, 'mission name field'), 'Heating repair message');
      await delay(200);
      await click(() => {
        const button = document.querySelector('[data-testid="custom-mission-create"]');
        return button && !button.disabled ? button : null;
      }, 18000, 'create mission');

      const composer = await waitFor('[data-testid="mission-turn-textarea"]', 20000, 'mission composer after create');
      composer.scrollIntoView({ block: 'center', inline: 'center' });
      composer.focus();
      if (typeof composer.select === 'function') composer.select();
      return true;
    })()
  `;
}

function openAtelierSession() {
  return `
    (async () => {
      const button = Array.from(document.querySelectorAll('button'))
        .find((node) => /Continue session|Begin session/i.test((node.textContent || '').trim()));
      if (button) {
        button.scrollIntoView({ block: 'center', inline: 'center' });
        button.click();
        await new Promise((resolve) => setTimeout(resolve, 1800));
      }
      return Boolean(document.querySelector('.session-spread, .mobile-session-brief'));
    })()
  `;
}

function openFeuilletonTaskOrLockedState() {
  return `
    (() => {
      const taskButton = document.querySelector('.mobile-reading-bar button.primary:not(:disabled)');
      if (taskButton) {
        taskButton.scrollIntoView({ block: 'center', inline: 'center' });
        taskButton.click();
        return true;
      }
      const launcher = document.querySelector('.mobile-story-task-launcher.revealed, .mobile-story-task-launcher:not([aria-hidden="true"]), [aria-label*="story task" i], [aria-label*="Story task" i]');
      if (launcher) {
        launcher.scrollIntoView({ block: 'center', inline: 'center' });
        launcher.click();
        return true;
      }
      const fallback = Array.from(document.querySelectorAll('section, article, div, button'))
        .find((node) => /Task sheet locked|Create first scene|No scene on the stand/i.test((node.textContent || '').trim()));
      if (fallback) fallback.scrollIntoView({ block: 'center', inline: 'nearest' });
      return Boolean(fallback);
    })()
  `;
}

function scrollToFeuilletonFinalTask() {
  return `
    (() => {
      const finalTask = document.querySelector('.mobile-final-task-card');
      if (!finalTask) return false;
      finalTask.scrollIntoView({ block: 'center', inline: 'nearest' });
      return true;
    })()
  `;
}

function clickConceptAndScrollToDetail() {
  return `
    (async () => {
      const el = document.querySelector('.notebook-concept-row[data-active="false"], .notebook-concept-row, [data-concept-row], .concept-row, .notebook-row, button[aria-label*="Open"]');
      if (!el) return false;
      el.scrollIntoView({ block: 'center', inline: 'center' });
      el.click();
      let detail = null;
      for (let attempt = 0; attempt < 20; attempt += 1) {
        const activeRow = document.querySelector('.notebook-concept-row[data-active="true"]');
        detail = activeRow?.nextElementSibling?.matches('.notebook-mobile-detail')
          ? activeRow.nextElementSibling
          : document.querySelector('.notebook-detail, .notebook-reference-card, .notebook-detail-loading');
        if (detail) break;
        await new Promise((resolve) => setTimeout(resolve, 300));
      }
      if (!detail) return false;
      detail.scrollIntoView({ block: 'start', inline: 'nearest' });
      return true;
    })()
  `;
}

function scrollToNotebookDetail() {
  return `
    (async () => {
      let detail = null;
      for (let attempt = 0; attempt < 30; attempt += 1) {
        const activeRow = document.querySelector('.notebook-concept-row[data-active="true"]');
        detail = activeRow?.nextElementSibling?.matches('.notebook-mobile-detail')
          ? activeRow.nextElementSibling
          : document.querySelector('.notebook-detail, .notebook-reference-card, .notebook-detail-loading');
        if (detail) break;
        await new Promise((resolve) => setTimeout(resolve, 300));
      }
      if (!detail) return false;
      detail.scrollIntoView({ block: 'start', inline: 'nearest' });
      return true;
    })()
  `;
}

async function captureFrame(client, frame) {
  const route = typeof frame.route === 'function' ? frame.route() : frame.route;
  await client.send('Page.navigate', { url: `${frontendUrl}${route}` });
  await waitForExpression(client, "document.readyState === 'complete' || document.readyState === 'interactive'");
  if (frame.waitFor) await waitForExpression(client, frame.waitFor);
  await delay(1200);

  const record = {
    name: frame.name,
    route,
    path: path.join(captureDir, `${frame.name}.png`),
    ok: true,
    warning: null,
  };

  try {
    await runAction(client, frame.action);
    if (frame.afterActionWaitFor) await waitForExpression(client, frame.afterActionWaitFor, 5000);
    await delay(frame.afterActionDelay || 900);
  } catch (error) {
    if (!frame.optional) throw error;
    record.warning = error instanceof Error ? error.message : String(error);
  }

  const screenshot = await client.send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: process.env.FULL_PAGE === 'true',
    fromSurface: true,
  });
  await writeFile(record.path, Buffer.from(screenshot.data, 'base64'));
  return record;
}

await mkdir(captureDir, { recursive: true });
const sessionToken = skipAuth ? null : await createPreviewSession();
const userDataDir = path.join(tmpdir(), `mobile-capture-${Date.now()}`);
const chrome = spawn(chromePath, [
  '--headless=new',
  '--disable-gpu',
  '--hide-scrollbars',
  '--no-first-run',
  '--no-default-browser-check',
  `--remote-debugging-port=${remotePort}`,
  `--user-data-dir=${userDataDir}`,
  'about:blank',
], { stdio: 'ignore' });

const manifest = {
  capturedAt: new Date().toISOString(),
  frontendUrl,
  backendUrl,
  viewport,
  frames: [],
};

try {
  await waitForJson(`http://127.0.0.1:${remotePort}/json/version`);
  const tab = await createTab('about:blank');
  const client = await connect(tab.webSocketDebuggerUrl);
  await client.send('Network.enable');
  await client.send('Page.enable');
  await client.send('Emulation.setDeviceMetricsOverride', viewport);
  if (sessionToken) {
    await client.send('Network.setCookie', {
      name: 'next-auth.session-token',
      value: sessionToken,
      url: frontendUrl,
      path: '/',
      httpOnly: true,
      secure: false,
      sameSite: 'Lax',
    });
  }

  for (const frame of frames) {
    try {
      manifest.frames.push(await captureFrame(client, frame));
      console.log(`captured ${frame.name}`);
    } catch (error) {
      manifest.frames.push({
        name: frame.name,
        route: frame.route,
        ok: false,
        error: error instanceof Error ? error.message : String(error),
      });
      console.warn(`failed ${frame.name}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  client.close();
} finally {
  chrome.kill('SIGTERM');
  await writeFile(path.join(captureDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
  console.log(`manifest ${path.join(captureDir, 'manifest.json')}`);
}

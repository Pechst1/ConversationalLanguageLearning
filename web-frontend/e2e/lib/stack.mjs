// The walk's own stack: a throwaway Postgres database, the fake-provider API with the
// test clock, and a Next dev server with its own build directory. It never touches the
// owner's ports (3000, 8000, 8010, 8011) or databases: ports are picked free, the
// database name is atelier_walk_<timestamp>, and everything is torn down at the end.
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, createWriteStream, readFileSync, rmSync } from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
export const WEB_ROOT = path.resolve(here, '../..');
export const REPO_ROOT = path.resolve(WEB_ROOT, '..');
const RESERVED = new Set([3000, 8000, 8010, 8011]);

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function canListen(port, host) {
  return new Promise((resolve) => {
    const srv = net.createServer();
    // A host without IPv6 (some containers) cannot bind '::' at all: nothing can hold
    // the port there, so it does not count against it.
    srv.once('error', (e) => resolve(e.code === 'EAFNOSUPPORT' || e.code === 'EADDRNOTAVAIL'));
    srv.listen(port, host, () => srv.close(() => resolve(true)));
  });
}

/** A free port below the OS's ephemeral range (outgoing connections steal those). */
export async function freePort() {
  for (let i = 0; i < 200; i += 1) {
    const port = 21000 + Math.floor(Math.random() * 8000);
    if (RESERVED.has(port)) continue;
    if ((await canListen(port, '127.0.0.1')) && (await canListen(port, '::')) && (await canListen(port, '0.0.0.0'))) return port;
  }
  throw new Error('no free port found');
}

export function python() {
  if (process.env.WALK_PYTHON) return process.env.WALK_PYTHON;
  const venv = path.join(REPO_ROOT, 'venv/bin/python');
  return existsSync(venv) ? venv : 'python';
}

function pgUrls(dbName) {
  // Admin URL (to CREATE/DROP) and the app URL for the throwaway database.
  const admin = process.env.WALK_PG_ADMIN_URL || 'postgresql://localhost/postgres';
  const u = new URL(admin);
  const app = new URL(admin);
  app.pathname = `/${dbName}`;
  app.protocol = 'postgresql+psycopg2:';
  return { admin: u.toString(), app: app.toString() };
}

function pgAdmin(adminUrl, sql) {
  const code = [
    'import sys, psycopg2',
    'c = psycopg2.connect(sys.argv[1].replace("postgresql+psycopg2", "postgresql")); c.autocommit = True',
    'c.cursor().execute(sys.argv[2]); c.close()',
  ].join('\n');
  const r = spawnSync(python(), ['-c', code, adminUrl, sql], { encoding: 'utf8' });
  if (r.status !== 0) throw new Error(`postgres admin failed: ${r.stderr}`);
}

async function waitFor(url, { timeoutMs = 120000, ok = (r) => r.status < 500 } = {}) {
  const t0 = Date.now();
  let last = '';
  while (Date.now() - t0 < timeoutMs) {
    try {
      const r = await fetch(url);
      if (ok(r)) return;
      last = `HTTP ${r.status}`;
    } catch (e) {
      last = String(e.message || e);
    }
    await sleep(500);
  }
  throw new Error(`timed out waiting for ${url}: ${last}`);
}

/** The pages the walk opens (its web.log's «Compiling …» lines), compiled before it plays. */
export const WARM_ROUTES = [
  '/atelier',
  '/missions',
  '/graphic-novel',
  '/vocabulary',
  '/vocabulary/review',
  '/fertig',
  '/settings',
  '/audio-session',
  '/auth/signin',
  '/walk-warm-not-found',
];

/**
 * Production's story flags, read from `render.yaml`: every `STORY_*` key with its value.
 * The walk server runs with them, so CI plays the story as production serves it (the scene
 * record, the day contract and its re-ask, the stand-in page, the shared pages). Both
 * services carry the same values; a manifest where they differ is refused, since the walk
 * could match only one of them. `stack.test.mjs` fails when a key is not passed on.
 */
export function productionStoryFlags(text = readFileSync(path.join(REPO_ROOT, 'render.yaml'), 'utf8')) {
  const flags = {};
  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i += 1) {
    const key = lines[i].match(/^\s*-\s*key:\s*(STORY_[A-Z0-9_]+)\s*$/);
    if (!key) continue;
    const value = (lines[i + 1] || '').match(/^\s*value:\s*(?:"([^"]*)"|'([^']*)'|(\S+))\s*$/);
    if (!value) throw new Error(`render.yaml: ${key[1]} has no literal value on the next line`);
    const v = value[1] ?? value[2] ?? value[3];
    if (key[1] in flags && flags[key[1]] !== v) {
      throw new Error(`render.yaml: ${key[1]} is «${flags[key[1]]}» on one service and «${v}» on another`);
    }
    flags[key[1]] = v;
  }
  return flags;
}

/** The walk API's environment: the caller's, the throwaway database, then production's story flags. */
export function walkApiEnv({ dbUrl, tokenMinutes = 1, comptoir = false, web, base = process.env, storyFlags = productionStoryFlags() }) {
  return {
    ...base,
    DATABASE_URL: dbUrl,
    ACCESS_TOKEN_EXPIRE_MINUTES: String(tokenMinutes),
    ...(comptoir ? { REVUE_COMPTOIR_ENABLED: 'true' } : {}),
    BACKEND_CORS_ORIGINS: JSON.stringify([web, web.replace('localhost', '127.0.0.1')]),
    // Last: a shell that set one of these differently does not walk another story.
    ...storyFlags,
  };
}

export async function startStack({ logDir, secret, live = false, tokenMinutes = 1, revue = false, comptoir = false }) {
  if (live) throw new Error('--live is not wired up in this harness: it would make paid model calls.');
  mkdirSync(logDir, { recursive: true });
  // Two walks started in the same millisecond (two shards side by side) took one name,
  // and the loser's teardown dropped the winner's database: a random tail, and a stack
  // drops only a database it created.
  const dbName = `atelier_walk_${Date.now()}_${Math.floor(Math.random() * 1e6)}`;
  let created = false;
  const { admin, app: dbUrl } = pgUrls(dbName);
  const apiPort = await freePort();
  const webPort = await freePort();
  const children = [];
  // dbUrl: the season walk's fast-forward (scripts/walk_fast_forward.py) reads the learner's
  // season state from the same throwaway database.
  const stack = { dbName, dbUrl, apiPort, webPort, children };
  // Test data only, on the walk's own throwaway database (the name is checked below).
  stack.sql = (statement) => pgAdmin(dbUrl, statement);

  const log = (name) => createWriteStream(path.join(logDir, `${name}.log`));
  const stop = async () => {
    for (const child of children.reverse()) {
      try {
        process.kill(-child.pid, 'SIGTERM');
      } catch { /* already gone */ }
    }
    await sleep(800);
    try {
      if (created) pgAdmin(admin, `DROP DATABASE IF EXISTS ${dbName} WITH (FORCE)`);
    } catch (e) {
      console.error(`[walk] could not drop ${dbName}: ${e.message}`);
    }
    if (stack.distDir) rmSync(stack.distDir, { recursive: true, force: true });
  };
  stack.stop = stop;

  try {
    if (!dbName.startsWith('atelier_walk_')) throw new Error('refusing an unexpected database name');
    pgAdmin(admin, `CREATE DATABASE ${dbName}`);
    created = true;
    const t0 = Date.now();
    // `heads`: parallel work packages branch the migration graph until a merge revision
    // lands; the throwaway database takes every branch (WALK_ALEMBIC_TARGET overrides).
    const mig = spawnSync(python(), ['-m', 'alembic', 'upgrade', process.env.WALK_ALEMBIC_TARGET || 'heads'], {
      cwd: REPO_ROOT,
      env: { ...process.env, DATABASE_URL: dbUrl },
      encoding: 'utf8',
    });
    if (mig.status !== 0) throw new Error(`alembic upgrade head failed:\n${mig.stderr.slice(-2000)}`);
    // The core word list (A1 → C1), as production's entrypoint syncs it after every
    // migration (docker/entrypoint.sh). Without it the catalogue held only the season's
    // own dozen words: almost every tapped word had no lookup and no «Garder», and the
    // day-7 drill had no kept word to bring back on its line (a flake that depended on
    // whether the day's lines happened to use one of those words).
    const lex = spawnSync(python(), ['scripts/sync_core_lexicon.py'], {
      cwd: REPO_ROOT,
      env: { ...process.env, DATABASE_URL: dbUrl },
      encoding: 'utf8',
    });
    if (lex.status !== 0) throw new Error(`core lexicon sync failed:\n${lex.stderr.slice(-2000)}`);
    stack.migrateSeconds = (Date.now() - t0) / 1000;

    const web = `http://localhost:${webPort}`;
    const apiLog = log('api');
    // WP-120 phase D: `revue` starts the same API with La Revue on (e2e/lib/carte_server.py).
    // «Au comptoir» (`comptoir`, implies `revue`): the same server with its switch on.
    const server = revue || comptoir ? 'web-frontend/e2e/lib/carte_server.py' : 'scripts/dev_walk_server.py';
    const api = spawn(python(), [server, '--port', String(apiPort)], {
      cwd: REPO_ROOT,
      env: walkApiEnv({ dbUrl, tokenMinutes, comptoir, web }),
      detached: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    api.stdout.pipe(apiLog);
    api.stderr.pipe(apiLog);
    children.push(api);
    await waitFor(`http://127.0.0.1:${apiPort}/health`, { timeoutMs: 90000 });

    stack.distDir = path.join(WEB_ROOT, `.next-walk-${webPort}`);
    const webLog = log('web');
    const next = spawn('npx', ['next', 'dev', '-p', String(webPort)], {
      cwd: WEB_ROOT,
      env: {
        ...process.env,
        API_URL: `http://127.0.0.1:${apiPort}`,
        NEXT_PUBLIC_API_URL: `http://127.0.0.1:${apiPort}/api/v1`,
        NEXTAUTH_URL: web,
        NEXTAUTH_SECRET: secret,
        NEXT_DIST_DIR: path.basename(stack.distDir),
        NEXT_TELEMETRY_DISABLED: '1',
      },
      detached: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    next.stdout.pipe(webLog);
    next.stderr.pipe(webLog);
    children.push(next);
    await waitFor(`${web}/api/auth/csrf`, { timeoutMs: 120000, ok: (r) => r.ok });
    // The dev server compiles a page the first time it is asked for, and a request in
    // flight while it writes its manifests can fail: main's 7-day walk (run 43027305551,
    // A1 day 2) got a 500 on GET /api/auth/session («SyntaxError: Unexpected end of JSON
    // input») while /vocabulary/review compiled for the first time. Every page the walk
    // opens is compiled here, before any learner plays, so no walk request meets a compile.
    for (const route of WARM_ROUTES) {
      await fetch(`${web}${route}`, { redirect: 'manual', signal: AbortSignal.timeout(120000) }).catch(() => {});
    }

    stack.web = web;
    stack.api = `http://127.0.0.1:${apiPort}/api/v1`;
    stack.setClock = async (days) => {
      const r = await fetch(`${stack.api}/dev/test-clock`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ offset_days: days }),
      });
      if (!r.ok) throw new Error(`test clock refused: ${r.status} ${await r.text()}`);
    };
    return stack;
  } catch (e) {
    await stop();
    throw e;
  }
}

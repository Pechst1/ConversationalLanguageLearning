// The walk's own stack: a throwaway Postgres database, the fake-provider API with the
// test clock, and a Next dev server with its own build directory. It never touches the
// owner's ports (3000, 8000, 8010, 8011) or databases: ports are picked free, the
// database name is atelier_walk_<timestamp>, and everything is torn down at the end.
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, createWriteStream, rmSync } from 'node:fs';
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
    srv.once('error', () => resolve(false));
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

function python() {
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

export async function startStack({ logDir, secret, live = false, tokenMinutes = 1 }) {
  if (live) throw new Error('--live is not wired up in this harness: it would make paid model calls.');
  mkdirSync(logDir, { recursive: true });
  const dbName = `atelier_walk_${Date.now()}`;
  const { admin, app: dbUrl } = pgUrls(dbName);
  const apiPort = await freePort();
  const webPort = await freePort();
  const children = [];
  const stack = { dbName, apiPort, webPort, children };

  const log = (name) => createWriteStream(path.join(logDir, `${name}.log`));
  const stop = async () => {
    for (const child of children.reverse()) {
      try {
        process.kill(-child.pid, 'SIGTERM');
      } catch { /* already gone */ }
    }
    await sleep(800);
    try {
      pgAdmin(admin, `DROP DATABASE IF EXISTS ${dbName} WITH (FORCE)`);
    } catch (e) {
      console.error(`[walk] could not drop ${dbName}: ${e.message}`);
    }
    if (stack.distDir) rmSync(stack.distDir, { recursive: true, force: true });
  };
  stack.stop = stop;

  try {
    if (!dbName.startsWith('atelier_walk_')) throw new Error('refusing an unexpected database name');
    pgAdmin(admin, `CREATE DATABASE ${dbName}`);
    const t0 = Date.now();
    const mig = spawnSync(python(), ['-m', 'alembic', 'upgrade', 'head'], {
      cwd: REPO_ROOT,
      env: { ...process.env, DATABASE_URL: dbUrl },
      encoding: 'utf8',
    });
    if (mig.status !== 0) throw new Error(`alembic upgrade head failed:\n${mig.stderr.slice(-2000)}`);
    stack.migrateSeconds = (Date.now() - t0) / 1000;

    const web = `http://localhost:${webPort}`;
    const apiLog = log('api');
    const api = spawn(python(), ['scripts/dev_walk_server.py', '--port', String(apiPort)], {
      cwd: REPO_ROOT,
      env: {
        ...process.env,
        DATABASE_URL: dbUrl,
        ACCESS_TOKEN_EXPIRE_MINUTES: String(tokenMinutes),
        BACKEND_CORS_ORIGINS: JSON.stringify([web, `http://127.0.0.1:${webPort}`]),
      },
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

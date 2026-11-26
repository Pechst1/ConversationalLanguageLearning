// #1041: the walk failed `harness-ran` twice in three days before its first screen, with
// «timed out waiting for …/api/auth/csrf: HTTP 404»: the dev server was still compiling
// when the walk's single fixed budget ran out. These run the wait against small local
// servers that answer the way a cold `next dev` does.
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const MODULE = path.join(here, 'dev-server-ready.mjs');
const ready = () => import('./dev-server-ready.mjs');

/** A stand-in dev server: `answer(path, nth)` gives [status, delayMs] for the nth request to a path. */
async function devServer(answer) {
  const seen = {};
  const server = http.createServer((req, res) => {
    const p = (req.url || '').split('?')[0];
    seen[p] = (seen[p] || 0) + 1;
    const [status, delay = 0] = answer(p, seen[p]);
    if (status === null) return; // hangs, as a request held by a compile that never ends
    setTimeout(() => {
      res.writeHead(status, { 'content-type': 'text/plain' });
      res.end(String(status));
    }, delay);
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  return {
    web: `http://127.0.0.1:${server.address().port}`,
    seen,
    close: () => new Promise((resolve) => { server.closeAllConnections(); server.close(() => resolve()); }),
  };
}

test('#1041: the walk waits for its dev server with a tested module', () => {
  assert.ok(existsSync(MODULE), "the walk's web-server readiness wait is a unit-tested module: scripts/dev-server-ready.mjs");
});

test('#1041: a server that answers 404 while it compiles and 200 after is waited for', async () => {
  const { waitForDevServer } = await ready();
  const t0 = Date.now();
  const compiled = () => Date.now() - t0 > 700;
  const s = await devServer(() => [compiled() ? 200 : 404]);
  try {
    const result = await waitForDevServer(s.web, { compileMs: 5000, probeMs: 2000, intervalMs: 50 });
    assert.equal(result.probeWindows, 1);
    assert.ok(s.seen['/auth/signin'] > 1, 'the readiness page was polled through its 404s');
  } finally {
    await s.close();
  }
});

test('#1041: a csrf probe whose first window ends on a 404 is retried once, and the walk starts', async () => {
  const { waitForDevServer } = await ready();
  let firstProbe = 0;
  // The page is compiled; the csrf route still answers 404 for longer than one probe window.
  const s = await devServer((p) => {
    if (p !== '/api/auth/csrf') return [200];
    firstProbe ||= Date.now();
    return [Date.now() - firstProbe < 500 ? 404 : 200];
  });
  try {
    const result = await waitForDevServer(s.web, { compileMs: 2000, probeMs: 300, intervalMs: 50 });
    assert.equal(result.probeWindows, 2, 'the walk started on the retried probe');
  } finally {
    await s.close();
  }
});

test('#1041: a request held past the deadline by a compile does not end the wait on its answer', async () => {
  const { waitForDevServer } = await ready();
  // The first csrf request is held by a compile for longer than the whole window and then
  // answers 404, the way run 120 ended; the next one answers 200.
  const s = await devServer((p, nth) => (p !== '/api/auth/csrf' ? [200] : nth === 1 ? [404, 900] : [200]));
  try {
    const t0 = Date.now();
    const result = await waitForDevServer(s.web, { compileMs: 2000, probeMs: 400, intervalMs: 50 });
    assert.equal(result.probeWindows, 2);
    assert.ok(Date.now() - t0 < 900, 'the held request was cut at the window, not waited out');
  } finally {
    await s.close();
  }
});

test('#1041: a csrf route that never answers fails after one retry, naming both windows and the log', async () => {
  const { waitForDevServer } = await ready();
  const s = await devServer((p) => [p === '/api/auth/csrf' ? 404 : 200]);
  try {
    await assert.rejects(
      waitForDevServer(s.web, { compileMs: 2000, probeMs: 250, intervalMs: 50, context: () => 'web.log: ○ Compiling /api/auth/[...nextauth] ...' }),
      (e) => {
        assert.match(e.message, /\/api\/auth\/csrf after \/auth\/signin answered: HTTP 404, then on the retry HTTP 404/);
        assert.match(e.message, /web\.log: ○ Compiling/);
        return true;
      },
    );
  } finally {
    await s.close();
  }
});

test('#1041: a page that never compiles fails inside its budget, though its requests hang', async () => {
  const { waitForDevServer } = await ready();
  const s = await devServer(() => [null]);
  try {
    const t0 = Date.now();
    await assert.rejects(waitForDevServer(s.web, { compileMs: 400, probeMs: 200, intervalMs: 50 }), /\/auth\/signin to compile .*: no answer/);
    assert.ok(Date.now() - t0 < 1500, `the wait gave up after ${Date.now() - t0}ms`);
  } finally {
    await s.close();
  }
});

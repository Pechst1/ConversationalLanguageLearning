// When a `next dev` server a harness started is ready to be walked (#1041), kept out of the
// walk so the unit tests can run it and scripts/loop/red_green.py can prove it. The browser
// walk (e2e/lib/stack.mjs) and the La Forge reading shots (e2e/forge-reading-shots.mjs) wait
// with it.
//
// The walk used to poll `/api/auth/csrf` with one fixed 120 s budget from the moment it spawned
// the dev server, with no limit on a single request and no second look: a cold compile on a
// slow runner could hold one request across the deadline, and whatever that request answered
// (twice an HTTP 404 from a server still compiling) failed the walk before its first screen.
// Now the server's own readiness comes first, a page that answers 200 once it is compiled,
// with a budget that covers a cold compile; then the csrf probe, retried once before it fails.
//
// Plain ES module with no imports: the walk runs under bare node.

/** A cold `next dev` compile on a CI runner: the first page and its shared chunks (5 min). */
export const COLD_COMPILE_MS = 300000;
/** One window of the csrf probe once the server answered its page (1 min). */
export const PROBE_MS = 60000;
/** A page every walk opens and that answers 200 to a visitor with no session once compiled. */
export const READY_PATH = '/auth/signin';
/** The sign-in flow's first request: the walk cannot sign anyone in until it answers. */
export const PROBE_PATH = '/api/auth/csrf';

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Poll `url` until `ok(response)` or `budgetMs` has passed. Each request is cut off at the
 * deadline, so a request that hangs cannot hold the wait past its budget.
 *
 * @returns {Promise<{ready: boolean, last: string, ms: number, attempts: number}>}
 */
export async function pollUntil(url, { budgetMs, ok = (r) => r.ok, intervalMs = 500 } = {}) {
  const t0 = Date.now();
  const deadline = t0 + budgetMs;
  let last = 'no answer';
  let attempts = 0;
  while (attempts === 0 || Date.now() < deadline) {
    attempts += 1;
    try {
      const r = await fetch(url, { redirect: 'manual', signal: AbortSignal.timeout(Math.max(1, deadline - Date.now())) });
      await r.arrayBuffer().catch(() => {});
      if (ok(r)) return { ready: true, last: `HTTP ${r.status}`, ms: Date.now() - t0, attempts };
      last = `HTTP ${r.status}`;
    } catch (e) {
      last = e?.name === 'TimeoutError' ? `no answer within ${Math.round(budgetMs / 1000)}s` : String(e?.cause?.code || e?.message || e);
    }
    const left = deadline - Date.now();
    if (left <= 0) break;
    await pause(Math.min(intervalMs, left));
  }
  return { ready: false, last, ms: Date.now() - t0, attempts };
}

/**
 * Wait for a `next dev` server at `web` to be ready for a walk: `readyPath` answers 200 within
 * `compileMs`, then `probePath` answers 2xx within `probeMs`, its window retried once. Throws
 * an error that names every window and what it last heard; `context()` (e.g. the tail of the
 * server's log) is appended to it.
 */
export async function waitForDevServer(web, {
  compileMs = COLD_COMPILE_MS,
  probeMs = PROBE_MS,
  readyPath = READY_PATH,
  probePath = PROBE_PATH,
  intervalMs = 500,
  context = () => '',
} = {}) {
  const fail = (message) => {
    const extra = String(context() || '').trim();
    return new Error(extra ? `${message}\n${extra}` : message);
  };
  const page = await pollUntil(`${web}${readyPath}`, { budgetMs: compileMs, ok: (r) => r.status === 200, intervalMs });
  if (!page.ready) {
    throw fail(`timed out waiting for ${web}${readyPath} to compile (${Math.round(compileMs / 1000)}s): ${page.last}`);
  }
  const windows = [];
  for (let window = 0; window < 2; window += 1) {
    const probe = await pollUntil(`${web}${probePath}`, { budgetMs: probeMs, intervalMs });
    if (probe.ready) return { compiledMs: page.ms, probeWindows: windows.length + 1 };
    windows.push(probe.last);
  }
  throw fail(`timed out waiting for ${web}${probePath} after ${readyPath} answered: ${windows.join(', then on the retry ')}`);
}

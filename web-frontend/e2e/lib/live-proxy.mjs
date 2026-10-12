// The live walk's app server: serves the static native bundle (`out/`) and forwards
// every /api/ request to the real API, so the browser talks to one origin. Production
// only allows the app's own origin (capacitor://localhost) for CORS; a same-origin
// proxy reaches it without touching that setting.
import { createReadStream, existsSync, statSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.webp': 'image/webp',
  '.woff2': 'font/woff2',
  '.mp3': 'audio/mpeg',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
};

// Request headers the upstream must not see as-is: hop-by-hop ones, and the browser's
// own origin, which production would refuse.
const DROP_REQUEST = new Set(['host', 'origin', 'referer', 'connection', 'content-length', 'accept-encoding']);
// fetch() has already decoded the body, so its length and encoding no longer apply.
const DROP_RESPONSE = new Set(['content-encoding', 'content-length', 'transfer-encoding', 'connection', 'access-control-allow-origin', 'access-control-allow-credentials']);

function staticFile(root, urlPath) {
  const clean = decodeURIComponent(urlPath.split('?')[0]).replace(/\/+$/, '');
  const candidates = [clean, `${clean}/index.html`, `${clean}.html`];
  for (const rel of candidates) {
    const file = path.join(root, rel);
    if (!file.startsWith(root)) return null;
    if (existsSync(file) && statSync(file).isFile()) return file;
  }
  return null;
}

/**
 * Start the proxy. `upstream` is the API origin (no /api/v1), `root` the static
 * export. Returns { url, close }.
 */
export function startLiveProxy({ port, root, upstream, log = () => {} }) {
  const origin = upstream.replace(/\/+$/, '');
  const server = http.createServer(async (req, res) => {
    try {
      if (req.url.startsWith('/api/')) {
        const chunks = [];
        for await (const chunk of req) chunks.push(chunk);
        const headers = {};
        for (const [k, v] of Object.entries(req.headers)) if (!DROP_REQUEST.has(k)) headers[k] = v;
        const upstreamRes = await fetch(`${origin}${req.url}`, {
          method: req.method,
          headers,
          body: ['GET', 'HEAD'].includes(req.method) ? undefined : Buffer.concat(chunks),
          redirect: 'manual',
        });
        const out = {};
        upstreamRes.headers.forEach((v, k) => { if (!DROP_RESPONSE.has(k)) out[k] = v; });
        const body = Buffer.from(await upstreamRes.arrayBuffer());
        res.writeHead(upstreamRes.status, out);
        res.end(body);
        if (upstreamRes.status >= 500) log({ proxy: 'upstream-error', status: upstreamRes.status, path: req.url.split('?')[0] });
        return;
      }
      const file = staticFile(root, req.url) || path.join(root, '404.html');
      if (!existsSync(file)) { res.writeHead(404); res.end('not found'); return; }
      res.writeHead(file.endsWith('404.html') && !req.url.startsWith('/404') ? 404 : 200, {
        'content-type': TYPES[path.extname(file)] || 'application/octet-stream',
      });
      createReadStream(file).pipe(res);
    } catch (e) {
      log({ proxy: 'error', path: req.url, error: String(e.message || e).slice(0, 300) });
      res.writeHead(502);
      res.end('proxy error');
    }
  });
  return new Promise((resolve) => {
    server.listen(port, '127.0.0.1', () => resolve({
      url: `http://127.0.0.1:${port}`,
      close: () => new Promise((r) => server.close(() => r())),
    }));
  });
}

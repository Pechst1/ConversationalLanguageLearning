#!/usr/bin/env node
// Le Quartier · photograph a forged place the way a player first sees it, for the forge to look at.
//   node scripts/quartier/forge-render.mjs <site.json> <out-dir> [--size 390x844] [--scale 2]
// Writes one PNG per view (the arrival, the landmarks inside and out, the market, the edge, a
// look from above), a contact sheet of them all (`sheet.png`), and `render.json` with the load
// time and the frame's cost per view. The forge reads the sheet and decides what to revise.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

import { build } from 'esbuild';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '..', '..');
const require = createRequire(import.meta.url);
const { chromium } = require(path.join(web, 'node_modules/playwright'));

const args = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : fallback;
};
const [sitePathArg, outDirArg] = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
if (!sitePathArg || !outDirArg) {
  console.error('usage: forge-render.mjs <site.json> <out-dir> [--size 390x844] [--scale 2]');
  process.exit(2);
}
const sitePath = path.resolve(sitePathArg);
const outDir = path.resolve(outDirArg);
const [width, height] = opt('--size', '390x844').split('x').map(Number);
const scale = Number(opt('--scale', '2'));

const result = await build({
  entryPoints: [path.join(here, 'forge-view.ts')],
  bundle: true,
  write: false,
  format: 'iife',
  platform: 'browser',
  target: ['chrome100'],
  jsx: 'automatic',
  minify: true,
  legalComments: 'none',
  tsconfig: path.join(web, 'tsconfig.json'),
  define: { 'process.env.NODE_ENV': '"production"' },
  logLevel: 'warning',
});
const js = result.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
const site = fs.readFileSync(sitePath, 'utf8');
const font = (family, style, weight, file) => {
  const b64 = fs.readFileSync(path.join(web, 'public', 'fonts', file)).toString('base64');
  return `@font-face{font-family:'${family}';font-style:${style};font-weight:${weight};font-display:block;src:url(data:font/woff2;base64,${b64}) format('woff2');}`;
};
const html = `<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>${font('AtelierSerif', 'italic', '400 800', 'eb-garamond-italic-latin.woff2')}${font('AtelierSans', 'normal', '400 700', 'instrument-sans-latin.woff2')}html,body{margin:0;height:100%;background:#0d1430}</style></head><body><script>window.__SITE=${site.replace(/<\/script/gi, '<\\/script')};</script><script>${js}</script></body></html>`;

fs.mkdirSync(outDir, { recursive: true });
const page = path.join(outDir, 'view.html');
fs.writeFileSync(page, html);

// software WebGL, so the photographs come out the same on any machine; CHROMIUM_PATH (or a
// cloud sandbox's preinstalled browser) stands in when Playwright's own is not downloaded
async function launch() {
  const flags = { args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] };
  if (process.env.CHROMIUM_PATH) return chromium.launch({ ...flags, executablePath: process.env.CHROMIUM_PATH });
  try {
    return await chromium.launch(flags);
  } catch (e) {
    if (!fs.existsSync('/opt/pw-browsers/chromium')) throw e;
    return chromium.launch({ ...flags, executablePath: '/opt/pw-browsers/chromium' });
  }
}
const browser = await launch();
const tab = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: scale });
const errors = [];
tab.on('pageerror', (e) => errors.push(e.message));
tab.on('console', (m) => {
  if (m.type() === 'error') errors.push(m.text());
});
await tab.goto(`file://${page}`);
await tab.waitForFunction(() => window.__forge, null, { timeout: 240000 });
const state = await tab.evaluate(() => ({ ready: window.__forge.ready, error: window.__forge.error, loadMs: window.__forge.loadMs, views: window.__forge.views }));
if (!state.ready) {
  console.error(state.error);
  await browser.close();
  process.exit(1);
}
const shots = [];
for (let i = 0; i < state.views.length; i++) {
  const stats = await tab.evaluate((k) => window.__forge.show(k), i);
  const file = path.join(outDir, `${String(i + 1).padStart(2, '0')}-${state.views[i]}.png`);
  await tab.screenshot({ path: file });
  shots.push({ view: state.views[i], file: path.basename(file), triangles: stats.triangles, calls: stats.calls });
  console.log(`${state.views[i]}: ${(stats.triangles / 1000).toFixed(0)}k triangles, ${stats.calls} calls`);
}

// the contact sheet: every view at a glance, named
const cells = shots
  .map((s) => `<figure><img src="data:image/png;base64,${fs.readFileSync(path.join(outDir, s.file)).toString('base64')}"><figcaption>${s.view}</figcaption></figure>`)
  .join('');
const cols = Math.min(4, shots.length);
await tab.setViewportSize({ width: cols * 300 + 24, height: 400 });
await tab.setContent(`<style>body{margin:0;padding:12px;background:#f1ece1;font:600 14px system-ui}main{display:grid;grid-template-columns:repeat(${cols},300px);gap:0 0}figure{margin:0 0 8px}img{width:290px;display:block}figcaption{padding:4px 0}</style><main>${cells}</main>`);
await tab.screenshot({ path: path.join(outDir, 'sheet.png'), fullPage: true });
await browser.close();

fs.writeFileSync(path.join(outDir, 'render.json'), `${JSON.stringify({ size: [width, height, scale], loadMs: state.loadMs, shots, errors }, null, 2)}\n`);
fs.rmSync(page);
console.log(`loaded in ${state.loadMs} ms; ${shots.length} views and sheet.png in ${path.relative(process.cwd(), outDir)}${errors.length ? `; ${errors.length} page errors (render.json)` : ''}`);

#!/usr/bin/env node
// Le Quartier · photograph the cast in the round, for whoever is modelling them to look at.
//   node scripts/quartier/cast3d-sheet.mjs <out.png> [--people margaux_barman,lila_bonnet]
//        [--expression joie] [--ambiance matin|nuit|room] [--pose rest|bind] [--tile 300x460]
//        [--views "0,35,90,180"] [--variant m] [--acts '[{"gesture":"salut","u":0.5},{"walk":0.4}]']
// One row per person, one column per view (the last view a close-up of the face), printed by the
// quarter's own print pass in software WebGL so the sheet comes out the same on any machine.
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
const out = args.find((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
if (!out) {
  console.error('usage: cast3d-sheet.mjs <out.png> [--people a,b] [--expression e] [--ambiance matin|nuit|room] [--pose rest|bind] [--tile WxH] [--views "0,35,90,180"]');
  process.exit(2);
}
const [tw, th] = opt('--tile', '300x460').split('x').map(Number);
const views = opt('--views', '')
  .split(',')
  .filter(Boolean)
  .map((s) => {
    const [yaw, at, dist, fov, pitch] = s.split(':').map(Number);
    return { yaw, at: Number.isFinite(at) ? at : undefined, dist: Number.isFinite(dist) ? dist : undefined, fov: Number.isFinite(fov) ? fov : undefined, pitch: Number.isFinite(pitch) ? pitch : undefined };
  });
const config = {
  people: opt('--people', '').split(',').filter(Boolean),
  views: views.length ? views : undefined,
  tile: [tw, th],
  expression: opt('--expression', 'neutre'),
  ambiance: opt('--ambiance', 'matin'),
  pose: opt('--pose', 'rest'),
  variant: opt('--variant', undefined),
  acts: opt('--acts', '') ? JSON.parse(opt('--acts', '[]')) : undefined,
};

const result = await build({
  entryPoints: [path.join(here, 'cast3d-view.ts')],
  bundle: true,
  write: false,
  format: 'iife',
  platform: 'browser',
  target: ['chrome100'],
  jsx: 'automatic',
  minify: false,
  legalComments: 'none',
  tsconfig: path.join(web, 'tsconfig.json'),
  define: { 'process.env.NODE_ENV': '"production"' },
  logLevel: 'warning',
});
const js = result.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
const html = `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#f1ece1}</style></head><body><script>window.__CAST=${JSON.stringify(config)};</script><script>${js}</script></body></html>`;
const dir = fs.mkdtempSync(path.join(path.dirname(path.resolve(out)), '.cast3d-'));
const page = path.join(dir, 'view.html');
fs.writeFileSync(page, html);

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
const tab = await browser.newPage({ viewport: { width: 1200, height: 900 } });
const errors = [];
tab.on('pageerror', (e) => errors.push(e.message));
tab.on('console', (m) => {
  if (m.type() === 'error' || m.type() === 'warning') errors.push(`${m.type()}: ${m.text()}`);
});
await tab.goto(`file://${page}`);
await tab.waitForFunction(() => window.__castDone, null, { timeout: 300000 });
const done = await tab.evaluate(() => window.__castDone);
if (!done.ok) {
  console.error(done.error);
  await browser.close();
  process.exit(1);
}
const data = await tab.evaluate(() => document.querySelector('canvas').toDataURL('image/png'));
fs.writeFileSync(path.resolve(out), Buffer.from(data.split(',')[1], 'base64'));
await browser.close();
fs.rmSync(dir, { recursive: true, force: true });
console.log(JSON.stringify({ out: path.resolve(out), triangles: done.triangles, ms: done.ms, errors: errors.slice(0, 12) }));

#!/usr/bin/env node
/**
 * WP-116 · PNG snapshots of the drawn cast, for the places that must stay an <img>:
 * push and notification icons, Open Graph images.
 *
 *   node scripts/render-rigs.mjs            # writes public/assets/serial/drawn/<id>/portrait-<mood>.png
 *   node scripts/render-rigs.mjs --sheet <file.png>   # also a contact sheet of every rig and mood
 *
 * Rerun whenever a rig changes; cast-rig.test.js checks the snapshots exist.
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const Module = require('node:module');
require(path.join(ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(ROOT, 'node_modules/sucrase/register/tsx'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};
const React = require(path.join(ROOT, 'node_modules/react'));
const { renderToStaticMarkup } = require(path.join(ROOT, 'node_modules/react-dom/server'));
globalThis.React = React;
const { CastRig } = require(path.join(ROOT, 'components/cast/CastRig.tsx'));
const { RIGS } = require(path.join(ROOT, 'components/cast/cast-registry.ts'));
const { RIG_MOODS } = require(path.join(ROOT, 'components/cast/rig-kit.ts'));
const { chromium } = require(path.join(ROOT, 'node_modules/playwright'));

const OUT = path.join(ROOT, 'public/assets/serial/drawn');
const SIZE = 256;
const sheetIndex = process.argv.indexOf('--sheet');
const sheetPath = sheetIndex > 0 ? process.argv[sheetIndex + 1] : null;
const css = fs.readFileSync(path.join(ROOT, 'styles/cast-rig.css'), 'utf8');
const rig = (props) => renderToStaticMarkup(React.createElement(CastRig, { still: true, ...props }));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: SIZE, height: SIZE }, deviceScaleFactor: 1 });
let written = 0;
for (const def of RIGS) {
  if (def.faceless) continue;
  fs.mkdirSync(path.join(OUT, def.id), { recursive: true });
  for (const mood of RIG_MOODS) {
    await page.setContent(`<style>body{margin:0;background:transparent}${css}</style>${rig({ id: def.id, mood, crop: 'head', size: SIZE })}`);
    await page.locator('svg').screenshot({ path: path.join(OUT, def.id, `portrait-${mood}.png`), omitBackground: true });
    written += 1;
  }
}
console.log(`${written} portraits written to ${path.relative(ROOT, OUT)}`);

if (sheetPath) {
  const rows = RIGS.map((def) => {
    const full = rig({ id: def.id, crop: 'full', size: 150 });
    const heads = def.faceless ? '' : RIG_MOODS.map((mood) => `<div class="t">${rig({ id: def.id, mood, crop: 'head', size: 96 })}</div>`).join('');
    return `<div class="r"><div>${full}<p>${def.name}</p></div>${heads}</div>`;
  }).join('');
  const sheet = await browser.newPage({ viewport: { width: 760, height: 400 } });
  await sheet.setContent(`<style>body{margin:0;background:#f1ece1;font:12px sans-serif;color:#6f6857}.r{display:flex;gap:10px;align-items:flex-end;padding:8px 16px}.t{background:#f8f3e8;border-radius:14px;overflow:hidden}${css}</style>${rows}`);
  await sheet.screenshot({ path: sheetPath, fullPage: true });
  console.log(`contact sheet: ${sheetPath}`);
}
await browser.close();

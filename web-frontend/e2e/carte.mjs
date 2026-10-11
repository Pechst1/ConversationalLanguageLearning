#!/usr/bin/env node
// WP-120 phase D · the walk check `carte-shows-where-i-was`, on its own stack.
//
//   node e2e/carte.mjs [--lang en|de|fr] [--out DIR] [--keep]      (from web-frontend/)
//
// Same harness as `npm run walk` (throwaway database, fake providers, minted NextAuth
// cookie, free ports), but the API is started with La Revue on (e2e/lib/carte_server.py):
// the 7-day walk keeps the Revue off because it changes the day shapes. Screenshots and
// a contact sheet go to e2e/out/<stamp>-carte/. Any failed assertion → exit code 1.
import { chromium } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Findings } from './lib/assertions.mjs';
import { carteShowsWhereIWas } from './lib/carte-check.mjs';
import { writeContactSheet } from './lib/contact-sheet.mjs';
import { sleep, startStack } from './lib/stack.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : dflt;
};
const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
const outDir = path.resolve(opt('out', path.join(here, 'out', `${stamp}-carte`)));
const native = opt('lang', 'en');
const SECRET = 'e3-walk-secret-not-for-production';

mkdirSync(outDir, { recursive: true });
const findings = new Findings();
const shots = { root: outDir, list: [] };
const t00 = Date.now();
let stack;
let browser;
let result = null;
let exitCode = 0;
try {
  console.log(`[carte] output: ${outDir}`);
  stack = await startStack({ logDir: path.join(outDir, 'logs'), secret: SECRET, revue: true });
  console.log(`[carte] stack up: api :${stack.apiPort}, web :${stack.webPort}, db ${stack.dbName}`);
  // Warm the routes the check visits so the screenshots are not compile spinners.
  for (const route of ['/revue', '/carte', '/notebook?mode=releve', '/settings']) {
    await fetch(`${stack.web}${route}`).catch(() => {});
  }
  browser = await chromium.launch();
  result = await carteShowsWhereIWas({ stack, browser, findings, shots, outDir, secret: SECRET, native });
  console.log(`[carte] session ${result.sessionId} (${result.dossierId}) closed by ${result.closedBy}`);
  if (result.placement) console.log(`[carte] ${result.placement}`);
} catch (e) {
  console.error('[carte] harness error:', e);
  findings.check('harness-ran', false, String(e.stack || e).slice(0, 400), {});
  exitCode = 1;
} finally {
  if (browser) await browser.close().catch(() => {});
  const seconds = Math.round((Date.now() - t00) / 1000);
  const meta = `${new Date().toISOString()} · carte-shows-where-i-was · ${native} · fake provider · ${seconds}s`;
  writeContactSheet({ outDir, shots: shots.list, findings, meta });
  writeFileSync(path.join(outDir, 'report.json'), JSON.stringify({ meta, seconds, result, summary: findings.summary(), failures: findings.failures, shots: shots.list.length }, null, 2));
  if (stack && !argv.includes('--keep')) await stack.stop();
  await sleep(200);
  console.log(`\n[carte] ${shots.list.length} screens, ${findings.results.length} checks, ${findings.failures.length} failed, ${seconds}s`);
  for (const r of findings.summary()) console.log(`  ${r.fail ? 'FAIL' : ' ok '} ${r.id}: ${r.pass} pass, ${r.fail} fail`);
  console.log(`[carte] contact sheet: ${path.join(outDir, 'index.html')}`);
  if (findings.failures.length) exitCode = 1;
  process.exit(exitCode);
}

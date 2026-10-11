// WP-72 — copies the canonical legal text (app/data/legal/legal_content.json,
// served by the API at /privacy and /terms) into the web app, so the in-app
// pages render offline inside the native shell. Run after editing the JSON:
//
//   node scripts/sync-legal-content.mjs          # write the copy
//   node scripts/sync-legal-content.mjs --check  # exit 1 when they differ
//
// tests/test_wp72_legal.py and scripts/wp72-app-store.test.mjs fail on drift.
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
export const CANONICAL = path.join(webRoot, '..', 'app', 'data', 'legal', 'legal_content.json');
export const WEB_COPY = path.join(webRoot, 'lib', 'legal-content.json');

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const source = readFileSync(CANONICAL, 'utf8');
  JSON.parse(source);
  if (process.argv.includes('--check')) {
    let copy = '';
    try {
      copy = readFileSync(WEB_COPY, 'utf8');
    } catch {
      copy = '';
    }
    if (copy !== source) {
      console.error(`${path.relative(webRoot, WEB_COPY)} is out of date. Run node scripts/sync-legal-content.mjs.`);
      process.exit(1);
    }
    console.log('Legal content in sync.');
  } else {
    writeFileSync(WEB_COPY, source);
    console.log(`Wrote ${path.relative(webRoot, WEB_COPY)}.`);
  }
}

// Le Quartier · the map's Paris: the twenty arrondissements and the Seine from La Carte's own
// drawing (public/assets/carte/paris.svg), so the quarter's map and La Carte are one Paris, and the
// Canal Saint-Martin as lat/lon (from Overture Maps' base/water, `scripts/forge/survey.py canal`),
// which the map projects with La Carte's projection. Run after La Carte's drawing changes:
//   node scripts/quartier/sync-paris.mjs [canal.json]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '..', '..');
const target = path.join(web, 'lib', 'quartier', 'world', 'paris.json');
const svg = fs.readFileSync(path.join(web, 'public', 'assets', 'carte', 'paris.svg'), 'utf8');

const viewBox = /viewBox="([^"]+)"/.exec(svg)[1].split(/\s+/).map(Number);
const labels = {};
for (const m of svg.matchAll(/<text class="carte-label carte-label--arr" x="([\d.]+)" y="([\d.]+)"[^>]*>([^<]+)<\/text>/g)) {
  labels[parseInt(m[3], 10)] = { text: m[3], x: Number(m[1]), y: Number(m[2]) };
}
const arr = [];
for (const m of svg.matchAll(/<path class="carte-land carte-border" data-code="(\d+)" data-name="([^"]+)" d="([^"]+)"\/>/g)) {
  const n = Number(m[1]) - 75100;
  arr.push({ code: m[1], n, name: m[2], d: m[3], label: labels[n] ?? null });
}
const seine = /<path class="carte-seine" d="([^"]+)"/.exec(svg)[1];

const before = fs.existsSync(target) ? JSON.parse(fs.readFileSync(target, 'utf8')) : {};
const canalFile = process.argv[2];
const canal = canalFile ? JSON.parse(fs.readFileSync(canalFile, 'utf8')) : before.canal;
if (!canal) throw new Error('No canal yet: pass the survey’s canal.json');

const out = { source: 'public/assets/carte/paris.svg', viewBox, arr, seine, canal };
fs.writeFileSync(target, `${JSON.stringify(out)}\n`);
console.log(`wrote ${path.relative(web, target)} (${arr.length} arrondissements, ${(fs.statSync(target).size / 1024).toFixed(1)} kB)`);

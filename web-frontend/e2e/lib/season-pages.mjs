// WP-111: the tentpoles of season 1 the season learner must meet, each once, on its day.
// The weekend flex may move T2 by a day, never more.
//
// #717: a page is told by its line at the level the season served it, not by its A2
// line alone. The season adapts to the learner's CEFR estimate, and a walker who plays
// the whole day (La Forge and the word deck, with its scripted misses) drops from A2
// to A1 by the second week: the server served T2 on its day, in its A1 wording
// («Ton billet est pour aujourd'hui»), and the walk, looking for the A2 wording only,
// saw it on no day. The lines come from the season's own files (the bible's A2 and B1
// lines, and their A1/B2/C1 variants in levels*.json, keyed as app/services/season/levels.py
// keys them), so an edit to the bible cannot leave the walk looking for a stale line.
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

import { REPO_ROOT } from './stack.mjs';

export const SEASON_DIR = path.join(REPO_ROOT, 'app/data/season/s1');

// `line` is a fragment of the page's A2 line in `file`: it names the line, the season
// data gives every level of it.
export const SEASON_PAGES = [
  { key: 't1.a', file: 't1.json', line: 'Tu as une valise, une lettre et une clé.', days: [1] },
  { key: 't1.b', file: 't1.json', line: "Mon grand-père a tout l'immeuble", days: [2] },
  { key: 't2.a', file: 't2.json', line: "Tu devais partir aujourd'hui. Tu es encore là.", days: [7, 8, 9] },
  { key: 't2.b', file: 't2.json', line: "Lila Bonnet. Architecte d'intérieur.", days: [8, 9, 10] },
];

const LEVELS = ['a1', 'b1', 'b2', 'c1'];

// French print sets the apostrophe as ’ and thin spaces before ?!:; (lib/french-typography);
// the bible writes ' and plain spaces.
export function fold(text) {
  return String(text || '')
    .replace(/[’ʼ]/g, "'")
    .replace(/[  ]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

// app/services/season/levels.py `level_key`: the line's A2 text and its B1 text, if any.
export function levelKey(a2, b1 = null) {
  return createHash('sha256').update(`${String(a2).trim()}␟${String(b1 || '').trim()}`, 'utf8').digest('hex').slice(0, 12);
}

function* says(node) {
  if (Array.isArray(node)) {
    for (const item of node) yield* says(item);
  } else if (node && typeof node === 'object') {
    if (typeof node.a2 === 'string') yield node;
    for (const value of Object.values(node)) yield* says(value);
  }
}

function readLevels(dir) {
  const lines = {};
  for (const name of readdirSync(dir).filter((n) => /^levels.*\.json$/.test(n)).sort()) {
    const payload = JSON.parse(readFileSync(path.join(dir, name), 'utf8'));
    for (const [key, variants] of Object.entries(payload.lines || {})) Object.assign((lines[key] ||= {}), variants || {});
  }
  return lines;
}

// Every wording of the page's line: A2, then B1 (the bible's), then A1, B2, C1 (levels*.json).
export function pageLines(page, dir = SEASON_DIR) {
  const raw = JSON.parse(readFileSync(path.join(dir, page.file), 'utf8'));
  const say = [...says(raw)].find((node) => fold(node.a2).includes(fold(page.line)));
  if (!say) throw new Error(`${page.key}: no line «${page.line}» in ${page.file}`);
  const variants = readLevels(dir)[levelKey(say.a2, say.b1)] || {};
  const wordings = [say.a2, say.b1, ...LEVELS.map((level) => variants[level])].filter((text) => typeof text === 'string' && text.trim());
  return [...new Set(wordings.map(fold))];
}

// The days on which the walk read the page, in any wording.
export function daysSeen(page, pages, lines = pageLines(page)) {
  return [...new Set((pages || []).filter((row) => lines.some((line) => fold(row.text).includes(line))).map((row) => row.day))];
}

#!/usr/bin/env node
// Which browser walk a CI run plays (.github/workflows/walk.yml, job «Walk · scope»).
//
// Main, the nightly run and a manual run play all four shards at full length. A pull
// request plays them too when it changes the walk or what the walk walks through: the
// walk itself, the journey client, the day's engine, the story, the season and the
// judge (owner, 11 Nov 2026: five red main runs in a row were the walk meeting what
// only main played). Any other pull request plays the one short shard.
//
//   git diff --name-only HEAD^1 HEAD | node e2e/lib/walk-scope.mjs pull_request
//
// prints the matrix as one JSON line: {"full": bool, "include": [...]}.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export const FULL_WALK_PATHS = [
  /^web-frontend\/e2e\//,
  /^web-frontend\/components\/atelier-v2\/journey\//,
  /^web-frontend\/pages\/atelier\.tsx$/,
  /^app\/services\/daily_journey\.py$/,
  /^app\/services\/living_story\.py$/,
  /^app\/services\/season\//,
  /^app\/services\/judge\.py$/,
  /^\.github\/workflows\/walk\.yml$/,
];

export const SHARDS = [
  { shard: 'en + B1', days: 7, key: 'en-b1', args: '--langs en --b1-days 3 --season-days 0' },
  { shard: 'de', days: 7, key: 'de', args: '--langs de --b1-days 0 --season-days 0' },
  { shard: 'fr', days: 7, key: 'fr', args: '--langs fr --b1-days 0 --season-days 0' },
  { shard: 'season', days: 10, key: 'season', args: '--langs , --b1-days 0 --season-days 10' },
];

/** The short walk: en + B1 for 3 days (day 1, the Feuilleton entry, the last-day checks). */
export const SHORT = [{ ...SHARDS[0], days: 3, pr_args: '--days 3' }];

export function needsFullWalk(files) {
  return files.some((file) => FULL_WALK_PATHS.some((re) => re.test(file)));
}

export function walkMatrix(event, files) {
  const full = event !== 'pull_request' || needsFullWalk(files);
  return { full, include: full ? SHARDS.map((row) => ({ ...row, pr_args: '' })) : SHORT };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const files = readFileSync(0, 'utf8').split('\n').map((line) => line.trim()).filter(Boolean);
  process.stdout.write(`${JSON.stringify(walkMatrix(process.argv[2] || '', files))}\n`);
}

#!/usr/bin/env node
// A browser walk that fails on main (.github/workflows/walk-main.yml) no longer stops the
// deploy, so it becomes an issue in the night shift's queue: one open issue per failing
// check, titled by the check. A later failure of the same check comments on that issue;
// it never opens a second one.
//
//   node .github/scripts/walk-main-issue.mjs --reports DIR --run URL --sha SHA [--dry-run]
//
// DIR holds the walk artifacts (one folder per shard, each with its report.json). A shard
// that left no report (the harness died, a timeout) is filed under «walk-harness».
import { execFileSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const LABELS = ['walk-finding', 'queue:ready', 'lane:code', 'size:S'];
const MAX_LINES = 12;

export function titleFor(id) {
  return `Main walk fails: ${id}`;
}

/** Every report.json under `root`, with the shard it came from (its folder's name). */
export function readReports(root) {
  const found = [];
  if (!root || !existsSync(root)) return found;
  const walkDir = (dir) => {
    for (const name of readdirSync(dir)) {
      const full = path.join(dir, name);
      if (statSync(full).isDirectory()) walkDir(full);
      else if (name === 'report.json') found.push({ shard: path.relative(root, dir).split(path.sep)[0] || '.', report: JSON.parse(readFileSync(full, 'utf8')) });
    }
  };
  walkDir(root);
  return found;
}

/** The issues to file: one per failing check, its failure lines across the shards. */
export function issuesFrom(reports, { run, sha, shards = [] }) {
  const byCheck = new Map();
  for (const { shard, report } of reports) {
    for (const failure of report.failures || []) {
      const rows = byCheck.get(failure.id) || [];
      const where = failure.where && Object.keys(failure.where).length ? ` (${JSON.stringify(failure.where).slice(0, 160)})` : '';
      rows.push(`- \`${shard}\`: ${String(failure.detail || '').replace(/\s+/g, ' ').slice(0, 300)}${where}`);
      byCheck.set(failure.id, rows);
    }
  }
  const reported = new Set(reports.map((row) => row.shard));
  const silent = shards.filter((shard) => !reported.has(shard));
  if (!reports.length || silent.length) {
    byCheck.set('walk-harness', [`- no walk report from ${silent.length ? silent.map((s) => `\`${s}\``).join(', ') : 'any shard'}: the harness stopped before its summary (see the run's log)`]);
  }
  return [...byCheck.entries()].map(([id, lines]) => {
    const shown = lines.slice(0, MAX_LINES);
    if (lines.length > shown.length) shown.push(`- … and ${lines.length - shown.length} more in the run`);
    const failing = shown.join('\n');
    return {
      id,
      title: titleFor(id),
      body: [
        `The browser walk on main failed \`${id}\` for ${sha.slice(0, 12)}.`,
        '',
        failing,
        '',
        `Run: ${run}`,
        '',
        'This walk no longer holds the deploy (walk-main.yml), so the commit may already be live.',
        '',
        `Done when: the walk on main passes \`${id}\` again, or the failure is a narrow entry in web-frontend/e2e/lib/known-failures.mjs with its own issue.`,
      ].join('\n'),
      comment: [`Failed again on main for ${sha.slice(0, 12)}:`, '', failing, '', `Run: ${run}`].join('\n'),
    };
  });
}

function gh(args, input) {
  return execFileSync('gh', args, { encoding: 'utf8', input, stdio: [input ? 'pipe' : 'ignore', 'pipe', 'inherit'] });
}

function main(argv) {
  const opt = (name) => {
    const i = argv.indexOf(`--${name}`);
    return i >= 0 ? argv[i + 1] : '';
  };
  const dry = argv.includes('--dry-run');
  const reports = readReports(opt('reports'));
  const shards = opt('reports') && existsSync(opt('reports')) ? readdirSync(opt('reports')) : [];
  const issues = issuesFrom(reports, { run: opt('run'), sha: opt('sha') || 'unknown', shards });
  for (const issue of issues) {
    const open = dry ? [] : JSON.parse(gh(['issue', 'list', '--state', 'open', '--label', 'walk-finding', '--search', `"${issue.title}" in:title`, '--json', 'number,title']))
      .filter((row) => row.title === issue.title);
    if (dry) {
      console.log(`--- ${issue.title}\n${issue.body}\n`);
    } else if (open.length) {
      gh(['issue', 'comment', String(open[0].number), '--body-file', '-'], issue.comment);
      console.log(`commented on #${open[0].number}: ${issue.title}`);
    } else {
      const url = gh(['issue', 'create', '--title', issue.title, '--body-file', '-', ...LABELS.flatMap((l) => ['--label', l])], issue.body).trim();
      console.log(`opened ${url}`);
    }
  }
  if (!issues.length) console.log('the walk failed and no report names a check: nothing to file');
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main(process.argv.slice(2));

import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));
const output = fileURLToPath(new URL('../lib/generated/cast.ts', import.meta.url));

const quote = (value) => `'${String(value).replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`;
const list = (values) => `[${values.map(quote).join(', ')}]`;

/** The registry's rows as a TypeScript module. Pure: the freshness test feeds it a changed row. */
export function renderCast({ people }) {
  const ids = people.map((person) => person.id);
  const row = (person) => [
    `  ${person.id}: {`,
    `    id: ${quote(person.id)},`,
    `    name: ${quote(person.name)},`,
    `    fullName: ${quote(person.fullName)},`,
    `    spokenName: ${quote(person.spokenName)},`,
    `    address: ${person.address ? quote(person.address) : 'null'},`,
    `    hasDrawnFace: ${person.hasDrawnFace},`,
    `    firstDay: [${person.firstDay[0]}, ${quote(person.firstDay[1])}],`,
    `    tokens: ${list(person.tokens)},`,
    `    spellings: ${list(person.spellings)},`,
    '  },',
  ].join('\n');
  return [
    '/**',
    ' * Generated from app/services/cast_registry.py (scripts/export_cast.py).',
    ' * Do not edit: change the registry, then run npm run cast:generate.',
    ' */',
    '',
    `export type CastPersonId = ${ids.map(quote).join(' | ')};`,
    '',
    'export type CastPerson = {',
    '  id: CastPersonId;',
    '  /** What the learner reads. */',
    '  name: string;',
    "  /** The season bible's full name; a speaker label prints `name`, not this. */",
    '  fullName: string;',
    '  /** What the person says when naming themselves. */',
    '  spokenName: string;',
    "  /** How the person opens with the learner, before the season moves it. */",
    "  address: 'tu' | 'vous' | null;",
    '  hasDrawnFace: boolean;',
    '  /** (tentpole, day letter) of their first page. */',
    '  firstDay: [number, string];',
    '  /** Lowercase, unaccented words that mean this person, for reading a payload. */',
    '  tokens: string[];',
    '  /** Every way a text may spell them. */',
    '  spellings: string[];',
    '};',
    '',
    'export const CAST: Record<CastPersonId, CastPerson> = {',
    ...people.map(row),
    '};',
    '',
    '/** The one name the learner reads, by id. */',
    'export const CAST_NAMES: Record<CastPersonId, string> = {',
    ...people.map((person) => `  ${person.id}: ${quote(person.name)},`),
    '};',
    '',
  ].join('\n');
}

export function exportCast() {
  const localPython = `${root}venv/bin/python`;
  const python = process.env.OPENAPI_PYTHON || (existsSync(localPython) ? localPython : 'python');
  const result = spawnSync(python, ['scripts/export_cast.py'], {
    cwd: root, encoding: 'utf8', maxBuffer: 5 * 1024 * 1024,
  });
  if (result.error || result.status !== 0) {
    throw new Error(result.error?.message || result.stderr || 'Cast export failed');
  }
  return JSON.parse(result.stdout);
}

export function checkFreshness(expected, actual) {
  if (expected !== actual) {
    throw new Error('The generated cast is stale. Run npm run cast:generate and commit lib/generated/cast.ts.');
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const generated = renderCast(exportCast());
  if (process.argv.includes('--check')) {
    checkFreshness(generated, existsSync(output) ? readFileSync(output, 'utf8') : '');
    console.log('The generated cast is current.');
  } else {
    mkdirSync(fileURLToPath(new URL('../lib/generated/', import.meta.url)), { recursive: true });
    writeFileSync(output, generated);
    console.log('Generated lib/generated/cast.ts');
  }
}

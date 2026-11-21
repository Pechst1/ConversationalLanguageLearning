// node --test scripts/one-cast-table.test.mjs
//
// ROOT CAUSE #147: a person's name lives in the cast registry, and the client reads it from the
// module generated from there (lib/generated/cast.ts). No other source file keeps a table of
// the cast's names: an object, an array or a regular expression naming two people or more fails.
// The Python half is tests/test_one_cast_table_147.py.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const WEB_ROOT = fileURLToPath(new URL('..', import.meta.url));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
const { CAST } = require(path.join(WEB_ROOT, 'lib/generated/cast.ts'));

const SOURCES = ['lib', 'components', 'pages', 'hooks', 'services', 'contexts', 'utils'];
const GENERATED = new Set(['lib/generated/cast.ts']);
/**
 * file -> why. Empty, and it stays that way: read `CAST_NAMES`, `castDisplayName` or `castIdFor`.
 * An entry here with no table left fails too.
 */
const ALLOWED = new Map();

/**
 * Written names only, capitals included: «Margaux», «M. Marchand». A lowercase key («margaux»: a
 * colour, a rig, a hold) says which accent or figure, and prints nothing; `tokens` come from the
 * registry too, but a list of them is not what drifted.
 */
const WHO_BY_SPELLING = new Map();
for (const person of Object.values(CAST)) {
  for (const spelling of [person.name, person.spokenName, person.fullName, ...person.spellings]) {
    if (/^\p{Lu}/u.test(spelling)) WHO_BY_SPELLING.set(spelling, person.id);
  }
}

function whoIs(text) {
  return WHO_BY_SPELLING.get(String(text).trim());
}

function peopleInAlternation(pattern) {
  const plain = pattern.replace(/\\[bBwWsSdD]|\(\?:|[()^$+*?[\]]/g, '').replace(/\\\./g, '.');
  return new Set(plain.split('|').map(whoIs).filter(Boolean));
}

/** Every string literal under a node, but not under a call (a call's words are its own). */
function stringsUnder(node, found = []) {
  if (ts.isCallExpression(node) || ts.isArrowFunction(node) || ts.isFunctionExpression(node)) return found;
  if (ts.isStringLiteralLike(node)) found.push(node.text);
  // (`forEachChild` stops at the first truthy return: this callback returns nothing.)
  ts.forEachChild(node, (child) => {
    stringsUnder(child, found);
  });
  return found;
}

/** [line, people] for each literal in this source that names two people or more. */
export function tablesIn(source, fileName = 'x.ts') {
  const kind = fileName.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const file = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, kind);
  const found = [];
  const line = (node) => file.getLineAndCharacterOfPosition(node.getStart()).line + 1;
  const visit = (node) => {
    if (ts.isObjectLiteralExpression(node) || ts.isArrayLiteralExpression(node)) {
      const named = new Set(stringsUnder(node).map(whoIs).filter(Boolean));
      if (named.size >= 2) {
        found.push([line(node), [...named].sort()]);
        return; // the outermost literal is the table; its rows would only repeat it
      }
    } else if (ts.isRegularExpressionLiteral(node)) {
      const named = peopleInAlternation(node.text.replace(/^\/|\/[a-z]*$/g, ''));
      if (named.size >= 2) found.push([line(node), [...named].sort()]);
    } else if (ts.isStringLiteralLike(node) && node.text.includes('|')) {
      const named = peopleInAlternation(node.text);
      if (named.size >= 2) found.push([line(node), [...named].sort()]);
    }
    ts.forEachChild(node, visit);
  };
  visit(file);
  return found;
}

function sourceFiles() {
  const files = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === 'node_modules' || entry.name === '__fixtures__' || entry.name.startsWith('.')) continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (/\.(ts|tsx)$/.test(entry.name) && !/\.d\.ts$/.test(entry.name) && !/\.test\./.test(entry.name)) {
        files.push(path.relative(WEB_ROOT, full).split(path.sep).join('/'));
      }
    }
  };
  for (const dir of SOURCES) {
    try {
      walk(path.join(WEB_ROOT, dir));
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error;
    }
  }
  return files;
}

test('the guard sees a table in every shape', () => {
  const source = [
    "const A = { margaux_barman: 'Margaux', lila_bonnet: 'Lila' };",
    "const B = ['Gus', 'Romy'];",
    "const C = [['romy_tremblay', { name: 'Romy' }], ['marin_leveque', { name: 'Marin' }]];",
    'const D = /\\b(?:Margaux|Marin)\\b/;',
    "const E = 'Margaux|Lila';",
  ].join('\n');
  assert.deepEqual(tablesIn(source).map(([line]) => line), [1, 2, 3, 4, 5]);
});

test('the guard leaves alone what is not a table', () => {
  const source = [
    "const A = { id: 'margaux_barman', name: 'Margaux' };",
    "const B = 'Margaux et Lila parlent.';",
    "const C = ['romy_tremblay', 'marin_leveque'];",
    "const D = 'tu|vous';",
    "const E = { say: w('Marin', 'Lila', 'Gus') };",
    "const F = { margaux: 'var(--char-margaux)', gus: 'var(--char-gus)' };",
    "const G = ['romy', 'marin', 'lila'];",
    'const H = /odile|cafe creme|margaux/;',
  ].join('\n');
  assert.deepEqual(tablesIn(source), []);
});

test('no source file keeps a table of the cast names', () => {
  const offenders = {};
  for (const file of sourceFiles()) {
    if (GENERATED.has(file) || ALLOWED.has(file)) continue;
    const tables = tablesIn(readFileSync(path.join(WEB_ROOT, file), 'utf8'), file);
    if (tables.length) offenders[file] = tables;
  }
  assert.deepEqual(offenders, {}, 'read CAST_NAMES, castDisplayName or castIdFor (lib/cast-faces.ts)');
});

test('the allow-list is empty, and an entry on it would have to still hold a table', () => {
  assert.equal(ALLOWED.size, 0);
  for (const file of ALLOWED.keys()) {
    assert.ok(tablesIn(readFileSync(path.join(WEB_ROOT, file), 'utf8'), file).length, `${file}: take it off ALLOWED`);
  }
});

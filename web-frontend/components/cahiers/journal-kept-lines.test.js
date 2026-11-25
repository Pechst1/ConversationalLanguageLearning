// node --test components/cahiers/journal-kept-lines.test.js
//
// #1063 — live walk 25 Nov. «You recalled everything the scene kept (1/1).» named no
// line: only missed lines were listed, so the scene's opening line under «The scene as
// it was» (Camille's «Grand-père veut parler avec vous.») read as the line the check had
// used. The card lists every line it counted, the found ones first.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '../..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const journal = require('./JournalTab.tsx');

const MARCHAND = 'Je comprends. Votre grand-mère ne vous a rien dit. Alors on est deux.';
const SETUP = 'Marchand ouvre le dossier.';

const written = (recall) => ({
  id: 'e1',
  status: 'written',
  cue: { character_name: 'M. Marchand', location_name: 'La gérance Marchand', days_ago: 1 },
  content_recall: { version: 'journal-recall-v1', status: 'scored', facts_total: 2, ...recall },
  errata_recorded: 0,
});

test('a recall that found every line names the lines it found', () => {
  assert.equal(typeof journal.keptLines, 'function', 'the recall card lists the lines it counted');
  const entry = written({
    score: 1,
    facts_total: 1,
    matched: [{ key: 'scene:1:0', text_fr: MARCHAND, cues_hit: ['comprends', 'rien'] }],
    missed: [],
  });
  assert.deepEqual(journal.keptLines(entry), [{ key: 'scene:1:0', text_fr: MARCHAND, found: true }]);
});

test('found lines come first, then the missed ones; nothing for an unscored scene', () => {
  const entry = written({
    score: 0.5,
    matched: [{ key: 'b', text_fr: MARCHAND }],
    missed: [{ key: 'a', text_fr: SETUP }],
  });
  assert.deepEqual(
    journal.keptLines(entry).map((line) => [line.text_fr, line.found]),
    [
      [MARCHAND, true],
      [SETUP, false],
    ],
  );
  assert.deepEqual(journal.keptLines(written({ status: 'no_facts', matched: [], missed: [] })), []);
  assert.deepEqual(journal.keptLines(null), []);
});

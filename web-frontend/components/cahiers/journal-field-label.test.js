// node --test components/cahiers/journal-field-label.test.js
//
// #918 — live walk 19 Nov. The Journal asked about a scene its own label called
// «2 days ago», and the field the learner wrote in said «Yesterday, in French».
// The field says when the scene was, the way the label above it does.

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

const { cahierCopy } = require('./cahier-copy.ts');
const journal = require('./JournalTab.tsx');

const entry = (days) => ({
  id: 'e1',
  status: 'offered',
  cue: { character_name: 'Marin', location_name: 'Le Mistral', scene_date: '2026-11-17', days_ago: days },
});

/** The label the writing field shows; on main it was the table's one fixed line. */
function fieldLabel(item, t) {
  return typeof journal.entryFieldLabel === 'function' ? journal.entryFieldLabel(item, t) : t.field_label;
}

test('#918 · a scene from two days ago is not written about «Yesterday»', () => {
  const en = cahierCopy('en').journal;
  assert.match(journal.cueLine(entry(2), en), /^2 days ago/);
  const label = fieldLabel(entry(2), en);
  assert.doesNotMatch(label, /Yesterday/, `the field says «${label}» for a scene two days ago`);
  assert.equal(label, '2 days ago, in French');
  assert.equal(fieldLabel(entry(2), cahierCopy('fr').journal), 'Il y a 2 jours, en français');
  assert.equal(fieldLabel(entry(3), cahierCopy('de').journal), 'Vor 3 Tagen, auf Französisch');
});

test('#918 · yesterday’s scene still says yesterday', () => {
  for (const language of ['fr', 'en', 'de']) {
    const t = cahierCopy(language).journal;
    assert.equal(fieldLabel(entry(1), t), t.field_label, language);
    assert.equal(fieldLabel(entry(null), t), t.field_label, `${language}: no date, the plain label`);
  }
});

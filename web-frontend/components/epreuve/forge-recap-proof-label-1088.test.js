// node --test components/epreuve/forge-recap-proof-label-1088.test.js
//
// #1088 (walk of 26 Nov, a1-de-fresh, day 2): the end sheet listed, under «Avoir ·
// Stufe 3 · Weiterhin in Übung», the lines the séance proved. With the stage line right
// above them, «Weiterhin in Übung» read as «still practising these», on day 1 too
// («Elle est malade.», right first time). The proof list has its own label (what today's
// answers showed), apart from the stage line.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const Forge = require('./Forge.tsx');
const { forgeCopy } = require('@/lib/forge-copy.ts');
const P = require('@/lib/forge-progress.ts');

const h = React.createElement;
const text = (html) => html.replace(/<[^>]+>/g, '\n').replace(/&#x27;/g, "'").split('\n').map((line) => line.trim()).filter(Boolean);

const RECAP = {
  forge: {
    rules: [
      {
        concept_id: 3,
        rung: 2,
        stage_before: 'practising',
        stage: 'practising',
        held_today: false,
        next_due: '2026-11-28T08:00:00+00:00',
        proof: [{ fr: "Margaux demande ton âge. J'ai trente-cinq ans.", fixed: false }],
      },
    ],
  },
};
const CONCEPTS = [{ id: 3, title_fr: 'Avoir' }];
const NOW = new Date('2026-11-26T12:00:00+01:00');

for (const language of ['de', 'en', 'fr']) {
  test(`${language}: the proof lines have their own label, not the stage line above them`, () => {
    const fc = forgeCopy(language);
    const rows = P.recapRuleRows(RECAP, CONCEPTS, (c) => c.title_fr, fc, language, NOW);
    const html = renderToStaticMarkup(h(Forge.ForgeRecapRules, { copy: fc, rows, proofRight: 'right', proofFixed: 'fixed' }));
    const lines = text(html);
    const proof = lines.indexOf("Margaux demande ton âge. J'ai trente-cinq ans.");
    assert.ok(proof > 0, lines.join(' | '));
    const above = lines[proof - 1];
    assert.notEqual(above, rows[0].change, `«${rows[0].change}» stands right above what today proved: ${lines.join(' | ')}`);
    assert.ok(fc.recap_proof_label, `${language} has a label for the proof lines`);
    assert.equal(above, fc.recap_proof_label, lines.join(' | '));
    assert.doesNotMatch(fc.recap_proof_label, /\{stage\}|Weiterhin|Still|Toujours/);
    // The list is named by that label too, for a screen reader.
    assert.match(html, new RegExp(`<ul class="forge-recap__proof" aria-label="${fc.recap_proof_label.replace(/[’']/g, '.')}"`));
  });
}

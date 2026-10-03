// node --test components/revue/revue-releve.test.js
//
// WP-119 phase 3 · «Le Papier» in Le Relevé.
//
//   1. lib/revue-releve.ts parses the snake_case wire into RvReleveEntryData,
//      drops malformed rows, and a 404 is `{ enabled: false, entries: [] }`;
//   2. RvReleveSection draws the claims with their source lines («D'après
//      <Source>, <date>», the link in a new tab), the claim kind, the
//      attribution of an interpretation, the words with their glosses and the
//      made text; the anchors are #revue and #revue-<period>;
//   3. only the newest entry is open: older ones are the title and
//      «Ton titre · 4 mots · 2 faits»;
//   4. zero entries draw nothing;
//   5. Le Relevé mounts the section right after Le Registre.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const { h, render, visibleText, decode } = require('./revue-test-setup');

const releve = require('../../lib/revue-releve.ts');
const { RvReleveSection, initialOpen } = require('./RvReleveSection.tsx');
const { entrySummary, entryKicker } = require('./RvReleveEntry.tsx');
const { revueCopy } = require('./revue-copy.ts');
const { releveCopy } = require('./releve-copy.ts');

const NOW = new Date('2026-10-03T10:00:00+02:00');
const LE_MONDE = { id: 'src-lm', name: 'Le Monde', url: 'https://www.lemonde.fr/budget', published_at: '2026-09-29' };
const RFI = { id: 'src-rfi', name: 'RFI', url: 'https://www.rfi.fr/budget', published_at: '2026-09-30' };

function wireEntry(extra = {}) {
  return {
    session_id: 's-40',
    period: '2026-W40',
    period_label: 'Semaine 40',
    closed_at: '2026-10-02T18:30:00+02:00',
    title_fr: 'Le budget 2027 arrive au Parlement',
    headline_fr: 'Le budget 2027 va être débattu en octobre',
    made: { kind: 'headline_choice', text_fr: 'Le budget 2027 va être débattu en octobre' },
    claims: [
      { id: 'c1', kind: 'fact', fr: 'Le gouvernement présente le budget le 1er octobre.', quote: 'présenté le 1er octobre', attributed_to: null, source: LE_MONDE },
      { id: 'c2', kind: 'fact', fr: 'Le texte arrive à l’Assemblée en octobre.', quote: '', attributed_to: null, source: RFI },
      { id: 'c3', kind: 'interpretation', fr: 'Le budget sera difficile à voter.', quote: 'difficile', attributed_to: 'plusieurs économistes', source: LE_MONDE },
    ],
    words: [
      { fr: 'le budget', gloss: 'the budget', claim_id: 'c1', used: true },
      { fr: 'débattre', gloss: 'to debate', claim_id: 'c2', used: false },
      { fr: "l'Assemblée", gloss: 'the Assembly', claim_id: 'c2', used: false },
      { fr: 'voter', gloss: 'to vote', claim_id: 'c3', used: false },
    ],
    sources: [LE_MONDE, RFI],
    second: false,
    ...extra,
  };
}

const OLDER = wireEntry({
  session_id: 's-39',
  period: '2026-W39',
  period_label: 'Semaine 39',
  closed_at: '2026-09-25T18:00:00+02:00',
  title_fr: 'Les prix des produits frais',
  made: { kind: 'headline_write', text_fr: 'Les tomates coûtent plus cher' },
});

test('parse: snake_case → camelCase, malformed rows dropped', () => {
  const entries = releve.parseReleve({ entries: [wireEntry(), { period: 'x' }, OLDER, 'junk'] });
  assert.equal(entries.length, 2);
  const [first] = entries;
  assert.equal(first.sessionId, 's-40');
  assert.equal(first.period, '2026-W40');
  assert.equal(first.periodLabel, 'Semaine 40');
  assert.equal(first.date, '2026-10-02');
  assert.equal(first.titleFr, 'Le budget 2027 arrive au Parlement');
  assert.equal(first.headlineFr, 'Le budget 2027 va être débattu en octobre');
  assert.deepEqual(first.made, { kind: 'headline_choice', textFr: 'Le budget 2027 va être débattu en octobre' });
  assert.equal(first.claims[2].attributedTo, 'plusieurs économistes');
  assert.deepEqual(first.claims[0].source, { id: 'src-lm', name: 'Le Monde', url: 'https://www.lemonde.fr/budget', publishedAt: '2026-09-29' });
  assert.deepEqual(first.words[0], { fr: 'le budget', gloss: 'the budget', claimId: 'c1', used: true });
  assert.equal(first.sources.length, 2);
  assert.equal(first.second, false);
  // An unknown made kind is no made; tell_margaux is known.
  assert.equal(releve.parseReleveEntry(wireEntry({ made: { kind: 'poem', text_fr: 'x' } })).made, null);
  assert.equal(releve.parseReleveEntry(wireEntry({ made: { kind: 'tell_margaux', text_fr: 'Ça coûte cher.' } })).made.kind, 'tell_margaux');
  assert.deepEqual(releve.parseReleve(null), []);
  assert.equal(releve.releveAnchor('2026-W40'), 'revue-2026-W40');
});

test('client: GET /revue/releve; a 404 is the Revue switched off', async () => {
  const seen = [];
  const ok = releve.createReleveClient({
    get: async (url) => {
      seen.push(url);
      return { entries: [wireEntry()] };
    },
    post: async () => ({}),
  });
  const result = await ok.releve();
  assert.deepEqual(seen, ['/revue/releve']);
  assert.equal(result.enabled, true);
  assert.equal(result.entries.length, 1);

  const off = releve.createReleveClient({
    get: async () => {
      throw { response: { status: 404, data: { detail: 'Not Found' } } };
    },
    post: async () => ({}),
  });
  assert.deepEqual(await off.releve(), { enabled: false, entries: [] });

  const down = releve.createReleveClient({
    get: async () => {
      throw { response: { status: 500, data: {} } };
    },
    post: async () => ({}),
  });
  await assert.rejects(down.releve(), (error) => error.name === 'RevueError' && error.code === 'server');
});

test('the section: claims with source lines, kinds, attribution, words with glosses, the made text', () => {
  const entries = releve.parseReleve({ entries: [wireEntry(), OLDER] });
  const html = decode(render(h(RvReleveSection, { entries, language: 'en', now: NOW })));
  const text = visibleText(html);

  assert.match(html, /<section[^>]*id="revue"/);
  assert.match(html, /id="revue-2026-W40"/);
  assert.match(html, /id="revue-2026-W39"/);
  assert.match(text, /Le Papier/);
  assert.match(text, /2 clippings/);

  // The kicker and the outlets.
  assert.match(text, /Semaine 40 · 2 oct\./);
  assert.match(text, /Le Monde · RFI/);
  assert.match(text, /Le budget 2027 arrive au Parlement/);

  // What was made, quoted, under its label.
  assert.match(text, /Your headline/);
  assert.match(text, /« Le budget 2027 va être débattu en octobre »/);

  // Claims: kind, French, attribution, the source line linked in a new tab.
  // The claim kinds are the Revue's own labels (French in every chrome).
  assert.match(text, /Fait/);
  assert.match(text, /Interprétation/);
  assert.match(text, /Le gouvernement présente le budget le 1er octobre\./);
  assert.match(text, /d'après plusieurs économistes/);
  assert.match(html, /data-kind="interpretation"/);
  assert.match(text, /From Le Monde, 29 sept\./);
  assert.match(text, /From RFI, 30 sept\./);
  assert.match(html, /<a href="https:\/\/www\.lemonde\.fr\/budget" target="_blank" rel="noopener noreferrer"/);

  // Words as chips: token, French, gloss.
  assert.equal((html.match(/data-releve-word=""/g) || []).length, 4);
  assert.match(text, /le budget the budget/);
  assert.match(text, /débattre to debate/);
  assert.match(html, /av2-word-token/);

  // A clipping, not a story day: no seal, no face.
  assert.doesNotMatch(html, /av2-portrait|cast-portrait|nb-seal/);
});

test('French chrome: «D\'après Le Monde, 29 sept.» and «2 coupures»', () => {
  const entries = releve.parseReleve({ entries: [wireEntry(), OLDER] });
  const text = visibleText(decode(render(h(RvReleveSection, { entries, language: 'fr', now: NOW }))));
  assert.match(text, /D'après Le Monde, 29 sept\./);
  assert.match(text, /2 coupures/);
  assert.match(text, /Fait/);
  assert.match(text, /Interprétation/);
});

test('only the newest is open; older ones are the title and «Ton titre · 4 mots · 2 faits»', () => {
  const entries = releve.parseReleve({ entries: [wireEntry(), OLDER] });
  const html = decode(render(h(RvReleveSection, { entries, language: 'fr', now: NOW })));
  const older = html.slice(html.indexOf('id="revue-2026-W39"'));
  const newer = html.slice(html.indexOf('id="revue-2026-W40"'), html.indexOf('id="revue-2026-W39"'));

  assert.match(visibleText(older), /Les prix des produits frais/);
  assert.match(visibleText(older), /Ton titre · 4 mots · 2 faits/);
  assert.doesNotMatch(older, /data-releve-word/);
  assert.doesNotMatch(older, /rv-claim"/);
  assert.match(older, /aria-expanded="false"/);

  assert.doesNotMatch(newer, /data-releve-summary/);
  assert.match(newer, /aria-expanded="true"/);

  const copy = revueCopy('fr');
  const words = releveCopy('fr');
  assert.equal(entrySummary(entries[1], copy, words), 'Ton titre · 4 mots · 2 faits');
  const single = releve.parseReleveEntry(wireEntry({ made: null, words: [wireEntry().words[0]], claims: [wireEntry().claims[0]] }));
  assert.equal(entrySummary(single, copy, words), '1 mot · 1 fait');
  assert.equal(entryKicker(entries[0], NOW), 'Semaine 40 · 2 oct.');

  // The hash opens the entry it names, beside the newest.
  const open = initialOpen(entries, '#revue-2026-W39');
  assert.deepEqual([...open].sort(), ['s-39', 's-40']);
  assert.deepEqual([...initialOpen(entries, null)], ['s-40']);
});

test('zero entries draw nothing', () => {
  assert.equal(render(h(RvReleveSection, { entries: [], language: 'fr' })), '');
});

test('Le Relevé mounts the section right after Le Registre', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'releve', 'Releve.tsx'), 'utf8');
  const registre = source.indexOf('---- Le Registre ----');
  const papier = source.indexOf('<RvReleveSection');
  const collection = source.indexOf('---- La Collection ----');
  assert.ok(registre > 0 && papier > registre && collection > papier);
});

// node --test components/revue/rdv/rdv.test.js
//
// «Papier · les rendez-vous» (2026-11-21), the client:
//
//   1. the wire: real payloads (fixtures/rdv-payloads.json, dumped from the backend's services)
//      parsed; a 404 (the switch off) resolves null and the surfaces draw nothing;
//   2. «Trois mots»: the pairing, no solution and no gloss before the match is resolved, a miss
//      said in the mother tongue (under French chrome too) without the right cue, the gap from
//      the story's own sentence, the solution only after;
//   3. the regular's line with its translation; «La une de la semaine» as plain semantic markup
//      (masthead, dateline, articles, lexique, count line); «La carte de presse»; every string in
//      fr, en and de;
//   4. the dev mock answers the routes the server's way (and 404 while `rdv` is off).

const assert = require('node:assert/strict');
const { test } = require('node:test');

const setup = require('../revue-test-setup');

const { h, render, visibleText, fixture } = setup;

const rdv = require('../../../lib/revue-rdv.ts');
const mockRdv = require('../../../lib/revue-mock-rdv.ts');
const uneHome = require('../../../lib/revue-une-semaine.ts');
const model = require('./rdv-model.ts');
const copyMod = require('./rdv-copy.ts');
const { RvTroisMotsView, RvUneSemaine, RvCarteDePresseCard, RvSouvenirLine, RvTroisMotsSlot } = require('./index.ts');

const P = fixture('rdv-payloads');
const round = (name) => rdv.parseTroisMotsResult(P[name]).round;
const noop = () => {};

function view(r, { pairs = {}, chrome = 'en', mother = 'en' } = {}) {
  return render(
    h(RvTroisMotsView, { round: r, pairs, copy: copyMod.rdvCopy(chrome), xcopy: copyMod.rdvCopy(mother), pending: false, onPairs: noop, onAct: noop }),
  );
}

// ---------------------------------------------------------------------------
// 1 · the wire
// ---------------------------------------------------------------------------

test('the real payloads parse into camelCase', () => {
  const open = round('round_open');
  assert.equal(open.step, 'match');
  assert.deepEqual(open.words.map((w) => w.fr), ['la fête', 'le bruit', 'les rues']);
  assert.deepEqual(open.words.map((w) => w.bareFr), ['fête', 'bruit', 'rues']);
  assert.ok(open.words.every((w) => w.gloss === null), 'no gloss before the match is resolved');
  assert.equal(open.match.solution, null);
  assert.equal(open.gap.solution, null);
  assert.equal(open.gap.sentenceFr, null);
  const line = rdv.parseSouvenir(P.souvenir);
  assert.equal(line.speakerFr, 'Gus');
  assert.equal(line.fr, "La dernière fois, tu étais contre moi. Et aujourd'hui ?");
  const une = rdv.parseUne(P.une);
  assert.deepEqual(une.items.map((i) => i.rubrique), ['titre', 'opinion', 'intox']);
  assert.equal(une.rubriquesFiled, 4);
  assert.equal(rdv.parseCarteDePresse(P.carte).rubriques.length, 6);
  assert.equal(rdv.parseSouvenir({ line: null }), null);
});

test('a 404 (the switch off) resolves null; the act body is snake_case', async () => {
  const off = { get: async () => Promise.reject({ response: { status: 404 } }), post: async () => ({}) };
  const client = rdv.createRdvClient(off);
  assert.equal(await client.souvenir('s'), null);
  assert.equal(await client.troisMots('s'), null);
  assert.equal(await client.une(), null);
  assert.equal(await client.carteDePresse(), null);
  const fail = rdv.createRdvClient({ get: async () => Promise.reject({ response: { status: 500 } }), post: async () => ({}) });
  await assert.rejects(() => fail.une());
  const seen = [];
  const client2 = rdv.createRdvClient({ get: async (u) => (seen.push(u), {}), post: async (u, b) => (seen.push([u, b]), P.round_gap) });
  await client2.troisMotsAct('id 1', { act: 'gap', word: 'b' });
  await client2.une('2026-W47');
  assert.deepEqual(seen, [['/revue/sessions/id%201/trois-mots', { act: 'gap', word: 'b' }], '/revue/une?week=2026-W47']);
});

// ---------------------------------------------------------------------------
// 2 · «Trois mots»
// ---------------------------------------------------------------------------

test('a tapped cue goes to the first word without one; a tapped word lets it go', () => {
  let pairs = {};
  pairs = model.pairCue(pairs, '2');
  pairs = model.pairCue(pairs, '1');
  assert.deepEqual(pairs, { a: '2', b: '1' });
  pairs = model.pairCue(pairs, '2'); // already a's: moves to c
  assert.deepEqual(pairs, { b: '1', c: '2' });
  assert.equal(model.activeWord(pairs), 'a');
  assert.equal(model.complete(pairs), false);
  pairs = model.pairCue(pairs, '3');
  assert.equal(model.complete(pairs), true);
  assert.deepEqual(model.unpair(pairs, 'b'), { a: '3', c: '2' });
});

test('the open round: the words, the cues in the mother tongue, «Check» waits for three pairs, no solution', () => {
  const html = view(round('round_open'));
  const text = visibleText(html);
  assert.match(text, /Trois mots/);
  assert.match(text, /Match each word to its meaning\./);
  for (const cue of ['party', 'noise', 'streets']) assert.ok(text.includes(cue));
  assert.match(html, /disabled="" data-tone="primary"><span>Check/);
  assert.ok(!/____/.test(html), 'the gap waits for the match');
  assert.ok(!/data-correct/.test(html));
});

test('a miss says, in the mother tongue under French chrome, which pairs were wrong — never the right cue', () => {
  const r = round('round_miss');
  assert.equal(r.match.tries, 1);
  assert.equal(r.match.resolved, false);
  const lines = model.missLines(r, copyMod.rdvCopy('de'));
  assert.equal(lines.length, 2);
  for (const line of lines) assert.match(line, /^„(fête|bruit|rues)“ bedeutet nicht „(party|noise|streets)“\.$/);
  const html = view(r, { pairs: { a: '1', b: '2', c: '3' }, chrome: 'fr', mother: 'de' });
  const text = visibleText(html);
  assert.match(text, /Relie chaque mot à son sens\./, 'French chrome');
  assert.match(text, /bedeutet nicht/, 'the reason in German');
  assert.match(text, /Versuch es noch einmal\./);
  assert.ok(r.words.every((w) => w.gloss === null), 'still no gloss: no solution before the retry');
  assert.equal(r.match.solution, null);
});

test('the gap: the story\'s own sentence with a blank, three options, then the miss in the mother tongue, then the sentence whole', () => {
  const gapRound = round('round_gap');
  assert.equal(gapRound.step, 'gap');
  assert.equal(gapRound.match.correct, true);
  let text = visibleText(view(gapRound));
  assert.match(text, /All three, right\./);
  assert.match(text, /Le 21 juin, des musiciens amateurs et professionnels jouent gratuitement dans les ____ , les bars et sur les places\./);
  assert.match(text, /Which word goes in the sentence\?/);
  const missed = round('round_gap_miss');
  assert.equal(missed.gap.solution, null);
  text = visibleText(view(missed, { chrome: 'fr', mother: 'en' }));
  assert.match(text, /“(fête|bruit)” means “(party|noise)”: it does not fit this sentence\./);
  assert.ok(!text.includes('rues ,') && !/Voici la phrase/.test(text));
  const done = round('round_done');
  assert.equal(done.step, 'done');
  text = visibleText(view(done, { chrome: 'de', mother: 'de' }));
  assert.match(text, /Richtig: Das ist der Satz aus dem Artikel\./);
  assert.match(text, /dans les rues , les bars/);
  assert.match(text, /Diese drei Wörter kommen morgen wieder/);
});

test('the slot draws nothing without the page\'s client or before the close', () => {
  assert.equal(render(h(RvTroisMotsSlot, { sessionId: 's', chrome: 'en', mother: 'en', closed: true })), '');
});

// ---------------------------------------------------------------------------
// 3 · the line, la une, la carte
// ---------------------------------------------------------------------------

test('the regular\'s line: French, with its translation in the mother tongue', () => {
  const line = rdv.parseSouvenir(P.souvenir);
  assert.equal(model.souvenirTranslation(line, 'de'), 'Letztes Mal warst du gegen mich. Und heute?');
  assert.equal(model.souvenirTranslation(line, 'fr'), null);
  const props = {
    copy: require('../revue-copy.ts').revueCopy('en'),
    ccopy: require('../comptoir/comptoir-copy.ts').comptoirCopy('en'),
    glossLanguage: 'en',
    glosses: [],
    voice: { supported: false, playing: null, play: noop, stop: noop },
    wordFor: () => noop,
  };
  const html = render(h(RvSouvenirLine, { line, props, language: 'en' }));
  const text = visibleText(html.replace(/<style[\s\S]*?<\/style>/g, ' '));
  assert.match(text, /Gus/);
  assert.match(text.replace(/\s+([,.?])/g, '$1'), /La dernière fois, tu étais contre moi\./);
  assert.match(html, /data-souvenir="opinion\.contre_moi\.a1"/);
});

test('la une: masthead, dateline, one article per printed piece, a titre leading, the lexique, the count line', () => {
  const une = rdv.parseUne(P.une);
  for (const [language, count] of [['fr', '4 rubriques sur 6 cette semaine'], ['en', '4 of 6 sections this week'], ['de', '4 von 6 Rubriken diese Woche']]) {
    const html = render(h(RvUneSemaine, { une, language }));
    const text = visibleText(html);
    assert.match(html, /<header class="une__mast"><h1[^>]*>La une de la semaine<\/h1>/);
    assert.ok(text.includes('Semaine 47 · '));
    assert.ok(text.includes(count), language);
    assert.equal((html.match(/<article /g) || []).length, 3);
    assert.match(html, /<article class="une-item" data-role="headline" data-lead=""[^>]*><p class="une-item__k">Le titre · mardi<\/p><h2 class="une-item__hl">Le bac commence lundi<\/h2>/);
    assert.match(text, /« À mon avis, c'est une très bonne nouvelle pour les musiciens\. » Toi · pour/);
    assert.match(text, /4 sur 5/);
    assert.match(html, /<section class="une__lexique"[^>]*><h2 id="une-lexique">Lexique<\/h2><ul><li>la fête<\/li>/);
    assert.ok(!text.includes('comence') && !text.includes('Raw draft'), 'printed text only');
  }
  const empty = render(h(RvUneSemaine, { une: rdv.parseUne(P.une_empty), language: 'de' }));
  assert.match(visibleText(empty), /Diese Woche ist noch nichts abgelegt\./);
  assert.ok(!/<article/.test(empty) && !/Lexique/.test(empty));
});

test('la carte de presse: the six rubriques, pieces, since when — no points, no streak', () => {
  const card = rdv.parseCarteDePresse(P.carte);
  const html = render(h(RvCarteDePresseCard, { card, language: 'fr' }));
  const text = visibleText(html);
  assert.match(text, /Carte de presse/);
  assert.match(text, /Depuis le 15 novembre 2026 · 5 papiers classés/);
  for (const name of ['Au comptoir', 'Le fil', 'Le titre', "L'intox express", 'La photo', 'Le micro']) assert.ok(text.includes(name), name);
  assert.match(text, /Le titre 2 classés/);
  assert.match(text, /La photo pas encore/);
  assert.match(html, /href="\/revue\/une"/);
  assert.ok(!/point|streak|série/i.test(text));
  assert.match(visibleText(render(h(RvCarteDePresseCard, { card, language: 'de' }))), /Seit 15\. November 2026/);
});

test('every string in fr, en and de', () => {
  const keys = (language) => Object.keys(copyMod.rdvCopy(language)).sort();
  assert.deepEqual(keys('fr'), keys('en'));
  assert.deepEqual(keys('de'), keys('en'));
  for (const language of ['fr', 'en', 'de']) for (const [key, value] of Object.entries(copyMod.rdvCopy(language))) assert.ok(value && !/!/.test(value), `${language}.${key}`);
});

test('Home: the une chip only on a due Sunday, never on the Papier day, after the Correcteur', () => {
  const une = rdv.parseUne(P.une);
  assert.equal(une.dueToday, true);
  const chip = uneHome.uneHomeChip(une);
  assert.equal(chip.href, '/revue/une');
  assert.equal(uneHome.uneHomeChip({ ...une, dueToday: false }), null);
  assert.equal(uneHome.uneHomeChip(null), null);
  const row = [{ id: 'courrier' }, { id: 'correcteur' }, { id: 'due' }];
  assert.deepEqual(uneHome.withUneChip(row, chip).map((c) => c.id), ['courrier', 'correcteur', 'une', 'due']);
  assert.deepEqual(uneHome.withUneChip(row, chip, true).map((c) => c.id), ['courrier', 'correcteur', 'due']);
});

// ---------------------------------------------------------------------------
// 4 · the dev mock
// ---------------------------------------------------------------------------

test('the mock plays a round from the session\'s own close, and answers 404 while off', async () => {
  const closed = {
    mode: 'titre',
    closing: { kept: { words: [{ fr: 'la fête', gloss: 'party' }, { fr: 'le bruit', gloss: 'noise' }] } },
    plan: { vocabulary: [{ fr: 'les rues', gloss: 'streets' }] },
    dossier: { summary_fr: 'La fête existe depuis 1982. Il y a du bruit.' },
  };
  const inner = { get: async () => closed, post: async () => ({}) };
  const client = rdv.createRdvClient(mockRdv.withRdvMock(inner));
  const open = (await client.troisMots('s1')).round;
  assert.deepEqual(open.words.map((w) => w.fr), ['la fête', 'le bruit', 'les rues']);
  assert.equal(open.match.solution, null);
  const wrong = { a: '1', b: '2', c: '3' };
  const after = (await client.troisMotsAct('s1', { act: 'match', pairs: wrong })).round;
  assert.equal(after.match.tries, 1);
  assert.equal((await client.souvenir('s1')).speakerFr, 'Romy');
  const off = rdv.createRdvClient(mockRdv.withRdvMock(inner, { enabled: false }));
  assert.equal(await off.troisMots('s1'), null);
  assert.equal(await off.une(), null);
});

// ---------------------------------------------------------------------------
// 1 · daily: Home's chip says the day, never «semaine » with no number
// ---------------------------------------------------------------------------

test('REVUE_CADENCE=daily: the Papier chip names the day; weekly is as before', () => {
  const { revueHomeChip } = require('../revue-home.ts');
  const offer = (iso, range) => ({
    enabled: true,
    offer: { week: { iso, label: 'Semaine 47', range }, recommended: { dossierId: 'x' }, alternatives: [{ dossierId: 'y' }], filed: null, resume: null },
  });
  for (const language of ['fr', 'en', 'de']) {
    const daily = revueHomeChip(offer('2026-11-20', 'le 20 nov.'), language);
    assert.equal(daily.ariaLabel, 'Le Papier de Romy, le 20 nov.');
    assert.ok(!/semaine\s*$|week\s*$|Woche\s*$/.test(daily.ariaLabel));
    const filed = revueHomeChip({ ...offer('2026-11-20', 'le 20 nov.'), offer: { ...offer('2026-11-20', 'le 20 nov.').offer, filed: { sessionId: 's' } } }, language);
    assert.match(filed.ariaLabel, /today|aujourd'hui|heute/);
  }
  assert.equal(revueHomeChip(offer('2026-W47', 'du 16 au 22 nov.'), 'fr').ariaLabel, 'Le Papier de Romy, semaine 47');
});

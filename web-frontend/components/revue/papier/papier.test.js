// node --test components/revue/papier/papier.test.js
//
// «Papier · la belle édition» (2026-11-21) · the paper objects shared by the four assignments:
//
//   1. the edition: the dateline's parts, the edition number from the week, the folio;
//   2. the seeded marks: a stamp's or a cutting's tilt (stable, never flat, within bounds),
//      the grease-pencil loop and the wavy rule (stable per seed), the drop cap, the byline;
//   3. the copy: every chrome language has every key; what the paper prints stays French;
//   4. the components: the masthead, the folio, the stamp (a word for screen readers), the
//      front page (masthead, dateline, kicker, headline, the signed piece, the Lexique);
//   5. in the players: no stamp, no loop before the loop says so; the strips carry their
//      slug and join once in order; the head keeps its progress bar;
//   6. the stylesheet: tokens only (no colour literal), every movement ≤ 300 ms and none
//      under reduced motion, the taps' 44 px floor kept.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const { h, render, visibleText, fixture } = require('../revue-test-setup');

const model = require('./papier-model.ts');
const { PAPIER_COPY, PAPIER_FR, papierCopy } = require('./papier-copy.ts');
const print = require('./PapierPrint.tsx');
const types = require('../../../lib/revue-types.ts');
const { RvRubrique } = require('../rubriques/RvRubrique.tsx');
const { RvFil } = require('../fil/RvFil.tsx');

const CSS = fs.readFileSync(path.join(__dirname, '..', '..', '..', 'styles', 'revue-papier.css'), 'utf8');

// ---------------------------------------------------------------------------
// 1. The edition
// ---------------------------------------------------------------------------

test('the edition: number from the week, the day in French, the dateline in order', () => {
  assert.equal(model.editionNumber('2026-W47'), '47');
  assert.equal(model.editionNumber('2026-W05'), '5');
  assert.equal(model.editionNumber('nonsense'), '');
  assert.equal(model.dayFr('2026-11-21'), 'samedi 21 novembre');
  assert.equal(model.dayFr('2026-11-20'), 'vendredi 20 novembre');
  assert.equal(model.dayFr(''), '');
  assert.equal(model.dayFr('not a date'), '');
  assert.deepEqual(model.datelineParts({ dateIso: '2026-11-20', weekIso: '2026-W47' }), ['Paris', 'vendredi 20 novembre', 'Nº 47']);
  // What the payload lacks is left out, never invented.
  assert.deepEqual(model.datelineParts({}), ['Paris']);
  assert.deepEqual(model.editionOf({ startedAt: '2026-11-19T08:00:00Z', closedAt: null, week: { iso: '2026-W47' } }), { dateIso: '2026-11-19T08:00:00Z', weekIso: '2026-W47' });
  assert.equal(model.editionOf({ startedAt: 'a', closedAt: 'b', week: null }).dateIso, 'b', 'a filed paper carries the day it was filed');
});

test('the folio: the screen as a page number, the last page once closed', () => {
  const steps = ['read', 'order', 'words', 'tell', 'page'];
  assert.deepEqual(model.folio(steps, 'read', false), { n: 1, total: 5, fill: 0.2 });
  assert.deepEqual(model.folio(steps, 'words', false), { n: 3, total: 5, fill: 0.6 });
  assert.deepEqual(model.folio(steps, 'page', true), { n: 5, total: 5, fill: 1 });
  assert.equal(model.folio(steps, 'unknown', false).n, 1);
});

// ---------------------------------------------------------------------------
// 2. Seeded marks
// ---------------------------------------------------------------------------

test('a stamp lands the same way every time, tilted between −4° and 4°, never flat', () => {
  const seen = new Set();
  for (let index = 0; index < 200; index += 1) {
    const angle = model.tilt(`session:${index}`);
    assert.ok(Math.abs(angle) <= 4 && Math.abs(angle) >= 1, `${angle}`);
    assert.equal(model.tilt(`session:${index}`), angle, 'stable');
    seen.add(angle);
  }
  assert.ok(seen.size > 20, 'they vary');
  assert.ok(Math.abs(model.tilt('x', 0.8)) <= 1, 'a cutting is barely off true');
});

test('the grease-pencil loop and the wavy rule are drawn by hand, the same for the same seed', () => {
  const loop = model.pencilLoop('s1:b');
  assert.match(loop, /^M[\d.]+ [\d.]+ L/);
  // It hugs the block: no point inside the text's own box (x 5…95, y 6…34 of the 100 × 40 frame).
  for (const [, x, y] of loop.matchAll(/([\d.]+) ([\d.]+)/g)) assert.ok(Number(x) < 8 || Number(x) > 92 || Number(y) < 3 || Number(y) > 37, `${x} ${y}`);
  assert.equal(model.pencilLoop('s1:b'), loop);
  assert.notEqual(model.pencilLoop('s1:c'), loop);
  const wave = model.wavePath('content', 7);
  assert.equal(wave.width % 8, 0);
  assert.ok(wave.width >= 24);
  assert.match(wave.d, /^M0 3( Q[\d.]+ [\d.]+ [\d.]+ 3)+$/);
  assert.equal(model.wavePath('content', 7).d, wave.d);
});

test('the drop cap takes the first letter; the byline says how the piece reached print', () => {
  assert.deepEqual(model.dropCap('Le 21 juin, des musiciens'), { cap: 'L', rest: 'e 21 juin, des musiciens' });
  assert.deepEqual(model.dropCap('Élèves et parents'), { cap: 'É', rest: 'lèves et parents' });
  assert.equal(model.dropCap('  À partir de 2027'), null, 'a one-letter word would strand a space');
  assert.equal(model.dropCap("D'abord, le bac"), null, 'an apostrophe never strands beside the cap');
  assert.equal(model.dropCap('« Oui »'), null, 'a quote keeps its guillemet');
  assert.equal(model.dropCap('2027 : le bac'), null);
  assert.equal(model.dropCap(''), null);
  assert.equal(model.bylineFr('clean'), 'Par toi · relu par Romy');
  assert.equal(model.bylineFr('fixed'), 'Par toi · corrigé par toi');
  assert.equal(model.bylineFr('corrected'), 'Par toi · corrigé par Romy');
  assert.equal(model.bylineFr('as_written'), 'Par toi');
  assert.equal(model.bylineFr('clean', true), 'Par toi', 'tiles: Romy did not read them');
});

test('the margin note hangs from the middle of its word, inside the proof', () => {
  assert.equal(model.hairlineX(40, 20, 300), 50);
  assert.equal(model.hairlineX(-30, 10, 300), 14);
  assert.equal(model.hairlineX(290, 40, 300), 286);
  assert.deepEqual(model.flipDeltas({ a: 0, b: 60, c: 120 }, { a: 60, b: 0, c: 120 }), { a: -60, b: 60 });
});

test('the page prints the story’s own picture with its credit, never a season plate', () => {
  const stage = {
    plateUrl: '/media/p.png',
    plateKind: 'story',
    pictures: [{ url: '/media/p.png', captionFr: null, creditFr: 'Illustration · Le Papier' }],
  };
  assert.deepEqual(model.pagePicture(stage, 'Une salle d’examen', 'X'), { url: '/media/p.png', captionFr: 'Une salle d’examen', creditFr: 'Illustration · Le Papier' });
  // A season plate is the place's: the story's own first picture leads instead, else nothing.
  assert.equal(model.pagePicture({ ...stage, plateKind: 'season', pictures: [{ url: '/m/photo.jpg', captionFr: 'Le kiosque', creditFr: 'Photo · A · CC BY' }] }, 'x', 'X').url, '/m/photo.jpg');
  assert.equal(model.pagePicture({ ...stage, plateKind: 'season', pictures: [] }, 'x', 'X'), null);
  assert.equal(model.pagePicture({ ...stage, pictures: [] }, null, 'Illustration · Le Papier').creditFr, 'Illustration · Le Papier');
});

// ---------------------------------------------------------------------------
// 3. The copy
// ---------------------------------------------------------------------------

test('the copy: every chrome language has every key; the paper prints French', () => {
  const keys = Object.keys(PAPIER_COPY.fr).sort();
  for (const language of ['de', 'en']) assert.deepEqual(Object.keys(PAPIER_COPY[language]).sort(), keys, language);
  for (const [language, table] of Object.entries(PAPIER_COPY)) {
    for (const [key, value] of Object.entries(table)) assert.ok(value && value.trim(), `${language}.${key}`);
  }
  assert.equal(papierCopy('de').refused, 'Abgelehnt');
  assert.equal(papierCopy('xx'), PAPIER_COPY.en);
  assert.equal(PAPIER_FR.masthead, 'Le Papier');
  assert.equal(PAPIER_FR.stamp_intox, 'Intox');
});

// ---------------------------------------------------------------------------
// 4. The components
// ---------------------------------------------------------------------------

test('the dateline and the opening: the masthead at display size, the section head under it', () => {
  const html = render(h(print.PpSection, { edition: { dateIso: '2026-11-20', weekIso: '2026-W47' }, section: 'Le fil', step: 'Lire', opening: true }));
  assert.match(html, /class="pp-opening__mast" lang="fr">Le Papier</);
  assert.match(visibleText(html), /Paris · vendredi 20 novembre · Nº 47/);
  assert.match(visibleText(html), /Le fil Lire$/);
  const later = render(h(print.PpSection, { edition: {}, section: 'Le fil', step: 'Raconter' }));
  assert.doesNotMatch(later, /pp-opening/, 'the masthead only opens the paper');
});

test('the stamp: the printed word is hidden from screen readers, its label is said instead', () => {
  const html = render(h(print.PpStamp, { kind: 'intox', seed: 's:a', label: 'Stamp: fake news' }));
  assert.match(html, /role="img" aria-label="Stamp: fake news"/);
  assert.match(html, /data-ink="intox"/);
  assert.match(html, /--pp-tilt:-?[\d.]+deg/);
  assert.match(html, /<span class="pp-stamp__ink" lang="fr" aria-hidden="true">Intox<\/span>/);
  assert.match(render(h(print.PpStamp, { kind: 'vrai', seed: 's:a', label: 'x', still: true })), /data-still=""/);
});

test('the front page: masthead, dateline, kicker, headline, the signed piece, the Lexique', () => {
  const html = render(
    h(
      print.PpFrontPage,
      { edition: { dateIso: '2026-11-20', weekIso: '2026-W47' }, kicker: 'Le fil de Romy', headline: 'Le bac', deck: 'Une salle d’examen' },
      h(print.PpMine, { textFr: 'Tout d’abord, le bac est créé en 1808.', byline: 'Par toi · relu par Romy', lead: true }),
      h(print.PpFrontCols, { words: ['le bac', 'la session'], wordsLabel: 'Les mots gardés' }, h('p', null, 'Le fil')),
    ),
  );
  // It opens the screen at its top (Romy's thanks follow it): no anchor scrolls it under the head.
  assert.match(html, /^<article class="ct-clip" data-pp-front="">/);
  const text = visibleText(html);
  assert.ok(text.startsWith('Le Papier Paris · vendredi 20 novembre · Nº 47 Le fil de Romy Le bac Une salle d’examen'), text);
  assert.match(html, /<span class="pp-cap" aria-hidden="true">T<\/span><span class="av2-sr">T<\/span>out d’abord/, 'a drop cap, read whole');
  assert.match(html, /class="pp-byline" lang="fr">Par toi · relu par Romy</);
  assert.match(html, /<aside class="pp-lexique" aria-label="Les mots gardés">/);
  assert.match(html, /data-lexique=""/, 'a column rule between the article and the Lexique');
  assert.ok(html.indexOf('pp-byline') > html.indexOf('pp-front__mine-fr'), 'the byline under the piece');
});

// ---------------------------------------------------------------------------
// 5. In the players
// ---------------------------------------------------------------------------

const SESSIONS = fixture('rubriques-sessions');
const FIL = fixture('fil-sessions');
const screen = (sessions, name, Player) => render(h(Player, { client: {}, session: types.parseSessionView(JSON.parse(JSON.stringify(sessions[name]))), onExit: () => {} }));

test('the head: the masthead, the folio and the progress bar the players had', () => {
  const html = screen(SESSIONS, 'titre_a1_three_wrong', RvRubrique);
  assert.match(html, /<p class="pp-head__mast" lang="fr" aria-hidden="true">Le Papier<\/p>/);
  assert.match(html, /class="pp-folio" aria-hidden="true"><span class="pp-folio__n">2<\/span>/);
  assert.match(html, /role="progressbar"[^>]*aria-valuenow="2"/);
  assert.match(html, /<header class="pp-section"><div class="pp-section__row"><p class="pp-section__line" lang="fr"><span class="pp-section__name">Le titre<\/span><span class="pp-section__step">Trois titres<\/span><\/p><button type="button" class="pp-link pp-translate-all" aria-pressed="false">Translate all<\/button>/);
  // One quiet translation for the set: no «Translate» button on any of the three proofs.
  const proofs = html.slice(html.indexOf('rb-heads'), html.indexOf('</ol>', html.indexOf('rb-heads')));
  // (a refused proof's cutting, «Fait», keeps its own quiet link)
  assert.equal((proofs.match(/class="rv-line__tools"/g) || []).length, (proofs.match(/class="rv-claim"/g) || []).length);
});

test('no stamp before the answer, no loop before a pick: the marks wait for the loop', () => {
  for (const name of Object.keys(SESSIONS)) {
    const raw = SESSIONS[name];
    const html = screen(SESSIONS, name, RvRubrique);
    const view = types.parseSessionView(JSON.parse(JSON.stringify(raw)));
    if (view.intox?.round && view.intox.step === 'round') {
      const answered = view.intox.round.cards.filter((card) => card.answer).length;
      const stamps = (html.match(/class="pp-stamp"/g) || []).length;
      assert.ok(stamps <= answered, `${name}: ${stamps} stamps for ${answered} answers`);
    }
    if (view.titre?.three && view.titre.step === 'three' && !view.titre.three.resolved) {
      assert.doesNotMatch(html, /class="pp-loop"/, `${name}: nothing circled before the learner picks`);
    }
  }
});

test('the wire: each strip carries its slug; the strips join once in order', () => {
  const names = Object.keys(FIL).filter((name) => FIL[name]?.fil?.step === 'order' || /order/.test(name));
  assert.ok(names.length > 0);
  for (const name of names) {
    const html = screen(FIL, name, RvFil);
    if (!/class="fl-strips"/.test(html)) continue;
    const view = types.parseSessionView(JSON.parse(JSON.stringify(FIL[name])));
    if (!view.fil?.order || view.fil.step !== 'order') continue;
    assert.match(html, /<p class="pp-slug" lang="fr" aria-hidden="true">Dépêche · <b>[A-D]<\/b><\/p>/, name);
    assert.equal(/<ol class="fl-strips"[^>]*data-joined=""/.test(html), Boolean(view.fil.order.resolved), name);
  }
});

// ---------------------------------------------------------------------------
// 6. The stylesheet
// ---------------------------------------------------------------------------

test('the stylesheet: tokens only, every movement ≤ 300 ms and none under reduced motion', () => {
  const body = CSS.replace(/\/\*[\s\S]*?\*\//g, '');
  // No colour literal: every colour is an --av2 token (or derived from one); #000/#0000 only in masks.
  const literals = (body.match(/#[0-9a-fA-F]{3,8}\b/g) || []).filter((hex) => hex !== '#000' && hex !== '#0000');
  assert.deepEqual(literals, []);
  for (const line of body.split('\n')) {
    if (/#000\b|#0000\b/.test(line)) assert.match(line, /mask|--pp-(holes|tear|flat)/, line);
  }
  assert.doesNotMatch(body, /rgb\(|hsl\(|font-family:\s*['"]/);
  for (const [, value, unit] of body.matchAll(/(?:animation|transition)[^;]*?(\d*\.?\d+)(m?s)\b/g)) {
    const ms = unit === 's' ? Number(value) * 1000 : Number(value);
    assert.ok(ms <= 300, `${value}${unit}`);
  }
  const reduced = body.slice(body.lastIndexOf('@media (prefers-reduced-motion: reduce)'));
  for (const selector of ['.pp-loop path', '.pp-stamp', '.pp-byline', '.ct-clip[data-pp-front]', '.pp-del path']) assert.ok(reduced.includes(selector), selector);
  // the floors kept: the trap's words and the players' small tools
  assert.match(body, /\.rb-trap__w \{[^}]*min-width: var\(--av2-tap\);[^}]*min-height: 52px;/);
  assert.match(body, /\.ct-player \.rv-chip::after \{ inset: -8px -6px; \}/);
  assert.match(body, /\.pp-link::after \{ content: ''; position: absolute; inset: -14px -8px; \}/);
  // long lines are never tracked capitals: the page's sources, the credits, the cutting's footer
  assert.match(body, /\.ct-clip\[data-pp-front\] \.pp-front__sources \{[^}]*text-transform: none; letter-spacing: 0;/);
  assert.match(body, /\.pp-figure__credit, \.av2 \.rv-gallery__credit, \.av2 \.ct-pic__credit, \.av2 \.rb-quote__by, \.av2 \.pp-cutting__src, \.av2 \.pp-front__sources \{\s*text-transform: none;/);
  // the head's air: anchors and the browser's own scrolling stop below it
  assert.match(body, /html:has\(\.av2\.rv-page\) \{ scroll-padding-top: 96px;/);
  assert.equal(require('../comptoir/scroll.ts').HEAD_AIR, 12);
  // the stamp is the event: clearly turned
  for (let index = 0; index < 100; index += 1) assert.ok(Math.abs(model.stampTilt(`k${index}`)) >= 2.5 && Math.abs(model.stampTilt(`k${index}`)) <= 4);
});

test('round 3: how a caption or an interview reached print, agreed in French; never «par toi» twice', () => {
  const m = require('./papier-model.ts');
  assert.equal(m.legendeBylineFr('clean'), 'Légende · par toi, relue par Romy');
  assert.equal(m.legendeBylineFr('fixed'), 'Légende · par toi, corrigée');
  assert.equal(m.legendeBylineFr('corrected'), 'Légende · par toi, corrigée par Romy');
  assert.equal(m.legendeBylineFr('clean', true), 'Légende · par toi', 'tiles: nothing to proofread');
  assert.equal(m.legendeBylineFr('as_written'), 'Légende · par toi');
  assert.equal(m.proofNoteFr('clean', 's'), 'relus par Romy');
  assert.equal(m.proofNoteFr(null), '');
});

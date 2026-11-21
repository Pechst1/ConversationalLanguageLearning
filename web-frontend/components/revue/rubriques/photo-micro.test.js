// node --test components/revue/rubriques/photo-micro.test.js
//
// «La photo» and «Le micro» (WIRE §12, 2026-11-21), the client:
//
//   1. the model: the A1 caption as the server builds it, a refusal said in the right table
//      (a reason in the mother tongue at every level), what changed after an act;
//   2. the wire: real views (fixtures/photo-micro-sessions.json, dumped from the backend's
//      loops) parsed; nothing says which picture goes with the headline, which caption is
//      wrong or what the witness will answer before it is earned; the slips never show during
//      the interview; acts in snake_case through the one route;
//   3. the player rendered from those views at A1 (de), A2 (de) and B1 (en, French chrome):
//      the chooser's names, explanations in the mother tongue, at most two foot buttons, the
//      credit printed under every picture, «La page» with its sources;
//   4. the dev mock (`photo: true`, `micro: true`) plays both through.

const assert = require('node:assert/strict');
const { test } = require('node:test');

const setup = require('../revue-test-setup');

const { h, render, fixture } = setup;
const visibleText = (html) => setup.visibleText(html.replace(/<style[\s\S]*?<\/style>/g, ' '));

const types = require('../../../lib/revue-types.ts');
const rtypes = require('../../../lib/revue-rubriques-types.ts');
const { createMockRevueClient } = require('../../../lib/revue-mock.ts');
const model = require('./photo-micro-model.ts');
const { photoMicroCopy, PHOTO_STEP_LABELS_FR, MICRO_STEP_LABELS_FR } = require('./photo-micro-copy.ts');
const { RvRubrique } = require('../index.ts');

const SESSIONS = fixture('photo-micro-sessions');
const session = (name) => types.parseSessionView(SESSIONS[name]);
const screen = (name) => render(h(RvRubrique, { client: {}, session: session(name), onExit: () => {}, onReleve: () => {} }));

function footButtons(html) {
  const at = html.lastIndexOf('class="rv-foot');
  if (at < 0) return 0;
  return (html.slice(at).match(/<button/g) || []).length;
}

// ---------------------------------------------------------------------------
// 1. The model
// ---------------------------------------------------------------------------

test('the A1 caption builds as the server builds it; a reason is said in the mother tongue', () => {
  assert.equal(model.a1Caption('photo', 'une guitare', 'La fête est gratuite.'), 'Sur la photo, on voit une guitare. La fête est gratuite.');
  assert.equal(model.a1Caption('illustration', 'le port', 'Les bateaux partent'), 'Sur l’image, on voit le port. Les bateaux partent.');
  assert.equal(model.a1Caption('photo', null, 'x'), '');
  const fr = photoMicroCopy('fr');
  const de = photoMicroCopy('de');
  assert.match(model.pmErrorText({ code: 'name_what_you_see', key: null, count: null }, fr, de), /Bild/, 'a reason: mother tongue');
  assert.match(model.pmErrorText({ code: 'pick_three', key: null, count: 3 }, fr, de), /Choisis/, 'an instruction: the chrome');
  assert.match(model.pmErrorText({ code: 'keep_questions', key: null, count: 3 }, fr, de), /3 Fragen/);
  for (const language of ['fr', 'en', 'de']) {
    const copy = photoMicroCopy(language);
    for (const key of Object.keys(fr)) assert.ok(copy[key], `${language}: ${key}`);
    for (const code of Object.keys(fr.errors)) assert.ok(copy.errors[code], `${language}: errors.${code}`);
  }
  assert.deepEqual(Object.keys(PHOTO_STEP_LABELS_FR), ['read', 'planche', 'legende', 'build', 'page']);
  assert.deepEqual(Object.keys(MICRO_STEP_LABELS_FR), ['read', 'prepare', 'interview', 'notes', 'review', 'page']);
});

test('what changed after an act is seen (the player brings it into view)', () => {
  const before = model.photoMicroProgress(session('photo_a1_de_planche'));
  assert.notEqual(before, model.photoMicroProgress(session('photo_a1_de_planche_miss')));
  assert.notEqual(model.photoMicroProgress(session('micro_a2_de_interview')), model.photoMicroProgress(session('micro_a2_de_shrug')));
});

// ---------------------------------------------------------------------------
// 2. The wire
// ---------------------------------------------------------------------------

test('a photo session parses, and nothing says which picture or caption it is before it is earned', () => {
  const s = session('photo_a1_de_planche');
  assert.equal(s.mode, 'photo');
  assert.equal(s.micro, null);
  assert.deepEqual(s.photo.steps, ['read', 'planche', 'legende', 'build', 'page']);
  assert.equal(s.photo.planche.pictures.length, 2);
  assert.ok(s.photo.planche.pictures.every((p) => p.url && p.creditFr.startsWith('Photo · ')));
  assert.equal(s.photo.planche.solution, null);
  assert.equal(s.photo.planche.seen, null);
  assert.ok(!/"lead":"photo|seen_not|basis_fr/.test(JSON.stringify(SESSIONS.photo_a1_de_planche.photo)), 'the raw view says nothing either');
  const miss = session('photo_a1_de_planche_miss').photo.planche;
  assert.equal(miss.solution, null);
  assert.deepEqual(miss.shows.map((t) => t.fr), ['Paris']);
  const seen = session('photo_a1_de_seen_miss').photo.planche.seen;
  assert.equal(seen.elsewhere.length, 1);
  assert.equal(seen.missing, 1);
  assert.deepEqual(seen.solution, [], 'never the answer after one miss');
  const legende = session('photo_a1_de_legende').photo.legende;
  assert.ok(legende.captions.every((c) => c.role === null && c.why === null));
  assert.equal(legende.solution, null);
  const picked = session('photo_a1_de_legende_miss').photo.legende;
  assert.deepEqual(picked.captions.filter((c) => c.role).map((c) => c.role), ['right']);
  const page = session('photo_a1_de_page');
  assert.equal(page.closing.photoPage.captionFr, 'Sur la photo, on voit une guitare. La fête est gratuite.');
  assert.ok(page.closing.photoPage.picture.creditFr);
  assert.equal(page.artifact.kind, 'photo');
});

test('a micro session parses; no answer before it is asked, no slip during the interview', () => {
  const s = session('micro_a2_de_prepare');
  assert.equal(s.mode, 'micro');
  assert.deepEqual(s.micro.steps, ['read', 'prepare', 'interview', 'notes', 'review', 'page']);
  assert.equal(s.micro.prepare.holes.length, 6);
  const raw = JSON.stringify(SESSIONS.micro_a2_de_prepare.micro);
  assert.ok(!/mon chou|value_fr|keywords|answer"/.test(raw), 'Romy’s notes only');
  const shrug = session('micro_a2_de_shrug').micro.interview;
  assert.equal(shrug.turns[0].kind, 'shrug');
  assert.equal(shrug.turns[0].spent, false);
  assert.equal(shrug.free, false);
  const notes = session('micro_a2_de_notes');
  assert.ok(!/inversion|question_word|slips/.test(JSON.stringify(SESSIONS.micro_a2_de_notes)), 'the slips wait for «Relis»');
  assert.ok(notes.micro.notes.items.every((item) => item.valueFr === null && item.options.length >= 2));
  const review = session('micro_a2_de_review').micro.review;
  assert.deepEqual(review.hints.map((hint) => hint.code), ['inversion', 'question_word']);
  const page = session('micro_a2_de_page').closing.microPage;
  assert.equal(page.lines.length, 3);
  assert.ok(page.lines.every((line) => line.sourceName && line.answerFr && line.questionFr.endsWith('?')));
  assert.equal(page.witness.id, 'lila_bonnet');
});

test('acts go out in snake_case through the one route', () => {
  assert.deepEqual(rtypes.rubriqueBodyWire({ act: 'prepare', keys: ['a', 'c', 'e'] }), { act: 'prepare', keys: ['a', 'c', 'e'] });
  assert.deepEqual(rtypes.rubriqueBodyWire({ act: 'build', key: 'b', parts: [0, 1] }), { act: 'build', key: 'b', parts: [0, 1] });
  assert.deepEqual(rtypes.rubriqueBodyWire({ act: 'ask', text: 'Combien ?', mode: 'text' }), { act: 'ask', text: 'Combien ?', mode: 'text' });
  assert.ok(types.RV_MADE_KINDS.includes('photo') && types.RV_MADE_KINDS.includes('micro'));
  assert.equal(types.parseRevueError(409, { detail: { code: 'revue_micro_out_of_order' } }).code, 'revue_micro_out_of_order');
});

// ---------------------------------------------------------------------------
// 3. The player
// ---------------------------------------------------------------------------

test('La planche (A1, de): German chrome, every picture credited, a miss explained in German, no answer', () => {
  const html = screen('photo_a1_de_planche');
  const text = visibleText(html);
  assert.match(text, /Welches Bild passt zu dieser Schlagzeile\?/);
  assert.equal((html.match(/rv-picture__credit/g) || []).length, 2, 'the credit under each picture');
  assert.ok(footButtons(html) <= 2);
  const miss = visibleText(screen('photo_a1_de_planche_miss'));
  assert.match(miss, /Nicht dieses\./);
  assert.match(miss, /Auf diesem Bild sieht man: Paris\./);
  assert.doesNotMatch(miss, /Hier ist das Bild/);
  const seen = visibleText(screen('photo_a1_de_seen_miss'));
  assert.match(seen, /Das ist auf einem anderen Bild: « Paris »\./);
  assert.match(seen, /Es fehlen noch 1\./);
});

test('La légende and À toi (A1, de): the picked caption explained in German, the tiles, then La page', () => {
  const miss = visibleText(screen('photo_a1_de_legende_miss'));
  assert.match(miss, /Nicht diese: Diese Bildunterschrift stimmt\./);
  const build = screen('photo_a1_de_build');
  assert.match(visibleText(build), /Wähle ein Bild für deine Bildunterschrift\./);
  assert.ok(footButtons(build) <= 2);
  const page = visibleText(screen('photo_a1_de_page'));
  assert.match(page, /La photo de Romy/);
  assert.match(page, /Sur la photo, on voit une guitare\. La fête est gratuite\./);
  assert.match(page, /Photo · .* · Wikimedia Commons/);
  assert.match(page, /d’après|d'après/);
});

test('B1 (en): French chrome, Romy’s marks, the reasons in English', () => {
  const html = screen('photo_b1_en_marked');
  const text = visibleText(html);
  assert.match(text, /À toi|Choisis|Ta légende|Corrige/);
  assert.ok(footButtons(html) <= 2);
  const marked = visibleText(screen('micro_b1_en_marked'));
  assert.match(marked, /tres/);
  assert.doesNotMatch(marked, /très attendue/, 'never the corrected form before the fix');
});

test('Le micro (A2, de): the witness answers in her bubble, a shrug explained in German, the notes, the hints', () => {
  const prepare = visibleText(screen('micro_a2_de_prepare'));
  assert.match(prepare, /Romy hat Lücken in ihren Notizen/);
  assert.match(prepare, /Les notes de Romy/);
  const shrug = screen('micro_a2_de_shrug');
  assert.match(visibleText(shrug), /Keine Antwort: Diese Frage zählt nicht/);
  assert.match(shrug, /data-char="lila_bonnet"/);
  assert.ok(footButtons(shrug) <= 2);
  const review = visibleText(screen('micro_a2_de_review'));
  assert.match(review, /Frage 1: Schriftlich stellt man nach einem Fragewort das Subjekt um/);
  assert.doesNotMatch(review, /Pourquoi est-elle/, 'the rule, never the corrected question');
  const page = visibleText(screen('micro_a2_de_page'));
  assert.match(page, /L’interview · Lila/);
  assert.match(page, /Q\. .*\?/);
  assert.match(page, /d’après Ministère de la Culture/);
  const tiles = screen('micro_a1_de_interview');
  assert.match(visibleText(tiles), /Wähle deine Frage\./);
});

// ---------------------------------------------------------------------------
// 4. The dev mock
// ---------------------------------------------------------------------------

test('the dev mock plays «La photo» (`photo: true`) and «Le micro» (`micro: true`) through', async () => {
  const photo = createMockRevueClient({ persist: false, photo: true, band: 'A1', language: 'de' });
  let s = await photo.start();
  assert.equal(s.mode, 'photo');
  const act = async (client, body) => {
    const result = await client.rubrique(s.id, body);
    s = result.session;
    return result.error;
  };
  await act(photo, { act: 'open' });
  await act(photo, { act: 'choose', key: 'a' });
  assert.equal(s.photo.planche.solution, null);
  await act(photo, { act: 'choose', key: 'b' });
  const own = s.photo.planche.seen.words.filter((w) => w.text.fr !== 'Paris').map((w) => w.index);
  await act(photo, { act: 'seen', words: own });
  assert.equal(s.photo.step, 'legende');
  const wrong = s.photo.legende.captions.find((c) => /14 juillet/.test(c.text.fr)).key;
  await act(photo, { act: 'caption', key: wrong });
  await act(photo, { act: 'caption_fix', value: 'le 21 juin' });
  assert.equal(s.photo.step, 'build');
  await act(photo, { act: 'build', key: 'b', parts: [0, 0] });
  const closed = await photo.close(s.id);
  assert.equal(closed.closing.photoPage.captionFr, 'Sur la photo, on voit une guitare. La fête est gratuite.');

  const micro = createMockRevueClient({ persist: false, micro: true, band: 'A2', language: 'de' });
  s = await micro.start();
  assert.equal(s.mode, 'micro');
  await act(micro, { act: 'open' });
  assert.equal((await act(micro, { act: 'prepare', keys: ['a'] })).code, 'pick_three');
  await act(micro, { act: 'prepare', keys: ['a', 'b', 'd'] });
  await act(micro, { act: 'ask', text: 'Qui organise la fête ?' });
  assert.equal(s.micro.interview.turns[0].kind, 'shrug');
  assert.equal(s.micro.interview.spent, 0);
  await act(micro, { act: 'ask', text: 'Combien coûte la fête ?' });
  await act(micro, { act: 'ask', text: 'Quand est-ce que la première fête a eu lieu ?' });
  await act(micro, { act: 'ask', text: 'Quelles musiques est-ce qu’on peut écouter ?' });
  assert.equal(s.micro.step, 'notes');
  for (const item of s.micro.notes.items) {
    const value = { 'Combien ça coûte ?': 'gratuite', 'Quand, la première fête ?': 'le 21 juin 1982', 'Quelles musiques ?': 'toutes les musiques' }[item.hole.fr];
    await act(micro, { act: 'note', key: item.key, value });
  }
  assert.equal(s.micro.step, 'review');
  await act(micro, { act: 'review' });
  const done = await micro.close(s.id);
  assert.equal(done.closing.microPage.lines.length, 3);
  assert.ok(done.closing.microPage.lines.every((line) => line.sourceName));
});

test('the chooser names the assignment dealt (a fault the browser showed, 2026-11-20)', async () => {
  const client = createMockRevueClient({ persist: false, micro: true, band: 'A2', language: 'de' });
  const week = await client.week();
  assert.deepEqual(week.offer.recommended.assignment, { key: 'micro', nameFr: 'Le micro' });
  const { RvChooser } = require('../RvChooser.tsx');
  const { revueCopy } = require('../revue-copy.ts');
  const html = render(h(RvChooser, { recommended: week.offer.recommended, alternatives: week.offer.alternatives, week: week.offer.week, onPick: () => {}, onAsk: async () => ({}), copy: revueCopy("de") }));
  assert.match(visibleText(html), /Dein Auftrag · Le micro/);
  assert.equal(types.parseStoryCard({ dossier_id: 'x', title_fr: 'x' }).assignment, null, 'switch off: nothing named');
});

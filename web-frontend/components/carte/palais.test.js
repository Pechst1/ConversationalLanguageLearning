// node --test components/carte/palais.test.js
//
// WP-121 · Le Palais de mémoire and La Relecture, client side.
//
//   1. dots: a pin with due words carries the ink dot (and says so to a screen reader);
//      a cluster sums its pins; no number on the map;
//   2. the card: «2 mots t'attendent ici» first, «Réviser ici» the one red press,
//      «Relire» secondary; the Relecture row («Relire ta question» / «Relue le …»);
//   3. CarteReview: the plate behind, the speaker's line, a format posed from the
//      server's item (word bank tiles, the matching grid), and the done state with
//      «Retour à la carte»; the progress model finishes after the last item or when
//      nothing is left at the place;
//   4. CarteRelecture: the field before, the pair after (both sides, the flags
//      underlined with their word, Romy's line, no score);
//   5. the wire: due counts, relecture marks, review items, the pair; the client's URLs.

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { h, render, visibleText } = require('../revue/revue-test-setup');

const { carteCopy } = require('./carte-copy.ts');
const mock = require('./carte-mock.ts');
const { Carte, CartePinCard, CarteReview, CarteRelecture } = require('./index.ts');
const palais = require('./palais-model.ts');
const types = require('../../lib/carte-types.ts');
const { createCarteClient } = require('../../lib/carte-api.ts');

const FR = carteCopy('fr');
const noop = () => undefined;
const words = (html) => visibleText(html.replace(/<style[\s\S]*?<\/style>/g, ' '));
const DRAWINGS = { france: '<svg/>', idf: '<svg/>', paris: '<svg/>' };
const aligre = () => mock.CARTE_MOCK_DUE_VIEW.pins.find((p) => p.sessionId === 'mock-aligre');

// --- 1. dots -------------------------------------------------------------------------

test('a pin with due words wears the dot; a cluster sums; the map never prints the number', () => {
  const paris = render(h(Carte, { pins: mock.CARTE_MOCK_DUE_VIEW.pins, copy: FR, onRelire: noop, onReleve: noop, initialLevel: 'paris', drawings: DRAWINGS, mapPx: 358 }));
  const pin = /<button[^>]*class="carte-pin"[^>]*data-session="mock-aligre"[^>]*>[\s\S]*?<\/button>/.exec(paris)[0];
  assert.match(pin, /data-due=""/);
  assert.match(pin, /aria-label="[^"]*2 mots à revoir ici"/);
  assert.match(pin, /<i class="carte-due-dot" aria-hidden="true"><\/i>/);
  assert.equal((paris.match(/carte-due-dot/g) || []).length, 1);
  const france = render(h(Carte, { pins: mock.CARTE_MOCK_DUE_VIEW.pins, copy: FR, onRelire: noop, onReleve: noop, drawings: DRAWINGS, mapPx: 358 }));
  assert.match(france, /class="carte-cluster"[^>]*data-due=""/);
  assert.equal(palais.clusterDue({ members: mock.CARTE_MOCK_DUE_VIEW.pins.map((item) => ({ item })) }), 2);
  const none = render(h(Carte, { pins: mock.CARTE_MOCK_VIEW.pins, copy: FR, onRelire: noop, onReleve: noop, drawings: DRAWINGS, mapPx: 358 }));
  assert.doesNotMatch(none, /carte-due-dot/);
});

// --- 2. the card -------------------------------------------------------------------------

test('the card opens on the waiting words and «Réviser ici» is the one red press', () => {
  const html = render(h(CartePinCard, { pin: aligre(), copy: FR, onClose: noop, onRelire: noop, onReleve: noop, onReview: noop, onRelecture: noop }));
  const text = visibleText(html);
  assert.ok(text.indexOf('2 mots t’attendent ici') < text.indexOf('Ta question'), 'the due row comes first');
  assert.match(html, /data-tone="primary"[^>]*><span>Réviser ici<\/span>/);
  assert.match(html, /data-tone="secondary"[^>]*><span>Relire<\/span>/);
  assert.equal((html.match(/av2-btn--primary/g) || []).length, 1);
  // Without due words (or without a review surface) the card is WP-120's.
  const plain = render(h(CartePinCard, { pin: { ...aligre(), dueWords: 0 }, copy: FR, onClose: noop, onRelire: noop, onReleve: noop, onReview: noop }));
  assert.doesNotMatch(plain, /Réviser ici/);
  assert.match(plain, /data-tone="primary"[^>]*><span>Relire<\/span>/);
});

test('the Relecture row: «Relire ta question» when eligible, «Relue le …» after', () => {
  const pins = mock.CARTE_MOCK_DUE_VIEW.pins;
  const open = visibleText(render(h(CartePinCard, { pin: pins.find((p) => p.sessionId === 'mock-bourgogne'), copy: FR, onClose: noop, onRelire: noop, onReleve: noop, onRelecture: noop })));
  assert.match(open, /Relire ta question/);
  const read = visibleText(render(h(CartePinCard, { pin: pins.find((p) => p.sessionId === 'mock-canicules'), copy: FR, onClose: noop, onRelire: noop, onReleve: noop, onRelecture: noop })));
  assert.match(read, /Relue le 22 oct\./);
  const headline = palais.relectureAction({ relecture: { state: 'eligible', readAt: null }, questionFr: null });
  assert.deepEqual(headline, { kind: 'open', headline: true });
  assert.equal(palais.relectureAction({ relecture: null, questionFr: 'Q ?' }), null);
});

// --- 3. CarteReview ----------------------------------------------------------------------------

test('CarteReview poses a word bank on the plate with the line that carried the word', () => {
  const html = render(h(CarteReview, { review: mock.CARTE_MOCK_REVIEW, copy: FR, onGrade: async () => ({}), onBack: noop }));
  const text = visibleText(html);
  assert.match(html, /class="carte-review__plate"[\s\S]*?src="\/assets\/serial\/locations\/marche_canal.webp"/);
  assert.match(html, /data-format="word_bank"/);
  assert.match(html, /data-char="margaux_barman"/);
  assert.match(text, /Margaux Mon primeur dit que la récolte a été mauvaise, alors tout monte\./);
  assert.match(text, /Remets la phrase d’ici dans l’ordre\. Un mot est en trop\./);
  assert.match(text, /1 sur 2/);
  assert.equal((html.match(/class="av2-tile"/g) || []).length, 7);
  assert.match(html, /data-tone="primary"[^>]*disabled=""[^>]*><span>Vérifier<\/span>|disabled=""[^>]*data-tone="primary"/);
});

test('CarteReview poses four words as a matching grid', () => {
  const words = ['la récolte', 'un étal', 'le prix', 'augmenter'].map((word, i) => ({ ...mock.CARTE_MOCK_REVIEW.words[0], progressId: `p${i}`, word, gloss: `g${i}` }));
  const item = {
    id: 'm:p0,p1,p2,p3', taskType: 'match_pairs', progressIds: words.map((w) => w.progressId), promptFr: null, answerKey: null, audioUrl: null,
    options: [...words.map((w, i) => ({ id: `f${i}`, text_fr: w.word, side: 'fr' })), ...words.map((w, i) => ({ id: `n${i}`, text_fr: w.gloss, side: 'native' }))],
  };
  const html = render(h(CarteReview, { review: { ...mock.CARTE_MOCK_REVIEW, words, items: [item] }, copy: FR, onGrade: async () => ({}), onBack: noop }));
  assert.match(html, /data-format="match_pairs"/);
  assert.equal((html.match(/class="av2-match__card"/g) || []).length, 8);
  assert.match(visibleText(html), /Relie chaque mot à son sens\./);
});

test('the review finishes after the last item, or as soon as the place is clear', async () => {
  const review = mock.CARTE_MOCK_REVIEW;
  const grade = mock.mockGradeFor();
  let progress = palais.reviewStart(review);
  assert.deepEqual(progress, { index: 0, results: {}, remaining: null, done: false });
  progress = palais.reviewGraded(progress, await grade({ itemId: 'w:mock-p1', tileIds: ['t0', 't1', 't2', 't3', 't4', 't5'] }));
  assert.equal(palais.itemVerdict(progress, review.items[0]), 'correct');
  progress = palais.reviewNext(progress, review);
  assert.equal(progress.index, 1);
  assert.equal(progress.done, false);
  progress = palais.reviewGraded(progress, await grade({ itemId: 'w:mock-p2', tileIds: ['u1', 'u0'] }));
  assert.equal(palais.itemVerdict(progress, review.items[1]), 'wrong');
  progress = palais.reviewNext(progress, review);
  assert.equal(progress.done, true);
  assert.equal(palais.reviewNext({ index: 0, results: {}, remaining: 0, done: false }, review).done, true);

  const html = render(h(CarteReview, { review, copy: FR, onGrade: grade, onBack: noop, initialProgress: progress }));
  const text = visibleText(html);
  assert.match(text, /C’est revu\./);
  assert.match(html, /data-tone="primary"[^>]*><span>Retour à la carte<\/span>/);
  assert.match(html, /data-right="true"[^>]*><b>la récolte<\/b>/);
  assert.match(html, /data-right="false"[^>]*><b>un étal<\/b>/);
});

// --- 4. CarteRelecture --------------------------------------------------------------------------

test('CarteRelecture asks first, without the old answer', () => {
  const html = render(h(CarteRelecture, { offer: mock.CARTE_MOCK_RELECTURE_OFFER, copy: FR, onAnswer: async () => mock.CARTE_MOCK_RELECTURE_PAIR, onBack: noop }));
  const text = visibleText(html);
  assert.match(text, /Est-ce que la récolte sera bonne cette année \?/);
  assert.match(text, /Aujourd’hui, qu’est-ce que tu y réponds \?/);
  assert.match(html, /<textarea[^>]*lang="fr"/);
  assert.doesNotMatch(text, /la récolte bonne cette année \? /, 'the old answer is not shown before sending');
  assert.doesNotMatch(text, /Semaine 35/);
});

test('CarteRelecture renders the pair: both answers, the flags underlined with their word, Romy’s line', () => {
  const html = render(h(CarteRelecture, { offer: mock.CARTE_MOCK_RELECTURE_OFFER, pair: mock.CARTE_MOCK_RELECTURE_PAIR, copy: FR, onAnswer: async () => mock.CARTE_MOCK_RELECTURE_PAIR, onBack: noop }));
  const text = words(html);
  assert.match(html, /data-side="then"[\s\S]*Semaine 35[\s\S]*la récolte bonne cette année \?/);
  assert.match(html, /data-side="now"[\s\S]*Aujourd’hui/);
  assert.match(html, /<span class="carte-flag" data-flag="register">vous savez<span class="av2-sr"> \(registre\)<\/span><\/span>/);
  assert.match(html, /<span class="carte-flag" data-flag="grammar">le récolte<span class="av2-sr"> \(grammaire\)<\/span><\/span>/);
  assert.match(text, /Avec moi, c’est « tu », pas « vous »\./);
  assert.doesNotMatch(text, /\d+ ?%|score|\/ ?10/i);
  assert.deepEqual(palais.relectureSegments('abcdef', [{ start: 1, end: 3, flag: 'grammar' }, { start: 2, end: 4, flag: 'register' }]), [
    { text: 'a', flag: null }, { text: 'bc', flag: 'grammar' }, { text: 'def', flag: null },
  ]);
});

// --- 5. the wire ------------------------------------------------------------------------------------

test('the parser reads due counts, relecture marks, review items and the pair', () => {
  const view = types.parseCarteView({
    pins: [{ session_id: 's1', lat: 48.85, lon: 2.35, place_id: 'marche_aligre', due_words: 2, relecture: { state: 'read', read_at: '2026-11-14T10:00:00Z' } },
           { session_id: 's2', lat: 48.86, lon: 2.36, due_words: -3, relecture: { state: 'maybe' } }],
    due_total: 2,
  });
  assert.equal(view.dueTotal, 2);
  assert.deepEqual([view.pins[0].placeId, view.pins[0].dueWords, view.pins[0].relecture], ['marche_aligre', 2, { state: 'read', readAt: '2026-11-14T10:00:00Z' }]);
  assert.deepEqual([view.pins[1].placeId, view.pins[1].dueWords, view.pins[1].relecture], [null, 0, null]);
  const review = types.parseCarteReview({
    place_id: 'marche_aligre', place_label_fr: 'Aligre', plate_url: '/p.webp', week: '2026-W40', headline_fr: 'T',
    words: [{ progress_id: 'p1', word_id: 3, word: 'la récolte', gloss: 'die Ernte', sentence_fr: 'S.', speaker_id: 'romy_tremblay', speaker_name: 'Romy', line_fr: 'L.', session_id: 's', week: '2026-W40' }],
    items: [{ id: 'w:p1', task_type: 'word_bank', progress_ids: ['p1'], options: [{ id: 'a', text_fr: 'la', side: null }], answer_key: { version: 1, salt: 's', digests: ['d'] } },
            { id: 'x', task_type: 'essay' }],
  });
  assert.equal(review.items.length, 1);
  assert.deepEqual(review.items[0].answerKey, { version: 1, salt: 's', digests: ['d'] });
  const pair = types.parseRelecturePair({
    session_id: 's', offer: { session_id: 's', week: '2026-W35', kind: 'question', dossier_title_fr: 'T', prompt_fr: 'Q ?', place_label_fr: 'P' },
    then: { label_fr: 'Semaine 35', text_fr: 'a', spans: [] }, now: { label_fr: 'Aujourd’hui', text_fr: 'abc', spans: [{ start: 0, end: 1, flag: 'register' }, { start: 2, end: 1, flag: 'grammar' }] },
    romy_line_fr: 'R', asked_at: 'x',
  });
  assert.deepEqual(pair.now.spans, [{ start: 0, end: 1, flag: 'register' }]);
  assert.equal(types.parseRelecturePair({ offer: {} }), null);
});

test('the client calls the review, grade and relecture routes', async () => {
  const calls = [];
  const client = createCarteClient({
    get: async (url) => (calls.push(['get', url]), url.endsWith('/offer') ? { offer: null } : { place_id: 'x', words: [], items: [] }),
    post: async (url, body) => (calls.push(['post', url, body]), url.includes('relecture')
      ? { session_id: 's', offer: { session_id: 's', prompt_fr: 'Q' }, then: {}, now: {}, romy_line_fr: 'R', asked_at: '' }
      : { item_id: body.item_id, results: [], remaining: 0 }),
  });
  await client.review('marche aligre');
  const grade = await client.grade('marche aligre', { itemId: 'w:p1', tileIds: ['a'] });
  assert.equal(grade.remaining, 0);
  assert.equal(await client.relectureOffer(), null);
  await client.relectureAnswer('s', 'Oui.');
  assert.deepEqual(calls, [
    ['get', '/revue/carte/review/marche%20aligre'],
    ['post', '/revue/carte/review/marche%20aligre/grade', { item_id: 'w:p1', tile_ids: ['a'], text: null, assisted: false }],
    ['get', '/revue/relecture/offer'],
    ['post', '/revue/relecture/s', { answer_fr: 'Oui.', mode: 'text' }],
  ]);
});

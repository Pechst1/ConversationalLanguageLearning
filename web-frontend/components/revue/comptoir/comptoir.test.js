// node --test components/revue/comptoir/comptoir.test.js
//
// «Au comptoir» (WP-119-AU-COMPTOIR §7), the client:
//
//   1. the model: the shown step never ahead of the server's, the main button
//      only once the screen's act is in, the dots, the takes revealed one by one,
//      the A1 sentence (elided «parce qu'»), Romy's red pen (word diff), the tally,
//      the liar's struck words;
//   2. the wire (WIRE §9): a snake_case view, result and page parsed; act bodies
//      sent in snake_case; the opinion is a Relevé kind;
//   3. the player rendered at A1, A2 and B1 from the dev mock's sessions, each step
//      in turn: one chrome language, the French publication words, at most two
//      buttons in a foot, the intox redacted until the liar is named;
//   4. the Une card and the chooser with the question of the day and the faces.

const assert = require('node:assert/strict');
const { test } = require('node:test');

const setup = require('../revue-test-setup');

const { h, render } = setup;
/** What a reader sees: the player's inline reader styles are not text. */
const visibleText = (html) => setup.visibleText(html.replace(/<style[\s\S]*?<\/style>/g, ' '));

const types = require('../../../lib/revue-types.ts');
const { createMockRevueClient } = require('../../../lib/revue-mock.ts');
const { revueCopy } = require('../revue-copy.ts');
const model = require('./comptoir-model.ts');
const { comptoirCopy, COMPTOIR_FR, lineIn, COMPTOIR_LINES } = require('./comptoir-copy.ts');
const { ComptoirClipping } = require('./RvComptoirPage.tsx');
const { RvComptoirTakes } = require('./RvComptoirTakes.tsx');
const { RvComptoirIntox } = require('./RvComptoirIntox.tsx');
const { sessionGlosses } = require('../revue-model.ts');
const { RvComptoir, RvUneCard } = require('../index.ts');

// ---------------------------------------------------------------------------
// 1. The model
// ---------------------------------------------------------------------------

const STEPS = ['read', 'takes', 'intox', 'opinion', 'page'];

test('the shown step: the server is the limit, «La page» only through the close', () => {
  assert.equal(model.openingStep({ step: 'takes' }, false), 'takes');
  assert.equal(model.openingStep({ step: 'page' }, false), 'opinion', 'the opinion screen holds «Voir la page»');
  assert.equal(model.openingStep({ step: 'opinion' }, true), 'page');
  assert.equal(model.clampStep({ step: 'takes' }, 'opinion', false), 'takes', 'never ahead of the server');
  assert.equal(model.clampStep({ step: 'opinion' }, 'read', false), 'read', 'a finished screen stays until its button');
  assert.equal(model.nextStep({ steps: STEPS }, 'takes'), 'intox');
  assert.equal(model.nextStep({ steps: ['read', 'takes', 'opinion', 'page'] }, 'takes'), 'opinion', 'four dots without an intox');
  assert.equal(model.nextStep({ steps: STEPS }, 'page'), null);
  assert.deepEqual(
    model.stepDots(STEPS, 'intox', false).map((dot) => dot.state),
    ['done', 'done', 'active', 'pending', 'pending'],
  );
  assert.ok(model.stepDots(STEPS, 'page', true).every((dot) => dot.state === 'done'));
});

test('the main button waits for the screen\'s act', () => {
  const cast = (reactions) => reactions.map((reaction, i) => ({ id: `g${i}`, reaction }));
  const view = (extra) => ({ vote: null, cast: cast([null, null, null]), intox: null, opinion: null, ...extra });
  assert.equal(model.stepDone(view(), 'read'), false);
  assert.equal(model.stepDone(view({ vote: 'pour' }), 'read'), true);
  assert.equal(model.stepDone(view({ cast: cast(['agree', 'disagree', null]) }), 'takes'), false);
  assert.equal(model.stepDone(view({ cast: cast(['agree', 'disagree', 'agree']) }), 'takes'), true);
  assert.equal(model.stepDone(view({ intox: { fix: null } }), 'intox'), false);
  assert.equal(model.stepDone(view({ intox: { fix: { correct: false } } }), 'intox'), true, 'a wrong fix still goes on');
  assert.equal(model.stepDone(view({ opinion: { comeback: null } }), 'opinion'), false);
  assert.equal(model.stepDone(view({ opinion: { comeback: { textFr: 'Un peu…' } } }), 'opinion'), true);
});

test('«Les avis»: the first take at once, one more per reaction', () => {
  assert.equal(model.revealedTakes([{ reaction: null }, { reaction: null }, { reaction: null }]), 1);
  assert.equal(model.revealedTakes([{ reaction: 'agree' }, { reaction: null }, { reaction: null }]), 2);
  assert.equal(model.revealedTakes([{ reaction: 'agree' }, { reaction: 'disagree' }, { reaction: 'agree' }]), 3);
});

test('A1: the sentence from the tiles, «parce qu\'» before a vowel', () => {
  assert.equal(model.parceQue('sa voix est belle'), 'parce que sa voix est belle');
  assert.equal(model.parceQue('il y a trop de bruit'), "parce qu'il y a trop de bruit");
  assert.equal(model.parceQue('on y parle entre voisins'), "parce qu'on y parle entre voisins");
  assert.equal(model.a1Sentence('pour', 'les légumes sont frais'), 'Je suis pour, parce que les légumes sont frais.');
  assert.equal(model.a1Sentence('nuance', 'elle chante bien.'), "Ça dépend, parce qu'elle chante bien.");
  assert.equal(model.a1Sentence('contre', null), 'Je suis contre, parce que…');
  assert.equal(model.insertWord('la foule  ', 'le bruit'), 'la foule le bruit');
  assert.equal(model.insertWord('', 'le bruit'), 'le bruit');
});

test('Romy\'s marks: the learner\'s words underlined where she found a slip, by offset, else by first occurrence', () => {
  const draft = 'le gens sont content';
  assert.deepEqual(model.markSegments(draft, [{ spanFr: 'le', start: 0, kind: 'accord' }, { spanFr: 'content', start: 13, kind: 'accord' }]), [
    { text: 'le', kind: 'accord' },
    { text: ' gens sont ', kind: null },
    { text: 'content', kind: 'accord' },
  ]);
  assert.deepEqual(
    model.markSegments(draft, [{ spanFr: 'gens', start: 99, kind: 'orthographe' }]),
    [{ text: 'le ', kind: null }, { text: 'gens', kind: 'orthographe' }, { text: ' sont content', kind: null }],
    'a stale offset falls back to the first occurrence',
  );
  assert.deepEqual(model.markSegments(draft, [{ spanFr: 'absent', start: 0, kind: 'mot' }]), [{ text: draft, kind: null }], 'a mark not in the draft is dropped');
  assert.deepEqual(
    model.markSegments(draft, [{ spanFr: 'le gens', start: 0, kind: 'accord' }, { spanFr: 'gens', start: 3, kind: 'mot' }]).filter((segment) => segment.kind),
    [{ text: 'le gens', kind: 'accord' }],
    'overlapping marks: the first stands',
  );
});

test('Romy\'s red pen: only the words she changed, one run for neighbours, never punctuation', () => {
  const marked = (before, after) =>
    model
      .wordDiff(before, after)
      .filter((segment) => segment.changed)
      .map((segment) => segment.text);
  assert.deepEqual(
    marked('le marché fait du bruit tres tôt et le gens sont fatigués', 'Le marché fait du bruit très tôt et les gens sont fatigués.'),
    ['très', 'les'],
    'a capital and the final stop are not marked',
  );
  assert.deepEqual(marked('sa voix est tres beau', 'Sa voix est très belle.'), ['très belle'], 'neighbours make one run');
  assert.deepEqual(marked('Je suis pour.', 'Je suis pour.'), []);
  assert.equal(model.edited('Je suis pour.', 'Je suis pour !'), false);
  assert.equal(model.edited('le gens', 'les gens'), true);
  const joined = model.wordDiff('a b c', 'a x c').map((segment) => segment.text).join('');
  assert.equal(joined, 'a x c', 'the segments rebuild the edit');
});

test('the page: the tally in the page\'s order, the view\'s votes, the liar\'s struck words', () => {
  assert.deepEqual(
    model.voteTally({ pour: 2, contre: 1, nuance: 1 }).map((row) => [row.stance, row.count, row.share]),
    [['pour', 2, 0.5], ['nuance', 1, 0.25], ['contre', 1, 0.25]],
  );
  assert.deepEqual(model.voteTally({ pour: 0, contre: 0, nuance: 0 }).map((row) => row.share), [0, 0, 0]);
  const cast = [{ stance: 'pour' }, { stance: 'nuance' }, { stance: 'contre' }];
  assert.deepEqual(model.viewVotes({ cast, vote: 'contre', opinion: null }), { pour: 1, contre: 2, nuance: 1 });
  assert.deepEqual(model.viewVotes({ cast, vote: 'contre', opinion: { stance: 'pour' } }), { pour: 2, contre: 1, nuance: 1 }, 'the opinion\'s side wins over the gut vote');
  assert.deepEqual(model.quoteSegments('Sept jours sur sept ? Mon cher, c’est trop de bruit.', 'sept jours sur sept'), [
    { text: 'Sept jours sur sept', wrong: true },
    { text: ' ? Mon cher, c’est trop de bruit.', wrong: false },
  ]);
  assert.deepEqual(model.quoteSegments('Le silence, toujours.', 'le 12 octobre'), [{ text: 'Le silence, toujours.', wrong: false }]);
  assert.equal(model.castName({ cast: [{ id: 'augustin_de_roncourt', nameFr: 'Gus' }] }, 'augustin_de_roncourt'), 'Gus');
  assert.equal(model.castName({ cast: [] }, 'lila_bonnet'), 'lila');
});

test('the copy: every chrome has every key; Romy\'s lines carry their translation', () => {
  const keys = Object.keys(comptoirCopy('fr')).sort();
  for (const lang of ['en', 'de']) assert.deepEqual(Object.keys(comptoirCopy(lang)).sort(), keys, lang);
  assert.equal(comptoirCopy('xx').give_opinion, 'Donner mon avis');
  assert.deepEqual(lineIn(COMPTOIR_LINES.intox_reveal, 'en', { name: 'Gus' }), { fr: "C'était Gus.", tr: 'It was Gus.' });
  assert.deepEqual(lineIn(COMPTOIR_LINES.intox_found, 'fr'), { fr: 'Bien vu !', tr: null });
  for (const lang of ['fr', 'en', 'de']) assert.ok(revueCopy(lang).made_opinion && revueCopy(lang).comptoir_faces.includes('{names}'), lang);
});

// ---------------------------------------------------------------------------
// 2. The wire
// ---------------------------------------------------------------------------

const claim = { id: 'c2', kind: 'fact', fr: "Le marché d'Aligre a lieu six jours sur sept.", quote: 'six jours sur sept', attributed_to: null, source: { id: 's1', name: 'Wikipédia', url: 'https://fr.wikipedia.org/wiki/March%C3%A9_d%27Aligre', published_at: '2026-03-10' } };
const RAW_VIEW = {
  step: 'opinion',
  steps: ['read', 'takes', 'intox', 'opinion', 'page'],
  band: 'a2',
  question: { fr: 'Aligre ouvre six jours sur sept. Bonne idée ?', tr: 'Aligre opens six days a week. Good idea?' },
  read: { dateline_fr: "Le marché d'Aligre, un matin", lead: { fr: 'Paris a 91 marchés.', tr: 'Paris has 91 markets.' }, sources: [claim.source] },
  cast: [
    { id: 'romy_tremblay', name_fr: 'Romy', role_fr: 'journaliste', stance: 'pour', take: { fr: 'Un marché, c’est la vraie vie.', tr: null }, reaction: 'agree' },
    { id: 'margaux_lefort', name_fr: 'Margaux', role_fr: 'Le Mistral', stance: 'nuance', take: { fr: 'Ça dépend.', tr: null }, reaction: 'disagree' },
    { id: 'augustin_de_roncourt', name_fr: 'Gus', role_fr: 'consultant', stance: 'contre', take: { fr: 'Sept jours sur sept ?', tr: null }, reaction: 'agree' },
  ],
  has_intox: true,
  vote: 'contre',
  intox: {
    quotes: [{ cast_id: 'augustin_de_roncourt', name_fr: 'Gus', role_fr: 'consultant', stance: 'contre', quote_fr: 'Sept jours sur sept ?' }],
    tries: ['romy_tremblay', 'augustin_de_roncourt'],
    resolved: true,
    found: true,
    by: 'augustin_de_roncourt',
    hint_claim: claim,
    ask: { fr: 'Combien de jours par semaine, en vrai ?', tr: null },
    options: ['six jours sur sept', '91 marchés'],
    fix: { correct: true, answer_fr: 'six jours sur sept', line_fr: "C'est faux, Gus ! C'est six jours sur sept, pas sept jours sur sept.", wrong_fr: 'sept jours sur sept', right_fr: 'six jours sur sept', claim, caught: { fr: 'Bon, j’ai arrondi.', tr: 'Well, I rounded up.' } },
  },
  kit: {
    input: 'frame',
    phrase: { fr: 'À mon avis…, parce que…', tr: null },
    reasons: { pour: [{ fr: 'le marché est vivant', tr: null }], contre: [], nuance: [] },
    frames: { pour: { fr: 'À mon avis, c’est une bonne idée, parce que…', tr: null }, contre: { fr: 'À mon avis, ce n’est pas une bonne idée, parce que…', tr: null }, nuance: { fr: 'Ça dépend…', tr: null } },
    bank: [{ fr: 'le bruit', tr: 'the noise' }],
    opponents: { pour: 'augustin_de_roncourt', contre: 'romy_tremblay', nuance: 'augustin_de_roncourt' },
  },
  opinion: {
    stance: 'contre',
    learner_fr: 'le gens sont fatigués',
    draft_fr: 'les gens sont fatigués',
    proof: 'fixed',
    marks: [],
    tries: 1,
    max_tries: 2,
    printed_fr: 'Les gens sont fatigués.',
    reply: { by: 'romy_tremblay', name_fr: 'Romy', line: { fr: 'Tu as peur du bruit ?', tr: 'Scared of the noise?' } },
    comebacks: [{ fr: 'Pas du tout !', tr: 'Not at all!' }, { fr: 'Un peu…', tr: 'A little…' }],
    comeback: { text_fr: 'Un peu…', index: 1, last_word: { fr: 'Ah bon ?', tr: 'Really?' } },
  },
};

test('wire: a comptoir session view, snake_case in, camelCase out (WIRE §9.2)', () => {
  const session = types.parseSessionView({ id: 's', status: 'active', mode: 'comptoir', comptoir: RAW_VIEW, thread: [] });
  assert.equal(session.mode, 'comptoir');
  const view = session.comptoir;
  assert.equal(view.step, 'opinion');
  assert.equal(view.band, 'a2');
  assert.equal(view.hasIntox, true);
  assert.equal(view.read.datelineFr, "Le marché d'Aligre, un matin");
  assert.deepEqual(view.cast.map((member) => [member.nameFr, member.stance, member.reaction]), [
    ['Romy', 'pour', 'agree'],
    ['Margaux', 'nuance', 'disagree'],
    ['Gus', 'contre', 'agree'],
  ]);
  assert.equal(view.intox.hintClaim.id, 'c2');
  assert.equal(view.intox.fix.lineFr, "C'est faux, Gus ! C'est six jours sur sept, pas sept jours sur sept.");
  assert.equal(view.intox.fix.caught.tr, 'Well, I rounded up.');
  assert.equal(view.kit.input, 'frame');
  assert.equal(view.kit.opponents.contre, 'romy_tremblay');
  assert.equal(view.opinion.proof, 'fixed');
  assert.equal(view.opinion.draftFr, 'les gens sont fatigués');
  assert.equal(view.opinion.printedFr, 'Les gens sont fatigués.');
  assert.deepEqual([view.opinion.tries, view.opinion.maxTries], [1, 2]);
  assert.equal(view.opinion.comeback.lastWord.fr, 'Ah bon ?');
  // Romy's marks while the sentence waits: a mark without its words is dropped, an unknown kind is «mot».
  const marked = types.parseComptoirView({
    ...RAW_VIEW,
    opinion: {
      ...RAW_VIEW.opinion,
      draft_fr: 'le gens sont fatigués',
      proof: 'marked',
      marks: [{ span_fr: 'le', start: 0, kind: 'accord' }, { span_fr: '', start: 0, kind: 'genre' }, { span_fr: 'gens', start: 3, kind: 'style' }],
      tries: 0,
      printed_fr: null,
      reply: null,
      comebacks: [],
      comeback: null,
    },
  });
  assert.deepEqual(marked.opinion.marks, [{ spanFr: 'le', start: 0, kind: 'accord' }, { spanFr: 'gens', start: 3, kind: 'mot' }]);
  assert.equal(marked.opinion.printedFr, null);
  assert.equal(marked.opinion.reply, null);
  // A view from before the proof (2026-10-23) has no draft: the learner's sentence stands in.
  const older = types.parseComptoirView({ ...RAW_VIEW, opinion: { stance: 'pour', learner_fr: 'Je suis pour.', reply: null, comebacks: [], comeback: null } });
  assert.equal(older.opinion.draftFr, 'Je suis pour.');
  assert.equal(view.opinion.comeback.index, 1);
});

test('wire: a chat session keeps its defaults; unknown values fall back safely', () => {
  const chat = types.parseSessionView({ id: 's', status: 'active', thread: [] });
  assert.equal(chat.mode, 'chat');
  assert.equal(chat.comptoir, null);
  const odd = types.parseComptoirView({ step: 'later', steps: ['read', 'nowhere'], band: 'c2', vote: 'peut-être' });
  assert.equal(odd.step, 'read');
  assert.deepEqual(odd.steps, ['read']);
  assert.equal(odd.band, 'a2');
  assert.equal(odd.vote, 'nuance');
  assert.equal(odd.intox, null);
  assert.equal(odd.opinion, null);
});

test('wire: the act result, the page at the close, the act bodies (WIRE §9.3–9.4)', () => {
  const result = types.parseComptoirResult({ session: { id: 's', status: 'active', mode: 'comptoir', comptoir: RAW_VIEW, thread: [] }, error_fr: 'Écris ta raison : quelques mots suffisent.' });
  assert.equal(result.errorFr, 'Écris ta raison : quelques mots suffisent.');
  assert.equal(result.session.comptoir.step, 'opinion');
  const page = types.parseComptoirPage({
    question_fr: 'Aligre ouvre six jours sur sept. Bonne idée ?',
    dateline_fr: "Le marché d'Aligre, un matin",
    standfirst_fr: 'Paris a 91 marchés.',
    quotes: [{ cast_id: 'romy_tremblay', name_fr: 'Romy', role_fr: 'journaliste', stance: 'pour', quote_fr: 'Un marché, c’est la vraie vie.' }],
    mine: { cast_id: 'user', name_fr: 'Toi', role_fr: '', stance: 'contre', quote_fr: 'Les gens sont fatigués.' },
    votes: { pour: 1, contre: 2, nuance: 1 },
    intox: { by: 'augustin_de_roncourt', name_fr: 'Gus', wrong_fr: 'sept jours sur sept', right_fr: 'six jours sur sept', source_name: 'Wikipédia' },
    phrase_fr: 'À mon avis…, parce que…',
    words: ['marchés', 'jours'],
  });
  assert.equal(page.mine.quoteFr, 'Les gens sont fatigués.');
  assert.equal(page.proof, null, 'a page closed before the proof');
  assert.equal(types.parseComptoirPage({ proof: 'corrected' }).proof, 'corrected');
  assert.deepEqual(page.votes, { pour: 1, contre: 2, nuance: 1 });
  assert.equal(page.intox.sourceName, 'Wikipédia');
  assert.deepEqual(types.comptoirBodyWire({ act: 'react', guestId: 'romy_tremblay', value: 'agree' }), { act: 'react', guest_id: 'romy_tremblay', value: 'agree' });
  assert.deepEqual(types.comptoirBodyWire({ act: 'opinion', value: 'pour', reasonIndex: 2 }), { act: 'opinion', value: 'pour', reason_index: 2 });
  assert.deepEqual(types.comptoirBodyWire({ act: 'intox_fix', text: "C'est faux !", mode: 'voice' }), { act: 'intox_fix', text: "C'est faux !", mode: 'voice' });
  assert.deepEqual(types.comptoirBodyWire({ act: 'comeback', index: 0 }), { act: 'comeback', index: 0 });
  assert.deepEqual(types.comptoirBodyWire({ act: 'opinion_fix', text: 'les gens', mode: 'text' }), { act: 'opinion_fix', text: 'les gens', mode: 'text' });
  assert.deepEqual(types.comptoirBodyWire({ act: 'opinion_fix', value: 'romy' }), { act: 'opinion_fix', value: 'romy' });
  // The learner's quote is a Relevé entry of its own kind.
  assert.equal(types.parseMade({ kind: 'opinion', text_fr: 'Les gens sont fatigués.' }).kind, 'opinion');
  assert.ok(types.RV_MADE_KINDS.includes('opinion'));
  assert.ok(!types.RV_MAKE_KINDS.includes('opinion'), 'never offered by the chat\'s make picker');
});

// ---------------------------------------------------------------------------
// 3. The player at A1, A2 and B1 (the dev mock's Céline story)
// ---------------------------------------------------------------------------

const LIAR = 'augustin_de_roncourt';

async function counter(band, language) {
  const client = createMockRevueClient({ persist: false, comptoir: true, band, language, pictures: true });
  const week = await client.week();
  let session = await client.start();
  const act = async (body) => {
    const result = await client.comptoir(session.id, body);
    session = result.session;
    return result;
  };
  // The player opens on the server's step; a finished screen (held until its button) is its step component.
  const screen = () => render(h(RvComptoir, { client, session, onExit: () => {}, onReleve: () => {} }));
  const step = (Component) => render(h(Component, stepProps(session)));
  return { client, week, act, screen, step, get session() { return session; }, set session(value) { session = value; } };
}

function stepProps(session) {
  const chrome = session.plan.uiLanguage;
  return {
    session,
    view: session.comptoir,
    copy: revueCopy(chrome),
    ccopy: comptoirCopy(chrome),
    glossLanguage: session.plan.glossLanguage,
    glosses: sessionGlosses(session),
    voice: { speak: () => {}, stop: () => {}, speakingKey: null, supported: false, progress: 0 },
    pending: null,
    readOnly: false,
    onAct: async () => true,
    onContinue: () => {},
    wordFor: () => () => {},
    notice: null,
    footRef: null,
  };
}

/** French lines print every word as its own control: compare without the spaces between them. */
const squash = (value) => value.replace(/\s+/g, '');
const has = (text, phrase) => squash(text).includes(squash(phrase));

/** The foot's buttons (the main button and at most one more). */
function footButtons(html) {
  const foot = html.slice(html.lastIndexOf('class="rv-foot'));
  return (foot.match(/<button/g) || []).length;
}

const ENGLISH_CHROME = /\b(Continue|Give my opinion|See the page|Listen|Translate)\b/;
const GERMAN_CHROME = /\b(Weiter|Meine Meinung sagen|Die Seite ansehen|Anhören|Übersetzen)\b/;

for (const [band, language] of [['A1', 'en'], ['A2', 'de'], ['B1', 'en']]) {
  test(`the player at ${band} (${language}): read → takes → intox → opinion → page`, async () => {
    const c = await counter(band, language);
    const lower = band !== 'B1';
    assert.equal(c.session.mode, 'comptoir');
    assert.equal(c.session.thread.length, 0, 'no chat at the counter');
    const view0 = c.session.comptoir;
    assert.equal(view0.band, band.toLowerCase());

    // «Lire»: the picture, the lead, the question and the gut vote; the press waits for the vote.
    let html = c.screen();
    let text = visibleText(html);
    assert.match(html, /class="ct-q"/);
    assert.match(text, /Céline revient en mai 2027/);
    for (const vote of ['Oui !', 'Non.', 'Bof…']) assert.ok(text.includes(vote), vote);
    assert.match(html, /<button[^>]*disabled=""[^>]*>[\s\S]*?Au comptoir/, 'the press waits for the vote');
    assert.ok(footButtons(html) <= 2);
    assert.match(html, new RegExp(`data-band="${band.toLowerCase()}"`));
    assert.match(html, /class="rv-word"/, 'every word of the lead can be tapped');

    await c.act({ act: 'vote', value: 'contre' });
    assert.equal(c.session.comptoir.step, 'takes');

    // «Les avis»: one take, then one more per reaction; the stance tags as the page prints them.
    html = c.screen();
    text = visibleText(html);
    assert.equal((html.match(/class="ct-takes__row"/g) || []).length, 1);
    assert.ok(text.includes('POUR'));
    assert.ok(!text.includes('CONTRE'), 'Gus has not spoken yet');
    const cast = c.session.comptoir.cast;
    await c.act({ act: 'react', guestId: cast[0].id, value: 'agree' });
    html = c.screen();
    assert.equal((html.match(/class="ct-takes__row"/g) || []).length, 2);
    await c.act({ act: 'react', guestId: cast[1].id, value: 'disagree' });
    html = c.screen();
    assert.equal((html.match(/class="ct-takes__row"/g) || []).length, 3);
    assert.match(html, /<button[^>]*disabled=""[^>]*>(<span>)?(Continue|Weiter)/, 'Continue waits for the last reaction');
    await c.act({ act: 'react', guestId: cast[2].id, value: 'agree' });
    assert.equal(c.session.comptoir.step, 'intox');
    html = c.step(RvComptoirTakes);
    text = visibleText(html);
    assert.equal((html.match(/class="ct-takes__row"/g) || []).length, 3);
    for (const tag of ['POUR', 'ÇA DÉPEND', 'CONTRE']) assert.ok(text.includes(tag), tag);
    assert.ok(text.includes(language === 'de' ? '3 Meinungen · 1 Falschmeldung versteckt' : '3 opinions · 1 false claim hidden'));
    assert.ok(!/<button[^>]*disabled=""[^>]*>(<span>)?(Continue|Weiter)/.test(html), 'then Continue');

    // «L'intox»: redacted until the liar is named.
    let intox = c.session.comptoir.intox;
    assert.equal(intox.by, null);
    assert.deepEqual(intox.options, []);
    html = c.screen();
    text = visibleText(html);
    assert.ok(has(text, "Attends… quelqu'un a dit un truc faux. Qui ?"));
    assert.equal((html.match(/class="ct-pick__b"/g) || []).length, 3);
    await c.act({ act: 'intox_who', guestId: 'romy_tremblay' });
    html = c.screen();
    text = visibleText(html);
    assert.ok(has(text, 'Non, relis bien.'));
    assert.match(html, /data-state="tried"/);
    assert.ok(c.session.comptoir.intox.hintClaim, 'the claim to reread');
    await c.act({ act: 'intox_who', guestId: LIAR });
    intox = c.session.comptoir.intox;
    assert.equal(intox.by, LIAR);
    assert.equal(intox.found, true);
    html = c.screen();
    text = visibleText(html);
    assert.ok(has(text, 'Bien vu !'));
    if (lower) {
      assert.equal((html.match(/class="ct-opt"/g) || []).length, 2, 'two options at A1–A2');
      await c.act({ act: 'intox_fix', value: 'le 17 octobre' });
    } else {
      assert.match(html, /class="rv-composer"/, 'B1 writes the correction');
      assert.ok(!html.includes('C&#x27;est …') && !text.includes("C'est …"), 'from an empty field: no prefill');
      const short = await c.act({ act: 'intox_fix', text: 'le 17 octobre' });
      assert.match(short.errorFr, /Une phrase entière/, 'the number alone is not a correction');
      assert.equal(c.session.comptoir.intox.fix, null);
      await c.act({ act: 'intox_fix', text: "C'est faux, Gus ! C'est le 17 octobre, pas le 12 octobre." });
    }
    intox = c.session.comptoir.intox;
    assert.equal(intox.fix.correct, true);
    assert.equal(c.session.comptoir.step, 'opinion');
    html = c.step(RvComptoirIntox);
    text = visibleText(html);
    // «Your line» only under the learner's own typed line; a pick is «the right line».
    const ccopy = comptoirCopy(language);
    assert.ok(text.includes(lower ? ccopy.intox_right_line : ccopy.intox_your_line), 'the line\'s label');
    assert.ok(!text.includes(lower ? ccopy.intox_your_line : ccopy.intox_right_line));
    assert.match(html, /<s class="ct-strike">le 12 octobre<\/s>/, 'the wrong words struck in the liar\'s quote');
    assert.ok(has(text, lineIn(COMPTOIR_LINES.intox_found, 'fr').fr));
    assert.ok(has(text, intox.fix.caught.fr), 'the liar caught');
    assert.equal((html.match(/class="rv-claim"/g) || []).length, 1, 'the settling claim is not printed twice');
    assert.ok(footButtons(html) <= 2);

    // «Ton avis»: the band's input; then Romy's marks, the learner's fix, the reply, the comeback.
    html = c.screen();
    text = visibleText(html);
    assert.ok(has(text, 'Et toi ? Il me manque une voix pour mon micro-trottoir.'));
    if (band === 'A1') {
      assert.equal((html.match(/class="ct-tile"/g) || []).length, 3, 'three reasons as tiles');
      await c.act({ act: 'opinion', value: 'contre', reasonIndex: 0 });
      assert.equal(c.session.comptoir.opinion.proof, 'clean', 'the tiles are correct by construction');
    } else if (band === 'A2') {
      assert.match(html, /class="ct-frame"/);
      assert.match(html, /class="ct-bank"/, 'A2 has its word bank');
      const short = await c.act({ act: 'opinion', value: 'contre', text: 'sa voix' });
      assert.match(short.errorFr, /4 mots au moins/, 'one bank chip is not a reason');
      assert.equal(c.session.comptoir.opinion, null);
      await c.act({ act: 'opinion', value: 'contre', text: 'les billets sont tres cher' });
    } else {
      const opponent = model.castName(c.session.comptoir, c.session.comptoir.kit.opponents.contre);
      assert.ok(text.includes(`Answer ${opponent}`), 'B1 answers the other side (the side defaults to the vote)');
      const short = await c.act({ act: 'opinion', value: 'contre', text: 'Je suis contre, parce que les billets sont tres cher' });
      assert.match(short.errorFr, /12 mots au moins/);
      await c.act({ act: 'opinion', value: 'contre', text: 'Je suis contre, parce que les billets sont tres cher et la salle est trop loin de chez moi' });
    }
    if (band !== 'A1') {
      // Romy marks the slip; nothing prints, nobody answers yet.
      let opinion = c.session.comptoir.opinion;
      assert.equal(opinion.proof, 'marked');
      assert.deepEqual(opinion.marks.map((mark) => [mark.spanFr, mark.kind]), [['tres', 'orthographe']]);
      assert.equal(opinion.printedFr, null);
      assert.equal(opinion.reply, null);
      html = c.screen();
      text = visibleText(html);
      assert.ok(has(text, lineIn(COMPTOIR_LINES.proof_marked, 'fr').fr));
      assert.match(html, /<mark class="ct-mark" data-kind="orthographe">tres<\/mark>/, 'the learner\'s word underlined, not fixed');
      assert.ok(text.includes(comptoirCopy(language).mark_kinds.orthographe), 'the kind of slip, in the chrome');
      assert.ok(!text.includes('très'), 'the answer is not given away');
      assert.ok(!text.includes(COMPTOIR_FR.in_paper_read), 'never «relu par Romy» before it is right');
      assert.match(html, /class="rv-composer"/, 'the fix in the foot');
      assert.ok(!text.includes(comptoirCopy(language).fix_romy), '«Corrige-le, Romy» only after a try');
      const same = await c.act({ act: 'opinion_fix', text: opinion.draftFr });
      assert.match(same.errorFr, /Rien n'a changé/);
      assert.equal(c.session.comptoir.opinion.tries, 0, 'an unchanged sentence is not a try');
      if (band === 'A2') {
        await c.act({ act: 'opinion_fix', text: opinion.draftFr.replace('tres', 'très') });
        opinion = c.session.comptoir.opinion;
        assert.equal(opinion.proof, 'fixed');
        html = c.screen();
        text = visibleText(html);
        assert.ok(text.includes(COMPTOIR_FR.in_paper_mine), 'corrigé par toi');
        assert.doesNotMatch(html, /class="ct-fix"/, 'the learner\'s own fix prints plain');
      } else {
        await c.act({ act: 'opinion_fix', text: opinion.draftFr.replace('cher', 'chers') });
        opinion = c.session.comptoir.opinion;
        assert.deepEqual([opinion.proof, opinion.tries], ['marked', 1], 'still a slip after the first try');
        html = c.screen();
        assert.ok(visibleText(html).includes(comptoirCopy(language).fix_romy), 'then «Corrige-le, Romy»');
        assert.ok(visibleText(html).includes('Try 2 of 2'));
        await c.act({ act: 'opinion_fix', value: 'romy' });
        opinion = c.session.comptoir.opinion;
        assert.equal(opinion.proof, 'corrected');
        html = c.screen();
        text = visibleText(html);
        assert.ok(text.includes(COMPTOIR_FR.in_paper_fixed), 'corrigé par Romy');
        assert.match(html, /<mark class="ct-fix">très<\/mark>/, 'what she changed is lit');
      }
    } else {
      html = c.screen();
      text = visibleText(html);
      assert.ok(text.includes(COMPTOIR_FR.in_paper) && !text.includes(COMPTOIR_FR.in_paper_read), 'A1\'s tiles: plain «Dans le journal»');
    }
    const opinion = c.session.comptoir.opinion;
    assert.ok(opinion.printedFr);
    assert.ok(has(text, opinion.reply.line.fr));
    if (lower) {
      assert.equal((html.match(/class="ct-comeback"/g) || []).length, 3);
      await c.act({ act: 'comeback', index: 1 });
    } else {
      assert.match(html, /class="rv-composer"/);
      await c.act({ act: 'comeback', text: 'Peut-être, mais moi je chante quand même !' });
    }
    assert.ok(c.session.comptoir.opinion.comeback.lastWord.fr);
    html = c.screen();
    text = visibleText(html);
    assert.ok(has(text, c.session.comptoir.opinion.comeback.lastWord.fr));
    assert.ok(footButtons(html) <= 2);

    // The chrome speaks one language; the publication's words stay French.
    if (language === 'en') assert.match(text, ENGLISH_CHROME);
    if (language === 'de') {
      assert.match(text, GERMAN_CHROME);
      assert.ok(!ENGLISH_CHROME.test(text), `no English in a German chrome: ${text.match(ENGLISH_CHROME)}`);
    }

    // «La page»: the close builds the vox pop; a later visit opens on it, filed.
    const closed = await c.client.close(c.session.id);
    const page = closed.closing.comptoirPage;
    assert.ok(page, 'the close prints the page');
    assert.equal(page.mine.stance, 'contre');
    assert.deepEqual(page.votes, model.viewVotes(c.session.comptoir));
    c.session = { ...closed.session, closing: closed.closing };
    html = c.screen();
    text = visibleText(html);
    assert.match(html, /class="ct-clip"/);
    assert.ok(text.includes(COMPTOIR_FR.page_kicker.toUpperCase()) || text.includes(COMPTOIR_FR.page_kicker));
    assert.ok(text.includes(band === 'B1' ? COMPTOIR_FR.you_by_corrected : COMPTOIR_FR.you_by));
    assert.equal(page.proof, band === 'A1' ? 'clean' : band === 'A2' ? 'fixed' : 'corrected');
    // «avec toi» only when the learner's own words are printed: never for A1's tiles.
    assert.equal(/avec toi/.test(closed.closing.dispatch.bylineFr), band !== 'A1');
    assert.ok(text.includes(COMPTOIR_FR.page_intox));
    assert.ok(text.includes(page.questionFr));
    assert.ok(footButtons(html) <= 2);
  });
}

test('the clipping: three regulars and the learner, the bar, the intox, the words', () => {
  const page = types.parseComptoirPage({
    question_fr: 'Aligre ouvre six jours sur sept. Bonne idée ?',
    dateline_fr: "Le marché d'Aligre, un matin",
    standfirst_fr: 'Paris a 91 marchés.',
    quotes: [
      { cast_id: 'romy_tremblay', name_fr: 'Romy', role_fr: 'journaliste', stance: 'pour', quote_fr: 'Un marché, c’est la vraie vie.' },
      { cast_id: 'margaux_lefort', name_fr: 'Margaux', role_fr: 'Le Mistral', stance: 'nuance', quote_fr: 'Des légumes frais, bien.' },
      { cast_id: LIAR, name_fr: 'Gus', role_fr: 'consultant', stance: 'contre', quote_fr: 'Trop de foule, trop de bruit.' },
    ],
    mine: { cast_id: 'user', name_fr: 'Toi', role_fr: '', stance: 'nuance', quote_fr: 'Ça dépend : le marché est sympa.' },
    votes: { pour: 1, contre: 1, nuance: 2 },
    intox: { by: LIAR, name_fr: 'Gus', wrong_fr: 'sept jours sur sept', right_fr: 'six jours sur sept', source_name: 'Wikipédia' },
    phrase_fr: 'Je ne suis pas d’accord avec…',
    words: ['marchés', 'jours'],
  });
  const html = render(h(ComptoirClipping, { page, ccopy: comptoirCopy('en') }));
  const text = visibleText(html);
  assert.equal((html.match(/class="ct-quote"/g) || []).length, 4);
  assert.match(html, /data-me=""/, 'the learner\'s row');
  assert.ok(text.includes('Toi, au comptoir'));
  assert.match(html, /aria-label="The vote: 1 for, 2 it depends, 1 against"/);
  assert.ok(text.includes('Pour 1') && text.includes('Ça dépend 2') && text.includes('Contre 1'));
  assert.ok(text.includes("L'intox du jour. Gus : « sept jours sur sept » ? Non : six jours sur sept (Wikipédia)."));
  assert.equal((html.match(/<i data-stance=/g) || []).length, 3, 'three parts of the bar');
});

// ---------------------------------------------------------------------------
// 4. The Une card with the question of the day
// ---------------------------------------------------------------------------

test('the Une card: the question as the title, the three faces, «Au comptoir» as the press', async () => {
  const client = createMockRevueClient({ persist: false, comptoir: true, language: 'en' });
  const week = await client.week();
  const story = week.offer.recommended;
  assert.ok(story.questionFr, 'the switch on: the story has its question');
  assert.equal(story.cast.length, 3);
  const html = render(h(RvUneCard, { story, week: week.offer.week, state: 'offer', onOpen: () => {}, onOtherSubject: () => {}, copy: revueCopy('en') }));
  const text = visibleText(html);
  assert.ok(text.includes(COMPTOIR_FR.question_kicker));
  assert.ok(text.includes(story.questionFr));
  assert.ok(text.includes('Au comptoir'));
  assert.match(html, /aria-label="Romy, [^"]+ and Gus are already arguing"/);
  assert.equal((html.match(/data-tone="primary"/g) || []).length, 1, 'one red press');

  // The switch off: the chat's card, unchanged.
  const chat = createMockRevueClient({ persist: false, language: 'en' });
  const plain = (await chat.week()).offer.recommended;
  assert.equal(plain.questionFr, null);
  const before = visibleText(render(h(RvUneCard, { story: plain, week: week.offer.week, state: 'offer', onOpen: () => {}, onOtherSubject: () => {}, copy: revueCopy('en') })));
  assert.ok(!before.includes(COMPTOIR_FR.question_kicker));
  assert.ok(!before.includes('Au comptoir'));
});

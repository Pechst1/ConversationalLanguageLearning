// node --test components/revue/revue-render.test.js
//
// WP-119 phase 1 · the Revue's components, rendered.
//
//   1. RvThread renders every wire item kind (and the client's folded claims,
//      typing and resume rows), as an ordered list with speaker prefixes;
//   2. RvGlossText: `shown` prints the gloss under the first occurrence only,
//      `tap` makes every word a control, `none` is plain text;
//   3. RvColumn: no number, ever; the word only at bouclage / bouclé; the
//      screen-reader sentence;
//   4. RvHeadlineChoice shows the verdict and the anchor quote only after a pick;
//   5. RvEncounter replays a resume payload into the same thread as RvThread;
//   6. the contribution is underline + «toi», never colour alone;
//   7. RvUneCard: the four states, one red press (none once filed).

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { h, render, visibleText, fixture } = require('./revue-test-setup');

const types = require('../../lib/revue-types.ts');
const { createMockRevueClient } = require('../../lib/revue-mock.ts');
const { revueCopy } = require('./revue-copy.ts');
const model = require('./revue-model.ts');
const {
  RvThread,
  RvGlossText,
  RvColumn,
  RvHeadlineChoice,
  RvEncounter,
  RvUneCard,
  RvDispatch,
  RvQuestionDraft,
  RvMakePicker,
  RvSessionHead,
} = require('./index.ts');

const MOCK = fixture('mock-wire');
const FR = revueCopy('fr');
const EN = revueCopy('en');
const SUPPORT_TAP = { glosses: 'tap', translation: 'on_request', readingTargetWords: 90, vocabTarget: 5, level: 0 };
const SUPPORT_SHOWN = { ...SUPPORT_TAP, glosses: 'shown', translation: 'one_tap' };
const SUPPORT_NONE = { ...SUPPORT_TAP, glosses: 'none', translation: 'none' };
const at = '2026-10-01T09:00:00+02:00';

const source = { id: 's', name: 'Ville de Paris (paris.fr)', url: 'https://www.paris.fr/x', publishedAt: '2026-09-23' };
const ALL_KINDS = [
  { id: '1.n0', seq: 1, at, kind: 'narration', textFr: 'Un dimanche matin, au marché.' },
  { id: '1', seq: 1, at, kind: 'line', speaker: 'romy_tremblay', role: 'purpose', textFr: 'Tu m’aides ?', translation: 'Will you help me?', glosses: [] },
  { id: '1.s', seq: 1, at, kind: 'summary', speaker: 'romy_tremblay', textFr: 'Paris a 91 marchés.' },
  {
    id: '2', seq: 2, at, kind: 'claims', claims: [
      { id: 'c1', kind: 'fact', fr: 'Paris compte 91 marchés.', quote: 'les 91 marchés de Paris', attributedTo: null, source },
      { id: 'c4', kind: 'interpretation', fr: 'Les marchés sont des lieux de vie.', quote: 'des lieux de vie', attributedTo: 'la Ville de Paris', source },
    ],
  },
  { id: '3', seq: 3, at, kind: 'mine', textFr: 'Et les prix ?', mode: 'text' },
  { id: '4', seq: 4, at, kind: 'line', speaker: 'romy_tremblay', role: 'reply', textFr: "Et là, je n'ai rien.", translation: null, glosses: [] },
  { id: '4.u', seq: 4, at, kind: 'uncertainty', textFr: 'Les sources ne disent pas si les prix sont plus bas.' },
  { id: '5', seq: 5, at, kind: 'shift', reason: 'bouclage', angle: null },
  { id: '6', seq: 6, at, kind: 'made', made: { kind: 'reader_question', textFr: 'Est-ce que les prix sont plus bas ?', contribution: [[11, 33]], learnerFr: 'les prix sont plus bas' } },
];

test('RvThread renders every wire kind, in an ordered list with speaker prefixes', () => {
  const html = render(h(RvThread, { items: ALL_KINDS, support: SUPPORT_TAP, copy: FR, glossLanguage: 'de', now: new Date(at) }));
  assert.match(html, /^<ol class="av2-thread rv-thread"/);
  const kinds = [...html.matchAll(/data-kind="([a-zA-Z]+)"/g)].map((m) => m[1]);
  // The claims came before the learner spoke: they fold into one quiet line.
  assert.deepEqual(kinds, ['narration', 'line', 'summary', 'claimsFolded', 'mine', 'line', 'uncertainty', 'shift', 'made']);
  assert.match(visibleText(html), /2 faits sur la table · d’après Ville de Paris/);
  assert.match(html, /<span class="av2-sr">Toi : <\/span>Et les prix \?/);
  assert.match(html, /Romy<span class="av2-sr"> : <\/span>/);
  assert.match(html, /class="rv-unknown"[\s\S]*Les sources ne le disent pas/);
  assert.match(html, /class="rv-shift" role="status">Bouclage</);
  assert.match(html, /Écouter le résumé/);
  // The latest Romy line is the headline; the earlier one is the small past bubble.
  assert.equal((html.match(/av2-speech--past/g) || []).length, 1);
  assert.match(html, /class="av2-headline" lang="fr">[^<]*<?[\s\S]*?je n&#x27;ai rien/);
  // The made row: the learner's part is underline + «toi».
  assert.match(html, /<span class="rv-yours">les prix sont plus bas<sup>toi<\/sup><\/span>/);

  // Unfolded (before the learner speaks), each claim is a card: kind by label + shape + rule.
  const cards = render(h(RvThread, { items: ALL_KINDS.slice(0, 4), support: SUPPORT_TAP, copy: FR, now: new Date(at) }));
  assert.match(cards, /<article class="rv-claim" data-kind="fact">/);
  assert.match(cards, /<article class="rv-claim" data-kind="interpretation">/);
  assert.match(cards, /av2-shape--square[\s\S]*Fait/);
  assert.match(cards, /av2-shape--circle[\s\S]*Interprétation/);
  assert.match(cards, /d&#x27;après la Ville de Paris/);
  assert.match(cards, /<a href="https:\/\/www.paris.fr\/x" target="_blank" rel="noopener noreferrer" aria-label="D&#x27;après Ville de Paris, 23 sept., s&#x27;ouvre dans un nouvel onglet">/);
  assert.match(cards, /La citation/);
  // The translation sits behind «Traduire» when the line has one.
  assert.match(cards, /class="rv-chip" aria-pressed="false"/);

  // Client rows: the typing line, a pending learner line, the resume marker.
  const live = render(h(RvThread, {
    items: [{ ...ALL_KINDS[0], at: '2026-09-30T09:00:00+02:00' }, ...ALL_KINDS.slice(4, 6)],
    support: SUPPORT_TAP,
    copy: FR,
    typing: true,
    pendingMine: 'Et alors ?',
    resumeToday: model.localDay(at),
    resumeLabel: 'Hier · tu reprends ici',
  }));
  assert.match(live, /data-kind="resume"[\s\S]*Hier · tu reprends ici/);
  assert.match(live, /data-pending="">[\s\S]*Et alors \?/);
  assert.match(live, /Romy cherche dans ses notes/);
});

test('RvGlossText: shown prints the gloss once, tap makes every word a control, none is plain', () => {
  const glosses = [{ fr: 'marché couvert', gloss: 'Markthalle', claimId: 'c3' }];
  const text = 'Il y a un marché couvert. Le marché couvert est ouvert.';
  const shown = render(h('p', null, h(RvGlossText, { text, glosses, mode: 'shown', glossLanguage: 'de' })));
  assert.equal((shown.match(/<ruby class="rv-gloss">/g) || []).length, 1, 'the first occurrence only');
  assert.match(shown, /<span class="rv-target">marché couvert<\/span><rt lang="de">Markthalle<\/rt>/);
  assert.doesNotMatch(shown, /<button/);

  const tap = render(h('p', null, h(RvGlossText, { text, glosses, mode: 'tap', onWord: () => {} })));
  const buttons = tap.match(/<button type="button" class="rv-word"/g) || [];
  assert.equal(buttons.length, 9, 'every word');
  assert.equal((tap.match(/data-target=""/g) || []).length, 2, 'the target words carry their gloss');
  assert.doesNotMatch(tap, /<ruby/);

  const none = render(h('p', null, h(RvGlossText, { text, glosses, mode: 'none', onWord: () => {} })));
  assert.equal(none, `<p>${text}</p>`);
  // Tap without a word handler is plain text (nothing to open).
  assert.doesNotMatch(render(h('p', null, h(RvGlossText, { text, glosses, mode: 'tap' }))), /<button/);

  const segments = model.glossSegments('Le marché, le Marché.', [{ fr: 'marché', gloss: 'market', claimId: 'c1' }], 'shown');
  assert.deepEqual(segments.map((s) => s.kind), ['text', 'gloss', 'text']);
});

test('RvColumn: seven lines, no number, the word only at bouclage and bouclé', () => {
  const html = (room) => render(h(RvColumn, { room, copy: FR }));
  const open = html({ used: 3, phase: 'open', remainingTurns: 4 });
  assert.equal((open.match(/<i data-used=""/g) || []).length, 3);
  assert.equal((open.match(/<i/g) || []).length, 7);
  assert.match(open, /aria-label="La colonne : De la place pour environ quatre échanges."/);
  assert.doesNotMatch(visibleText(open), /\d/);
  assert.doesNotMatch(open, /Bouclage|Bouclé/);

  const bouclage = html({ used: 6, phase: 'bouclage', remainingTurns: 1 });
  assert.match(bouclage, /data-phase="bouclage"/);
  assert.match(bouclage, /<i data-used="" data-last=""><\/i>/);
  assert.match(visibleText(bouclage), /^Bouclage$/);
  assert.match(bouclage, /environ un échanges|environ un/);

  const boucle = html({ used: 7, phase: 'boucle', remainingTurns: 0 });
  assert.match(visibleText(boucle), /^Bouclé$/);
  assert.match(boucle, /aria-label="La colonne : La colonne est pleine."/);
  assert.match(render(h(RvColumn, { room: { used: 2, phase: 'open', remainingTurns: 5 }, copy: EN })), /Room for about five exchanges/);

  const head = render(h(RvSessionHead, { beat: 'pursue', room: { used: 2, phase: 'open', remainingTurns: 5 }, onExit: () => {}, copy: FR }));
  assert.match(head, /aria-label="Quitter la Revue — Romy garde tes notes"/);
  assert.deepEqual([...head.matchAll(/data-beat="(\w+)" data-state="(\w+)"/g)].map((m) => `${m[1]}:${m[2]}`), [
    'arrive:done', 'facts:done', 'pursue:active', 'make:pending', 'close:pending',
  ]);
});

test('RvHeadlineChoice shows the verdict and the anchor quote only after the pick', () => {
  const pick = types.parseMakeResult(MOCK.make_pick);
  const options = MOCK.make_offer.options[0].options.map((o) => ({ id: o.id, textFr: o.text_fr }));
  const before = render(h(RvHeadlineChoice, { options, result: null, picked: null, onPick: () => {}, copy: FR }));
  assert.doesNotMatch(before, /data-evidence/);
  assert.doesNotMatch(before, /av2-feedback/);
  assert.equal((before.match(/role="radio"/g) || []).length, 3);

  const greve = [
    { id: 'h1', textFr: 'Grève : un préavis de cinq jours au moins' },
    { id: 'h2', textFr: 'Grève : aucun préavis' },
    { id: 'h3', textFr: 'Grève : un vrai service minimum' },
  ];
  const after = render(h(RvHeadlineChoice, { options: greve, result: pick, picked: 'h2', onPick: () => {}, copy: FR }));
  assert.match(after, /data-evidence=""/);
  assert.ok(visibleText(after).includes(pick.evidence.quote.slice(0, 30)), 'the quote is cited');
  assert.match(visibleText(after), /D'après Ministère de la Transition écologique, 25 mai 2018/);
  assert.match(after, new RegExp(`data-state="correct"[^>]*>[\\s\\S]*?${pick.made.textFr.slice(0, 10)}`));
  assert.match(after, /data-state="wrong"/, 'the wrong pick is marked, with its word');
  assert.match(after, /à revoir/);
  assert.match(after, /Pas celui-là/);
});

test('RvEncounter replays a resume payload into the same thread', async () => {
  const session = types.parseSessionView(MOCK.session_resume);
  const client = createMockRevueClient({ persist: false });
  const encounter = render(h(RvEncounter, { client, session, language: 'de', onExit: () => {}, now: new Date(at) }));
  const thread = render(h(RvThread, {
    items: session.thread,
    support: session.plan.support,
    copy: revueCopy('de'),
    vocabulary: session.plan.vocabulary,
    band: session.plan.band,
    glossLanguage: session.plan.glossLanguage,
    onWord: () => {},
    resumeToday: model.localDay(at),
    now: new Date(at),
  }));
  const ol = (html) => {
    const start = html.indexOf('<ol class="av2-thread rv-thread"');
    return html.slice(start, html.indexOf('</ol>', start) + 5);
  };
  assert.ok(ol(encounter).length > 200);
  assert.equal(ol(encounter), ol(thread), 'the encounter shows exactly the replayed thread');
  // Same ids, same order as the server sent them.
  const ids = session.thread.map((item) => item.id);
  assert.deepEqual(ids, MOCK.session_resume.thread.map((item) => item.id));
  // The learner has spoken: the band, not the full plate; the head is on `pursue`.
  assert.match(encounter, /class="rv-stage" data-size="band"/);
  assert.match(encounter, /data-beat="pursue" data-state="active"/);
  // Toi wears the plan's dress on the Revue stage, in the waist crop.
  assert.match(encounter, /cast-stage__figure--you" data-outfit="apron" data-crop="half"/);
  // Started on an earlier day, resumed today: the marker sits where today begins.
  const tomorrow = render(h(RvEncounter, { client, session, language: 'fr', onExit: () => {}, now: new Date('2026-10-02T10:00:00+02:00') }));
  assert.doesNotMatch(tomorrow, /tu reprends ici/, 'every item is from one earlier day: nothing to mark before it');
});

test('the arrive screen: full plate, one red press that is the learner\'s French', () => {
  const session = types.parseSessionView(MOCK.session_arrive);
  const html = render(h(RvEncounter, { client: createMockRevueClient({ persist: false }), session, language: 'en', onExit: () => {}, now: new Date(at) }));
  assert.match(html, /class="rv-stage" data-size="full"/);
  assert.equal((html.match(/av2-btn--primary/g) || []).length, 1);
  assert.match(html, /av2-btn--primary[^>]*lang="fr"|lang="fr"[^>]*av2-btn--primary/);
  assert.match(visibleText(html), /D'accord, je t'aide\./);
  assert.match(visibleText(html), /Answer another way/);
  assert.match(visibleText(html), /Not news · a seasonal classic/);
  assert.match(html, /data-role="place_note"/);
});

test('the close: dispatch with the learner\'s part, «Pour ton Relevé», the ink press', () => {
  const close = types.parseCloseResult(MOCK.close);
  const live = render(h(RvEncounter, {
    client: createMockRevueClient({ persist: false }),
    session: { ...types.parseSessionView(MOCK.session_resume), closing: close.closing },
    language: 'fr',
    onExit: () => {},
    onReleve: () => {},
    now: new Date(at),
  }));
  assert.match(live, /data-dispatch=""/);
  assert.match(live, /<span class="rv-yours">[^<]*prix[^<]*<sup>toi<\/sup>/);
  assert.match(visibleText(live), /Pour ton Relevé 5 mots · 2 faits/);
  assert.match(live, /av2-btn--done[\s\S]*Classer la Revue/);
  assert.equal((live.match(/av2-btn--primary/g) || []).length, 0, 'nothing is left to do: no red press');
  assert.match(visibleText(live), /La suite la semaine prochaine\./);

  // Opened again after the close: read-only, back arrow, the dispatch, «Relire».
  const ended = render(h(RvEncounter, { client: createMockRevueClient({ persist: false }), session: close.session, language: 'fr', onExit: () => {}, now: new Date(at) }));
  assert.match(ended, /aria-label="Retour à La Une"/);
  assert.match(visibleText(ended), /Revue bouclée le 1 oct\./);
  assert.match(visibleText(ended), /Relire la conversation/);
  assert.doesNotMatch(ended, /class="av2-thread rv-thread"/, 'the conversation is folded away until asked');
  assert.doesNotMatch(ended, /rv-foot/);
});

test('the make step pieces: picker with Romy\'s mark, the draft with the learner\'s words', () => {
  const picker = render(h(RvMakePicker, {
    options: [
      { id: 'reader_question', titleFr: FR.make_options.reader_question.title, detail: FR.make_options.reader_question.detail },
      { id: 'headline_choice', titleFr: FR.make_options.headline_choice.title, detail: FR.make_options.headline_choice.detail },
    ],
    recommended: 'reader_question',
    value: 'reader_question',
    onChange: () => {},
    copy: FR,
  }));
  assert.equal((picker.match(/Ce que Romy te propose/g) || []).length, 1);
  assert.match(picker, /aria-checked="true"[^>]*data-state="selected" data-make="reader_question"/);
  assert.doesNotMatch(picker, /aria-disabled/, 'an unavailable option is absent, never greyed');

  const draft = types.parseMakeResult(MOCK.make_propose).draft;
  const html = render(h(RvQuestionDraft, { ...draft, glossLanguage: 'de', onSend: () => {}, copy: revueCopy('de') }));
  assert.match(visibleText(html), /Deine Version/);
  assert.match(html, /<span class="rv-yours">les prix sont plus bas qu&#x27;au supermarché<sup>du<\/sup><\/span>/);
  assert.match(html, /<p class="rv-draft__why" lang="de">/);
  assert.equal((html.match(/av2-btn--primary/g) || []).length, 1);
});

test('RvDispatch marks the learner\'s part with a word, not only a colour', () => {
  const dispatch = types.parseDispatch(MOCK.close.closing.dispatch);
  const html = render(h(RvDispatch, { ...dispatch, copy: EN }));
  assert.match(html, /<sup>you<\/sup>/);
  assert.match(html, /Le Papier de Romy · semaine 40/);
  assert.match(html, /Romy Tremblay, avec toi/);
});

test('model: folding, applyTurn dedupe, open question, contribution segments', () => {
  const rows = model.displayThread(ALL_KINDS);
  assert.equal(rows.filter((row) => row.kind === 'claimsFolded').length, 1);
  const reopened = model.displayThread(ALL_KINDS, { opened: new Set(['2']) });
  assert.equal(reopened.filter((row) => row.kind === 'claimsFolded').length, 0);

  const session = types.parseSessionView(MOCK.session_arrive);
  const turn = types.parseTurnResult(MOCK.turn_facts);
  const once = model.applyTurn(session, turn);
  const twice = model.applyTurn(once, turn);
  assert.equal(twice.thread.length, once.thread.length, 'a retried turn adds nothing');
  assert.equal(once.beat, 'facts');
  assert.equal(model.openQuestion(ALL_KINDS), 'Et les prix ?');

  assert.deepEqual(model.contributionSegments('abcdef', [[4, 9], [1, 2], [1, 3]]), [
    { text: 'a', mine: false },
    { text: 'bc', mine: true },
    { text: 'd', mine: false },
    { text: 'ef', mine: true },
  ]);
  assert.equal(model.sourceDate('2018-05-25', new Date(at)), '25 mai 2018');
  assert.equal(model.sourceDate('2026-09-23', new Date(at)), '23 sept.');
});

test('RvUneCard: offer, evergreen, resume and filed; one red press until filed', () => {
  const offer = types.parseOffer(MOCK.offer);
  const story = offer.recommended;
  const card = (state, extra = {}) =>
    render(h(RvUneCard, { story, week: offer.week, state, onOpen: () => {}, onOtherSubject: () => {}, copy: FR, ...extra }));
  const offerHtml = card('offer');
  // An evergreen story is labelled honestly even when asked for as an offer.
  assert.match(visibleText(offerHtml), /Le Papier · hors actualité/);
  assert.match(visibleText(offerHtml), /Autre sujet \?/);
  assert.match(visibleText(offerHtml), /Rejoindre Romy/);
  assert.equal((offerHtml.match(/av2-btn--primary/g) || []).length, 1);
  assert.match(offerHtml, /data-size="une"/);
  assert.doesNotMatch(offerHtml, /cast-stage__figure--you/, 'La Une shows Romy alone');

  const resume = card('resume', { resumeLine: 'Commencée hier · ta question attend.' });
  assert.match(visibleText(resume), /Reprendre avec Romy/);
  assert.match(visibleText(resume), /Commencée hier · ta question attend\./);
  assert.doesNotMatch(visibleText(resume), /Autre sujet/);

  const filedOffer = types.parseOffer(MOCK.offer_filed);
  const filed = card('filed', { filed: { made: filedOffer.filed.made } });
  assert.equal((filed.match(/av2-btn/g) || []).length, 0, 'no press once filed');
  assert.match(visibleText(filed), /Revue bouclée/, 'the week leaves the kicker when the headline is long (WP-81 budget)');
  const short = card('filed', { filed: { made: { ...filedOffer.filed.made, textFr: 'Les prix au marché', contribution: [[4, 18]] } } });
  assert.match(visibleText(short), /Revue bouclée · semaine 40/);
  assert.match(filed, /<sup>toi<\/sup>/);
  assert.match(visibleText(filed), /La suite la semaine prochaine\./);
});

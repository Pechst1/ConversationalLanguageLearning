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
//   7. RvUneCard: the four states, one red press (none once filed);
//   8. WP-119 §8.4: RvPicture printed like a press photograph (frame, caption on
//      its rule, «Illustration · Le Papier»), «La légende» chosen or written
//      (RvCaption), the dispatch's picture, Romy's «Regarde» on the arrive screen.
//   9. 2026-10-19 (the Papier walk): every word tappable at every band, the
//      Papier's own glosses handed to the word sheet, «Traduire» fetched once per
//      text, «Écrire le papier →» once the learner has spoken, the band out of the
//      pinned top, the close line printed once and the two links on one row.

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
  // A2: the claims wait behind one «Sources» fold under the lead.
  assert.deepEqual(kinds, ['narration', 'line', 'summary', 'sources', 'mine', 'line', 'uncertainty', 'shift', 'made']);
  assert.match(visibleText(html), /Sources · 2 faits/);
  // B1: the claims came before the learner spoke: they fold into one quiet line.
  const b1 = render(h(RvThread, { items: ALL_KINDS, support: SUPPORT_TAP, copy: FR, band: 'B1', glossLanguage: 'de', now: new Date(at) }));
  assert.deepEqual([...b1.matchAll(/data-kind="([a-zA-Z]+)"/g)].map((m) => m[1]), ['narration', 'line', 'summary', 'claimsFolded', 'mine', 'line', 'uncertainty', 'shift', 'made']);
  assert.match(visibleText(b1), /2 faits sur la table · d’après Ville de Paris/);
  assert.match(html, /<span class="av2-sr">Toi : <\/span>Et les prix \?/);
  assert.match(html, /Romy<span class="av2-sr"> : <\/span>/);
  assert.match(html, /class="rv-unknown"[\s\S]*Les sources ne le disent pas/);
  assert.match(html, /class="rv-shift" role="status">Bouclage</);
  // The lead is text from the start, under its kicker (it used to hide behind the play button).
  assert.match(html, /<section class="rv-lead" aria-label="Ce qui s&#x27;est passé"><p class="rv-lead__k">Ce qui s&#x27;est passé<\/p><p class="rv-lead__fr" lang="fr">Paris a 91 marchés\.<\/p>/);
  // The latest Romy line is the headline; the earlier one is the small past bubble.
  assert.equal((html.match(/av2-speech--past/g) || []).length, 1);
  assert.match(html, /class="av2-headline" lang="fr">[^<]*<?[\s\S]*?je n&#x27;ai rien/);
  // The made row: the learner's part is underline + «toi».
  assert.match(html, /<span class="rv-yours">les prix sont plus bas<sup>toi<\/sup><\/span>/);

  // Unfolded (before the learner speaks), each claim is a card: kind by label + shape + rule.
  const cards = render(h(RvThread, { items: ALL_KINDS.slice(0, 4), support: SUPPORT_TAP, copy: FR, band: 'B1', now: new Date(at) }));
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

  // 2026-10-19: with a word handler every word opens the sheet at every band.
  const none = render(h('p', null, h(RvGlossText, { text, glosses, mode: 'none', onWord: () => {} })));
  assert.equal((none.match(/<button type="button" class="rv-word"/g) || []).length, 9, 'B2: every word');
  assert.doesNotMatch(none, /data-target|<ruby/, 'B2: the targets are not marked on the page');
  assert.equal(render(h('p', null, h(RvGlossText, { text, glosses, mode: 'none' }))), `<p>${text}</p>`, 'no handler: plain');
  // A1: the printed gloss stays under the first target, which is a control too; so is every other word.
  const shownTap = render(h('p', null, h(RvGlossText, { text, glosses, mode: 'shown', glossLanguage: 'de', onWord: () => {} })));
  assert.equal((shownTap.match(/<ruby class="rv-gloss">/g) || []).length, 1);
  assert.match(shownTap, /<ruby class="rv-gloss"><button type="button" class="rv-word" data-target=""><span class="rv-target">marché couvert<\/span><\/button><rt lang="de">Markthalle<\/rt><\/ruby>/);
  assert.equal((shownTap.match(/<button type="button" class="rv-word"/g) || []).length, 9, 'A1: every word');
  // Tap without a word handler is plain text (nothing to open).
  assert.doesNotMatch(render(h('p', null, h(RvGlossText, { text, glosses, mode: 'tap' }))), /<button/);

  const segments = model.glossSegments('Le marché, le Marché.', [{ fr: 'marché', gloss: 'market', claimId: 'c1' }], 'shown');
  assert.deepEqual(segments.map((s) => s.kind), ['text', 'gloss', 'text']);
  const tapped = model.glossSegments('Le marché, le Marché.', [{ fr: 'marché', gloss: 'market', claimId: 'c1' }], 'shown', true);
  assert.deepEqual(tapped.filter((s) => s.kind !== 'text').map((s) => [s.kind, s.text, s.gloss]), [
    ['word', 'Le', null], ['gloss', 'marché', 'market'], ['word', 'le', null], ['word', 'Marché', 'market'],
  ], 'the repeated target carries its gloss to the sheet');
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

  const head = render(h(RvSessionHead, { beat: 'pursue', onExit: () => {}, copy: FR }));
  assert.match(head, /aria-label="Quitter le Papier — Romy garde tes notes"/);
  assert.doesNotMatch(head, /rv-col/, '2026-10-19: the column is no longer drawn in the head');
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
  assert.match(encounter, /cast-stage__figure--you" data-outfit="coat" data-crop="half"/);
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
  assert.match(live, /av2-btn--done[\s\S]*Classer le Papier/);
  assert.equal((live.match(/av2-btn--primary/g) || []).length, 0, 'nothing is left to do: no red press');
  assert.match(visibleText(live), /La suite la semaine prochaine\./);

  // Opened again after the close: read-only, back arrow, the dispatch, «Relire».
  const ended = render(h(RvEncounter, { client: createMockRevueClient({ persist: false }), session: close.session, language: 'fr', onExit: () => {}, now: new Date(at) }));
  assert.match(ended, /aria-label="Retour à La Une"/);
  assert.match(visibleText(ended), /Papier bouclé le 1 oct\./);
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
  // A line of the learner's own (not a chip) opens «Écrire le papier» without a reload (2026-10-23).
  assert.equal(model.applyTurn({ ...session, ownLine: false }, { ...turn, ownLine: true }).ownLine, true);
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
  assert.match(visibleText(filed), /Papier bouclé/, 'the week leaves the kicker when the headline is long (WP-81 budget)');
  const short = card('filed', { filed: { made: { ...filedOffer.filed.made, textFr: 'Les prix au marché', contribution: [[4, 18]] } } });
  assert.match(visibleText(short), /Papier bouclé · semaine 40/);
  assert.match(filed, /<sup>toi<\/sup>/);
  assert.match(visibleText(filed), /La suite la semaine prochaine\./);
});

// ---------------------------------------------------------------------------
// Phase 2 · «Les invités» (WIRE §6), the vignette at the close (WP-120), read-only replay
// ---------------------------------------------------------------------------

const B1 = revueCopy('fr');
const guest = (id, move, position, textFr, reasonFr = null, reason = null) => ({
  id, seq: Number(id), at, kind: 'guest', castId: 'margaux_barman', textFr, move, position, reasonFr, reason, glosses: [],
});

test('a guest in the thread: the entrance with her reason, her own bubble, the move shown quietly', () => {
  const items = [
    ALL_KINDS[4],
    { ...ALL_KINDS[5], id: '4', seq: 4 },
    guest('5', 'enter', 'against', "Les prix ? Ce n'est pas toujours moins cher.", 'Elle achète les citrons du bar ici, chaque dimanche.'),
    { id: '6', seq: 6, at, kind: 'mine', textFr: 'Mais les produits sont plus frais ?', mode: 'text' },
    guest('7', 'disagree', 'against', "Je ne suis pas d'accord."),
    { id: '8', seq: 8, at, kind: 'mine', textFr: 'Les producteurs vendent eux-mêmes.', mode: 'text' },
    guest('9', 'moved', 'moved', "Bon. Vu comme ça, tu n'as pas tort."),
  ];
  const html = render(h(RvThread, { items, support: SUPPORT_TAP, copy: FR, now: new Date(at) }));
  const kinds = [...html.matchAll(/<li class="av2-thread__line" data-kind="([a-z]+)"/g)].map((m) => m[1]);
  assert.deepEqual(kinds, ['mine', 'line', 'guest', 'mine', 'guest', 'mine', 'guest']);
  // The entrance: «Margaux arrive.» (chrome) + her reason (French), in her accent.
  assert.match(html, /<p class="rv-entrance" data-char="margaux_barman" role="status"><b>Margaux arrive\.<\/b> <span lang="fr">Elle achète les citrons du bar ici, chaque dimanche\.<\/span><\/p>/);
  assert.equal((html.match(/rv-entrance/g) || []).length, 1, 'one entrance');
  // Her own bubble: her face, her name, a quiet tag — never a claim card.
  assert.match(html, /class="av2-speech rv-guest av2-speech--past" data-mood="neutral" data-char="margaux_barman" data-move="enter"/);
  assert.match(visibleText(html), /Margaux · témoignage/);
  assert.match(visibleText(html), /Margaux · pas d’accord/);
  assert.doesNotMatch(html, /rv-claim/);
  // Her change of mind: a hairline marker in the control language.
  assert.match(html, /data-kind="guest" data-move="moved"[\s\S]*<p class="rv-shift" role="status">Margaux a changé d’avis<\/p>/);
  // Whoever spoke last is the screen's headline: her latest line is not «past».
  assert.match(html, /data-move="moved"><span class="av2-speech__face"[\s\S]*?class="av2-headline" lang="fr"/);
  assert.equal((html.match(/av2-speech--past/g) || []).length, 3, 'Romy\'s reply and Margaux\'s two earlier lines');
  assert.match(render(h(RvThread, { items, support: SUPPORT_TAP, copy: EN })), /Margaux joins\./);
  assert.match(render(h(RvThread, { items, support: SUPPORT_TAP, copy: revueCopy('de') })), /Margaux hat die Meinung geändert/);
});

test('fallback reasons: model_down gets the quiet notice once a turn, the others look like any line', () => {
  const romy = (id, reason) => ({ id, seq: Number(id), at, kind: 'line', speaker: 'romy_tremblay', role: 'fallback', textFr: 'Je ne sais pas encore. On regarde ce que disent les sources ?', translation: null, glosses: [], reason });
  const down = render(h(RvThread, {
    items: [ALL_KINDS[4], romy('5', 'model_down'), guest('6', 'follow_up', 'against', 'Je repasse plus tard.', null, 'model_down')],
    support: SUPPORT_TAP,
    copy: FR,
  }));
  assert.match(down, /data-role="fallback" data-reason="model_down"/);
  assert.equal((down.match(/La conversation ne répond pas pour le moment/g) || []).length, 1, 'one notice for the turn');
  assert.match(down, /data-kind="guest" data-move="follow_up" data-reason="model_down"/);
  assert.match(visibleText(down), /Margaux · une question/);
  const guestDown = render(h(RvThread, { items: [ALL_KINDS[4], guest('6', 'follow_up', 'against', 'Je repasse plus tard.', null, 'model_down')], support: SUPPORT_TAP, copy: FR }));
  assert.match(guestDown, /La conversation ne répond pas pour le moment/, 'a guest\'s stand-in line alone gets it too');

  for (const reason of ['knowledge_refused', 'budget', 'no_match']) {
    const html = render(h(RvThread, { items: [ALL_KINDS[4], romy('5', reason)], support: SUPPORT_TAP, copy: FR }));
    assert.match(html, new RegExp(`data-reason="${reason}"`));
    assert.doesNotMatch(html, /av2-notice/, `${reason}: a normal-looking line`);
  }
  // budget: the column reads «Bouclé» even if the room has not caught up.
  assert.deepEqual(model.shownRoom({ used: 5, phase: 'bouclage', remainingTurns: 1 }, [ALL_KINDS[4], romy('5', 'budget')]), { used: 7, phase: 'boucle', remainingTurns: 0 });
  assert.equal(model.shownRoom({ used: 5, phase: 'open', remainingTurns: 1 }, [romy('5', 'model_down')]).phase, 'open');
});

test('the register note is worded under the learner\'s line (vous → tu)', () => {
  const html = render(h(RvThread, { items: [ALL_KINDS[4]], support: SUPPORT_TAP, copy: revueCopy('de'), registerNotes: { '3': 'vous_to_tu' } }));
  assert.match(html, /data-kind="mine"[\s\S]*data-kind="register"/);
  assert.match(html, /data-state="register">Das Register</);
  assert.match(html, /lang="fr">Avec Romy, on se tutoie\.</);
  assert.match(visibleText(html), /Romy duzt dich/);
});

test('the guest on stage: beside Romy from her entrance, sliding in, in front when she speaks', () => {
  const session = types.parseSessionView(MOCK.session_b1_guest);
  // The resume payload already lists her; a turn result does not carry a stage, so the thread adds her.
  const wireCast = [{ id: 'romy_tremblay', hold: 'notebook' }, { id: 'user', hold: null }];
  assert.deepEqual(model.castWithGuests(wireCast, session.thread).map((m) => m.id), ['romy_tremblay', 'margaux_barman', 'user']);
  assert.deepEqual(model.castWithGuests(session.stage.cast, session.thread), session.stage.cast, 'never twice');
  assert.equal(model.enteringGuest(types.parseTurnResult(MOCK.turn_guest_enter).items), 'margaux_barman');
  const html = render(h(RvEncounter, { client: createMockRevueClient({ persist: false }), session, language: 'fr', onExit: () => {}, now: new Date(at) }));
  assert.match(html, /data-cast-stage="romy_tremblay margaux_barman"/);
  assert.equal(model.lastSpeaker(session.thread), 'romy_tremblay', 'the model-down turn ends on Romy');
  const { stageCast } = require('./index.ts');
  assert.deepEqual(stageCast(session.stage.cast, 'margaux_barman').map((m) => [m.id, m.speaking]), [['romy_tremblay', false], ['margaux_barman', true]]);
});

test('make: Romy\'s intro is a line of the thread; headline_write shows the count and the fact fit; short_report records or falls back to text', () => {
  const offer = types.parseMakeOffer(MOCK.make_offer_b1);
  const session = model.appendItems(types.parseSessionView(MOCK.session_b1_guest), [offer.intro]);
  const html = render(h(RvThread, { items: session.thread, support: session.plan.support, copy: B1 }));
  // The learner left a question the sources cannot answer: Romy's intro offers the reader question.
  assert.equal(offer.recommended, 'reader_question');
  assert.match(html, /data-role="make_intro"[\s\S]*Ta question, on la pose aux lecteurs \?/);

  const { RvHeadlineWrite, RvShortReport, RvMadeCard } = require('./index.ts');
  const before = render(h(RvHeadlineWrite, { maxWords: 14, result: null, onSend: () => {}, copy: B1 }));
  assert.match(before, /<span class="av2-field__label">Ton titre<\/span>/);
  assert.match(visibleText(before), /0 mots sur 14 au plus/);
  assert.equal((before.match(/av2-btn--primary/g) || []).length, 1);
  assert.doesNotMatch(before, /av2-feedback/);

  const rejected = types.parseMakeResult(MOCK.make_write_rejected);
  const wrong = render(h(RvHeadlineWrite, { maxWords: 14, result: rejected, onSend: () => {}, copy: B1 }));
  assert.match(wrong, /data-tone="wrong"/);
  assert.match(visibleText(wrong), /Les sources disent autre chose\. Réécris-le\./);
  assert.match(wrong, /av2-btn--primary/, 'write again');

  const accepted = types.parseMakeResult(MOCK.make_write);
  const right = render(h(RvHeadlineWrite, { maxWords: 14, result: accepted, onSend: () => {}, copy: B1 }));
  assert.match(right, /data-tone="correct"/);
  assert.match(visibleText(right), /Les sources le disent\./);
  assert.match(visibleText(right), /Bien employé : en plein air/);
  assert.doesNotMatch(right, /av2-btn--primary/, 'filed: the foot\'s «Continuer» is the one press');
  assert.match(right, /<textarea[^>]*disabled=""[^>]*>Paris et ses 91 marchés en plein air<\/textarea>/);
  assert.match(visibleText(right), /8 mots sur 14 au plus/);

  const mic = render(h(RvShortReport, { seconds: 30, onSend: () => {}, copy: B1, voice: true }));
  assert.match(mic, /data-mode="idle"/);
  assert.match(visibleText(mic), /Enregistrer · 30 s/);
  assert.equal((mic.match(/av2-btn--primary/g) || []).length, 1);
  const noMic = render(h(RvShortReport, { seconds: 30, onSend: () => {}, copy: EN, voice: false }));
  assert.match(noMic, /data-mode="text"/);
  assert.match(visibleText(noMic), /No microphone here: write your report\./);
  assert.match(noMic, /<span class="av2-field__label">Your report, in writing<\/span>/);

  const report = types.parseMakeResult(MOCK.make_report);
  assert.match(visibleText(render(h(RvMadeCard, { made: report.made, copy: B1 }))), /^Ton reportage Je suis au marché/);
  for (const language of ['fr', 'en', 'de']) {
    const copy = revueCopy(language);
    for (const kind of ['headline_choice', 'headline_write', 'reader_question', 'short_report']) {
      assert.ok(copy.make_options[kind].title && copy.make_options[kind].detail, `${language} ${kind}`);
    }
  }
});

test('the close stamps the vignette before «Classer»; no vignette, no stamp; the kept words wear the rubric', () => {
  const close = types.parseCloseResult(MOCK.close_b1_write);
  const resume = types.parseSessionView(MOCK.session_b1_guest);
  const live = render(h(RvEncounter, {
    client: createMockRevueClient({ persist: false }),
    session: { ...resume, closing: close.closing },
    language: 'fr',
    onExit: () => {},
    now: new Date(at),
  }));
  assert.match(live, /data-kind="vignette"[\s\S]*class="rv-vignette rv-vignette--large rv-vignette--stamping" data-ring="headline" data-size="large" data-kept=""/);
  assert.match(visibleText(live), /Ta vignette · Semaine 40/);
  const order = ['data-dispatch=""', 'data-kind="kept"', 'data-kind="vignette"', 'data-kind="colophon"', 'Classer le Papier'].map((needle) => live.indexOf(needle));
  assert.deepEqual(order.slice().sort((a, b) => a - b), order, 'dispatch, kept, the stamp, the colophon, then the press');
  assert.ok(order.every((index) => index >= 0));

  const bare = render(h(RvEncounter, {
    client: createMockRevueClient({ persist: false }),
    session: { ...resume, closing: { ...close.closing, vignette: null } },
    language: 'fr',
    onExit: () => {},
    now: new Date(at),
  }));
  assert.doesNotMatch(bare, /rv-vignette/);
  assert.match(bare, /Classer le Papier/);

  // Reopened after the close: the stamp is there, already pressed.
  const ended = render(h(RvEncounter, { client: createMockRevueClient({ persist: false }), session: close.session, language: 'fr', onExit: () => {}, now: new Date(at) }));
  assert.match(ended, /class="rv-vignette rv-vignette--large" data-ring="headline"/);

  const { RvKept } = require('./index.ts');
  const kept = render(h(RvKept, {
    words: close.closing.kept.words,
    claims: [],
    copy: FR,
    outcomes: model.mergeWordOutcomes({}, types.parseMakeResult(MOCK.make_write).evidence),
  }));
  assert.match(kept, /data-outcome="correct"><span class="av2-word-token av2-word-token--sm"[^>]*data-tone="known"[\s\S]*?en plein air<span class="rv-kept__right">bien employé<\/span>/);
  assert.equal((kept.match(/data-outcome="correct"/g) || []).length, 1);
  // Correct wins over a later unscored use; unscored never marks.
  const merged = model.mergeWordOutcomes(model.mergeWordOutcomes({}, { words: [{ fr: 'Matins', outcome: 'correct', capabilityKnown: true }] }), { words: [{ fr: 'matins', outcome: 'unscored', capabilityKnown: true }] });
  assert.equal(model.wordOutcome(merged, 'matins'), 'correct');
});

test('read-only replay (La Carte\'s «Relire»): the thread, no composer, no press', () => {
  const session = types.parseSessionView(MOCK.session_b1_guest);
  const html = render(h(RvEncounter, { client: createMockRevueClient({ persist: false }), session, language: 'fr', onExit: () => {}, readOnly: true, now: new Date(at) }));
  assert.match(html, /data-readonly=""/);
  assert.match(html, /class="av2-thread rv-thread"/);
  assert.match(html, /data-kind="guest" data-move="enter"/);
  assert.doesNotMatch(html, /rv-foot|rv-composer|av2-btn--primary|<textarea/);
  assert.match(html, /aria-label="Retour à La Une"/, 'the back arrow, not the ×');

  const closed = types.parseCloseResult(MOCK.close).session;
  const replay = render(h(RvEncounter, { client: createMockRevueClient({ persist: false }), session: closed, language: 'fr', onExit: () => {}, readOnly: true, now: new Date(at) }));
  assert.match(replay, /data-dispatch=""/);
  assert.match(replay, /class="av2-thread rv-thread"/, 'the conversation is open, not folded away');
  assert.doesNotMatch(replay, /Relire la conversation/);
  assert.doesNotMatch(replay, /rv-foot/);
});

test('a read-only replay of an active session keeps its real beat bar; only the icon is the back arrow', () => {
  const room = { used: 2, phase: 'open', remainingTurns: 5 };
  const back = render(h(RvSessionHead, { beat: 'pursue', room, onExit: () => {}, back: true, copy: FR }));
  assert.match(back, /aria-label="Retour à La Une"/);
  assert.deepEqual([...back.matchAll(/data-beat="(\w+)" data-state="(\w+)"/g)].map((m) => `${m[1]}:${m[2]}`), [
    'arrive:done', 'facts:done', 'pursue:active', 'make:pending', 'close:pending',
  ]);
  // `ended` still fills every beat and implies the arrow.
  const ended = render(h(RvSessionHead, { beat: 'close', room, onExit: () => {}, ended: true, copy: FR }));
  assert.match(ended, /aria-label="Retour à La Une"/);
  assert.ok(!/data-state="pending"/.test(ended));

  const session = types.parseSessionView(MOCK.session_b1_guest);
  assert.equal(session.status, 'active');
  const html = render(h(RvEncounter, { client: createMockRevueClient({ persist: false }), session, language: 'fr', onExit: () => {}, readOnly: true, now: new Date(at) }));
  assert.match(html, /aria-label="Retour à La Une"/);
  assert.match(html, /data-state="pending"/, 'the beats still to come are not filled on a replay');
  const source = require('node:fs').readFileSync(require('node:path').join(__dirname, 'RvEncounter.tsx'), 'utf8');
  assert.match(source, /ended=\{ended\} back=\{ended \|\| readOnly\}/);
  assert.doesNotMatch(source, /Classer la Revue/);
});

test('replayable evidence: the kept words wear their stored outcome and the line its register note after a reload', () => {
  // The wire: `kept.words[].outcome` (WIRE §3.8) and the mine item's `register_note` (§2).
  const close = types.parseCloseResult(MOCK.close_b1_write);
  const stored = close.closing.kept.words.map((word, index) => ({ ...word, outcome: index === 0 ? 'correct' : null }));
  const raw = JSON.parse(JSON.stringify(MOCK.close_b1_write));
  raw.closing.kept.words = raw.closing.kept.words.map((word, index) => ({ ...word, outcome: index === 0 ? 'correct' : index === 1 ? 'bogus' : undefined }));
  const parsed = types.parseCloseResult(raw).closing.kept.words;
  assert.equal(parsed[0].outcome, 'correct');
  assert.equal(parsed[1].outcome, null, 'an unknown outcome reads as none');
  const { RvKept } = require('./index.ts');
  // No evidence in this visit (a reload): the stored outcome alone marks the word.
  const kept = render(h(RvKept, { words: stored, claims: [], copy: FR, outcomes: {} }));
  assert.equal((kept.match(/data-outcome="correct"/g) || []).length, 1);
  assert.match(kept, /bien employé/);

  const mine = types.parseThreadItem({ ...MOCK.session_resume.thread.find((item) => item.kind === 'mine'), register_note: 'vous_to_tu' });
  assert.equal(mine.registerNote, 'vous_to_tu');
  assert.equal(types.parseThreadItem({ ...MOCK.session_resume.thread.find((item) => item.kind === 'mine'), register_note: 'ok' }).registerNote, null);
  const html = render(h(RvThread, { items: [mine], support: SUPPORT_TAP, copy: revueCopy('fr'), registerNotes: {} }));
  assert.match(html, /data-kind="mine"[\s\S]*data-kind="register"/);
  assert.match(html, /Avec Romy, on se tutoie\./);
});

// ---------------------------------------------------------------------------
// WP-119 §8.4 · the story's own picture: RvPicture, «La légende», the dispatch
// ---------------------------------------------------------------------------

const PICTURE = '/assets/serial/locations/marche_canal.webp';
const DESK_CAPTION = 'Un marché en plein air, un matin, entre les étals de fruits et légumes.';
const WRITTEN_CAPTION = 'Un marché en plein air, devant le marché couvert, un matin.';

test('RvPicture prints the house print like a press photograph: the frame, the caption on its rule, the credit', () => {
  const { RvPicture, PICTURE_CREDIT_FR } = require('./index.ts');
  const html = render(h(RvPicture, { url: PICTURE, captionFr: 'Un marché en plein air.', contribution: [[0, 23]], copy: FR }));
  assert.match(html, /^<figure class="rv-picture" data-size="full" data-picture=""><div class="rv-picture__frame"><img class="rv-picture__img" src="\/assets\/serial\/locations\/marche_canal\.webp" alt="" decoding="async"\/><\/div><figcaption class="rv-picture__cap">/);
  assert.match(html, /<span class="rv-picture__fr" lang="fr"><span class="rv-yours">Un marché en plein air\.<sup>toi<\/sup><\/span><\/span>/, 'the learner\'s caption: underline + «toi»');
  assert.equal(PICTURE_CREDIT_FR, 'Illustration · Le Papier');
  assert.match(html, /<span class="rv-picture__credit" lang="fr">Illustration · Le Papier<\/span><\/figcaption>/, 'an illustration, and it says so');
  assert.match(render(h(RvPicture, { url: PICTURE, copy: EN })), /Illustration · Le Papier/, 'the publication\'s credit, French in every chrome');
  // No caption yet: a dotted blank line, the caption still to find.
  const blank = render(h(RvPicture, { url: PICTURE, captionFr: '  ', copy: FR }));
  assert.match(blank, /<span class="rv-picture__blank" aria-hidden="true"><\/span>/);
  assert.doesNotMatch(blank, /class="rv-picture__fr"/);
  // A draft is printed grey and never marked as the learner's yet.
  const draft = render(h(RvPicture, { url: PICTURE, captionFr: 'Un marché', contribution: [[0, 9]], draft: true, size: 'small', copy: FR }));
  assert.match(draft, /data-size="small"/);
  assert.match(draft, /<span class="rv-picture__fr" lang="fr" data-draft="">Un marché<\/span>/);
  assert.doesNotMatch(draft, /rv-yours/);
});

test('«La légende» at A1–A2 (2026-10-23): written first; a refused try brings three captions; a pick is inked in, never «toi»', () => {
  const { RvCaption, captionFeedback } = require('./index.ts');
  const offer = types.parseMakeOffer(MOCK.make_offer_caption).options.find((option) => option.kind === 'caption');
  const props = { offer, picked: null, result: null, onPick: () => {}, onWrite: () => {}, glossLanguage: 'fr', copy: FR };
  const before = render(h(RvCaption, props));
  assert.match(before, /^<div class="rv-caption" data-format="write"><figure class="rv-picture"/);
  assert.match(before, /rv-picture__blank/, 'the caption still to write');
  assert.match(before, /<button type="button" class="av2-tile rv-caption__word"/, 'the picture\'s words drop into the caption');
  assert.match(before, /<textarea/);
  assert.doesNotMatch(before, /role="radiogroup"/, 'nothing to pick before a try');

  // Too short: Romy asks for more, the field stays, and the three captions come as the way out.
  const short = types.parseMakeResult(MOCK.make_caption_short_a2);
  const refused = render(h(RvCaption, { ...props, result: short }));
  assert.match(visibleText(refused), /Un peu court pour une légende : encore quelques mots\./);
  assert.equal(captionFeedback(short, FR).title, FR.caption_too_short);
  assert.match(refused, /<textarea/, 'write again');
  assert.match(refused, /role="radiogroup" aria-label="Ou choisis la légende"/);
  assert.match(refused, /<p class="rv-caption__or-label">Ou choisis la légende<\/p>/, 'the way out is said on screen');
  assert.equal((refused.match(/role="radio"/g) || []).length, 3);
  assert.doesNotMatch(refused, /data-state="(correct|wrong)"/, 'the answer stays with the server until the pick');

  // The pick on its way prints grey under the picture (a resume's offer carries the three).
  const resumed = { ...props, offer: { ...offer, options: short.options } };
  const sending = render(h(RvCaption, { ...resumed, picked: 'l2', pending: true }));
  assert.match(sending, /data-format="choice"/);
  assert.match(sending, /data-draft="">Un marché fermé, un soir de pluie\.<\/span>/);

  // A wrong pick: marked with its word, the picture's own caption inked in, uncredited.
  const wrong = render(h(RvCaption, { ...resumed, picked: 'l2', result: types.parseMakeResult(MOCK.make_caption_pick_wrong) }));
  assert.match(wrong, /data-answered=""/);
  assert.match(wrong, new RegExp(`<span class="rv-picture__fr" lang="fr">${DESK_CAPTION.replace(/\./g, '\\.')}</span>`));
  assert.doesNotMatch(wrong, /<sup>toi<\/sup>/);
  assert.match(wrong, /data-state="correct" disabled=""><span lang="fr">Un marché en plein air/);
  assert.match(wrong, /data-state="wrong" disabled=""><span lang="fr">Un marché fermé[\s\S]*?à revoir/);
  assert.match(wrong, /data-tone="wrong"/);
  assert.match(visibleText(wrong), /Pas celle-là : l’image montre autre chose\./);

  // The right pick: inked in, still not the learner's caption.
  const right = render(h(RvCaption, { ...resumed, picked: 'l1', result: types.parseMakeResult(MOCK.make_caption_pick_right) }));
  assert.match(right, new RegExp(`<span class="rv-picture__fr" lang="fr">${DESK_CAPTION.replace(/\./g, '\\.')}</span>`));
  assert.doesNotMatch(right, /rv-yours|<sup>toi<\/sup>/);
  assert.match(right, /data-tone="correct"/);
  assert.match(visibleText(right), /C’est ce qu’on voit\./);
});

test('«La légende» at B1+: the words are tiles that drop into the caption; the count; refused → write again; filed → printed as theirs', () => {
  const { RvCaption, captionShown, captionFeedback } = require('./index.ts');
  const offer = types.parseMakeOffer(MOCK.make_offer_caption_b1).options.find((option) => option.kind === 'caption');
  const props = { offer, picked: null, result: null, onPick: () => {}, onWrite: () => {}, glossLanguage: 'en', copy: EN };
  const before = render(h(RvCaption, props));
  assert.match(before, /data-format="write"/);
  assert.match(before, /<button type="button" class="av2-tile rv-caption__word" aria-label="Add «marché couvert» to your caption"><span class="rv-caption__fr" lang="fr">marché couvert<\/span><small class="rv-caption__gloss" lang="en">covered market<\/small><\/button>/);
  assert.match(before, /<span class="av2-field__label">Your caption<\/span><textarea class="av2-field__control" lang="fr"[^>]*aria-describedby="rv-caption-count"/);
  assert.match(before, /<p class="rv-write__count" id="rv-caption-count">0 of 16 words at most<\/p>/);
  assert.match(before, /<button type="button" class="av2-btn av2-btn--primary" disabled=""[^>]*><span>Suggest the caption<\/span>/, 'nothing to send yet');
  assert.equal((before.match(/av2-btn--primary/g) || []).length, 1);
  // Typing prints the caption grey under the picture as it grows; a tile drops its words in.
  assert.deepEqual(captionShown(offer, null, null, ' Un marché '), { captionFr: 'Un marché', contribution: [], draft: true });
  assert.deepEqual(captionShown(offer, null, null, ''), { captionFr: null, contribution: [], draft: true });
  assert.equal(model.captionInsert('', 'en plein air'), 'En plein air');
  assert.equal(model.captionInsert('Un marché', 'en plein air'), 'Un marché en plein air');
  assert.equal(model.captionUses('Un Marché couvert, le matin', 'le marché couvert'), true);
  assert.equal(model.captionUses('Un marché', 'en plein air'), false);

  const refusedResult = types.parseMakeResult(MOCK.make_caption_refused);
  const refused = render(h(RvCaption, { ...props, result: refusedResult }));
  assert.match(refused, /data-tone="wrong"/);
  assert.match(visibleText(refused), /The picture or the sources say otherwise\. Write it again\. Used well: en plein air/);
  assert.match(refused, /<textarea/, 'write again');
  assert.match(refused, /av2-btn--primary/);
  assert.deepEqual(captionShown(offer, refusedResult, null, WRITTEN_CAPTION).draft, true, 'a refused caption stays a draft');

  const filedResult = types.parseMakeResult(MOCK.make_caption_write);
  const filed = render(h(RvCaption, { ...props, result: filedResult }));
  assert.match(filed, /data-accepted=""/);
  assert.match(filed, new RegExp(`<span class="rv-yours">${WRITTEN_CAPTION.replace(/\./g, '\\.')}<sup>you</sup></span>`));
  assert.match(filed, /data-state="placed" aria-label="marché couvert, in your caption" disabled=""/);
  assert.match(filed, /data-state="placed" aria-label="en plein air, in your caption" disabled=""/);
  assert.doesNotMatch(filed, /<textarea|av2-btn--primary/, 'filed: the foot\'s «Continuer» is the one press');
  assert.deepEqual(captionFeedback(filedResult, EN), { tone: 'correct', title: 'The picture and the sources say so.', detail: 'Used well: marché couvert, en plein air' });
  assert.equal(captionFeedback({ ...filedResult, evidence: { ...filedResult.evidence, factFit: 'unsupported', words: [] } }, FR).title, 'Ce n’est pas tout à fait sur l’image, mais Romy la garde.');
  // Glosses off: the words without their gloss.
  assert.doesNotMatch(render(h(RvCaption, { ...props, glosses: 'none' })), /rv-caption__gloss/);
});

test('the dispatch prints the story\'s picture under the headline, the caption marked only when the learner made it', () => {
  const desk = render(h(RvDispatch, { ...types.parseCloseResult(MOCK.close_caption_choice).closing.dispatch, copy: FR }));
  const order = ['class="rv-dispatch__hl"', 'data-picture=""', 'class="rv-dispatch__body"', 'class="rv-dispatch__by"'].map((needle) => desk.indexOf(needle));
  assert.ok(order.every((index) => index >= 0));
  assert.deepEqual(order.slice().sort((a, b) => a - b), order, 'headline, picture, body, byline');
  assert.match(desk, new RegExp(`<span class="rv-picture__fr" lang="fr">${DESK_CAPTION.replace(/\./g, '\\.')}</span>`));
  assert.doesNotMatch(desk, /<sup>toi<\/sup>/, 'the desk\'s caption after a wrong pick: no «toi»');
  const mine = render(h(RvDispatch, { ...types.parseCloseResult(MOCK.close_caption_write).closing.dispatch, copy: EN }));
  assert.match(mine, new RegExp(`<span class="rv-yours">${WRITTEN_CAPTION.replace(/\./g, '\\.')}<sup>you</sup></span>`));
  assert.match(visibleText(mine), /Illustration · Le Papier/);
  assert.doesNotMatch(render(h(RvDispatch, { ...types.parseDispatch(MOCK.close.closing.dispatch), copy: FR })), /rv-picture/, 'no picture, no frame');

  // In the close, the dispatch with its picture comes before «Pour ton Relevé».
  const close = types.parseCloseResult(MOCK.close_caption_write);
  const live = render(h(RvEncounter, {
    client: createMockRevueClient({ persist: false }),
    session: { ...types.parseSessionView(MOCK.session_b1_picture_arrive), closing: close.closing },
    language: 'en',
    onExit: () => {},
    now: new Date(at),
  }));
  assert.ok(live.indexOf('data-picture=""') > live.indexOf('data-dispatch=""'));
  assert.ok(live.indexOf('data-picture=""') < live.indexOf('data-kind="kept"'));
  assert.match(visibleText(live).replace(/ ([,.])/g, '$1'), /Ta légende part sous l'image, avec mon papier\./);
  const { RvMadeCard } = require('./index.ts');
  assert.match(visibleText(render(h(RvMadeCard, { made: types.parseMakeResult(MOCK.make_caption_write).made, copy: FR }))), /^Ta légende Un marché en plein air/);
  // A pick is not the learner's: «La légende», «Le titre», never «Ta» / «Ton» (2026-10-23).
  assert.match(visibleText(render(h(RvMadeCard, { made: types.parseMakeResult(MOCK.make_caption_pick_right).made, copy: FR }))), /^La légende Un marché en plein air/);
  assert.match(visibleText(render(h(RvMadeCard, { made: types.parseMakeResult(MOCK.make_pick).made, copy: FR }))), /^Le titre /);
});

test('the arrive screen on the story\'s own picture: the picture is the plate, Romy says «Regarde», nothing stands in', () => {
  const session = types.parseSessionView(MOCK.session_picture_arrive);
  const html = render(h(RvEncounter, { client: createMockRevueClient({ persist: false }), session, language: 'fr', onExit: () => {}, now: new Date(at) }));
  assert.match(html, /<div class="rv-stage" data-size="full"><img class="rv-stage__plate" src="\/assets\/serial\/locations\/marche_canal\.webp"/);
  assert.match(html, /data-role="look"/);
  assert.doesNotMatch(html, /data-role="place_note"/);
  assert.ok(html.indexOf('data-role="look"') < html.indexOf('data-role="purpose"'), 'Romy points at the picture, then says why she is here');
  assert.match(visibleText(html), /Regarde : le marché en plein air , et derrière , le marché couvert \./);
  assert.equal((html.match(/av2-btn--primary/g) || []).length, 1);
});

test('the make picker names «La légende» in every chrome: to choose (A1–A2), to write (B1+)', () => {
  for (const language of ['fr', 'en', 'de']) {
    const copy = revueCopy(language);
    for (const kind of ['caption', 'caption_write']) {
      assert.ok(copy.make_options[kind].title && copy.make_options[kind].detail, `${language} ${kind}`);
    }
    assert.match(copy.make_options.caption_write.detail, /\{n\}/, `${language}: the word cap is shown`);
    for (const key of ['caption_label', 'caption_right', 'caption_wrong', 'caption_write_label', 'caption_placeholder', 'caption_send', 'caption_supported', 'caption_unsupported', 'caption_contradicted', 'caption_words', 'caption_word_add', 'caption_word_used', 'made_caption']) {
      assert.ok(copy[key], `${language} ${key}`);
    }
    assert.match(copy.caption_word_add, /\{word\}/);
  }
  const picker = render(h(RvMakePicker, {
    options: [
      { id: 'caption', titleFr: FR.make_options.caption.title, detail: FR.make_options.caption.detail },
      { id: 'headline_choice', titleFr: FR.make_options.headline_choice.title, detail: FR.make_options.headline_choice.detail },
    ],
    recommended: 'caption',
    value: 'caption',
    onChange: () => {},
    copy: FR,
  }));
  assert.match(picker, /aria-checked="true"[^>]*data-state="selected" data-make="caption"/);
  assert.match(visibleText(picker), /Choisir la légende Trois légendes, une seule dit ce qu’on voit\./);
});


test('2026-10-18 · the lead translates at every band; at A1–A2 the claim cards wait behind one «Sources» fold', () => {
  const { RvLead, RvNewsCard, newsHeadline } = require('./index.ts');
  const lead = { id: '1.s', textFr: 'Paris a 91 marchés.', translation: 'Paris hat 91 Märkte.', glosses: [], copy: FR, glossLanguage: 'de' };
  assert.match(render(h(RvLead, { ...lead, support: SUPPORT_SHOWN })), /class="rv-chip" aria-pressed="false">[\s\S]*Traduire/);
  // 2026-10-19: help at every band, with or without the server's translation (it is fetched on the press).
  assert.match(render(h(RvLead, { ...lead, support: SUPPORT_NONE })), /Traduire/, 'B1 and up too');
  assert.match(render(h(RvLead, { ...lead, translation: null, support: SUPPORT_SHOWN })), /Traduire/);
  assert.doesNotMatch(render(h(RvLead, { ...lead, support: SUPPORT_SHOWN })), /Paris hat 91 Märkte/, 'nothing shown until pressed');
  assert.match(render(h(RvLead, { ...lead, support: SUPPORT_TAP, copy: EN })), /<p class="rv-lead__k">What happened<\/p>/);

  const claims = ALL_KINDS.slice(0, 4);
  for (const band of ['A1', 'A2']) {
    const plain = render(h(RvThread, { items: claims, support: SUPPORT_TAP, copy: FR, band, now: new Date(at) }));
    // Romy has just said the fact: the cards wait behind one quiet line under the lead, closed.
    assert.match(plain, /data-kind="summary"[\s\S]*<li class="av2-thread__line" data-kind="sources"><div class="rv-claims" data-plain="" data-sources=""><button type="button" class="rv-folded" aria-expanded="false">/, band);
    assert.match(visibleText(plain), /Sources · 2 faits/, band);
    assert.doesNotMatch(plain, /Interprétation|La citation|rv-claim"|Les marchés sont des lieux de vie/, `${band}: nothing twice until the fold opens`);
  }
  // One fold for the whole thread, not a row after each of Romy's replies; it lists every claim so far.
  const reply = (id, claimIds) => [
    { id: `${id}.m`, seq: id, at, kind: 'mine', textFr: 'Et après ?', mode: 'text' },
    { id: `${id}.r`, seq: id, at, kind: 'line', speaker: 'romy_tremblay', role: 'reply', textFr: 'Voilà.', translation: null, glosses: [] },
    { id: `${id}.c`, seq: id, at, kind: 'claims', claims: ALL_KINDS[3].claims.filter((claim) => claimIds.includes(claim.id)) },
  ];
  const long = render(h(RvThread, { items: [...ALL_KINDS.slice(0, 3), ...reply(5, ['c1']), ...reply(6, ['c4', 'c1'])], support: SUPPORT_TAP, copy: EN, band: 'A1', now: new Date(at) }));
  assert.equal((long.match(/data-kind="sources"/g) || []).length, 1);
  assert.doesNotMatch(long, /claimsFolded|facts on the table/);
  assert.match(visibleText(long), /Sources · 2 facts/);
  assert.deepEqual(model.claimsShown([...reply(5, ['c1']), ...reply(6, ['c4', 'c1'])]).map((claim) => claim.id), ['c1', 'c4']);
  const b1 = render(h(RvThread, { items: claims, support: SUPPORT_NONE, copy: FR, band: 'B1', now: new Date(at) }));
  assert.doesNotMatch(b1, /rv-plain/);
  assert.match(b1, /Interprétation/);

  // Home's news card: the sticker, the six-word headline, one link with a sentence for its label.
  const story = { ...types.parseOffer(MOCK.offer).recommended, headlineFr: 'Un marché six matins sur sept', plateUrl: '/static/revue/plates/x.webp' };
  const card = render(h(RvNewsCard, { story, href: '/revue?dossier=x', copy: EN }));
  assert.match(card, /^<a class="rv-news" href="\/revue\?dossier=x" data-revue-card="news" aria-label="Today&#x27;s news with Romy: Un marché six matins sur sept">/);
  assert.match(card, /<span class="rv-news__sticker" aria-hidden="true">À la une !/);
  assert.match(card, /<img src="[^"]*x\.webp" alt=""/);
  assert.equal(newsHeadline({ headlineFr: '  ', titleFr: 'Le titre' }), 'Le titre', 'no headline: the title');
});

test('2026-10-19 · every word is a control at every band; the Papier\'s glosses reach the sheet; one «Traduire» per bubble', () => {
  const items = ALL_KINDS.slice(0, 3);
  for (const [band, support] of [['A1', SUPPORT_SHOWN], ['A2', SUPPORT_TAP], ['B2', SUPPORT_NONE]]) {
    const html = render(h(RvThread, { items, support, copy: FR, band, glossLanguage: 'de', onWord: () => {}, now: new Date(at) }));
    for (const kind of ['narration', 'line', 'summary']) {
      const row = html.match(new RegExp(`data-kind="${kind}"[\\s\\S]*?</li>`))[0];
      assert.match(row, /<button type="button" class="rv-word"/, `${band} ${kind}: the words are tappable`);
    }
    for (const kind of ['line', 'summary']) {
      const row = html.match(new RegExp(`data-kind="${kind}"[\\s\\S]*?</li>`))[0];
      assert.equal((row.match(/Traduire/g) || []).length, 1, `${band} ${kind}: one «Traduire»`);
    }
  }

  // The gloss the Papier already knows: accents, case and the article aside.
  const session = types.parseSessionView(MOCK.session_resume);
  const glosses = model.sessionGlosses(session);
  assert.equal(model.knownGloss('Marché couvert', glosses), 'Markthalle');
  assert.equal(model.knownGloss('l’arrondissement', glosses), 'Bezirk');
  assert.equal(model.knownGloss('les matins', glosses), 'Vormittage');
  assert.equal(model.knownGloss('grève', glosses), null, 'not a word of this Papier: the sheet looks it up');
  assert.equal(model.knownGloss('lecture', [{ fr: 'cture', gloss: 'x' }]), null, '«le» is an article only before a space');
  // A homograph of the other gender is not reused: the sentence's article decides.
  const tower = [{ fr: 'la tour', gloss: 'Turm' }];
  assert.equal(model.knownGloss('tour', tower, 'Le Tour de France part samedi.'), null, '«le tour» is not «la tour»');
  assert.equal(model.knownGloss('tour', tower, 'Au tour de Paris !'), null);
  assert.equal(model.knownGloss('tour', tower, 'La tour Eiffel brille.'), 'Turm');
  assert.equal(model.knownGloss('tour', tower, 'Les spectateurs regardent la tour.'), 'Turm');
  assert.equal(model.knownGloss('tour', tower, 'Leur tour arrive.'), 'Turm', 'no gendered article before it: as before');
  assert.equal(model.knownGloss('tour', tower), 'Turm', 'no sentence: as before');
});

test('2026-10-19 · «Traduire» asks once per text; a failure is forgotten, so the next press asks again', async () => {
  const { translateOnce, knownTranslation } = require('./revue-translate.ts');
  const asked = [];
  const fetcher = async (text) => {
    asked.push(text);
    return 'Paris has 91 markets.';
  };
  const [first, twin] = await Promise.all([translateOnce(' Paris a 91 marchés. ', 'en', fetcher), translateOnce('Paris a 91 marchés.', 'en', fetcher)]);
  assert.equal(first, 'Paris has 91 markets.');
  assert.equal(twin, first);
  assert.equal(await translateOnce('Paris a 91 marchés.', 'en', fetcher), first);
  assert.deepEqual(asked, ['Paris a 91 marchés.'], 'the same sentence, on any bubble, is fetched once');
  assert.equal(knownTranslation('Paris a 91 marchés.', 'en'), first);
  assert.equal(knownTranslation('Paris a 91 marchés.', 'de'), '', 'kept per language');

  let calls = 0;
  const flaky = async () => {
    calls += 1;
    if (calls === 1) throw new Error('down');
    return calls === 2 ? '' : 'Another market.';
  };
  await assert.rejects(translateOnce('Un autre marché.', 'en', flaky));
  assert.equal(await translateOnce('Un autre marché.', 'en', flaky), '', 'an empty answer is a failure too');
  assert.equal(await translateOnce('Un autre marché.', 'en', flaky), 'Another market.');
  assert.equal(calls, 3);
});

test('2026-10-19 · the way forward: «Écrire le papier →» once the learner has spoken; the band scrolls with the page', () => {
  const client = createMockRevueClient({ persist: false });
  const arrive = render(h(RvEncounter, { client, session: types.parseSessionView(MOCK.session_arrive), language: 'en', onExit: () => {}, now: new Date(at) }));
  assert.doesNotMatch(arrive, /rv-quick__go/, 'nothing to write before the first word');

  const resume = render(h(RvEncounter, { client, session: types.parseSessionView(MOCK.session_resume), language: 'en', onExit: () => {}, now: new Date(at) }));
  // The make, first in the one row of quick replies.
  assert.match(resume, /<div class="rv-quick"[^>]*><button type="button" class="av2-chip rv-quick__go">Write the piece →<\/button>/);
  // 2026-10-23: chips alone do not open the make; a hint says what will.
  const chipsOnly = render(h(RvEncounter, { client, session: { ...types.parseSessionView(MOCK.session_resume), ownLine: false }, language: 'en', onExit: () => {}, now: new Date(at) }));
  assert.doesNotMatch(chipsOnly, /rv-quick__go/);
  assert.match(chipsOnly, /<p class="rv-foot__hint">To write the piece, first tell her something in your own words\.<\/p>/);
  assert.doesNotMatch(resume, /rv-foot__hint/);
  for (const language of ['fr', 'en', 'de']) assert.ok(revueCopy(language).write_paper.endsWith('→'), language);
  assert.match(revueCopy('fr').write_paper, /^Écrire le papier/);
  // Only the head row is pinned: the band comes after it, in the page.
  assert.match(resume, /<div class="rv-top"><div class="rv-head">[\s\S]*?<\/div><\/div><div class="rv-stage" data-size="band"/);
  assert.doesNotMatch(resume, /rv-col/);
  // A1–A2: one «Sources» line in the thread, no fold row after each reply.
  assert.equal((resume.match(/data-kind="sources"/g) || []).length, 1);
});

test('2026-10-19 · the close: Romy\'s close line once, the colophon from the server, the two links on one row', () => {
  const close = types.parseCloseResult(MOCK.close);
  const resume = types.parseSessionView(MOCK.session_resume);
  const closeLine = { id: '13', seq: 13, at, kind: 'line', speaker: 'romy_tremblay', role: 'close', textFr: close.closing.romyLineFr, translation: null, glosses: [] };
  const page = (thread, closing = close.closing) =>
    render(h(RvEncounter, {
      client: createMockRevueClient({ persist: false }),
      session: { ...resume, thread, closing },
      language: 'fr',
      onExit: () => {},
      onReleve: () => {},
      now: new Date(at),
    }));
  const count = (html) => visibleText(html).replace(/ ([,.!?])/g, '$1').split(close.closing.romyLineFr).length - 1;
  assert.equal(count(page(resume.thread)), 1, 'the client prints it when the thread does not');
  assert.equal(count(page([...resume.thread, closeLine])), 1, 'the server replayed it: not twice');
  // The make's done line already said it: the server's close line is not printed again.
  const done = { ...closeLine, id: '12', role: 'make_done' };
  const rows = model.displayThread([...resume.thread, done, closeLine]);
  assert.deepEqual(rows.slice(-1).map((row) => row.kind === 'item' && [row.item.id, row.past]), [['12', false]]);

  const daily = page(resume.thread, { ...close.closing, colophonFr: 'La suite demain.' });
  assert.match(visibleText(daily), /La suite demain\./);
  assert.match(daily, /av2-btn--done[\s\S]*Classer le Papier[\s\S]*<div class="rv-foot__links"><a [^>]*>[\s\S]*?<\/a><button[^>]*>[\s\S]*Voir dans le Relevé/);
});

// #283 (22 Oct live walk): Home's «À la une» thumbnail showed the browser's broken-image
// glyph in an empty frame. Server markup cannot fire `onError`, so the card is called as a
// function with `useState` held in a slot table: render, fail the picture, render again.
function renderWithState(Component, props, afterFirst) {
  const slots = [];
  let cursor = 0;
  const original = React.useState;
  React.useState = (initial) => {
    const index = cursor++;
    if (!(index in slots)) slots[index] = typeof initial === 'function' ? initial() : initial;
    return [slots[index], (value) => { slots[index] = typeof value === 'function' ? value(slots[index]) : value; }];
  };
  try {
    const first = Component(props);
    afterFirst(first);
    cursor = 0;
    return Component(props);
  } finally {
    React.useState = original;
  }
}

function findElements(node, predicate, found = []) {
  if (node == null || typeof node !== 'object') return found;
  if (Array.isArray(node)) { node.forEach((child) => findElements(child, predicate, found)); return found; }
  if (predicate(node)) found.push(node);
  findElements(node.props && node.props.children, predicate, found);
  return found;
}

test('#283 · a news picture that fails to load leaves no broken glyph and no empty frame', () => {
  const { RvNewsCard } = require('./index.ts');
  const story = { ...types.parseOffer(MOCK.offer).recommended, headlineFr: 'Le PSG bat le Barça 4-2', plateUrl: '/static/revue/plates/gone.webp' };
  const isImg = (el) => el.type === 'img';
  const isFrame = (el) => el.props && String(el.props.className || '').includes('rv-news__pic');

  const after = renderWithState(RvNewsCard, { story, href: '/revue?dossier=x', copy: EN }, (first) => {
    const [img] = findElements(first, isImg);
    assert.ok(img, 'a picture is printed while it may still load');
    assert.equal(typeof img.props.onError, 'function', 'the picture hears its own failure');
    img.props.onError();
  });
  assert.equal(findElements(after, isImg).length, 0, 'a dead picture URL prints no <img>: no broken-image glyph');
  assert.equal(findElements(after, isFrame).length, 0, 'and no empty frame in its place');
  assert.equal(findElements(after, (el) => el.props && el.props['data-revue-card'] === 'news').length, 1, 'the card itself stays');
});

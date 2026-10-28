// node --test components/revue/revue-wire.test.js
//
// WP-119 phases 1–2 · the wire, client side (phase 2 «Les invités», WIRE §6:
// fallback reasons, the guest item, make_intro / make_done, the rubric,
// headline_write and short_report; WP-120's vignette on the close; §8.4 the
// story's own picture: the stage's `plate_kind` / `picture_words`, the `look`
// line, «La légende» and the dispatch's picture).
//
//   1. every JSON example of docs/implementation/atelier-v2/WP-119-WIRE.md parses
//      (fixtures/wire-examples.json, copied verbatim), and so does every payload
//      the mock produces (fixtures/mock-wire.json — validated against
//      app/schemas/revue.py, extra=forbid);
//   2. snake_case → camelCase, field for field, with nothing invented;
//   3. errors: the flag-off 404 is `{ enabled: false }`, coded 404/409/422 become
//      typed RevueErrors carrying their `session_id` / `dossier_id` / `kind`;
//   4. request bodies go out in snake_case.

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { fixture } = require('./revue-test-setup');

const types = require('../../lib/revue-types.ts');
const { createRevueClient, RevueError } = require('../../lib/revue-api.ts');

const WIRE = fixture('wire-examples');
const MOCK = fixture('mock-wire');

test('the wire document\'s offer example parses', () => {
  const offer = types.parseOffer(WIRE.offer);
  assert.deepEqual(offer.week, { iso: '2026-W40', label: 'Semaine 40', range: 'du 28 sept. au 4 oct.' });
  assert.equal(offer.recommended.dossierId, 'evergreen-marche-du-dimanche');
  assert.equal(offer.recommended.evergreen, true);
  assert.equal(offer.recommended.stage.platePlaceId, 'marche_canal');
  assert.equal(offer.recommended.stage.placeIsReal, false);
  assert.equal(offer.recommended.stage.dress, 'apron');
  assert.deepEqual(offer.recommended.stage.cast, [
    { id: 'romy_tremblay', hold: 'notebook' },
    { id: 'user', hold: null },
  ]);
  assert.equal(offer.recommendedReason, 'interests');
  assert.equal(offer.alternatives.length, 1);
  assert.equal(offer.alternatives[0].dossierId, 'evergreen-greve-transports');
  assert.equal(offer.evergreenOnly, true);
  assert.equal(offer.resume, null);
  assert.equal(offer.filed, null);
});

test('the wire document\'s match miss and turn examples parse', () => {
  assert.deepEqual(types.parseMatch(WIRE.match_miss), {
    match: null,
    romyLineFr: "Je n'ai que ça cette semaine, désolée. Le marché du dimanche à Aligre, ça te dit ?",
  });
  const turn = types.parseTurnResult(WIRE.turn);
  assert.deepEqual(turn.items.map((item) => item.kind), ['mine', 'line', 'uncertainty', 'guest']);
  assert.equal(turn.items[1].reason, null);
  assert.deepEqual(
    { castId: turn.items[3].castId, move: turn.items[3].move, position: turn.items[3].position, reasonFr: turn.items[3].reasonFr },
    { castId: 'margaux_barman', move: 'enter', position: 'for', reasonFr: null },
  );
  assert.equal(turn.items[0].textFr, 'Est-ce que les prix sont plus bas qu\'au supermarché ?');
  assert.equal(turn.items[1].role, 'reply');
  assert.equal(turn.items[1].speaker, 'romy_tremblay');
  assert.equal(turn.items[2].id, '11.u');
  assert.deepEqual(turn.room, { used: 2, phase: 'open', remainingTurns: 10 });
  assert.deepEqual(turn.support, { glosses: 'tap', translation: 'on_request', readingTargetWords: 90, vocabTarget: 5, level: 0 });
  assert.deepEqual(turn.quickReplies[0], { label: 'On formule la question', sendFr: 'On formule la question ensemble ?' });
  assert.equal(turn.steerToMake, false);
  assert.deepEqual(turn.evidence, {
    outcome: 'unscored',
    capabilityKnown: false,
    grader: 'revue-rubric-v1',
    words: [
      { fr: 'compte', outcome: 'unscored', capabilityKnown: false },
      { fr: 'marchés', outcome: 'unscored', capabilityKnown: true },
    ],
    factFit: 'not_applicable',
    registerNote: 'ok',
    pending: false,
  });
});

test('every phase-2 example of the wire document parses (WIRE §6)', () => {
  const fallback = types.parseThreadItem(WIRE.fallback_line);
  assert.equal(fallback.kind, 'line');
  assert.equal(fallback.role, 'fallback');
  assert.equal(fallback.reason, 'model_down');

  const enter = types.parseThreadItem(WIRE.guest_enter);
  assert.deepEqual(enter, {
    id: '10', seq: 10, at: '…', kind: 'guest', castId: 'margaux_barman',
    textFr: 'Ce que je sers au comptoir, ça vient de quelque part. Alors ça me regarde.',
    move: 'enter', position: 'for', reasonFr: null, reason: null, glosses: [],
  });
  const moved = types.parseThreadItem(WIRE.guest_moved);
  assert.equal(moved.move, 'moved');
  assert.equal(moved.position, 'moved');

  const evidence = types.parseEvidence(WIRE.evidence);
  assert.equal(evidence.outcome, 'correct');
  assert.equal(evidence.factFit, 'supported');
  assert.deepEqual(evidence.words[1], { fr: 'marchés', outcome: 'correct', capabilityKnown: true });

  const offer = types.parseMakeOffer(WIRE.make_offer_b1);
  assert.equal(offer.recommended, 'headline_write');
  assert.deepEqual(offer.options.map((o) => o.kind), ['headline_choice', 'headline_write', 'reader_question', 'short_report']);
  assert.equal(offer.options[1].maxWords, 14);
  assert.equal(offer.options[3].seconds, 30);
  assert.equal(offer.intro.role, 'make_intro');
  assert.match(offer.intro.textFr, /Tu l'écris \?/);

  const write = types.parseMakeResult(WIRE.make_write);
  assert.equal(write.kind, 'headline_write');
  assert.equal(write.accepted, true);
  assert.equal(write.made.kind, 'headline_write');
  assert.deepEqual(write.made.contribution, [[0, 36]]);
  assert.equal(write.line.role, 'make_done');
  assert.equal(write.evidence.grader, 'revue-rubric-v1');

  // The report example elides its evidence («…»): the parser fills the phase-1 defaults, never guesses.
  const report = types.parseMakeResult(WIRE.make_report);
  assert.equal(report.kind, 'short_report');
  assert.equal(report.made.kind, 'short_report');
  assert.equal(report.made.learnerFr, "Je suis au marché d'Aligre…");
  assert.equal(report.line.role, 'make_done');
  assert.equal(report.line.textFr, "C'est enregistré. Je le mets dans mon papier.");
  assert.equal(report.evidence.factFit, 'not_applicable');
});

test('every mock payload parses into the full client shapes', () => {
  const session = types.parseSessionView(MOCK.session_arrive);
  assert.equal(session.status, 'active');
  assert.equal(session.beat, 'arrive');
  assert.equal(session.plan.band, 'A1');
  assert.equal(session.plan.glossLanguage, 'de');
  assert.deepEqual(session.plan.makeOptions, ['headline_choice', 'reader_question'], 'A1/A2: the phase-2 makes are absent');
  assert.deepEqual(types.parseSessionView(MOCK.session_b1_arrive).plan.makeOptions, ['headline_write', 'reader_question', 'short_report'], 'no headline to pick from B1');
  // 2026-10-23: «Écrire le papier» waits for a line the learner typed or said; a chip is not one.
  assert.equal(session.ownLine, false);
  assert.deepEqual(['turn_facts', 'turn_prix', 'turn_formulate'].map((key) => types.parseTurnResult(MOCK[key]).ownLine), [false, true, true]);
  assert.equal(types.parseSessionView(MOCK.session_resume).ownLine, true);
  assert.equal(session.plan.vocabulary.length, 5);
  assert.ok(session.plan.vocabulary.every((gloss) => gloss.fr && gloss.gloss && gloss.claimId));
  assert.deepEqual(session.thread.map((item) => item.kind), ['narration', 'narration', 'line', 'line', 'summary']);
  assert.deepEqual(session.thread.filter((item) => item.kind === 'line').map((item) => item.role), ['place_note', 'purpose']);
  assert.equal(session.quickReplies[0].sendFr, "D'accord, je t'aide.");

  const facts = types.parseTurnResult(MOCK.turn_facts);
  const claims = facts.items.find((item) => item.kind === 'claims');
  assert.equal(claims.claims.length, 2);
  assert.equal(claims.claims[0].source.publishedAt, '2026-09-23');
  assert.equal(claims.claims[0].attributedTo, null);

  const offer = types.parseMakeOffer(MOCK.make_offer);
  assert.equal(offer.recommended, 'reader_question');
  assert.deepEqual(offer.options.map((option) => option.kind), ['headline_choice', 'reader_question']);
  assert.equal(offer.options[0].options.length, 3);
  assert.match(offer.options[1].seedFr, /prix/);

  const propose = types.parseMakeResult(MOCK.make_propose);
  assert.equal(propose.kind, 'reader_question');
  assert.ok(propose.draft.proposalFr.startsWith('Est-ce que'));
  assert.ok(propose.draft.contribution.length >= 1);
  const send = types.parseMakeResult(MOCK.make_send);
  assert.equal(send.made.kind, 'reader_question');
  const pick = types.parseMakeResult(MOCK.make_pick);
  assert.equal(pick.kind, 'headline_choice');
  assert.equal(typeof pick.correct, 'boolean');
  assert.ok(pick.evidence.quote.length > 10);
  assert.deepEqual(pick.made.contribution, [], 'a pick is not the learner\'s writing');

  const close = types.parseCloseResult(MOCK.close);
  assert.equal(close.session.status, 'closed');
  assert.deepEqual(
    { ring: close.closing.vignette.ring, kept: close.closing.vignette.keptContribution, week: close.closing.vignette.week },
    { ring: 'question', kept: true, week: '2026-W40' },
  );
  assert.match(close.closing.vignette.pictogramSvg, /^<svg[^>]*viewBox="0 0 100 100"/);
  assert.deepEqual(types.parseVignettes(MOCK.vignettes).map((v) => v.sessionId), [close.session.id]);
  assert.equal(types.parseCloseResult(MOCK.close_report).closing.vignette.ring, 'report');
  assert.equal(types.parseCloseResult(MOCK.close_b1_write).closing.vignette.ring, 'headline');
  // A close without a vignette (a backend before WP-120) is simply no stamp.
  const { vignette, ...noVignette } = MOCK.close.closing;
  void vignette;
  assert.equal(types.parseClosing(noVignette).vignette, null);
  assert.equal(close.closing.colophonFr, 'La suite la semaine prochaine.');
  assert.equal(close.closing.dispatch.bodyFr.length, 3);
  assert.ok(close.closing.kept.words.every((word) => typeof word.used === 'boolean'));

  const resume = types.parseOffer(MOCK.offer_resume);
  assert.equal(resume.resume.beat, 'pursue');
  assert.match(resume.resume.openQuestionFr, /prix/);
  const filed = types.parseOffer(MOCK.offer_filed);
  assert.equal(filed.filed.made.kind, 'reader_question');
  assert.equal(filed.filed.dispatch.kickerFr, 'Le Papier de Romy · semaine 40');

  for (const key of Object.keys(MOCK).filter((name) => name.startsWith('turn_'))) {
    const result = types.parseTurnResult(MOCK[key]);
    assert.ok(result.items.length >= 2, key);
    assert.equal(result.items[0].kind, 'mine', key);
  }
});

test('an unknown thread kind (a later phase\'s) is dropped, never guessed; the guest now parses', () => {
  const thread = types.parseThread([
    { id: '0', seq: 0, at: 'x', kind: 'poll', text_fr: 'Vote' },
    { id: '1', seq: 1, at: 'x', kind: 'guest', cast_id: 'lila_bonnet', text_fr: 'Bonjour', move: 'follow_up', position: null, reason_fr: null, reason: 'knowledge_refused', glosses: [] },
    { id: '2', seq: 2, at: 'x', kind: 'mine', text_fr: 'Salut', mode: 'voice' },
  ]);
  assert.deepEqual(thread.map((item) => item.kind), ['guest', 'mine']);
  assert.equal(thread[0].reason, 'knowledge_refused');
  assert.equal(thread[1].mode, 'voice');
});

test('the mock\'s phase-2 payloads: guest moves, fallback reasons, the rubric, make intro / done', () => {
  const enter = types.parseTurnResult(MOCK.turn_guest_enter);
  assert.deepEqual(enter.items.map((item) => item.kind), ['mine', 'line', 'uncertainty', 'guest']);
  const guest = enter.items[3];
  assert.equal(guest.move, 'enter');
  assert.ok(guest.reasonFr, 'Margaux says why she cares');
  assert.equal(types.parseTurnResult(MOCK.turn_guest_disagree).items.find((i) => i.kind === 'guest').move, 'disagree');
  assert.equal(types.parseTurnResult(MOCK.turn_guest_disagree).evidence.registerNote, 'vous_to_tu');
  const moved = types.parseTurnResult(MOCK.turn_guest_moved);
  assert.equal(moved.items.find((i) => i.kind === 'guest').position, 'moved');
  assert.deepEqual(moved.evidence.words.find((w) => w.fr === 'marché couvert'), { fr: 'marché couvert', outcome: 'correct', capabilityKnown: true });
  const stage = types.parseSessionView(MOCK.session_b1_guest).stage.cast.map((m) => m.id);
  assert.deepEqual(stage, ['romy_tremblay', 'margaux_barman', 'user'], 'the guest stands right after Romy');

  assert.equal(types.parseTurnResult(MOCK.turn_model_down).items[1].reason, 'model_down');
  assert.equal(types.parseTurnResult(MOCK.turn_budget).items[1].reason, 'budget');
  assert.ok(types.parseTurnResult(MOCK.turn_b0).items.every((i) => i.kind !== 'line' || i.reason === null));

  assert.equal(types.parseMakeOffer(MOCK.make_offer).intro.role, 'make_intro');
  assert.equal(types.parseMakeResult(MOCK.make_send).line.role, 'make_done');
  assert.equal(types.parseMakeResult(MOCK.make_pick).line.role, 'make_done');
  const rejected = types.parseMakeResult(MOCK.make_write_rejected);
  assert.deepEqual([rejected.accepted, rejected.made, rejected.evidence.factFit], [false, null, 'contradicted']);
  assert.match(rejected.line.textFr, /les sources disent autre chose/);
  const report = types.parseMakeResult(MOCK.make_report);
  assert.equal(report.made.kind, 'short_report');
  assert.equal(report.evidence.grader, 'revue-rubric-v1');
});

test('§8.4 the story\'s own picture: the stage, «Regarde», «La légende», the dispatch', () => {
  // The stage carries the story's picture and the words it shows, never its caption (that is
  // the answer of «La légende»); an older payload is a season plate with no picture words.
  const session = types.parseSessionView(MOCK.session_picture_arrive);
  assert.deepEqual([session.stage.plateKind, session.stage.plateUrl], ['story', '/assets/serial/locations/marche_canal.webp']);
  assert.deepEqual(session.stage.pictureWords.map((word) => [word.fr, word.gloss]), [['marché couvert', 'marché sous un toit'], ['en plein air', 'dehors']]);
  assert.equal(JSON.stringify(MOCK.session_picture_arrive).includes('entre les étals de fruits'), false, 'the desk caption is not on the wire before the pick');
  const older = types.parseSessionView(MOCK.session_arrive).stage;
  assert.deepEqual([older.plateKind, older.pictureWords], ['season', []]);
  const offer = types.parseOffer(MOCK.offer_picture);
  assert.equal(offer.recommended.stage.plateKind, 'story');
  assert.deepEqual(offer.alternatives.map((card) => card.stage.plateKind), ['stand_in', 'stand_in']);

  // «Regarde»: Romy's look line, the picture's words glossed, before her purpose; the
  // picture's words lead the vocabulary (so they are the ones kept for review).
  assert.deepEqual(session.thread.filter((item) => item.kind === 'line').map((item) => item.role), ['look', 'purpose']);
  const look = session.thread.find((item) => item.kind === 'line' && item.role === 'look');
  assert.deepEqual(look.glosses.map((gloss) => gloss.fr), ['marché couvert', 'en plein air']);
  assert.deepEqual(session.plan.vocabulary.slice(0, 2).map((gloss) => gloss.fr), ['marché couvert', 'en plein air']);
  assert.deepEqual(session.plan.makeOptions, ['headline_choice', 'reader_question', 'caption']);

  // «La légende», A1–A2 (2026-10-23): written first, like B1; it leads.
  const make = types.parseMakeOffer(MOCK.make_offer_caption);
  assert.equal(make.recommended, 'caption');
  const first = make.options.find((option) => option.kind === 'caption');
  assert.deepEqual(
    { format: first.format, pictureUrl: first.pictureUrl, ids: first.options.map((option) => option.id), maxWords: first.maxWords },
    { format: 'write', pictureUrl: '/assets/serial/locations/marche_canal.webp', ids: [], maxWords: 12 },
  );
  assert.deepEqual(first.words.map((word) => word.gloss), ['marché sous un toit', 'dehors']);
  assert.match(make.intro.textFr, /légende sous l'image/);
  // A refused try (too short here) brings the three captions; one says what the picture shows.
  const short = types.parseMakeResult(MOCK.make_caption_short_a2);
  assert.deepEqual([short.accepted, short.made, short.options.map((option) => option.id)], [false, null, ['l1', 'l2', 'l3']]);
  assert.match(short.line.textFr, /Encore quelques mots/);
  const wrong = types.parseMakeResult(MOCK.make_caption_pick_wrong);
  assert.deepEqual([wrong.kind, wrong.format, wrong.accepted, wrong.correct, wrong.answerId, wrong.evidence], ['caption', 'choice', true, false, 'l1', null]);
  assert.deepEqual([wrong.made.textFr, wrong.made.contribution], [short.options[0].textFr, []], 'a wrong pick files the picture\'s caption, uncredited');
  const right = types.parseMakeResult(MOCK.make_caption_pick_right);
  assert.deepEqual([right.correct, right.made.contribution, right.line.role], [true, [], 'make_done'], 'a right pick is not theirs either');

  // B1+: written, the picture's words as tiles; refused (nothing filed) when the picture or a source contradicts it.
  const write = types.parseMakeOffer(MOCK.make_offer_caption_b1).options.find((option) => option.kind === 'caption');
  assert.deepEqual([write.format, write.options, write.maxWords], ['write', [], 16]);
  assert.deepEqual(write.words.map((word) => [word.fr, word.gloss]), [['marché couvert', 'covered market'], ['en plein air', 'outdoors']]);
  const refused = types.parseMakeResult(MOCK.make_caption_refused);
  assert.deepEqual([refused.format, refused.accepted, refused.correct, refused.answerId, refused.made, refused.evidence.factFit], ['write', false, null, null, null, 'contradicted']);
  assert.match(refused.line.textFr, /Tu réessaies/);
  const filed = types.parseMakeResult(MOCK.make_caption_write);
  assert.deepEqual([filed.accepted, filed.evidence.factFit, filed.made.contribution], [true, 'supported', [[0, 59]]]);
  assert.equal(filed.made.learnerFr, 'Un marché en plein air, devant le marché couvert, un matin.');

  // «La légende» without its picture is absent, never greyed; a choice needs two captions.
  const without = (patch) => types.parseMakeOffer({
    ...MOCK.make_offer_caption,
    options: MOCK.make_offer_caption.options.map((option) => (option.kind === 'caption' ? { ...option, ...patch } : option)),
  }).options.map((option) => option.kind);
  assert.deepEqual(without({ picture_url: null }), ['headline_choice', 'reader_question']);
  assert.deepEqual(without({ format: 'choice', options: MOCK.make_caption_short_a2.options.slice(0, 1) }), ['headline_choice', 'reader_question']);
  assert.deepEqual(without({ format: 'write', options: [] }), ['headline_choice', 'reader_question', 'caption']);

  // The dispatch prints the picture under its caption: the desk's after a wrong pick, the learner's otherwise.
  const desk = types.parseCloseResult(MOCK.close_caption_choice).closing;
  assert.deepEqual(
    [desk.dispatch.pictureUrl, desk.dispatch.captionFr, desk.dispatch.captionByLearner, desk.vignette.keptContribution],
    ['/assets/serial/locations/marche_canal.webp', 'Un marché en plein air, un matin, entre les étals de fruits et légumes.', false, false],
  );
  const picked = types.parseCloseResult(MOCK.close_caption_right).closing;
  assert.deepEqual([picked.dispatch.captionByLearner, picked.vignette.keptContribution], [false, false], 'a right pick is not the learner\'s caption');
  assert.doesNotMatch(picked.dispatch.bylineFr, /avec toi/);
  assert.match(picked.romyLineFr, /que tu as choisie/);
  const mine = types.parseCloseResult(MOCK.close_caption_write).closing;
  assert.deepEqual([mine.dispatch.captionFr, mine.dispatch.captionByLearner], ['Un marché en plein air, devant le marché couvert, un matin.', true]);
  assert.deepEqual(mine.kept.words.filter((word) => word.used).map((word) => word.fr), ['marché couvert', 'en plein air'], 'the words the caption used are kept as used');
  // A caption is printed only under a picture; a dispatch before §8.4 has neither.
  assert.deepEqual(
    (({ pictureUrl, captionFr, captionByLearner }) => [pictureUrl, captionFr, captionByLearner])(
      types.parseDispatch({ ...MOCK.close.closing.dispatch, caption_fr: 'Une légende', caption_by_learner: true }),
    ),
    [null, null, false],
  );
});

function fakeTransport(routes) {
  const calls = [];
  const reply = async (method, url, body) => {
    calls.push({ method, url, body });
    const answer = routes[`${method} ${url}`];
    if (!answer) throw Object.assign(new Error('404'), { response: { status: 404, data: { detail: 'Not Found' } } });
    if (answer.__error) throw Object.assign(new Error(String(answer.__error)), { response: { status: answer.__error, data: answer.body } });
    return answer;
  };
  return { calls, transport: { get: (url) => reply('GET', url, null), post: (url, body) => reply('POST', url, body) } };
}

test('the flag-off 404 on GET /revue/week is { enabled: false }; on with an offer, enabled', async () => {
  const off = createRevueClient(fakeTransport({}).transport);
  assert.deepEqual(await off.week(), { enabled: false });
  const on = createRevueClient(fakeTransport({ 'GET /revue/week': WIRE.offer }).transport);
  const week = await on.week();
  assert.equal(week.enabled, true);
  assert.equal(week.offer.recommended.titleFr, 'Le marché du dimanche à Aligre');
});

test('every coded error of the wire becomes a typed RevueError', async () => {
  const codes = [];
  for (const example of WIRE.errors) {
    const error = types.parseRevueError(example.status, example.body);
    assert.ok(error instanceof RevueError);
    codes.push(`${example.status} ${error.code}`);
  }
  assert.deepEqual(codes, [
    '404 revue_disabled',
    '404 revue_dossier_not_found',
    '409 revue_session_active',
    '409 revue_week_filed',
    '404 revue_session_not_found',
    '409 revue_session_closed',
    '409 revue_make_unavailable',
    '422 revue_unknown_option',
  ]);
  const active = types.parseRevueError(409, { detail: { code: 'revue_session_active', session_id: 'abc' } });
  assert.equal(active.sessionId, 'abc');
  const unavailable = types.parseRevueError(409, { detail: { code: 'revue_make_unavailable', kind: 'headline_choice' } });
  assert.equal(unavailable.makeKind, 'headline_choice');
  assert.equal(types.parseRevueError(422, { detail: [{ loc: ['body', 'text'] }] }).code, 'validation');
  assert.equal(types.parseRevueError(401, { detail: 'Not authenticated' }).code, 'unauthorized');

  const { transport } = fakeTransport({
    'POST /revue/sessions': { __error: 409, body: { detail: { code: 'revue_session_active', session_id: 's-1' } } },
  });
  const client = createRevueClient(transport);
  await assert.rejects(client.start({ dossierId: 'x' }), (error) => error instanceof RevueError && error.code === 'revue_session_active' && error.sessionId === 's-1');
  const offline = createRevueClient({ get: async () => { throw new Error('offline'); }, post: async () => { throw new Error('offline'); } });
  await assert.rejects(offline.session('s'), (error) => error.code === 'network');
});

test('request bodies go out in snake_case, on the wire\'s paths', async () => {
  const { calls, transport } = fakeTransport({
    'POST /revue/sessions': MOCK.session_arrive,
    'POST /revue/sessions/s%201/turns': MOCK.turn_facts,
    'POST /revue/sessions/s%201/make': MOCK.make_pick,
    'GET /revue/sessions/s%201/make': MOCK.make_offer,
    'POST /revue/sessions/s%201/close': MOCK.close,
    'POST /revue/match': WIRE.match_miss,
    'GET /revue/week?week=2026-W40': WIRE.offer,
  });
  const client = createRevueClient(transport);
  await client.start({ dossierId: 'evergreen-greve-transports', freeRequest: 'grève', angleId: 'a2', week: '2026-W40' });
  await client.turn('s 1', { text: 'Bonjour', clientTurnId: 't-1' });
  await client.make('s 1', { kind: 'headline_choice', action: 'pick', optionId: 'h2' });
  await client.make('s 1', { kind: 'reader_question', action: 'propose', text: 'les prix' });
  await client.make('s 1', { kind: 'reader_question', action: 'send', textFr: 'Est-ce que les prix ?' });
  await client.make('s 1', { kind: 'headline_write', action: 'write', textFr: 'Paris et ses marchés' });
  await client.make('s 1', { kind: 'short_report', action: 'report', transcript: 'Je suis au marché.' });
  await client.make('s 1', { kind: 'short_report', action: 'report', transcript: 'Je tape.', mode: 'text' });
  await client.make('s 1', { kind: 'caption', action: 'caption', optionId: 'l2' });
  await client.make('s 1', { kind: 'caption', action: 'caption', textFr: 'Un marché en plein air, un matin.' });
  await client.makeOffer('s 1');
  await client.close('s 1');
  await client.match('le cinéma', '2026-W40');
  await client.week('2026-W40');
  assert.deepEqual(calls.map((call) => [call.method, call.url, call.body]), [
    ['POST', '/revue/sessions', { week: '2026-W40', dossier_id: 'evergreen-greve-transports', free_request: 'grève', angle_id: 'a2' }],
    ['POST', '/revue/sessions/s%201/turns', { text: 'Bonjour', mode: 'text', client_turn_id: 't-1' }],
    ['POST', '/revue/sessions/s%201/make', { kind: 'headline_choice', action: 'pick', option_id: 'h2' }],
    ['POST', '/revue/sessions/s%201/make', { kind: 'reader_question', action: 'propose', text: 'les prix' }],
    ['POST', '/revue/sessions/s%201/make', { kind: 'reader_question', action: 'send', text_fr: 'Est-ce que les prix ?' }],
    ['POST', '/revue/sessions/s%201/make', { kind: 'headline_write', action: 'write', text_fr: 'Paris et ses marchés' }],
    ['POST', '/revue/sessions/s%201/make', { kind: 'short_report', action: 'report', transcript: 'Je suis au marché.', mode: 'voice' }],
    ['POST', '/revue/sessions/s%201/make', { kind: 'short_report', action: 'report', transcript: 'Je tape.', mode: 'text' }],
    ['POST', '/revue/sessions/s%201/make', { kind: 'caption', action: 'caption', option_id: 'l2' }],
    ['POST', '/revue/sessions/s%201/make', { kind: 'caption', action: 'caption', text_fr: 'Un marché en plein air, un matin.' }],
    ['GET', '/revue/sessions/s%201/make', null],
    ['POST', '/revue/sessions/s%201/close', {}],
    ['POST', '/revue/match', { text: 'le cinéma', week: '2026-W40' }],
    ['GET', '/revue/week?week=2026-W40', null],
  ]);
});

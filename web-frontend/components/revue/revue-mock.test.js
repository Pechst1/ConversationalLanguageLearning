// node --test components/revue/revue-mock.test.js
//
// WP-119 §1 · the acceptance test, scripted against the dev mock (lib/revue-mock.ts)
// through the real client and parsers — the sequence the E-3 walk drives:
//
//   the learner asks a question the dossier cannot answer → Romy names the gap
//   (an `uncertainty` item) → they phrase the reader question together, the
//   learner's own words kept → the session closes with it, and the dispatch
//   carries the learner's words, marked as theirs.
//
// Plus: the 80 % steer and the 100 % «bouclé»; simplify on breakdown; resume is
// a replay; a retried turn is safe; the flag-off 404; one active Revue a week;
// WP-119 §8.4 (`pictures: true`): the story's own picture on the stage, Romy's
// «Regarde», «La légende» chosen (A1–A2) or written (B1+), the dispatch's picture.

const assert = require('node:assert/strict');
const { test } = require('node:test');

require('./revue-test-setup');

const { createMockRevueClient } = require('../../lib/revue-mock.ts');
const { RevueError } = require('../../lib/revue-api.ts');
const { contributionSegments } = require('./revue-model.ts');

const mine = (text, spans) => contributionSegments(text, spans).filter((s) => s.mine).map((s) => s.text).join(' ');

test('the acceptance test: Romy names the gap, they phrase the question, the close carries the learner\'s words', async () => {
  const client = createMockRevueClient({ persist: false, language: 'de' });

  const week = await client.week();
  assert.equal(week.enabled, true);
  assert.equal(week.offer.recommended.dossierId, 'evergreen-marche-du-dimanche');
  assert.equal(week.offer.alternatives.length, 2);

  const arrive = await client.start();
  assert.equal(arrive.beat, 'arrive');
  assert.equal(arrive.plan.chosenBy, 'recommended');
  assert.equal(arrive.stage.dress, 'coat');
  assert.equal(arrive.stage.placeIsReal, false);
  assert.ok(arrive.thread.some((item) => item.kind === 'line' && item.role === 'place_note'), 'Romy says the plate stands in');
  assert.ok(arrive.thread.some((item) => item.kind === 'line' && item.role === 'purpose' && /Tu m’aides/.test(item.textFr)));

  const facts = await client.turn(arrive.id, { text: arrive.quickReplies[0].sendFr });
  assert.equal(facts.beat, 'facts');
  const claims = facts.items.find((item) => item.kind === 'claims');
  assert.equal(claims.claims.length, 2, 'two claims on the table');

  const question = "Est-ce que les prix sont plus bas qu'au supermarché ?";
  const gap = await client.turn(arrive.id, { text: question });
  assert.equal(gap.beat, 'pursue');
  const reply = gap.items.find((item) => item.kind === 'line');
  assert.match(reply.textFr, /je n'ai rien/);
  const uncertainty = gap.items.find((item) => item.kind === 'uncertainty');
  assert.ok(uncertainty, 'the gap is named as an uncertainty');
  assert.match(uncertainty.textFr, /prix/);
  assert.equal(gap.quickReplies[0].label, 'On formule la question');
  assert.ok(!gap.items.some((item) => item.kind === 'claims'), 'no claim is invented for it');

  await client.turn(arrive.id, { text: gap.quickReplies[0].sendFr });

  const offer = await client.makeOffer(arrive.id);
  assert.equal(offer.recommended, 'reader_question', 'the question the sources cannot answer leads');
  const readerOption = offer.options.find((option) => option.kind === 'reader_question');
  assert.equal(readerOption.seedFr, question);

  const learnerWords = "les prix au marché sont moins chers qu'au supermarché";
  const proposed = await client.make(arrive.id, { kind: 'reader_question', action: 'propose', text: learnerWords });
  const draft = proposed.draft;
  assert.equal(draft.learnerFr, learnerWords);
  assert.match(draft.proposalFr, /^Est-ce que .* \?$/);
  assert.equal(mine(draft.proposalFr, draft.contribution), learnerWords, 'the learner\'s words are marked as theirs');
  assert.ok(draft.whyNative && /Est-ce que/.test(draft.whyNative), 'one line of why, in the learner\'s language');

  const sent = await client.make(arrive.id, { kind: 'reader_question', action: 'send', textFr: draft.proposalFr });
  assert.equal(sent.made.kind, 'reader_question');
  assert.equal(sent.made.textFr, draft.proposalFr);
  assert.equal(sent.made.learnerFr, learnerWords);

  const { session, closing } = await client.close(arrive.id);
  assert.equal(session.status, 'closed');
  assert.equal(session.beat, 'close');
  assert.match(closing.romyLineFr, /ta question/);
  const dispatch = closing.dispatch;
  assert.ok(dispatch.headlineFr.includes('les prix au marché sont moins chers'), 'the dispatch carries the learner\'s question');
  assert.equal(mine(dispatch.headlineFr, dispatch.contribution), learnerWords);
  assert.equal(dispatch.bodyFr.length, 3);
  assert.match(dispatch.bylineFr, /avec toi/);
  assert.equal(closing.kept.claims.length, 2);
  assert.equal(closing.colophonFr, 'La suite la semaine prochaine.');
  assert.ok(session.thread.some((item) => item.kind === 'made' && item.made.textFr === draft.proposalFr));

  // Closing again is idempotent; turns are refused; the week shows it filed.
  assert.deepEqual((await client.close(arrive.id)).closing, closing);
  await assert.rejects(client.turn(arrive.id, { text: 'Encore ?' }), (error) => error instanceof RevueError && error.code === 'revue_session_closed');
  const filed = await client.week();
  assert.equal(filed.offer.filed.sessionId, arrive.id);
  await assert.rejects(client.start(), (error) => error.code === 'revue_week_filed' && error.sessionId === arrive.id);
});

test('resume is a replay; a retried turn adds nothing; one active Revue a week', async () => {
  const client = createMockRevueClient({ persist: false });
  const start = await client.start({ dossierId: 'evergreen-greve-transports' });
  assert.equal(start.plan.chosenBy, 'learner');
  const first = await client.turn(start.id, { text: "D'accord.", clientTurnId: 't-1' });
  const again = await client.turn(start.id, { text: "D'accord.", clientTurnId: 't-1' });
  assert.deepEqual(again, first, 'the same client_turn_id returns the stored result');
  const resumed = await client.session(start.id);
  assert.deepEqual(resumed.thread.map((item) => item.id), start.thread.concat(first.items).map((item) => item.id));
  assert.deepEqual(await client.session(start.id), resumed, 'a GET writes nothing');
  await assert.rejects(client.start(), (error) => error.code === 'revue_session_active' && error.sessionId === start.id);
  const week = await client.week();
  assert.equal(week.offer.resume.sessionId, start.id);
});

test('the column: a steer at 80 %, «bouclé» at 100 %, then Romy keeps the question', async () => {
  const client = createMockRevueClient({ persist: false });
  const s = await client.start();
  const results = [];
  for (let i = 0; i < 7; i += 1) results.push(await client.turn(s.id, { text: i === 0 ? "D'accord." : "Dis-m'en plus." }));
  const phases = results.map((r) => r.room.phase);
  assert.deepEqual(phases, ['open', 'open', 'open', 'open', 'bouclage', 'boucle', 'boucle']);
  const bouclage = results[4];
  assert.ok(bouclage.items.some((item) => item.kind === 'shift' && item.reason === 'bouclage'));
  assert.ok(bouclage.items.some((item) => item.kind === 'line' && item.role === 'steer'));
  assert.equal(bouclage.steerToMake, true);
  assert.ok(results[5].items.some((item) => item.kind === 'shift' && item.reason === 'boucle'));
  assert.match(results[6].items.find((item) => item.kind === 'line').textFr, /Je la garde pour la semaine prochaine/);
  assert.ok(results.every((r) => r.room.used >= 0 && r.room.used <= 7));
});

test('simplify on breakdown: two «je ne comprends pas» switch the support, no modal', async () => {
  const client = createMockRevueClient({ persist: false });
  const s = await client.start();
  await client.turn(s.id, { text: "D'accord." });
  const once = await client.turn(s.id, { text: 'Je ne comprends pas.' });
  assert.equal(once.support.glosses, 'tap');
  const twice = await client.turn(s.id, { text: 'Je ne comprends pas.' });
  assert.ok(twice.items.some((item) => item.kind === 'shift' && item.reason === 'simplify'));
  assert.equal(twice.support.glosses, 'shown');
  assert.equal(twice.support.level, 1);
  assert.deepEqual(twice.quickReplies.map((q) => q.label), ["Ah, d'accord", 'Encore plus simple']);
});

/** A line the learner typed (2026-10-23): the make waits for one; a chip is not one. */
const OWN_LINE = "Oui, avec plaisir, je t'écoute.";

test('2026-10-23 · the make waits for a line the learner wrote: a chip is not one', async () => {
  const client = createMockRevueClient({ persist: false });
  const s = await client.start();
  assert.equal(s.ownLine, false);
  const chip = await client.turn(s.id, { text: "D'accord, je t'aide." });
  assert.equal(chip.ownLine, false);
  await assert.rejects(client.makeOffer(s.id), (error) => error instanceof RevueError && error.code === 'revue_make_needs_a_line');
  await assert.rejects(client.make(s.id, { kind: 'headline_choice', action: 'pick', optionId: 'h1' }), (error) => error.code === 'revue_make_needs_a_line');
  const own = await client.turn(s.id, { text: OWN_LINE });
  assert.equal(own.ownLine, true);
  assert.equal((await client.session(s.id)).ownLine, true);
  assert.ok((await client.makeOffer(s.id)).options.length > 0);
});

test('the headline choice: exactly one supported headline; the evidence cites its quote', async () => {
  const client = createMockRevueClient({ persist: false });
  const s = await client.start();
  await client.turn(s.id, { text: OWN_LINE });
  const offer = await client.makeOffer(s.id);
  const headline = offer.options.find((option) => option.kind === 'headline_choice');
  assert.equal(headline.options.length, 3);
  const wrong = await client.make(s.id, { kind: 'headline_choice', action: 'pick', optionId: 'h1' });
  assert.equal(wrong.correct, false);
  assert.equal(wrong.answerId, 'h2');
  assert.match(wrong.evidence.quote, /tous les matins sauf le lundi/);
  assert.deepEqual(wrong.made.contribution, [], 'a pick is not the learner\'s headline');
  await assert.rejects(client.make(s.id, { kind: 'headline_choice', action: 'pick', optionId: 'zz' }), (error) => error.code === 'revue_unknown_option');
});

test('a free request: matched by words, a miss gets Romy\'s line; flag off is invisible', async () => {
  const client = createMockRevueClient({ persist: false });
  assert.equal((await client.match('la grève du métro')).match, 'evergreen-greve-transports');
  const miss = await client.match('le cinéma');
  assert.equal(miss.match, null);
  assert.match(miss.romyLineFr, /Je n'ai que ça cette semaine/);
  const off = createMockRevueClient({ persist: false, disabled: true });
  assert.deepEqual(await off.week(), { enabled: false });
});

// ---------------------------------------------------------------------------
// Phase 2 · «Les invités» (WIRE §6) and the WP-120 vignette
// ---------------------------------------------------------------------------

test('the guest: Margaux enters on the price question, disagrees once, changes her mind after the learner\'s point', async () => {
  const client = createMockRevueClient({ persist: false, band: 'B1', language: 'fr' });
  const s = await client.start();
  const facts = await client.turn(s.id, { text: "D'accord, je t'aide." });
  assert.ok(!facts.items.some((item) => item.kind === 'guest'), 'never in `facts`');
  const enter = await client.turn(s.id, { text: "Est-ce que les prix sont plus bas qu'au supermarché ?" });
  const guest = enter.items.find((item) => item.kind === 'guest');
  assert.equal(guest.castId, 'margaux_barman');
  assert.equal(guest.move, 'enter');
  assert.ok(guest.reasonFr && guest.reasonFr.length > 10, 'with her reason');
  // Order inside the turn: mine, line, uncertainty, guest.
  assert.deepEqual(enter.items.map((item) => item.kind), ['mine', 'line', 'uncertainty', 'guest']);
  assert.ok(guest.textFr.split(/\s+/).length <= 25);
  const after = await client.session(s.id);
  assert.deepEqual(after.stage.cast.map((m) => m.id), ['romy_tremblay', 'margaux_barman', 'user']);

  // A quick reply is not a point: she has nothing to add.
  const more = await client.turn(s.id, { text: "Dis-m'en plus." });
  assert.ok(!more.items.some((item) => item.kind === 'guest'));
  const disagree = await client.turn(s.id, { text: 'Mais les produits sont plus frais, non ?' });
  assert.equal(disagree.items.find((item) => item.kind === 'guest').move, 'disagree');
  const moved = await client.turn(s.id, { text: 'Les producteurs vendent eux-mêmes, alors le prix est juste.' });
  const change = moved.items.find((item) => item.kind === 'guest');
  assert.deepEqual([change.move, change.position], ['moved', 'moved']);
  const silent = await client.turn(s.id, { text: 'Et puis le marché est beau le matin.' });
  assert.ok(!silent.items.some((item) => item.kind === 'guest'), 'once moved she stays moved, and quiet');
});

test('fallback reasons: budget, no_match, model_down, knowledge_refused', async () => {
  const miss = createMockRevueClient({ persist: false });
  const started = await miss.start({ freeRequest: 'le cinéma' });
  assert.equal(started.thread.find((item) => item.kind === 'line' && item.role === 'fallback').reason, 'no_match');

  const client = createMockRevueClient({ persist: false });
  const s = await client.start();
  await client.turn(s.id, { text: "D'accord." });
  const down = await client.turn(s.id, { text: 'Et alors ? [panne]' });
  const line = down.items.find((item) => item.kind === 'line');
  assert.deepEqual([line.role, line.reason], ['fallback', 'model_down']);
  assert.match(line.textFr, /Je ne sais pas encore/);
  for (let i = 0; i < 4; i += 1) await client.turn(s.id, { text: "Dis-m'en plus." });
  const full = await client.turn(s.id, { text: 'Et les horaires ?' });
  assert.equal(full.items.find((item) => item.kind === 'line').reason, 'budget');
});

test('the rubric: plan words, the Credit check, fact fit, the register note', async () => {
  const client = createMockRevueClient({ persist: false, band: 'B1' });
  const s = await client.start();
  await client.turn(s.id, { text: "D'accord." });
  const turn = await client.turn(s.id, { text: 'Vous savez, le marché couvert a du savoir-faire.' });
  assert.equal(turn.evidence.grader, 'revue-rubric-v1');
  assert.equal(turn.evidence.words.length, 5, 'every plan word');
  assert.deepEqual(turn.evidence.words.find((w) => w.fr === 'marché couvert'), { fr: 'marché couvert', outcome: 'correct', capabilityKnown: true });
  assert.deepEqual(turn.evidence.words.find((w) => w.fr === 'savoir-faire'), { fr: 'savoir-faire', outcome: 'unscored', capabilityKnown: false }, 'never mastery for a word no can-do lists');
  assert.equal(turn.evidence.outcome, 'correct');
  assert.equal(turn.evidence.registerNote, 'vous_to_tu');
});

test('make at B1: Romy\'s intro once, headline_write (contradicted → write again; then filed), her make_done line', async () => {
  const client = createMockRevueClient({ persist: false, band: 'B1', language: 'fr' });
  const s = await client.start();
  assert.deepEqual(s.plan.makeOptions, ['headline_write', 'reader_question', 'short_report'], 'no headline to pick from B1');
  await client.turn(s.id, { text: OWN_LINE });
  const offer = await client.makeOffer(s.id);
  assert.equal(offer.recommended, 'headline_write');
  assert.deepEqual(offer.options.map((o) => o.kind), ['headline_write', 'reader_question', 'short_report']);
  await assert.rejects(client.make(s.id, { kind: 'headline_choice', action: 'pick', optionId: 'h2' }), (error) => error.code === 'revue_make_unavailable');
  assert.equal(offer.intro.role, 'make_intro');
  const again = await client.makeOffer(s.id);
  assert.deepEqual(again.intro, offer.intro, 'written once, on the first GET');
  assert.equal((await client.session(s.id)).thread.filter((item) => item.kind === 'line' && item.role === 'make_intro').length, 1, 'it replays as a thread item');

  const wrong = await client.make(s.id, { kind: 'headline_write', action: 'write', textFr: "À Aligre, le marché n'ouvre que le dimanche" });
  assert.equal(wrong.accepted, false);
  assert.equal(wrong.made, null, 'nothing filed');
  assert.equal(wrong.evidence.factFit, 'contradicted');
  assert.match(wrong.line.textFr, /Tu réessaies/);
  const right = await client.make(s.id, { kind: 'headline_write', action: 'write', textFr: 'Paris et ses 91 marchés en plein air' });
  assert.equal(right.accepted, true);
  assert.equal(right.evidence.factFit, 'supported');
  assert.equal(right.made.textFr, 'Paris et ses 91 marchés en plein air');
  assert.equal(right.line.role, 'make_done');
  const { closing } = await client.close(s.id);
  assert.equal(closing.dispatch.headlineFr, 'Paris et ses 91 marchés en plein air', 'the dispatch takes the headline as written');
  assert.deepEqual(closing.vignette.ring, 'headline');
  assert.equal(closing.vignette.keptContribution, true);
});

test('make at B1: the thirty-second report is filed; the dispatch keeps its own headline; the vignette is red', async () => {
  const client = createMockRevueClient({ persist: false, band: 'B1' });
  const s = await client.start();
  await client.turn(s.id, { text: OWN_LINE });
  const offer = await client.makeOffer(s.id);
  assert.equal(offer.options.find((o) => o.kind === 'short_report').seconds, 30);
  const transcript = "Je suis au marché d'Aligre. Il y a un marché couvert.";
  const report = await client.make(s.id, { kind: 'short_report', action: 'report', transcript, mode: 'voice' });
  assert.equal(report.made.kind, 'short_report');
  assert.equal(report.made.textFr, transcript);
  assert.equal(report.line.textFr, "C'est enregistré. Je le mets dans mon papier.");
  const { closing } = await client.close(s.id);
  assert.notEqual(closing.dispatch.headlineFr, transcript, 'a report is not a headline');
  assert.match(closing.dispatch.bodyFr[2], /Je suis au marché d'Aligre/);
  assert.equal(closing.vignette.ring, 'report');
  const list = await client.vignettes();
  assert.equal(list.length, 1);
  assert.equal(list[0].sessionId, s.id);
});

test('below B1 the phase-2 makes are absent, and refused with 409 revue_make_unavailable', async () => {
  const client = createMockRevueClient({ persist: false, band: 'A2' });
  const s = await client.start();
  await client.turn(s.id, { text: OWN_LINE });
  const offer = await client.makeOffer(s.id);
  assert.deepEqual(offer.options.map((o) => o.kind), ['headline_choice', 'reader_question']);
  await assert.rejects(
    client.make(s.id, { kind: 'headline_write', action: 'write', textFr: 'Un titre' }),
    (error) => error instanceof RevueError && error.code === 'revue_make_unavailable' && error.makeKind === 'headline_write',
  );
  const off = createMockRevueClient({ persist: false, disabled: true });
  await assert.rejects(off.vignettes(), (error) => error.code === 'revue_disabled');
});

// ---------------------------------------------------------------------------
// WP-119 §8.4 · the story's own picture: «Regarde», «La légende», the dispatch
// ---------------------------------------------------------------------------

const DESK_CAPTION = 'Un marché en plein air, un matin, entre les étals de fruits et légumes.';

test('§8.4 A2: the picture is the stage, Romy points at it, its words lead; the caption is written first, a pick only after a refused try, uncredited', async () => {
  const client = createMockRevueClient({ persist: false, band: 'A2', language: 'fr', pictures: true });
  assert.equal((await client.week()).offer.recommended.stage.plateKind, 'story');
  const s = await client.start();
  assert.deepEqual([s.stage.plateKind, s.stage.placeIsReal], ['story', true], 'the story\'s own picture: nothing stands in');
  assert.deepEqual(s.stage.pictureWords.map((word) => word.fr), ['marché couvert', 'en plein air']);
  assert.deepEqual(s.plan.vocabulary.slice(0, 2).map((word) => word.fr), ['marché couvert', 'en plein air'], 'the picture\'s words lead the vocabulary');
  const lines = s.thread.filter((item) => item.kind === 'line');
  assert.deepEqual(lines.map((item) => item.role), ['look', 'purpose'], 'Romy points at the picture instead of the place note');
  assert.match(lines[0].textFr, /^Regarde : /);
  assert.deepEqual(lines[0].glosses.map((gloss) => gloss.fr), ['marché couvert', 'en plein air']);
  assert.deepEqual(s.plan.makeOptions, ['headline_choice', 'reader_question', 'caption']);

  await client.turn(s.id, { text: OWN_LINE });
  const offer = await client.makeOffer(s.id);
  assert.equal(offer.recommended, 'caption', 'the story\'s own picture is captioned first');
  assert.match(offer.intro.textFr, /légende sous l'image/);
  const caption = offer.options.find((option) => option.kind === 'caption');
  assert.deepEqual([caption.format, caption.options, caption.maxWords], ['write', [], 12], 'written first, nothing to pick yet');
  await assert.rejects(client.make(s.id, { kind: 'caption', action: 'caption', optionId: 'l1' }), (error) => error.code === 'revue_caption_write_first');

  // Two words are not a caption at A2: Romy asks for more, and the three captions come as the way out.
  const short = await client.make(s.id, { kind: 'caption', action: 'caption', textFr: 'Un marché.' });
  assert.deepEqual([short.accepted, short.made], [false, null], 'nothing filed');
  assert.match(short.line.textFr, /Encore quelques mots/);
  assert.equal(short.options.length, 3);
  assert.ok(short.options.some((option) => option.textFr === DESK_CAPTION), 'one says what the picture shows');
  const again = (await client.makeOffer(s.id)).options.find((option) => option.kind === 'caption');
  assert.equal(again.options.length, 3, 'a resume offers the pick too');
  const answer = short.options.find((option) => option.textFr === DESK_CAPTION);
  await assert.rejects(client.make(s.id, { kind: 'caption', action: 'caption', optionId: 'zz' }), (error) => error.code === 'revue_unknown_option');
  const wrong = await client.make(s.id, { kind: 'caption', action: 'caption', optionId: short.options.find((option) => option !== answer).id });
  assert.deepEqual([wrong.accepted, wrong.correct, wrong.answerId], [true, false, answer.id]);
  assert.deepEqual([wrong.made.textFr, wrong.made.contribution], [DESK_CAPTION, []], 'a pick is not the learner\'s caption');
  assert.match(wrong.line.textFr, /On garde l'autre/);

  const { closing } = await client.close(s.id);
  assert.deepEqual(
    [closing.dispatch.pictureUrl, closing.dispatch.captionFr, closing.dispatch.captionByLearner],
    [caption.pictureUrl, DESK_CAPTION, false],
  );
  assert.notEqual(closing.dispatch.headlineFr, DESK_CAPTION, 'a caption is not a headline');
  assert.equal(closing.vignette.keptContribution, false);
  assert.match(closing.romyLineFr, /que tu as choisie/);
  assert.doesNotMatch(closing.dispatch.bylineFr, /avec toi/, 'a pick is not credited');
});

test('§8.4 A1: the learner writes the caption too; a right pick after a refused try is still not theirs', async () => {
  const client = createMockRevueClient({ persist: false, band: 'A1', language: 'de', pictures: true });
  const s = await client.start();
  assert.deepEqual(s.stage.pictureWords.map((word) => word.gloss), ['Markthalle', 'im Freien'], 'glossed in the learner\'s language');
  await client.turn(s.id, { text: OWN_LINE });
  const caption = (await client.makeOffer(s.id)).options.find((option) => option.kind === 'caption');
  assert.deepEqual([caption.format, caption.maxWords], ['write', 10]);
  const refused = await client.make(s.id, { kind: 'caption', action: 'caption', textFr: "Le marché n'ouvre que le dimanche, en plein air." });
  assert.deepEqual([refused.accepted, refused.evidence.factFit, refused.options.length], [false, 'contradicted', 3]);
  const right = await client.make(s.id, { kind: 'caption', action: 'caption', optionId: refused.options.find((option) => option.textFr === DESK_CAPTION).id });
  assert.deepEqual([right.correct, right.made.contribution], [true, []]);
  assert.match(right.line.textFr, /Celle-là dit ce qu'on voit/);
  assert.doesNotMatch(right.line.textFr, /ta légende/);
  const { closing } = await client.close(s.id);
  assert.deepEqual([closing.dispatch.captionFr, closing.dispatch.captionByLearner], [DESK_CAPTION, false]);
  assert.equal(closing.vignette.keptContribution, false);

  // Written, it is theirs: «toi» under the picture.
  const writer = createMockRevueClient({ persist: false, band: 'A1', language: 'de', pictures: true });
  const w = await writer.start();
  await writer.turn(w.id, { text: OWN_LINE });
  const filed = await writer.make(w.id, { kind: 'caption', action: 'caption', textFr: 'Un marché en plein air.' });
  assert.deepEqual([filed.accepted, filed.made.contribution], [true, [[0, 'Un marché en plein air.'.length]]]);
  assert.match(filed.line.textFr, /C'est ta légende/);
  const written = (await writer.close(w.id)).closing;
  assert.deepEqual([written.dispatch.captionByLearner, written.vignette.keptContribution], [true, true]);
  assert.match(written.dispatch.bylineFr, /avec toi/);
});

test('§8.4 B1: the caption is written with the picture\'s words; contradicted → write again; filed, it is printed as theirs', async () => {
  const client = createMockRevueClient({ persist: false, band: 'B1', language: 'en', pictures: true });
  const s = await client.start();
  assert.deepEqual(s.plan.makeOptions, ['headline_write', 'reader_question', 'short_report', 'caption']);
  await client.turn(s.id, { text: OWN_LINE });
  const offer = await client.makeOffer(s.id);
  assert.equal(offer.recommended, 'caption');
  const caption = offer.options.find((option) => option.kind === 'caption');
  assert.deepEqual([caption.format, caption.options, caption.maxWords], ['write', [], 16]);
  assert.deepEqual(caption.words.map((word) => [word.fr, word.gloss]), [['marché couvert', 'covered market'], ['en plein air', 'outdoors']]);

  const refused = await client.make(s.id, { kind: 'caption', action: 'caption', textFr: "Le marché n'ouvre que le dimanche, en plein air." });
  assert.deepEqual([refused.accepted, refused.made, refused.evidence.factFit], [false, null, 'contradicted'], 'nothing filed');
  assert.match(refused.line.textFr, /Tu réessaies/);
  assert.deepEqual(refused.options, [], 'no pick from B1');
  await assert.rejects(client.make(s.id, { kind: 'caption', action: 'caption', optionId: 'l1' }), (error) => error.code === 'revue_caption_write_first');
  const text = 'Un marché en plein air, devant le marché couvert, un matin.';
  const filed = await client.make(s.id, { kind: 'caption', action: 'caption', textFr: text });
  assert.deepEqual([filed.accepted, filed.made.learnerFr, filed.made.contribution], [true, text, [[0, text.length]]]);
  assert.deepEqual(filed.evidence.words.filter((word) => word.outcome === 'correct').map((word) => word.fr), ['marché couvert', 'en plein air']);

  const { closing } = await client.close(s.id);
  assert.deepEqual([closing.dispatch.captionFr, closing.dispatch.captionByLearner], [text, true]);
  assert.notEqual(closing.dispatch.headlineFr, text, 'a caption is not a headline');
  assert.deepEqual(closing.kept.words.filter((word) => word.used).map((word) => word.fr), ['marché couvert', 'en plein air'], 'the words the caption used are kept as used, for review');
  assert.deepEqual([closing.vignette.ring, closing.vignette.keptContribution], ['headline', true]);
});

test('§8.4 without the story\'s picture: the plate stands in, no «Regarde», no «La légende» (refused with 409)', async () => {
  const client = createMockRevueClient({ persist: false, band: 'A2' });
  const s = await client.start();
  await client.turn(s.id, { text: OWN_LINE });
  assert.deepEqual([s.stage.plateKind, s.stage.pictureWords], ['stand_in', []]);
  assert.ok(!s.thread.some((item) => item.kind === 'line' && item.role === 'look'));
  assert.ok(s.thread.some((item) => item.kind === 'line' && item.role === 'place_note'));
  assert.ok(!(await client.makeOffer(s.id)).options.some((option) => option.kind === 'caption'), 'absent, never greyed');
  await assert.rejects(
    client.make(s.id, { kind: 'caption', action: 'caption', optionId: 'l1' }),
    (error) => error instanceof RevueError && error.code === 'revue_make_unavailable' && error.makeKind === 'caption',
  );
  const { closing } = await client.close(s.id);
  assert.deepEqual([closing.dispatch.pictureUrl, closing.dispatch.captionFr], [null, null]);
});

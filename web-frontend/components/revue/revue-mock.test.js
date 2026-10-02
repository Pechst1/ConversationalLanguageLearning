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
// a replay; a retried turn is safe; the flag-off 404; one active Revue a week.

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
  assert.equal(arrive.stage.dress, 'apron');
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

test('the headline choice: exactly one supported headline; the evidence cites its quote', async () => {
  const client = createMockRevueClient({ persist: false });
  const s = await client.start();
  const offer = await client.makeOffer(s.id);
  const headline = offer.options.find((option) => option.kind === 'headline_choice');
  assert.equal(headline.options.length, 3);
  const wrong = await client.make(s.id, { kind: 'headline_choice', action: 'pick', optionId: 'h1' });
  assert.equal(wrong.correct, false);
  assert.equal(wrong.answerId, 'h2');
  assert.match(wrong.evidence.quote, /tous les matins sauf le lundi/);
  assert.deepEqual(wrong.made.contribution, [], 'a wrong pick is not the learner\'s headline');
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

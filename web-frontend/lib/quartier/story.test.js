// node --test lib/quartier/story.test.js
//
// Le Quartier · the day's story as the quarter reads it (`story.ts`): the page the server
// resolves, which question comes next, and the quarter's own copy of T1 day a for the standalone
// page, which reads no French beyond the examples it repeats.

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { OfflineStory, STAGED_DAYS, T1A_COPY, hookOf, nextTurn, pageOfCopy, storyletOf, turnsOf } = require('./story.ts');

const panel = (id) => ({ kind: 'panel', id, lines: [] });
const turn = (id, only_after = null) => ({ kind: 'turn', id, to: 'margaux_barman', only_after, panel: panel(`${id}.p`) });

/** The questions of the copy: its turns, and «Le choix» where someone asks it. */
const questions = (copy) => copy.movements.filter((m) => m.kind === 'turn' || (m.kind === 'solve' && m.mechanic === 'choix' && m.to));
/** What reads as each answer: a reply's examples; an option's label, then its examples. */
const said = (q, a) => [...(q.kind === 'solve' ? [a.label.a2] : []), ...(a.examples ?? [])];

/** A day written with «Le choix» asked as a question, the way the season writes one. */
const CHOICE_COPY = {
  episode: 't9',
  number: 9,
  day: 'a',
  title_fr: 'Essai',
  story_date_fr: 'lundi 1er mars',
  location_id: 'le_mistral',
  can_do: { en: 'Choose.', de: 'Wählen.', fr: 'Choisir.' },
  movements: [
    {
      kind: 'turn',
      id: 'a.turn1',
      to: 'augustin_de_roncourt',
      panel: { kind: 'panel', id: 'a.p6', lines: [{ who: 'augustin_de_roncourt', say: { a2: 'Et vous êtes ?' } }] },
      task: { en: 'Say who you are.', de: 'Sag, wer du bist.', fr: 'Dis qui tu es.' },
      fallback: 'c',
      replies: [
        { id: 'a', examples: ["Je suis la petite-fille d'Odile."], beats: [] },
        { id: 'c', examples: ['Bonsoir.'], beats: [] },
      ],
    },
    {
      kind: 'solve',
      id: 'a.cafe',
      mechanic: 'choix',
      to: 'margaux_barman',
      only_after: { 'a.turn1': ['a'] },
      prompt: { a2: 'Le café crème est pour toi. Tu le prends ?', native: { en: 'The café crème is for you. Will you take it?', de: 'Der Milchkaffee ist für dich. Nimmst du ihn?' } },
      task: { en: 'Take the café crème, or say no.', de: 'Nimm den Milchkaffee, oder sag nein.', fr: 'Prends le café crème, ou dis non.' },
      options: [
        { id: 'drink', label: { a2: 'Merci.', native: { en: 'Thank you.' } }, examples: ['Je le prends.'], sets: {}, beats: [{ kind: 'panel', id: 'a.cafe.drink.r1', lines: [{ who: 'margaux_barman', say: { a2: 'Bois.' } }] }] },
        { id: 'declined', label: { a2: 'Non merci.' }, sets: {}, beats: [{ kind: 'panel', id: 'a.cafe.declined.r1', silence: true }] },
      ],
    },
    { kind: 'solve', id: 'a.letter', mechanic: 'choix', prompt: { a2: 'À qui tu montres la lettre ?' }, options: [{ id: 'margaux', label: { a2: 'Margaux' }, beats: [] }] },
    { kind: 'hook', id: 'a.hook', panel: { kind: 'panel', id: 'a.p8', lines: [] } },
  ],
};

test('a question is asked only when the replies before it allow it', () => {
  const page = {
    movements: [panel('a.p1'), turn('a.turn1'), turn('a.cafe', { 'a.turn1': ['a', 'c'] }), turn('a.turn2'), turn('a.key'), { kind: 'hook', id: 'a.hook', panel: panel('a.p8') }],
    storylets: [],
  };
  assert.equal(nextTurn(page, null, {}), 'a.turn1');
  assert.equal(nextTurn(page, 'a.turn1', { 'a.turn1': 'a' }), 'a.cafe');
  assert.equal(nextTurn(page, 'a.turn1', { 'a.turn1': 'c' }), 'a.cafe');
  assert.equal(nextTurn(page, 'a.turn1', { 'a.turn1': 'b' }), 'a.turn2');
  assert.equal(nextTurn(page, 'a.cafe', { 'a.turn1': 'a', 'a.cafe': 'drink' }), 'a.turn2');
  assert.equal(nextTurn(page, 'a.key', {}), null, 'the last question closes the talk');
  assert.equal(nextTurn(page, 'a.nowhere', {}), null);
  assert.deepEqual(turnsOf(page).map((t) => t.id), ['a.turn1', 'a.cafe', 'a.turn2', 'a.key']);
  assert.equal(hookOf(page).panel.id, 'a.p8');
});

test('the copy resolves to a page the way the server resolves one: one level, one language', () => {
  assert.ok(STAGED_DAYS.includes('t1.a'));
  const en = pageOfCopy(T1A_COPY, { level: 'a2', native: 'en' });
  const de = pageOfCopy(T1A_COPY, { level: 'a2', native: 'de' });
  const b1 = pageOfCopy(T1A_COPY, { level: 'b1', native: 'de' });
  assert.equal(en.key, 't1.a');
  assert.equal(en.number, T1A_COPY.number);
  assert.equal(en.can_do_native, T1A_COPY.can_do.en);
  assert.equal(de.can_do_native, T1A_COPY.can_do.de);
  assert.deepEqual(en.movements.map((m) => m.id), T1A_COPY.movements.map((m) => m.id));
  const first = (p) => p.movements[0].lines[0];
  assert.equal(first(en).text_fr, T1A_COPY.movements[0].lines[0].say.a2);
  assert.equal(first(de).text_native, T1A_COPY.movements[0].lines[0].say.native.de);
  assert.equal(first(b1).text_native, null, 'no translations past A2');
  for (const id of ['walk_out', 'margaux_text', 'talk']) assert.ok(storyletOf(en, id), id);
  for (const p of storyletOf(en, 'talk').people) assert.ok(p.hello && p.hello.text_fr, `${p.who} says nothing as you come up`);
  const back = storyletOf(en, 'walk_out').lines.filter((l) => l.role === 'back');
  assert.ok(back.some((l) => l.during === 'a.p2') && back.some((l) => !l.during));
});

test("offline, each reply's examples read as that reply, and anything else as the fallback", async () => {
  for (const copy of [T1A_COPY, CHOICE_COPY]) {
    for (const q of questions(copy)) {
      for (const answer of q.replies ?? q.options) {
        for (const example of said(q, answer)) {
          const heard = await new OfflineStory({}, copy).answer(q.id, example);
          assert.equal(heard.reply, answer.id, `${q.id}: «${example}»`);
          assert.deepEqual(heard.beats.map((b) => b.id), [...answer.beats, ...(q.after ?? [])].map((b) => b.id));
        }
      }
      const lost = await new OfflineStory({}, copy).answer(q.id, 'Euh… bof.');
      // a choice has no fallback: it is asked again
      assert.equal(lost.reply, q.fallback ?? null, `${q.id} falls back`);
      assert.equal(lost.mend, null);
    }
  }
});

test('«Le choix» with someone to ask it is a question: they say its prompt, its options are the answers', async () => {
  const page = pageOfCopy(CHOICE_COPY, { native: 'en' });
  assert.deepEqual(page.movements.map((m) => m.id), ['a.turn1', 'a.cafe', 'a.hook'], 'a choice nobody asks is no question');
  const cafe = page.movements[1];
  assert.deepEqual([cafe.kind, cafe.to, cafe.choice, cafe.task_native], ['turn', 'margaux_barman', true, 'Take the café crème, or say no.']);
  assert.deepEqual(cafe.only_after, { 'a.turn1': ['a'] });
  assert.equal(cafe.panel.id, 'a.cafe.prompt');
  assert.deepEqual(cafe.panel.in_frame, ['margaux_barman']);
  assert.deepEqual(
    cafe.panel.lines.map((l) => [l.who, l.kind, l.text_fr, l.text_native]),
    [['margaux_barman', 'speech', 'Le café crème est pour toi. Tu le prends ?', 'The café crème is for you. Will you take it?']],
  );

  const story = new OfflineStory({}, CHOICE_COPY);
  assert.equal((await story.answer('a.turn1', "Je suis la petite-fille d'Odile.")).next, 'a.cafe');
  assert.deepEqual(await story.ask('a.cafe'), { task: 'Take the café crème, or say no.', help: ['words', 'example'] });
  assert.deepEqual((await story.help('a.cafe', 'words')).words, ['Merci.', 'Non merci.']);
  assert.equal((await story.help('a.cafe', 'example')).text, 'Merci.');
  const unclear = await story.answer('a.cafe', 'Euh… bof.');
  assert.deepEqual([unclear.reply, unclear.next, unclear.closing], [null, 'a.cafe', false], 'asked again');
  assert.deepEqual(
    unclear.beats.map((b) => [b.id, b.lines[0].who, b.lines[0].text_fr]),
    [['a.cafe.ask_again', 'margaux_barman', 'Pardon ? Le café crème est pour toi. Tu le prends ?']],
  );
  const declined = await story.answer('a.cafe', 'non merci');
  assert.deepEqual([declined.reply, declined.next, declined.closing], ['declined', null, true]);
  assert.deepEqual(declined.beats.map((b) => [b.id, b.silence]), [['a.cafe.declined.r1', true]]);
});

test('offline, the talk walks the page to its last question', async () => {
  const story = new OfflineStory();
  const turns = turnsOf(story.page);
  let at = nextTurn(story.page, null, {});
  const asked = [];
  while (at) {
    asked.push(at);
    let heard = await story.answer(at, 'Je ne sais pas.');
    if (heard.reply === null) {
      // a choice asks again until an option is taken: the first word it offers
      assert.equal(heard.next, at);
      heard = await story.answer(at, (await story.help(at, 'words')).words[0]);
    }
    assert.equal(heard.turn, at);
    assert.equal(heard.closing, heard.next === null);
    at = heard.next;
  }
  const order = turns.map((t) => t.id);
  assert.deepEqual(asked, order.filter((id) => asked.includes(id)), 'in the order of the page');
  for (const t of turns) if (!t.only_after) assert.ok(asked.includes(t.id), `${t.id} was never asked`);
});

test('offline help is an example, and the options on a choice', async () => {
  const story = new OfflineStory();
  const t = T1A_COPY.movements.find((m) => m.kind === 'turn');
  const ask = await story.ask(t.id);
  assert.ok(ask.task);
  assert.equal(ask.help[ask.help.length - 1], 'example');
  const example = await story.help(t.id, 'example');
  const fallback = t.replies.find((r) => r.id === t.fallback);
  assert.equal(example.text, fallback.examples[0]);
  assert.equal(await story.help(t.id, 'hint'), null);
  assert.equal(await story.help('a.nowhere', 'example'), null);
});

test('offline gestures: walking out is kept, a talk opens on a hello and answers in canon', async () => {
  const story = new OfflineStory({ native: 'de' });
  const out = await story.gesture({ storylet: 'walk_out', at: 'a.p2' });
  assert.equal(out.sets['user.walked_out'], true);
  const hello = await story.gesture({ storylet: 'talk', to: 'margaux_barman' });
  assert.equal(hello.beats.length, 1);
  assert.ok(hello.beats[0].lines[0].text_fr);
  assert.ok(hello.chips.length >= 1, 'help to say something');
  const told = await story.gesture({ storylet: 'talk', to: 'margaux_barman', text: 'Tu connaissais bien Odile ?' });
  assert.equal(told.heard, 'margaux.odile');
  assert.ok(told.beats[0].lines.length >= 1);
  assert.ok(told.learned.some((l) => l.id === 'margaux.odile' && l.text_native), 'what you learn, in your language');
  const away = await story.gesture({ storylet: 'margaux_text' });
  assert.deepEqual([away.beats[0].id, away.beats[0].lines[0].kind], ['margaux_text.text', 'sms']);
  assert.equal(away.sets['user.stayed_away'], true);
  const text = await story.gesture({ storylet: 'margaux_text', text: "J'arrive." });
  assert.equal(text.beats[0].id, 'margaux_text.answer');
  assert.ok(text.beats[0].lines[0].text_fr);
  assert.equal(await story.gesture({ storylet: 'talk', to: 'odile' }), null, 'nobody to talk to');
  assert.deepEqual(story.gestures.map((g) => g.storylet), ['walk_out', 'talk', 'talk', 'margaux_text', 'margaux_text', 'talk']);
});

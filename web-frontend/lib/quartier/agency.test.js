// node --test lib/quartier/agency.test.js
//
// Le Quartier · what you can do besides answer, and what the quarter remembers. These tests hold
// the agency layer to itself and to the season's canon: every route of the day changes something,
// every condition names something the quarter can actually remember, nobody speaks out of their
// register, and no line agrees an adjective with you.

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const A = require('./agency.ts');
const { Memory, eligible, matches, pick } = require('./memory.ts');
const { T1A_COPY: T1A } = require('./story.ts');
const { WORLD, worldState } = require('./world.ts');
const PARIS = require('./world/paris.json');

const CAST = Object.keys(A.PEOPLE);
/** The day's questions: its turns, and «Le choix» where someone asks it. */
const turns = T1A.movements.filter((m) => m.kind === 'turn' || (m.kind === 'solve' && m.to));
/** The café crème and the key, as the engine asks them: questions whose replies are the options. */
const CHOICES = { 'a.cafe': ['drink', 'declined', 'refused'], 'a.key': ['take', 'leave'] };

/** Every effect list the agency layer can apply. */
function allEffects() {
  const lists = [
    ...Object.values(A.REPLY_EFFECTS),
    A.LEAVE.effects,
    A.TEXT_SUITCASE.effects,
  ];
  for (const p of Object.values(A.PEOPLE)) for (const i of p.intents) lists.push(i.effects ?? []);
  return lists.flat();
}

/** Every storylet with a condition. */
function allStorylets() {
  const out = [...A.STREET_BARKS, ...A.WHILE_AWAY, ...A.NOTES];
  for (const p of Object.values(A.PEOPLE)) out.push(...p.hello, ...p.intents);
  return out;
}

/** Every line a person of the cast says in the agency layer, with who says it. */
function allLines() {
  const out = [];
  for (const p of Object.values(A.PEOPLE)) {
    for (const h of p.hello) out.push({ who: p.id, fr: h.say.fr, where: h.id });
    for (const i of p.intents) out.push({ who: p.id, fr: i.reply.fr, where: i.id });
    p.fallback.forEach((f, n) => out.push({ who: p.id, fr: f.fr, where: `${p.id}.fallback.${n}` }));
    if (p.bye) out.push({ who: p.id, fr: p.bye.fr, where: `${p.id}.bye` });
  }
  for (const k of ['asked', 'resume', 'resumeGus']) out.push({ who: A.LEAVE[k].who, fr: A.LEAVE[k].say.fr, where: `leave.${k}` });
  out.push({ who: A.TEXT_SUITCASE.who, fr: A.TEXT_SUITCASE.say.fr, where: 'text' });
  return out;
}

test('every route of the day changes something, and says so in the carnet', () => {
  const routes = turns.flatMap((t) => (t.replies ?? t.options).map((r) => `${t.id}.${r.id}`));
  for (const [turn, replies] of Object.entries(CHOICES)) for (const r of replies) routes.push(`${turn}.${r}`);
  for (const route of new Set(routes)) {
    const effects = A.REPLY_EFFECTS[route];
    assert.ok(effects && effects.length, `${route} has no effects`);
    assert.ok(effects.some((e) => e.kind === 'journal'), `${route} writes nothing in the carnet`);
  }
  for (const route of Object.keys(A.REPLY_EFFECTS)) assert.ok(routes.includes(route), `${route} is no route of the day`);
});

test('the café crème and the key each settle what the days after read', () => {
  for (const [turn, replies] of Object.entries(CHOICES)) {
    for (const r of replies) assert.ok(A.REPLY_EFFECTS[`${turn}.${r}`].some((e) => e.kind === 'fact'), `${turn}.${r}`);
  }
  const holder = (r) => A.REPLY_EFFECTS[`a.key.${r}`].find((e) => e.kind === 'item').holder;
  assert.equal(holder('take'), 'toi');
  assert.equal(holder('leave'), 'margaux_barman');
});

test('what the engine heard in a talk moves regard and the carnet, not the facts it sends itself', () => {
  assert.deepEqual(A.heardEffects('margaux_barman', null), []);
  assert.deepEqual(A.heardEffects('margaux_barman', 'no.such.line'), []);
  for (const p of Object.values(A.PEOPLE)) {
    for (const i of p.intents) {
      const kept = A.heardEffects(p.id, i.id);
      assert.ok(kept.every((e) => e.kind === 'regard' || e.kind === 'journal'), i.id);
      assert.equal(kept.length, (i.effects ?? []).filter((e) => e.kind === 'regard' || e.kind === 'journal').length, i.id);
    }
  }
});

test('a conversation answers in its own register, and the slip comes first, once', () => {
  const gus = A.respond('augustin_de_roncourt', 'Tu viens souvent ici ?', {});
  assert.equal(gus.lines[0].say, A.PEOPLE.augustin_de_roncourt.slip);
  assert.equal(gus.intent, 'gus.zinc');
  const again = A.respond('augustin_de_roncourt', 'Tu viens souvent ici ?', {}, { slipped: true });
  assert.equal(again.lines.length, 1);
  const lila = A.respond('lila_bonnet', 'Vous habitez ici ?', {});
  assert.equal(lila.lines[0].say, A.PEOPLE.lila_bonnet.slip);
  assert.equal(lila.intent, 'lila.home');
  const margaux = A.respond('margaux_barman', 'Bonjour, ça va ?', {}, { turn: 1 });
  assert.equal(margaux.intent, null);
  assert.equal(margaux.lines[0].say, A.PEOPLE.margaux_barman.fallback[1]);
});

test('what Margaux tells you, Lila hears about; the fire stays unsaid', () => {
  const m = new Memory(false);
  const deflect = A.respond('margaux_barman', 'Pourquoi elle est partie ?', m.state());
  assert.notEqual(deflect.intent, 'margaux.why_left', 'only once Odile has come up');
  const told = A.respond('margaux_barman', 'Tu connaissais bien Odile ?', m.state());
  assert.equal(told.intent, 'margaux.odile');
  m.apply('t1a', told.effects);
  assert.equal(m.state()['knows.margaux.odile'], true);
  const why = A.respond('margaux_barman', 'Pourquoi elle est partie ?', m.state());
  assert.equal(why.intent, 'margaux.why_left');
  assert.equal(why.lines[0].say.fr, "J'ai rien entendu.");
  const lila = A.respond('lila_bonnet', "Margaux m'a parlé d'Odile.", m.state());
  assert.equal(lila.intent, 'lila.margaux_spoke');
  m.apply('t1a', lila.effects);
  assert.equal(A.respond('lila_bonnet', "Margaux m'a parlé d'Odile.", m.state()).intent, 'lila.odile', 'the surprise plays once');
});

test('the chips offer what may play now, three at most, each once', () => {
  const chips = A.chipsFor('lila_bonnet', { 'regard.lila_bonnet': 1 });
  assert.ok(chips.length <= 3);
  assert.equal(new Set(chips).size, chips.length);
  assert.ok(chips.includes("Et moi, j'ai combien sur vingt ?"));
  assert.ok(!A.chipsFor('margaux_barman', {}).includes('Pourquoi elle est partie ?'));
  assert.ok(A.chipsFor('margaux_barman', { 'knows.margaux.odile': true }).includes('Pourquoi elle est partie ?'));
  for (const who of CAST) assert.ok(A.chipsFor(who, {}).length >= 1, `${who} offers nothing to say`);
});

test('every condition names something the quarter can remember', () => {
  const facts = new Map();
  const learned = new Set();
  const holders = new Set(['toi']);
  for (const e of allEffects()) {
    if (e.kind === 'fact') {
      if (!facts.has(e.key)) facts.set(e.key, new Set());
      facts.get(e.key).add(e.value);
    } else if (e.kind === 'learn') learned.add(e.key);
    else if (e.kind === 'item') holders.add(e.holder);
  }
  for (const p of Object.values(A.PEOPLE)) for (const i of p.intents) if (i.once) facts.set(`seen.${i.id}`, new Set([true]));
  const worldIds = new Set(WORLD.places.map((p) => p.id));
  for (const s of allStorylets()) {
    for (const [key, want] of Object.entries(s.when ?? {})) {
      const [head, ...rest] = key.split('.');
      const tail = rest.join('.');
      if (['visits', 'rain', 'night'].includes(key)) continue;
      if (head === 'regard' || head === 'met') assert.ok(CAST.includes(tail), `${s.id}: ${key}`);
      else if (head === 'world') {
        assert.ok(worldIds.has(tail), `${s.id}: ${key}`);
        for (const v of [want].flat()) if (typeof v === 'string') assert.ok(['open', 'en_chantier', 'locked'].includes(v), `${s.id}: ${key} = ${v}`);
      } else if (head === 'place') assert.ok(A.PLACES[tail], `${s.id}: ${key}`);
      else if (head === 'item') {
        assert.ok(A.ITEMS[tail], `${s.id}: ${key}`);
        for (const v of [want].flat()) if (typeof v === 'string') assert.ok(holders.has(v), `${s.id}: nobody ever holds ${tail} as ${v}`);
      } else if (head === 'knows') assert.ok(learned.has(tail), `${s.id}: nothing teaches ${tail}`);
      else {
        assert.ok(facts.has(key), `${s.id}: nothing sets ${key}`);
        for (const v of [want].flat()) if (typeof v !== 'object') assert.ok(facts.get(key).has(v), `${s.id}: ${key} is never ${v}`);
      }
    }
  }
});

test('nobody speaks out of their register (but for the line about it)', () => {
  for (const l of allLines()) {
    const want = A.PEOPLE[l.who]?.register;
    if (!want) continue;
    const reg = A.registerOf(l.fr);
    assert.ok(reg === null || reg === want, `${l.where}: ${l.who} says ${reg} in «${l.fr}»`);
  }
  // strangers in the street say vous
  for (const b of A.STREET_BARKS) assert.notEqual(A.registerOf(b.say.fr), 'tu', b.id);
});

test('no line agrees an adjective with you, and Camille is never gendered', () => {
  const aboutYou = [
    ...Object.values(A.REPLY_EFFECTS).flat(),
    ...allEffects(),
  ]
    .filter((e) => e.kind === 'journal' || e.kind === 'learn')
    .map((e) => e.words.fr);
  aboutYou.push(...A.WHILE_AWAY.map((b) => b.say.fr), ...A.NOTES.map((b) => b.say.fr), ...A.STREET_BARKS.map((b) => b.say.fr));
  aboutYou.push(A.MOMENT.caption.fr, A.LEAVE.asked.say.fr, A.LEAVE.resume.say.fr, A.TEXT_SUITCASE.say.fr);
  for (const who of CAST) for (let r = -3; r <= 3; r++) aboutYou.push(A.regardWords(who, r).fr);
  // what follows «tu es», «t'es», «te voilà»… must not be a word that takes your gender
  const toiIs = /\b(?:tu es|tu étais|tu seras|t'es|tu sembles|tu as l'air|tu restes|tu deviens|te voilà|te revoilà)\s+(?:(?:si|très|trop|bien|pas|plus|encore|déjà|vraiment)\s+)*([a-zàâçéèêëîïôûùüÿœ'-]+)/gi;
  const gendered = /^(?:.*(?:é|ée|és|ées)|(?:parti|partie|venu|venue|seul|seule|prêt|prête|perdu|perdue|content|contente|sûr|sûre|franc|franche|gentil|gentille|heureux|heureuse|nouveau|nouvelle|petit|petite|grand|grande)s?)$/i;
  for (const fr of aboutYou) {
    for (const m of fr.matchAll(toiIs)) assert.doesNotMatch(m[1], gendered, `«${fr}»`);
    assert.doesNotMatch(fr, /\b(petite-fille|petit-fils|héritière|héritier)\b/i, `«${fr}»`);
  }
  for (const l of allLines().filter((x) => x.who !== 'margaux_barman')) assert.doesNotMatch(l.fr, /\b(petite-fille|petit-fils)\b/i, l.where);
  const camille = [...allEffects().filter((e) => e.kind === 'learn' && e.who === 'camille_marchand').map((e) => e.words.fr), ...A.NOTES.filter((n) => n.who === 'camille_marchand').map((n) => n.say.fr)];
  for (const fr of camille) assert.doesNotMatch(fr, /\b(il|elle|lui-même|elle-même)\b/i, `«${fr}»`);
});

test('Odile never speaks, and the painter of the picture is never named', () => {
  for (const l of allLines()) assert.notEqual(l.who, 'odile');
  const every = JSON.stringify(A);
  assert.doesNotMatch(every, /«\s*L\.\s*»|\bL\. [A-Z]|peintre|painter|Maler/);
});

test('the memory keeps facts, regard, objects and days apart', () => {
  const m = new Memory(false);
  m.apply('t1a', [
    { kind: 'fact', key: 't1.told', value: 'family' },
    { kind: 'regard', who: 'lila_bonnet', delta: 2 },
    { kind: 'regard', who: 'lila_bonnet', delta: 3 },
    { kind: 'item', id: 'cle_cigale', holder: 'toi' },
    { kind: 'journal', words: { fr: 'un', en: 'one', de: 'eins' } },
    { kind: 'learn', key: 'x', words: { fr: 'x', en: 'x', de: 'x' } },
  ]);
  m.apply('roam', [
    { kind: 'item', id: 'cle_cigale', holder: 'margaux_barman' },
    { kind: 'journal', words: { fr: 'deux', en: 'two', de: 'zwei' } },
    { kind: 'learn', key: 'x', words: { fr: 'x again', en: 'x', de: 'x' } },
    { kind: 'meet', who: 'marin_leveque' },
    { kind: 'place', id: 'marche_aligre', status: 'noticed' },
  ]);
  assert.equal(m.regard('lila_bonnet'), 3, 'regard is held between -3 and 3');
  assert.equal(m.holder('cle_cigale'), 'margaux_barman');
  assert.deepEqual(m.journal().map((j) => j.words.fr), ['deux', 'un']);
  assert.equal(m.known().length, 1);
  const s = m.state();
  assert.equal(s['t1.told'], 'family');
  assert.equal(s['item.cle_cigale'], 'margaux_barman');
  assert.equal(s['met.marin_leveque'], true);
  assert.equal(s['place.marche_aligre'], 'noticed');
  m.beginDay('t1a');
  assert.equal(m.state()['t1.told'], undefined, 'replaying the day forgets what the day did');
  assert.equal(m.holder('cle_cigale'), 'margaux_barman', 'and keeps what happened after');
  m.clear();
  assert.equal(m.entries.length, 0);
});

test('conditions read the way the pilot writes them', () => {
  const s = { 't1.told': 'family', 'regard.gus': -1, visits: 2 };
  assert.ok(matches({ 't1.told': ['family', 'nothing'] }, s));
  assert.ok(!matches({ 't1.told': 'selling' }, s));
  assert.ok(matches({ 't1.cafe': { set: false } }, s));
  assert.ok(matches({ visits: { min: 2 }, 'regard.gus': { max: -1 } }, s));
  assert.ok(matches({ 'regard.marin_leveque': 0 }, s), 'a regard nobody moved is 0');
  const list = [
    { id: 'a', salience: 1 },
    { id: 'b', salience: 3, once: true },
    { id: 'c', salience: 2, when: { visits: { min: 5 } } },
  ];
  assert.deepEqual(eligible(list, s).map((x) => x.id), ['b', 'a']);
  assert.equal(pick(list, { ...s, 'seen.b': true }).id, 'a');
});

test('the world has every place it names, on the map of Paris', () => {
  const ids = WORLD.places.map((p) => p.id);
  assert.equal(new Set(ids).size, ids.length);
  for (const p of WORLD.places) {
    for (const k of ['fr', 'en', 'de']) {
      assert.ok(p.name[k], `${p.id} name.${k}`);
      assert.ok(p.why[k], `${p.id} why.${k}`);
    }
    assert.ok(p.lat > 48.81 && p.lat < 48.91 && p.lon > 2.22 && p.lon < 2.47, `${p.id} is not in Paris`);
    assert.ok(['open', 'en_chantier', 'locked'].includes(p.status));
    if (p.kind === 'news') assert.equal(p.source?.kind, 'papier', `${p.id}: a news place says which Papier asked for it`);
    if (p.status === 'open' && p.kind !== 'home') assert.ok(p.site, `${p.id} is open with no site`);
  }
  for (const place of Object.values(A.BARK_PLACES)) assert.ok(ids.includes(place) && A.PLACES[place], place);
  assert.equal(worldState()['world.quai_de_valmy'], 'open');
  assert.equal(PARIS.arr.length, 20);
  assert.ok(PARIS.canal.open.length >= 1 && PARIS.canal.covered.length >= 1);
});

test('every line has its two translations', () => {
  const words = [];
  const walk = (x) => {
    if (!x || typeof x !== 'object') return;
    if (typeof x.fr === 'string' && 'en' in x && 'de' in x) words.push(x);
    else Object.values(x).forEach(walk);
  };
  walk(A);
  assert.ok(words.length > 100);
  for (const w of words) for (const k of ['fr', 'en', 'de']) assert.ok(typeof w[k] === 'string' && w[k].trim(), `${JSON.stringify(w)} has no ${k}`);
});

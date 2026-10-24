// node --test lib/quartier/course-talk.test.js
//
// Le Quartier · race day's words. The window reads a bet the way it is said («deux euros gagnant
// sur le sept»), takes the money and hands a ticket over; the regular tells the Papier's facts;
// the race is called with the winner at the post; and the canon holds: the clerk and the regular
// say vous, and nothing they say agrees with Toi.

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

require(path.join(__dirname, '..', '..', 'node_modules/sucrase/register/ts'));

const { atRail, atWindow, callRace, newRegular, newWindow, payout, readBet, windowHello, RACE_BARKS } = require('./course-talk.ts');
const { fieldOf } = require('./hippodrome.ts');

const spec = { name: { fr: "Prix de l'Arc de Triomphe", en: "Prix de l'Arc de Triomphe", de: "Prix de l'Arc de Triomphe" }, metres: 2400, hour: '16 h 05', runners: 16, seed: 2026 };
const raceOf = () => {
  const { runners, holder } = fieldOf(spec);
  return { spec, runners, holder, result: null };
};

test('a bet is read the way it is said', () => {
  assert.deepEqual(readBet('Deux euros gagnant sur le sept, s’il vous plaît.'), { horse: 7, kind: 'gagnant', stake: 2 });
  assert.deepEqual(readBet('Le 12 placé, 5 €'), { horse: 12, kind: 'place', stake: 5 });
  assert.deepEqual(readBet('un pari gagnant sur le 3'), { horse: 3, kind: 'gagnant', stake: null });
  assert.deepEqual(readBet('Placé.'), { horse: null, kind: 'place', stake: null });
  assert.deepEqual(readBet('Sur le numéro neuf'), { horse: 9, kind: null, stake: null });
});

test('the field: sixteen runners, last year’s winner the favourite, the same for a seed', () => {
  const a = fieldOf(spec);
  const b = fieldOf(spec);
  assert.equal(a.runners.length, 16);
  assert.deepEqual(a, b);
  const fav = a.runners.slice().sort((x, y) => x.odds - y.odds)[0];
  assert.equal(fav.n, a.holder);
  assert.equal(new Set(a.runners.map((r) => r.odds)).size, 16);
});

test('at the window: bonjour, a bet, the money, a ticket; and a winning ticket pays', () => {
  const race = raceOf();
  const c = newWindow();
  let r = atWindow(c, 'Bonjour !', race);
  assert.match(r.lines[0].say.fr, /numéro/);
  r = atWindow(c, 'Deux euros gagnant sur le 9, s’il vous plaît.', race);
  assert.equal(c.owing, 2);
  assert.match(r.lines[0].say.fr, /Ça fait 2 €/);
  r = atWindow(c, 'Voilà.', race);
  assert.deepEqual(c.ticket, { horse: 9, kind: 'gagnant', stake: 2, odds: race.runners[8].odds });
  assert.ok(r.effects.some((e) => e.kind === 'journal' && /Tu as joué 2 € gagnant sur le 9/.test(e.words.fr)));
  race.result = [9].concat(race.runners.map((x) => x.n).filter((n) => n !== 9));
  r = atWindow(c, 'Voilà mon ticket.', race);
  assert.ok(c.paid);
  assert.equal(payout(c.ticket, race.result), 2 * (race.runners[8].odds + 1));
  assert.ok(r.effects.some((e) => e.kind === 'journal' && /Tu as gagné/.test(e.words.fr)));
});

test('the window notices a missing bonjour and a tu, and keeps to its sixteen runners', () => {
  const race = raceOf();
  const c = newWindow();
  let r = atWindow(c, 'Le 7 gagnant', race);
  assert.match(r.lines[0].say.fr, /Bonjour d’abord/);
  assert.ok(r.effects.some((e) => e.kind === 'fact' && e.value === 'forgot'));
  r = atWindow(c, 'Tu me mets le 20 ?', race);
  assert.ok(r.lines.some((l) => /On ne se connaît pas/.test(l.say.fr)));
  assert.ok(r.lines.some((l) => /que seize partants/.test(l.say.fr)));
});

test('the clerk remembers a missing bonjour the next time, until you say it', () => {
  const race = raceOf();
  const c = newWindow(true);
  assert.match(windowHello(c, race).say.fr, /pas de bonjour/);
  const r = atWindow(c, 'Bonjour ! Le 5 gagnant, deux euros.', race);
  assert.match(r.lines[0].say.fr, /c’est mieux/);
  assert.ok(r.effects.some((e) => e.kind === 'fact' && e.key === 'hippodrome_longchamp.guichetiere.bonjour' && e.value === 'said'));
  assert.equal(c.slighted, false);
  assert.doesNotMatch(windowHello(newWindow(), race).say.fr, /pas de bonjour/);
});

test('the regular tells the article’s facts, and you learn them', () => {
  const race = raceOf();
  const g = newRegular(race, 0.3);
  const r = atRail(g, 'La course fait combien de mètres ?', race);
  assert.match(r.lines[0].say.fr, /Deux mille quatre cents mètres/);
  assert.ok(r.effects.some((e) => e.kind === 'learn' && /2 400 mètres/.test(e.words.fr)));
  assert.match(atRail(g, 'Qui est le favori ?', race).lines[0].say.fr, /accélération/);
  assert.match(atRail(g, 'Il y a combien d’argent à gagner ?', race).lines[0].say.fr, /Cinq millions/);
});

test('the race is called from the off to the finish, the winner at the post', () => {
  const race = raceOf();
  const finish = race.runners.map((r) => r.n).reverse();
  const calls = callRace(race, () => finish, 23, 41, finish);
  assert.match(calls[0].say.fr, /Ils sont partis/);
  const post = calls.find((c) => c.at === 41);
  assert.match(post.say.fr, new RegExp(`Le ${finish[0]} gagne`));
  assert.match(calls[calls.length - 1].say.fr, new RegExp(`Arrivée : le ${finish[0]}, le ${finish[1]}, le ${finish[2]}`));
  calls.forEach((c, i) => i && assert.ok(c.at >= calls[i - 1].at, 'in order'));
});

test('the canon: the clerk and the regular say vous, and nothing agrees with Toi', () => {
  const race = raceOf();
  const said = [];
  const c = newWindow();
  ['Bonjour', 'C’est qui, le favori ?', 'Ça veut dire quoi, placé ?', 'Le 4', 'gagnant', 'Voilà', 'Au revoir'].forEach((t) => atWindow(c, t, race).lines.forEach((l) => said.push(l.say.fr)));
  const back = newWindow(true);
  said.push(windowHello(back, race).say.fr);
  atWindow(back, 'Bonjour', race).lines.forEach((l) => said.push(l.say.fr));
  const g = newRegular(race, 0.7);
  ['Bonjour', 'Vous jouez qui ?', 'Et les chevaux japonais ?', 'Seize partants ?', 'Merci, bonne course'].forEach((t) => atRail(g, t, race).lines.forEach((l) => said.push(l.say.fr)));
  RACE_BARKS.forEach((b) => said.push(b.fr));
  said.forEach((line) => {
    assert.doesNotMatch(line, /\b(tu|te|ton|ta|tes|toi)\b/i, `«${line}» says tu`);
    assert.doesNotMatch(line, /\b(prêt|prête|venu|venue|content|contente|seul|seule)\b/i, `«${line}» agrees with Toi`);
  });
});

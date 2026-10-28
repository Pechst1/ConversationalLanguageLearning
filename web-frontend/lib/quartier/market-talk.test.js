// node --test lib/quartier/market-talk.test.js
//
// Le Quartier · buying at the market in your own French. These tests hold the stallholders to
// their arithmetic (what you asked for, what it costs, the change), to their manners (bonjour,
// vous, no haggling over fruit), to what they remember of you, and to the canon: they say vous,
// and nothing they say agrees an adjective with you.

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const T = require('./market-talk.ts');
const { GOODS } = require('./market.ts');
const { registerOf } = require('./agency.ts');

const name = (fr) => ({ fr, en: fr, de: fr });
const primeur = () => T.newSale('primeur', 'marche_aligre', name('Le primeur'), T.TRADES.primeur, GOODS.fruits.slice(0, 4));
const fromager = () => T.newSale('fromagere', 'marche_aligre', name('La fromagère'), T.TRADES.fromager, GOODS.fromages);
const brocante = () => T.newSale('brocanteur', 'marche_aligre', name('Le brocanteur'), T.TRADES.brocanteur, GOODS.brocante);
const said = (turn) => turn.lines.map((l) => l.say.fr).join(' ');

test('numbers are said the French way', () => {
  const cases = { 1: 'un', 16: 'seize', 17: 'dix-sept', 21: 'vingt et un', 22: 'vingt-deux', 70: 'soixante-dix', 71: 'soixante et onze', 77: 'soixante-dix-sept', 80: 'quatre-vingts', 81: 'quatre-vingt-un', 91: 'quatre-vingt-onze', 100: 'cent', 200: 'deux cents', 250: 'deux cent cinquante' };
  Object.keys(cases).forEach((n) => assert.equal(T.frenchNumber(Number(n)), cases[n]));
  assert.equal(T.frenchNumber(1, true), 'une');
  assert.equal(T.sayEuros(350), 'trois euros cinquante');
  assert.equal(T.sayEuros(100), 'un euro');
  assert.equal(T.sayEuros(280), 'deux euros quatre-vingts');
  assert.equal(T.sayEuros(80), 'quatre-vingts centimes');
  assert.equal(T.showEuros(350), '3,50 €');
  assert.equal(T.showEuros(700), '7 €');
  assert.equal(T.centsOf('3,50 €'), 350);
  assert.equal(T.centsOf('26 €'), 2600);
});

test('numbers and money are read back from what you type', () => {
  const n = (s) => T.numbersIn(s).map((x) => x.n);
  assert.deepEqual(n('deux cents grammes'), [200]);
  assert.deepEqual(n('quatre-vingt-dix'), [90]);
  assert.deepEqual(n('vingt et un'), [21]);
  assert.deepEqual(n('trois cent cinquante'), [350]);
  assert.deepEqual(n('2,5 kilos'), [2.5]);
  assert.equal(T.moneyIn('voila dix euros'), 1000);
  assert.equal(T.moneyIn('cinq euros cinquante'), 550);
  assert.equal(T.moneyIn('un billet de vingt'), 2000);
  assert.equal(T.moneyIn('20 €'), 2000);
  assert.equal(T.moneyIn('un kilo de pommes'), null);
});

test('an amount is read in the unit the ware is sold by, or questioned', () => {
  const [clem] = GOODS.fruits;
  const kaki = GOODS.fruits.find((w) => w.label === 'Kakis');
  assert.deepEqual(T.amountIn('un kilo de clementines', clem), { amount: { grams: 1000 } });
  assert.deepEqual(T.amountIn('un kilo et demi de clementines', clem), { amount: { grams: 1500 } });
  assert.deepEqual(T.amountIn('un demi-kilo', clem), { amount: { grams: 500 } });
  assert.deepEqual(T.amountIn('500 grammes', clem), { amount: { grams: 500 } });
  assert.deepEqual(T.amountIn('trois kakis', kaki), { amount: { pieces: 3 } });
  assert.ok('wrong' in T.amountIn('deux clementines', clem));
  assert.equal(T.amountIn('des clementines', clem), null);
  assert.equal(T.costOf(clem, { grams: 1500 }), 530);
  assert.equal(T.costOf(kaki, { pieces: 3 }), 300);
  const poches = GOODS.livres.find((w) => w.label === 'Poches');
  assert.equal(T.costOf(poches, { pieces: 4 }), 300);
});

test('a sale: bonjour, an order, the total, a note and the change', () => {
  const s = primeur();
  let r = T.sell(s, 'Bonjour ! Je voudrais deux kilos de clémentines, s’il vous plaît.', {});
  assert.match(said(r), /^Deux kilos de clémentines, voilà\. Et avec ceci \?$/);
  assert.equal(s.bag.length, 1);
  assert.equal(s.bag[0].cents, 700);
  assert.ok(r.effects.some((e) => e.kind === 'fact' && e.key === 'marche_aligre.primeur.bonjour' && e.value === 'said'));
  r = T.sell(s, "C'est tout, merci.", {});
  // the bonjour earns a clementine, free
  assert.match(said(r), /une clémentine en plus/);
  assert.match(said(r), /ça fait sept euros\.$/);
  r = T.sell(s, 'Voilà dix euros.', {});
  assert.match(said(r), /Sur dix euros… je vous rends trois euros\./);
  const journal = r.effects.find((e) => e.kind === 'journal');
  assert.ok(journal, 'the purchase goes into the carnet');
  assert.match(journal.words.fr, /^Chez le primeur, tu as acheté deux kilos de clémentines/);
  assert.ok(r.effects.some((e) => e.kind === 'fact' && e.key === 'marche_aligre.primeur.bought'));
  assert.equal(s.owing, null);
  assert.equal(s.bag.length, 0);
});

test('without bonjour, you are told so, and it is remembered', () => {
  const s = primeur();
  const r = T.sell(s, "C'est combien, les pommes ?", {});
  assert.match(said(r), /^Bonjour quand même ! Les pommes \? Deux euros quatre-vingts le kilo\.$/);
  assert.ok(r.effects.some((e) => e.kind === 'fact' && e.value === 'forgot'));
  assert.ok(r.effects.some((e) => e.kind === 'learn' && e.key === 'market.bonjour' && e.from === 'Le primeur'));
  // the next visit opens on it
  const hello = T.helloOf(primeur(), { 'marche_aligre.primeur.bonjour': 'forgot' });
  assert.equal(hello.id, 'primeur.forgot');
  assert.equal(T.helloOf(primeur(), { 'marche_aligre.primeur.bought': 'Pommes' }).id, 'primeur.again');
  assert.equal(T.helloOf(primeur(), {}).id, 'primeur.hello');
});

test('a price for an amount is said, not weighed; a yes puts it in the bag', () => {
  const s = primeur();
  let r = T.sell(s, 'Bonjour, combien pour un kilo et demi de pommes ?', {});
  assert.match(said(r), /Un kilo et demi de pommes \? Quatre euros vingt\./);
  assert.equal(s.bag.length, 0);
  r = T.sell(s, "Oui, s'il vous plaît.", {});
  assert.equal(s.bag.length, 1);
  assert.equal(s.bag[0].cents, 420);
});

test('two clementines: they go by weight, and the stallholder suggests a kilo', () => {
  const s = primeur();
  let r = T.sell(s, 'Bonjour, deux clémentines.', {});
  assert.match(said(r), /c'est au poids\. Un kilo de clémentines \?/);
  r = T.sell(s, 'Oui.', {});
  assert.equal(s.bag[0].cents, 350);
});

test('tu to a stallholder gets a smile, once', () => {
  const s = primeur();
  const r = T.sell(s, 'Bonjour, tu as des poires ?', {});
  assert.match(said(r), /On se connaît \?/);
  assert.ok(r.effects.some((e) => e.kind === 'learn' && e.key === 'market.vous'));
  const r2 = T.sell(s, 'Tu as des pommes ?', {});
  assert.doesNotMatch(said(r2), /On se connaît/);
});

test('no haggling over fruit; haggling at the brocante, down to a price, never below half', () => {
  const s = primeur();
  T.sell(s, 'Bonjour', {});
  const r = T.sell(s, 'Vous me faites un prix ?', {});
  assert.match(said(r), /les prix sont sur l’ardoise/);
  const b = brocante();
  T.sell(b, 'Bonjour ! Combien, cette lampe ?', {});
  let h = T.sell(b, 'Huit euros ?', {});
  assert.ok(b.haggle, 'a price is on the table');
  assert.ok(b.haggle.counter >= 750 && b.haggle.counter < 1500);
  const counter = b.haggle.counter;
  h = T.sell(b, `D'accord pour ${T.sayEuros(counter)}.`, {});
  assert.equal(b.haggle, null);
  assert.equal(b.bag[0].cents, counter);
  assert.equal(b.bag[0].asked, 1500);
  assert.ok(h.effects.some((e) => e.kind === 'fact' && e.key === 'marche_aligre.brocanteur.haggled'));
  T.sell(b, "C'est tout.", {});
  const paid = T.sell(b, 'Tenez.', {});
  const j = paid.effects.find((e) => e.kind === 'journal');
  assert.match(j.words.fr, /Tu as marchandé/);
  // an offer far too low is refused
  const c = brocante();
  T.sell(c, 'Bonjour', {});
  const low = T.sell(c, 'Je vous en donne deux euros pour la lampe.', {});
  assert.match(said(low), /quand même/);
  assert.ok(c.haggle.counter >= 750);
});

test('what the Papier says, they know; and they send you to the right stall', () => {
  const s = fromager();
  T.sell(s, 'Bonjour', {});
  let r = T.sell(s, "C'est ouvert l'après-midi ?", {});
  assert.match(said(r), /toute la journée/);
  assert.ok(r.effects.some((e) => e.kind === 'learn' && e.key === 'aligre.beauvau'));
  r = T.sell(s, 'Vous êtes là le lundi ?', {});
  assert.match(said(r), /sauf le lundi/);
  r = T.sell(s, 'Vous avez des clémentines ?', {});
  assert.match(said(r), /primeur/);
  const p = primeur();
  T.sell(p, 'Bonjour', {});
  r = T.sell(p, 'Il y a beaucoup de marchés à Paris ?', {});
  assert.match(said(r), /Quatre-vingt-onze/);
});

test('walking off with the bag gets you called back', () => {
  const s = primeur();
  T.sell(s, 'Bonjour, un kilo de poires.', {});
  const r = T.sell(s, 'Au revoir !', {});
  assert.match(said(r), /^Eh ! Ça fait trois euros vingt !$/);
  assert.equal(s.owing, 320);
});

test('money held out before the total: they reckon it up and give the change', () => {
  const s = brocante();
  T.sell(s, 'Bonjour monsieur. C’est combien, la lampe ?', {});
  T.sell(s, 'Vous me la faites à dix euros ?', {});
  T.sell(s, 'D’accord, je la prends.', {});
  assert.equal(s.owing, null);
  const r = T.sell(s, 'Voilà vingt euros.', {});
  assert.match(said(r), /^Alors… ça fait treize euros\. Sur vingt euros… je vous rends sept euros\. Merci ! Bonne journée\.$/);
  assert.ok(r.effects.some((e) => e.kind === 'journal'));
  assert.equal(s.bag.length, 0);
});

test('a thing they sell but have not brought today is not given another’s price', () => {
  const T2 = T.newSale('fromagere', 'marche_aligre', name('La fromagère'), T.TRADES.fromager, GOODS.fromages.slice(0, 1), GOODS.fromages);
  T.sell(T2, 'Bonjour madame, deux cents grammes de comté.', {});
  const r = T.sell(T2, 'Combien coûte le chèvre ?', {});
  assert.match(said(r), /^Du chèvre \? Pas aujourd'hui, je n'en ai plus\. Mais j'ai du comté\.$/);
  assert.equal(T2.focus.label, 'Comté');
});

test('what they know of Aligre, they say only at Aligre', () => {
  const elsewhere = T.newSale('primeur', 'marche_bastille', name('Le primeur'), T.TRADES.primeur, GOODS.fruits.slice(0, 4));
  T.sell(elsewhere, 'Bonjour !', {});
  const r = T.sell(elsewhere, 'Vous êtes là tous les jours ?', {});
  assert.doesNotMatch(said(r), /sauf le lundi/);
  assert.ok(T.chipsOf(elsewhere, {}).indexOf('Vous êtes là tous les jours ?') < 0);
  const here = primeur();
  T.sell(here, 'Bonjour !', {});
  assert.match(said(T.sell(here, 'Vous êtes là tous les jours ?', {})), /sauf le lundi/);
});

test('a goodbye ends the talk', () => {
  const s = primeur();
  T.sell(s, 'Bonjour !', {});
  const r = T.sell(s, 'Merci, au revoir !', {});
  assert.equal(r.done, true);
});

test('the chips follow the sale', () => {
  const s = primeur();
  assert.deepEqual(T.chipsOf(s, {}).slice(0, 1), ['Bonjour !']);
  T.sell(s, 'Bonjour, des pommes', {});
  assert.match(T.chipsOf(s, {})[0], /Un kilo de pommes, s'il vous plaît\./);
  T.sell(s, 'Oui', {});
  assert.equal(T.chipsOf(s, {})[0], "C'est tout, merci.");
  T.sell(s, "C'est tout", {});
  assert.match(T.chipsOf(s, {})[0], /^Voilà cinq euros\.$/);
});

test('every line a stallholder can say keeps to vous and never agrees with you', () => {
  const lines = [];
  Object.keys(T.TRADES).forEach((k) => {
    const tr = T.TRADES[k];
    tr.hello.forEach((h) => lines.push(h.say.fr));
    tr.cries.forEach((c) => lines.push(c.fr));
    tr.fallback.forEach((f) => lines.push(f.fr));
    tr.knows.forEach((x) => lines.push(x.say.fr));
    if (tr.taste) lines.push(tr.taste.yes.fr, tr.taste.no.fr, ...(tr.taste.offer ? [tr.taste.offer.fr] : []));
    if (tr.extra) lines.push(tr.extra.say.fr);
  });
  T.MARKET_BARKS.forEach((b) => lines.push(b.say.fr));
  lines.forEach((l) => {
    assert.notEqual(registerOf(l), 'tu', `«${l}» says tu`);
    // no «vous êtes nouveau/nouvelle», «content(e) de vous voir»: an adjective about you would have to agree
    assert.doesNotMatch(l, /vous (êtes|etes) (nouveau|nouvelle|perdu|perdue|sûr|sûre|pressé|pressée)|content de vous|contente de vous/i, l);
  });
});

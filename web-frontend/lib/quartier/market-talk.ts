/**
 * Le Quartier · buying at the market, in your own French.
 *
 * What a stallholder makes of what you type: which of their wares you mean, how much of it (un
 * kilo, deux cents grammes, trois roses, un kilo et demi), what that comes to, what you hand over
 * and the change. Like `agency.ts` it reads patterns where the app would ask a model, and answers
 * through the same effects into the same memory. A stallholder has no script: a sale is a small
 * state (what you asked about, what is in the bag, what you owe, a price on the table at the
 * brocante), so you may ask a price and walk off, change your mind, buy three things, pay with a
 * note and count the change, haggle where haggling is done, refuse a taste, or forget to say
 * bonjour and be told so. And they remember: the next time, the greeting is about last time.
 *
 * Stallholders say vous to you and never agree an adjective with you; you are «la personne qui…»
 * at most. What they know about the market is the Papier's («Le marché du dimanche à Aligre»,
 * claims c1 to c3), and nothing more: where the sources are silent (are the prices lower than at
 * the supermarket?), so are they.
 */
import { fold, registerOf } from './agency';
import { matches } from './memory';
import type { Effect, Storylet, Value, Words } from './memory';
import type { GoodsKind, Ware } from './market';

const w = (fr: string, en: string, de: string): Words => ({ fr, en, de });

/* ------------------------------------------------------------------------------------------ */
/* numbers and money                                                                          */
/* ------------------------------------------------------------------------------------------ */

const UNITS = ['zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix', 'onze', 'douze', 'treize', 'quatorze', 'quinze', 'seize'];
const TENS = ['', 'dix', 'vingt', 'trente', 'quarante', 'cinquante', 'soixante'];

/** A whole number from 0 to 999 in French words, hyphenated the traditional way («vingt et un», «quatre-vingts»). */
export function frenchNumber(n: number, feminine = false): string {
  if (n < 0 || n > 999 || Math.floor(n) !== n) return String(n);
  if (n === 1) return feminine ? 'une' : 'un';
  if (n <= 16) return UNITS[n];
  if (n < 20) return `dix-${UNITS[n - 10]}`;
  if (n < 70) {
    const t = Math.floor(n / 10);
    const u = n % 10;
    if (u === 0) return TENS[t];
    if (u === 1) return `${TENS[t]} et ${feminine ? 'une' : 'un'}`;
    return `${TENS[t]}-${UNITS[u]}`;
  }
  if (n < 80) return n === 71 ? 'soixante et onze' : `soixante-${frenchNumber(n - 60)}`;
  if (n < 100) return n === 80 ? 'quatre-vingts' : `quatre-vingt-${frenchNumber(n - 80, feminine)}`;
  const h = Math.floor(n / 100);
  const r = n % 100;
  const head = h === 1 ? 'cent' : `${UNITS[h]} cent${r === 0 ? 's' : ''}`;
  return r === 0 ? head : `${head} ${frenchNumber(r, feminine)}`;
}

/** An amount as a stallholder says it: «trois euros cinquante», «un euro», «quatre-vingts centimes». */
export function sayEuros(cents: number): string {
  const e = Math.floor(cents / 100);
  const c = Math.round(cents % 100);
  if (e === 0) return `${frenchNumber(c)} centime${c > 1 ? 's' : ''}`;
  const euros = `${frenchNumber(e)} euro${e > 1 ? 's' : ''}`;
  return c ? `${euros} ${frenchNumber(c)}` : euros;
}

/** An amount as a slate writes it: «3,50 €», «7 €». */
export function showEuros(cents: number): string {
  const e = Math.floor(cents / 100);
  const c = Math.round(cents % 100);
  return c ? `${e},${c < 10 ? '0' : ''}${c} €` : `${e} €`;
}

const enEuros = (cents: number) => (cents % 100 ? `€${(cents / 100).toFixed(2)}` : `€${cents / 100}`);

/** A slate's price («3,50 €») in cents. */
export function centsOf(price: string): number {
  const m = /(\d+)(?:,(\d{1,2}))?/.exec(price);
  if (!m) return 0;
  return Number(m[1]) * 100 + (m[2] ? Number(m[2].length === 1 ? `${m[2]}0` : m[2]) : 0);
}

const NUMBER_WORDS: Record<string, number> = {
  un: 1,
  une: 1,
  deux: 2,
  trois: 3,
  quatre: 4,
  cinq: 5,
  six: 6,
  sept: 7,
  huit: 8,
  neuf: 9,
  dix: 10,
  onze: 11,
  douze: 12,
  treize: 13,
  quatorze: 14,
  quinze: 15,
  seize: 16,
  vingt: 20,
  vingts: 20,
  trente: 30,
  quarante: 40,
  cinquante: 50,
  soixante: 60,
  cent: 100,
  cents: 100,
};

/** The words of folded text, hyphens split («quatre-vingt-dix» is three words). */
function wordsOf(t: string) {
  return t
    .replace(/[^a-z0-9,.'\- ]/g, ' ')
    .replace(/-/g, ' ')
    .split(/\s+/)
    .map((tok) => (/^\d+([.,]\d+)?$/.test(tok) ? tok : tok.replace(/^[.,]+|[.,]+$/g, '')))
    .filter(Boolean);
}

/**
 * Every number said in the text, in order, with where it ends: digits («250», «2,5») or words
 * («deux cents», «quatre-vingt-dix», «vingt et un», «un kilo et demi» gives 1 then the half).
 */
export function numbersIn(t: string): Array<{ n: number; start: number; end: number }> {
  return numbersOfWords(wordsOf(t));
}

function numbersOfWords(words: string[]): Array<{ n: number; start: number; end: number }> {
  const out: Array<{ n: number; start: number; end: number }> = [];
  let i = 0;
  while (i < words.length) {
    const tok = words[i];
    if (/^\d+([.,]\d+)?$/.test(tok)) {
      out.push({ n: Number(tok.replace(',', '.')), start: i, end: i + 1 });
      i++;
      continue;
    }
    if (NUMBER_WORDS[tok] === undefined) {
      i++;
      continue;
    }
    let total = 0;
    let current = 0;
    let j = i;
    let last = 0;
    while (j < words.length) {
      const v = NUMBER_WORDS[words[j]];
      if (v === undefined) {
        // «vingt et un», «soixante et onze»
        if (words[j] === 'et' && j + 1 < words.length && (words[j + 1] === 'un' || words[j + 1] === 'une' || words[j + 1] === 'onze') && current >= 20) {
          j++;
          continue;
        }
        break;
      }
      if (v === 100) current = (current || 1) * 100;
      else if (v === 20 && last === 4 && current % 100 === 4) current += 76;
      else current += v;
      last = v;
      j++;
    }
    total += current;
    out.push({ n: total, start: i, end: j });
    i = j;
  }
  return out;
}

/** A sum of money in what you say: «dix euros», «un billet de vingt», «20 €», «cinq euros cinquante». */
export function moneyIn(t: string): number | null {
  const words = wordsOf(t.replace(/€/g, ' euros '));
  const nums = numbersOfWords(words);
  for (let k = 0; k < nums.length; k++) {
    const { n, start, end } = nums[k];
    if (/^(euros?|eur)$/.test(words[end] ?? '')) {
      let cents = Math.round(n * 100);
      // «cinq euros cinquante»
      const after = nums[k + 1];
      if (after && after.start === end + 1 && after.n < 100 && Math.floor(after.n) === after.n) cents += after.n;
      return cents;
    }
    // «un billet de vingt», «une pièce de deux»
    if (/billet|piece/.test(words.slice(Math.max(0, start - 3), start).join(' '))) return Math.round(n * 100);
  }
  return null;
}

/* ------------------------------------------------------------------------------------------ */
/* the wares as words                                                                          */
/* ------------------------------------------------------------------------------------------ */

interface Noun {
  /** one and several, in the three languages; `f`: feminine in French */
  one: [string, string, string];
  many: [string, string, string];
  f?: boolean;
  /** «des clémentines», «du comté»: what you ask for without a number */
  some: string;
}

const N = (one: [string, string, string], many: [string, string, string], some: string, f = false): Noun => ({ one, many, some, f });

/** The words for each ware (by its slate label), for the sentences a sale makes. */
export const NOUNS: Record<string, Noun> = {
  Clémentines: N(['clémentine', 'clementine', 'Clementine'], ['clémentines', 'clementines', 'Clementinen'], 'des clémentines', true),
  Pommes: N(['pomme', 'apple', 'Apfel'], ['pommes', 'apples', 'Äpfel'], 'des pommes', true),
  Poires: N(['poire', 'pear', 'Birne'], ['poires', 'pears', 'Birnen'], 'des poires', true),
  Raisin: N(['grappe de raisin', 'bunch of grapes', 'Traube'], ['grappes de raisin', 'bunches of grapes', 'Trauben'], 'du raisin', true),
  Kakis: N(['kaki', 'persimmon', 'Kaki'], ['kakis', 'persimmons', 'Kakis'], 'des kakis'),
  Bananes: N(['banane', 'banana', 'Banane'], ['bananes', 'bananas', 'Bananen'], 'des bananes', true),
  Poireaux: N(['botte de poireaux', 'bunch of leeks', 'Bund Lauch'], ['bottes de poireaux', 'bunches of leeks', 'Bund Lauch'], 'des poireaux', true),
  Carottes: N(['carotte', 'carrot', 'Karotte'], ['carottes', 'carrots', 'Karotten'], 'des carottes', true),
  'Pommes de terre': N(['pomme de terre', 'potato', 'Kartoffel'], ['pommes de terre', 'potatoes', 'Kartoffeln'], 'des pommes de terre', true),
  Potiron: N(['potiron', 'pumpkin', 'Kürbis'], ['potirons', 'pumpkins', 'Kürbisse'], 'du potiron'),
  'Choux-fleurs': N(['chou-fleur', 'cauliflower', 'Blumenkohl'], ['choux-fleurs', 'cauliflowers', 'Blumenkohlköpfe'], 'des choux-fleurs'),
  Champignons: N(['champignon', 'mushroom', 'Pilz'], ['champignons', 'mushrooms', 'Pilze'], 'des champignons'),
  Salades: N(['salade', 'lettuce', 'Salat'], ['salades', 'lettuces', 'Salate'], 'de la salade', true),
  Bouquets: N(['bouquet', 'bunch of flowers', 'Strauß'], ['bouquets', 'bunches of flowers', 'Sträuße'], 'des fleurs'),
  Chrysanthèmes: N(['pot de chrysanthèmes', 'pot of chrysanthemums', 'Topf Chrysanthemen'], ['pots de chrysanthèmes', 'pots of chrysanthemums', 'Töpfe Chrysanthemen'], 'des chrysanthèmes'),
  Roses: N(['rose', 'rose', 'Rose'], ['roses', 'roses', 'Rosen'], 'des roses', true),
  'Olives vertes': N(['olive verte', 'green olive', 'grüne Olive'], ['olives vertes', 'green olives', 'grüne Oliven'], 'des olives vertes', true),
  'Olives noires': N(['olive noire', 'black olive', 'schwarze Olive'], ['olives noires', 'black olives', 'schwarze Oliven'], 'des olives noires', true),
  Tapenade: N(['pot de tapenade', 'jar of tapenade', 'Glas Tapenade'], ['pots de tapenade', 'jars of tapenade', 'Gläser Tapenade'], 'de la tapenade'),
  Comté: N(['morceau de comté', 'piece of Comté', 'Stück Comté'], ['morceaux de comté', 'pieces of Comté', 'Stücke Comté'], 'du comté'),
  Brie: N(['part de brie', 'slice of Brie', 'Stück Brie'], ['parts de brie', 'slices of Brie', 'Stücke Brie'], 'du brie', true),
  Chèvre: N(['chèvre', 'goat cheese', 'Ziegenkäse'], ['chèvres', 'goat cheeses', 'Ziegenkäse'], 'du chèvre'),
  'Tout à 2 €': N(['petit vase', 'little vase', 'kleine Vase'], ['petits vases', 'little vases', 'kleine Vasen'], 'des petits objets'),
  Lampes: N(['lampe', 'lamp', 'Lampe'], ['lampes', 'lamps', 'Lampen'], 'une lampe', true),
  Livres: N(['livre', 'book', 'Buch'], ['livres', 'books', 'Bücher'], 'des livres'),
  Poches: N(['livre de poche', 'paperback', 'Taschenbuch'], ['livres de poche', 'paperbacks', 'Taschenbücher'], 'des livres de poche'),
  Assiettes: N(['assiette', 'plate', 'Teller'], ['assiettes', 'plates', 'Teller'], 'des assiettes', true),
  Verres: N(['verre', 'glass', 'Glas'], ['verres', 'glasses', 'Gläser'], 'des verres'),
  Vinyles: N(['vinyle', 'record', 'Schallplatte'], ['vinyles', 'records', 'Schallplatten'], 'des vinyles'),
};

const nounOf = (ware: Ware): Noun => NOUNS[ware.label] ?? N([ware.fr, ware.en, ware.de], [ware.fr, ware.en, ware.de], ware.fr);

/** How a ware is sold, from its slate: by weight (per kilo or per 100 g), or by the piece (or lot). */
type Sold = { by: 'weight'; per: number } | { by: 'piece'; lot: number };

function soldOf(ware: Ware): Sold {
  const u = fold(ware.unit);
  if (/kilo/.test(u)) return { by: 'weight', per: 1000 };
  if (/100 ?g/.test(u)) return { by: 'weight', per: 100 };
  if (/quatre/.test(u)) return { by: 'piece', lot: 4 };
  if (/six/.test(u)) return { by: 'piece', lot: 6 };
  return { by: 'piece', lot: 1 };
}

/** The slate's terms in the other two languages. */
function unitWords(ware: Ware): [string, string] {
  const u = fold(ware.unit);
  if (/kilo/.test(u)) return ['a kilo', 'das Kilo'];
  if (/100 ?g/.test(u)) return ['per 100 g', 'pro 100 g'];
  if (/botte/.test(u)) return ['a bunch', 'das Bund'];
  if (/bouquet/.test(u)) return ['a bunch', 'der Strauß'];
  if (/pot/.test(u)) return ['each', 'pro Stück'];
  if (/part/.test(u)) return ['a slice', 'das Stück'];
  if (/quatre/.test(u)) return ['for four', 'für vier'];
  if (/six/.test(u)) return ['for six', 'für sechs'];
  return ['each', 'das Stück'];
}

/** «Les clémentines ? Trois euros cinquante le kilo.» */
export function priceWords(ware: Ware): Words {
  const cents = centsOf(ware.price);
  const [en, de] = unitWords(ware);
  return w(`${cap(ware.fr)} ? ${cap(ware.say)}.`, `The ${ware.en}? ${enEuros(cents)} ${en}.`, `${cap(ware.de)}? ${showEuros(cents)} ${de}.`);
}

const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);

/** An amount of a ware: what you asked for, in grams or pieces. */
export interface Amount {
  grams?: number;
  pieces?: number;
}

/** The amount in words: «deux kilos de clémentines», «trois cents grammes de champignons», «une rose». */
export function amountWords(ware: Ware, a: Amount): Words {
  const n = nounOf(ware);
  if (a.grams !== undefined) {
    const g = a.grams;
    const de = n.some.replace(/^(des|du|de la|une|un) /, '');
    const of = /^[aeiouyhéèê]/i.test(de) ? 'd’' : 'de ';
    let fr: string;
    if (g === 500) fr = `une livre ${of}${de}`;
    else if (g % 1000 === 0) fr = `${frenchNumber(g / 1000)} kilo${g > 1000 ? 's' : ''} ${of}${de}`;
    else if (g > 1000 && g % 1000 === 500) fr = `${frenchNumber(Math.floor(g / 1000))} kilo${g > 2000 ? 's' : ''} et demi ${of}${de}`;
    else fr = `${frenchNumber(g)} grammes ${of}${de}`;
    const wt = g >= 1000 ? `${g / 1000} kg` : `${g} g`;
    return w(fr, `${wt} of ${ware.en}`, `${wt.replace('.', ',')} ${ware.de}`);
  }
  const k = a.pieces ?? 1;
  return w(`${frenchNumber(k, n.f)} ${k > 1 ? n.many[0] : n.one[0]}`, `${k} ${k > 1 ? n.many[1] : n.one[1]}`, `${k} ${k > 1 ? n.many[2] : n.one[2]}`);
}

/** What an amount of a ware costs, in cents (weights to the nearest ten cents, as on a market scale). */
export function costOf(ware: Ware, a: Amount): number {
  const price = centsOf(ware.price);
  const sold = soldOf(ware);
  if (sold.by === 'weight') return Math.round((((a.grams ?? 0) / sold.per) * price) / 10) * 10;
  const lots = Math.ceil((a.pieces ?? 1) / sold.lot);
  return lots * price;
}

/** Which of these wares the text names (the longest name wins: «pommes de terre» before «pommes»). */
export function wareIn(t: string, wares: readonly Ware[]): Ware | null {
  let best: Ware | null = null;
  let len = 0;
  wares.forEach((ware) => {
    ware.match.forEach((m) => {
      if (m.length > len && t.indexOf(m) >= 0) {
        best = ware;
        len = m.length;
      }
    });
  });
  return best;
}

/**
 * How much of `ware` the text asks for. `null`: no amount said. `wrong`: an amount the ware is not
 * sold by (two clementines, when they go by the kilo), with what the stallholder suggests instead.
 */
export function amountIn(t: string, ware: Ware): { amount: Amount } | { wrong: Amount } | null {
  const sold = soldOf(ware);
  const words = wordsOf(t);
  const nums = numbersIn(t);
  // «un demi-kilo», «une livre de», «un kilo et demi»
  const half = /\bdemi[- ]?kilo|\bune livre (de|d')/.test(t);
  if (half && sold.by === 'weight') return { amount: { grams: 500 } };
  for (let k = 0; k < nums.length; k++) {
    const { n, end } = nums[k];
    const unit = words[end] ?? '';
    const andHalf = words[end + 1] === 'et' && /^demie?$/.test(words[end + 2] ?? '');
    if (/^(kilos?|kg|kilogrammes?)$/.test(unit)) {
      const grams = Math.round((n + (andHalf ? 0.5 : 0)) * 1000);
      return sold.by === 'weight' ? { amount: { grams } } : { wrong: { pieces: 1 } };
    }
    if (/^(grammes?|g|gr)$/.test(unit)) return sold.by === 'weight' ? { amount: { grams: Math.round(n) } } : { wrong: { pieces: 1 } };
    if (/^(euros?|eur)$/.test(unit)) continue;
    // a number on its own, or before the name: pieces
    if (n > 0 && n < 100 && Math.floor(n) === n) {
      if (sold.by === 'piece') return { amount: { pieces: n } };
      return { wrong: sold.per === 1000 ? { grams: 1000 } : { grams: 200 } };
    }
  }
  return null;
}

/* ------------------------------------------------------------------------------------------ */
/* the stallholders                                                                           */
/* ------------------------------------------------------------------------------------------ */

export interface Said {
  say: Words;
  mood?: string;
  direction?: string;
}

export interface Hello extends Storylet {
  say: Words;
  mood?: string;
  /** they offer you a taste */
  taste?: boolean;
}

/** A fact they know, from the Papier, and how they put it. */
export interface Know extends Storylet {
  chip?: string;
  match: RegExp;
  say: Words;
  /** a fact about one place (its days, its hall), said only there; without one, true of any market */
  place?: string;
  /** what you learn (into the carnet's «Ce que tu sais») */
  learn?: { key: string; words: Words };
}

/** A kind of stallholder: how they greet, call out, haggle (or not), and what they know. */
export interface Trade {
  goods: GoodsKind[];
  hello: Hello[];
  /** calls to the street, besides each ware's own price */
  cries: Words[];
  /** a price can be discussed here */
  haggles: boolean;
  /** a taste is offered at the first hello (of a ware on the stall), with the offer if the hello does not make it */
  taste?: { of: string; offer?: Words; yes: Words; no: Words };
  /** something extra in the bag when you said bonjour */
  extra?: { ware: string; say: Words };
  knows: Know[];
  fallback: Words[];
}

/* the Papier's claims, as a stallholder says them */
const C1: Know = {
  id: 'c1',
  chip: 'Il y a beaucoup de marchés à Paris ?',
  match: /combien de marches|beaucoup de marches|d'autres marches|marches (a|de|dans) paris|les marches de paris/,
  say: w("Quatre-vingt-onze, à Paris. Mais celui-ci, c'est le mien.", 'Ninety-one, in Paris. But this one is mine.', 'Einundneunzig, in Paris. Aber dieser hier ist meiner.'),
  learn: { key: 'paris.markets', words: w('Paris compte quatre-vingt-onze marchés.', 'Paris has ninety-one markets.', 'Paris hat einundneunzig Märkte.') },
};
const C2: Know = {
  id: 'c2',
  place: 'marche_aligre',
  chip: 'Vous êtes là tous les jours ?',
  match: /tous les jours|tous les matins|ouvert|ouvre|ferme|quand|lundi|dimanche|samedi|horaire|demain|la semaine|chaque jour/,
  say: w('Tous les matins, sauf le lundi.', 'Every morning except Monday.', 'Jeden Morgen außer montags.'),
  learn: { key: 'aligre.days', words: w("Le marché d'Aligre a lieu tous les matins, sauf le lundi.", 'The Aligre market is on every morning except Monday.', 'Der Markt in Aligre findet jeden Morgen statt, außer montags.') },
};
const C3: Know = {
  id: 'c3',
  place: 'marche_aligre',
  chip: "C'est ouvert l'après-midi ?",
  match: /apres-?midi|toute la journee|le soir|ce soir|jusqu'a quelle heure|ouvert|ouvre|ferme|quand|horaire/,
  salience: 1,
  say: w("Sous la halle, c'est ouvert toute la journée. Dehors, seulement le matin.", 'Under the hall roof, it is open all day. Outside, only in the morning.', 'In der Halle ist den ganzen Tag offen. Draußen nur vormittags.'),
  learn: {
    key: 'aligre.beauvau',
    words: w("Le marché Beauvau, le marché couvert, est ouvert toute la journée ; le marché dehors, seulement le matin.", 'The Marché Beauvau, the covered market, is open all day; the outdoor market only in the morning.', 'Der Marché Beauvau, die Markthalle, hat den ganzen Tag offen; der Markt draußen nur vormittags.'),
  },
};
const HALL: Know = {
  id: 'hall',
  place: 'marche_aligre',
  chip: "C'est quoi, la halle ?",
  match: /halle|marche couvert|beauvau|ce batiment|la grande maison/,
  say: w("C'est le marché Beauvau. Le marché couvert d'Aligre.", "It's the Marché Beauvau. Aligre's covered market.", 'Das ist der Marché Beauvau. Die Markthalle von Aligre.'),
  learn: { key: 'aligre.hall', words: w("Le marché couvert d'Aligre s'appelle le marché Beauvau.", "Aligre's covered market is called the Marché Beauvau.", 'Die Markthalle von Aligre heißt Marché Beauvau.') },
};

const lastTime = (key: string, value: Value | { set: boolean }) => ({ [key]: value });

export const TRADES: Record<string, Trade> = {
  primeur: {
    goods: ['fruits', 'legumes'],
    hello: [
      { id: 'primeur.forgot', when: lastTime('$.bonjour', 'forgot'), salience: 3, mood: 'malice', say: w('Bonjour, bonjour. Ici, on commence par là.', 'Good morning, good morning. Here, that is how we start.', 'Guten Morgen, guten Morgen. Hier fängt man damit an.') },
      { id: 'primeur.again', when: lastTime('$.bought', { set: true }), salience: 2, mood: 'joie', say: w('Ah, bonjour ! Comme la dernière fois ?', 'Ah, good morning! Same as last time?', 'Ah, guten Morgen! Wie beim letzten Mal?') },
      { id: 'primeur.hello', mood: 'joie', taste: true, say: w("Bonjour ! Qu'est-ce qu'il vous faut ?", 'Good morning! What can I get you?', 'Guten Morgen! Was darf es sein?') },
    ],
    cries: [w('Allez, allez, goûtez !', 'Come on, have a taste!', 'Na los, probieren Sie!'), w('Qui veut goûter ?', 'Who wants a taste?', 'Wer möchte probieren?')],
    haggles: false,
    taste: {
      of: 'Clémentines',
      offer: w('Tenez, goûtez une clémentine !', 'Here, taste a clementine!', 'Hier, probieren Sie eine Clementine!'),
      yes: w('Alors ? Elle est bonne, hein ?', 'Well? Good, isn’t it?', 'Na? Gut, oder?'),
      no: w('Comme vous voulez.', 'As you like.', 'Wie Sie möchten.'),
    },
    extra: { ware: 'Clémentines', say: w('Je vous mets une clémentine en plus. Pour le bonjour.', 'I’ll put in an extra clementine. For the bonjour.', 'Ich lege Ihnen eine Clementine dazu. Für das Bonjour.') },
    knows: [C2, C1, HALL],
    fallback: [w("Pardon ? Dites-moi ce qu'il vous faut.", 'Sorry? Tell me what you need.', 'Wie bitte? Sagen Sie mir, was Sie brauchen.'), w('Des fruits ? Des légumes ? Tout est sur les ardoises.', 'Fruit? Vegetables? Everything is on the slates.', 'Obst? Gemüse? Alles steht auf den Tafeln.')],
  },
  fromager: {
    goods: ['fromages', 'olives'],
    hello: [
      { id: 'fromager.forgot', when: lastTime('$.bonjour', 'forgot'), salience: 3, mood: 'malice', say: w('Bonjour… Aujourd’hui, on dit bonjour ?', 'Good morning… Are we saying good morning today?', 'Guten Morgen… Sagen wir heute guten Morgen?') },
      { id: 'fromager.again', when: lastTime('$.bought', { set: true }), salience: 2, mood: 'joie', say: w('Re-bonjour ! Alors, il était bon ?', 'Hello again! So, was it good?', 'Hallo, wieder da! Na, war er gut?') },
      { id: 'fromager.hello', mood: 'joie', taste: true, say: w('Bonjour ! Vous voulez goûter le comté ?', 'Good morning! Would you like to taste the Comté?', 'Guten Morgen! Möchten Sie den Comté probieren?') },
    ],
    cries: [w('Goûtez le comté !', 'Taste the Comté!', 'Probieren Sie den Comté!')],
    haggles: false,
    taste: {
      of: 'Comté',
      yes: w('Il a dix-huit mois. Fruité, hein ?', "It's eighteen months old. Fruity, isn't it?", 'Er ist achtzehn Monate alt. Fruchtig, oder?'),
      no: w('Une autre fois, alors.', 'Another time, then.', 'Dann ein andermal.'),
    },
    knows: [C3, C2, HALL, C1],
    fallback: [w('Pardon ? Un fromage en particulier ?', 'Sorry? A particular cheese?', 'Wie bitte? Ein bestimmter Käse?'), w('Regardez, tout est sur les ardoises.', 'Look, everything is on the slates.', 'Schauen Sie, alles steht auf den Tafeln.')],
  },
  brocanteur: {
    goods: ['brocante', 'livres', 'vaisselle', 'disques'],
    hello: [
      { id: 'brocanteur.haggled', when: lastTime('$.haggled', true), salience: 3, mood: 'malice', say: w('Ah, vous revoilà ! On discute encore les prix ?', 'Ah, you again! Haggling again?', 'Ah, Sie schon wieder! Feilschen wir wieder?') },
      { id: 'brocanteur.forgot', when: lastTime('$.bonjour', 'forgot'), salience: 2, mood: 'malice', say: w('Ah ! La personne qui ne dit pas bonjour.', "Ah! The person who doesn't say bonjour.", 'Ah! Die Person, die nicht bonjour sagt.') },
      { id: 'brocanteur.hello', say: w('Bonjour ! Regardez, regardez. Tout est à vendre.', 'Good morning! Have a look. Everything is for sale.', 'Guten Morgen! Schauen Sie nur. Alles ist zu verkaufen.') },
    ],
    cries: [w('Tout à deux euros, regardez !', 'Everything two euros, have a look!', 'Alles zwei Euro, schauen Sie!'), w('Des livres, des disques, des lampes !', 'Books, records, lamps!', 'Bücher, Platten, Lampen!')],
    haggles: true,
    knows: [{ ...C2, say: w('La brocante ? Tous les matins, sauf le lundi. Comme le marché.', 'The flea market? Every morning except Monday. Like the market.', 'Der Flohmarkt? Jeden Morgen außer montags. Wie der Markt.') }, HALL, C1],
    fallback: [w('Hm ? Montrez-moi ce qui vous plaît.', 'Hm? Show me what you like.', 'Hm? Zeigen Sie mir, was Ihnen gefällt.'), w("Ça, c'est une vraie affaire. Demandez le prix !", "That's a real bargain. Ask the price!", 'Das ist ein echtes Schnäppchen. Fragen Sie nach dem Preis!')],
  },
};

/** The trade of someone who sells these goods. */
export function tradeOf(goods: GoodsKind): Trade {
  const keys = Object.keys(TRADES);
  for (let i = 0; i < keys.length; i++) if (TRADES[keys[i]].goods.indexOf(goods) >= 0) return TRADES[keys[i]];
  return TRADES.primeur;
}

/** Where else in the market a thing is sold, for when you ask the wrong stall. */
const ELSEWHERE: Array<{ goods: GoodsKind; match: RegExp; say: Words }> = [
  { goods: 'fromages', match: /fromage|comte|brie|chevre|camembert/, say: w('Le fromage ? Sous la halle.', 'Cheese? In the covered market.', 'Käse? In der Markthalle.') },
  { goods: 'legumes', match: /legume|poireau|carotte|patate|pommes? de terre|salade|champignon|potiron|chou/, say: w('Les légumes ? Dans la rue, il y en a partout.', 'Vegetables? In the street, they are everywhere.', 'Gemüse? In der Straße, überall.') },
  { goods: 'fruits', match: /fruit|clementine|pomme\b|pommes\b|poire|raisin|banane|kaki/, say: w('Les fruits ? Au primeur, dans la rue.', 'Fruit? At the greengrocer, in the street.', 'Obst? Beim Obsthändler, in der Straße.') },
  { goods: 'brocante', match: /lampe|vase|livre|disque|vinyle|assiette|verre|brocante/, say: w('Ça ? À la brocante, sur la place.', 'That? At the flea market, on the square.', 'Das? Auf dem Flohmarkt, auf dem Platz.') },
  { goods: 'fleurs', match: /fleur|rose|bouquet|chrysantheme/, say: w('Des fleurs ? Dans la rue, vers la place.', 'Flowers? In the street, toward the square.', 'Blumen? In der Straße, Richtung Platz.') },
  { goods: 'olives', match: /olive|tapenade/, say: w('Les olives ? Dans la rue, ou sous la halle.', 'Olives? In the street, or in the covered market.', 'Oliven? In der Straße oder in der Markthalle.') },
];

/* ------------------------------------------------------------------------------------------ */
/* a sale                                                                                     */
/* ------------------------------------------------------------------------------------------ */

export interface Bagged {
  ware: Ware;
  amount: Amount;
  cents: number;
  /** haggled down from this */
  asked?: number;
}

export interface Sale {
  /** who you are buying from (their key in the place), and the place (for what they remember) */
  who: string;
  place: string;
  name: Words;
  trade: Trade;
  wares: Ware[];
  /** everything a stall of this kind sells, on the stall today or not */
  stock: Ware[];
  bag: Bagged[];
  /** the ware you are talking about (the last you asked about or bought) */
  focus: Ware | null;
  /** they asked how much of it */
  pending: { ware: Ware; suggest: Amount } | null;
  /** the total you were told and owe */
  owing: number | null;
  /** a price on the table at the brocante */
  haggle: { ware: Ware; amount: Amount; asked: number; counter: number; rounds: number } | null;
  /** a taste offered and not answered */
  offered: boolean;
  greeted: boolean;
  slipped: boolean;
  turns: number;
  paid: boolean;
}

export function newSale(who: string, place: string, name: Words, trade: Trade, wares: Ware[], stock: Ware[] = wares): Sale {
  return { who, place, name, trade, wares, stock, bag: [], focus: null, pending: null, owing: null, haggle: null, offered: false, greeted: false, slipped: false, turns: 0, paid: false };
}

/** The keys a stallholder remembers you by: `marche_aligre.primeur.bought`. */
export const memoryKey = (s: { place: string; who: string }, what: string) => `${s.place}.${s.who}.${what}`;

/** A storylet's `when` written for any stallholder (`$.bought`), made theirs. */
function whenFor(s: { place: string; who: string }, when: Storylet['when']) {
  if (!when) return when;
  const out: NonNullable<Storylet['when']> = {};
  Object.keys(when).forEach((k) => {
    out[k.replace('$', `${s.place}.${s.who}`)] = when[k];
  });
  return out;
}

/** What they say when you come up to them, from what they remember of you. */
export function helloOf(s: Sale, state: Record<string, Value>): Hello {
  const list = s.trade.hello.filter((h) => matches(whenFor(s, h.when), state)).sort((a, b) => (b.salience ?? 0) - (a.salience ?? 0));
  return list[0] ?? s.trade.hello[s.trade.hello.length - 1];
}

/** What a stallholder calls out to the street: a line of their own, or a price off a slate. */
export function cryOf(trade: Trade, wares: readonly Ware[], roll: number): Words {
  const pool: Words[] = [...trade.cries];
  wares.forEach((ware) => {
    const cents = centsOf(ware.price);
    const [en, de] = unitWords(ware);
    pool.push(w(`${cap(ware.fr)}, ${ware.say} !`, `${cap(ware.en)}, ${enEuros(cents)} ${en}!`, `${cap(ware.de)}, ${showEuros(cents)} ${de}!`));
  });
  return pool[Math.floor(roll * pool.length) % pool.length];
}

const GREET = /\b(bonjour|bonsoir|salut|coucou|bjr|hello)\b/;
const THANKS_BYE = /\b(au revoir|bonne journee|a bientot|bonne fin|a la prochaine|bonne continuation|ciao)\b/;
const DONE = /c'est tout|ca sera tout|ce sera tout|rien d'autre|c'est bon|ca ira|ca suffit|combien je vous dois|je vous dois combien|combien en tout|ca fait combien|ca me fait combien|au total|l'addition|je vais payer|je peux payer|on peut payer/;
const PRICE = /combien|quel prix|le prix|ca coute|ca vaut|c'est a combien|a combien|c'est quoi le prix|tarif/;
const WANT = /je voudrais|je veux|j'aimerais|je prends|je vais prendre|il me faut|donnez-moi|mettez-moi|je cherche|vous avez|avez-vous|est-ce que vous avez|s'il vous plait/;
const HAGGLE = /moins cher|trop cher|un prix|petit prix|reduction|rabais|un geste|ristourne|negoci|marchand|je vous en donne|je vous propose|vous me la laissez|vous me le laissez|vous me les laissez|ca va pas|c'est cher/;
const YES = /^(oui|ouais|d'accord|ok|okay|volontiers|avec plaisir|je veux bien|allez|ca marche|va pour|entendu|tope|marche conclu|parfait|tres bien|pourquoi pas)\b|\bje (la|le|les) prends\b|\bva pour\b|\bmarche conclu\b/;
const NO = /^(non|nan|pas maintenant|ca va|non merci|merci non|pas pour moi|une autre fois|tant pis|je reflechis|je vais reflechir|laissez)\b|\btant pis\b|\btrop cher\b/;
const PAY = /voila|tenez|je paie|je vous paie|par carte|carte bleue|en liquide|en especes|sans contact|la monnaie|un billet/;

export interface SaleTurn {
  lines: Said[];
  effects: Effect[];
  /** the conversation is over (a goodbye) */
  done?: boolean;
  /** what the stallholder now shows on their face */
  mood?: string;
}

const learnFrom = (s: Sale, key: string, words: Words): Effect => ({ kind: 'learn', key, words, from: s.name.fr });
const factOf = (s: Sale, what: string, value: Value): Effect => ({ kind: 'fact', key: memoryKey(s, what), value });

const sum = (bag: readonly Bagged[]) => bag.reduce((t, b) => t + b.cents, 0);

/** What `text` gets you at this stall. `sale` is changed in place: it is the stall's memory of this conversation. */
export function sell(s: Sale, text: string, state: Record<string, Value>): SaleTurn {
  const t = fold(text).trim();
  const lines: Said[] = [];
  const effects: Effect[] = [];
  const first = s.turns === 0;
  s.turns++;
  const greet = GREET.test(t);
  // bonjour first: a market is a place of manners before it is a shop
  if (greet && !s.greeted) {
    s.greeted = true;
    if (first) effects.push(factOf(s, 'bonjour', 'said'));
  } else if (first && !greet) {
    lines.push({ say: w('Bonjour quand même !', 'Good morning anyway!', 'Trotzdem guten Morgen!'), mood: 'malice', direction: 'eyebrows up' });
    effects.push(factOf(s, 'bonjour', 'forgot'));
    if (!state['knows.market.bonjour']) effects.push(learnFrom(s, 'market.bonjour', w('Au marché, on dit bonjour avant de demander quoi que ce soit.', 'At the market, you say bonjour before asking for anything.', 'Auf dem Markt sagt man bonjour, bevor man nach irgendetwas fragt.')));
  }
  // tu to a stallholder
  if (!s.slipped && registerOf(text) === 'tu') {
    s.slipped = true;
    lines.push({ say: w('On se connaît ?', 'Do we know each other?', 'Kennen wir uns?'), mood: 'malice', direction: 'smiling' });
    effects.push(factOf(s, 'tu', true));
    if (!state['knows.market.vous']) effects.push(learnFrom(s, 'market.vous', w('Avec les commerçants, on dit vous.', 'With shopkeepers, you say vous.', 'Zu Händlern sagt man vous.')));
  }

  const ware = wareIn(t, s.wares);
  // something they sell, but not on the stall today
  const gone = ware ? null : wareIn(t, s.stock.filter((x) => s.wares.indexOf(x) < 0));
  const amount = ware ? amountIn(t, ware) : s.pending ? amountIn(t, s.pending.ware) : s.focus ? amountIn(t, s.focus) : null;
  const money = moneyIn(t);
  const done = (more: Partial<SaleTurn> = {}): SaleTurn => ({ lines, effects, ...more });

  // money held out before the total: they reckon it up, then take it
  if (s.owing === null && s.bag.length && money !== null && !ware && !s.haggle && !HAGGLE.test(t) && !/\?\s*$/.test(text)) reckon(s, lines, effects);

  // paying what you owe
  if (s.owing !== null && !ware) {
    const owing = s.owing;
    if (money !== null && money < owing) {
      lines.push({ say: w(`Il manque ${sayEuros(owing - money)}.`, `You are ${enEuros(owing - money)} short.`, `Es fehlen ${showEuros(owing - money)}.`), direction: 'holding out a hand' });
      return done();
    }
    if (money !== null || PAY.test(t) || YES.test(t)) {
      const change = money !== null ? money - owing : 0;
      if (money !== null && change > 0) lines.push({ say: w(`Sur ${sayEuros(money)}… je vous rends ${sayEuros(change)}.`, `Out of ${enEuros(money)}… here's ${enEuros(change)} change.`, `Von ${showEuros(money)}… ${showEuros(change)} zurück.`), direction: 'counting the change into your hand' });
      lines.push({ say: w('Merci ! Bonne journée.', 'Thank you! Have a good day.', 'Danke! Schönen Tag noch.'), mood: 'joie' });
      effects.push(...paid(s));
      return done({ mood: 'joie' });
    }
    if (NO.test(t)) {
      s.owing = null;
      s.bag = [];
      lines.push({ say: w('Ah bon ? Bon… je remets tout.', 'Oh? Well… I’ll put it all back.', 'Ach so? Na gut… ich lege alles zurück.'), mood: 'surprise' });
      effects.push(factOf(s, 'walked', true));
      return done({ mood: 'surprise' });
    }
  }

  // a price on the table
  const h = s.haggle;
  if (h) {
    const offered = money;
    if (YES.test(t) && offered === null) {
      s.haggle = null;
      putIn(s, { ware: h.ware, amount: h.amount, cents: h.counter, asked: h.asked });
      lines.push({ say: w(`Allez, ${sayEuros(h.counter)}. Marché conclu !`, `Go on then, ${enEuros(h.counter)}. Deal!`, `Na gut, ${showEuros(h.counter)}. Abgemacht!`), mood: 'joie' });
      effects.push(factOf(s, 'haggled', true));
      return done({ mood: 'joie' });
    }
    if (offered !== null) return haggle(s, h.ware, h.amount, h.asked, offered, h.rounds + 1, lines, effects);
    if (NO.test(t)) {
      s.haggle = null;
      lines.push({ say: w('Tant pis. Elle ne bougera pas d’ici.', "Too bad. It won't go anywhere.", 'Schade. Es läuft nicht weg.'), direction: 'shrugging' });
      return done();
    }
  }

  // a haggle opened
  if (HAGGLE.test(t) || (money !== null && (ware || s.focus) && s.owing === null && !s.pending && PRICE.test(t) === false && /\?$/.test(text.trim()))) {
    if (!s.trade.haggles) {
      lines.push({ say: w('Ah non, ici, les prix sont sur l’ardoise.', 'Oh no, here the prices are on the slate.', 'Oh nein, hier stehen die Preise auf der Tafel.'), mood: 'malice' });
      if (!state['knows.market.haggle']) effects.push(learnFrom(s, 'market.haggle', w('On ne marchande pas les fruits et légumes. À la brocante, oui.', "You don't haggle over fruit and vegetables. At the flea market, you do.", 'Bei Obst und Gemüse feilscht man nicht. Auf dem Flohmarkt schon.')));
      return done({ mood: 'malice' });
    }
    const target = ware ?? s.focus ?? (s.bag.length ? s.bag[s.bag.length - 1].ware : null);
    if (!target) {
      lines.push({ say: w('Pour quoi ? Montrez-moi.', 'For what? Show me.', 'Wofür? Zeigen Sie mal.') });
      return done();
    }
    const amt = amount && 'amount' in amount ? amount.amount : { pieces: 1 };
    const asked = costOf(target, amt);
    // it was already in the bag at its price: take it out to discuss it
    s.bag = s.bag.filter((b) => b.ware !== target);
    s.owing = null;
    if (money === null) {
      const counter = roundTo(asked * 0.85, asked >= 1000 ? 100 : 50);
      s.haggle = { ware: target, amount: amt, asked, counter, rounds: 0 };
      lines.push({ say: w(`Pour vous… ${sayEuros(counter)}.`, `For you… ${enEuros(counter)}.`, `Für Sie… ${showEuros(counter)}.`), direction: 'looking you up and down' });
      return done();
    }
    return haggle(s, target, amt, asked, money, 1, lines, effects);
  }

  // the taste they offered
  if (s.offered) {
    s.offered = false;
    const taste = s.trade.taste;
    if (taste && (YES.test(t) || /^merci\b/.test(t)) && !ware) {
      lines.push({ say: taste.yes, mood: 'joie', direction: 'holding one out' });
      effects.push(factOf(s, 'tasted', true));
      return done({ mood: 'joie' });
    }
    if (taste && NO.test(t) && !ware) {
      lines.push({ say: taste.no });
      return done();
    }
  }

  // not today
  if (gone) {
    const have = s.wares.slice(0, 2);
    const but = (fr: string[], en: string[], de: string[]) => (have.length ? [` Mais j'ai ${fr.join(' et ')}.`, ` But I have ${en.join(' and ')}.`, ` Aber ich habe ${de.join(' und ')}.`] : ['', '', '']);
    const [bf, be, bd] = but(
      have.map((x) => nounOf(x).some),
      have.map((x) => x.en),
      have.map((x) => x.de),
    );
    lines.push({ say: w(`${cap(nounOf(gone).some)} ? Pas aujourd'hui, je n'en ai plus.${bf}`, `${cap(gone.en)}? Not today, I've run out.${be}`, `${cap(gone.de)}? Heute nicht, ist ausverkauft.${bd}`), direction: 'shaking their head' });
    return done();
  }

  // that is all: the total
  if (DONE.test(t) && !ware) {
    if (!s.bag.length) {
      lines.push({ say: w('Vous ne prenez rien ? Pas de souci.', 'Not taking anything? No problem.', 'Sie nehmen nichts? Kein Problem.') });
      return done();
    }
    reckon(s, lines, effects);
    return done();
  }

  // a price asked
  if (PRICE.test(t) && !WANT.test(t)) {
    const of = ware ?? s.focus;
    if (of && amount && 'amount' in amount) {
      s.focus = of;
      s.pending = { ware: of, suggest: amount.amount };
      const what = amountWords(of, amount.amount);
      const c = costOf(of, amount.amount);
      lines.push({ say: w(`${cap(what.fr)} ? ${cap(sayEuros(c))}.`, `${cap(what.en)}? ${enEuros(c)}.`, `${cap(what.de)}? ${showEuros(c)}.`) });
      return done();
    }
    if (of) {
      s.focus = of;
      lines.push({ say: priceWords(of) });
      return done();
    }
    if (!ware && /\b(ca|ceci|cela|celui-ci|celle-ci|ceux-ci|celles-ci)\b/.test(t) && s.wares.length) {
      s.focus = s.wares[0];
      lines.push({ say: priceWords(s.wares[0]) });
      return done();
    }
    const two = s.wares.slice(0, 2).map(priceWords);
    lines.push({ say: w('Tout est marqué sur les ardoises.', 'Everything is marked on the slates.', 'Alles steht auf den Tafeln.') });
    two.forEach((p) => lines.push({ say: p }));
    return done();
  }

  // asking for something
  const target = ware ?? (amount || YES.test(t) ? (s.pending?.ware ?? s.focus) : null);
  if (target) {
    s.focus = target;
    if (amount && 'amount' in amount) return give(s, target, amount.amount, lines, effects);
    if (amount && 'wrong' in amount) {
      s.pending = { ware: target, suggest: amount.wrong };
      const sold = soldOf(target);
      const how = sold.by === 'weight' ? w(`${cap(target.fr)}, c'est au poids. ${cap(amountWords(target, amount.wrong).fr)} ?`, `The ${target.en} go by weight. ${amountWords(target, amount.wrong).en}?`, `${cap(target.de)} gibt es nach Gewicht. ${amountWords(target, amount.wrong).de}?`) : w(`${cap(target.fr)}, c'est ${target.unit === 'pièce' ? 'à la pièce' : target.unit}. Combien ?`, `The ${target.en} are sold ${unitWords(target)[0]}. How many?`, `${cap(target.de)} gibt es ${unitWords(target)[1]}. Wie viele?`);
      lines.push({ say: how });
      return done();
    }
    if (s.pending && YES.test(t)) return give(s, s.pending.ware, s.pending.suggest, lines, effects);
    // named without an amount: how much?
    const sold = soldOf(target);
    const suggest: Amount = sold.by === 'weight' ? { grams: sold.per === 1000 ? 1000 : 200 } : { pieces: sold.lot };
    if (sold.by === 'piece' && sold.lot === 1 && /\b(ce|cet|cette|celui-ci|celle-ci)\b/.test(t)) return give(s, target, { pieces: 1 }, lines, effects);
    s.pending = { ware: target, suggest };
    lines.push({ say: w(`${cap(nounOf(target).some)} ? ${cap(amountWords(target, suggest).fr)} ?`, `${cap(target.en)}? ${amountWords(target, suggest).en}?`, `${cap(target.de)}? ${amountWords(target, suggest).de}?`) });
    return done();
  }

  // something sold elsewhere in the market
  for (let i = 0; i < ELSEWHERE.length; i++) {
    const e = ELSEWHERE[i];
    if (s.trade.goods.indexOf(e.goods) < 0 && e.match.test(t)) {
      lines.push({ say: e.say, direction: 'pointing' });
      return done();
    }
  }

  // what they know
  const knows = s.trade.knows.filter((k) => (!k.place || k.place === s.place) && k.match.test(t) && matches(k.when, state)).sort((a, b) => (b.salience ?? 0) - (a.salience ?? 0));
  if (knows.length) {
    const k = knows[0];
    lines.push({ say: k.say });
    if (k.learn && !state[`knows.${k.learn.key}`]) effects.push(learnFrom(s, k.learn.key, k.learn.words));
    return done();
  }

  // goodbye
  if (THANKS_BYE.test(t) || (/\bmerci\b/.test(t) && !s.bag.length && s.owing === null)) {
    if (s.bag.length || s.owing !== null) {
      const owing = s.owing ?? sum(s.bag);
      s.owing = owing;
      lines.push({ say: w(`Eh ! Ça fait ${sayEuros(owing)} !`, `Hey! That's ${enEuros(owing)}!`, `He! Das macht ${showEuros(owing)}!`), mood: 'surprise' });
      return done({ mood: 'surprise' });
    }
    lines.push({ say: w('Merci à vous. Bonne journée !', 'Thank you. Have a good day!', 'Ich danke Ihnen. Schönen Tag noch!'), mood: 'joie' });
    return done({ done: true, mood: 'joie' });
  }

  if (s.pending && NO.test(t)) {
    s.pending = null;
    lines.push({ say: w('Comme vous voulez.', 'As you like.', 'Wie Sie möchten.') });
    return done();
  }

  // a want without a ware they sell
  if (WANT.test(t)) {
    const list = s.wares.slice(0, 3).map((x) => x.fr);
    lines.push({ say: w(`J'ai ${list.join(', ')}…`, `I have ${s.wares.slice(0, 3).map((x) => x.en).join(', ')}…`, `Ich habe ${s.wares.slice(0, 3).map((x) => x.de).join(', ')}…`), direction: 'showing the crates' });
    return done();
  }

  if (greet && !lines.length) {
    lines.push({ say: w('Bonjour !', 'Good morning!', 'Guten Morgen!'), mood: 'joie' });
    return done({ mood: 'joie' });
  }
  if (!lines.length) lines.push({ say: s.trade.fallback[(s.turns - 1) % s.trade.fallback.length] });
  return done();
}

const roundTo = (cents: number, step: number) => Math.max(step, Math.round(cents / step) * step);

/** The total: what is in the bag (and, for a bonjour, one more on the house). */
function reckon(s: Sale, lines: Said[], effects: Effect[]) {
  const extra = s.trade.extra;
  if (extra && s.greeted && !s.bag.some((b) => b.ware.label === extra.ware && b.cents === 0) && s.wares.some((x) => x.label === extra.ware)) {
    const gift = s.wares.find((x) => x.label === extra.ware) as Ware;
    s.bag.push({ ware: gift, amount: { pieces: 1 }, cents: 0 });
    lines.push({ say: extra.say, mood: 'joie', direction: 'adding one to the bag' });
    effects.push(factOf(s, 'gift', true));
  }
  s.owing = sum(s.bag);
  lines.push({ say: w(`Alors… ça fait ${sayEuros(s.owing)}.`, `So… that's ${enEuros(s.owing)}.`, `Also… das macht ${showEuros(s.owing)}.`) });
}

/** Put something in the bag (the same ware twice adds up). */
function putIn(s: Sale, b: Bagged) {
  const same = s.bag.find((x) => x.ware === b.ware && x.cents > 0 && b.cents > 0 && !x.asked && !b.asked);
  if (same) {
    same.amount = same.amount.grams !== undefined ? { grams: (same.amount.grams ?? 0) + (b.amount.grams ?? 0) } : { pieces: (same.amount.pieces ?? 0) + (b.amount.pieces ?? 0) };
    same.cents += b.cents;
  } else s.bag.push(b);
  s.focus = b.ware;
  s.pending = null;
  s.owing = null;
}

/** They weigh it out (or count it) and put it in the bag. */
function give(s: Sale, ware: Ware, amount: Amount, lines: Said[], effects: Effect[]): SaleTurn {
  const sold = soldOf(ware);
  if ((amount.grams ?? 0) > 10000 || (amount.pieces ?? 0) > 40) {
    lines.push({ say: w("Vous faites une fête ? Je n'en ai pas autant !", "Throwing a party? I don't have that many!", 'Feiern Sie ein Fest? So viel habe ich nicht!'), mood: 'surprise' });
    return { lines, effects, mood: 'surprise' };
  }
  let a = amount;
  // a lot is a lot: four paperbacks, six glasses
  if (sold.by === 'piece' && sold.lot > 1 && (a.pieces ?? 1) % sold.lot !== 0) {
    a = { pieces: Math.ceil((a.pieces ?? 1) / sold.lot) * sold.lot };
    lines.push({ say: w(`C'est ${ware.unit} : je vous en mets ${frenchNumber(a.pieces ?? sold.lot, nounOf(ware).f)}.`, `They go ${unitWords(ware)[0]}: I'll give you ${a.pieces}.`, `Die gibt es nur ${unitWords(ware)[1]}: ich gebe Ihnen ${a.pieces}.`) });
  }
  const cents = costOf(ware, a);
  putIn(s, { ware, amount: a, cents });
  const what = amountWords(ware, a);
  lines.push({ say: w(`${cap(what.fr)}, voilà. Et avec ceci ?`, `${cap(what.en)}, there you go. Anything else?`, `${cap(what.de)}, bitte schön. Darf’s noch etwas sein?`), direction: sold.by === 'weight' ? 'weighing it out' : 'counting them into a bag' });
  return { lines, effects };
}

/** At the brocante: your offer against their price. They give in a little, once or twice, never below half. */
function haggle(s: Sale, ware: Ware, amount: Amount, asked: number, offer: number, rounds: number, lines: Said[], effects: Effect[]): SaleTurn {
  const step = asked >= 1000 ? 100 : 50;
  if (offer >= asked) {
    s.haggle = null;
    putIn(s, { ware, amount, cents: asked });
    lines.push({ say: w(`${cap(sayEuros(asked))}, c'est le prix. Vendu !`, `${enEuros(asked)} is the price. Sold!`, `${showEuros(asked)} ist der Preis. Verkauft!`), mood: 'joie' });
    return { lines, effects, mood: 'joie' };
  }
  const floor = s.haggle ? s.haggle.counter : asked;
  if (offer >= asked * 0.8 || (s.haggle && offer >= s.haggle.counter * 0.95)) {
    s.haggle = null;
    const price = roundTo(offer, 50);
    putIn(s, { ware, amount, cents: price, asked });
    lines.push({ say: w(`Allez… ${sayEuros(price)}. Pour vous.`, `Go on… ${enEuros(price)}. For you.`, `Na gut… ${showEuros(price)}. Für Sie.`), mood: 'joie', direction: 'sighing for show' });
    effects.push(factOf(s, 'haggled', true));
    return { lines, effects, mood: 'joie' };
  }
  if (rounds >= 3) {
    s.haggle = { ware, amount, asked, counter: floor, rounds };
    lines.push({ say: w(`Non. ${cap(sayEuros(floor))}, c'est mon dernier prix.`, `No. ${enEuros(floor)} is my last price.`, `Nein. ${showEuros(floor)} ist mein letzter Preis.`), mood: 'fache', direction: 'arms folded' });
    return { lines, effects, mood: 'fache' };
  }
  if (offer < asked * 0.5) {
    const counter = Math.min(floor, roundTo(asked * 0.9, step));
    s.haggle = { ware, amount, asked, counter, rounds };
    lines.push({ say: w(`Ah non, quand même ! ${cap(sayEuros(counter))}, pas moins.`, `Oh no, come on! ${enEuros(counter)}, not less.`, `Ach nein, also wirklich! ${showEuros(counter)}, nicht weniger.`), mood: 'fache' });
    return { lines, effects, mood: 'fache' };
  }
  const counter = Math.min(floor, roundTo((offer + asked) / 2, step));
  s.haggle = { ware, amount, asked, counter, rounds };
  lines.push({ say: w(`${cap(sayEuros(counter))}, et c'est mon dernier prix.`, `${enEuros(counter)}, and that's my last price.`, `${showEuros(counter)}, und das ist mein letzter Preis.`), direction: 'scratching their chin' });
  return { lines, effects };
}

/** You paid: what you bought goes into the carnet, and they will remember. */
function paid(s: Sale): Effect[] {
  const out: Effect[] = [];
  const bought = s.bag.filter((b) => b.cents > 0);
  const gift = s.bag.some((b) => b.cents === 0);
  if (bought.length) {
    const list = bought.map((b) => amountWords(b.ware, b.amount));
    const join = (k: 0 | 1 | 2, and: string) => {
      const parts = list.map((x) => [x.fr, x.en, x.de][k]);
      return parts.length > 1 ? `${parts.slice(0, -1).join(', ')} ${and} ${parts[parts.length - 1]}` : parts[0];
    };
    const total = s.owing ?? sum(s.bag);
    const who = s.name;
    const deal = bought.filter((b) => b.asked !== undefined);
    const saved = deal.reduce((t, b) => t + (b.asked ?? b.cents) - b.cents, 0);
    out.push({
      kind: 'journal',
      words: w(
        `Chez ${who.fr.toLowerCase()}, tu as acheté ${join(0, 'et')} (${showEuros(total)})${gift ? ', avec un petit cadeau' : ''}.${saved ? ` Tu as marchandé : ${showEuros(saved)} de moins.` : ''}`,
        `At ${who.en.toLowerCase()}'s, you bought ${join(1, 'and')} (${enEuros(total)})${gift ? ', with a little extra' : ''}.${saved ? ` You haggled ${enEuros(saved)} off.` : ''}`,
        `${who.de.replace(/^Der /, 'Beim ').replace(/^Die /, 'Bei der ').replace(/^Das /, 'Beim ')} hast du ${join(2, 'und')} gekauft (${showEuros(total)})${gift ? ', mit einer kleinen Zugabe' : ''}.${saved ? ` Du hast ${showEuros(saved)} heruntergehandelt.` : ''}`,
      ),
    });
    out.push(factOf(s, 'bought', bought[bought.length - 1].ware.label));
  }
  s.bag = [];
  s.owing = null;
  s.paid = true;
  return out;
}

/** What the sheet offers you to say next, from where the sale is. */
export function chipsOf(s: Sale, state: Record<string, Value>): string[] {
  const out: string[] = [];
  const first = s.wares[0];
  if (s.owing !== null) {
    const note = [500, 1000, 2000, 5000].find((n) => n >= (s.owing ?? 0)) ?? 5000;
    out.push(`Voilà ${sayEuros(note)}.`, 'Je peux payer par carte ?');
    return out;
  }
  if (s.haggle) {
    out.push(`D'accord pour ${sayEuros(s.haggle.counter)}.`, `${cap(sayEuros(roundTo(s.haggle.counter * 0.8, 50)))} ?`, "Non merci, c'est trop cher.");
    return out;
  }
  if (s.offered) {
    out.push('Oui, merci !', 'Non merci, ça va.');
    return out;
  }
  if (s.pending) {
    out.push(`${cap(amountWords(s.pending.ware, s.pending.suggest).fr)}, s'il vous plaît.`);
    const sold = soldOf(s.pending.ware);
    if (sold.by === 'weight') out.push(sold.per === 1000 ? 'Un kilo et demi.' : 'Cent grammes.');
    else out.push('Deux, s’il vous plaît.');
    return out;
  }
  if (s.turns === 0) {
    out.push('Bonjour !');
    if (first) out.push(`C'est combien, ${first.fr} ?`);
    return out;
  }
  if (s.bag.length) {
    out.push("C'est tout, merci.");
    const other = s.wares.find((x) => !s.bag.some((b) => b.ware === x));
    if (other) out.push(`Et ${other.ask[0]}, s'il vous plaît.`);
    return out;
  }
  if (s.trade.haggles && s.focus) out.push(`Vous me faites un prix ?`);
  if (first) out.push(`Je voudrais ${(s.focus ?? first).ask[0]}, s'il vous plaît.`);
  const know = s.trade.knows.find((k) => (!k.place || k.place === s.place) && k.chip && k.learn && !state[`knows.${k.learn.key}`]);
  if (know?.chip) out.push(know.chip);
  if (s.paid) out.push('Merci, au revoir !');
  return out.slice(0, 3);
}

/* ------------------------------------------------------------------------------------------ */
/* the market's street                                                                        */
/* ------------------------------------------------------------------------------------------ */

export interface MarketBark extends Storylet {
  say: Words;
  /** only in this place */
  place?: string;
}

/** What people in a market say as you pass (all vous; a stranger never says tu). */
export const MARKET_BARKS: MarketBark[] = [
  { id: 'm.pardon', say: w('Pardon, je passe !', 'Excuse me, coming through!', 'Entschuldigung, ich muss vorbei!') },
  { id: 'm.excuse', say: w('Excusez-moi.', 'Excuse me.', 'Entschuldigen Sie.') },
  { id: 'm.crate', say: w('Attention, ça passe !', 'Mind out, coming through!', 'Vorsicht, hier kommt was!') },
  { id: 'm.crowd', say: w('Il y a du monde, ce matin.', "It's busy this morning.", 'Ganz schön voll heute Morgen.') },
  { id: 'm.cold', when: { night: false }, say: w('Il fait frais, hein ?', "Chilly, isn't it?", 'Ganz schön frisch, oder?') },
  { id: 'm.basket', say: w('Mon panier est déjà plein.', 'My basket is already full.', 'Mein Korb ist schon voll.') },
  { id: 'm.markets', place: 'marche_aligre', salience: 1, say: w('Paris a quatre-vingt-onze marchés. Mais Aligre, c’est autre chose.', 'Paris has ninety-one markets. But Aligre is something else.', 'Paris hat einundneunzig Märkte. Aber Aligre ist etwas anderes.') },
  { id: 'm.monday', salience: 1, say: w('Heureusement, ce n’est pas lundi.', "Lucky it's not Monday.", 'Zum Glück ist nicht Montag.') },
  // the market talks about you
  { id: 'm.you.bonjour', when: { 'knows.market.bonjour': true }, salience: 2, say: w('Ici, on dit bonjour, hein.', 'Round here, we say bonjour.', 'Hier sagt man bonjour, ja.') },
  { id: 'm.you.haggle', place: 'marche_aligre', when: { 'marche_aligre.brocanteur.haggled': true }, salience: 2, say: w('C’est vous qui marchandez à la brocante ?', 'Are you the one who haggles at the flea market?', 'Sind Sie die Person, die auf dem Flohmarkt feilscht?') },
];

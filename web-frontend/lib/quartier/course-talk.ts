/**
 * Le Quartier · what is said on race day: at the betting window, by the regular at the rail,
 * in the crowd, and by the voice over the course calling the race.
 *
 * The facts are the Papier's (`2026-w40-prix-de-l-arc-de-triomphe`): sixteen runners, 2 400
 * metres at more than 60 km/h for a little over two minutes, five million euros, last year's
 * winner and its acceleration, the Japanese horses nobody is sure about. Nobody here is a real
 * person, and no horse is named: the stands read a race by its numbers.
 *
 * The canon holds: the clerk and the regular say vous; nothing agrees with Toi.
 */
import type { Effect, Words } from './memory';
import type { RaceSpec, Runner } from './hippodrome';

const w = (fr: string, en: string, de: string): Words => ({ fr, en, de });

export interface Said {
  say: Words;
  mood?: string;
}

export interface Reply {
  lines: Said[];
  effects: Effect[];
  chips: string[];
  /** a goodbye: the sheet closes after their answer */
  done?: boolean;
}

/* ---- numbers ------------------------------------------------------------------------------ */

const UNITS = ['zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix', 'onze', 'douze', 'treize', 'quatorze', 'quinze', 'seize', 'dix-sept', 'dix-huit', 'dix-neuf', 'vingt'];
const EN = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty'];
const DE = ['null', 'eins', 'zwei', 'drei', 'vier', 'fünf', 'sechs', 'sieben', 'acht', 'neun', 'zehn', 'elf', 'zwölf', 'dreizehn', 'vierzehn', 'fünfzehn', 'sechzehn', 'siebzehn', 'achtzehn', 'neunzehn', 'zwanzig'];

/** A number as the clerk says it (up to twenty in words, then figures). */
export function said(n: number, lang: keyof Words = 'fr'): string {
  const list = lang === 'fr' ? UNITS : lang === 'en' ? EN : DE;
  if (Number.isInteger(n) && n >= 0 && n <= 20) return list[n];
  const s = n.toFixed(n % 1 ? 2 : 0);
  return lang === 'en' ? s : s.replace('.', ',');
}

/** Euros, written: «7,50 €». */
function euros(n: number, lang: keyof Words = 'fr') {
  const s = n % 1 ? n.toFixed(2) : String(n);
  return lang === 'en' ? `€${s}` : `${s.replace('.', ',')} €`;
}

/** Lower case, no accents, the euro sign as a word, apostrophes as spaces. */
export function plain(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/€/g, ' euros ')
    .replace(/[’'`]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

const WORD_N: Record<string, number> = { un: 1, une: 1, deux: 2, trois: 3, quatre: 4, cinq: 5, six: 6, sept: 7, huit: 8, neuf: 9, dix: 10, onze: 11, douze: 12, treize: 13, quatorze: 14, quinze: 15, seize: 16, vingt: 20, cinquante: 50, cent: 100 };
const NUM = '(\\d+(?:[.,]\\d+)?|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize|vingt|cinquante|cent)';
const toN = (s: string) => (s in WORD_N ? WORD_N[s] : parseFloat(s.replace(',', '.')));

export interface BetAsked {
  horse: number | null;
  kind: 'gagnant' | 'place' | null;
  stake: number | null;
}

/** What a sentence at the window asks for: a number, gagnant or placé, a stake. */
export function readBet(text: string): BetAsked {
  let t = ` ${plain(text)} `;
  let stake: number | null = null;
  const st = new RegExp(`\\b${NUM}\\s*euros?\\b`).exec(t);
  if (st) {
    stake = toN(st[1]);
    t = t.replace(st[0], ' ');
  }
  let horse: number | null = null;
  const named = new RegExp(`\\b(?:le|numero|no|n°|sur)\\s+(?:numero\\s+)?${NUM}\\b`).exec(t);
  if (named) horse = toN(named[1]);
  else {
    const bare = /\b(\d{1,2})\b/.exec(t);
    if (bare) horse = parseInt(bare[1], 10);
    else {
      const word = /\b(deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize)\b/.exec(t);
      if (word) horse = WORD_N[word[1]];
    }
  }
  const kind = /\bgagnant/.test(t) ? 'gagnant' : /\bplaces?\b/.test(t) ? 'place' : null;
  return { horse, kind, stake };
}

const HELLO = /\b(bonjour|bonsoir|salut|coucou|bonne apres-midi)\b/;
const BYE = /\b(au revoir|bonne (journee|course|soiree)|a bientot|a plus|ciao)\b/;
const THANKS = /\bmerci\b/;
const TU = /\b(tu|toi|ton|ta|tes|t as|t es)\b/;
const PAY = /\b(voila|voici|tenez|je (vous )?paie|par carte|en especes|le voila)\b/;

/* ---- the betting window ------------------------------------------------------------------- */

export interface Ticket {
  horse: number;
  kind: 'gagnant' | 'place';
  stake: number;
  odds: number;
}

export interface Window {
  greeted: boolean;
  /** she remembers you came last time without a bonjour */
  slighted: boolean;
  /** the bet so far, as you asked for it */
  ask: BetAsked;
  /** the clerk named the price and waits for the money */
  owing: number | null;
  ticket: Ticket | null;
  /** your winnings are in your pocket */
  paid: boolean;
}

export interface Race {
  spec: RaceSpec;
  runners: Runner[];
  holder: number;
  /** the finish, first to last, once run */
  result: number[] | null;
}

export const newWindow = (slighted = false): Window => ({ greeted: false, slighted, ask: { horse: null, kind: null, stake: null }, owing: null, ticket: null, paid: false });

const KIND: Record<'gagnant' | 'place', Words> = {
  gagnant: w('gagnant', 'to win', 'auf Sieg'),
  place: w('placé', 'each way', 'auf Platz'),
};

/** What a ticket pays: to win, the stake at the odds and the stake back; placed, about a quarter of the odds. */
export function payout(t: Ticket, result: number[]): number {
  if (t.kind === 'gagnant') return result[0] === t.horse ? t.stake * (t.odds + 1) : 0;
  return result.slice(0, 3).indexOf(t.horse) >= 0 ? Math.round(t.stake * (1 + t.odds / 4) * 2) / 2 : 0;
}

export function oddsOf(race: Race, n: number) {
  return race.runners.find((r) => r.n === n)?.odds ?? 0;
}

/** The suggestions under the sheet, by where the bet is. */
export function windowChips(c: Window, race: Race): string[] {
  if (!c.greeted) return ['Bonjour !'];
  if (race.result) {
    if (c.ticket && !c.paid) return ['Voilà mon ticket.', 'Au revoir !'];
    return ['Merci, au revoir !'];
  }
  if (c.owing !== null) return ['Voilà.', 'Par carte, c’est possible ?'];
  if (c.ticket) return ['Merci, au revoir !', 'C’est qui, le favori ?'];
  if (c.ask.horse && !c.ask.kind) return ['Gagnant.', 'Placé.'];
  if (c.ask.kind && !c.ask.horse) return [`Sur le ${race.holder}.`, 'Sur le 9.'];
  return [`Deux euros gagnant sur le ${race.holder}, s’il vous plaît.`, 'C’est qui, le favori ?', 'Ça veut dire quoi, placé ?'];
}

/** The clerk opens the sheet: by what she remembers of your ticket. */
export function windowHello(c: Window, race: Race): Said {
  if (race.result && c.ticket && !c.paid) return { say: w('Ah, vous revoilà. Vous avez votre ticket ?', "Ah, you're back. Have you got your ticket?", 'Ah, da sind Sie wieder. Haben Sie Ihr Ticket?'), mood: 'joie' };
  if (race.result) return { say: w('La course est finie. Il y en aura d’autres !', "The race is over. There'll be others!", 'Das Rennen ist vorbei. Es gibt noch andere!') };
  if (c.ticket) return { say: w('Vous avez déjà votre ticket. Allez vite voir la course !', 'You have your ticket already. Go and watch the race!', 'Sie haben Ihr Ticket schon. Schnell, schauen Sie sich das Rennen an!') };
  if (c.slighted && !c.greeted) return { say: w('Ah, c’est vous. La dernière fois, pas de bonjour… On recommence ?', 'Ah, it’s you. Last time, no bonjour… Shall we start again?', 'Ah, Sie sind’s. Letztes Mal kein Bonjour… Fangen wir neu an?'), mood: 'malice' };
  return { say: w('Bonjour ! C’est pour un pari ?', 'Hello! Is it for a bet?', 'Guten Tag! Möchten Sie wetten?') };
}

/** What you say at the window, and what the clerk answers. */
export function atWindow(c: Window, text: string, race: Race): Reply {
  const t = plain(text);
  const lines: Said[] = [];
  const effects: Effect[] = [];
  const reply = (done = false): Reply => ({ lines, effects, chips: done ? [] : windowChips(c, race), done });
  const hello = HELLO.test(t);
  if (!c.greeted) {
    c.greeted = true;
    if (!hello) {
      lines.push({ say: w('Bonjour d’abord, peut-être…', 'Hello first, maybe…', 'Erst mal guten Tag, vielleicht…'), mood: 'malice' });
      effects.push({ kind: 'fact', key: 'hippodrome_longchamp.guichetiere.bonjour', value: 'forgot' });
    } else if (c.slighted) {
      // the grudge ends with the bonjour she was owed
      c.slighted = false;
      lines.push({ say: w('Bonjour ! Voilà, c’est mieux.', 'Hello! There, that’s better.', 'Guten Tag! So ist es besser.'), mood: 'joie' });
      effects.push({ kind: 'fact', key: 'hippodrome_longchamp.guichetiere.bonjour', value: 'said' });
    }
  }
  if (TU.test(t)) lines.push({ say: w('On ne se connaît pas, il me semble. Mais je vous écoute.', "We don't know each other, I think. But go on.", 'Wir kennen uns nicht, glaube ich. Aber bitte.'), mood: 'surprise' });

  // after the race: the ticket, and what it pays
  if (race.result) {
    const r = race.result;
    if (c.ticket && !c.paid) {
      const tk = c.ticket;
      const won = payout(tk, r);
      c.paid = true;
      if (won > 0) {
        lines.push({
          say: w(
            `Le ${tk.horse} ${KIND[tk.kind].fr} : bravo ! ${said(tk.stake)} euros à ${tk.odds} contre 1… ça vous fait ${euros(won)}.`,
            `Number ${tk.horse} ${KIND[tk.kind].en}: well done! ${euros(tk.stake, 'en')} at ${tk.odds} to 1… that's ${euros(won, 'en')} for you.`,
            `Die ${tk.horse} ${KIND[tk.kind].de}: bravo! ${euros(tk.stake, 'de')} zu ${tk.odds} zu 1… das macht ${euros(won, 'de')} für Sie.`,
          ),
          mood: 'joie',
        });
        effects.push({ kind: 'journal', words: w(`Tu as gagné ${euros(won)} sur le ${tk.horse}.`, `You won ${euros(won, 'en')} on number ${tk.horse}.`, `Du hast ${euros(won, 'de')} mit der ${tk.horse} gewonnen.`) });
        effects.push({ kind: 'fact', key: 'hippodrome_longchamp.won', value: won });
      } else {
        lines.push({ say: w(`Le ${tk.horse}… Ah, pas cette fois. Le ${r[0]} a gagné.`, `Number ${tk.horse}… Ah, not this time. Number ${r[0]} won.`, `Die ${tk.horse}… Ach, diesmal nicht. Die ${r[0]} hat gewonnen.`), mood: 'cold' });
        effects.push({ kind: 'fact', key: 'hippodrome_longchamp.won', value: 0 });
      }
      return reply();
    }
    if (BYE.test(t) || THANKS.test(t)) {
      lines.push({ say: w('Au revoir ! Bonne fin de journée.', 'Goodbye! Enjoy the rest of the day.', 'Auf Wiedersehen! Einen schönen Tag noch.') });
      return reply(true);
    }
    lines.push({ say: w('Les paris sont fermés pour l’Arc. Revenez à la prochaine course !', 'Betting is closed for the Arc. Come back for the next race!', 'Die Wetten für den Arc sind geschlossen. Kommen Sie zum nächsten Rennen!') });
    return reply();
  }

  // the money, when she asked for it
  if (c.owing !== null && (PAY.test(t) || /^(oui|ok|d accord)\b/.test(t))) {
    const a = c.ask;
    const tk: Ticket = { horse: a.horse as number, kind: a.kind as 'gagnant' | 'place', stake: c.owing, odds: oddsOf(race, a.horse as number) };
    c.ticket = tk;
    c.owing = null;
    if (/carte/.test(t)) lines.push({ say: w('Par carte, oui, bien sûr.', 'By card, yes, of course.', 'Mit Karte, ja, natürlich.') });
    lines.push({ say: w(`Merci. Voilà votre ticket : le ${tk.horse}, ${KIND[tk.kind].fr}. Bonne chance !`, `Thank you. Here's your ticket: number ${tk.horse}, ${KIND[tk.kind].en}. Good luck!`, `Danke. Hier ist Ihr Ticket: die ${tk.horse}, ${KIND[tk.kind].de}. Viel Glück!`), mood: 'joie' });
    effects.push({ kind: 'journal', words: w(`Tu as joué ${euros(tk.stake)} ${KIND[tk.kind].fr} sur le ${tk.horse}, à ${tk.odds} contre 1.`, `You bet ${euros(tk.stake, 'en')} ${KIND[tk.kind].en} on number ${tk.horse}, at ${tk.odds} to 1.`, `Du hast ${euros(tk.stake, 'de')} ${KIND[tk.kind].de} auf die ${tk.horse} gesetzt, zu ${tk.odds} zu 1.`) });
    effects.push({ kind: 'fact', key: 'hippodrome_longchamp.bet', value: tk.horse });
    return reply();
  }
  if (BYE.test(t) && !/s il vous plait/.test(t)) {
    if (c.owing !== null) {
      c.owing = null;
      c.ask = { horse: null, kind: null, stake: null };
      lines.push({ say: w('Ah, vous ne jouez pas finalement ? Au revoir !', "Oh, not betting after all? Goodbye!", 'Ach, Sie wetten doch nicht? Auf Wiedersehen!'), mood: 'surprise' });
    } else lines.push({ say: w('Au revoir, et bonne course !', 'Goodbye, and enjoy the race!', 'Auf Wiedersehen, und viel Spaß beim Rennen!') });
    return reply(true);
  }

  // questions
  if (/\bfavori/.test(t)) {
    const h = race.holder;
    lines.push({ say: w(`Le favori, c’est le ${h}, le gagnant de l’an dernier. Il est à ${oddsOf(race, h)} contre 1.`, `The favourite is number ${h}, last year's winner. He's at ${oddsOf(race, h)} to 1.`, `Favorit ist die ${h}, der Sieger vom letzten Jahr. Er steht ${oddsOf(race, h)} zu 1.`) });
    return reply();
  }
  if (/\bplace/.test(t) && /(veut dire|c est quoi|quoi|difference|comment)/.test(t)) {
    lines.push({ say: w('Placé, votre cheval doit finir dans les trois premiers. Gagnant, il doit arriver premier. Placé rapporte moins.', 'Each way, your horse has to finish in the first three. To win, it has to come first. Each way pays less.', 'Auf Platz muss Ihr Pferd unter die ersten drei kommen. Auf Sieg muss es Erster werden. Platz bringt weniger.') });
    return reply();
  }
  if (/(minimum|combien.*(mise|miser|jouer|parier))/.test(t)) {
    lines.push({ say: w('Deux euros minimum. C’est ce que tout le monde joue.', "Two euros minimum. That's what everyone bets.", 'Mindestens zwei Euro. Das setzen alle.') });
    return reply();
  }
  const asked = readBet(text);
  if (c.ticket && (asked.horse || asked.kind)) {
    lines.push({ say: w('Vous avez déjà votre ticket pour l’Arc. Un ticket par course, ici !', 'You already have your ticket for the Arc. One ticket a race, here!', 'Sie haben schon Ihr Ticket für den Arc. Ein Ticket pro Rennen hier!') });
    return reply();
  }
  if (asked.horse !== null || asked.kind !== null || asked.stake !== null) {
    const n = race.runners.length;
    if (asked.horse !== null && (asked.horse < 1 || asked.horse > n || asked.horse % 1)) {
      lines.push({ say: w(`Il n’y a que ${said(n)} partants : du 1 au ${n}.`, `There are only ${n} runners: 1 to ${n}.`, `Es gibt nur ${n} Starter: 1 bis ${n}.`) });
      return reply();
    }
    // a question about one horse's price
    if (asked.horse !== null && /(cote|combien|il est a|rapporte)/.test(t) && !asked.kind) {
      lines.push({ say: w(`Le ${asked.horse} ? À ${oddsOf(race, asked.horse)} contre 1.`, `Number ${asked.horse}? At ${oddsOf(race, asked.horse)} to 1.`, `Die ${asked.horse}? ${oddsOf(race, asked.horse)} zu 1.`) });
      return reply();
    }
    if (asked.horse !== null) c.ask.horse = asked.horse;
    if (asked.kind !== null) c.ask.kind = asked.kind;
    if (asked.stake !== null) c.ask.stake = asked.stake;
    const a = c.ask;
    if (a.stake !== null && a.stake > 20) {
      a.stake = 20;
      lines.push({ say: w('Ici, on joue petit : vingt euros au plus.', 'Here we bet small: twenty euros at most.', 'Hier wird klein gewettet: höchstens zwanzig Euro.') });
    } else if (a.stake !== null && a.stake < 2) {
      a.stake = 2;
      lines.push({ say: w('Deux euros minimum, je mets deux.', "Two euros minimum, I'll put two.", 'Mindestens zwei Euro, ich nehme zwei.') });
    }
    if (a.horse !== null && a.kind === null) {
      lines.push({ say: w(`Le ${a.horse}, gagnant ou placé ?`, `Number ${a.horse}, to win or each way?`, `Die ${a.horse}, auf Sieg oder auf Platz?`) });
      return reply();
    }
    if (a.kind !== null && a.horse === null) {
      lines.push({ say: w(`${a.kind === 'gagnant' ? 'Gagnant' : 'Placé'}, sur quel numéro ?`, `${a.kind === 'gagnant' ? 'To win' : 'Each way'}, on which number?`, `${a.kind === 'gagnant' ? 'Auf Sieg' : 'Auf Platz'}, auf welche Nummer?`) });
      return reply();
    }
    if (a.horse !== null && a.kind !== null) {
      const stake = a.stake ?? 2;
      a.stake = stake;
      c.owing = stake;
      lines.push({
        say: w(
          `${said(stake).replace(/^./, (m) => m.toUpperCase())} euros ${KIND[a.kind].fr} sur le ${a.horse}. Ça fait ${euros(stake)}, s’il vous plaît.`,
          `${euros(stake, 'en')} ${KIND[a.kind].en} on number ${a.horse}. That's ${euros(stake, 'en')}, please.`,
          `${euros(stake, 'de')} ${KIND[a.kind].de} auf die ${a.horse}. Das macht ${euros(stake, 'de')}, bitte.`,
        ),
      });
      return reply();
    }
    lines.push({ say: w('Sur quel numéro, et gagnant ou placé ?', 'On which number, and to win or each way?', 'Auf welche Nummer, und auf Sieg oder auf Platz?') });
    return reply();
  }
  if (hello) {
    lines.push({ say: w('Bonjour ! Vous jouez quel numéro ?', 'Hello! Which number are you backing?', 'Guten Tag! Auf welche Nummer setzen Sie?') });
    return reply();
  }
  if (THANKS.test(t)) {
    lines.push({ say: w('Je vous en prie.', "You're welcome.", 'Gern geschehen.') });
    return reply();
  }
  if (c.owing !== null) {
    lines.push({ say: w(`Ça fait ${euros(c.owing)}, s’il vous plaît.`, `That's ${euros(c.owing, 'en')}, please.`, `Das macht ${euros(c.owing, 'de')}, bitte.`) });
    return reply();
  }
  lines.push({ say: w('Pardon ? Dites-moi un numéro, de 1 à 16, et gagnant ou placé.', 'Sorry? Tell me a number, 1 to 16, and to win or each way.', 'Wie bitte? Sagen Sie mir eine Nummer, von 1 bis 16, und Sieg oder Platz.'), mood: 'surprise' });
  return reply();
}

/* ---- the regular at the rail -------------------------------------------------------------- */

export interface Regular {
  greeted: boolean;
  /** the number he backs today */
  pick: number;
  told: string[];
}

/** He has been coming for forty years; today he backs an outsider he likes the look of. */
export function newRegular(race: Race, roll: number): Regular {
  const outsiders = race.runners.filter((r) => r.odds >= 9 && r.odds <= 25).map((r) => r.n);
  return { greeted: false, pick: outsiders.length ? outsiders[Math.floor(roll * outsiders.length) % outsiders.length] : race.holder, told: [] };
}

export function regularHello(g: Regular, race: Race): Said {
  if (race.result) {
    const won = race.result[0] === g.pick;
    return won
      ? { say: w(`Le ${g.pick} ! Je vous l’avais dit, non ?`, `Number ${g.pick}! I told you, didn't I?`, `Die ${g.pick}! Hab ich's Ihnen nicht gesagt?`), mood: 'joie' }
      : { say: w(`Le ${g.pick}, ${race.result.indexOf(g.pick) + 1}e… Ce sera pour l’année prochaine.`, `Number ${g.pick}, ${race.result.indexOf(g.pick) + 1}th… Next year, then.`, `Die ${g.pick}, ${race.result.indexOf(g.pick) + 1}.… Dann eben nächstes Jahr.`), mood: 'cold' };
  }
  return { say: w('Belle journée pour l’Arc, hein ? Premier Arc ?', 'Lovely day for the Arc, eh? First Arc?', 'Schöner Tag für den Arc, was? Ihr erster Arc?'), mood: 'joie' };
}

export function regularChips(g: Regular, race: Race): string[] {
  const all: Array<[string, string]> = [
    ['pick', 'Vous jouez qui ?'],
    ['metres', 'La course fait combien de mètres ?'],
    ['holder', 'Qui est le favori ?'],
    ['purse', 'Il y a combien d’argent à gagner ?'],
    ['japon', 'Et les chevaux japonais ?'],
  ];
  if (race.result) return ['Au revoir !'];
  return all
    .filter(([k]) => g.told.indexOf(k) < 0)
    .slice(0, 3)
    .map(([, s]) => s)
    .concat(g.told.length >= 2 ? ['Merci, bonne course !'] : []);
}

const learn = (key: string, words: Words): Effect => ({ kind: 'learn', key: `hippodrome_longchamp.${key}`, words, from: 'L’habitué' });

/** What you say to the regular, and what he tells you: the article, as a man at the rail tells it. */
export function atRail(g: Regular, text: string, race: Race): Reply {
  const t = plain(text);
  const lines: Said[] = [];
  const effects: Effect[] = [];
  const tell = (key: string, say: Words, fact?: Words) => {
    if (g.told.indexOf(key) < 0) g.told.push(key);
    lines.push({ say });
    if (fact) effects.push(learn(key, fact));
  };
  const reply = (done = false): Reply => ({ lines, effects, chips: done ? [] : regularChips(g, race), done });
  if (BYE.test(t) || (THANKS.test(t) && g.told.length)) {
    lines.push({ say: w('Bonne course ! Et criez fort dans la ligne droite.', 'Enjoy the race! And shout loud in the straight.', 'Viel Spaß beim Rennen! Und schreien Sie laut auf der Zielgeraden.') });
    return reply(true);
  }
  if (/\b(qui|quel)\b.*\b(jouez|joue|gagner|gagne|conseil|choisi)|vous jouez|votre (cheval|numero)/.test(t)) {
    tell('pick', w(`Moi, je joue le ${g.pick}. ${oddsOf(race, g.pick)} contre 1 ! Personne n’y croit, mais il aime le terrain souple.`, `Me, I'm backing number ${g.pick}. ${oddsOf(race, g.pick)} to 1! Nobody believes in him, but he likes soft ground.`, `Ich setze auf die ${g.pick}. ${oddsOf(race, g.pick)} zu 1! Keiner glaubt an ihn, aber er mag weichen Boden.`));
    return reply();
  }
  if (/(combien de (metres|kilometres)|metres|distance|longue|long|minutes|vite|km)/.test(t)) {
    tell(
      'metres',
      w('Deux mille quatre cents mètres. Un peu plus de deux minutes, et ils galopent à plus de soixante à l’heure !', 'Two thousand four hundred metres. A little over two minutes, and they gallop at more than sixty an hour!', 'Zweitausendvierhundert Meter. Gut zwei Minuten, und sie galoppieren mit über sechzig Sachen!'),
      w('L’Arc se court sur 2 400 mètres, à plus de 60 km/h.', 'The Arc is run over 2,400 metres, at more than 60 km/h.', 'Der Arc geht über 2400 Meter, mit über 60 km/h.'),
    );
    return reply();
  }
  if (/(favori|an dernier|tenant|gagnant de)/.test(t)) {
    tell(
      'holder',
      w(`Le ${race.holder}, le gagnant de l’an dernier. Son entraîneur dit que sa force, c’est son accélération.`, `Number ${race.holder}, last year's winner. His trainer says his strength is his acceleration.`, `Die ${race.holder}, der Sieger vom letzten Jahr. Sein Trainer sagt, seine Stärke ist sein Antritt.`),
      w('Le gagnant de l’an dernier court encore : sa force, c’est son accélération.', "Last year's winner runs again: his strength is his acceleration.", 'Der Vorjahressieger läuft wieder: seine Stärke ist sein Antritt.'),
    );
    return reply();
  }
  if (/(argent|euros|million|prix|gagner combien|combien.*gagn)/.test(t)) {
    tell(
      'purse',
      w('Cinq millions d’euros pour la course ! Et plus de deux millions huit cent mille pour le premier.', 'Five million euros for the race! And more than two point eight million for the winner.', 'Fünf Millionen Euro für das Rennen! Und über 2,8 Millionen für den Sieger.'),
      w('L’Arc offre 5 millions d’euros, dont plus de 2,8 millions au vainqueur.', 'The Arc offers 5 million euros, more than 2.8 million to the winner.', 'Der Arc ist mit 5 Millionen Euro dotiert, über 2,8 Millionen für den Sieger.'),
    );
    return reply();
  }
  if (/(japon|japonais)/.test(t)) {
    tell(
      'japon',
      w('Les japonais ? On dit qu’ils sont faits pour cette piste. Mais ça, personne n’en est sûr.', "The Japanese? They say they're made for this track. But nobody's sure of that.", 'Die Japaner? Man sagt, sie sind wie gemacht für diese Bahn. Aber sicher ist das keiner.'),
      w('Les chevaux japonais seraient faits pour cette piste, mais rien n’est sûr.', 'The Japanese horses may be made for this track, but nothing is sure.', 'Die japanischen Pferde sollen für diese Bahn gemacht sein, aber sicher ist nichts.'),
    );
    return reply();
  }
  if (/(seize|partants|combien de chevaux|d ou|viennent)/.test(t)) {
    tell('field', w('Seize partants : de France, d’Irlande, d’Angleterre et du Japon.', 'Sixteen runners: from France, Ireland, England and Japan.', 'Sechzehn Starter: aus Frankreich, Irland, England und Japan.'), w('Seize chevaux courent l’Arc, venus de France, d’Irlande, d’Angleterre et du Japon.', 'Sixteen horses run the Arc, from France, Ireland, England and Japan.', 'Sechzehn Pferde laufen den Arc, aus Frankreich, Irland, England und Japan.'));
    return reply();
  }
  if (HELLO.test(t) && !g.greeted) {
    g.greeted = true;
    lines.push({ say: w('Bonjour ! Moi, ça fait quarante ans que je viens. Demandez-moi, je sais tout.', "Hello! I've been coming for forty years. Ask me, I know everything.", 'Guten Tag! Ich komme seit vierzig Jahren. Fragen Sie mich, ich weiß alles.'), mood: 'joie' });
    return reply();
  }
  lines.push({ say: w('Ici, on parle chevaux ! Demandez-moi qui va gagner.', "Here, we talk horses! Ask me who's going to win.", 'Hier redet man über Pferde! Fragen Sie mich, wer gewinnt.') });
  return reply();
}

/* ---- the voice over the course ------------------------------------------------------------ */

export interface Call {
  /** seconds from the off */
  at: number;
  say: Words;
}

const pos = (n: number) => w(`le ${n}`, `number ${n}`, `die ${n}`);

/**
 * The race, called: the start, the far side of the course while the horses are out of sight,
 * the straight as it unfolds (`order(t)`: who leads at a time), and the finish.
 */
export function callRace(race: Race, order: (t: number) => number[], straight: number, post: number, finish: number[]): Call[] {
  const at = (t: number) => order(t);
  const o5 = at(5);
  const o19 = at(19);
  const calls: Call[] = [
    { at: 0, say: w(`Ils sont partis ! Le ${race.spec.name.fr} est lancé !`, `They're off! The ${race.spec.name.en} is under way!`, `Sie sind gestartet! Der ${race.spec.name.de} läuft!`) },
    { at: 5, say: w(`${cap(pos(o5[0]).fr)} prend la tête, devant ${pos(o5[1]).fr} et ${pos(o5[2]).fr}.`, `${cap(pos(o5[0]).en)} takes the lead, ahead of ${pos(o5[1]).en} and ${pos(o5[2]).en}.`, `${cap(pos(o5[0]).de)} übernimmt die Führung, vor ${pos(o5[1]).de} und ${pos(o5[2]).de}.`) },
    { at: 12, say: w(`Ils montent vers le moulin. ${cap(pos(race.holder).fr)}, le gagnant de l’an dernier, attend à la corde.`, `They climb toward the windmill. ${cap(pos(race.holder).en)}, last year's winner, waits on the rail.`, `Sie ziehen hinauf zur Mühle. ${cap(pos(race.holder).de)}, der Vorjahressieger, wartet innen.`) },
    { at: 19, say: w(`La descente, puis la fausse ligne droite. ${cap(pos(o19[0]).fr)} mène toujours. Ça se resserre !`, `Down the hill, then the false straight. ${cap(pos(o19[0]).en)} still leads. It's closing up!`, `Bergab, dann die falsche Gerade. ${cap(pos(o19[0]).de)} führt noch. Das Feld rückt zusammen!`) },
    { at: straight, say: w('Ils entrent dans la ligne droite !', "They're into the straight!", 'Sie biegen in die Zielgerade ein!') },
  ];
  const span = post - straight;
  const w1 = at(straight + span * 0.35);
  const winner = finish[0];
  calls.push(
    w1[0] === winner
      ? { at: straight + span * 0.35, say: w(`${cap(pos(winner).fr)} accélère ! Il prend deux longueurs !`, `${cap(pos(winner).en)} kicks on! Two lengths clear!`, `${cap(pos(winner).de)} zieht an! Zwei Längen vorn!`) }
      : { at: straight + span * 0.35, say: w(`${cap(pos(w1[0]).fr)} est en tête… mais ${pos(winner).fr} attaque à l’extérieur !`, `${cap(pos(w1[0]).en)} leads… but ${pos(winner).en} comes on the outside!`, `${cap(pos(w1[0]).de)} führt… aber ${pos(winner).de} greift außen an!`) },
  );
  const w2 = at(straight + span * 0.7);
  const late = w2.slice(0, 2).indexOf(winner) < 0;
  calls.push({
    at: straight + span * 0.7,
    say: late
      ? w(`${cap(pos(w2[0]).fr)} et ${pos(w2[1]).fr}, côte à côte… mais ${pos(winner).fr} revient très fort !`, `${cap(pos(w2[0]).en)} and ${pos(w2[1]).en}, side by side… but ${pos(winner).en} is flying!`, `${cap(pos(w2[0]).de)} und ${pos(w2[1]).de}, Kopf an Kopf… aber ${pos(winner).de} kommt mit Macht!`)
      : w(`${cap(pos(w2[0]).fr)} et ${pos(w2[1]).fr}, côte à côte ! Deux cents mètres !`, `${cap(pos(w2[0]).en)} and ${pos(w2[1]).en}, side by side! Two hundred metres!`, `${cap(pos(w2[0]).de)} und ${pos(w2[1]).de}, Kopf an Kopf! Noch zweihundert Meter!`),
  });
  calls.push({ at: post, say: w(`${cap(pos(winner).fr)} gagne le ${race.spec.name.fr} !`, `${cap(pos(winner).en)} wins the ${race.spec.name.en}!`, `${cap(pos(winner).de)} gewinnt den ${race.spec.name.de}!`) });
  calls.push({ at: post + 5, say: w(`Arrivée : le ${finish[0]}, le ${finish[1]}, le ${finish[2]}.`, `Result: ${finish[0]}, ${finish[1]}, ${finish[2]}.`, `Einlauf: ${finish[0]}, ${finish[1]}, ${finish[2]}.`) });
  return calls;
}

const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);

/* ---- the crowd ---------------------------------------------------------------------------- */

export const RACE_BARKS: Words[] = [
  w('Seize partants… Je n’arrive pas à choisir.', "Sixteen runners… I can't choose.", 'Sechzehn Starter… Ich kann mich nicht entscheiden.'),
  w('Deux minutes de course, et on attend ça toute l’année !', 'Two minutes of racing, and we wait all year for it!', 'Zwei Minuten Rennen, und darauf warten wir das ganze Jahr!'),
  w('Le gagnant de l’an dernier peut le refaire. Moi, j’y crois.', 'Last year’s winner can do it again. I believe it.', 'Der Vorjahressieger kann es nochmal schaffen. Ich glaube daran.'),
  w('Il paraît que les japonais aiment cette piste.', 'Apparently the Japanese horses like this track.', 'Angeblich mögen die Japaner diese Bahn.'),
  w('J’ai joué deux euros placé. On ne sait jamais.', 'I put two euros each way. You never know.', 'Ich habe zwei Euro auf Platz gesetzt. Man weiß ja nie.'),
  w('Le moulin, là-bas : c’est de là qu’ils partent.', "The windmill over there: that's where they start from.", 'Die Mühle da drüben: Da starten sie.'),
  w('Plus de soixante à l’heure, ces chevaux !', 'More than sixty an hour, these horses!', 'Über sechzig Sachen, diese Pferde!'),
];

export const CHEERS: Words[] = [w('Allez ! Allez !', 'Come on! Come on!', 'Los! Los!'), w('Vas-y, vas-y !', 'Go on, go on!', 'Komm schon!'), w('Allez le {n} !', 'Come on number {n}!', 'Los, die {n}!')];

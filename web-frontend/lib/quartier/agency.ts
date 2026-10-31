/**
 * Le Quartier · what you do besides answer, as the quarter keeps it, and the quarter's own lines.
 *
 * The story engine owns the story: the season's turns, the café crème and the key (asked as
 * questions), walking out, Margaux's text and free talk (gestures it keeps beside the story,
 * `story.ts`). What the quarter keeps here is what the engine does not send yet: what each reply
 * and each gesture changes in the carnet (a fact, someone's regard, a line), read from the route
 * the engine took (`REPLY_EFFECTS`, by `turn.reply`); what the street says as you pass; what is
 * waiting when you come back. And the lines the quarter plays away from the server (the standalone
 * page): the gestures' lines and a small stand-in for free talk, read by patterns here where the
 * engine asks a model. The engine's copy of those lines is `app/data/season/s1/agency.json`.
 *
 * Every line is written to the season's canon (`app/data/season/s1/world.json`): lines addressed
 * to Toi never agree an adjective with them; Gus and Camille say vous, the others tu; Odile never
 * speaks; Margaux deflects anything near the fire; «L.» is never named.
 */
import { matches } from './memory';
import type { CastId, Effect, Storylet, Value, Words } from './memory';

/* ------------------------------------------------------------------------------------------ */
/* reading what you type                                                                      */
/* ------------------------------------------------------------------------------------------ */

export const fold = (s: string) =>
  s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[’`]/g, "'");

/** Does a French line speak to someone as tu, or as vous? */
export function registerOf(text: string): 'tu' | 'vous' | null {
  const t = ` ${fold(text)} `;
  const vous = /\b(vous|votre|vos)\b/.test(t);
  const tu = /\b(tu|te|toi|ton|ta|tes)\b|\bt'/.test(t);
  if (vous && !tu) return 'vous';
  if (tu && !vous) return 'tu';
  return null;
}

const w = (fr: string, en: string, de: string): Words => ({ fr, en, de });

/* ------------------------------------------------------------------------------------------ */
/* what each route of the day changes                                                         */
/* ------------------------------------------------------------------------------------------ */

const regard = (who: CastId, delta: number): Effect => ({ kind: 'regard', who, delta });
const fact = (key: string, value: Value): Effect => ({ kind: 'fact', key, value });
const journal = (words: Words, who?: CastId): Effect => ({ kind: 'journal', words, who });

/** The effects of each reply of the day, by `turn.reply`. */
export const REPLY_EFFECTS: Record<string, Effect[]> = {
  'a.turn1.a': [
    fact('t1.told', 'family'),
    regard('margaux_barman', 1),
    regard('marin_leveque', 1),
    regard('lila_bonnet', 1),
    journal(w("Tu as dit qui tu es : la famille d'Odile.", "You said who you are: Odile's family.", 'Du hast gesagt, wer du bist: Odiles Familie.')),
  ],
  'a.turn1.b': [
    fact('t1.told', 'selling'),
    regard('augustin_de_roncourt', -1),
    regard('marin_leveque', -1),
    journal(w('Tu as dit que tu viens pour vendre.', "You said you've come to sell.", 'Du hast gesagt, dass du zum Verkaufen gekommen bist.')),
  ],
  'a.turn1.c': [
    fact('t1.told', 'family'),
    fact('t1.showed_key', true),
    regard('lila_bonnet', 1),
    regard('margaux_barman', 1),
    regard('marin_leveque', 1),
    journal(w('Tu as montré la clé à la cigale. Lila a compris.', 'You showed the key ring with the cicada. Lila understood.', 'Du hast den Schlüsselbund mit der Zikade gezeigt. Lila hat verstanden.')),
  ],
  'a.turn1.d': [
    fact('t1.told', 'question'),
    regard('augustin_de_roncourt', 1),
    regard('lila_bonnet', 1),
    journal(w('Tu as retourné la question à Gus. Ça lui a plu.', 'You turned the question back on Gus. He liked it.', 'Du hast Gus die Frage zurückgegeben. Das hat ihm gefallen.'), 'augustin_de_roncourt'),
  ],
  'a.turn2.tonight': [
    fact('t1.going_up', 'tonight'),
    journal(w('Tu voulais monter ce soir. Margaux a dit : pas ce soir.', 'You wanted to go up tonight. Margaux said: not tonight.', 'Du wolltest heute Abend hochgehen. Margaux hat gesagt: nicht heute Abend.'), 'margaux_barman'),
  ],
  'a.turn2.dont_know': [
    fact('t1.going_up', 'not_yet'),
    regard('margaux_barman', 1),
    journal(w('Tu ne sais pas encore si tu vas monter. Margaux trouve ça bien.', "You don't know yet whether you'll go up. Margaux thinks that's good.", 'Du weißt noch nicht, ob du hochgehst. Margaux findet das gut.'), 'margaux_barman'),
  ],
  'a.turn2.sell_and_leave': [
    fact('t1.going_up', 'never'),
    fact('t1.plans', 'sell_and_leave'),
    regard('marin_leveque', -1),
    journal(w('Tu as dit : je vends et je pars dans une semaine.', "You said: I'm selling and leaving in a week.", 'Du hast gesagt: Ich verkaufe und fahre in einer Woche.')),
  ],
  'a.turn2.clumsy': [
    fact('t1.going_up', 'tomorrow'),
    regard('margaux_barman', 2),
    journal(w('Tu as dit que tu as un peu peur. Margaux aussi.', "You said you're a little afraid. So is Margaux.", 'Du hast gesagt, dass du ein bisschen Angst hast. Margaux auch.'), 'margaux_barman'),
  ],
  'a.cafe.drink': [
    fact('t1.cafe', 'drank'),
    regard('margaux_barman', 1),
    regard('marin_leveque', 1),
    journal(w("Tu as bu le café crème d'Odile.", "You drank Odile's café crème.", 'Du hast Odiles Café Crème getrunken.'), 'margaux_barman'),
  ],
  'a.cafe.declined': [
    fact('t1.cafe', 'declined'),
    journal(w("Tu as dit non merci. Margaux a poussé la tasse vers le tabouret d'Odile.", "You said no thank you. Margaux pushed the cup toward Odile's stool.", 'Du hast nein danke gesagt. Margaux hat die Tasse zu Odiles Hocker geschoben.'), 'margaux_barman'),
  ],
  'a.cafe.refused': [
    fact('t1.cafe', 'refused'),
    regard('margaux_barman', -2),
    regard('augustin_de_roncourt', -1),
    journal(w('Tu as refusé le café sèchement. Margaux a repris la tasse.', 'You turned the coffee down curtly. Margaux took the cup back.', 'Du hast den Kaffee schroff abgelehnt. Margaux hat die Tasse zurückgenommen.'), 'margaux_barman'),
  ],
  'a.key.take': [
    { kind: 'item', id: 'cle_cigale', holder: 'toi' },
    fact('t1.key', 'toi'),
    journal(w('Tu as gardé la clé.', 'You kept the key.', 'Du hast den Schlüssel behalten.')),
  ],
  'a.key.leave': [
    { kind: 'item', id: 'cle_cigale', holder: 'margaux_barman' },
    fact('t1.key', 'margaux'),
    regard('margaux_barman', 1),
    journal(w('Tu as laissé la clé à Margaux, derrière la caisse.', 'You left the key with Margaux, behind the till.', 'Du hast den Schlüssel bei Margaux gelassen, hinter der Kasse.'), 'margaux_barman'),
  ],
  // T1 day b, «La lettre»
  'b.turn1.a': [journal(w('Tu as dit à Camille : je vends et je rentre.', "You told Camille: I'm selling and going home.", 'Du hast Camille gesagt: Ich verkaufe und fahre nach Hause.'), 'camille_marchand')],
  'b.turn1.b': [journal(w('Tu as dit à Camille : pas encore.', 'You told Camille: not yet.', 'Du hast Camille gesagt: noch nicht.'), 'camille_marchand')],
  'b.turn1.c': [regard('camille_marchand', 1), journal(w('Tu as demandé à Camille : plus simple pour qui ?', 'You asked Camille: simpler for whom?', 'Du hast Camille gefragt: einfacher für wen?'), 'camille_marchand')],
  'b.turn1.d': [journal(w('Tu as dit à Camille : pas ce soir.', 'You told Camille: not tonight.', 'Du hast Camille gesagt: nicht heute Abend.'), 'camille_marchand')],
  'b.letter.margaux': [regard('margaux_barman', 1), journal(w('Tu as montré la lettre à Margaux.', 'You showed the letter to Margaux.', 'Du hast Margaux den Brief gezeigt.'), 'margaux_barman')],
  'b.letter.lila': [regard('lila_bonnet', 1), journal(w('Tu as montré la lettre à Lila.', 'You showed the letter to Lila.', 'Du hast Lila den Brief gezeigt.'), 'lila_bonnet')],
  'b.letter.gus': [journal(w('Tu as montré la lettre à Gus. Tout le café connaît le prix.', 'You showed the letter to Gus. The whole café knows the price.', 'Du hast Gus den Brief gezeigt. Das ganze Café kennt den Preis.'), 'augustin_de_roncourt')],
  'b.letter.marin': [regard('marin_leveque', 1), journal(w('Tu as montré la lettre à Marin.', 'You showed the letter to Marin.', 'Du hast Marin den Brief gezeigt.'), 'marin_leveque')],
  'b.letter.nobody': [journal(w('Tu as gardé la lettre pour toi.', 'You kept the letter to yourself.', 'Du hast den Brief für dich behalten.'))],
  'b.key.asks': [{ kind: 'item', id: 'cle_cigale', holder: 'toi' }, journal(w('Margaux t’a rendu la clé.', 'Margaux gave you back the key.', 'Margaux hat dir den Schlüssel zurückgegeben.'), 'margaux_barman')],
  'b.key.clumsy': [{ kind: 'item', id: 'cle_cigale', holder: 'toi' }, journal(w('Margaux t’a rendu la clé.', 'Margaux gave you back the key.', 'Margaux hat dir den Schlüssel zurückgegeben.'), 'margaux_barman')],
  'b.key.other': [{ kind: 'item', id: 'cle_cigale', holder: 'toi' }, journal(w('Margaux t’a tendu la clé sans un mot.', 'Margaux held out the key without a word.', 'Margaux hat dir wortlos den Schlüssel hingehalten.'), 'margaux_barman')],
};

/* ------------------------------------------------------------------------------------------ */
/* walking out, and coming back                                                               */
/* ------------------------------------------------------------------------------------------ */

export const LEAVE = {
  /** as you turn to the door */
  asked: { who: 'margaux_barman' as CastId, say: w('Tu pars déjà ?', 'Leaving already?', 'Gehst du schon?') },
  /** back in, during Gus's story */
  resumeGus: { who: 'augustin_de_roncourt' as CastId, mood: 'happy', say: w('Bon. Où en étais-je ? Ah oui. Le duc.', 'Right. Where was I? Ah yes. The duke.', 'Also. Wo war ich? Ach ja. Der Herzog.') },
  /** back in, any other time */
  resume: { who: 'margaux_barman' as CastId, say: w('Te revoilà.', "There you are again.", 'Da bist du wieder.') },
  effects: [fact('t1.walked_out', true), journal(w('Tu as quitté le Mistral en pleine soirée.', 'You walked out of Le Mistral in the middle of the evening.', 'Du hast das Mistral mitten am Abend verlassen.'))],
  /** how long outside before Margaux writes (seconds) */
  textAfter: 40,
  goal: w('Revenir au Mistral', 'Go back to Le Mistral', 'Zurück ins Mistral'),
};

export interface PhoneText {
  id: string;
  from: string;
  /** who it turns out to be */
  who: CastId;
  say: Words;
  chips: string[];
  /** their answer to yours */
  answer: Words;
  effects: Effect[];
}

export const TEXT_SUITCASE: PhoneText = {
  id: 'margaux_suitcase',
  from: 'Numéro inconnu',
  who: 'margaux_barman',
  say: w("C'est Margaux. Ta valise est toujours là.", "It's Margaux. Your suitcase is still here.", 'Hier ist Margaux. Dein Koffer ist noch da.'),
  chips: ["J'arrive.", "Merci. J'arrive.", 'Demain.'],
  answer: w('Bon.', 'Fine.', 'Gut.'),
  effects: [fact('t1.stayed_away', true), journal(w('Margaux t\'a écrit : ta valise est toujours là.', 'Margaux texted you: your suitcase is still there.', 'Margaux hat dir geschrieben: Dein Koffer ist noch da.'), 'margaux_barman')],
};

/* ------------------------------------------------------------------------------------------ */
/* the moment before the bell: talk to anyone                                                 */
/* ------------------------------------------------------------------------------------------ */

export const MOMENT = {
  caption: w("Tu as un moment. Parle à quelqu'un, ou attends.", 'You have a moment. Talk to someone, or wait.', 'Du hast einen Moment. Sprich mit jemandem, oder warte.'),
  go: 'Continuer',
};

export interface Hello extends Storylet {
  say: Words;
  mood?: string;
}

export interface Intent extends Storylet {
  /** the example the sheet offers */
  chip?: string;
  /** what it answers, over the folded text (no accents, lower case) */
  match: RegExp;
  reply: Words;
  mood?: string;
  direction?: string;
  effects?: Effect[];
}

export interface Person {
  id: CastId;
  register: 'tu' | 'vous';
  hello: Hello[];
  intents: Intent[];
  /** when you speak to them in the other register */
  slip: Words;
  fallback: Words[];
  bye?: Words;
}

const learn = (key: string, words: Words, who: CastId): Effect => ({ kind: 'learn', key, words, who });

export const PEOPLE: Record<CastId, Person> = {
  margaux_barman: {
    id: 'margaux_barman',
    register: 'tu',
    hello: [
      { id: 'margaux.key', when: { 'item.cle_cigale': 'margaux_barman' }, salience: 3, say: w('Elle est derrière la caisse.', "It's behind the till.", 'Er liegt hinter der Kasse.') },
      { id: 'margaux.cold', when: { 't1.cafe': 'refused' }, salience: 2, mood: 'cold', say: w('Oui ?', 'Yes?', 'Ja?') },
      { id: 'margaux.same', when: { 't1.cafe': 'drank' }, salience: 2, say: w('La même chose ?', 'Same again?', 'Dasselbe noch mal?') },
      { id: 'margaux.hello', say: w('Oui ?', 'Yes?', 'Ja?') },
    ],
    intents: [
      {
        id: 'margaux.why_left',
        chip: 'Pourquoi elle est partie ?',
        when: { 'knows.margaux.odile': true },
        salience: 3,
        match: /partie|parti\b|pourquoi elle|incendie|\bfeu\b|brule|2023|fumee/,
        direction: 'looking at the ceiling',
        reply: w("J'ai rien entendu.", "I didn't hear anything.", 'Ich hab nichts gehört.'),
        effects: [learn('margaux.wont_say', w('Margaux ne dit pas pourquoi Odile est partie.', "Margaux won't say why Odile left.", 'Margaux sagt nicht, warum Odile gegangen ist.'), 'margaux_barman')],
      },
      {
        id: 'margaux.odile',
        chip: 'Tu connaissais bien Odile ?',
        salience: 2,
        match: /odile|grand-?mere|ta cliente|elle venait|connaissais|connaissiez|connaitre/,
        direction: 'drying a glass that is already dry',
        reply: w('Tous les matins. Un café crème, au bout du zinc.', 'Every morning. A café crème, at the end of the zinc.', 'Jeden Morgen. Ein Café Crème, am Ende der Theke.'),
        effects: [learn('margaux.odile', w('Odile prenait un café crème tous les matins, au bout du zinc.', 'Odile had a café crème every morning, at the end of the zinc.', 'Odile trank jeden Morgen einen Café Crème, am Ende der Theke.'), 'margaux_barman')],
      },
      {
        id: 'margaux.cicada',
        chip: 'Et la cigale ?',
        salience: 1,
        match: /cigale|porte-?cle|provence/,
        reply: w('De Provence. Elle y tenait.', 'From Provence. She was attached to it.', 'Aus der Provence. Sie hing daran.'),
        effects: [learn('margaux.cicada', w("La cigale vient de Provence. Odile y tenait.", 'The cicada comes from Provence. Odile was attached to it.', 'Die Zikade kommt aus der Provence. Odile hing daran.'), 'margaux_barman')],
      },
      {
        id: 'margaux.water',
        chip: "Un verre d'eau, s'il te plaît.",
        match: /\beau\b|un verre|boire|un cafe|un the|une biere|un vin|un sirop|commander|encore un/,
        direction: 'setting down a glass',
        reply: w('Voilà.', 'There you go.', 'Bitte schön.'),
      },
    ],
    slip: w('Tu. Ici, on dit tu.', "Tu. Here we say tu.", 'Du. Hier sagt man du.'),
    fallback: [w('Hm. Redis ?', 'Hm. Say again?', 'Hm. Noch mal?'), w('Plus simple. Je suis fatiguée.', "Simpler. I'm tired.", 'Einfacher. Ich bin müde.')],
  },
  augustin_de_roncourt: {
    id: 'augustin_de_roncourt',
    register: 'vous',
    hello: [
      { id: 'gus.selling', when: { 't1.told': 'selling' }, salience: 3, mood: 'cold', say: w('Ah. La personne qui vend.', "Ah. The person who's selling.", 'Ah. Die Person, die verkauft.') },
      { id: 'gus.rude', when: { 't1.cafe': 'refused' }, salience: 2, say: w('Le café crème. Quelle histoire.', 'The café crème. What a business.', 'Der Café Crème. Was für eine Geschichte.') },
      { id: 'gus.question', when: { 't1.told': 'question' }, salience: 2, mood: 'happy', say: w('Ah ! Vous revoilà. Vous me plaisez toujours.', 'Ah! You again. I still like you.', 'Ah! Da sind Sie wieder. Sie gefallen mir immer noch.') },
      { id: 'gus.hello', say: w('Je vous écoute.', "I'm listening.", 'Ich höre.') },
    ],
    intents: [
      {
        id: 'gus.sorry',
        once: true,
        when: { 'regard.augustin_de_roncourt': { max: -1 } },
        salience: 3,
        match: /pardon|desole|excuse/,
        mood: 'happy',
        reply: w('Excuses acceptées. Provisoirement.', 'Apology accepted. Provisionally.', 'Entschuldigung angenommen. Vorläufig.'),
        effects: [regard('augustin_de_roncourt', 1)],
      },
      {
        id: 'gus.duke',
        chip: 'Et le duc, il existe vraiment ?',
        salience: 2,
        match: /\bduc\b|histoire|vraiment|mensonge|invente/,
        mood: 'happy',
        reply: w("Tous mes ducs existent. Certains plus que d'autres.", 'All my dukes exist. Some more than others.', 'Alle meine Herzöge existieren. Manche mehr als andere.'),
        effects: [regard('augustin_de_roncourt', 1)],
        once: true,
      },
      {
        id: 'gus.zinc',
        chip: 'Vous venez souvent ici ?',
        salience: 1,
        match: /souvent|habitue|\bzinc\b|mistral|depuis quand/,
        reply: w('Mon arrière-grand-père a posé ce zinc. Alors oui. Souvent.', 'My great-grandfather laid this zinc. So yes. Often.', 'Mein Urgroßvater hat diese Zinktheke eingebaut. Also ja. Oft.'),
        effects: [learn('gus.zinc', w("Gus dit que son arrière-grand-père a posé le zinc.", 'Gus says his great-grandfather laid the zinc.', 'Gus sagt, sein Urgroßvater habe die Zinktheke eingebaut.'), 'augustin_de_roncourt')],
      },
      {
        id: 'gus.method',
        chip: "C'est quoi, La Méthode ?",
        salience: 1,
        match: /methode|regle/,
        reply: w('Règle numéro un de La Méthode : ne jamais expliquer La Méthode.', 'Rule number one of The Method: never explain The Method.', 'Regel Nummer eins der Methode: Die Methode wird nie erklärt.'),
      },
      {
        id: 'gus.compliment',
        once: true,
        salience: 2,
        match: /elegant|\bchic\b|\bbeau\b|costume|magnifique|\bclasse\b|sublime/,
        mood: 'happy',
        direction: 'a hand on his heart',
        reply: w("Enfin quelqu'un qui le remarque ! C'est magnifique. Non : c'est sublime.", "Finally someone who notices! It's magnificent. No: it's sublime.", 'Endlich jemand, der es bemerkt! Es ist großartig. Nein: Es ist erhaben.'),
        effects: [regard('augustin_de_roncourt', 1)],
      },
    ],
    slip: w('« Tu » ? Nous n\'avons pas gardé les cochons ensemble.', "“Tu”? We're hardly old friends.", '„Du“? Wir haben doch nicht zusammen Schweine gehütet.'),
    fallback: [w('Pardon ? Articulez, je vous prie.', 'Pardon? Speak clearly, I beg you.', 'Wie bitte? Bitte deutlich sprechen.'), w('Fascinant. Absolument fascinant.', 'Fascinating. Absolutely fascinating.', 'Faszinierend. Absolut faszinierend.')],
  },
  marin_leveque: {
    id: 'marin_leveque',
    register: 'tu',
    hello: [
      { id: 'marin.fed', when: { 'marin.fed': true }, salience: 3, say: w('Il reste de la soupe, hein.', "There's soup left, you know.", 'Es ist noch Suppe da.') },
      { id: 'marin.family', when: { 't1.told': 'family' }, salience: 2, mood: 'happy', say: w('Ma grand-mère disait toujours : « La pluie apporte la famille. »', 'My grandmother always said: “Rain brings family.”', 'Meine Großmutter sagte immer: „Regen bringt die Familie.“') },
      { id: 'marin.hello', say: w('Ça va ?', 'All right?', 'Alles gut?') },
    ],
    intents: [
      {
        id: 'marin.soup',
        chip: 'Elle sent bon, ta soupe.',
        salience: 2,
        match: /soupe|faim|manger|sent bon|appetit|diner/,
        mood: 'happy',
        reply: w("C'est un signe, ça. Assieds-toi, je t'en sers une.", "That's a sign, that is. Sit down, I'll get you a bowl.", 'Das ist ein Zeichen. Setz dich, ich hol dir einen Teller.'),
        effects: [fact('marin.fed', true), regard('marin_leveque', 1), journal(w('Marin t\'a servi de la soupe.', 'Marin served you some soup.', 'Marin hat dir Suppe gegeben.'), 'marin_leveque')],
        once: true,
      },
      {
        id: 'marin.solvel',
        chip: "C'est qui, Solvel ?",
        salience: 2,
        match: /solvel|promoteur|immobili|acheter|achete/,
        reply: w('Des gens qui achètent des immeubles. Ma grand-mère disait toujours : « Méfie-toi des parapluies neufs. »', 'People who buy buildings. My grandmother always said: “Beware of new umbrellas.”', 'Leute, die Häuser kaufen. Meine Großmutter sagte immer: „Trau keinen neuen Regenschirmen.“'),
        effects: [learn('marin.solvel', w('Solvel achète des immeubles. Marin s\'en méfie.', "Solvel buys buildings. Marin doesn't trust them.", 'Solvel kauft Häuser. Marin traut ihnen nicht.'), 'marin_leveque')],
      },
      {
        id: 'marin.odile',
        chip: 'Tu connaissais Odile ?',
        salience: 1,
        match: /odile|grand-?mere|connaissais/,
        mood: 'moved',
        reply: w('Elle croyait aux signes. Comme moi.', 'She believed in signs. Like me.', 'Sie glaubte an Zeichen. Wie ich.'),
        effects: [learn('marin.odile', w('Odile croyait aux signes, comme Marin.', 'Odile believed in signs, like Marin.', 'Odile glaubte an Zeichen, wie Marin.'), 'marin_leveque')],
      },
      {
        id: 'marin.bye',
        salience: 1,
        match: /au revoir|bonne nuit|a demain|\bbye\b|\bciao\b|bonne soiree/,
        mood: 'happy',
        reply: w('Kenavo ! Ça veut dire au revoir. Enfin, à la prochaine.', 'Kenavo! It means goodbye. Well, see you next time.', 'Kenavo! Das heißt auf Wiedersehen. Na ja, bis zum nächsten Mal.'),
      },
    ],
    slip: w('Tu peux me dire tu, hein. Tout le monde me dit tu.', 'You can say tu to me, you know. Everyone does.', 'Du kannst mich duzen. Alle duzen mich.'),
    fallback: [w("Pardon, je… Ma grand-mère disait toujours… non, j'ai oublié.", "Sorry, I… My grandmother always said… no, I've forgotten.", 'Entschuldige, ich… Meine Großmutter sagte immer… nein, vergessen.'), w("Hein ? Redis, je n'ai pas compris.", "Huh? Say it again, I didn't get it.", 'Hm? Sag noch mal, ich hab’s nicht verstanden.')],
  },
  lila_bonnet: {
    id: 'lila_bonnet',
    register: 'tu',
    hello: [
      { id: 'lila.family', when: { 't1.told': 'family' }, salience: 2, mood: 'happy', say: w("Salut, l'héritage !", "Hi there, l'héritage!", "Hallo, l'héritage!") },
      { id: 'lila.selling', when: { 't1.told': 'selling' }, salience: 2, mood: 'malice', say: w('Sept sur vingt, ta soirée.', 'Seven out of twenty, your evening.', 'Sieben von zwanzig, dein Abend.') },
      { id: 'lila.hello', say: w('Bon, on fait quoi ?', 'Right, what do we do?', 'Also, was machen wir?') },
    ],
    intents: [
      {
        id: 'lila.margaux_spoke',
        once: true,
        when: { 'knows.margaux.odile': true },
        salience: 4,
        match: /odile|cafe creme|margaux|le matin|tous les matins/,
        mood: 'surprised',
        reply: w("Margaux t'a parlé d'Odile ? Elle ne parle jamais d'Odile.", 'Margaux talked to you about Odile? She never talks about Odile.', 'Margaux hat mit dir über Odile geredet? Sie redet nie über Odile.'),
        effects: [regard('lila_bonnet', 1), learn('lila.margaux_silent', w("Margaux ne parle jamais d'Odile. Sauf à toi.", 'Margaux never talks about Odile. Except to you.', 'Margaux redet nie über Odile. Außer mit dir.'), 'lila_bonnet')],
      },
      {
        id: 'lila.shoes',
        chip: 'Pourquoi mes chaussures ?',
        salience: 2,
        match: /chaussure|pieds|comment tu (as|sais)|pourquoi tu/,
        mood: 'malice',
        reply: w('Mais arrête. Tu as marché sous la pluie avec une valise. Solvel prend des taxis.', 'Oh, come on. You walked through the rain with a suitcase. Solvel takes taxis.', 'Ach, hör auf. Du bist mit einem Koffer durch den Regen gelaufen. Solvel nimmt Taxis.'),
      },
      {
        id: 'lila.grade_good',
        chip: "Et moi, j'ai combien sur vingt ?",
        when: { 'regard.lila_bonnet': { min: 1 } },
        salience: 2,
        match: /sur vingt|\/ ?20|\bnote\b|combien/,
        mood: 'happy',
        reply: w('Douze sur vingt. Peut mieux faire.', 'Twelve out of twenty. Could do better.', 'Zwölf von zwanzig. Da geht noch was.'),
      },
      {
        id: 'lila.grade',
        chip: "Et moi, j'ai combien sur vingt ?",
        salience: 1,
        match: /sur vingt|\/ ?20|\bnote\b|combien/,
        mood: 'malice',
        reply: w('Sept sur vingt. Peut mieux faire.', 'Seven out of twenty. Could do better.', 'Sieben von zwanzig. Da geht noch was.'),
      },
      {
        id: 'lila.home',
        chip: 'Tu habites ici ?',
        salience: 1,
        match: /habite|\bvis\b|loges|coloc|ensemble|et marin/,
        reply: w("À côté. Avec Marin. On n'est pas ensemble, avant que tu demandes.", "Nearby. With Marin. We're not together, before you ask.", 'Gleich nebenan. Mit Marin. Wir sind kein Paar, bevor du fragst.'),
        effects: [learn('lila.flatmates', w('Lila et Marin habitent ensemble. Ils ne sont pas en couple.', "Lila and Marin share a flat. They're not a couple.", 'Lila und Marin wohnen zusammen. Sie sind kein Paar.'), 'lila_bonnet')],
      },
      {
        id: 'lila.odile',
        salience: 0,
        match: /odile/,
        reply: w("La preuve qu'on peut partir et revenir.", 'Proof that you can leave and come back.', 'Der Beweis, dass man gehen und wiederkommen kann.'),
      },
    ],
    slip: w('Tu me vouvoies ? Je le dis à ma classe.', "You're saying vous to me? I'm telling my class.", 'Du siezt mich? Das erzähl ich meiner Klasse.'),
    fallback: [w('Oh, fan de chichourle ! Redis ?', 'Oh, good grief! Say that again?', 'Ach du liebe Zeit! Noch mal?'), w('Bon, on fait quoi ?', 'Right, what do we do?', 'Also, was machen wir?')],
    bye: w('Allez, file.', 'Go on, off you go.', 'Na los, ab mit dir.'),
  },
  camille_marchand: {
    id: 'camille_marchand',
    register: 'vous',
    hello: [{ id: 'camille.hello', say: w('Bonsoir.', 'Good evening.', 'Guten Abend.') }],
    intents: [
      {
        id: 'camille.key',
        chip: 'Pourquoi vous avez une clé ?',
        salience: 2,
        match: /\bcle\b|porte|premier|etage|appartement/,
        reply: w('Les chiffres sont simples : une porte, deux clés. Il faudra parler.', "The numbers are simple: one door, two keys. We'll have to talk.", 'Die Zahlen sind einfach: eine Tür, zwei Schlüssel. Wir werden reden müssen.'),
      },
      {
        id: 'camille.rain',
        chip: 'Il pleut, hein ?',
        salience: 1,
        match: /pleut|pluie|mouill|tremp|velo|casque/,
        reply: w('Onze minutes à vélo. Dix-huit sous la pluie.', 'Eleven minutes by bike. Eighteen in the rain.', 'Elf Minuten mit dem Rad. Achtzehn im Regen.'),
      },
      {
        id: 'camille.odile',
        salience: 1,
        match: /odile/,
        reply: w("Je l'ai vue deux fois. Des dimanches.", 'I saw her twice. On Sundays.', 'Ich habe sie zweimal gesehen. An Sonntagen.'),
        effects: [learn('camille.odile', w("Camille a vu Odile deux fois, des dimanches.", 'Camille saw Odile twice, on Sundays.', 'Camille hat Odile zweimal gesehen, an Sonntagen.'), 'camille_marchand')],
      },
    ],
    slip: w("Je préfère vous. Pour l'instant.", "I'd rather keep to vous. For now.", 'Ich bleibe lieber beim Sie. Vorerst.'),
    fallback: [w('Pouvez-vous répéter ? Lentement.', 'Could you say that again? Slowly.', 'Können Sie das wiederholen? Langsam.')],
  },
};

/* ------------------------------------------------------------------------------------------ */
/* talking: the reader that stands in for improvisation                                       */
/* ------------------------------------------------------------------------------------------ */

export interface TalkTurn {
  lines: Array<{ say: Words; mood?: string; direction?: string }>;
  effects: Effect[];
  intent: string | null;
}

/**
 * What `who` answers to `text`, given the state. A slip of register is answered first (once a
 * conversation); then the most salient intent that matches and may play; else a fallback.
 */
export function respond(who: CastId, text: string, state: Record<string, Value>, opts: { slipped?: boolean; turn?: number; used?: string[] } = {}): TalkTurn {
  const p = PEOPLE[who];
  const t = fold(text);
  const lines: TalkTurn['lines'] = [];
  const effects: Effect[] = [];
  const reg = registerOf(text);
  if (!opts.slipped && reg && reg !== p.register) lines.push({ say: p.slip, mood: p.register === 'vous' ? 'cold' : 'malice' });
  const usable = p.intents
    .filter((i) => i.match.test(t) && matchesWhen(i, state) && !(i.once && (state[`seen.${i.id}`] || opts.used?.includes(i.id))))
    .sort((a, b) => (b.salience ?? 0) - (a.salience ?? 0));
  const hit = usable[0] ?? null;
  if (hit) {
    lines.push({ say: hit.reply, mood: hit.mood, direction: hit.direction });
    effects.push(...(hit.effects ?? []));
    if (hit.once) effects.push(fact(`seen.${hit.id}`, true));
  } else if (!lines.length) {
    lines.push({ say: p.fallback[(opts.turn ?? 0) % p.fallback.length] });
  }
  return { lines, effects, intent: hit?.id ?? null };
}

const matchesWhen = (s: Storylet, state: Record<string, Value>) => matches(s.when, state);

/** The chips a conversation offers now: one per intent that may play, most salient first. */
export function chipsFor(who: CastId, state: Record<string, Value>, used: string[] = []): string[] {
  const out: string[] = [];
  PEOPLE[who].intents
    .filter((i) => i.chip && matchesWhen(i, state) && !used.includes(i.id) && !(i.once && state[`seen.${i.id}`]))
    .sort((a, b) => (b.salience ?? 0) - (a.salience ?? 0))
    .forEach((i) => {
      if (i.chip && !out.includes(i.chip)) out.push(i.chip);
    });
  return out.slice(0, 3);
}

/** What someone says when you come up to them. */
export function helloOf(who: CastId, state: Record<string, Value>): Hello {
  const list = PEOPLE[who].hello.filter((h) => matchesWhen(h, state)).sort((a, b) => (b.salience ?? 0) - (a.salience ?? 0));
  return list[0] ?? PEOPLE[who].hello[PEOPLE[who].hello.length - 1];
}

/**
 * What the quarter keeps when the engine heard one of `who`'s lines in free talk: the regard and
 * the carnet's line. The engine sends what was learned and the flags itself.
 */
export function heardEffects(who: CastId, heard: string | null): Effect[] {
  const intent = heard ? PEOPLE[who]?.intents.find((i) => i.id === heard) : undefined;
  return (intent?.effects ?? []).filter((e) => e.kind === 'regard' || e.kind === 'journal');
}

/* ------------------------------------------------------------------------------------------ */
/* the street: what passers-by say                                                            */
/* ------------------------------------------------------------------------------------------ */

export interface Bark extends Storylet {
  say: Words;
}

/** Said as you pass. `night`/`day` and `rain` come from the hour; the rest from the state. */
export const STREET_BARKS: Bark[] = [
  { id: 'rain.1', when: { rain: true }, say: w('Quel temps !', 'What weather!', 'Was für ein Wetter!') },
  { id: 'rain.2', when: { rain: true }, say: w('Il pleut des cordes.', "It's pouring.", 'Es schüttet wie aus Eimern.') },
  { id: 'rain.3', when: { rain: true }, say: w('Attention, ça glisse.', "Careful, it's slippery.", 'Vorsicht, rutschig.') },
  { id: 'night.1', when: { night: true }, say: w('Bonsoir.', 'Good evening.', 'Guten Abend.') },
  { id: 'night.2', when: { night: true }, say: w('Pardon.', 'Excuse me.', 'Entschuldigung.') },
  { id: 'day.1', when: { night: false }, say: w('Bonjour !', 'Good morning!', 'Guten Morgen!') },
  { id: 'day.2', when: { night: false }, say: w('Belle journée, hein ?', 'Lovely day, isn’t it?', 'Schöner Tag, oder?') },
  { id: 'day.3', when: { night: false }, say: w('Il fait frais ce matin.', "It's chilly this morning.", 'Ist frisch heute Morgen.') },
  // overheard: the Papier «Le marché du dimanche à Aligre» (app/services/revue/evergreen), its own claims
  { id: 'news.aligre.1', salience: 1, say: w("Demain, je vais au marché d'Aligre.", "Tomorrow I'm going to the Aligre market.", 'Morgen gehe ich auf den Markt in Aligre.') },
  { id: 'news.aligre.2', salience: 1, say: w("Aligre, c'est ouvert six matins sur sept.", 'Aligre is open six mornings out of seven.', 'Aligre hat an sechs von sieben Morgen geöffnet.') },
  { id: 'news.aligre.3', salience: 1, say: w("Le marché couvert d'Aligre, c'est Beauvau.", "Aligre's covered market is the Beauvau.", 'Die Markthalle in Aligre heißt Beauvau.') },
  // the quarter talks about you, from your second visit
  { id: 'you.family', when: { 't1.told': 'family', visits: { min: 2 } }, salience: 2, say: w("C'est vous, la famille d'Odile ?", "Are you Odile's family?", 'Sind Sie Odiles Familie?') },
  { id: 'you.selling', when: { 't1.told': 'selling', visits: { min: 2 } }, salience: 2, say: w("C'est vous qui vendez, au-dessus du Mistral ?", "Are you the one selling, above Le Mistral?", 'Sind Sie die Person, die über dem Mistral verkauft?') },
];

/** The barks that mention the market put it in your carnet as a place you heard of. */
export const BARK_PLACES: Record<string, string> = {
  'news.aligre.1': 'marche_aligre',
  'news.aligre.2': 'marche_aligre',
  'news.aligre.3': 'marche_aligre',
};

/* ------------------------------------------------------------------------------------------ */
/* when you come back, and what tomorrow holds                                                */
/* ------------------------------------------------------------------------------------------ */

export const WHILE_AWAY: Bark[] = [
  { id: 'away.key', when: { 'item.cle_cigale': 'margaux_barman' }, salience: 4, say: w('Margaux a rangé ta clé derrière la caisse.', 'Margaux put your key away behind the till.', 'Margaux hat deinen Schlüssel hinter der Kasse verstaut.') },
  { id: 'away.card', when: { 't1.told': 'family' }, salience: 3, say: w('Gus a écrit une fiche sur toi. Elle est tombée sous le zinc.', 'Gus wrote an index card about you. It fell under the zinc.', 'Gus hat eine Karteikarte über dich geschrieben. Sie ist unter die Theke gefallen.') },
  { id: 'away.grade', when: { 't1.told': 'selling' }, salience: 3, say: w('Lila a donné une note à ta soirée : sept sur vingt.', 'Lila gave your evening a grade: seven out of twenty.', 'Lila hat deinem Abend eine Note gegeben: sieben von zwanzig.') },
  { id: 'away.cup', when: { 't1.cafe': 'declined' }, salience: 2, say: w("Le café crème est resté devant le tabouret d'Odile.", "The café crème stayed in front of Odile's stool.", 'Der Café Crème blieb vor Odiles Hocker stehen.') },
  { id: 'away.soup', salience: 1, say: w('Marin a gardé une assiette de soupe.', 'Marin kept a bowl of soup aside.', 'Marin hat einen Teller Suppe aufgehoben.') },
  { id: 'away.aligre', when: { 'world.marche_aligre': 'en_chantier' }, salience: 2, say: w("Un échafaudage est monté au marché d'Aligre.", 'Scaffolding went up at the Aligre market.', 'Am Markt in Aligre steht jetzt ein Gerüst.') },
  { id: 'away.aligre_open', when: { 'world.marche_aligre': 'open', 'place.marche_aligre': { set: false } }, salience: 2, say: w("Le marché d'Aligre est ouvert. Tu peux y aller.", 'The Aligre market is open. You can go there.', 'Der Markt in Aligre ist offen. Du kannst hingehen.') },
];


/* ------------------------------------------------------------------------------------------ */
/* the carnet's words                                                                         */
/* ------------------------------------------------------------------------------------------ */

export const NAMES: Record<CastId, string> = {
  augustin_de_roncourt: 'Gus',
  marin_leveque: 'Marin',
  lila_bonnet: 'Lila',
  margaux_barman: 'Margaux',
  camille_marchand: 'Camille',
};

/** How someone sees you, in a sentence that names them and never agrees with you. */
export function regardWords(who: CastId, r: number): Words {
  const n = NAMES[who];
  if (r <= -2) return w(`${n} se méfie de toi.`, `${n} doesn't trust you.`, `${n} misstraut dir.`);
  if (r === -1) return w(`${n} t'a à l'œil.`, `${n} is keeping an eye on you.`, `${n} behält dich im Auge.`);
  if (r === 0) return w(`${n} ne sait pas encore quoi penser de toi.`, `${n} doesn't know what to make of you yet.`, `${n} ist sich bei dir noch nicht sicher.`);
  if (r === 1) return w(`${n} t'aime bien.`, `${n} likes you.`, `${n} mag dich.`);
  return w(`${n} est de ton côté.`, `${n} is on your side.`, `${n} steht auf deiner Seite.`);
}

/** One more thing the carnet says about someone, from what happened. */
export const NOTES: Array<Bark & { who: CastId }> = [
  { id: 'note.gus.nerve', who: 'augustin_de_roncourt', when: { 't1.told': 'question' }, salience: 2, say: w('Gus aime ton aplomb.', 'Gus likes your nerve.', 'Gus mag deine Chuzpe.') },
  { id: 'note.gus.plans', who: 'augustin_de_roncourt', when: { 't1.told': 'selling' }, salience: 2, say: w('Gus se méfie de tes projets.', 'Gus is wary of your plans.', 'Gus traut deinen Plänen nicht.') },
  { id: 'note.margaux.key', who: 'margaux_barman', when: { 'item.cle_cigale': 'margaux_barman' }, salience: 3, say: w('Margaux garde la clé.', 'Margaux is keeping the key.', 'Margaux bewahrt den Schlüssel auf.') },
  { id: 'note.margaux.afraid', who: 'margaux_barman', when: { 't1.going_up': 'tomorrow' }, salience: 2, say: w('Margaux a peur, elle aussi.', 'Margaux is afraid too.', 'Margaux hat auch Angst.') },
  { id: 'note.lila.cheek', who: 'lila_bonnet', when: { 't1.told': 'question' }, salience: 2, say: w('Lila aime ton culot.', 'Lila likes your cheek.', 'Lila mag deine Frechheit.') },
  { id: 'note.marin.plate', who: 'marin_leveque', when: { 'marin.fed': true }, salience: 2, say: w('Marin te garde une assiette.', 'Marin keeps a plate for you.', 'Marin hebt dir einen Teller auf.') },
];

export const ITEMS: Record<string, { name: Words; art: string }> = {
  cle_cigale: { name: w('La clé à la cigale', 'The key ring with the cicada', 'Der Schlüsselbund mit der Zikade'), art: 'cle_cigale' },
  enveloppe: { name: w("L'enveloppe du notaire", "The notary's envelope", 'Der Umschlag vom Notariat'), art: 'enveloppe' },
};

export const PLACES: Record<string, Words> = {
  quai_de_valmy: w('Le quai de Valmy', 'The quai de Valmy', 'Der Quai de Valmy'),
  le_mistral: w('Le Mistral', 'Le Mistral', 'Das Mistral'),
  marche_aligre: w("Le marché d'Aligre", 'The Aligre market', 'Der Markt in Aligre'),
};

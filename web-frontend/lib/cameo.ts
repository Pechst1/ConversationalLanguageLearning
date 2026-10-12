/**
 * Les apparitions · the cast leaves its discs.
 *
 * Until now the drawn cast lived in small round portraits and on the story's
 * panels. This module lets them walk in on the rest of the app, uninvited:
 * Romy photobombs a right answer with her camera, Gus notes «génie» in his
 * Carnet after three in a row, Marin cries a little at a long streak, Margaux
 * comforts a second mistake, the whole troupe pops up from the bottom edge for
 * a big streak and takes a bow when a session ends, and anybody you poke on
 * screen pokes back.
 *
 * Everything said is French (one short line, the kind of French the learner
 * can read) with a gloss in the learner's own language underneath.
 *
 * This file is pure: `decideCameo(state, event, now, rand)` returns what to
 * show and the next state, so the rhythm (how often, who, which line) is unit
 * tested. `CameoLayer` (components/cast) draws it; `emitCameo` is how a screen
 * tells the layer that something happened.
 */

export type CameoLang = 'en' | 'de' | 'fr';
export type CameoMood = 'neutre' | 'ravie' | 'surprise' | 'fachee' | 'emue';
export type CameoGag = 'flash' | 'note' | 'coffee' | 'tears' | 'phone' | 'sparkle';
export type CameoTrigger = 'streak' | 'comfort' | 'photobomb' | 'idle' | 'poke' | 'finale' | 'troupe';

export type CameoEvent =
  | { type: 'answer'; correct: boolean; coachId?: string | null }
  | { type: 'idle' }
  | { type: 'poke'; id: string }
  | { type: 'finale' };

export type CameoLine = { fr: string; en: string; de: string };

export type CameoFigure = {
  id: string;
  name: string;
  mood: CameoMood;
  line: CameoLine;
};

export type Cameo = {
  key: number;
  trigger: CameoTrigger;
  /** solo: one figure peeks from a side; troupe: a row pops up from the bottom; poke: the tapped face answers in place. */
  kind: 'solo' | 'troupe' | 'poke';
  edge: 'left' | 'right' | 'bottom';
  figures: CameoFigure[];
  gag?: CameoGag;
  /** How long it stays, in ms. */
  ttl: number;
};

export type CameoState = {
  streak: number;
  wrongRun: number;
  /** When the last unrequested cameo (photobomb, comfort, idle) appeared. */
  lastAmbientAt: number;
  lastIdleAt: number;
  lastId: string | null;
  poke: { id: string; count: number; at: number } | null;
  seq: number;
};

export const INITIAL_CAMEO_STATE: CameoState = {
  streak: 0,
  wrongRun: 0,
  lastAmbientAt: -Infinity,
  lastIdleAt: -Infinity,
  lastId: null,
  poke: null,
  seq: 0,
};

/** Streak lengths that always get a cameo. From six on, the whole troupe. */
export const STREAK_MILESTONES = [3, 6, 10, 15, 20, 30, 50];
/** At most one unrequested cameo in this window, so it stays a surprise. */
export const AMBIENT_COOLDOWN_MS = 45_000;
export const IDLE_COOLDOWN_MS = 180_000;
/** Chance that a right answer outside a milestone is photobombed. */
export const PHOTOBOMB_CHANCE = 0.16;
/** Pokes closer together than this count as the same poking. */
export const POKE_WINDOW_MS = 6_000;

type Who = { id: string; name: string; gag: CameoGag };

export const CAMEO_CAST: readonly Who[] = [
  { id: 'romy_tremblay', name: 'Romy', gag: 'flash' },
  { id: 'augustin_de_roncourt', name: 'Gus', gag: 'note' },
  { id: 'margaux_barman', name: 'Margaux', gag: 'coffee' },
  { id: 'marin_leveque', name: 'Marin', gag: 'tears' },
  { id: 'landlord_marchand', name: 'M. Marchand', gag: 'phone' },
  { id: 'lila_bonnet', name: 'Lila', gag: 'sparkle' },
];

const L = (fr: string, de: string, en: string): CameoLine => ({ fr, de, en });

type Pool = Record<string, Array<[CameoMood, CameoLine]>>;

/** Three, six, ten right in a row: the person whose rule it is, or anyone. */
const STREAK: Pool = {
  romy_tremblay: [
    ['ravie', L('Ne bouge pas… Clic ! C’est pour la Une.', 'Nicht bewegen… Klick! Das kommt auf die Titelseite.', 'Don’t move… Click! That’s for the front page.')],
    ['surprise', L('Encore juste ? Je veux une interview.', 'Schon wieder richtig? Ich will ein Interview.', 'Right again? I want an interview.')],
  ],
  augustin_de_roncourt: [
    ['ravie', L('Je note : « génie ». Avec un G majuscule.', 'Ich notiere: „Genie“. Mit großem G.', 'Noted: “genius”. Capital G.')],
    ['surprise', L('Trois de suite ? Même moi, je n’y arrive pas.', 'Drei am Stück? Nicht mal ich schaffe das.', 'Three in a row? Even I can’t do that.')],
  ],
  margaux_barman: [
    ['ravie', L('Trois de suite ? Le café est pour moi.', 'Drei am Stück? Der Kaffee geht auf mich.', 'Three in a row? Coffee’s on me.')],
    ['ravie', L('Je mets ton nom au tableau du Mistral.', 'Ich schreib deinen Namen an die Tafel im Mistral.', 'Your name goes on the board at Le Mistral.')],
  ],
  marin_leveque: [
    ['emue', L('C’est trop beau… je pleure un peu.', 'Das ist so schön… ich weine ein bisschen.', 'It’s so beautiful… I’m crying a little.')],
    ['ravie', L('Tu es une machine ! Une gentille machine.', 'Du bist eine Maschine! Eine nette Maschine.', 'You’re a machine! A nice machine.')],
  ],
  landlord_marchand: [
    ['ravie', L('Bravo. Je n’augmente pas le loyer. Aujourd’hui.', 'Bravo. Ich erhöhe die Miete nicht. Heute.', 'Well done. I won’t raise the rent. Today.')],
    ['surprise', L('Pas mal… pour un locataire.', 'Nicht schlecht… für einen Mieter.', 'Not bad… for a tenant.')],
  ],
  lila_bonnet: [
    ['ravie', L('Incroyable ! Tu parles mieux que mon chat.', 'Unglaublich! Du sprichst besser als meine Katze.', 'Unbelievable! You speak better than my cat.')],
    ['surprise', L('Attends… tu es français, en fait ?', 'Moment… bist du eigentlich Franzose?', 'Wait… are you actually French?')],
  ],
};

/** The second mistake in a row: somebody turns up on the learner's side. */
const COMFORT: Pool = {
  marin_leveque: [
    ['emue', L('Moi, hier, j’ai dit « bonsoir » à midi.', 'Ich hab gestern mittags „bonsoir“ gesagt.', 'Yesterday I said “good evening” at noon.')],
  ],
  margaux_barman: [
    ['neutre', L('Une erreur ? Ici, on appelle ça un brouillon.', 'Ein Fehler? Hier nennen wir das einen Entwurf.', 'A mistake? Here we call that a draft.')],
  ],
  augustin_de_roncourt: [
    ['neutre', L('Même Victor Hugo a raturé. Beaucoup.', 'Sogar Victor Hugo hat durchgestrichen. Viel.', 'Even Victor Hugo crossed things out. A lot.')],
  ],
  lila_bonnet: [
    ['ravie', L('Respire. Le français, c’est un sport.', 'Atmen. Französisch ist ein Sport.', 'Breathe. French is a sport.')],
  ],
  romy_tremblay: [
    ['neutre', L('Celle-là, je ne la prends pas en photo. Promis.', 'Das fotografiere ich nicht. Versprochen.', 'I’m not photographing that one. Promise.')],
  ],
  landlord_marchand: [
    ['neutre', L('Pas de panique. Le loyer, c’est pire.', 'Keine Panik. Die Miete ist schlimmer.', 'Don’t panic. Rent is worse.')],
  ],
};

/** A right answer, now and then, with somebody walking through the shot. */
const PHOTOBOMB: Pool = {
  romy_tremblay: [['ravie', L('Clic ! Pardon, tu étais trop bien.', 'Klick! Sorry, du sahst zu gut aus.', 'Click! Sorry, you looked too good.')]],
  augustin_de_roncourt: [['neutre', L('Ne fais pas attention à moi. Je passe.', 'Beachte mich nicht. Ich geh nur vorbei.', 'Don’t mind me. Just passing.')]],
  lila_bonnet: [['ravie', L('Coucou ! Non, rien. Continue !', 'Huhu! Nee, nichts. Mach weiter!', 'Hi! No, nothing. Carry on!')]],
  margaux_barman: [['neutre', L('Un petit café ? Non ? D’accord.', 'Ein kleiner Kaffee? Nein? Okay.', 'A little coffee? No? OK.')]],
  marin_leveque: [['surprise', L('Tu as vu mes clés ? Non ? Bon.', 'Hast du meine Schlüssel gesehen? Nein? Gut.', 'Seen my keys? No? Fine.')]],
  landlord_marchand: [['neutre', L('Tout va bien dans l’appartement ? Bien. Bien.', 'Alles gut in der Wohnung? Gut. Gut.', 'All well in the flat? Good. Good.')]],
};

/** Nothing has moved for a while. */
const IDLE: Pool = {
  lila_bonnet: [['surprise', L('Psst… tu dors ?', 'Psst… schläfst du?', 'Psst… are you asleep?')]],
  romy_tremblay: [['surprise', L('Allô ? Il y a quelqu’un ?', 'Hallo? Ist da jemand?', 'Hello? Anyone there?')]],
  augustin_de_roncourt: [['neutre', L('Je peux attendre. J’ai un livre.', 'Ich kann warten. Ich hab ein Buch.', 'I can wait. I have a book.')]],
  margaux_barman: [['neutre', L('Prends ton temps. Le café est encore chaud.', 'Lass dir Zeit. Der Kaffee ist noch warm.', 'Take your time. The coffee’s still warm.')]],
  marin_leveque: [['ravie', L('Allez, encore une, et on va manger !', 'Komm, noch eine, dann gehen wir essen!', 'Come on, one more and we eat!')]],
  landlord_marchand: [['fachee', L('Tic-tac, tic-tac…', 'Tick-tack, tick-tack…', 'Tick-tock, tick-tock…')]],
};

/** Tapping a face. The first poke is a joke; the fifth is a relationship. */
const POKE_FIRST: Record<string, [CameoMood, CameoLine]> = {
  romy_tremblay: ['surprise', L('Pas les yeux !', 'Nicht in die Augen!', 'Not the eyes!')],
  augustin_de_roncourt: ['surprise', L('Pardon ?!', 'Wie bitte?!', 'I beg your pardon?!')],
  margaux_barman: ['ravie', L('Oui ? Un café ?', 'Ja? Einen Kaffee?', 'Yes? A coffee?')],
  marin_leveque: ['surprise', L('Aïe ! Mes boucles !', 'Au! Meine Locken!', 'Ouch! My curls!')],
  landlord_marchand: ['fachee', L('On ne touche pas au propriétaire.', 'Den Vermieter fasst man nicht an.', 'One does not touch the landlord.')],
  lila_bonnet: ['ravie', L('Hé ! Ça chatouille !', 'Hey! Das kitzelt!', 'Hey! That tickles!')],
};
const POKE_AGAIN = L('Encore ?', 'Schon wieder?', 'Again?');
const POKE_STOP = L('Arrête !', 'Hör auf!', 'Stop it!');
const POKE_GIVE_UP = L('Bon… d’accord. Je t’aime bien.', 'Na gut… okay. Ich mag dich.', 'Fine… OK. I like you.');

/** The troupe's interjections: one word each, and every one is French worth having. */
const TROUPE_WORDS: CameoLine[] = [
  L('Bravo !', 'Bravo!', 'Bravo!'),
  L('Chapeau !', 'Hut ab!', 'Hats off!'),
  L('Encore !', 'Zugabe!', 'More!'),
  L('Génial !', 'Genial!', 'Brilliant!'),
  L('Ouah !', 'Wow!', 'Wow!'),
  L('Super !', 'Super!', 'Great!'),
];
const FINALE_WORDS: CameoLine[] = [
  L('À demain !', 'Bis morgen!', 'See you tomorrow!'),
  L('Bien joué !', 'Gut gemacht!', 'Well played!'),
  L('Chapeau !', 'Hut ab!', 'Hats off!'),
  L('Bisous !', 'Küsschen!', 'Kisses!'),
  L('Bravo !', 'Bravo!', 'Bravo!'),
  L('Rideau !', 'Vorhang!', 'Curtain!'),
];

function pick<T>(items: readonly T[], rand: () => number): T {
  return items[Math.min(items.length - 1, Math.floor(rand() * items.length))];
}

function castMember(id: string | null | undefined): Who | null {
  if (!id) return null;
  return CAMEO_CAST.find((who) => who.id === id) ?? null;
}

/** Anyone but whoever came last, so two cameos in a row are two people. */
function someone(rand: () => number, avoid: string | null): Who {
  const pool = CAMEO_CAST.filter((who) => who.id !== avoid);
  return pick(pool, rand);
}

function solo(
  state: CameoState,
  trigger: CameoTrigger,
  who: Who,
  pool: Pool,
  rand: () => number,
  extras: { gag?: boolean; ttl?: number } = {},
): Cameo {
  const [mood, line] = pick(pool[who.id], rand);
  return {
    key: state.seq + 1,
    trigger,
    kind: 'solo',
    edge: rand() < 0.5 ? 'left' : 'right',
    figures: [{ id: who.id, name: who.name, mood, line }],
    gag: extras.gag ? who.gag : undefined,
    ttl: extras.ttl ?? 3600,
  };
}

function troupe(state: CameoState, trigger: 'troupe' | 'finale', rand: () => number, size: number): Cameo {
  const words = trigger === 'finale' ? FINALE_WORDS : TROUPE_WORDS;
  const shuffled = [...CAMEO_CAST].sort(() => rand() - 0.5).slice(0, size);
  const said = [...words].sort(() => rand() - 0.5);
  const figures = shuffled.map((who, i) => ({
    id: who.id,
    name: who.name,
    // Marin cries at the curtain. He always does.
    mood: (who.id === 'marin_leveque' && trigger === 'finale' ? 'emue' : 'ravie') as CameoMood,
    line: said[i % said.length],
  }));
  return { key: state.seq + 1, trigger, kind: 'troupe', edge: 'bottom', figures, ttl: trigger === 'finale' ? 4200 : 3000 };
}

/**
 * The director. Pure: same state, event, clock and dice give the same cameo.
 * Returns `cameo: null` when the moment should pass without anybody.
 */
export function decideCameo(
  state: CameoState,
  event: CameoEvent,
  now: number,
  rand: () => number = Math.random,
): { state: CameoState; cameo: Cameo | null } {
  const next: CameoState = { ...state };
  let cameo: Cameo | null = null;

  if (event.type === 'answer') {
    if (event.correct) {
      next.streak = state.streak + 1;
      next.wrongRun = 0;
      if (STREAK_MILESTONES.includes(next.streak)) {
        if (next.streak >= 6) {
          cameo = troupe(state, 'troupe', rand, Math.min(CAMEO_CAST.length, 2 + Math.floor(next.streak / 5)));
        } else {
          // The rule's own coach is the one who is proudest, when there is one.
          const who = castMember(event.coachId) ?? someone(rand, state.lastId);
          cameo = solo(state, 'streak', who, STREAK, rand, { gag: true, ttl: 4000 });
        }
      } else if (now - state.lastAmbientAt >= AMBIENT_COOLDOWN_MS && rand() < PHOTOBOMB_CHANCE) {
        cameo = solo(state, 'photobomb', someone(rand, state.lastId), PHOTOBOMB, rand, { gag: true });
        next.lastAmbientAt = now;
      }
    } else {
      next.streak = 0;
      next.wrongRun = state.wrongRun + 1;
      if (next.wrongRun === 2 && now - state.lastAmbientAt >= AMBIENT_COOLDOWN_MS / 2) {
        // Not the coach: the coach's face in the band is already making the cross one.
        const avoid = castMember(event.coachId)?.id ?? state.lastId;
        cameo = solo(state, 'comfort', someone(rand, avoid), COMFORT, rand, { ttl: 4200 });
        next.lastAmbientAt = now;
      }
    }
  } else if (event.type === 'idle') {
    if (now - state.lastIdleAt >= IDLE_COOLDOWN_MS && now - state.lastAmbientAt >= AMBIENT_COOLDOWN_MS / 3) {
      cameo = solo(state, 'idle', someone(rand, state.lastId), IDLE, rand, { ttl: 4000 });
      next.lastIdleAt = now;
      next.lastAmbientAt = now;
    }
  } else if (event.type === 'poke') {
    const who = castMember(event.id);
    if (who) {
      const count = state.poke && state.poke.id === who.id && now - state.poke.at < POKE_WINDOW_MS ? state.poke.count + 1 : 1;
      next.poke = { id: who.id, count, at: now };
      const [mood, line]: [CameoMood, CameoLine] = count === 1
        ? POKE_FIRST[who.id]
        : count === 2
          ? ['surprise', POKE_AGAIN]
          : count < 5
            ? ['fachee', POKE_STOP]
            : ['emue', POKE_GIVE_UP];
      cameo = { key: state.seq + 1, trigger: 'poke', kind: 'poke', edge: 'bottom', figures: [{ id: who.id, name: who.name, mood, line }], ttl: 1800 };
      if (count >= 5) next.poke = null;
    }
  } else if (event.type === 'finale') {
    next.streak = 0;
    next.wrongRun = 0;
    cameo = troupe(state, 'finale', rand, CAMEO_CAST.length);
  }

  if (cameo) {
    next.seq = cameo.key;
    if (cameo.kind === 'solo') next.lastId = cameo.figures[0].id;
  }
  return { state: next, cameo };
}

/** The line under the French, in the learner's language; none for French speakers. */
export function cameoGloss(line: CameoLine, lang: CameoLang): string | null {
  if (lang === 'fr') return null;
  return line[lang] || line.en;
}

/* ---------- the bus and the switch ---------- */

export const CAMEO_EVENT = 'atelier:cameo';
export const CAMEO_STORAGE_KEY = 'atelier.cameos';

/** On unless the learner switched it off in Réglages. Never throws. */
export function cameosEnabled(): boolean {
  try {
    return window.localStorage.getItem(CAMEO_STORAGE_KEY) !== 'off';
  } catch {
    return true;
  }
}

export function setCameosEnabled(on: boolean): void {
  try {
    window.localStorage.setItem(CAMEO_STORAGE_KEY, on ? 'on' : 'off');
  } catch {
    // Storage denied: the switch simply does not persist.
  }
}

/** A screen tells the cast that something happened. Safe on the server. */
export function emitCameo(event: CameoEvent): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent<CameoEvent>(CAMEO_EVENT, { detail: event }));
}

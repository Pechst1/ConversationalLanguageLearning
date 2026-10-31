/**
 * Les apparitions · the cast leaves its discs.
 *
 * Until now the drawn cast lived in small round portraits and on the story's
 * panels. This module lets them walk in on the rest of the app, at moments
 * that belong to the story and to the learner's answers:
 *
 *   * whoever walks in is somebody from today's page when there is one (the
 *     day's scene cast, remembered for the day), so the drills feel like the
 *     same afternoon at Le Mistral, not a random visit;
 *   * a run of five right answers brings one of them, ten the whole troupe;
 *   * a second mistake in a row brings somebody to the learner's side, and the
 *     next right answer brings that same person back («Tu vois ?»);
 *   * a new part of the season, once its first page is read, brings the person
 *     whose object that part turns on, holding it (lib/season-items);
 *   * a session ends with the troupe's bow, and anybody you poke pokes back.
 *
 * Everything said is French (one short line, the kind of French the learner
 * can read) with a gloss in the learner's own language underneath.
 *
 * This file is pure: `decideCameo(state, event, now, rand)` returns what to
 * show and the next state, so the rhythm (how often, who, which line) is unit
 * tested. `CameoLayer` (components/cast) draws it; `emitCameo` is how a screen
 * tells the layer that something happened.
 */

import { itemHandedIn, itemKey } from './season-items';
import type { SeasonItemId, SeasonPart } from './season-items';

export type CameoLang = 'en' | 'de' | 'fr';
export type CameoMood = 'neutre' | 'ravie' | 'surprise' | 'fachee' | 'emue';
export type CameoGag = 'flash' | 'note' | 'coffee' | 'tears' | 'phone' | 'sparkle';
export type CameoTrigger =
  | 'streak' | 'comfort' | 'rebound' | 'photobomb' | 'idle' | 'poke' | 'finale' | 'troupe' | 'chapter';

export type CameoEvent =
  | {
    type: 'answer';
    correct: boolean;
    coachId?: string | null;
    /**
     * Which checked answer this is (#302). A screen reports from an effect, and an effect can run
     * more than once for one answer (React's dev double-run, a remount), so the director counts
     * an attempt once however often it is told. A retry is a new attempt with a new id.
     */
    attempt?: string | null;
  }
  | { type: 'idle' }
  | { type: 'poke'; id: string }
  | { type: 'finale'; lead?: string | null }
  /** Somebody the learner has now seen on screen (a speaker, a cast-intro face). */
  | { type: 'met'; ids: ReadonlyArray<string | null | undefined> }
  /** Who is in today's page: they are the ones who walk in on today's drills. */
  | { type: 'scene'; ids: ReadonlyArray<string | null | undefined> }
  /** The learner has read a page of this part of the season. */
  | { type: 'chapter'; part: SeasonPart; /** the gallery: hand it over even if it was before */ replay?: boolean };

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
  /**
   * Why they came, in a few words over the bubble («5 de suite», «Nouvel objet»), so a cameo
   * reads as a reward for something the learner did, not a random visit. None for a poke.
   */
  reason?: CameoLine;
  /** The season object the figure is holding out (`chapter`). */
  item?: SeasonItemId;
  /** How long it stays, in ms. */
  ttl: number;
};

export type CameoState = {
  streak: number;
  wrongRun: number;
  /** The last attempt counted (`answer.attempt`), so one answer told twice is one answer. */
  lastAttempt: string | null;
  /** When the last unrequested cameo (photobomb, comfort, idle) appeared. */
  lastAmbientAt: number;
  lastIdleAt: number;
  lastId: string | null;
  poke: { id: string; count: number; at: number } | null;
  seq: number;
  /** Cast members the learner has met. Only `LATE_CAST` waits on this. */
  met: readonly string[];
  /** Today's page's cast: whoever is in it comes first, and only they photobomb. */
  scene: readonly string[];
  /** Who came to comfort a second mistake, waiting to see the next answer. */
  comforter: string | null;
  /** The season objects already handed over (`itemKey`), each only once. */
  items: readonly string[];
};

export const INITIAL_CAMEO_STATE: CameoState = {
  streak: 0,
  wrongRun: 0,
  lastAttempt: null,
  lastAmbientAt: -Infinity,
  lastIdleAt: -Infinity,
  lastId: null,
  poke: null,
  seq: 0,
  met: [],
  scene: [],
  comforter: null,
  items: [],
};

/**
 * Streak lengths that always get a cameo. From ten on, the whole troupe.
 * (Three was too few: a day opens on three short drills, so somebody popped up on nearly every
 * day's first screen, for answers that had cost nothing.)
 */
export const STREAK_MILESTONES = [5, 10, 15, 20, 30, 50];
export const TROUPE_FROM = 10;
/** At most one unrequested cameo in this window, so it stays a surprise. */
export const AMBIENT_COOLDOWN_MS = 45_000;
export const IDLE_COOLDOWN_MS = 180_000;
/** Chance that a right answer outside a milestone is photobombed (by somebody from today's page). */
export const PHOTOBOMB_CHANCE = 0.12;
/** Pokes closer together than this count as the same poking. */
export const POKE_WINDOW_MS = 6_000;

/**
 * #155: a cameo is somebody the learner knows. Romy is not in the first cast intro (she
 * joins the story later), so she cannot photobomb a drill before she has been on screen.
 */
export const LATE_CAST: readonly string[] = ['romy_tremblay'];

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

/** Five right in a row: somebody from today's page, proud of you. */
const STREAK: Pool = {
  romy_tremblay: [
    ['ravie', L('Ne bouge pas… Clic ! C’est pour la Une.', 'Nicht bewegen… Klick! Das kommt auf die Titelseite.', 'Don’t move… Click! That’s for the front page.')],
    ['surprise', L('Encore juste ? Je veux une interview.', 'Schon wieder richtig? Ich will ein Interview.', 'Right again? I want an interview.')],
  ],
  augustin_de_roncourt: [
    ['ravie', L('Je note : « génie ». Avec un G majuscule.', 'Ich notiere: „Genie“. Mit großem G.', 'Noted: “genius”. Capital G.')],
    ['surprise', L('Cinq de suite ? Même moi, je n’y arrive pas.', 'Fünf am Stück? Nicht mal ich schaffe das.', 'Five in a row? Even I can’t do that.')],
  ],
  margaux_barman: [
    ['ravie', L('Cinq de suite ? Le café est pour moi.', 'Fünf am Stück? Der Kaffee geht auf mich.', 'Five in a row? Coffee’s on me.')],
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

/** The right answer straight after a comfort: the one who comforted comes back. */
const REBOUND: Pool = {
  marin_leveque: [['ravie', L('Tu vois ? Moi aussi, je dis bonsoir le soir.', 'Siehst du? Ich sag jetzt auch abends bonsoir.', 'See? I say good evening in the evening now too.')]],
  margaux_barman: [['ravie', L('Tu vois ? Le brouillon, puis le propre.', 'Siehst du? Erst der Entwurf, dann die Reinschrift.', 'See? First the draft, then the fair copy.')]],
  augustin_de_roncourt: [['ravie', L('Voilà. Victor Hugo serait jaloux.', 'Na also. Victor Hugo wäre neidisch.', 'There. Victor Hugo would be jealous.')]],
  lila_bonnet: [['ravie', L('Tu vois ? Tu as respiré !', 'Siehst du? Du hast geatmet!', 'See? You breathed!')]],
  romy_tremblay: [['ravie', L('Celle-là, je la prends en photo !', 'Das hier fotografiere ich!', 'That one I’m photographing!')]],
  landlord_marchand: [['ravie', L('Bien. Très bien. Je le note.', 'Gut. Sehr gut. Ich notiere es.', 'Good. Very good. I’ll make a note.')]],
};

/** A right answer, now and then, with somebody from today's page walking through the shot. */
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

/** Handing over somebody else's object. */
const HANDOVER = L('Tiens. Ça, c’est à toi maintenant.', 'Hier. Das gehört jetzt dir.', 'Here. This is yours now.');

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

/** Who may appear for this learner right now. */
export function castFor(state: Pick<CameoState, 'met'>): readonly Who[] {
  return CAMEO_CAST.filter((who) => !LATE_CAST.includes(who.id) || state.met.includes(who.id));
}

function castMember(id: string | null | undefined): Who | null {
  if (!id) return null;
  return CAMEO_CAST.find((who) => who.id === id) ?? null;
}

/** Today's page's people the learner may meet in a cameo. */
function sceneCast(state: CameoState): readonly Who[] {
  return castFor(state).filter((who) => state.scene.includes(who.id));
}

/**
 * Somebody from today's page when there is one, else anyone the learner knows; never whoever
 * came last, so two cameos in a row are two people.
 */
function someone(state: CameoState, rand: () => number, avoid: string | null): Who {
  const scene = sceneCast(state);
  const today = scene.filter((who) => who.id !== avoid);
  if (today.length) return pick(today, rand);
  // a one-person page keeps its one person, even twice in a row, before a stranger walks in
  if (scene.length) return pick(scene, rand);
  const pool = castFor(state).filter((who) => who.id !== avoid);
  return pick(pool.length ? pool : castFor(state), rand);
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
  return soloSaying(state, trigger, who, mood, line, rand, extras);
}

function soloSaying(
  state: CameoState,
  trigger: CameoTrigger,
  who: Who,
  mood: CameoMood,
  line: CameoLine,
  rand: () => number,
  extras: { gag?: boolean; ttl?: number; item?: SeasonItemId; edge?: 'left' | 'right' } = {},
): Cameo {
  const side: 'left' | 'right' = rand() < 0.5 ? 'left' : 'right';
  return {
    key: state.seq + 1,
    trigger,
    kind: 'solo',
    edge: extras.edge ?? side,
    figures: [{ id: who.id, name: who.name, mood, line }],
    gag: extras.gag ? who.gag : undefined,
    item: extras.item,
    ttl: extras.ttl ?? 3600,
  };
}

function troupe(state: CameoState, trigger: 'troupe' | 'finale', rand: () => number, size: number, lead: Who | null = null): Cameo {
  const words = trigger === 'finale' ? FINALE_WORDS : TROUPE_WORDS;
  const shuffled = [...castFor(state)].sort(() => rand() - 0.5).slice(0, size);
  // The day's own person takes the bow in the middle of the line.
  if (lead) {
    const rest = shuffled.filter((who) => who.id !== lead.id).slice(0, Math.max(0, size - 1));
    shuffled.splice(0, shuffled.length, ...rest);
    shuffled.splice(Math.floor(shuffled.length / 2), 0, lead);
  }
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

/** Why a cameo came, said over its bubble in the learner's language. */
function reasonFor(cameo: Cameo, streak: number): CameoLine | undefined {
  switch (cameo.trigger) {
    case 'streak':
    case 'troupe':
      return { fr: `${streak} de suite`, de: `${streak} am Stück`, en: `${streak} in a row` };
    case 'comfort':
      return REASONS.comfort;
    case 'rebound':
      return REASONS.rebound;
    case 'photobomb':
      return REASONS.photobomb;
    case 'idle':
      return REASONS.idle;
    case 'finale':
      return REASONS.finale;
    case 'chapter':
      // The object's name is on the card it comes on; the tag only says what kind of moment it is.
      return REASONS.chapter;
    default:
      return undefined;
  }
}

const REASONS = {
  comfort: L('Deux erreurs de suite', 'Zwei Fehler am Stück', 'Two mistakes in a row'),
  rebound: L('Et maintenant, juste !', 'Und jetzt richtig!', 'And now it’s right!'),
  photobomb: L('Vu dans la page du jour', 'Aus der heutigen Folge', 'From today’s page'),
  idle: L('Une pause ?', 'Eine Pause?', 'Taking a break?'),
  finale: L('Fin de la séance', 'Ende der Einheit', 'End of the session'),
  chapter: L('Nouvel objet de la saison', 'Neuer Gegenstand der Staffel', 'New object of the season'),
};

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
    // The same checked answer told again is not a second answer.
    if (event.attempt && event.attempt === state.lastAttempt) return { state, cameo: null };
    next.lastAttempt = event.attempt ?? null;
    const comforter = castFor(state).find((who) => who.id === state.comforter) ?? null;
    next.comforter = null;
    if (event.correct) {
      next.streak = state.streak + 1;
      next.wrongRun = 0;
      if (comforter) {
        // The one who stood beside the learner sees them get it right.
        cameo = solo(state, 'rebound', comforter, REBOUND, rand, { ttl: 3200 });
      } else if (STREAK_MILESTONES.includes(next.streak)) {
        if (next.streak >= TROUPE_FROM) {
          cameo = troupe(state, 'troupe', rand, Math.min(castFor(state).length, 2 + Math.floor(next.streak / 5)));
        } else {
          // The rule's own coach is the one who is proudest, when there is one.
          // The rule's coach is already acting in the verdict, so a colleague leans in with the gag.
          const who = someone(state, rand, castMember(event.coachId)?.id ?? state.lastId);
          cameo = solo(state, 'streak', who, STREAK, rand, { gag: true, ttl: 4000 });
        }
      } else if (
        sceneCast(state).some((who) => who.id !== state.lastId)
        && now - state.lastAmbientAt >= AMBIENT_COOLDOWN_MS
        && rand() < PHOTOBOMB_CHANCE
      ) {
        // Only somebody from today's page wanders through: a stranger to the day would be noise.
        cameo = solo(state, 'photobomb', someone(state, rand, state.lastId), PHOTOBOMB, rand, { gag: true });
        next.lastAmbientAt = now;
      }
    } else {
      next.streak = 0;
      next.wrongRun = state.wrongRun + 1;
      if (next.wrongRun === 2 && now - state.lastAmbientAt >= AMBIENT_COOLDOWN_MS / 2) {
        // Not the coach: the coach's face in the band is already making the cross one.
        const avoid = castMember(event.coachId)?.id ?? state.lastId;
        cameo = solo(state, 'comfort', someone(state, rand, avoid), COMFORT, rand, { ttl: 4200 });
        next.lastAmbientAt = now;
        next.comforter = cameo.figures[0].id;
      }
    }
  } else if (event.type === 'idle') {
    if (now - state.lastIdleAt >= IDLE_COOLDOWN_MS && now - state.lastAmbientAt >= AMBIENT_COOLDOWN_MS / 3) {
      cameo = solo(state, 'idle', someone(state, rand, state.lastId), IDLE, rand, { ttl: 4000 });
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
  } else if (event.type === 'met') {
    const fresh = event.ids.filter((id): id is string => !!id && !next.met.includes(id));
    if (fresh.length) next.met = [...next.met, ...fresh];
  } else if (event.type === 'scene') {
    const ids = event.ids.filter((id): id is string => !!id && CAMEO_CAST.some((who) => who.id === id));
    next.scene = Array.from(new Set(ids));
    // Whoever is on today's page has been seen.
    const fresh = next.scene.filter((id) => !next.met.includes(id));
    if (fresh.length) next.met = [...next.met, ...fresh];
  } else if (event.type === 'chapter') {
    const item = itemHandedIn(event.part);
    if (item && (event.replay || !state.items.includes(itemKey(item)))) {
      if (!state.items.includes(itemKey(item))) next.items = [...state.items, itemKey(item)];
      // The object's own person hands it over; somebody from the page if the learner has not met them.
      const who = castFor(state).find((c) => c.id === item.carrier) ?? someone(state, rand, null);
      // From the left, so the hand holding it out (the figure's right) reaches into the page.
      cameo = soloSaying(state, 'chapter', who, item.mood, who.id === item.carrier ? item.line : HANDOVER, rand, {
        ttl: 6500,
        item: item.id,
        edge: 'left',
      });
      next.lastAmbientAt = now;
    }
  } else if (event.type === 'finale') {
    next.streak = 0;
    next.wrongRun = 0;
    cameo = troupe(state, 'finale', rand, castFor(state).length, castFor(state).find((who) => who.id === event.lead) ?? null);
  }

  if (cameo) {
    cameo.reason = reasonFor(cameo, next.streak);
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

export const CAMEO_MET_KEY = 'atelier.cameoMet';

/** The cast members this browser has seen on screen. Never throws. */
export function readMetCast(): string[] {
  try {
    const raw = JSON.parse(window.localStorage.getItem(CAMEO_MET_KEY) || '[]');
    return Array.isArray(raw) ? raw.filter((id): id is string => typeof id === 'string') : [];
  } catch {
    return [];
  }
}

export function writeMetCast(ids: readonly string[]): void {
  try {
    window.localStorage.setItem(CAMEO_MET_KEY, JSON.stringify(ids));
  } catch {
    // Not remembered: a late cast member waits one more session.
  }
}

// Under `pilot:` so sign-out and an account switch sweep them (lib/pilot-resilience): the next
// learner on this browser never inherits the last one's page or objects.
export const CAMEO_SCENE_KEY = 'pilot:cameo-scene:v1';
export const CAMEO_ITEMS_KEY = 'pilot:cameo-items:v1';

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${now.getMonth() + 1}-${now.getDate()}`;
}

/** Today's page's cast, as remembered for the rest of the local day (a deck after the story). */
export function readSceneCast(): string[] {
  try {
    const raw = JSON.parse(window.localStorage.getItem(CAMEO_SCENE_KEY) || '{}');
    if (!raw || raw.date !== today() || !Array.isArray(raw.ids)) return [];
    return raw.ids.filter((id: unknown): id is string => typeof id === 'string');
  } catch {
    return [];
  }
}

export function writeSceneCast(ids: readonly string[]): void {
  try {
    window.localStorage.setItem(CAMEO_SCENE_KEY, JSON.stringify({ date: today(), ids }));
  } catch {
    // Not remembered: a later deck today draws from everyone the learner knows.
  }
}

/** The season objects this device has been handed. Never throws. */
export function readCameoItems(): string[] {
  try {
    const raw = JSON.parse(window.localStorage.getItem(CAMEO_ITEMS_KEY) || '[]');
    return Array.isArray(raw) ? raw.filter((id): id is string => typeof id === 'string') : [];
  } catch {
    return [];
  }
}

export function writeCameoItems(ids: readonly string[]): void {
  try {
    window.localStorage.setItem(CAMEO_ITEMS_KEY, JSON.stringify(ids));
  } catch {
    // Not remembered: the object may be handed over once more.
  }
}

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

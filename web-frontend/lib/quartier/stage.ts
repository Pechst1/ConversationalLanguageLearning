/**
 * Le Quartier · the stage director: a day of the season played in the quarter. It has blocking for
 * T1 day a («Le mauvais accueil») and day b («La lettre») in the café (`story.STAGED_DAYS`); day b
 * goes on after closing in the stairwell next door, which the room's director plays (`interior.ts`).
 *
 * The words are the story engine's (`story.ts`): in the app the page the server resolved for this
 * learner, read through today's journey; nothing here writes a line of the story. What the
 * director adds is the blocking the Feuilleton's panels describe: where you stand, who walks
 * where, who turns to look, what lies on the zinc, keyed on the page's movement ids. It walks the
 * page in order, plays each panel, asks a question only when the engine asks it, and publishes
 * what the screen should show (a caption, a line, a goal, the answer sheet) while it waits for
 * you: a tap to go on, a walk to the door, a reply in French.
 *
 * Your replies go to the engine, which reads them, answers what you said, asks again when it is
 * unclear, and says which of the question's replies the room plays. The answer sheet opens on an
 * empty field; help comes only when asked, a step at a time, and the engine records it. The café
 * crème and the key are questions like the others: what the room does with the cup and the key
 * ring is acted from the reply the engine read.
 *
 * Between the season's beats you act: walk out (the scene waits for you), answer Margaux's text,
 * and talk to anyone in the moment before the bell and in the free walk after. Those are the
 * engine's gestures (`Story.gesture`); what they change in your carnet the quarter keeps in its
 * memory (`memory.ts`, from `agency.ts`).
 */
import { Euler, Matrix4, Quaternion, Vector3 } from 'three';
import type { Object3D } from 'three';

import { BARK_PLACES, LEAVE, MOMENT, PEOPLE as TALKERS, REPLY_EFFECTS, STREET_BARKS, TEXT_SUITCASE, heardEffects } from './agency';
import type { Hit, Quartier } from './engine';
import { Memory, eligible } from './memory';
import type { CastId, Effect, Value, Words } from './memory';
import { CHAIR, MARKS } from './mistral';
import { AMBIANCES } from './palette';
import { STRIDE } from './pace';
import { PLAN } from './quai';
import { OfflineStory, hookOf, nextTurn, roomOf, storyletOf } from './story';
import type { Answered, Ask, Help, HelpStep, Heard, Mend, Story, StoryHook, StoryLine, StoryPanel, StoryPerson, StoryTurn } from './story';

/** The day's id in the quarter's memory (`t1a`, `t1b`). */
export function dayOf(page: { key: string }) {
  return page.key.replace('.', '');
}

/* ------------------------------------------------------------------------------------------ */
/* what the screen shows                                                                      */
/* ------------------------------------------------------------------------------------------ */

export type Level = 'a2' | 'b1';
export type Native = 'en' | 'de';
export type Phase = 'title' | 'scene' | 'answer' | 'end' | 'roam';

/** The short keys the app's stylesheets use for each person's accent (`--char-*`). */
export type CharKey = 'gus' | 'marin' | 'lila' | 'margaux' | 'camille' | 'toi' | 'passant';

export interface SpeechUi {
  who: string;
  char: CharKey;
  name: string;
  text: string;
  native: string | null;
  direction: string | null;
}

export interface AnswerUi {
  id: string;
  /** a question of the story, or a choice asked as one (the café crème, the key) */
  kind: 'turn' | 'choice';
  char: CharKey;
  to: string;
  /** what to do, in the learner's language */
  task: string | null;
  /** the help the question offers, in order */
  steps: HelpStep[];
  /** the help given so far */
  help: Help[];
  /** the next step of help on offer; null once all of it is given */
  more: HelpStep | null;
  /** the engine is reading (the answer, or a step of help) */
  busy: boolean;
  /** the room asked again: the same question, another try */
  again: boolean;
  /** the answer did not reach the engine: send it again */
  failed: boolean;
}

export interface TalkUi {
  who: string;
  char: CharKey;
  name: string;
  /** what they said last (a slip of register comes first) */
  lines: Array<{ text: string; native: string | null; direction: string | null }>;
  /** what you said to them */
  you: string | null;
  chips: string[];
  /** the chips are help: shown only once asked for */
  chipsOnAsk?: boolean;
  /** waiting for their answer */
  busy?: boolean;
  /** what you said did not reach them */
  failed?: boolean;
}

export interface PhoneUi {
  from: string;
  char: CharKey;
  text: string;
  native: string | null;
  chips: string[];
  /** the chips are help: shown only once asked for */
  chipsOnAsk?: boolean;
  /** your answer, once sent */
  sent: string | null;
  /** theirs */
  reply: { text: string; native: string | null } | null;
}

export interface StageUi {
  phase: Phase;
  caption: { text: string; native: string | null } | null;
  speech: SpeechUi | null;
  /** your reply, as Toi's balloon, while the room takes it in */
  you: string | null;
  /** what the engine made right in your reply, under your balloon */
  mend: Mend | null;
  /** where to go next, with the dotted way on the ground */
  goal: { label: string; native: string } | null;
  answer: AnswerUi | null;
  /** a silent panel: the screen letterboxes and the line cards step aside */
  silent: boolean;
  /** a tap anywhere goes on */
  waitingTap: boolean;
  /** the movement on stage, for tests and the progress bar */
  beat: string | null;
  progress: number;
  /** in the free walk afterwards: who you last tapped */
  met: { char: CharKey; name: string; at: number } | null;
  /** you may walk out of the scene now */
  canLeave: boolean;
  /** you walked out: the scene waits */
  away: boolean;
  /** a line outside the script (asking why you leave, greeting you back): a tap clears it */
  aside: SpeechUi | null;
  /** the moment before the bell: talk to anyone, then go on */
  moment: { text: string; native: string } | null;
  talk: TalkUi | null;
  /** a line someone says as you pass */
  bark: (SpeechUi & { at: number }) | null;
  phone: PhoneUi | null;
  /** the end card: what you did, and what comes next (a visit's; the story's comes from the engine) */
  recap: { did: Array<{ text: string; native: string }>; tomorrow: Array<{ text: string; native: string }> } | null;
}

/** The sounds a director asks for; `switch` and `tick` are a stairwell's minuterie (the press, its clockwork). */
export type Cue = 'bell' | 'door' | 'key' | 'cup' | 'chair' | 'paper' | 'phone' | 'switch' | 'tick';

/** What a place adds to the sound as it goes (`audio.ts`), each from 0 to 1. */
export interface Din {
  /** a crowd outdoors: about 0.2 a murmur, 1 the roar at the post */
  crowd: number;
  /** a field at the gallop: 0 out of earshot, 1 going past you at the rail */
  hooves: number;
}

/** What the director may ask of the passers-by (`crowd.ts`). */
export interface Street {
  hop(key: string): void;
}

export interface StageOptions {
  level?: Level;
  native?: Native;
  /** sounds the director asks for (the screen plays them, `audio.ts`) */
  onCue?: (cue: Cue) => void;
  /** what the quarter remembers (the screen passes the phone's; tests a fresh one) */
  memory?: Memory;
  street?: Street;
  /**
   * The page goes on in a room of the season (day b's stairwell): the screen builds the room and
   * its director picks the story up at `from`. Without it, the panels play where you are.
   */
  onRoom?: (to: { room: string; story: Story; from: string }) => void;
}

const PEOPLE: Record<string, { char: CharKey; name: string }> = {
  augustin_de_roncourt: { char: 'gus', name: 'Gus' },
  marin_leveque: { char: 'marin', name: 'Marin' },
  lila_bonnet: { char: 'lila', name: 'Lila' },
  margaux_barman: { char: 'margaux', name: 'Margaux' },
  camille_marchand: { char: 'camille', name: 'Camille' },
  toi: { char: 'toi', name: 'Toi' },
};

/** Who someone is on the screen: their accent and the name the cards print. */
export function personOf(key: string): { char: CharKey; name: string } | null {
  return PEOPLE[key] ?? null;
}

/** The app's moods as the troupe's faces (the same table as `MOOD_EXPRESSION` in CastActor). */
const MOOD_EXPRESSION: Record<string, string> = {
  neutral: 'neutre',
  happy: 'joie',
  cross: 'fache',
  moved: 'emu',
  surprised: 'surprise',
  cold: 'neutre',
  malice: 'malice',
};

const UP = new Vector3(0, 1, 0);

const GOALS = {
  door: { label: 'Entre au Mistral', native: { en: 'Go into Le Mistral', de: 'Geh ins Le Mistral' } },
  zinc: { label: 'Va au zinc', native: { en: 'Go to the bar', de: 'Geh zur Theke' } },
};

/** The silent beats of the replies, and what the director acts out for each. */
export const SILENT_BEATS: Record<string, RegExp> = {
  /** Margaux sets down a café crème nobody ordered */
  cup: /\.(a\.r1|c\.r2)$/,
  /** Gus's triumph goes out of him */
  deflate: /\.b\.r2$/,
  /** a «non merci»: Margaux slides the cup to the end of the zinc, before Odile's stool */
  slide: /\.cafe\.declined\.r\d+$/,
  /** the key ring taken: into your pocket */
  pocket: /\.key\.take\.r\d+$/,
  /** Gus reads the price aloud: every face in the café turns to the zinc */
  faces: /\.letter\.gus\.r\d+$/,
};

/**
 * The movements of T1 this director has blocking for, in the order the pages play them: day a,
 * then day b in the café (its stairwell, R1 to R4, and the hook are the room's: `interior.ts`).
 */
export const STAGED = [
  'a.p1', 'a.p2', 'a.p3', 'a.p4', 'a.p5', 'a.turn1', 'a.cafe', 'a.turn2', 'a.key', 'a.hook',
  'b.cup', 'b.camille', 'b.p1', 'b.p2', 'b.p3', 'b.turn1', 'b.p5', 'b.p6', 'b.letter', 'b.key', 'b.r1', 'b.r2', 'b.r3', 'b.r4', 'b.suivre',
];

/** Who takes the notary's letter, by the reply to «À qui tu montres la lettre ?». */
const READERS: Record<string, string> = {
  margaux: 'margaux_barman',
  lila: 'lila_bonnet',
  gus: 'augustin_de_roncourt',
  marin: 'marin_leveque',
};

/** Where the cast spend the rest of the evening, once the day is played. */
const EVENING: Array<[string, Vector3]> = [
  ['augustin_de_roncourt', MARKS.boothCorner],
  ['marin_leveque', MARKS.boothMiddle],
  ['lila_bonnet', MARKS.boothLeft],
  ['margaux_barman', MARKS.zincInside],
  ['camille_marchand', new Vector3(-33.95, MARKS.atZinc.y, -11.0)],
];

/** On the zinc in front of Odile's stool, where a cup nobody drinks ends up. */
const ODILE_PLACE = new Vector3(-35.0, MARKS.zincTop.y - 0.018, -16.45);
/** Behind the till, at the zinc's far end. */
const BEHIND_TILL = new Vector3(-35.62, MARKS.zincTop.y + 0.0, -16.85);

class Cancelled extends Error {}

/* ------------------------------------------------------------------------------------------ */
/* the director                                                                               */
/* ------------------------------------------------------------------------------------------ */

/** The screen with nothing on it (before a title card). */
export const BLANK: StageUi = {
  phase: 'title',
  caption: null,
  speech: null,
  you: null,
  mend: null,
  goal: null,
  answer: null,
  silent: false,
  waitingTap: false,
  beat: null,
  progress: 0,
  met: null,
  canLeave: false,
  away: false,
  aside: null,
  moment: null,
  talk: null,
  bark: null,
  phone: null,
  recap: null,
};

/** What the script shows; while you are away it waits in the snapshot instead of the screen. */
const SCRIPT_KEYS: Array<keyof StageUi> = ['caption', 'speech', 'you', 'mend', 'answer', 'silent', 'waitingTap', 'moment', 'phase'];

/**
 * What the screen asks of whoever directs a place: the season's scene on the quai (`Stage`), or a
 * visit to a place the forge built (`visit.ts`). Both publish a `StageUi` and take the same taps.
 */
export interface Director {
  readonly ui: StageUi;
  subscribe(fn: (ui: StageUi) => void): () => void;
  setLevel(level: Level): void;
  setNative(native: Native): void;
  setStreet(street: Street | undefined): void;
  prepare(): Promise<void>;
  begin(): void;
  tap(): void;
  answer(text: string): void;
  /** the next step of help on the answer sheet */
  askHelp?(): void;
  go(): void;
  skipWalk(): void;
  goOn(): void;
  replay(): void;
  roam(): void;
  leave(): void;
  talkTo(key: string): void;
  talkSay(text: string): void;
  endTalk(): void;
  passerby(key: string, tapped: boolean): void;
  phoneReply(text: string): void;
  closePhone(): void;
  /** the crowd and the hooves, where the place has them */
  din?(): Din;
  dispose(): void;
}

export class Stage implements Director {
  ui: StageUi = { ...BLANK };
  readonly memory: Memory;
  private listeners = new Set<(ui: StageUi) => void>();
  private gen = 0;
  private tapWait: { gen: number; resolve: () => void } | null = null;
  private answerWait: { gen: number; resolve: (text: string) => void } | null = null;
  private momentWait: { gen: number; resolve: () => void } | null = null;
  /** where you are going; `outFirst`: only once you have been out on the quai (the way back in) */
  private goalAt: { to: Vector3; radius: number; look: Vector3; outFirst?: boolean } | null = null;
  private goalResolve: (() => void) | null = null;
  private wayAt = 0;
  private stopTick: () => void;
  private stopHit: () => void;
  private level: Level;
  private native: Native;
  private onCue?: (cue: Cue) => void;
  private onRoom?: StageOptions['onRoom'];
  private street?: Street;
  private story: Story;
  /** the reply each question took today, and the question the engine asks next */
  private routes: Record<string, string> = {};
  private asking: string | null = null;
  /** where the key lies on the zinc, in front of you, and how it lies */
  private keyHome = new Vector3();
  private keyFlat = new Quaternion().setFromEuler(new Euler(0, -0.4, 0));
  /** who has the key ring once the key is settled */
  private keyWith: 'zinc' | 'toi' | 'margaux' = 'zinc';
  /** lets go of whatever you are holding up */
  private holding: (() => void) | null = null;
  /** the scene as you left it, and when */
  private away: {
    snapshot: Partial<StageUi>;
    feet: Vector3;
    since: number;
    texted: boolean;
    beat: string | null;
    wentOut: boolean;
    /** what the engine has said for when you come back */
    back?: StoryLine | null;
  } | null = null;
  private restore: Partial<StageUi> | null = null;
  /** whether the script wants you held still (it is applied when you are not away) */
  private frozenWanted = false;
  private talking: { who: CastId; day: string } | null = null;
  /** the last thing each person said when you came up to them, for when you pass them again */
  private greetings = new Map<string, StoryLine>();
  private barkAt = 0;
  private barkedBy = new Map<string, number>();

  constructor(
    private q: Quartier,
    story?: Story,
    opts: StageOptions = {},
  ) {
    this.level = opts.level ?? 'a2';
    this.native = opts.native ?? 'en';
    this.onCue = opts.onCue;
    this.onRoom = opts.onRoom;
    this.street = opts.street;
    const memory = opts.memory ?? new Memory(false);
    this.memory = memory;
    this.story = story ?? new OfflineStory({ level: this.level, native: this.native, state: () => memory.state() });
    this.stopTick = q.onTick(() => this.tick());
    this.stopHit = q.on((hit) => this.hit(hit));
  }

  /** The day the director plays. */
  get page() {
    return this.story.page;
  }

  /** Its id in the quarter's memory. */
  private get day() {
    return dayOf(this.story.page);
  }

  get replayable() {
    return this.story.replayable;
  }

  /** Today's story, once it is known (before the scene starts). */
  setStory(story: Story) {
    if (this.ui.phase === 'title' || this.ui.phase === 'roam') this.story = story;
  }

  subscribe(fn: (ui: StageUi) => void) {
    this.listeners.add(fn);
    fn(this.ui);
    return () => {
      this.listeners.delete(fn);
    };
  }

  setLevel(level: Level) {
    this.level = level;
  }

  setNative(native: Native) {
    this.native = native;
  }

  setStreet(street: Street | undefined) {
    this.street = street;
  }

  /** The script's changes: while you are away, what it shows waits for your return. */
  private set(patch: Partial<StageUi>) {
    if (this.away) {
      const live: Partial<StageUi> = {};
      (Object.keys(patch) as Array<keyof StageUi>).forEach((k) => {
        if (SCRIPT_KEYS.includes(k)) (this.away!.snapshot as Record<string, unknown>)[k] = patch[k];
        else (live as Record<string, unknown>)[k] = patch[k];
      });
      this.show(live);
      return;
    }
    if (this.restore) {
      // a line was greeting you back: what the script shows now replaces the scene you left
      Object.assign(this.restore, patch);
    }
    this.show(patch);
  }

  /** Straight to the screen. */
  private show(patch: Partial<StageUi>) {
    if (!Object.keys(patch).length) return;
    this.ui = { ...this.ui, ...patch };
    this.listeners.forEach((fn) => fn(this.ui));
  }

  private say(words: Words) {
    return { text: words.fr, native: words[this.native] };
  }

  private speechOf(who: string, words: Words, direction: string | null = null): SpeechUi {
    const p = PEOPLE[who] ?? { char: 'passant' as CharKey, name: 'Quelqu’un' };
    return { who, char: p.char, name: p.name, text: words.fr, native: words[this.native], direction };
  }

  /** A line of the engine's, as a card outside the script. */
  private speechOfLine(line: StoryLine): SpeechUi {
    const p = PEOPLE[line.who] ?? { char: 'passant' as CharKey, name: line.name ?? 'Quelqu’un' };
    return { who: line.who, char: p.char, name: p.name, text: line.text_fr, native: line.text_native ?? null, direction: line.direction ?? null };
  }

  private talkLine(line: StoryLine) {
    return { text: line.text_fr, native: line.text_native ?? null, direction: line.direction ?? null };
  }

  /** The engine's French and its translation, as the carnet keeps words. */
  private words(fr: string, native: string | null): Words {
    return { fr, en: this.native === 'en' ? (native ?? '') : '', de: this.native === 'de' ? (native ?? '') : '' };
  }

  private remember(effects: Effect | Effect[] | undefined, day = this.day) {
    this.memory.apply(day, effects);
  }

  /** What a gesture brought back, into the quarter's memory: what you learned, the flags, the regard. */
  private keep(a: Answered | null, who?: CastId, day = this.day) {
    if (!a) return;
    const effects: Effect[] = [];
    for (const l of a.learned) effects.push({ kind: 'learn', key: l.id, words: this.words(l.text_fr, l.text_native), who });
    for (const [key, value] of Object.entries(a.sets)) effects.push({ kind: 'fact', key, value: value as Value });
    if (who) effects.push(...heardEffects(who, a.heard));
    if (effects.length) this.remember(effects, day);
    // what each says as you come up, as things now stand
    for (const p of a.people ?? []) if (p.hello) this.greetings.set(p.who, p.hello);
  }

  /** Who will talk, as the day's page lists them. */
  private person(key: string): StoryPerson | null {
    return storyletOf(this.story.page, 'talk')?.people.find((p) => p.who === key) ?? null;
  }

  /* ---- what the screen calls ------------------------------------------------------------- */

  /** Print the season's objects the day needs (the key ring, the notary's envelope). */
  async prepare() {
    if (!this.q.props.has('key')) await this.q.addItem('key', 'cle_cigale', 0.17);
    if (!this.q.props.has('envelope')) await this.q.addItem('envelope', 'enveloppe', 0.2);
  }

  /** From the title card: the scene starts on the quai. */
  begin() {
    void this.play();
  }

  /** Go on (a tap on the card or anywhere on the street). */
  tap() {
    if (this.ui.aside) {
      this.dismissAside();
      return;
    }
    if (this.away) return;
    const w = this.tapWait;
    if (w) {
      this.tapWait = null;
      w.resolve();
    }
  }

  /** Your reply to the current question. */
  answer(text: string) {
    if (this.away) return;
    const w = this.answerWait;
    if (w && text.trim()) {
      this.answerWait = null;
      w.resolve(text.trim());
    }
  }

  /** The next step of help on the sheet: the engine records it, then the sheet shows it. */
  askHelp() {
    const a = this.ui.answer;
    if (!a || !a.more || a.busy || this.away) return;
    const step = a.more;
    const gen = this.gen;
    this.set({ answer: { ...a, busy: true } });
    void this.story
      .help(a.id, step)
      .catch((): Help | null => null)
      .then((h) => {
        if (gen !== this.gen) return;
        const now = this.sheet();
        if (!now || now.id !== a.id) return;
        const more = now.steps[now.steps.indexOf(step) + 1] ?? null;
        this.set({ answer: { ...now, busy: false, more, help: h ? [...now.help, h] : now.help } });
      });
  }

  /** «Y aller»: walk me to where I am going. */
  go() {
    const g = this.goalAt;
    if (g) void this.q.walkTo(g.to, STRIDE);
  }

  /** «Directement»: put me there. */
  skipWalk() {
    const g = this.goalAt;
    if (g) {
      this.q.place(g.to, g.look);
      this.checkGoal(true);
    }
  }

  /** «Continuer», from the moment before the bell. */
  goOn() {
    const m = this.momentWait;
    if (m && !this.away) {
      this.momentWait = null;
      m.resolve();
    }
  }

  /** The day again, where the story allows it (the quarter's own copy; the engine keeps a played day). */
  replay() {
    if (this.story.replayable) void this.play();
  }

  /** After the end card: the quarter is yours to walk. */
  roam() {
    const gen = ++this.gen;
    this.clearWaits();
    this.away = null;
    this.restore = null;
    this.talking = null;
    // you put the key ring down where it was, unless it is in your pocket or behind the till
    this.letGo();
    const key = this.prop('key');
    if (key) {
      key.position.copy(this.keyHome);
      key.quaternion.copy(this.keyFlat);
      key.visible = this.keyWith === 'zinc';
    }
    this.q.frozen = false;
    this.frozenWanted = false;
    this.q.look(null);
    this.q.lens(60);
    this.q.showWay(null);
    this.q.openDoor(false);
    // back from somewhere else on the map, you may walk the quai without playing the day
    if (this.memory.places().quai_de_valmy !== 'visited') this.remember({ kind: 'place', id: 'quai_de_valmy', status: 'visited' });
    this.show({ ...BLANK, phase: 'roam', progress: 1 });
    // the evening goes on: everyone back to their place
    for (const [k, at] of EVENING) {
      const f = this.fig(k);
      if (!f || !f.visible) continue;
      f.seat = 0;
      f.lift = 0;
      void this.walkFig(gen, k, at, 0.9).catch(() => undefined);
    }
  }

  /** Walk out of the scene. It waits: come back through the door to pick it up where it was. */
  leave() {
    if (!this.ui.canLeave || this.away) return;
    const s = this.ui;
    this.away = {
      snapshot: { caption: s.caption, speech: s.speech, you: s.you, mend: s.mend, answer: s.answer, silent: s.silent, waitingTap: s.waitingTap, moment: s.moment, phase: s.phase },
      feet: this.q.feet.clone(),
      since: performance.now(),
      texted: false,
      beat: s.beat,
      wentOut: false,
    };
    if (!this.memory.fact('t1.walked_out')) {
      this.remember(LEAVE.effects);
      const away = this.away;
      void this.story.gesture({ storylet: 'walk_out', at: s.beat }).then((a) => {
        this.keep(a);
        if (this.away === away) away.back = a?.beats.flatMap((b) => b.lines)[0] ?? null;
      });
    }
    this.talking = null;
    this.letGo();
    this.q.frozen = false;
    this.q.look(null);
    this.q.lens(60);
    this.q.openDoor(true);
    this.onCue?.('bell');
    // the way back in is the doorway you walk out through: it counts once you have been outside
    this.goalAt = { to: MARKS.doorIn.clone(), radius: 0.9, look: MARKS.atZinc.clone().setY(1.6), outFirst: true };
    this.goalResolve = () => this.comeBack();
    this.wayAt = performance.now() + 2500;
    const asked = storyletOf(this.story.page, 'walk_out')?.lines.find((l) => l.role === 'asked');
    this.show({
      caption: null,
      speech: null,
      you: null,
      mend: null,
      answer: null,
      silent: false,
      waitingTap: false,
      moment: null,
      talk: null,
      phase: 'scene',
      away: true,
      canLeave: false,
      aside: asked ? this.speechOfLine(asked) : null,
      goal: { label: LEAVE.goal.fr, native: LEAVE.goal[this.native] },
    });
    void this.q.walkTo(MARKS.doorOut, 1.6).then(() => {
      if (this.away && this.ui.aside) this.show({ aside: null });
    });
  }

  private comeBack() {
    const a = this.away;
    if (!a) return;
    this.away = null;
    this.q.openDoor(false);
    this.onCue?.('door');
    // the line the engine chose for your return, else the page's for where the scene was
    const back = storyletOf(this.story.page, 'walk_out')?.lines.filter((l) => l.role === 'back') ?? [];
    const line = a.back ?? back.find((l) => l.during && l.during === a.beat) ?? back.find((l) => !l.during);
    if (line) {
      this.restore = a.snapshot;
      const f = this.fig(line.who);
      if (f) {
        f.talk(1.6);
        this.q.look(f.face(), 2.6);
      }
      this.show({ away: false, goal: null, aside: this.speechOfLine(line) });
    } else {
      this.show({ away: false, goal: null, ...a.snapshot });
    }
    void this.q.walkTo(a.feet, 1.9).then(() => {
      if (!this.away) this.q.frozen = this.frozenWanted;
    });
  }

  private dismissAside() {
    const r = this.restore;
    this.restore = null;
    this.show({ aside: null, ...(r ?? {}) });
    if (r && !this.away) this.q.frozen = this.frozenWanted && !this.q.walking ? true : this.q.frozen;
  }

  /** Talk to someone in the room (in the moment before the bell, or in the free walk). */
  talkTo(key: string) {
    const id = key as CastId;
    const person = this.person(key);
    if (!person || !TALKERS[id] || this.away) return;
    const f = this.fig(key);
    if (!f || !f.visible) return;
    const day = this.ui.phase === 'roam' ? 'roam' : this.day;
    if (!this.memory.state()[`met.${id}`]) this.remember({ kind: 'meet', who: id }, day);
    const talking = { who: id, day };
    this.talking = talking;
    f.hop();
    f.talk(1.2);
    this.lookAbove(f.face());
    this.onCue?.('paper');
    const p = PEOPLE[key];
    this.show({ talk: { who: key, char: p.char, name: p.name, lines: [], you: null, chips: [], chipsOnAsk: true, busy: true }, bark: null });
    const gen = this.gen;
    void this.story.gesture({ storylet: 'talk', to: key }).then((a) => {
      if (gen !== this.gen || this.talking !== talking) return;
      this.keep(a, id, day);
      const lines = a?.beats.flatMap((b) => b.lines) ?? [];
      const hello = lines.length ? lines : person.hello ? [person.hello] : [];
      if (hello.length) {
        this.greetings.set(key, hello[0]);
        this.face(id, hello[hello.length - 1].mood ?? undefined);
      }
      const now = this.ui.talk;
      if (!now || now.who !== key) return;
      this.show({ talk: { ...now, busy: false, lines: hello.map((l) => this.talkLine(l)), chips: a?.chips ?? [] } });
    });
  }

  /** What you say to them. */
  talkSay(text: string) {
    const t = this.talking;
    const talk = this.ui.talk;
    if (!t || !talk || !text.trim() || talk.busy) return;
    const said = text.trim();
    this.show({ talk: { ...talk, you: said, busy: true, failed: false } });
    const gen = this.gen;
    void this.story.gesture({ storylet: 'talk', to: t.who, text: said }).then((a) => {
      if (gen !== this.gen || this.talking !== t) return;
      this.keep(a, t.who, t.day);
      const now = this.ui.talk;
      if (!now || now.who !== t.who) return;
      const lines = a?.beats.flatMap((b) => b.lines) ?? [];
      if (lines.length) {
        this.face(t.who, lines[lines.length - 1].mood ?? undefined);
        this.fig(t.who)?.talk(0.9 + lines.reduce((s, l) => s + l.text_fr.length, 0) * 0.045);
      }
      this.show({
        talk: {
          ...now,
          busy: false,
          failed: !a,
          lines: lines.length ? lines.map((l) => this.talkLine(l)) : now.lines,
          chips: a?.chips ?? now.chips,
        },
      });
    });
  }

  endTalk() {
    if (!this.talking && !this.ui.talk) return;
    this.talking = null;
    this.q.look(null);
    this.show({ talk: null });
  }

  /** A passer-by (`crowd.ts`) you passed close to, or tapped: maybe a line. */
  passerby(key: string, tapped: boolean) {
    const now = performance.now();
    const ui = this.ui;
    if (ui.phase === 'title' || ui.phase === 'end' || ui.talk || ui.answer || ui.aside || ui.phone || ui.caption || ui.speech) return;
    if (tapped) this.street?.hop(key);
    if (!tapped && (now - this.barkAt < 9000 || now - (this.barkedBy.get(key) ?? -1e9) < 60000)) return;
    if (tapped && now - (this.barkedBy.get(key) ?? -1e9) < 1500) return;
    const a = AMBIANCES[this.q.ambiance];
    const state: Record<string, Value> = { ...this.memory.state(), rain: a.rain, night: a.night > 0.5 };
    const list = eligible(STREET_BARKS, state);
    if (!list.length) return;
    // a weighted draw: the more salient, the likelier; never the same line twice in a row
    const pool = list.filter((b) => b.id !== this.lastBark);
    const total = pool.reduce((s, b) => s + 1 + (b.salience ?? 0), 0);
    let roll = Math.random() * total;
    const b = pool.find((x) => (roll -= 1 + (x.salience ?? 0)) < 0) ?? pool[0];
    this.lastBark = b.id;
    this.barkAt = now;
    this.barkedBy.set(key, now);
    this.show({ bark: { ...this.speechOf(key, b.say), at: now } });
    const place = BARK_PLACES[b.id];
    if (place && !state[`place.${place}`]) this.remember({ kind: 'place', id: place, status: 'noticed' }, 'roam');
  }

  private lastBark = '';

  /** Your answer to a text. */
  phoneReply(text: string) {
    const p = this.ui.phone;
    if (!p || p.sent || !text.trim()) return;
    const sent = text.trim();
    this.show({ phone: { ...p, sent } });
    this.remember({ kind: 'journal', who: TEXT_SUITCASE.who, words: { fr: `Tu as répondu à Margaux : « ${sent} »`, en: `You replied to Margaux: “${sent}”`, de: `Du hast Margaux geantwortet: „${sent}“` } });
    const gen = this.gen;
    const fallback = storyletOf(this.story.page, 'margaux_text')?.lines.find((l) => l.role === 'answer') ?? null;
    // the answer comes a moment later, as a text does
    const at = performance.now() + 1500;
    void this.story.gesture({ storylet: 'margaux_text', text: sent }).then((a) => {
      if (gen !== this.gen) return;
      this.keep(a);
      const line = a?.beats.flatMap((b) => b.lines)[0] ?? fallback;
      if (!line) return;
      const stop = this.q.onTick(() => {
        if (gen !== this.gen) {
          stop();
          return;
        }
        if (performance.now() < at) return;
        stop();
        const now = this.ui.phone;
        if (now && now.sent === sent) {
          this.onCue?.('phone');
          this.show({ phone: { ...now, reply: { text: line.text_fr, native: line.text_native ?? null } } });
        }
      });
    });
  }

  closePhone() {
    this.show({ phone: null });
  }

  dispose() {
    this.gen++;
    this.clearWaits();
    this.letGo();
    this.stopTick();
    this.stopHit();
    this.listeners.clear();
  }

  /* ---- input and the frame --------------------------------------------------------------- */

  private hit(hit: Hit) {
    if (this.ui.aside && !this.away) {
      this.tap();
      return;
    }
    if (this.tapWait && !this.away) {
      this.tap();
      return;
    }
    const phase = this.ui.phase;
    const free = phase === 'roam' || Boolean(this.ui.moment) || this.away;
    if (free) {
      if (hit.kind === 'person') {
        if (hit.key.startsWith('passant:')) {
          this.passerby(hit.key, true);
          return;
        }
        if (this.away) return;
        if (TALKERS[hit.key as CastId] && this.person(hit.key)) {
          this.talkTo(hit.key);
          return;
        }
        const f = this.q.troupe.get(hit.key);
        f?.hop();
        this.onCue?.('paper');
        const who = PEOPLE[hit.key];
        if (who) this.show({ met: { char: who.char, name: who.name, at: performance.now() } });
      } else if (hit.kind === 'ground') {
        if (this.ui.talk) this.endTalk();
        void this.q.walkTo(hit.point, STRIDE);
      } else if (hit.kind === 'spot' && this.away) {
        this.go();
      }
      return;
    }
    if (phase === 'scene' && this.goalAt) {
      if (hit.kind === 'ground') void this.q.walkTo(hit.point, STRIDE);
      else if (hit.kind === 'spot' || hit.kind === 'person') this.go();
    }
  }

  private tick() {
    const now = performance.now();
    if (this.goalAt) {
      if (now - this.wayAt > 900 && !this.q.walking) {
        this.wayAt = now;
        this.q.showWay(this.goalAt.to);
      }
      this.checkGoal(false);
    }
    // a passing line fades by itself
    if (this.ui.bark && now - this.ui.bark.at > 6500) this.show({ bark: null });
    // a text from Margaux, if you stay away
    const a = this.away;
    if (a && !a.wentOut && !this.q.indoors) a.wentOut = true;
    if (a && !a.texted) {
      const text = storyletOf(this.story.page, 'margaux_text');
      if (text && now - a.since > (text.after_seconds ?? LEAVE.textAfter) * 1000) {
        a.texted = true;
        this.textFromMargaux();
      }
    }
    // may you walk out now?
    const phase = this.ui.phase;
    const canLeave = !this.away && !this.goalAt && this.q.indoors && !this.ui.talk && (phase === 'scene' || phase === 'answer' || Boolean(this.ui.moment)) && this.story.page.movements.length > 0;
    if (canLeave !== this.ui.canLeave) this.show({ canLeave });
    // in the free walk, the cast notice you as you pass
    if (phase === 'roam' && !this.ui.talk && now - this.barkAt > 6000) {
      this.q.troupe.people.forEach((f, key) => {
        if (now - this.barkAt < 6000 || !TALKERS[key as CastId] || !f.visible) return;
        const d = Math.hypot(f.pos.x - this.q.feet.x, f.pos.z - this.q.feet.z);
        if (d > 2.4 || now - (this.barkedBy.get(key) ?? -1e9) < 40000) return;
        const hello = this.greetings.get(key) ?? this.person(key)?.hello;
        if (!hello) return;
        this.barkAt = now;
        this.barkedBy.set(key, now);
        f.talk(1.4);
        this.show({ bark: { ...this.speechOfLine(hello), at: now } });
      });
    }
  }

  private textFromMargaux() {
    const s = storyletOf(this.story.page, 'margaux_text');
    const line = s?.lines.find((l) => l.role === 'text');
    if (!s || !line) return;
    this.remember(TEXT_SUITCASE.effects);
    // the engine keeps that you stayed away; the text itself is the page's
    void this.story.gesture({ storylet: 'margaux_text' }).then((a) => this.keep(a));
    this.onCue?.('phone');
    this.show({ phone: { from: line.from_fr ?? TEXT_SUITCASE.from, char: 'margaux', text: line.text_fr, native: line.text_native ?? null, chips: s.chips, chipsOnAsk: true, sent: null, reply: null } });
  }

  private checkGoal(force: boolean) {
    const g = this.goalAt;
    if (!g) return;
    const d = Math.hypot(this.q.feet.x - g.to.x, this.q.feet.z - g.to.z);
    if (!force && g.outFirst && !this.away?.wentOut) return;
    if (force || d < g.radius) {
      this.goalAt = null;
      this.q.showWay(null);
      this.q.stop();
      const r = this.goalResolve;
      this.goalResolve = null;
      r?.();
    }
  }

  private clearWaits() {
    this.tapWait = null;
    this.answerWait = null;
    this.momentWait = null;
    this.goalAt = null;
    this.goalResolve = null;
  }

  /* ---- what the script may do to you, unless you walked out --------------------------------- */

  private look(target: Vector3 | null, strength?: number) {
    if (!this.away) this.q.look(target, strength);
  }

  private lens(fov: number) {
    if (!this.away) this.q.lens(fov);
  }

  private freeze(on: boolean) {
    this.frozenWanted = on;
    if (!this.away && !this.restore) this.q.frozen = on;
  }

  /** Look so that `p` sits in the top half of the frame, clear of the sheet at the bottom. */
  private lookAbove(p: Vector3, strength = 2.4) {
    const d = this.q.camera.position.distanceTo(p);
    this.look(p.clone().add(new Vector3(0, -d * 0.26, 0)), strength);
  }

  /* ---- the waits the script is made of ----------------------------------------------------- */

  private alive(gen: number) {
    if (gen !== this.gen) throw new Cancelled();
  }

  private async waitTap(gen: number) {
    this.set({ waitingTap: true });
    await new Promise<void>((resolve) => {
      this.tapWait = { gen, resolve };
    });
    this.alive(gen);
    this.set({ waitingTap: false });
  }

  private async wait(gen: number, seconds: number) {
    await new Promise<void>((resolve) => {
      const until = performance.now() + seconds * 1000;
      const stop = this.q.onTick(() => {
        if (performance.now() >= until || gen !== this.gen) {
          stop();
          resolve();
        }
      });
    });
    this.alive(gen);
  }

  /** Ease something over a few seconds (t from 0 to 1, smoothstepped). */
  private async tween(gen: number, seconds: number, fn: (t: number) => void) {
    await new Promise<void>((resolve) => {
      const t0 = performance.now();
      const stop = this.q.onTick(() => {
        const raw = Math.min(1, (performance.now() - t0) / (seconds * 1000));
        const t = raw * raw * (3 - 2 * raw);
        if (gen === this.gen) fn(t);
        if (raw >= 1 || gen !== this.gen) {
          stop();
          resolve();
        }
      });
    });
    this.alive(gen);
  }

  /** A place to reach on foot, with the dotted way and «Y aller». */
  private async reach(gen: number, goal: keyof typeof GOALS, to: Vector3, radius: number, look: Vector3) {
    const g = GOALS[goal];
    this.freeze(false);
    this.look(null);
    this.goalAt = { to: to.clone(), radius, look };
    this.wayAt = 0;
    this.set({ goal: { label: g.label, native: g.native[this.native] } });
    await new Promise<void>((resolve) => {
      this.goalResolve = resolve;
    });
    this.alive(gen);
    this.set({ goal: null });
    this.freeze(true);
  }

  /** The answer sheet as it is now, wherever it waits (on the screen, or for your return). */
  private sheet(): AnswerUi | null {
    if (this.away) return (this.away.snapshot.answer as AnswerUi | null | undefined) ?? null;
    return this.ui.answer ?? ((this.restore?.answer as AnswerUi | null | undefined) ?? null);
  }

  /**
   * The answer sheet for a question: an empty field, the task, help on request. What you send goes
   * to the engine; the sheet stays (busy) until it has read it, and says so when it could not.
   */
  private async reply(gen: number, turn: StoryTurn, again: boolean): Promise<Heard> {
    const ask = await this.story.ask(turn.id).catch((): Ask => ({ task: turn.task_native ?? null, help: [] }));
    this.alive(gen);
    const who = PEOPLE[turn.to] ?? { char: 'passant' as CharKey, name: turn.to_name ?? turn.to };
    this.set({
      phase: 'answer',
      speech: null,
      answer: {
        id: turn.id,
        kind: turn.choice ? 'choice' : 'turn',
        char: who.char,
        to: turn.to_name ?? who.name,
        task: ask.task,
        steps: ask.help,
        help: [],
        more: ask.help[0] ?? null,
        busy: false,
        again,
        failed: false,
      },
    });
    for (;;) {
      const text = await new Promise<string>((resolve) => {
        this.answerWait = { gen, resolve };
      });
      this.alive(gen);
      const sheet = this.sheet();
      if (sheet) this.set({ answer: { ...sheet, busy: true, failed: false } });
      try {
        const heard = await this.story.answer(turn.id, text);
        this.alive(gen);
        this.set({ phase: 'scene', answer: null, you: text, mend: heard.mend, speech: null });
        return heard;
      } catch (e) {
        if (e instanceof Cancelled) throw e;
        this.alive(gen);
        const now = this.sheet();
        if (now) this.set({ answer: { ...now, busy: false, failed: true } });
      }
    }
  }

  /* ---- people ----------------------------------------------------------------------------- */

  private fig(key: string) {
    return this.q.troupe.get(key);
  }

  private faceOf(key: string) {
    return this.fig(key)?.face() ?? MARKS.zincTop.clone();
  }

  private face(key: string, mood?: string | null) {
    const f = this.fig(key);
    if (!f) return;
    const expression = MOOD_EXPRESSION[mood ?? 'neutral'] ?? 'neutre';
    if (expression !== f.expression) void this.q.troupe.face(key, expression, f.gesture);
  }

  /** One line: the speaker's face and mood, your head turns to them, the card waits for a tap. */
  private async speak(gen: number, line: StoryLine) {
    if (line.who === 'caption' || line.kind === 'caption') {
      this.set({ caption: { text: line.text_fr, native: line.text_native ?? null }, speech: null });
      await this.waitTap(gen);
      return;
    }
    const who = PEOPLE[line.who] ?? { char: 'passant' as CharKey, name: line.name ?? line.who };
    const f = this.fig(line.who);
    const text = line.text_fr;
    if (f) {
      this.face(line.who, line.mood);
      f.talk(0.9 + text.length * 0.045);
      this.look(f.face(), 3.4);
    }
    if (TALKERS[line.who as CastId] && !this.memory.state()[`met.${line.who}`]) this.remember({ kind: 'meet', who: line.who as CastId });
    const name = line.who === 'camille_marchand' && !this.camilleNamed ? 'Quelqu’un' : who.name;
    if (line.who === 'camille_marchand') this.camilleNamed = true;
    this.set({
      caption: null,
      speech: { who: line.who, char: who.char, name, text, native: line.text_native ?? null, direction: line.direction ?? null },
    });
    await this.waitTap(gen);
  }

  private camilleNamed = false;

  private async lines(gen: number, panel: StoryPanel, before?: (line: StoryLine, i: number) => Promise<void> | void) {
    const ls = panel.lines ?? [];
    for (let i = 0; i < ls.length; i++) {
      if (before) await before(ls[i], i);
      this.alive(gen);
      await this.speak(gen, ls[i]);
    }
  }

  /** A silent panel: the cards step aside, the room holds still, a tap goes on. */
  private async silent(gen: number, seconds: number, action?: () => Promise<void>) {
    this.set({ silent: true, speech: null, caption: null });
    const hold = this.wait(gen, seconds);
    if (action) await action();
    await hold;
    await this.waitTap(gen);
    this.set({ silent: false });
  }

  /** Walk someone along the streets (or across the room) to a point. */
  private async walkFig(gen: number, key: string, to: Vector3, speed = 1.1) {
    const f = this.fig(key);
    if (!f) return;
    const from = this.q.nav.nearest(f.pos.x, f.pos.z, 3);
    const start = from ? new Vector3(from[0], this.q.nav.heightAt(from[0], from[1]), from[1]) : f.pos.clone();
    const path = this.q.nav.path(start, to) ?? [to.clone()];
    f.walk([start, ...path], speed);
    await new Promise<void>((resolve) => {
      const stop = this.q.onTick(() => {
        if (!f.walking || gen !== this.gen) {
          stop();
          resolve();
        }
      });
    });
    this.alive(gen);
  }

  /** A point a little in front of you, toward a target (where Gus stops to bow). */
  private before(you: Vector3, toward: Vector3, gap: number) {
    const d = new Vector3(toward.x - you.x, 0, toward.z - you.z).normalize();
    return new Vector3(you.x + d.x * gap, you.y, you.z + d.z * gap);
  }

  private prop(key: string) {
    return this.q.props.get(key)?.object ?? null;
  }

  /** The turn that shows a lying card upright to someone looking along `fwd`. */
  private facing(fwd: Vector3, spin = 0) {
    const f = fwd.clone().normalize();
    const r = new Vector3().crossVectors(f, UP).normalize();
    const u = new Vector3().crossVectors(r, f);
    const turn = new Quaternion().setFromRotationMatrix(new Matrix4().makeBasis(r, f.clone().negate(), u.negate()));
    return spin ? turn.multiply(new Quaternion().setFromAxisAngle(UP, spin)) : turn;
  }

  /** Something held up in front of you: `right` and `down` in parts of the half-view. */
  private inView(right: number, down: number, dist: number) {
    const cam = this.q.camera;
    const f = cam.getWorldDirection(new Vector3());
    const r = new Vector3().crossVectors(f, UP).normalize();
    const u = new Vector3().crossVectors(r, f);
    const half = Math.tan((cam.fov * Math.PI) / 360) * dist;
    const pos = cam.position.clone().addScaledVector(f, dist).addScaledVector(r, right * half * cam.aspect).addScaledVector(u, -down * half);
    return { pos, turn: this.facing(f, -0.35) };
  }

  /** Move a prop to a place and a turn; the goal is asked again each frame, so it can follow your eyes. */
  private async carry(gen: number, obj: Object3D, seconds: number, to: () => { pos: Vector3; turn: Quaternion }) {
    this.letGo();
    const p0 = obj.position.clone();
    const q0 = obj.quaternion.clone();
    await this.tween(gen, seconds, (t) => {
      const g = to();
      obj.position.lerpVectors(p0, g.pos, t);
      obj.quaternion.slerpQuaternions(q0, g.turn, t);
    });
  }

  /** Keep holding a prop up in front of you while the eyes move, until `letGo`. */
  private hold(obj: Object3D, right: number, down: number, dist: number) {
    this.letGo();
    this.holding = this.q.onTick(() => {
      const g = this.inView(right, down, dist);
      obj.position.copy(g.pos);
      obj.quaternion.copy(g.turn);
    });
  }

  private letGo() {
    this.holding?.();
    this.holding = null;
  }

  /** The key ring back on the zinc, flat, where it was. */
  private async keyBack(gen: number) {
    const key = this.prop('key');
    if (key && key.position.distanceTo(this.keyHome) > 0.02) await this.carry(gen, key, 0.6, () => ({ pos: this.keyHome, turn: this.keyFlat }));
  }

  /* ---- the day ------------------------------------------------------------------------------ */

  private reset() {
    const q = this.q;
    q.stop();
    q.frozen = false;
    this.frozenWanted = false;
    q.look(null);
    q.lens(60);
    q.openDoor(false);
    q.setNeon(1);
    q.showWay(null);
    q.place(PLAN.start.pos, PLAN.start.look);
    const t = q.troupe;
    const stand = (key: string, at: Vector3, expression = 'neutre') => {
      const f = t.get(key);
      if (!f) return;
      f.place(at);
      f.visible = true;
      f.seat = 0;
      f.lift = 0;
      if (f.expression !== expression) void t.face(key, expression, null);
    };
    // through the window: Gus on the booth's bench, mid-anecdote; Marin and Lila listening
    stand('augustin_de_roncourt', MARKS.boothBench, 'joie');
    stand('marin_leveque', MARKS.boothMiddle);
    stand('lila_bonnet', MARKS.boothLeft, 'malice');
    stand('margaux_barman', MARKS.zincInside);
    const camille = t.get('camille_marchand');
    if (camille) {
      camille.place(MARKS.doorway);
      camille.visible = false;
    }
    // the zinc, empty; the chair tucked in
    this.keyHome.set(MARKS.atZinc.x - 1.25, MARKS.zincTop.y + 0.008, MARKS.atZinc.z + 0.05);
    this.keyWith = 'zinc';
    this.letGo();
    for (const k of ['key', 'envelope', 'cup']) {
      const p = this.prop(k);
      if (p) p.visible = false;
    }
    this.prop('key')?.quaternion.copy(this.keyFlat);
    const chair = this.prop('chair');
    if (chair) {
      chair.position.copy(CHAIR.tucked);
      chair.rotation.set(0, 0, 0);
    }
    this.envHome.set(this.keyHome.x + 0.04, this.keyHome.y - 0.006, this.keyHome.z - 0.17);
    this.camilleNamed = false;
    this.closedUp = false;
    this.away = null;
    this.restore = null;
    this.talking = null;
    if (this.day === 't1b') this.resetB();
  }

  /** Where the notary's envelope lies on the zinc, once it is out. */
  private envHome = new Vector3();
  /** the café has closed for the night (day b): the regulars gone, the neon off */
  private closedUp = false;

  /**
   * Day b: the next evening at the zinc, the regulars in the booth, the envelope in front of you.
   * The key ring is where day a left it: behind the till (the page asks Margaux for it), or yours.
   * After a «non merci» the cup is still in front of Odile's stool.
   */
  private resetB() {
    const page = this.story.page;
    this.q.place(MARKS.atZinc, MARKS.doorway.clone().setY(1.6));
    for (const [k, at] of EVENING) {
      const f = this.fig(k);
      if (!f || k === 'camille_marchand') continue;
      f.place(at);
      f.visible = true;
    }
    const env = this.prop('envelope');
    if (env) {
      env.position.copy(this.envHome);
      env.rotation.set(0, 0.25, 0);
      env.visible = true;
    }
    this.keyWith = page.movements.some((m) => m.id === 'b.key') ? 'margaux' : 'toi';
    const cup = this.prop('cup');
    if (cup && page.movements.some((m) => m.id === 'b.cup')) {
      cup.position.copy(ODILE_PLACE);
      cup.visible = true;
    }
    // Camille is known since yesterday's hook: the cards print the name
    this.camilleNamed = true;
  }

  /** Stand someone up in full who waited as a silhouette (Camille in the doorway, day a). */
  private async inFull(key: string, height: number) {
    const t = this.q.troupe;
    const f = t.get(key);
    if (!f || this.unveiled.has(key)) return;
    this.unveiled.add(key);
    const at = f.pos.clone();
    t.remove(key);
    const g = await t.add({ key, height }, at);
    if (g) g.visible = false;
  }

  private unveiled = new Set<string>();

  private progress(id: string) {
    const all = this.story.page.movements;
    const i = all.findIndex((m) => m.id === id);
    this.set({ beat: id, progress: Math.max(0, i) / all.length });
  }

  private async play() {
    const gen = ++this.gen;
    this.clearWaits();
    // day b plays Camille in the round, at the zinc
    if (this.day === 't1b') await this.inFull('camille_marchand', 1.72);
    if (gen !== this.gen) return;
    this.reset();
    this.memory.beginDay(this.day);
    this.remember([
      { kind: 'place', id: 'quai_de_valmy', status: 'visited' },
      { kind: 'item', id: 'cle_cigale', holder: 'toi' },
      { kind: 'item', id: 'enveloppe', holder: 'toi' },
    ]);
    const page = this.story.page;
    this.routes = {};
    this.asking = nextTurn(page, null, {});
    this.show({ ...BLANK, phase: 'scene' });
    try {
      for (const m of page.movements) {
        this.alive(gen);
        // the page goes on in a room of the season: the screen builds it, and its director plays on
        const room = roomOf(m);
        if (room && this.onRoom) {
          await this.toRoom(gen, room, m.id);
          return;
        }
        if (m.kind === 'turn') {
          // a question the engine does not ask today (its `only_after` did not hold) is not asked here either
          if (m.id === this.asking) await this.turn(gen, m);
        } else if (m.kind === 'hook') {
          // the moment before the bell is the day's that has people to talk to
          if (storyletOf(page, 'talk')) await this.moment(gen);
          await this.hook(gen, m);
        } else {
          await this.panel(gen, m);
        }
      }
      this.freeze(false);
      this.set({ speech: null, caption: null, silent: false, waitingTap: false });
      // the engine moves the day on to what follows the scene before the end card says what that is
      await this.story.close().catch(() => undefined);
      this.alive(gen);
      this.set({ phase: 'end', speech: null, caption: null, silent: false, progress: 1 });
      this.show({ recap: this.recap(), canLeave: false });
    } catch (e) {
      if (!(e instanceof Cancelled)) throw e;
    }
  }

  /** The end card's own lines: what you did tonight. What comes next is the engine's. */
  private recap(): StageUi['recap'] {
    const did = this.memory
      .journal()
      .filter((j) => j.day === this.day)
      .slice(0, 4)
      .reverse()
      .map((j) => this.say(j.words));
    return { did, tomorrow: [] };
  }

  /** A panel of the page: its blocking where the director has some, else its lines, spoken in turn. */
  private async panel(gen: number, m: StoryPanel) {
    this.progress(m.id);
    switch (m.id) {
      case 'a.p1':
        await this.p1(gen, m);
        this.remember({ kind: 'place', id: 'le_mistral', status: 'visited' });
        return;
      case 'a.p2':
        return this.p2(gen, m);
      case 'a.p3':
        return this.p3(gen);
      case 'a.p4':
        return this.p4(gen, m);
      case 'a.p5':
        return this.p5(gen, m);
      case 'b.cup':
        return this.bCup(gen);
      case 'b.p1':
        return this.bP1(gen, m);
      case 'b.p2':
        return this.bP2(gen, m);
      case 'b.p3':
        return this.bP3(gen, m);
      case 'b.p5':
        return this.bP5(gen);
      case 'b.p6':
        return this.bP6(gen, m);
      default:
        return this.beat(gen, m);
    }
  }

  /** a.p1 · the quai in the rain; the neon; through the window, the booth. You go in. */
  private async p1(gen: number, panel: StoryPanel) {
    const q = this.q;
    this.freeze(true);
    // your eyes go to the window where Gus is holding forth, then they are yours
    this.look(new Vector3(-28.6, 2.6, -14.5), 0.9);
    await this.lines(gen, panel);
    this.set({ caption: null });
    await this.reach(gen, 'door', MARKS.doorOut, 1.25, new Vector3(-30.5, 1.7, -10.5));
    // the bell, the warmth; two steps in and the door swings shut behind you
    q.openDoor(true);
    this.onCue?.('bell');
    this.look(this.faceOf('augustin_de_roncourt'), 1.6);
    await this.wait(gen, 0.7);
    this.freeze(false);
    await q.walkTo(MARKS.doorIn, 1.15);
    this.alive(gen);
    this.freeze(true);
    q.openDoor(false);
    this.onCue?.('door');
  }

  /** a.p2 · heads turn; Gus freezes on the bench mid-story. */
  private async p2(gen: number, panel: StoryPanel) {
    for (const k of ['augustin_de_roncourt', 'marin_leveque', 'lila_bonnet', 'margaux_barman']) {
      this.fig(k)?.hop();
      await this.wait(gen, 0.09);
    }
    await this.lines(gen, panel);
  }

  /** a.p3 · silent: the zinc, close. The envelope, the key ring with its cicada. Margaux stops. */
  private async p3(gen: number) {
    this.set({ speech: null });
    await this.reach(gen, 'zinc', MARKS.atZinc, 0.75, MARKS.zincTop);
    this.look(this.keyHome, 2.6);
    this.lens(42);
    await this.silent(gen, 2.6, async () => {
      await this.wait(gen, 0.5);
      const env = this.prop('envelope');
      if (env) {
        env.position.set(this.keyHome.x + 0.04, this.keyHome.y - 0.006, this.keyHome.z - 0.17);
        env.rotation.set(0, 0.25, 0);
        env.visible = true;
        this.onCue?.('paper');
      }
      await this.wait(gen, 0.7);
      const key = this.prop('key');
      if (key) {
        key.visible = true;
        key.quaternion.copy(this.keyFlat);
        this.onCue?.('key');
        await this.tween(gen, 0.35, (t) => key.position.set(this.keyHome.x, this.keyHome.y + 0.18 * (1 - t), this.keyHome.z));
      }
      // her hand stops: the card holds its breath, then the smallest start
      await this.wait(gen, 0.6);
      this.fig('margaux_barman')?.hop();
    });
    this.lens(60);
  }

  /** a.p4 · Gus steps down from the bench and crosses the room, bowing far too deep. */
  private async p4(gen: number, panel: StoryPanel) {
    const gus = this.fig('augustin_de_roncourt');
    if (gus) {
      void this.q.troupe.face('augustin_de_roncourt', 'neutre', null);
      this.look(gus.face(), 2.2);
      const follow = this.q.onTick(() => this.look(gus.face(), 2.2));
      await this.walkFig(gen, 'augustin_de_roncourt', MARKS.bowStop, 1.05);
      follow();
      gus.bow(0.72, 1.8);
      this.onCue?.('paper');
      await this.wait(gen, 1.0);
    }
    await this.lines(gen, panel, async (line) => {
      // once he has said his piece, Gus takes his place at the zinc beside you, out of the way
      if (line.who !== 'augustin_de_roncourt' && gus && gus.pos.distanceTo(MARKS.zincBeside) > 0.5) {
        void this.walkFig(gen, 'augustin_de_roncourt', MARKS.zincBeside, 0.9).catch(() => undefined);
      }
    });
  }

  /** a.p5 · Marin pulls out a chair for you; then he cannot help himself. Lila looks at your shoes. */
  private async p5(gen: number, panel: StoryPanel) {
    const marin = this.fig('marin_leveque');
    if (marin) {
      marin.hop();
      this.look(marin.face(), 2.4);
      await this.walkFig(gen, 'marin_leveque', MARKS.pulledChair, 1.0);
      const chair = this.prop('chair');
      if (chair) {
        this.onCue?.('chair');
        const from = chair.position.clone();
        const turn = Math.atan2(this.q.feet.x - CHAIR.pulled.x, this.q.feet.z - CHAIR.pulled.z) + Math.PI;
        await this.tween(gen, 0.7, (t) => {
          chair.position.lerpVectors(from, CHAIR.pulled, t);
          chair.rotation.y = turn * t * 0.35;
        });
      }
    }
    await this.lines(gen, panel, async (line, i) => {
      // Lila's line is a deduction from the evidence: she looks at your feet, and so do you
      if (line.who === 'lila_bonnet' && i === 2) {
        this.look(new Vector3(this.q.feet.x, 0.1, this.q.feet.z).add(this.towardRoom(0.5)), 2.6);
        await this.wait(gen, 0.9);
      }
    });
  }

  private towardRoom(len: number) {
    const d = new Vector3(-31.0 - this.q.feet.x, 0, -15.5 - this.q.feet.z).normalize();
    return d.multiplyScalar(len);
  }

  /* ---- day b, «La lettre» ------------------------------------------------------------------ */

  /** b.cup · silent: yesterday's café crème, cold, in front of Odile's empty stool. Nobody has moved it. */
  private async bCup(gen: number) {
    this.look(ODILE_PLACE, 2.0);
    this.lens(44);
    await this.silent(gen, 2.4);
    this.lens(60);
  }

  /** b.p1 · the bell: Camille, dripping, helmet under one arm, comes to the zinc. A towel, a chocolate. */
  private async bP1(gen: number, panel: StoryPanel) {
    const q = this.q;
    const camille = this.fig('camille_marchand');
    q.openDoor(true);
    this.onCue?.('bell');
    for (const k of ['augustin_de_roncourt', 'marin_leveque', 'lila_bonnet']) this.fig(k)?.hop();
    if (camille) {
      camille.place(MARKS.doorway);
      camille.visible = true;
      this.look(camille.face(), 2.4);
      await this.wait(gen, 0.8);
      const follow = q.onTick(() => this.look(camille.face(), 2.2));
      await this.walkFig(gen, 'camille_marchand', MARKS.zincBeside, 1.0);
      follow();
    }
    q.openDoor(false);
    this.onCue?.('door');
    await this.lines(gen, panel, async (line, i) => {
      // «Chocolat ?»: a cup nobody ordered, in front of Camille (unless yesterday's is still at Odile's place)
      const cup = this.prop('cup');
      if (i === 0 && line.who === 'margaux_barman' && cup && !cup.visible && camille) {
        const to = new Vector3(MARKS.zincBeside.x - 0.95, MARKS.zincTop.y + 0.002, MARKS.zincBeside.z);
        cup.position.copy(to).add(new Vector3(-0.5, 0, 0));
        cup.visible = true;
        this.onCue?.('cup');
        const from = cup.position.clone();
        await this.tween(gen, 0.6, (t) => cup.position.lerpVectors(from, to, t));
      }
    });
  }

  /** b.p2 · Camille and you, face to face; behind you the booth listens without shame. */
  private async bP2(gen: number, panel: StoryPanel) {
    for (const k of ['augustin_de_roncourt', 'marin_leveque', 'lila_bonnet']) {
      this.fig(k)?.hop();
      await this.wait(gen, 0.12);
    }
    // Gus's menu held up as a screen; Marin forgets his soup
    this.fig('augustin_de_roncourt')?.bow(0.2, 1.4);
    await this.lines(gen, panel);
  }

  /** b.p3 · Solvel's card slid across the zinc, a tap on your envelope. */
  private async bP3(gen: number, panel: StoryPanel) {
    this.fig('camille_marchand')?.bow(0.25, 0.9);
    this.onCue?.('paper');
    this.look(this.envHome, 2.4);
    this.lens(48);
    await this.wait(gen, 1.0);
    this.lens(60);
    await this.lines(gen, panel);
  }

  /** b.p5 · silent: the door closes behind Camille; the room turns, as one, to you and the envelope. */
  private async bP5(gen: number) {
    const q = this.q;
    await this.silent(gen, 1.6, async () => {
      const camille = this.fig('camille_marchand');
      if (camille) {
        const follow = q.onTick(() => this.look(camille.face(), 2.0));
        await this.walkFig(gen, 'camille_marchand', MARKS.doorway, 1.15);
        follow();
        q.openDoor(true);
        this.onCue?.('bell');
        await this.wait(gen, 0.6);
        camille.visible = false;
        q.openDoor(false);
        this.onCue?.('door');
      }
      for (const k of ['augustin_de_roncourt', 'marin_leveque', 'lila_bonnet', 'margaux_barman']) this.fig(k)?.hop();
      this.look(this.envHome, 2.2);
    });
  }

  /** b.p6 · Lila pulls her chair up to the zinc; four hands more or less open for the letter. */
  private async bP6(gen: number, panel: StoryPanel) {
    const lila = this.fig('lila_bonnet');
    if (lila) {
      this.onCue?.('chair');
      const follow = this.q.onTick(() => this.look(lila.face(), 2.2));
      await this.walkFig(gen, 'lila_bonnet', MARKS.zincBeside, 1.1);
      follow();
    }
    void this.walkFig(gen, 'augustin_de_roncourt', MARKS.bowStop, 0.9).catch(() => undefined);
    void this.walkFig(gen, 'marin_leveque', MARKS.pulledChair, 0.8).catch(() => undefined);
    await this.lines(gen, panel, (line) => {
      if (line.who === 'augustin_de_roncourt') this.fig(line.who)?.bow(0.4, 1.2);
    });
  }

  /** Where someone standing in the café holds something out to you. */
  private handOf(key: string) {
    const f = this.fig(key);
    if (!f) return null;
    if (key === 'margaux_barman') return f.pos.clone().add(new Vector3(0.42, 0.98, 0.3));
    const d = new Vector3(this.q.feet.x - f.pos.x, 0, this.q.feet.z - f.pos.z).normalize();
    return f.pos.clone().addScaledVector(d, 0.32).add(new Vector3(0, 1.02, 0));
  }

  /** Something into your pocket: up in front of you, then down and out of sight. */
  private async pocket(gen: number, obj: Object3D) {
    await this.carry(gen, obj, 0.5, () => this.inView(0.25, 0.55, 0.45));
    await this.wait(gen, 0.4);
    await this.carry(gen, obj, 0.35, () => this.inView(0.3, 1.4, 0.45));
    obj.visible = false;
  }

  /** The letter, to whoever the engine heard you give it to: read there, then back, or kept. */
  private async letter(gen: number, reply: string, beats: StoryPanel[]) {
    const env = this.prop('envelope');
    const reader = READERS[reply];
    const hand = reader ? this.handOf(reader) : null;
    if (env && hand) {
      this.onCue?.('paper');
      this.look(hand, 2.2);
      await this.carry(gen, env, 0.8, () => ({ pos: hand, turn: this.facing(hand.clone().sub(this.q.camera.position), 0.3) }));
    } else if (env && reply === 'nobody') {
      // into a pocket; Margaux gives a small nod
      this.onCue?.('paper');
      await this.pocket(gen, env);
      this.fig('margaux_barman')?.bow(0.15, 0.8);
    }
    for (const b of beats) await this.beat(gen, b);
    if (!env || !env.visible) return;
    if (reply === 'margaux') {
      // she folds it and slides it back into your inside pocket herself
      this.onCue?.('paper');
      await this.pocket(gen, env);
    } else {
      await this.carry(gen, env, 0.6, () => ({ pos: this.envHome, turn: new Quaternion().setFromEuler(new Euler(0, 0.25, 0)) }));
    }
  }

  /**
   * After closing: the neon off, the regulars gone home through the door, Margaux at the till.
   * The envelope goes into your coat. Once a night.
   */
  private async afterHours(gen: number) {
    if (this.closedUp) return;
    this.closedUp = true;
    const q = this.q;
    this.set({ silent: true, speech: null, caption: null });
    this.look(MARKS.doorway.clone().setY(1.5), 1.6);
    q.setNeon(0);
    this.prop('cup')?.position.copy(ODILE_PLACE);
    const env = this.prop('envelope');
    if (env?.visible) env.visible = false;
    q.openDoor(true);
    this.onCue?.('bell');
    const going = ['augustin_de_roncourt', 'marin_leveque', 'lila_bonnet'].filter((k) => this.fig(k)?.visible);
    await Promise.all(going.map((k, i) => this.walkFig(gen, k, MARKS.doorway.clone().add(new Vector3(0.3 * i, 0, 0.2 * i)), 1.3)));
    for (const k of going) {
      const f = this.fig(k);
      if (f) f.visible = false;
    }
    q.openDoor(false);
    this.onCue?.('door');
    const margaux = this.fig('margaux_barman');
    if (margaux && margaux.pos.distanceTo(MARKS.zincInside) > 0.3) await this.walkFig(gen, 'margaux_barman', MARKS.zincInside, 0.9);
    await this.wait(gen, 0.8);
    this.set({ silent: false });
  }

  /** The key ring Margaux kept behind the till, back to you whatever you said: on the zinc, or held up until you take it. */
  private async keyBack2(gen: number, reply: string, beats: StoryPanel[]) {
    const key = this.prop('key');
    const hand = this.handOf('margaux_barman');
    if (key && hand) {
      key.position.copy(BEHIND_TILL);
      key.quaternion.copy(this.keyFlat);
      key.visible = true;
      this.onCue?.('key');
      if (reply === 'other') {
        this.look(hand, 2.2);
        await this.carry(gen, key, 0.7, () => ({ pos: hand, turn: this.facing(hand.clone().sub(this.q.camera.position), 0.3) }));
      } else {
        this.look(this.keyHome, 2.2);
        await this.carry(gen, key, 0.8, () => ({ pos: this.keyHome, turn: this.keyFlat }));
      }
    }
    for (const b of beats) await this.beat(gen, b);
    if (key?.visible) {
      this.onCue?.('key');
      await this.pocket(gen, key);
    }
    this.keyWith = 'toi';
  }

  /** Out by the café's door after closing: the stairwell is next door, in the same building. */
  private async toRoom(gen: number, room: string, from: string) {
    await this.afterHours(gen);
    this.progress(from);
    this.freeze(false);
    this.look(null);
    this.q.openDoor(true);
    this.onCue?.('bell');
    await this.q.walkTo(MARKS.doorIn, 1.4);
    this.alive(gen);
    this.set({ speech: null, caption: null, silent: false, waitingTap: false });
    this.onRoom?.({ room, story: this.story, from });
  }

  /**
   * A question: the room sets it up, asks it, and waits for your French. The engine reads it and
   * the room plays what it heard; asked again, the sheet opens again on the same question.
   */
  private async turn(gen: number, turn: StoryTurn) {
    this.progress(turn.id);
    await this.setUp(gen, turn);
    await this.lines(gen, turn.panel);
    let again = false;
    for (;;) {
      const heard = await this.reply(gen, turn, again);
      await this.react(gen, turn, heard);
      if (heard.reply !== null || heard.next !== turn.id) {
        if (heard.reply !== null) this.routes[turn.id] = heard.reply;
        this.asking = heard.next;
        break;
      }
      again = true;
    }
    // whatever was said to Margaux, the key ends up back on the zinc in front of you: yours to take, or not
    if (turn.id === 'a.turn2') await this.keyBack(gen);
  }

  /** What happens in the room before a question is asked. */
  private async setUp(gen: number, turn: StoryTurn) {
    if (turn.id === 'a.turn1') {
      // Gus at the zinc beside you: who are you, exactly?
      const gus = this.fig('augustin_de_roncourt');
      if (gus) {
        const follow = this.q.onTick(() => this.look(gus.face(), 2.0));
        await this.walkFig(gen, 'augustin_de_roncourt', MARKS.zincBeside, 0.9);
        follow();
      }
    } else if (turn.id === 'a.cafe') {
      // the cup is in front of you: drink it, or not
      const cup = this.prop('cup');
      if (cup) this.lookAbove(cup.position);
    } else if (turn.id === 'a.turn2') {
      // Margaux turns the cicada in her fingers: are you going up? She holds the key ring out, at her side
      const key = this.prop('key');
      const margaux = this.fig('margaux_barman');
      if (key && margaux) {
        this.onCue?.('key');
        const hand = margaux.pos.clone().add(new Vector3(0.42, 0.98, 0.3));
        const toward = this.facing(hand.clone().sub(this.q.camera.position), 0.3);
        await this.carry(gen, key, 0.8, () => ({ pos: hand, turn: toward }));
      }
      this.fig('marin_leveque')?.bow(0.32, 1.6);
      this.fig('lila_bonnet')?.bow(0.3, 1.5);
    } else if (turn.id === 'a.key') {
      // the key ring on the zinc: take it, or leave it with Margaux
      await this.keyBack(gen);
      this.lookAbove(this.keyHome);
    } else if (turn.id === 'b.turn1') {
      const camille = this.fig('camille_marchand');
      if (camille) this.look(camille.face(), 2.4);
    } else if (turn.id === 'b.letter') {
      // the envelope on the zinc, and four hands more or less open
      this.lookAbove(this.envHome);
    } else if (turn.id === 'b.key') {
      // after closing: Margaux counts the till; behind her, the cicada
      await this.afterHours(gen);
      const margaux = this.fig('margaux_barman');
      if (margaux) this.look(margaux.face(), 2.4);
    }
  }

  /** What the room does with what you said: the first line back, then the reply the engine read. */
  private async react(gen: number, turn: StoryTurn, heard: Heard) {
    this.set({ beat: heard.reply === null ? `${turn.id}.again` : `${turn.id}.${heard.reply}` });
    if (heard.reply !== null) this.remember(REPLY_EFFECTS[`${turn.id}.${heard.reply}`]);
    // your line stays while the room takes it in; a correction stays until you have read it
    if (heard.mend) await this.waitTap(gen);
    else await this.wait(gen, 1.2);
    this.set({ you: null, mend: null });
    // the tail of the talk is the page's own panels after its last question (and the hook's), which
    // the director stages from the page in their turn
    const page = new Set(this.story.page.movements.map((m) => m.id));
    const tail = hookOf(this.story.page)?.panel.id;
    const beats = heard.beats.filter((b) => b.id !== tail && !page.has(b.id));
    if (heard.reply !== null && ['a.cafe', 'a.key', 'b.letter', 'b.key'].includes(turn.id)) {
      const first = beats.filter((b) => /\.ack$/.test(b.id));
      for (const b of first) await this.beat(gen, b);
      const rest = beats.filter((b) => !/\.ack$/.test(b.id));
      if (turn.id === 'a.cafe') await this.cafe(gen, heard.reply, rest);
      else if (turn.id === 'a.key') await this.key(gen, heard.reply, rest);
      else if (turn.id === 'b.letter') await this.letter(gen, heard.reply, rest);
      else await this.keyBack2(gen, heard.reply, rest);
      return;
    }
    for (const b of beats) await this.beat(gen, b);
  }

  /** The café crème nobody ordered, as the engine read your answer: drunk, declined, or refused. */
  private async cafe(gen: number, reply: string, beats: StoryPanel[]) {
    const cup = this.prop('cup');
    const spoken = beats.filter((b) => b.lines.length);
    if (reply === 'drink') {
      const first = spoken[0];
      if (first) await this.speak(gen, first.lines[0]);
      if (cup?.visible) {
        // a sip: the cup comes up to you, and back down
        this.onCue?.('cup');
        const home = cup.position.clone();
        const flat = cup.quaternion.clone();
        await this.carry(gen, cup, 0.7, () => {
          const g = this.inView(0.0, 0.42, 0.42);
          return { pos: g.pos, turn: flat };
        });
        await this.wait(gen, 0.9);
        await this.carry(gen, cup, 0.6, () => ({ pos: home, turn: flat }));
      }
      if (first) for (const l of first.lines.slice(1)) await this.speak(gen, l);
      for (const b of spoken.slice(1)) await this.lines(gen, b);
    } else if (reply === 'declined') {
      // nobody says anything: Margaux slides the cup to the end of the zinc, in front of Odile's stool
      await this.silent(gen, 2.0, async () => {
        const margaux = this.fig('margaux_barman');
        if (margaux) this.look(margaux.face(), 2.4);
        await this.wait(gen, 0.4);
        if (cup) {
          this.look(ODILE_PLACE, 2.0);
          const from = cup.position.clone();
          await this.tween(gen, 1.1, (t) => cup.position.lerpVectors(from, ODILE_PLACE, t));
        }
      });
      for (const b of spoken) await this.lines(gen, b);
    } else if (reply === 'refused') {
      // an eyebrow; the cup goes back; Gus shrugs
      void this.q.troupe.face('margaux_barman', 'surprise', null);
      await this.silent(gen, 1.6, async () => {
        const margaux = this.fig('margaux_barman');
        if (margaux) this.look(margaux.face(), 2.6);
        await this.wait(gen, 0.6);
        if (cup) {
          const from = cup.position.clone();
          const to = from.clone().add(new Vector3(-0.6, 0, 0));
          await this.tween(gen, 0.6, (t) => cup.position.lerpVectors(from, to, t));
          cup.visible = false;
        }
      });
      void this.q.troupe.face('margaux_barman', 'neutre', null);
      for (const b of spoken) {
        await this.lines(gen, b, (l) => {
          if (l.who === 'augustin_de_roncourt') this.fig(l.who)?.bow(0.18, 0.9);
        });
      }
    } else {
      for (const b of beats) await this.beat(gen, b);
    }
  }

  /** The key ring on the zinc, as the engine read your answer: in your pocket, or behind the till. */
  private async key(gen: number, reply: string, beats: StoryPanel[]) {
    const key = this.prop('key');
    const spoken = beats.filter((b) => b.lines.length);
    if (reply === 'take') {
      if (key) {
        this.onCue?.('key');
        await this.carry(gen, key, 0.5, () => this.inView(0.25, 0.55, 0.45));
        await this.wait(gen, 0.5);
        await this.carry(gen, key, 0.35, () => this.inView(0.3, 1.4, 0.45));
        key.visible = false;
      }
      this.keyWith = 'toi';
      for (const b of spoken) await this.lines(gen, b);
    } else if (reply === 'leave') {
      const margaux = this.fig('margaux_barman');
      if (key && margaux) {
        this.onCue?.('key');
        const hand = margaux.pos.clone().add(new Vector3(0.42, 0.98, 0.3));
        await this.carry(gen, key, 0.7, () => ({ pos: hand, turn: this.keyFlat }));
      }
      for (const b of spoken) await this.lines(gen, b);
      if (key) {
        await this.carry(gen, key, 0.6, () => ({ pos: BEHIND_TILL, turn: this.keyFlat }));
        key.visible = false;
      }
      this.keyWith = 'margaux';
    } else {
      for (const b of beats) await this.beat(gen, b);
    }
  }

  /** The moment before the bell: the room is yours to walk, anyone to talk to. */
  private async moment(gen: number) {
    this.set({ beat: 'a.moment', moment: this.say(MOMENT.caption), speech: null, caption: null });
    this.freeze(false);
    this.look(null);
    await new Promise<void>((resolve) => {
      this.momentWait = { gen, resolve };
    });
    this.alive(gen);
    this.endTalk();
    this.set({ moment: null });
    // back to the zinc for the bell
    if (Math.hypot(this.q.feet.x - MARKS.atZinc.x, this.q.feet.z - MARKS.atZinc.z) > 0.6) {
      await this.q.walkTo(MARKS.atZinc, 2.2);
      this.alive(gen);
    }
    this.freeze(true);
  }

  /** a.hook · the bell again: someone in a wet helmet holds up a key. Two keys, one door. */
  private async hook(gen: number, hook: StoryHook) {
    this.progress(hook.id);
    if (hook.id !== 'a.hook') {
      // a hook the director has no blocking for: its panel, letterboxed
      await this.beat(gen, hook.panel);
      return;
    }
    const q = this.q;
    q.openDoor(true);
    this.onCue?.('bell');
    const camille = this.fig('camille_marchand');
    if (camille) {
      camille.place(MARKS.doorway);
      camille.visible = true;
    }
    for (const k of ['augustin_de_roncourt', 'marin_leveque', 'lila_bonnet']) this.fig(k)?.hop();
    this.look(this.faceOf('camille_marchand'), 2.4);
    await this.wait(gen, 1.0);
    await this.lines(gen, hook.panel, async (line) => {
      if (line.who === 'augustin_de_roncourt') {
        const gus = this.fig('augustin_de_roncourt');
        if (gus) {
          gus.seat = 0;
          // he stops short of Camille and to one side, so you still see Camille past him
          const stop = this.before(MARKS.doorway, MARKS.atZinc, 1.5);
          const d = MARKS.doorway.clone().sub(MARKS.atZinc).setY(0).normalize();
          stop.addScaledVector(new Vector3(-d.z, 0, d.x), 0.95);
          await this.walkFig(gen, 'augustin_de_roncourt', stop, 1.2);
          gus.bow(0.95, 1.6);
          this.onCue?.('paper');
        }
      }
      if (line.who === 'caption') {
        const key = this.prop('key');
        if (this.keyWith === 'margaux') {
          // two keys in one frame: Camille's in the doorway, and yours, held up behind the till
          const margaux = this.fig('margaux_barman');
          if (key && margaux) {
            const hand = margaux.pos.clone().add(new Vector3(0.38, 1.12, 0.32));
            key.position.copy(BEHIND_TILL);
            key.visible = true;
            this.onCue?.('key');
            this.look(hand, 2.0);
            this.lens(52);
            const turn = this.facing(hand.clone().sub(this.q.camera.position), 0.3);
            await this.carry(gen, key, 0.8, () => ({ pos: hand, turn }));
          }
        } else {
          // two keys in one frame: yours, held up in front of you; hers, in the doorway
          this.look(this.faceOf('camille_marchand'), 2.0);
          this.lens(52);
          if (key) {
            key.visible = true;
            this.onCue?.('key');
            await this.carry(gen, key, 0.7, () => this.inView(-0.42, 0.42, 0.5));
            this.hold(key, -0.42, 0.42, 0.5);
          }
        }
      }
    });
    q.openDoor(false);
    this.lens(60);
  }

  /** One beat of a reply: lines, or a silent panel acted out by its id. */
  private async beat(gen: number, b: StoryPanel) {
    const id = b.id;
    // day a's silent beats are its own (day b has replies of the same letters, with lines)
    const dayA = id.startsWith('a.');
    if (dayA && SILENT_BEATS.cup.test(id)) {
      // Margaux sets a café crème in front of you; nobody ordered it
      await this.silent(gen, 2.4, async () => {
        const margaux = this.fig('margaux_barman');
        if (margaux) this.look(margaux.face(), 2.4);
        await this.wait(gen, 0.6);
        const cup = this.prop('cup');
        if (cup) {
          const to = new Vector3(MARKS.atZinc.x - 1.0, MARKS.zincTop.y + 0.002, MARKS.atZinc.z - 0.36);
          const from = to.clone().add(new Vector3(-0.55, 0, 0));
          cup.visible = true;
          this.onCue?.('cup');
          this.look(to, 2.2);
          await this.tween(gen, 0.7, (t) => cup.position.lerpVectors(from, to, t));
        }
      });
      return;
    }
    if (dayA && SILENT_BEATS.deflate.test(id)) {
      // Gus's triumph goes out of him; the room looks from him to you
      void this.q.troupe.face('augustin_de_roncourt', 'neutre', null);
      await this.silent(gen, 2.2, async () => {
        const gus = this.fig('augustin_de_roncourt');
        if (gus) {
          this.look(gus.face(), 2.2);
          await this.tween(gen, 0.9, (t) => (gus.seat = 0.08 * t));
        }
      });
      return;
    }
    if (SILENT_BEATS.faces.test(id) && b.silence && !b.lines.length) {
      // every face in the café turns to the zinc
      await this.silent(gen, 2.0, async () => {
        this.look(new Vector3(-31.0, 1.5, -15.5), 1.4);
        this.q.troupe.people.forEach((f) => f.visible && f.hop());
        await this.wait(gen, 0.4);
        this.q.troupe.people.forEach((f) => f.visible && f.hop());
      });
      return;
    }
    if (dayA && /\.c\.r1$/.test(id)) {
      // you hold up the key ring; the cicada catches the light; Lila jumps up
      const key = this.prop('key');
      if (key) {
        this.onCue?.('key');
        await this.carry(gen, key, 0.5, () => this.inView(0.3, 0.5, 0.5));
        this.hold(key, 0.3, 0.5, 0.5);
      }
      const lila = this.fig('lila_bonnet');
      if (lila) {
        lila.hop();
        await this.wait(gen, 0.3);
        lila.hop();
      }
      await this.lines(gen, b);
      this.letGo();
      await this.keyBack(gen);
      return;
    }
    if (/sell_and_leave\.r1$/.test(id)) {
      await this.lines(gen, b, (line) => {
        const f = this.fig(line.who);
        if (line.who === 'augustin_de_roncourt') f?.hop();
        if (line.who === 'marin_leveque') f?.bow(0.35, 1.2);
        if (line.who === 'lila_bonnet') f?.hop();
      });
      return;
    }
    if (b.silence && !b.lines.length) {
      // a silence the director has no blocking for: the room holds still
      await this.silent(gen, 1.8);
      return;
    }
    await this.lines(gen, b, async (line) => {
      if (line.who === 'augustin_de_roncourt' && line.direction === 'sitting down slowly') {
        const gus = this.fig('augustin_de_roncourt');
        if (gus) await this.tween(gen, 1.2, (t) => (gus.seat = 0.2 * t));
      }
      if (line.direction?.startsWith('triumphant') || line.direction === 'delighted') this.fig(line.who)?.hop();
    });
  }
}

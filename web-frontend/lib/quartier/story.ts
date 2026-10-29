/**
 * Le Quartier · where the day's story comes from.
 *
 * One story, two renderers: the story engine owns every word, every reply it reads and every
 * choice it keeps, and the quarter only stages them. In the app the story is today's journey
 * (`journey-story.ts`): the page the server resolved for this learner (`stage` on the scene step),
 * the answers read through the same attempts endpoint as the Feuilleton's, the help it records,
 * the gestures it keeps beside the story. The stage director (`stage.ts`) asks a `Story` for all
 * of it and adds what the quarter adds: where people stand, what the camera sees, the light.
 *
 * Away from the server (the standalone page, the tests) the quarter plays its own copy of T1 day
 * a (`OfflineStory`, `scenes/t1-a.json`, and the gestures' lines from `agency.ts`). It reads no
 * French: an answer takes the reply whose example it repeats word for word, else the turn's
 * fallback (a choice asks again), and nothing it hears leaves the phone.
 */
import { LEAVE, NAMES, PEOPLE as TALKERS, TEXT_SUITCASE, chipsFor, fold, helloOf, registerOf, respond } from './agency';
import type { CastId, Value, Words } from './memory';
import scene from './scenes/t1-a.json';

/* ------------------------------------------------------------------------------------------ */
/* the page, as the server resolves it for one learner (`steps[kind=scene].prompt.stage`)     */
/* ------------------------------------------------------------------------------------------ */

/** One line of a panel, at the learner's level. */
export interface StoryLine {
  /** a cast id, `toi`, or `caption` */
  who: string;
  name?: string | null;
  /** `speech`, `caption`, `sms`, `letter`, `card`, `toi`, `all` */
  kind?: string | null;
  mood?: string | null;
  direction?: string | null;
  text_fr: string;
  /** the line in the learner's language, for an A1/A2 learner reading English or German */
  text_native?: string | null;
}

export interface StoryPanel {
  kind: 'panel';
  id: string;
  visual?: string | null;
  location_id?: string | null;
  in_frame?: string[] | null;
  /** nobody speaks: the screen letterboxes */
  silence?: boolean | null;
  lines: StoryLine[];
}

export interface StoryTurn {
  kind: 'turn';
  id: string;
  /** who asks */
  to: string;
  to_name?: string | null;
  /** what to do, in the learner's language */
  task_native?: string | null;
  /** «Le choix» asked as a question (the café crème, the key): the Feuilleton shows cards, the quarter takes French */
  choice?: boolean | null;
  /** asked only when an earlier turn took one of these replies (`{"a.turn1": ["a", "c"]}`) */
  only_after?: Record<string, string[]> | null;
  /** the panel that asks the question */
  panel: StoryPanel;
}

export interface StoryHook {
  kind: 'hook';
  id: string;
  role?: string | null;
  panel: StoryPanel;
}

export type StoryMovement = StoryPanel | StoryTurn | StoryHook;

/** A line of a gesture: what it is for (`asked`, `back`, `text`, `answer`), and when it plays. */
export interface StoryletLine extends StoryLine {
  role: string;
  /** only while this movement is on stage (`a.p2`); none: any time */
  during?: string | null;
  /** who a text is from, as the phone shows it */
  from_fr?: string | null;
}

export interface StoryPerson {
  who: string;
  name: string;
  register: 'tu' | 'vous';
  /** what they say as you pass */
  hello?: StoryLine | null;
  bye?: StoryLine | null;
}

/** Something the learner may do that is not an answer: walk out, answer a text, talk to anyone. */
export interface Storylet {
  /** `walk_out`, `margaux_text`, `talk` */
  id: string;
  /** when it comes up: `walk_out`, `away`, `talk` */
  cue: string;
  who: string | null;
  /** how long away before it comes (a text) */
  after_seconds: number | null;
  lines: StoryletLine[];
  /** help only, never shown first */
  chips: string[];
  /** who will talk (free talk) */
  people: StoryPerson[];
}

export interface StoryPage {
  season_id: string;
  /** the tentpole or gap (`t1`) and its day (`a`); `key` is both (`t1.a`) */
  segment: string;
  day: string;
  key: string;
  number?: number | null;
  title_fr: string;
  story_date_fr?: string | null;
  location_id?: string | null;
  /** what the learner practises today, in their language */
  can_do_native?: string | null;
  movements: StoryMovement[];
  storylets: Storylet[];
}

/** The days the quarter can stage, by their blocking: T1 day a, and day b (the café, then the stairwell). */
export const STAGED_DAYS = ['t1.a', 't1.b'];

/** Where a page's panel plays in a room of the season rather than the café: the stairwell and Odile's door (T1 R1–R4). */
export const ROOM_OF: Record<string, string> = {
  stairwell: 'escalier_mistral',
  odile_flat: 'escalier_mistral',
};

/** The room a movement plays in, if it is one (a hook plays where the room's scene ends). */
export function roomOf(m: StoryMovement): string | null {
  const at = m.kind === 'panel' ? m.location_id : m.panel.location_id;
  return (at && ROOM_OF[at]) ?? null;
}

/** The questions of a page, in order. */
export function turnsOf(page: StoryPage): StoryTurn[] {
  return page.movements.filter((m): m is StoryTurn => m.kind === 'turn');
}

/** The hook of a page, if it has one. */
export function hookOf(page: StoryPage): StoryHook | null {
  return page.movements.find((m): m is StoryHook => m.kind === 'hook') ?? null;
}

/**
 * The question asked after `from` (the first one when `from` is null), given the replies the
 * turns took so far: a question whose `only_after` does not hold is not asked.
 */
export function nextTurn(page: StoryPage, from: string | null, routes: Record<string, string>): string | null {
  const turns = turnsOf(page);
  const start = from === null ? 0 : turns.findIndex((t) => t.id === from) + 1;
  if (from !== null && start === 0) return null;
  for (const t of turns.slice(start)) {
    const holds = Object.entries(t.only_after ?? {}).every(([turn, replies]) => replies.includes(routes[turn]));
    if (holds) return t.id;
  }
  return null;
}

export function storyletOf(page: StoryPage, id: string): Storylet | null {
  return page.storylets.find((s) => s.id === id) ?? null;
}

/* ------------------------------------------------------------------------------------------ */
/* a turn: what the engine asks, the help it gives, what it heard                              */
/* ------------------------------------------------------------------------------------------ */

/**
 * Help, one step at a time and only when asked, as in the Feuilleton's answer: a hint in the
 * learner's language, then words to build the answer with, then a whole example. The engine
 * records the hint and the example before it shows them.
 */
export type HelpStep = 'hint' | 'words' | 'example';

export interface Ask {
  /** what to do, in the learner's language */
  task: string | null;
  /** the help this question offers, in the order it is given */
  help: HelpStep[];
}

export interface Help {
  step: HelpStep;
  /** an example, in French */
  text: string | null;
  /** a hint, in the learner's language */
  native: string | null;
  /** words to build the answer with, or the choice's options */
  words: string[];
}

/** One issue in the learner's French, made right. */
export interface Mend {
  span: string;
  corrected: string;
  note: string | null;
}

export interface Heard {
  /** the question answered */
  turn: string;
  /** the reply the engine read the answer as; `null`: it asked again (unclear, or not French) */
  reply: string | null;
  /** what the room does, in order: the first line back, the reply's beats, what follows the question */
  beats: StoryPanel[];
  /** the question now asked; `null` once the talk is over */
  next: string | null;
  closing: boolean;
  mend: Mend | null;
}

/** A gesture, as the engine takes it. */
export type Gesture =
  | { storylet: 'walk_out'; at: string | null }
  /** no text: the learner stayed away and the text comes; a text: their answer to it */
  | { storylet: 'margaux_text'; text?: string }
  | { storylet: 'talk'; to: string; text?: string };

export interface Learned {
  id: string;
  text_fr: string;
  text_native: string | null;
}

/** What a gesture brings back. */
export interface Answered {
  beats: StoryPanel[];
  /** help only, never shown first */
  chips: string[];
  /** the line the engine heard (`margaux.odile`), if any */
  heard: string | null;
  learned: Learned[];
  /** the season flags it sets */
  sets: Record<string, Value>;
  /** who will talk, with what each says now as you come up; none: as the page has them */
  people?: StoryPerson[] | null;
}

export interface Story {
  readonly page: StoryPage;
  /** whether the day may be played again here (the quarter's own copy), or the engine has kept it */
  readonly replayable: boolean;
  /** The room is about to ask this question: what the engine wants, and the help on offer. */
  ask(turnId: string): Promise<Ask>;
  /** What the learner said to a question. */
  answer(turnId: string, text: string): Promise<Heard>;
  /** A step of help, recorded before it is shown; `null` when the question has none of that kind. */
  help(turnId: string, step: HelpStep): Promise<Help | null>;
  /** Something done, not answered; `null` when the engine could not be reached (the gesture is lost). */
  gesture(g: Gesture): Promise<Answered | null>;
  /** The scene has played to its hook: what the engine needs before the rest of the day. */
  close(): Promise<void>;
}

/* ------------------------------------------------------------------------------------------ */
/* the quarter's own copy, for the standalone page and the tests                              */
/* ------------------------------------------------------------------------------------------ */

interface CopySay {
  a2: string;
  b1?: string;
  native?: { en?: string; de?: string };
}

interface CopyLine {
  who: string;
  mood?: string;
  direction?: string;
  say: CopySay;
}

interface CopyPanel {
  kind: 'panel';
  id: string;
  visual?: string;
  location_id?: string;
  in_frame?: string[];
  silence?: boolean;
  lines?: CopyLine[];
}

interface CopyReply {
  id: string;
  examples: string[];
  beats: CopyPanel[];
}

interface CopyTurn {
  kind: 'turn';
  id: string;
  to: string;
  panel: CopyPanel;
  task: { en: string; de: string; fr: string };
  choice?: boolean;
  only_after?: Record<string, string[]>;
  fallback: string;
  replies: CopyReply[];
  after?: CopyPanel[];
}

interface CopyOption {
  id: string;
  label: CopySay;
  examples?: string[];
  beats: CopyPanel[];
}

/** A solve. «Le choix» with someone to ask it (the café crème, the key) is asked as a question. */
interface CopySolve {
  kind: 'solve';
  id: string;
  mechanic: string;
  to?: string;
  prompt?: CopySay;
  task?: { en: string; de: string; fr: string };
  only_after?: Record<string, string[]>;
  options: CopyOption[];
}

type CopyMovement = CopyPanel | CopyTurn | CopySolve | { kind: 'hook'; id: string; role?: string; panel: CopyPanel };

interface Copy {
  episode: string;
  number: number;
  day: string;
  title_fr: string;
  story_date_fr: string;
  location_id: string;
  can_do: { en: string; de: string; fr: string };
  movements: CopyMovement[];
}

/** The copy of T1 day a in the frontend (`scripts/quartier/sync-scene.mjs`). */
export const T1A_COPY = scene as unknown as Copy;

export interface CopyOptions {
  level?: 'a2' | 'b1';
  native?: 'en' | 'de';
}

type Resolved = Required<CopyOptions>;

function lineOf(l: CopyLine, o: Resolved): StoryLine {
  return {
    who: l.who,
    kind: l.who === 'caption' ? 'caption' : 'speech',
    mood: l.mood ?? null,
    direction: l.direction ?? null,
    text_fr: (o.level === 'b1' && l.say.b1) || l.say.a2,
    // as on the server: translations up to A2
    text_native: o.level === 'b1' ? null : (l.say.native?.[o.native] ?? null),
  };
}

function panelOf(p: CopyPanel, o: Resolved): StoryPanel {
  return {
    kind: 'panel',
    id: p.id,
    visual: p.visual ?? null,
    location_id: p.location_id ?? null,
    in_frame: p.in_frame ?? [],
    silence: Boolean(p.silence),
    lines: (p.lines ?? []).map((l) => lineOf(l, o)),
  };
}

/** One of the quarter's own lines (`agency.ts`), as the page carries it. */
function said(who: string, words: Words, o: Resolved, extra: { mood?: string; direction?: string } = {}): StoryLine {
  return {
    who,
    kind: 'speech',
    mood: extra.mood ?? null,
    direction: extra.direction ?? null,
    text_fr: words.fr,
    text_native: o.level === 'b1' ? null : words[o.native],
  };
}

/** Walking out, Margaux's text and free talk, from the quarter's own lines. */
function storyletsOf(o: Resolved): Storylet[] {
  return [
    {
      id: 'walk_out',
      cue: 'walk_out',
      who: LEAVE.asked.who,
      after_seconds: null,
      lines: [
        { role: 'asked', during: null, ...said(LEAVE.asked.who, LEAVE.asked.say, o) },
        { role: 'back', during: null, ...said(LEAVE.resume.who, LEAVE.resume.say, o) },
        { role: 'back', during: 'a.p2', ...said(LEAVE.resumeGus.who, LEAVE.resumeGus.say, o, { mood: LEAVE.resumeGus.mood }) },
      ],
      chips: [],
      people: [],
    },
    {
      id: 'margaux_text',
      cue: 'away',
      who: TEXT_SUITCASE.who,
      after_seconds: LEAVE.textAfter,
      lines: [
        { role: 'text', from_fr: TEXT_SUITCASE.from, ...said(TEXT_SUITCASE.who, TEXT_SUITCASE.say, o), kind: 'sms' },
        { role: 'answer', ...said(TEXT_SUITCASE.who, TEXT_SUITCASE.answer, o), kind: 'sms' },
      ],
      chips: TEXT_SUITCASE.chips,
      people: [],
    },
    {
      id: 'talk',
      cue: 'talk',
      who: null,
      after_seconds: null,
      lines: [],
      chips: [],
      people: (Object.keys(TALKERS) as CastId[]).map((who) => {
        const p = TALKERS[who];
        const hello = helloOf(who, {});
        return { who, name: NAMES[who], register: p.register, hello: said(who, hello.say, o, { mood: hello.mood }), bye: p.bye ? said(who, p.bye, o) : null };
      }),
    },
  ];
}

/** The copy resolved the way the server resolves a page: one level, one language. */
export function pageOfCopy(copy: Copy = T1A_COPY, opts: CopyOptions = {}): StoryPage {
  const o: Resolved = { level: opts.level ?? 'a2', native: opts.native ?? 'en' };
  return {
    season_id: 's1',
    segment: copy.episode,
    day: copy.day,
    key: `${copy.episode}.${copy.day}`,
    number: copy.number,
    title_fr: copy.title_fr,
    story_date_fr: copy.story_date_fr,
    location_id: copy.location_id,
    can_do_native: copy.can_do[o.native],
    movements: copy.movements.flatMap((m): StoryMovement[] => {
      if (m.kind === 'turn') {
        return [{ kind: 'turn', id: m.id, to: m.to, task_native: m.task[o.native], choice: Boolean(m.choice), only_after: m.only_after ?? null, panel: panelOf(m.panel, o) }];
      }
      if (m.kind === 'solve') {
        const q = questionOf(m);
        return q ? [{ kind: 'turn', id: q.id, to: q.to, task_native: q.task?.[o.native] ?? null, choice: true, only_after: q.only_after, panel: panelOf(q.panel, o) }] : [];
      }
      if (m.kind === 'hook') return [{ kind: 'hook', id: m.id, role: m.role ?? null, panel: panelOf(m.panel, o) }];
      return [panelOf(m, o)];
    }),
    storylets: storyletsOf(o),
  };
}

/** A question of the copy: a turn, or a choice asked as one. */
interface Question {
  id: string;
  to: string;
  task: { en: string; de: string; fr: string } | null;
  only_after: Record<string, string[]> | null;
  /** the panel that asks it: a choice's prompt is said by the one who asks */
  panel: CopyPanel;
  choice: boolean;
  /** a turn's replies, or a choice's options, whose label reads as that option too */
  answers: CopyReply[];
  /** what anything else reads as; none: it is asked again */
  fallback: string | null;
  after: CopyPanel[];
}

function questionOf(m: CopyMovement): Question | null {
  if (m.kind === 'turn') {
    return { id: m.id, to: m.to, task: m.task, only_after: m.only_after ?? null, panel: m.panel, choice: Boolean(m.choice), answers: m.replies, fallback: m.fallback, after: m.after ?? [] };
  }
  if (m.kind !== 'solve' || m.mechanic !== 'choix' || !m.to) return null;
  return {
    id: m.id,
    to: m.to,
    task: m.task ?? null,
    only_after: m.only_after ?? null,
    panel: { kind: 'panel', id: `${m.id}.prompt`, in_frame: [m.to], lines: m.prompt ? [{ who: m.to, say: m.prompt }] : [] },
    choice: true,
    answers: m.options.map((x) => ({ id: x.id, examples: [x.label.a2, ...(x.examples ?? [])], beats: x.beats })),
    fallback: null,
    after: [],
  };
}

const panel = (id: string, lines: StoryLine[]): StoryPanel => ({ kind: 'panel', id, lines });

/**
 * T1 day a without the engine: the page from the copy; an answer takes the reply whose example it
 * repeats, else the turn's fallback; talk is read by the quarter's own patterns (`agency.respond`).
 * For the standalone page and the tests only: the app always plays the journey.
 */
export class OfflineStory implements Story {
  readonly page: StoryPage;
  readonly replayable = true;
  /** what the learner did that is not an answer, in order (the tests read it) */
  readonly gestures: Gesture[] = [];
  private copy: Copy;
  private o: Resolved;
  private state: () => Record<string, Value>;
  private routes: Record<string, string> = {};
  private talking: { who: CastId; used: string[]; slipped: boolean; turns: number } | null = null;

  constructor(opts: CopyOptions & { state?: () => Record<string, Value> } = {}, copy: Copy = T1A_COPY) {
    this.copy = copy;
    this.o = { level: opts.level ?? 'a2', native: opts.native ?? 'en' };
    this.state = opts.state ?? (() => ({}));
    this.page = pageOfCopy(copy, this.o);
  }

  private turn(turnId: string): Question | null {
    const m = this.copy.movements.find((x) => x.id === turnId);
    return m ? questionOf(m) : null;
  }

  /** The reply anything else reads as; on a choice, the first option (its example only). */
  private fallback(q: Question) {
    return q.answers.find((r) => r.id === q.fallback) ?? q.answers[0];
  }

  async ask(turnId: string): Promise<Ask> {
    const q = this.turn(turnId);
    return { task: q?.task?.[this.o.native] ?? null, help: q?.choice ? ['words', 'example'] : ['example'] };
  }

  async answer(turnId: string, text: string): Promise<Heard> {
    const q = this.turn(turnId);
    if (!q) return { turn: turnId, reply: null, beats: [], next: null, closing: true, mend: null };
    const typed = fold(text).replace(/[.!?…\s]+$/, '');
    const reply = q.answers.find((r) => r.examples.some((e) => fold(e).replace(/[.!?…\s]+$/, '') === typed)) ?? (q.fallback ? this.fallback(q) : null);
    if (!reply) {
      // a choice the quarter could not read: asked again, as the engine asks
      const prompt = q.panel.lines?.[0];
      const again = prompt ? [{ ...prompt, say: { ...prompt.say, a2: `Pardon ? ${prompt.say.a2}`, b1: undefined } }] : [];
      return { turn: turnId, reply: null, beats: [panelOf({ kind: 'panel', id: `${turnId}.ask_again`, lines: again }, this.o)], next: turnId, closing: false, mend: null };
    }
    this.routes[turnId] = reply.id;
    const next = nextTurn(this.page, turnId, this.routes);
    return {
      turn: turnId,
      reply: reply.id,
      beats: [...reply.beats, ...q.after].map((b) => panelOf(b, this.o)),
      next,
      closing: next === null,
      mend: null,
    };
  }

  async help(turnId: string, step: HelpStep): Promise<Help | null> {
    const q = this.turn(turnId);
    if (!q) return null;
    if (step === 'example') return { step, text: this.fallback(q).examples[0] ?? null, native: null, words: [] };
    if (step === 'words' && q.choice) return { step, text: null, native: null, words: q.answers.map((r) => r.examples[0]).filter(Boolean) };
    return null;
  }

  async gesture(g: Gesture): Promise<Answered | null> {
    this.gestures.push(g);
    const none: Answered = { beats: [], chips: [], heard: null, learned: [], sets: {} };
    if (g.storylet === 'walk_out') return { ...none, sets: { 'user.walked_out': true } };
    if (g.storylet === 'margaux_text') {
      const [id, words] = g.text === undefined ? ['margaux_text.text', TEXT_SUITCASE.say] : ['margaux_text.answer', TEXT_SUITCASE.answer];
      return { ...none, beats: [panel(id, [{ ...said(TEXT_SUITCASE.who, words, this.o), kind: 'sms' }])], sets: { 'user.stayed_away': true } };
    }
    const who = g.to as CastId;
    if (!TALKERS[who]) return null;
    const state = this.state();
    if (g.text === undefined) {
      this.talking = { who, used: [], slipped: false, turns: 0 };
      const h = helloOf(who, state);
      return { ...none, beats: [panel(`talk.${who}.hello`, [said(who, h.say, this.o, { mood: h.mood })])], chips: chipsFor(who, state) };
    }
    if (this.talking?.who !== who) this.talking = { who, used: [], slipped: false, turns: 0 };
    const t = this.talking;
    const r = respond(who, g.text, state, { slipped: t.slipped, turn: t.turns, used: t.used });
    const reg = registerOf(g.text);
    if (reg && reg !== TALKERS[who].register) t.slipped = true;
    t.turns++;
    if (r.intent) t.used.push(r.intent);
    const learned: Learned[] = [];
    const sets: Record<string, Value> = {};
    for (const e of r.effects) {
      if (e.kind === 'learn') learned.push({ id: e.key, text_fr: e.words.fr, text_native: e.words[this.o.native] });
      if (e.kind === 'fact') sets[e.key] = e.value;
    }
    return {
      beats: [panel(`talk.${who}.${r.intent ?? 'fallback'}`, r.lines.map((l) => said(who, l.say, this.o, { mood: l.mood, direction: l.direction })))],
      chips: chipsFor(who, { ...state, ...sets }, t.used),
      heard: r.intent,
      learned,
      sets,
    };
  }

  async close() {
    // nothing to tell anyone
  }
}

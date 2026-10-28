/**
 * Le Quartier · today's journey, as the story the quarter stages (`story.ts`).
 *
 * The page is the one the server resolved for this learner, on the scene step (`prompt.stage`).
 * The answers go through the Feuilleton's own attempts endpoint and the help through its help
 * endpoint, which records each step before it is shown; the gestures go to `POST …/choices`. The
 * journey moves on the way the Feuilleton moves it: the scene is acknowledged when its first
 * question is asked, each answer is an attempt on the respond step, and once the hook has played
 * the talk and the ending are acknowledged, so the rest of the day (the words, the grammar) follows
 * in the Feuilleton's own steps.
 *
 * The stage fields are additive to journey contract v1, so a server that does not stage leaves
 * them out: they are read here, defensively, field by field.
 */
import { createMutationKeyring, runMutation } from '@/components/atelier-v2/journey/journey-requests';
import { currentStepOf, isReconcileCode, journeyAwaitsFinish, resolutionAwaitsStory } from '@/components/atelier-v2/journey/journey-state';
import dailyJourneyService, { journeyErrorCode, mutationId } from '@/services/daily-journey';
import type { AttemptResult, HelpKind, JourneySnapshot, RespondStep, SceneStep, StoryletChoiceResult } from '@/types/daily-journey';

import type { Value } from './memory';
import { STAGED_DAYS, nextTurn } from './story';
import type {
  Answered,
  Ask,
  Gesture,
  Heard,
  Help,
  HelpStep,
  Learned,
  Mend,
  Story,
  StoryLine,
  StoryMovement,
  StoryPage,
  StoryPanel,
  StoryPerson,
  StoryTurn,
  Storylet,
  StoryletLine,
} from './story';

/* ------------------------------------------------------------------------------------------ */
/* the page, off the wire                                                                     */
/* ------------------------------------------------------------------------------------------ */

type Raw = Record<string, unknown>;

const isRaw = (x: unknown): x is Raw => Boolean(x) && typeof x === 'object' && !Array.isArray(x);
const str = (x: unknown): string | null => (typeof x === 'string' ? x : null);
const strs = (x: unknown): string[] => (Array.isArray(x) ? x.filter((s): s is string => typeof s === 'string') : []);
const some = <T>(x: T | null): x is T => x !== null;

function lineOf(x: unknown, who: string | null = null): StoryLine | null {
  if (!isRaw(x) || typeof x.text_fr !== 'string') return null;
  return {
    who: str(x.who) ?? who ?? 'caption',
    name: str(x.name),
    kind: str(x.kind),
    mood: str(x.mood),
    direction: str(x.direction),
    text_fr: x.text_fr,
    text_native: str(x.text_native),
  };
}

function panelOf(x: unknown): StoryPanel | null {
  if (!isRaw(x) || typeof x.id !== 'string') return null;
  return {
    kind: 'panel',
    id: x.id,
    visual: str(x.visual),
    location_id: str(x.location_id),
    in_frame: strs(x.in_frame),
    silence: x.silence === true,
    lines: Array.isArray(x.lines) ? x.lines.map((l) => lineOf(l)).filter(some) : [],
  };
}

function onlyAfterOf(x: unknown): Record<string, string[]> | null {
  if (!isRaw(x)) return null;
  const out: Record<string, string[]> = {};
  for (const [turn, replies] of Object.entries(x)) out[turn] = strs(replies);
  return Object.keys(out).length ? out : null;
}

function movementOf(x: unknown): StoryMovement | null {
  if (!isRaw(x) || typeof x.id !== 'string') return null;
  if (x.kind === 'turn') {
    const panel = panelOf(x.panel);
    if (!panel || typeof x.to !== 'string') return null;
    return {
      kind: 'turn',
      id: x.id,
      to: x.to,
      to_name: str(x.to_name),
      task_native: str(x.task_native),
      choice: x.choice === true,
      only_after: onlyAfterOf(x.only_after),
      panel,
    };
  }
  if (x.kind === 'hook') {
    const panel = panelOf(x.panel);
    return panel ? { kind: 'hook', id: x.id, role: str(x.role), panel } : null;
  }
  // a solve the quarter does not ask arrives as the panels the page plays for it
  return x.kind === 'panel' ? panelOf(x) : null;
}

function storyletLineOf(x: unknown, who: string | null): StoryletLine | null {
  const line = lineOf(x, who);
  if (!line || !isRaw(x)) return null;
  return { ...line, role: str(x.role) ?? '', during: str(x.during), from_fr: str(x.from_fr) };
}

function personOf(x: unknown): StoryPerson | null {
  if (!isRaw(x) || typeof x.who !== 'string') return null;
  return {
    who: x.who,
    name: str(x.name) ?? x.who,
    register: x.register === 'vous' ? 'vous' : 'tu',
    hello: lineOf(x.hello, x.who),
    bye: lineOf(x.bye, x.who),
  };
}

function storyletOf(x: unknown): Storylet | null {
  if (!isRaw(x) || typeof x.id !== 'string') return null;
  const who = str(x.who);
  return {
    id: x.id,
    cue: str(x.cue) ?? x.id,
    who,
    after_seconds: typeof x.after_seconds === 'number' ? x.after_seconds : null,
    lines: Array.isArray(x.lines) ? x.lines.map((l) => storyletLineOf(l, who)).filter(some) : [],
    chips: strs(x.chips),
    people: Array.isArray(x.people) ? x.people.map(personOf).filter(some) : [],
  };
}

/** The scene step's `stage`, as the quarter reads a page; `null` when it is not one. */
export function pageOfStage(x: unknown): StoryPage | null {
  if (!isRaw(x) || typeof x.key !== 'string' || !Array.isArray(x.movements)) return null;
  const movements = x.movements.map(movementOf).filter(some);
  if (!movements.length) return null;
  const [segment, day] = x.key.split('.');
  return {
    season_id: str(x.season_id) ?? 's1',
    segment: str(x.segment) ?? segment ?? '',
    day: str(x.day) ?? day ?? '',
    key: x.key,
    number: typeof x.number === 'number' ? x.number : null,
    title_fr: str(x.title_fr) ?? '',
    story_date_fr: str(x.story_date_fr),
    location_id: str(x.location_id),
    can_do_native: str(x.can_do_native),
    movements,
    storylets: Array.isArray(x.storylets) ? x.storylets.map(storyletOf).filter(some) : [],
  };
}

/** Today's page, from the journey's scene step; `null` off an authored season page. */
export function pageOfJourney(journey: JourneySnapshot | null): StoryPage | null {
  const scene = journey?.steps.find((s): s is SceneStep => s.kind === 'scene');
  return scene ? pageOfStage(scene.prompt.stage) : null;
}

/** Today's page when it is a day the quarter has blocking for, wherever the day stands; else `null`. */
export function stagedPageOf(journey: JourneySnapshot | null): StoryPage | null {
  const page = pageOfJourney(journey);
  return page && STAGED_DAYS.includes(page.key) ? page : null;
}

/** The talk of the scene: the first respond step after it. */
function talkOf(journey: JourneySnapshot): RespondStep | null {
  const scene = journey.steps.find((s) => s.kind === 'scene');
  const talks = journey.steps
    .filter((s): s is RespondStep => s.kind === 'respond' && (!scene || s.ordinal > scene.ordinal))
    .sort((a, b) => a.ordinal - b.ordinal);
  return talks[0] ?? null;
}

/* ------------------------------------------------------------------------------------------ */
/* what /quartier does with today                                                             */
/* ------------------------------------------------------------------------------------------ */

export type Today =
  /** no journey yet: start today's */
  | { kind: 'start' }
  /** the server is writing the day */
  | { kind: 'preparing' }
  /** the scene is ahead: the quarter plays it */
  | { kind: 'play'; page: StoryPage }
  /** the scene is played: the rest of the day is the Feuilleton's steps */
  | { kind: 'practice'; page: StoryPage }
  /** the day is over: its recap */
  | { kind: 'done' }
  /** the Feuilleton reads it: a day the quarter has no blocking for, or one left mid-question */
  | { kind: 'handoff'; why: 'day' | 'midway' | 'unavailable' };

export function todayOf(journey: JourneySnapshot | null): Today {
  if (!journey) return { kind: 'start' };
  if (journey.status === 'preparing') return { kind: 'preparing' };
  if (journey.status === 'completed' || journey.status === 'ended_early') return { kind: 'done' };
  if (journey.status === 'unavailable') return { kind: 'handoff', why: 'unavailable' };
  const page = stagedPageOf(journey);
  const scene = journey.steps.find((s) => s.kind === 'scene');
  if (!page || !scene) return { kind: 'handoff', why: 'day' };
  const step = currentStepOf(journey);
  if (!step) return { kind: 'practice', page };
  // steps before the scene are the Feuilleton's, in its order
  if (step.ordinal < scene.ordinal) return { kind: 'handoff', why: 'day' };
  if (step.kind === 'scene') return { kind: 'play', page };
  const talk = talkOf(journey);
  if (talk && step.id === talk.id && step.status !== 'completed') {
    // a question already answered here was left behind: where the talk stands is the Feuilleton's
    return talk.prompt.turn_index === 0 ? { kind: 'play', page } : { kind: 'handoff', why: 'midway' };
  }
  return { kind: 'practice', page };
}

/* ------------------------------------------------------------------------------------------ */
/* the story, through today's journey                                                         */
/* ------------------------------------------------------------------------------------------ */

export type JourneyService = Pick<typeof dailyJourneyService, 'get' | 'resume' | 'advance' | 'attempt' | 'help' | 'finish' | 'choose'>;

export interface JourneyStoryOptions {
  service?: JourneyService;
  /** each snapshot the engine hands back */
  onSnapshot?: (journey: JourneySnapshot) => void;
  /** the journey moved on without the scene (another device, a reload mid-question) */
  onLost?: () => void;
  /** injected for tests */
  sleep?: (ms: number) => Promise<void>;
}

/** The journey moved on without the scene: nothing the quarter shows of it is current any more. */
export class StoryLost extends Error {}

/** How often an answer whose grading did not happen is sent again before the sheet says so. */
const GRADING_TRIES = 3;

const realSleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

interface Mutation<T> {
  intent: string;
  send: (id: string, revision: number) => Promise<T>;
  /** the snapshot it hands back; none when nothing was applied, and the key is kept for the retry */
  journey: (value: T) => JourneySnapshot | null;
  /** after a conflict, with the journey read again: send again, nothing left to do, or the scene is lost */
  check?: () => 'again' | 'done' | 'lost';
}

function answeredOf(x: StoryletChoiceResult): Answered {
  const sets: Record<string, Value> = {};
  for (const [key, value] of Object.entries(isRaw(x.sets) ? x.sets : {})) {
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') sets[key] = value;
  }
  const learned: Learned[] = (Array.isArray(x.learned) ? x.learned : [])
    .filter((l) => isRaw(l) && typeof l.id === 'string' && typeof l.text_fr === 'string')
    .map((l) => ({ id: l.id, text_fr: l.text_fr, text_native: str(l.text_native) }));
  return {
    beats: (Array.isArray(x.beats) ? x.beats : []).map(panelOf).filter(some),
    chips: strs(x.chips),
    heard: str(x.heard),
    learned,
    sets,
    people: Array.isArray(x.people) ? x.people.map(personOf).filter(some) : null,
  };
}

export class JourneyStory implements Story {
  readonly page: StoryPage;
  readonly replayable = false;
  private journey: JourneySnapshot;
  private service: JourneyService;
  private opts: JourneyStoryOptions;
  private sleep: (ms: number) => Promise<void>;
  private keys = createMutationKeyring();
  private queue: Promise<unknown> = Promise.resolve();
  private closing: Promise<void> | null = null;
  /** the question the engine asks next: the first while nothing is answered, then the one its last answer named */
  private asking: string | null;

  constructor(journey: JourneySnapshot, page: StoryPage, opts: JourneyStoryOptions = {}) {
    this.journey = journey;
    this.page = page;
    this.opts = opts;
    this.service = opts.service ?? dailyJourneyService;
    this.sleep = opts.sleep ?? realSleep;
    // a talk already past its first question is not one this story can pick up (`todayOf`)
    const talk = talkOf(journey);
    this.asking = talk && talk.status !== 'completed' && talk.prompt.turn_index === 0 ? nextTurn(page, null, {}) : null;
  }

  /** The journey as the engine last handed it back. */
  get snapshot(): JourneySnapshot {
    return this.journey;
  }

  private take(journey: JourneySnapshot) {
    if (journey.id !== this.journey.id || journey.revision < this.journey.revision) return;
    this.journey = journey;
    this.opts.onSnapshot?.(journey);
  }

  private lost() {
    this.opts.onLost?.();
    return new StoryLost('the journey moved on without the scene');
  }

  /** One journey mutation at a time: each needs the revision the last one handed back. */
  private serial<T>(fn: () => Promise<T>): Promise<T> {
    const run = this.queue.then(fn, fn);
    this.queue = run.catch(() => undefined);
    return run;
  }

  /**
   * A mutation against the journey as it stands. The same intent sent again at the same revision
   * goes out under the same key (a replay, never a second record); a conflict reads the journey
   * again and, while the intent still holds, sends it under a new one.
   */
  private async mutate<T>(m: Mutation<T>): Promise<T | null> {
    for (let tries = 0; ; tries++) {
      const revision = this.journey.revision;
      const key = `${m.intent}@${revision}`;
      const outcome = await runMutation({ mutationId: this.keys.idFor(key), invoke: (id) => m.send(id, revision), sleep: this.sleep });
      if (outcome.ok) {
        const journey = m.journey(outcome.value);
        if (journey) {
          this.keys.release(key);
          this.take(journey);
        }
        return outcome.value;
      }
      const code = outcome.detail?.code ?? journeyErrorCode(outcome.error);
      if (!isReconcileCode(code ?? null) || tries >= 2) throw outcome.error ?? new Error(code ?? 'journey_error');
      this.keys.release(key);
      this.take(await this.service.get(this.journey.id));
      const next = m.check?.() ?? 'again';
      if (next === 'done') return null;
      if (next === 'lost') throw this.lost();
    }
  }

  private advance(stepId: string) {
    return this.mutate({
      intent: `advance:${stepId}`,
      send: (id, revision) => this.service.advance(this.journey.id, { expectedRevision: revision, currentStepId: stepId, mutationId: id }),
      journey: (s) => s,
      check: () => (currentStepOf(this.journey)?.id === stepId ? 'again' : 'done'),
    });
  }

  /** The question open on the talk: a paused day is resumed, the scene acknowledged. */
  private async talk(): Promise<RespondStep> {
    if (this.journey.status === 'paused') {
      await this.mutate({
        intent: 'resume',
        send: (id, revision) => this.service.resume(this.journey.id, { expectedRevision: revision, mutationId: id }),
        journey: (s) => s,
        check: () => (this.journey.status === 'paused' ? 'again' : 'done'),
      });
    }
    let step = currentStepOf(this.journey);
    if (step?.kind === 'scene') {
      await this.advance(step.id);
      step = currentStepOf(this.journey);
    }
    const talk = talkOf(this.journey);
    if (!step || !talk || step.id !== talk.id || step.status === 'completed') throw this.lost();
    return step as RespondStep;
  }

  /**
   * The talk, on this question. A question the engine is not asking (the scene played again after
   * a ride across the map, once its talk had moved on) is never answered here: the Feuilleton has it.
   */
  private async question(turnId: string): Promise<RespondStep> {
    if (turnId !== this.asking) throw this.lost();
    return this.talk();
  }

  /** Still the same question: the talk is current and has not moved past this turn. */
  private open(stepId: string, turnIndex: number) {
    const step = currentStepOf(this.journey);
    return step?.id === stepId && step.kind === 'respond' && step.status !== 'completed' && step.prompt.turn_index === turnIndex;
  }

  private turn(turnId: string): StoryTurn | null {
    return this.page.movements.find((m): m is StoryTurn => m.kind === 'turn' && m.id === turnId) ?? null;
  }

  /** Words to build the answer with: the choice's options on a choice, else the talk's targets. */
  private words(turn: StoryTurn | null, step: RespondStep) {
    const p = step.prompt;
    const from = turn?.choice && p.choices.length ? p.choices.map((c) => c.label_fr) : p.targets.filter((t) => !t.concept_title).map((t) => t.label_fr);
    return Array.from(new Set(from.filter(Boolean)));
  }

  async ask(turnId: string): Promise<Ask> {
    const turn = this.turn(turnId);
    const step = await this.serial(() => this.question(turnId));
    const p = step.prompt;
    const help: HelpStep[] = [];
    if (p.help_available.includes('hint')) help.push('hint');
    if (this.words(turn, step).length) help.push('words');
    if (p.help_available.includes('suggested_response')) help.push('example');
    return { task: turn?.task_native ?? p.objective_native ?? null, help };
  }

  async answer(turnId: string, text: string): Promise<Heard> {
    return this.serial(async () => {
      const step = await this.question(turnId);
      const at = step.prompt.turn_index;
      const send = () =>
        this.mutate<AttemptResult>({
          intent: `attempt:${step.id}:${at}:${text}`,
          send: (id, revision) => this.service.attempt(this.journey.id, step.id, { expectedRevision: revision, input: { mode: 'text', text }, mutationId: id }),
          journey: (r) => (r.pending ? null : r.journey),
          check: () => (this.open(step.id, at) ? 'again' : 'lost'),
        });
      let result = await send();
      // grading that did not happen is sent again as it was: the same body, the same key
      for (let i = 1; result?.pending && i < GRADING_TRIES; i++) {
        await this.sleep(1500);
        result = await send();
      }
      if (!result || result.pending) throw new Error('grading_pending');
      const heard = this.heardOf(turnId, result);
      this.asking = heard.next;
      return heard;
    });
  }

  private heardOf(turnId: string, r: AttemptResult): Heard {
    const c = r.correction;
    const mend: Mend | null = c && c.span_fr && c.corrected_fr && c.span_fr !== c.corrected_fr ? { span: c.span_fr, corrected: c.corrected_fr, note: c.note_native || null } : null;
    const stage: unknown = r.stage;
    if (isRaw(stage) && typeof stage.turn_id === 'string') {
      return {
        turn: stage.turn_id,
        reply: str(stage.reply_id),
        beats: (Array.isArray(stage.beats) ? stage.beats : []).map(panelOf).filter(some),
        next: str(stage.next_turn_id),
        closing: stage.closing === true,
        mend,
      };
    }
    // a server that does not stage its answers: the room says what the engine said, and the
    // question stays open until the engine has heard enough
    const to = this.turn(turnId)?.to ?? 'caption';
    const lines: StoryLine[] = (r.character_lines ?? []).map((l) => ({ who: l.speaker_id ?? to, name: l.speaker_name, kind: 'speech', text_fr: l.text_fr }));
    const next = r.next_turn ? turnId : null;
    return { turn: turnId, reply: null, beats: lines.length ? [{ kind: 'panel', id: `${turnId}.said`, lines }] : [], next, closing: next === null, mend };
  }

  async help(turnId: string, step: HelpStep): Promise<Help | null> {
    const turn = this.turn(turnId);
    if (step === 'words') {
      const talk = await this.serial(() => this.question(turnId));
      const words = this.words(turn, talk);
      return words.length ? { step, text: null, native: null, words } : null;
    }
    const kind: HelpKind = step === 'hint' ? 'hint' : 'suggested_response';
    return this.serial(async () => {
      const talk = await this.question(turnId);
      if (!talk.prompt.help_available.includes(kind)) return null;
      const at = talk.prompt.turn_index;
      const r = await this.mutate({
        intent: `help:${talk.id}:${at}:${kind}`,
        send: (id, revision) => this.service.help(this.journey.id, talk.id, { expectedRevision: revision, helpKind: kind, mutationId: id }),
        journey: (h) => h.journey,
        check: () => (this.open(talk.id, at) ? 'again' : 'lost'),
      });
      return r ? { step, text: r.content_fr, native: r.content_native, words: [] } : null;
    });
  }

  async gesture(g: Gesture): Promise<Answered | null> {
    const outcome = await runMutation({
      mutationId: mutationId(),
      invoke: (id) =>
        this.service.choose(this.journey.id, {
          storyletId: g.storylet,
          mutationId: id,
          at: g.storylet === 'walk_out' ? g.at : undefined,
          to: g.storylet === 'talk' ? g.to : undefined,
          text: g.storylet === 'walk_out' ? undefined : g.text,
        }),
      sleep: this.sleep,
    }).catch(() => null);
    return outcome?.ok ? answeredOf(outcome.value) : null;
  }

  /**
   * The hook has played: the talk is acknowledged, then the ending (unless it is still being
   * written, which the Feuilleton waits for), and a day with nothing after it is finished. Once.
   */
  close(): Promise<void> {
    this.closing ??= this.serial(async () => {
      for (let i = 0; i < 4 && this.journey.status === 'active'; i++) {
        const step = currentStepOf(this.journey);
        const talk = talkOf(this.journey);
        const ours =
          step?.kind === 'scene' ||
          (step && talk && step.id === talk.id && step.status === 'completed') ||
          (step?.kind === 'resolution' && !resolutionAwaitsStory(step));
        if (!step || !ours) break;
        await this.advance(step.id);
      }
      if (journeyAwaitsFinish(this.journey)) {
        await this.mutate({
          intent: 'finish',
          send: (id, revision) => this.service.finish(this.journey.id, { expectedRevision: revision, finishKind: 'complete', mutationId: id }),
          journey: (s) => s,
          check: () => (journeyAwaitsFinish(this.journey) ? 'again' : 'done'),
        });
      }
    }).catch((e) => {
      this.closing = null;
      throw e;
    });
    return this.closing;
  }
}

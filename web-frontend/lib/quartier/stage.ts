/**
 * Le Quartier · the stage director: T1, day a («Le mauvais accueil»), played in the quarter.
 *
 * The words are the season's own (`scenes/t1-a.json`, copied from app/data by
 * `scripts/quartier/sync-scene.mjs`); nothing here rewrites a line. What the director adds is the
 * blocking the Feuilleton's panels describe: where you stand, who walks where, who turns to look,
 * what lies on the zinc. It publishes what the screen should show (a caption, a line, a goal, the
 * answer sheet) and waits for you: a tap to go on, a walk to the door, a reply in French.
 *
 * Replies are read by a small local reader (`classify`) that knows the two turns of this day; in
 * the app the same choice comes from the backend's classifier, with the same reply ids.
 */
import { Euler, Matrix4, Quaternion, Vector3 } from 'three';
import type { Object3D } from 'three';

import type { Hit, Quartier } from './engine';
import { CHAIR, MARKS } from './mistral';
import { PLAN } from './quai';
import scene from './scenes/t1-a.json';

/* ------------------------------------------------------------------------------------------ */
/* the scene's shape (as in app/data/season/s1/t1.json)                                       */
/* ------------------------------------------------------------------------------------------ */

interface Say {
  a2: string;
  b1?: string;
  native?: { en?: string; de?: string };
}

interface Line {
  who: string;
  mood?: string;
  direction?: string;
  say: Say;
}

interface Panel {
  kind: 'panel';
  id: string;
  visual?: string;
  lines?: Line[];
  silence?: boolean;
}

interface Reply {
  id: string;
  label: string;
  examples: string[];
  clumsy?: boolean;
  beats: Panel[];
}

interface Turn {
  kind: 'turn';
  id: string;
  to: string;
  panel: Panel;
  task: { en: string; de: string; fr: string };
  fallback: string;
  replies: Reply[];
}

interface Hook {
  kind: 'hook';
  id: string;
  panel: Panel;
}

type Movement = Panel | Turn | Hook;

export interface SceneData {
  episode: string;
  number: number;
  episode_title_fr: string;
  title_fr: string;
  story_date_fr: string;
  can_do: { en: string; de: string; fr: string };
  movements: Movement[];
}

export const T1A = scene as unknown as SceneData;

/* ------------------------------------------------------------------------------------------ */
/* what the screen shows                                                                      */
/* ------------------------------------------------------------------------------------------ */

export type Level = 'a2' | 'b1';
export type Native = 'en' | 'de';
export type Phase = 'title' | 'scene' | 'answer' | 'end' | 'roam';

/** The short keys the app's stylesheets use for each person's accent (`--char-*`). */
export type CharKey = 'gus' | 'marin' | 'lila' | 'margaux' | 'camille' | 'toi';

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
  char: CharKey;
  to: string;
  task: string;
  taskNative: string;
  chips: string[];
}

export interface StageUi {
  phase: Phase;
  caption: { text: string; native: string | null } | null;
  speech: SpeechUi | null;
  /** your reply, as Toi's balloon, while the room takes it in */
  you: string | null;
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
}

export type Cue = 'bell' | 'door' | 'key' | 'cup' | 'chair' | 'paper';

export interface StageOptions {
  level?: Level;
  native?: Native;
  /** sounds the director asks for (the screen plays them, `audio.ts`) */
  onCue?: (cue: Cue) => void;
}

const PEOPLE: Record<string, { char: CharKey; name: string }> = {
  augustin_de_roncourt: { char: 'gus', name: 'Gus' },
  marin_leveque: { char: 'marin', name: 'Marin' },
  lila_bonnet: { char: 'lila', name: 'Lila' },
  margaux_barman: { char: 'margaux', name: 'Margaux' },
  camille_marchand: { char: 'camille', name: 'Camille' },
  toi: { char: 'toi', name: 'Toi' },
};

/** The app's moods as the troupe's faces (the same table as `MOOD_EXPRESSION` in CastActor). */
const MOOD_EXPRESSION: Record<string, string> = {
  neutral: 'neutre',
  happy: 'joie',
  cross: 'fache',
  moved: 'emu',
  surprised: 'surprise',
  cold: 'neutre',
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
};

/** The day's movements this director stages, in order. */
export const STAGED = ['a.p1', 'a.p2', 'a.p3', 'a.p4', 'a.p5', 'a.turn1', 'a.turn2', 'a.hook'];

class Cancelled extends Error {}

/* ------------------------------------------------------------------------------------------ */
/* reading a reply                                                                            */
/* ------------------------------------------------------------------------------------------ */

const fold = (s: string) =>
  s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[’`]/g, "'");

const first = (t: string, re: RegExp) => {
  const m = re.exec(t);
  return m ? m.index : -1;
};

/**
 * Which of a turn's replies a French answer is closest to. A prototype's reader: a handful of
 * patterns per turn, enough for the chips and for what a beginner types; it never refuses an
 * answer, it falls back the way the season says to.
 */
export function classify(turnId: string, text: string): string {
  const t = fold(text);
  const halting = /\.\.\.|…/.test(text);
  if (turnId === 'a.turn1') {
    const family = first(t, /grand ?-?(mere|pere|maman)|mamie|famille|petite?-?(fille|fils|enfant)|(ma|mon) [^.]*odile|odile[^.]*(ma|mon) |heritier|heritiere/);
    const sell = first(t, /vend|vente|a moi|proprietaire|mon appartement|l'appartement est/);
    if (family >= 0 && (sell < 0 || family < sell)) return halting ? 'c' : 'a';
    if (sell >= 0) return halting ? 'c' : 'b';
    if (/\bet vous\b|vous etes qui|qui etes-vous|\bet toi\b|qui es-tu|c'est qui|et lui/.test(t)) return 'd';
    return 'c';
  }
  if (turnId === 'a.turn2') {
    if (/sais pas|aucune idee|peut-etre|j'hesite|\bbof\b|pas ce soir|^non\b/.test(t)) return 'dont_know';
    if (/vend|je pars|partir|semaine|quitter|rentrer/.test(t)) return 'sell_and_leave';
    if (/demain|peur|plus tard/.test(t)) return 'clumsy';
    if (/ce soir|\boui\b|maintenant|tout de suite|je monte|j'y vais|aujourd'hui/.test(t)) return 'tonight';
    return 'dont_know';
  }
  return 'a';
}

/* ------------------------------------------------------------------------------------------ */
/* the director                                                                               */
/* ------------------------------------------------------------------------------------------ */

const BLANK: StageUi = {
  phase: 'title',
  caption: null,
  speech: null,
  you: null,
  goal: null,
  answer: null,
  silent: false,
  waitingTap: false,
  beat: null,
  progress: 0,
  met: null,
};

export class Stage {
  ui: StageUi = { ...BLANK };
  private listeners = new Set<(ui: StageUi) => void>();
  private gen = 0;
  private tapWait: { gen: number; resolve: () => void } | null = null;
  private answerWait: { gen: number; resolve: (text: string) => void } | null = null;
  private goalAt: { to: Vector3; radius: number; look: Vector3 } | null = null;
  private goalResolve: (() => void) | null = null;
  private wayAt = 0;
  private stopTick: () => void;
  private stopHit: () => void;
  private level: Level;
  private native: Native;
  private onCue?: (cue: Cue) => void;
  private moves = new Map<string, Movement>();
  /** where the key lies on the zinc, in front of you, and how it lies */
  private keyHome = new Vector3();
  private keyFlat = new Quaternion().setFromEuler(new Euler(0, -0.4, 0));
  /** lets go of whatever you are holding up */
  private holding: (() => void) | null = null;

  constructor(private q: Quartier, private data: SceneData = T1A, opts: StageOptions = {}) {
    this.level = opts.level ?? 'a2';
    this.native = opts.native ?? 'en';
    this.onCue = opts.onCue;
    data.movements.forEach((m) => this.moves.set(m.id, m));
    this.stopTick = q.onTick(() => this.tick());
    this.stopHit = q.on((hit) => this.hit(hit));
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

  private set(patch: Partial<StageUi>) {
    this.ui = { ...this.ui, ...patch };
    this.listeners.forEach((fn) => fn(this.ui));
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
    const w = this.tapWait;
    if (w) {
      this.tapWait = null;
      w.resolve();
    }
  }

  /** Your reply to the current turn. */
  answer(text: string) {
    const w = this.answerWait;
    if (w && text.trim()) {
      this.answerWait = null;
      w.resolve(text.trim());
    }
  }

  /** «Y aller»: walk me to where I am going. */
  go() {
    const g = this.goalAt;
    if (g) void this.q.walkTo(g.to);
  }

  /** «Directement»: put me there. */
  skipWalk() {
    const g = this.goalAt;
    if (g) {
      this.q.place(g.to, g.look);
      this.checkGoal(true);
    }
  }

  replay() {
    void this.play();
  }

  /** After the end card: the quarter is yours to walk. */
  roam() {
    this.gen++;
    this.clearWaits();
    // you put the key ring down where it was
    this.letGo();
    const key = this.prop('key');
    if (key) {
      key.position.copy(this.keyHome);
      key.quaternion.copy(this.keyFlat);
    }
    this.q.frozen = false;
    this.q.look(null);
    this.q.lens(60);
    this.q.showWay(null);
    this.set({ ...BLANK, phase: 'roam', progress: 1 });
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
    if (this.tapWait) {
      this.tap();
      return;
    }
    const phase = this.ui.phase;
    if (phase === 'roam') {
      if (hit.kind === 'person') {
        const f = this.q.troupe.get(hit.key);
        f?.hop();
        this.onCue?.('paper');
        const who = PEOPLE[hit.key];
        if (who) this.set({ met: { char: who.char, name: who.name, at: performance.now() } });
      } else if (hit.kind === 'ground') {
        void this.q.walkTo(hit.point);
      }
      return;
    }
    if (phase === 'scene' && this.goalAt) {
      if (hit.kind === 'ground') void this.q.walkTo(hit.point);
      else if (hit.kind === 'spot' || hit.kind === 'person') this.go();
    }
  }

  private tick() {
    if (!this.goalAt) return;
    const now = performance.now();
    if (now - this.wayAt > 900 && !this.q.walking) {
      this.wayAt = now;
      this.q.showWay(this.goalAt.to);
    }
    this.checkGoal(false);
  }

  private checkGoal(force: boolean) {
    const g = this.goalAt;
    if (!g) return;
    const d = Math.hypot(this.q.feet.x - g.to.x, this.q.feet.z - g.to.z);
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
    this.goalAt = null;
    this.goalResolve = null;
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
    this.q.frozen = false;
    this.q.look(null);
    this.goalAt = { to: to.clone(), radius, look };
    this.wayAt = 0;
    this.set({ goal: { label: g.label, native: g.native[this.native] } });
    await new Promise<void>((resolve) => {
      this.goalResolve = resolve;
    });
    this.alive(gen);
    this.set({ goal: null });
    this.q.frozen = true;
  }

  private async replyFrom(gen: number, turn: Turn) {
    const who = PEOPLE[turn.to] ?? PEOPLE.toi;
    const chips = turn.replies.map((r) => r.examples[0]).filter(Boolean);
    this.set({
      phase: 'answer',
      answer: { id: turn.id, char: who.char, to: who.name, task: turn.task.fr, taskNative: turn.task[this.native], chips },
    });
    const text = await new Promise<string>((resolve) => {
      this.answerWait = { gen, resolve };
    });
    this.alive(gen);
    this.set({ phase: 'scene', answer: null, you: text, speech: null });
    return text;
  }

  /* ---- people ----------------------------------------------------------------------------- */

  private fig(key: string) {
    return this.q.troupe.get(key);
  }

  private faceOf(key: string) {
    return this.fig(key)?.face() ?? MARKS.zincTop.clone();
  }

  private text(say: Say) {
    return (this.level === 'b1' && say.b1) || say.a2;
  }

  /** One line: the speaker's face and mood, your head turns to them, the card waits for a tap. */
  private async speak(gen: number, line: Line) {
    if (line.who === 'caption') {
      this.set({ caption: { text: this.text(line.say), native: line.say.native?.[this.native] ?? null }, speech: null });
      await this.waitTap(gen);
      return;
    }
    const who = PEOPLE[line.who] ?? { char: 'toi' as CharKey, name: line.who };
    const f = this.fig(line.who);
    const text = this.text(line.say);
    if (f) {
      const expression = MOOD_EXPRESSION[line.mood ?? 'neutral'] ?? 'neutre';
      if (expression !== f.expression) void this.q.troupe.face(line.who, expression, f.gesture);
      f.talk(0.9 + text.length * 0.045);
      this.q.look(f.face(), 3.4);
    }
    const name = line.who === 'camille_marchand' && !this.camilleNamed ? 'Quelqu’un' : who.name;
    if (line.who === 'camille_marchand') this.camilleNamed = true;
    this.set({
      caption: null,
      speech: { who: line.who, char: who.char, name, text, native: line.say.native?.[this.native] ?? null, direction: line.direction ?? null },
    });
    await this.waitTap(gen);
  }

  private camilleNamed = false;

  private async lines(gen: number, panel: Panel, before?: (line: Line, i: number) => Promise<void> | void) {
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
    this.camilleNamed = false;
  }

  private progress(id: string) {
    const i = this.data.movements.findIndex((m) => m.id === id);
    this.set({ beat: id, progress: Math.max(0, i) / this.data.movements.length });
  }

  private async play() {
    const gen = ++this.gen;
    this.clearWaits();
    this.reset();
    this.set({ ...BLANK, phase: 'scene' });
    try {
      await this.p1(gen);
      await this.p2(gen);
      await this.p3(gen);
      await this.p4(gen);
      await this.p5(gen);
      await this.turn1(gen);
      await this.turn2(gen);
      await this.hook(gen);
      this.q.frozen = false;
      this.set({ phase: 'end', speech: null, caption: null, silent: false, progress: 1 });
    } catch (e) {
      if (!(e instanceof Cancelled)) throw e;
    }
  }

  private panelOf(id: string): Panel {
    const m = this.moves.get(id);
    if (!m) return { kind: 'panel', id, lines: [] };
    return m.kind === 'panel' ? m : m.panel;
  }

  /** a.p1 · the quai in the rain; the neon; through the window, the booth. You go in. */
  private async p1(gen: number) {
    this.progress('a.p1');
    const q = this.q;
    q.frozen = true;
    // your eyes go to the window where Gus is holding forth, then they are yours
    q.look(new Vector3(-28.6, 2.6, -14.5), 0.9);
    await this.lines(gen, this.panelOf('a.p1'));
    this.set({ caption: null });
    await this.reach(gen, 'door', MARKS.doorOut, 1.25, new Vector3(-30.5, 1.7, -10.5));
    // the bell, the warmth; two steps in and the door swings shut behind you
    q.openDoor(true);
    this.onCue?.('bell');
    q.look(this.faceOf('augustin_de_roncourt'), 1.6);
    await this.wait(gen, 0.7);
    q.frozen = false;
    await q.walkTo(MARKS.doorIn, 1.15);
    this.alive(gen);
    q.frozen = true;
    q.openDoor(false);
    this.onCue?.('door');
  }

  /** a.p2 · heads turn; Gus freezes on the bench mid-story. */
  private async p2(gen: number) {
    this.progress('a.p2');
    for (const k of ['augustin_de_roncourt', 'marin_leveque', 'lila_bonnet', 'margaux_barman']) {
      this.fig(k)?.hop();
      await this.wait(gen, 0.09);
    }
    await this.lines(gen, this.panelOf('a.p2'));
  }

  /** a.p3 · silent: the zinc, close. The envelope, the key ring with its cicada. Margaux stops. */
  private async p3(gen: number) {
    this.progress('a.p3');
    this.set({ speech: null });
    await this.reach(gen, 'zinc', MARKS.atZinc, 0.75, MARKS.zincTop);
    const q = this.q;
    q.look(this.keyHome, 2.6);
    q.lens(42);
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
    q.lens(60);
  }

  /** a.p4 · Gus steps down from the bench and crosses the room, bowing far too deep. */
  private async p4(gen: number) {
    this.progress('a.p4');
    const gus = this.fig('augustin_de_roncourt');
    const panel = this.panelOf('a.p4');
    if (gus) {
      void this.q.troupe.face('augustin_de_roncourt', 'neutre', null);
      this.q.look(gus.face(), 2.2);
      const follow = this.q.onTick(() => this.q.look(gus.face(), 2.2));
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
  private async p5(gen: number) {
    this.progress('a.p5');
    const panel = this.panelOf('a.p5');
    const marin = this.fig('marin_leveque');
    if (marin) {
      marin.hop();
      this.q.look(marin.face(), 2.4);
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
        this.q.look(new Vector3(this.q.feet.x, 0.1, this.q.feet.z).add(this.towardRoom(0.5)), 2.6);
        await this.wait(gen, 0.9);
      }
    });
  }

  private towardRoom(len: number) {
    const d = new Vector3(-31.0 - this.q.feet.x, 0, -15.5 - this.q.feet.z).normalize();
    return d.multiplyScalar(len);
  }

  private async turnBeats(gen: number, turn: Turn, replyId: string) {
    const reply = turn.replies.find((r) => r.id === replyId) ?? turn.replies.find((r) => r.id === turn.fallback) ?? turn.replies[0];
    this.set({ beat: `${turn.id}.${reply.id}` });
    await this.wait(gen, 1.2);
    this.set({ you: null });
    for (const beat of reply.beats) await this.beat(gen, beat);
  }

  /** a.turn1 · Gus at the zinc beside you: who are you, exactly? */
  private async turn1(gen: number) {
    this.progress('a.turn1');
    const turn = this.moves.get('a.turn1') as Turn;
    const gus = this.fig('augustin_de_roncourt');
    if (gus) {
      const follow = this.q.onTick(() => this.q.look(gus.face(), 2.0));
      await this.walkFig(gen, 'augustin_de_roncourt', MARKS.zincBeside, 0.9);
      follow();
    }
    await this.lines(gen, turn.panel);
    const text = await this.replyFrom(gen, turn);
    await this.turnBeats(gen, turn, classify(turn.id, text));
  }

  /** a.turn2 · Margaux turns the cicada in her fingers: are you going up? */
  private async turn2(gen: number) {
    this.progress('a.turn2');
    const turn = this.moves.get('a.turn2') as Turn;
    const key = this.prop('key');
    const margaux = this.fig('margaux_barman');
    if (key && margaux) {
      // she picks the key ring up and holds it out, at her side, the cicada toward you
      this.onCue?.('key');
      const hand = margaux.pos.clone().add(new Vector3(0.42, 0.98, 0.3));
      const turn = this.facing(hand.clone().sub(this.q.camera.position), 0.3);
      await this.carry(gen, key, 0.8, () => ({ pos: hand, turn }));
    }
    this.fig('marin_leveque')?.bow(0.32, 1.6);
    this.fig('lila_bonnet')?.bow(0.3, 1.5);
    await this.lines(gen, turn.panel);
    const text = await this.replyFrom(gen, turn);
    await this.turnBeats(gen, turn, classify(turn.id, text));
    // whatever was said, the key ends up back on the zinc in front of you
    await this.keyBack(gen);
  }

  /** a.hook · the bell again: someone in a wet helmet holds up a key. Two keys, one door. */
  private async hook(gen: number) {
    this.progress('a.hook');
    const panel = this.panelOf('a.hook');
    const q = this.q;
    q.openDoor(true);
    this.onCue?.('bell');
    const camille = this.fig('camille_marchand');
    if (camille) {
      camille.place(MARKS.doorway);
      camille.visible = true;
    }
    for (const k of ['augustin_de_roncourt', 'marin_leveque', 'lila_bonnet']) this.fig(k)?.hop();
    q.look(this.faceOf('camille_marchand'), 2.4);
    await this.wait(gen, 1.0);
    await this.lines(gen, panel, async (line) => {
      if (line.who === 'augustin_de_roncourt') {
        const gus = this.fig('augustin_de_roncourt');
        if (gus) {
          gus.seat = 0;
          // he stops short of her and to one side, so you still see her past him
          const stop = this.before(MARKS.doorway, MARKS.atZinc, 1.5);
          const d = MARKS.doorway.clone().sub(MARKS.atZinc).setY(0).normalize();
          stop.addScaledVector(new Vector3(-d.z, 0, d.x), 0.95);
          await this.walkFig(gen, 'augustin_de_roncourt', stop, 1.2);
          gus.bow(0.95, 1.6);
          this.onCue?.('paper');
        }
      }
      if (line.who === 'caption') {
        // two keys in one frame: yours, held up in front of you; hers, in the doorway
        q.look(this.faceOf('camille_marchand'), 2.0);
        q.lens(52);
        const key = this.prop('key');
        if (key) {
          this.onCue?.('key');
          await this.carry(gen, key, 0.7, () => this.inView(-0.42, 0.42, 0.5));
          this.hold(key, -0.42, 0.42, 0.5);
        }
      }
    });
    q.openDoor(false);
    q.lens(60);
  }

  /** One beat of a reply: lines, or a silent panel acted out by its id. */
  private async beat(gen: number, b: Panel) {
    const id = b.id;
    if (SILENT_BEATS.cup.test(id)) {
      // Margaux sets a café crème in front of you; nobody ordered it
      await this.silent(gen, 2.4, async () => {
        const margaux = this.fig('margaux_barman');
        if (margaux) this.q.look(margaux.face(), 2.4);
        await this.wait(gen, 0.6);
        const cup = this.prop('cup');
        if (cup) {
          const to = new Vector3(MARKS.atZinc.x - 1.0, MARKS.zincTop.y + 0.002, MARKS.atZinc.z - 0.36);
          const from = to.clone().add(new Vector3(-0.55, 0, 0));
          cup.visible = true;
          this.onCue?.('cup');
          this.q.look(to, 2.2);
          await this.tween(gen, 0.7, (t) => cup.position.lerpVectors(from, to, t));
        }
      });
      return;
    }
    if (SILENT_BEATS.deflate.test(id)) {
      // Gus's triumph goes out of him; the room looks from him to you
      void this.q.troupe.face('augustin_de_roncourt', 'neutre', null);
      await this.silent(gen, 2.2, async () => {
        const gus = this.fig('augustin_de_roncourt');
        if (gus) {
          this.q.look(gus.face(), 2.2);
          await this.tween(gen, 0.9, (t) => (gus.seat = 0.08 * t));
        }
      });
      return;
    }
    if (/\.c\.r1$/.test(id)) {
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
    await this.lines(gen, b, async (line) => {
      if (line.who === 'augustin_de_roncourt' && line.direction === 'sitting down slowly') {
        const gus = this.fig('augustin_de_roncourt');
        if (gus) await this.tween(gen, 1.2, (t) => (gus.seat = 0.2 * t));
      }
      if (line.direction?.startsWith('triumphant') || line.direction === 'delighted') this.fig(line.who)?.hop();
    });
  }
}
